import base64
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from morph_ui.paths import ProjectPaths, UiError
from morph_ui.settings import SettingsStore


class OllamaSettingsTests(unittest.TestCase):
    def setUp(self):
        base = Path(__file__).resolve().parents[2] / 'temp/morph-ui-tests'
        base.mkdir(parents=True, exist_ok=True)
        temporary = tempfile.TemporaryDirectory(prefix='ollama-settings-', dir=base)
        self.addCleanup(temporary.cleanup)
        self.paths = ProjectPaths(temporary.name)
        self.store = SettingsStore(self.paths)
        self.path = self.paths.data / 'settings.json'

    def write_settings(self, config):
        raw = json.dumps(config, ensure_ascii=False, indent=2).replace('\n', '\r\n').encode('utf-8')
        self.path.write_bytes(raw)
        return raw

    def migrate(self):
        self.assertTrue(callable(getattr(self.store, 'migrate_to_ollama', None)),
                        'SettingsStore needs an explicit, backup-protected migration')
        return self.store.migrate_to_ollama()

    def backups(self):
        return list(self.paths.data.glob('settings-lmstudio-backup-*.json'))

    def test_first_read_uses_ollama_without_creating_settings(self):
        self.assertEqual(self.store.read_public(), {
            'provider': 'ollama', 'endpoint': 'http://127.0.0.1:11434',
            'model_key': '', 'instance_id': '', 'has_token': False,
        })
        self.assertFalse(self.path.exists())

    def test_read_legacy_settings_resets_provider_fields_only_in_memory(self):
        raw = self.write_settings({
            'provider': 'lmstudio', 'endpoint': 'http://127.0.0.1:1234',
            'model_key': 'old/model', 'instance_id': 'old-instance',
            'token_protected': base64.b64encode(b'legacy ciphertext').decode('ascii'),
            'theme': {'contrast': 'high'},
        })
        self.assertEqual(self.store.read_public(), {
            'provider': 'ollama', 'endpoint': 'http://127.0.0.1:11434',
            'model_key': '', 'instance_id': '', 'has_token': False,
        })
        self.assertEqual(self.store.read()['theme'], {'contrast': 'high'})
        self.assertEqual(self.store.token(), '')
        self.assertEqual(self.path.read_bytes(), raw)
        self.assertEqual(self.backups(), [])

    def test_explicit_migration_preserves_exact_legacy_bytes_and_unrelated_keys(self):
        raw = self.write_settings({
            'provider': 'lmstudio', 'endpoint': 'http://127.0.0.1:1234',
            'model_key': 'old/model', 'instance_id': 'old-instance',
            'token_protected': base64.b64encode(b'legacy ciphertext').decode('ascii'),
            'theme': {'contrast': 'high'},
        })
        self.migrate()
        self.assertEqual(len(self.backups()), 1)
        self.assertEqual(self.backups()[0].read_bytes(), raw)
        saved = json.loads(self.path.read_text(encoding='utf-8'))
        self.assertEqual(saved, {
            'provider': 'ollama', 'endpoint': 'http://127.0.0.1:11434',
            'model_key': '', 'instance_id': '', 'theme': {'contrast': 'high'},
        })
        self.migrate()
        self.assertEqual(len(self.backups()), 1)

    def test_missing_legacy_provider_is_migrated_with_backup(self):
        raw = self.write_settings({'endpoint': 'http://localhost:1234', 'model_key': 'old/model'})
        self.migrate()
        self.assertEqual(self.backups()[0].read_bytes(), raw)
        self.assertEqual(self.store.read()['provider'], 'ollama')
        self.assertEqual(self.store.read()['model_key'], '')

    def test_existing_backup_is_never_replaced(self):
        previous = self.paths.data / 'settings-lmstudio-backup-previous.json'
        previous.write_bytes(b'previous saved configuration')
        raw = self.write_settings({'provider': 'lmstudio'})
        self.migrate()
        self.assertEqual(previous.read_bytes(), b'previous saved configuration')
        self.assertEqual(len(self.backups()), 2)
        self.assertIn(raw, [item.read_bytes() for item in self.backups()])

    def test_existing_ollama_settings_and_token_are_preserved_without_backup(self):
        raw = self.write_settings({
            'provider': 'ollama', 'endpoint': 'http://127.0.0.1:23111',
            'model_key': 'own-model:latest', 'instance_id': 'own-model:latest',
            'token_protected': base64.b64encode(b'protected token').decode('ascii'),
        })
        self.migrate()
        self.migrate()
        self.assertEqual(self.path.read_bytes(), raw)
        self.assertEqual(self.backups(), [])
        self.assertEqual(self.store.read_public(), {
            'provider': 'ollama', 'endpoint': 'http://127.0.0.1:23111',
            'model_key': 'own-model:latest', 'instance_id': 'own-model:latest', 'has_token': True,
        })

    def test_new_installation_migration_does_not_create_a_legacy_backup(self):
        self.migrate()
        self.assertEqual(self.backups(), [])
        self.assertEqual(self.store.read()['provider'], 'ollama')

    def test_corrupt_and_unsupported_settings_are_not_overwritten(self):
        for raw in [b'{broken', b'[]', b'null', b'{"provider":"other"}',
                    b'{"provider":null}', b'{"endpoint":null}',
                    b'{"provider":"ollama","model_key":[]}',
                    b'{"provider":"ollama","token_protected":{}}']:
            with self.subTest(raw=raw):
                self.path.write_bytes(raw)
                for operation in [self.store.read, self.migrate, lambda: self.store.save({'model_key': 'new'})]:
                    with self.assertRaises(UiError):
                        operation()
                    self.assertEqual(self.path.read_bytes(), raw)
                    self.assertEqual(self.backups(), [])

    def test_atomic_replace_failure_keeps_original_and_complete_backup(self):
        raw = self.write_settings({'provider': 'lmstudio', 'endpoint': 'http://127.0.0.1:1234'})
        with patch('morph_ui.settings.os.replace', side_effect=OSError('synthetic replace failure')):
            with self.assertRaises(UiError):
                self.migrate()
        self.assertEqual(self.path.read_bytes(), raw)
        self.assertEqual(len(self.backups()), 1)
        self.assertEqual(self.backups()[0].read_bytes(), raw)
        self.assertEqual(list(self.paths.data.glob('settings-*.tmp')), [])

    def test_saving_legacy_settings_first_preserves_a_backup(self):
        raw = self.write_settings({'provider': 'lmstudio', 'model_key': 'old/model'})
        self.store.save({'endpoint': 'http://127.0.0.1:22434'})
        self.assertEqual(len(self.backups()), 1)
        self.assertEqual(self.backups()[0].read_bytes(), raw)
        self.assertEqual(self.store.read()['provider'], 'ollama')

    def test_endpoint_change_clears_old_server_identifiers(self):
        self.write_settings({
            'provider': 'ollama', 'endpoint': 'http://127.0.0.1:11434',
            'model_key': 'old/model', 'instance_id': 'old-instance',
        })
        self.store.save({'endpoint': 'http://127.0.0.1:22434'})
        self.assertEqual(self.store.read()['model_key'], '')
        self.assertEqual(self.store.read()['instance_id'], '')

    def test_endpoint_change_keeps_only_identifiers_explicitly_selected_for_new_server(self):
        self.write_settings({
            'provider': 'ollama', 'endpoint': 'http://127.0.0.1:11434',
            'model_key': 'old/model', 'instance_id': 'old-instance',
        })
        self.store.save({'endpoint': 'http://127.0.0.1:22434', 'model_key': 'new/model'})
        self.assertEqual(self.store.read()['model_key'], 'new/model')
        self.assertEqual(self.store.read()['instance_id'], '')

    def test_equivalent_endpoint_does_not_clear_current_selection(self):
        self.write_settings({
            'provider': 'ollama', 'endpoint': 'http://127.0.0.1:11434',
            'model_key': 'own-model', 'instance_id': 'own-model',
        })
        self.store.save({'endpoint': 'http://localhost:11434/'})
        self.assertEqual(self.store.read()['model_key'], 'own-model')
        self.assertEqual(self.store.read()['instance_id'], 'own-model')

    def test_saved_ollama_token_is_protected_and_private(self):
        self.store.save({'endpoint': 'http://127.0.0.1:1234', 'token': 'own-ollama-test-secret'})
        self.assertEqual(self.store.token(), 'own-ollama-test-secret')
        self.assertNotIn('own-ollama-test-secret', self.path.read_text(encoding='utf-8'))
        self.assertNotIn('token_protected', self.store.read_public())
        self.assertTrue(self.store.read_public()['has_token'])
        self.assertEqual(self.store.read_public()['provider'], 'ollama')


if __name__ == '__main__':
    unittest.main()
