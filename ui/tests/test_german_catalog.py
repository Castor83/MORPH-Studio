import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from morph_ui.catalog import Catalog, ENTRIES
from morph_ui.paths import ProjectPaths, UiError
from support import Sandbox


class GermanCatalogTests(unittest.TestCase):
    def setUp(self):
        self.paths = ProjectPaths(Sandbox(self).root)
        self.catalog = Catalog(self.paths)

    def test_german_prompt_defaults_leave_saved_workflows_unchanged(self):
        phrases = {'sdxl': 'Tasse', 'kontext': 'Tasse', 'wan': 'Bewegung',
                   'qwen21': 'Tasse', 'krea2': 'Hemd'}
        for key, phrase in phrases.items():
            with self.subTest(tool=key):
                original = self.catalog.graph(key)
                fields = self.catalog.controls(key)
                self.assertNotIn('Englisch', fields['prompt']['label'])
                self.assertIn(phrase.casefold(), fields['prompt']['default'].casefold())
                self.assertEqual(self.catalog.graph(key), original)

    def test_proposal_entries_do_not_check_readiness_or_expose_model_paths(self):
        with patch.object(self.catalog, 'readiness', side_effect=AssertionError('No readiness')):
            entries = self.catalog.proposal_entries()
        self.assertEqual([item['id'] for item in entries], list(ENTRIES))
        for entry in entries:
            self.assertEqual(set(entry), {'id', 'name', 'description', 'roles', 'controls'})
            self.assertFalse(any(spec['kind'] == 'model' for spec in entry['controls'].values()))

    def test_planning_can_validate_settings_without_requiring_model_files(self):
        with patch.object(self.catalog.library, 'resolve', side_effect=AssertionError('No asset resolution')):
            values = self.catalog.validate_controls('sdxl', {'width': 512}, validate_models=False)
        self.assertEqual(values['width'], 512)
        with self.assertRaises(UiError):
            self.catalog.validate_controls('sdxl', {'width': 17}, validate_models=False)

    def test_planning_still_rejects_unsafe_model_paths(self):
        for name in ['checkpoints/../private.safetensors', 'checkpoints/C:/outside',
                     'checkpoints/a\\other', 'checkpoints//other', 'checkpoints/a\x00b']:
            with self.subTest(name=name), self.assertRaises(UiError):
                self.catalog.validate_controls('sdxl', {'image_model': name}, validate_models=False)

    def test_execution_still_requires_real_model_assets(self):
        with patch.object(self.catalog.library, 'resolve', side_effect=UiError('model_missing', 'Fehlt')):
            with self.assertRaises(UiError):
                self.catalog.validate_controls('sdxl', {'width': 512})

    def test_oversized_integer_is_reported_as_invalid_control(self):
        with self.assertRaises(UiError):
            self.catalog.validate_controls('sdxl', {'width': 10 ** 400}, validate_models=False)


if __name__ == '__main__':
    unittest.main()
