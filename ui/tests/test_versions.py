from contextlib import closing
import io
import json
import sqlite3
import sys
import tempfile
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from morph_ui.files import FileStore
from morph_ui.paths import ProjectPaths, UiError
try:
    from morph_ui.versions import VersionStore
except ModuleNotFoundError:
    VersionStore = None


def picture(color=(170, 40, 20)):
    stream = io.BytesIO()
    Image.new('RGB', (8, 6), color).save(stream, format='PNG')
    return stream.getvalue()


class VersionTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(VersionStore, 'Die persistente Bildhistorie fehlt noch.')
        base = Path(__file__).resolve().parents[2] / 'temp/morph-ui-tests'
        base.mkdir(parents=True, exist_ok=True)
        temporary = tempfile.TemporaryDirectory(prefix='versions-', dir=base)
        self.addCleanup(temporary.cleanup)
        self.paths = ProjectPaths(Path(temporary.name))
        self.files = FileStore(self.paths)
        self.addCleanup(self.files.close)
        self.original = self.files.save_upload(picture(), 'original.png')
        self.store = VersionStore(self.paths, self.files)
        self.addCleanup(self.store.close)

    def project(self):
        return self.store.create_project(str(uuid.uuid4()), self.original['id'], 'Testbild')

    def output(self, color=(20, 50, 170)):
        path = self.paths.output / (uuid.uuid4().hex + '.png')
        path.write_bytes(picture(color))
        return self.files.register_output(path)

    def job(self, project, parent, output=None):
        return {'id': str(uuid.uuid4()), 'state': 'completed',
                'project_id': project['id'], 'parent_version_id': parent,
                'workflow_id': 'kontext', 'controls': {'prompt': 'Nur die Kleidung ändern.', 'seed': 27},
                'graph': {'1': {'class_type': 'UNETLoader', 'inputs': {'unet_name': 'example.safetensors'}}},
                'model_components': [{'name': 'example.safetensors', 'loader': 'UNETLoader'}],
                'outputs': [output or self.output()]}

    def test_first_schema_has_consistent_backup_without_new_tables(self):
        backups = list((self.paths.data / 'backups').glob('*.sqlite3'))
        self.assertEqual(len(backups), 1)
        with closing(sqlite3.connect(backups[0])) as backup:
            self.assertEqual(backup.execute('PRAGMA integrity_check').fetchone()[0], 'ok')
            names = {row[0] for row in backup.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            self.assertIn('media', names)
            self.assertNotIn('image_projects', names)
            self.assertEqual(backup.execute('SELECT COUNT(*) FROM media').fetchone()[0], 1)
        reopened = VersionStore(self.paths, self.files)
        self.addCleanup(reopened.close)
        self.assertEqual(len(list((self.paths.data / 'backups').glob('*.sqlite3'))), 1)

    def test_original_two_edits_and_branch_survive_reopening(self):
        project = self.project()
        original = project['original_version_id']
        first = self.store.record_job_outputs(self.job(project, original))[0]
        second = self.store.record_job_outputs(self.job(project, first['id']))[0]
        branch = self.store.record_job_outputs(self.job(project, first['id'], self.output((30, 130, 60))))[0]
        reopened = VersionStore(self.paths, self.files)
        self.addCleanup(reopened.close)
        restored = reopened.get_project(project['id'])
        self.assertEqual(len(restored['versions']), 4)
        self.assertEqual({v['id']: v['parent_version_id'] for v in restored['versions']},
                         {original: None, first['id']: original, second['id']: first['id'], branch['id']: first['id']})
        self.assertEqual(reopened.list_projects()[0]['original_version_id'], original)
        self.assertEqual(self.files.resolve(self.original['id']).read_bytes(), picture())

    def test_project_request_is_idempotent_but_payload_mismatch_is_rejected(self):
        request = str(uuid.uuid4())
        first = self.store.create_project(request, self.original['id'], 'Mein Bild')
        second = self.store.create_project(request, self.original['id'], 'Mein Bild')
        self.assertEqual(first['id'], second['id'])
        self.assertEqual(first['original_version_id'], second['original_version_id'])
        with self.assertRaises(UiError):
            self.store.create_project(request, self.original['id'], 'Anderer Name')
        with self.assertRaises(UiError):
            self.store.create_project(request, self.output()['id'], 'Mein Bild')
        self.assertEqual(len(self.store.list_projects()), 1)

    def test_original_snapshot_is_independent_of_uploaded_file(self):
        project = self.project()
        version = self.store.get_version(project['original_version_id'])
        frozen = self.files.resolve(version['media']['id'])
        self.assertIn('MORPH-UI/versions/' + project['id'], frozen.as_posix())
        self.files.resolve(self.original['id']).write_bytes(picture((1, 2, 3)))
        self.assertEqual(frozen.read_bytes(), picture())
        self.assertEqual(self.store.get_version(version['id'])['sha256'], version['sha256'])

    def test_prepare_input_is_explicit_idempotent_and_bound_to_selected_version(self):
        project = self.project()
        version_id = project['original_version_id']
        prepared = self.store.prepare_input(version_id)
        again = self.store.prepare_input(version_id)
        self.assertEqual(prepared, again)
        self.assertEqual(prepared['image']['category'], 'input')
        self.assertNotEqual(prepared['image']['id'], self.original['id'])
        self.assertEqual(self.files.resolve(prepared['image']['id']).read_bytes(), picture())
        self.assertEqual(self.store.validate_job_context(project['id'], version_id, 'kontext',
                         {'image': prepared['image']['id']}),
                         {'project_id': project['id'], 'parent_version_id': version_id})
        self.assertEqual(self.store.validate_job_context(None, None, 'sdxl', {}), {})

    def test_parent_project_input_and_workflow_mismatch_are_rejected(self):
        first, other = self.project(), self.project()
        root = first['original_version_id']
        prepared = self.store.prepare_input(root)['image']['id']
        wrong = self.files.save_upload(picture((1, 2, 3)), 'wrong.png')['id']
        for args in [(first['id'], None, 'kontext', {'image': prepared}),
                     (other['id'], root, 'kontext', {'image': prepared}),
                     (first['id'], root, 'kontext', {'image': wrong}),
                     (first['id'], root, 'sdxl', {}),
                     ('../outside', root, 'kontext', {'image': prepared})]:
            with self.subTest(args=args), self.assertRaises(UiError):
                self.store.validate_job_context(*args)
        self.assertEqual(self.store.validate_job_context(first['id'], root, 'reactor', {'target': prepared}),
                         {'project_id': first['id'], 'parent_version_id': root})

    def test_mutated_version_and_prepared_input_are_not_silently_overwritten(self):
        project = self.project()
        root = project['original_version_id']
        prepared = self.store.prepare_input(root)
        self.files.resolve(prepared['image']['id']).write_bytes(picture((1, 2, 3)))
        with self.assertRaises(UiError):
            self.store.prepare_input(root)
        version = self.store.get_version(root)
        path = self.files.resolve(version['media']['id'])
        changed = picture((4, 5, 6))
        path.write_bytes(changed)
        with self.assertRaises(UiError):
            self.store.get_version(root)
        self.assertEqual(path.read_bytes(), changed)

    def test_job_versions_are_idempotent_and_metadata_is_a_snapshot(self):
        project = self.project()
        job = self.job(project, project['original_version_id'])
        first = self.store.record_job_outputs(job)
        again = self.store.record_job_outputs(job)
        self.assertEqual(first, again)
        self.assertEqual(len(self.store.get_project(project['id'])['versions']), 2)
        self.assertEqual(first[0]['metadata']['controls']['seed'], 27)
        self.assertEqual(first[0]['metadata']['graph'], job['graph'])
        self.assertEqual(first[0]['metadata']['model_components'], job['model_components'])
        self.assertEqual(first[0]['metadata']['prompt'], job['controls']['prompt'])
        job['controls']['seed'] = 28
        self.assertEqual(self.store.get_version(first[0]['id'])['metadata']['controls']['seed'], 27)
        with self.assertRaises(UiError):
            self.store.record_job_outputs(job)

    def test_old_incomplete_failed_cancelled_and_video_jobs_make_no_versions(self):
        self.assertEqual(self.store.record_job_outputs({'state': 'completed', 'outputs': []}), [])
        project = self.project()
        for state in ['queued', 'running', 'error', 'cancelled', 'unknown']:
            job = self.job(project, project['original_version_id'])
            job['state'] = state
            self.assertEqual(self.store.record_job_outputs(job), [])
        path = self.paths.output / 'clip.mp4'
        path.write_bytes(b'not decoded: video is outside the image history')
        video = self.files.register_output(path)
        self.assertEqual(self.store.record_job_outputs(self.job(project, project['original_version_id'], video)), [])
        self.assertEqual(len(self.store.get_project(project['id'])['versions']), 1)

    def test_output_copy_and_media_registration_recover_after_metadata_failure(self):
        project = self.project()
        job = self.job(project, project['original_version_id'])
        original = self.files.register_output
        copied = []
        def registered_then_crash(path):
            result = original(path)
            copied.append(result)
            raise RuntimeError('simulierter Absturz nach Mediencommit')
        with patch.object(self.files, 'register_output', side_effect=registered_then_crash):
            with self.assertRaisesRegex(RuntimeError, 'Mediencommit'):
                self.store.record_job_outputs(job)
        self.assertEqual(len(self.store.get_project(project['id'])['versions']), 1)
        recovered = self.store.record_job_outputs(job)
        self.assertEqual(recovered[0]['media']['id'], copied[0]['id'])
        self.assertEqual(len(list((self.paths.output / 'MORPH-UI/versions' / project['id']).glob('*.png'))), 2)

    def test_multiple_outputs_commit_together_and_ignore_duplicate_references(self):
        project = self.project()
        one, two = self.output(), self.output((20, 180, 70))
        job = self.job(project, project['original_version_id'], one)
        job['outputs'] = [one, one, two]
        versions = self.store.record_job_outputs(job)
        self.assertEqual(len(versions), 2)
        self.assertEqual(len(self.store.record_job_outputs(job)), 2)
        self.assertEqual(len(self.store.get_project(project['id'])['versions']), 3)

    def test_new_tables_enforce_parent_belongs_to_the_same_project(self):
        first, other = self.project(), self.project()
        job = self.job(first, first['original_version_id'])
        child = self.store.record_job_outputs(job)[0]
        with closing(sqlite3.connect(self.paths.database)) as db:
            db.execute('PRAGMA foreign_keys=ON')
            with self.assertRaises(sqlite3.IntegrityError):
                db.execute('UPDATE image_versions SET parent_version_id=? WHERE id=?',
                           (other['original_version_id'], child['id']))

    def test_committed_version_replays_when_its_temporary_raw_import_is_gone(self):
        project = self.project()
        job = self.job(project, project['original_version_id'])
        recorded = self.store.record_job_outputs(job)
        raw = self.files.resolve(job['outputs'][0]['id'])
        raw.rename(raw.with_suffix('.moved-fixture'))
        replayed = self.store.record_job_outputs(job)
        self.assertEqual(replayed, recorded)
        self.assertEqual(self.files.resolve(replayed[0]['media']['id']).read_bytes(), picture((20, 50, 170)))

    def test_input_copy_is_reused_after_media_commit_before_version_link(self):
        project = self.project()
        version_id = project['original_version_id']
        real_db = self.store.db
        class FailedLink:
            def execute(self, sql, parameters=()):
                if sql.startswith('UPDATE image_versions SET input_media_id='):
                    raise sqlite3.OperationalError('simulierter Linkfehler')
                return real_db.execute(sql, parameters)
            def __enter__(self):
                real_db.__enter__()
                return self
            def __exit__(self, *args):
                return real_db.__exit__(*args)
        with patch.object(self.store, 'db', FailedLink()):
            with self.assertRaisesRegex(sqlite3.OperationalError, 'Linkfehler'):
                self.store.prepare_input(version_id)
        copied = self.files.db.execute("SELECT id FROM media WHERE category='input' AND id!=?",
                                       (self.original['id'],)).fetchall()
        self.assertEqual(len(copied), 1)
        prepared = self.store.prepare_input(version_id)
        self.assertEqual(prepared['image']['id'], copied[0][0])
        self.assertEqual(len(list(self.paths.input.rglob('*.png'))), 2)

    def test_stable_input_upload_reuses_a_complete_copy_without_a_media_row(self):
        stable_id = '3' * 32
        target = self.paths.input / ('morph-ui/' + stable_id + '.png')
        target.write_bytes(picture())
        saved = self.files.save_upload(picture(), 'copy.png', stable_id=stable_id)
        self.assertEqual(saved['id'], stable_id)
        self.assertEqual(self.files.resolve(saved['id']), target)
        self.assertEqual(self.files.save_upload(picture(), 'copy.png', stable_id=stable_id), saved)
        self.assertEqual(len(list(self.paths.input.rglob('*.png'))), 2)

    def test_stable_input_upload_refuses_different_bytes_or_another_media_owner(self):
        stable_id = '4' * 32
        saved = self.files.save_upload(picture(), 'copy.png', stable_id=stable_id)
        target = self.files.resolve(saved['id'])
        with self.assertRaises(UiError):
            self.files.save_upload(picture((1, 2, 3)), 'copy.png', stable_id=stable_id)
        self.assertEqual(target.read_bytes(), picture())
        with self.files.db:
            self.files.db.execute('UPDATE media SET id=? WHERE id=?', ('5' * 32, stable_id))
        with self.assertRaises(UiError):
            self.files.save_upload(picture(), 'copy.png', stable_id=stable_id)
        self.assertEqual(target.read_bytes(), picture())
        self.assertEqual(self.files.db.execute('SELECT COUNT(*) FROM media').fetchone()[0], 2)

    def test_failed_stable_input_write_can_be_retried_without_a_partial_final_file(self):
        stable_id = '6' * 32
        target = self.paths.input / ('morph-ui/' + stable_id + '.png')
        real_open = Path.open

        class FailedWrite:
            def __init__(self, output):
                self.output = output
            def __enter__(self):
                return self
            def __exit__(self, *args):
                self.output.close()
            def write(self, data):
                self.output.write(data[:12])
                raise OSError('Simulated disk full')

        def interrupted_open(path, mode='r', *args, **kwargs):
            output = real_open(path, mode, *args, **kwargs)
            return FailedWrite(output) if mode == 'xb' else output

        with patch.object(Path, 'open', interrupted_open):
            with self.assertRaises(OSError):
                self.files.save_upload(picture(), 'copy.png', stable_id=stable_id)
        self.assertFalse(target.exists(), 'A partial file must not occupy the stable final path')
        self.assertEqual(list(target.parent.glob('*.part')), [])
        saved = self.files.save_upload(picture(), 'copy.png', stable_id=stable_id)
        self.assertEqual(self.files.resolve(saved['id']).read_bytes(), picture())
        self.assertEqual(self.files.save_upload(picture(), 'copy.png', stable_id=stable_id), saved)


if __name__ == '__main__':
    unittest.main()
