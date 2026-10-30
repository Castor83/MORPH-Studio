import subprocess
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
try:
    from morph_ui.paths import ProjectPaths, UiError
    from morph_ui.catalog import Catalog
    from morph_ui.files import FileStore
except ModuleNotFoundError:
    Catalog = FileStore = None
from support import Sandbox, png

class CatalogFilesTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(Catalog, 'Workflow-Katalog noch nicht implementiert')
        self.assertIsNotNone(FileStore, 'Bildverwaltung noch nicht implementiert')
        self.box = Sandbox(self)
        self.paths = ProjectPaths(self.box.root)
        self.catalog = Catalog(self.paths)
        self.files = FileStore(self.paths)
        self.addCleanup(self.files.close)

    def image_name(self):
        return self.files.save_upload(png(), 'Ausgangsbild.png')['relative_path']

    def test_missing_and_wrong_image_roles_prevent_build(self):
        for images in [{}, {'source': self.image_name()}]:
            with self.assertRaises(UiError):
                self.catalog.build('kontext', {}, images)
        with self.assertRaises(UiError):
            self.catalog.build('reactor', {}, {'target': self.image_name()})

    def test_unsupported_parameter_cannot_change_graph(self):
        with self.assertRaises(UiError):
            self.catalog.build('sdxl', {'class_type': 'RunCommand'}, {})

    def test_graph_copy_uses_exact_image_and_preserves_template(self):
        original = (self.paths.workflows / 'LMStudio-Bildbearbeitung-Kontext-api.json').read_bytes()
        name = self.image_name()
        graph = self.catalog.build('kontext', {'prompt': 'Change only the mug color.', 'width': 768}, {'image': name})
        self.assertEqual(graph['4']['inputs']['image'], name)
        self.assertEqual(graph['7']['inputs']['text'], 'Change only the mug color.')
        self.assertEqual(graph['11']['inputs']['width'], 768)
        self.assertEqual((self.paths.workflows / 'LMStudio-Bildbearbeitung-Kontext-api.json').read_bytes(), original)

    def test_wan_dimensions_frames_and_both_frame_rates_are_consistent(self):
        name = self.image_name()
        graph = self.catalog.build('wan', {'width': 768, 'height': 512, 'frames': 81, 'base_fps': 23, 'output_fps': 30}, {'image': name})
        self.assertEqual(graph['131']['inputs']['value'], 768)
        self.assertEqual(graph['130']['inputs']['value'], 512)
        self.assertEqual(graph['226']['inputs']['frame_rate'], 23)
        self.assertEqual(graph['253']['inputs']['source_fps'], 23)
        for node in ['254','256']:
            self.assertEqual(graph[node]['inputs']['frame_rate'], 30)
        self.assertEqual(graph['253']['inputs']['target_fps'], 30)
        for controls in [{'frames': 82}, {'steps': 4, 'split': 4}, {'width': 513}, {'seed': True}]:
            with self.assertRaises(UiError):
                self.catalog.build('wan', controls, {'image': name})

    def test_missing_model_is_named_at_real_location(self):
        path = self.paths.models / 'vae/ae.safetensors'
        path.unlink()
        issues = self.catalog.readiness('kontext')
        self.assertTrue(any(x['path'] == str(path) and 'ae.safetensors' in x['message'] for x in issues))
        with self.assertRaises(UiError):
            self.catalog.build('kontext', {}, {'image': self.image_name()})

    def test_upload_preserves_bytes_and_original_uses_unique_name(self):
        original = self.paths.input / 'Original.png'
        original.write_bytes(png())
        saved = self.files.save_upload(original.read_bytes(), '../../Original.png')
        self.assertEqual(original.read_bytes(), png())
        self.assertEqual(self.files.resolve(saved['id']).read_bytes(), png())
        self.assertNotEqual(self.files.resolve(saved['id']), original)
        self.assertEqual(saved['name'], 'Original.png')
        other = FileStore(self.paths)
        self.addCleanup(other.close)
        self.assertEqual(other.resolve(saved['id']), self.files.resolve(saved['id']))

    def test_arbitrary_file_id_and_fake_image_are_rejected(self):
        for value in ['../Original.png', str(self.paths.input / 'Original.png')]:
            with self.assertRaises(UiError):
                self.files.resolve(value)
        with self.assertRaises(UiError):
            self.files.save_upload(b'<svg>not an image</svg>', 'fake.png')

    def test_registered_media_cannot_escape_through_junction(self):
        inside = self.paths.output / 'result'
        inside.mkdir()
        (inside / 'picture.png').write_bytes(png())
        item = self.files.register_output(inside / 'picture.png')
        inside.rename(self.paths.output / 'old-result')
        outside = self.box.base / 'outside'
        outside.mkdir()
        (outside / 'picture.png').write_bytes(png())
        command = "New-Item -ItemType Junction -Path '" + str(inside).replace("'", "''") + "' -Target '" + str(outside).replace("'", "''") + "' | Out-Null"
        subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-Command',command], check=True, creationflags=subprocess.CREATE_NO_WINDOW)
        self.addCleanup(lambda: inside.rmdir())
        with self.assertRaises(UiError):
            self.files.resolve(item['id'])

if __name__ == '__main__':
    unittest.main()
