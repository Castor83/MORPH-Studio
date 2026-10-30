import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from morph_ui.catalog import Catalog
from morph_ui.files import FileStore
from morph_ui.paths import ProjectPaths, UiError
from support import Sandbox, png


class KreaProfileTests(unittest.TestCase):
    def setUp(self):
        self.box = Sandbox(self)
        self.paths = ProjectPaths(self.box.root)
        self.catalog = Catalog(self.paths)
        self.files = FileStore(self.paths)
        self.addCleanup(self.files.close)
        self.template = self.paths.workflows / 'KREA2-SNOFS-Edit-20261015-api.json'

    def image_name(self):
        return self.files.save_upload(png(), 'Krea-Eingabe.png')['relative_path']

    def profile(self):
        entries = {entry['id']: entry for entry in self.catalog.list_entries()}
        self.assertIn('krea2', list(entries), 'KREA-2-Bildbearbeitung fehlt im Workflow-Katalog')
        return entries['krea2']

    def test_profile_requires_one_image_and_selects_only_matching_model_components(self):
        entry = self.profile()
        self.assertEqual(entry['name'], 'Bild mit KREA 2 bearbeiten')
        self.assertIn('SNOFS', entry['description'])
        self.assertEqual(entry['roles'], [{'id': 'image', 'label': 'Ausgangsbild'}])
        self.assertEqual(entry['issues'], [])
        self.assertIn('image_model', entry['controls'])
        self.assertIn('image_encoder', entry['controls'])
        self.assertEqual([x['name'] for x in entry['controls']['image_model']['options']], ['KREA 2 Edit SNOFS Merge Q5 - Krea2.gguf'])
        graph = self.catalog.build('krea2', {}, {'image': self.image_name()})
        self.assertEqual(graph['55']['inputs']['unet_name'], 'KREA 2 Edit SNOFS Merge Q5 - Krea2.gguf')
        self.assertEqual(graph['56']['inputs']['clip_name'], 'qwen3vl_4b_fp8_scaled.safetensors')
        self.assertEqual(graph['57']['inputs']['vae_name'], 'qwen_image_vae.safetensors')
        self.assertEqual(graph['79']['inputs']['ref_boost'], 1)

    def test_controls_reach_edit_graph_and_do_not_modify_template(self):
        self.profile()
        original = self.template.read_bytes()
        image = self.image_name()
        controls = {'prompt': 'Change only the shirt to green.', 'width': 640, 'height': 512,
                    'seed': 707, 'steps': 12, 'cfg': 1.5, 'ref_boost': 1.41}
        graph = self.catalog.build('krea2', controls, {'image': image})
        self.assertEqual(graph['72']['inputs']['image'], image)
        self.assertEqual(graph['84']['inputs']['prompt'], 'Change only the shirt to green.')
        self.assertEqual((graph['82']['inputs']['width'], graph['82']['inputs']['height']), (640, 512))
        self.assertEqual((graph['53']['inputs']['seed'], graph['53']['inputs']['steps'], graph['53']['inputs']['cfg']), (707, 12, 1.5))
        self.assertEqual(graph['79']['inputs']['ref_boost'], 1.41)
        self.assertEqual(graph['29']['inputs']['filename_prefix'], 'MORPH-UI/Krea2')
        self.assertEqual(self.template.read_bytes(), original)

    def test_both_groundings_use_same_input_and_preserve_tested_edit_links(self):
        self.profile()
        graph = self.catalog.build('krea2', {}, {'image': self.image_name()})
        for node in ['84', '85']:
            self.assertEqual(graph[node]['class_type'], 'Krea2EditGroundedEncode')
            self.assertEqual(graph[node]['inputs']['image'], ['72', 0])
            self.assertEqual(graph[node]['inputs']['grounding_px'], 768)
            self.assertEqual(graph[node]['inputs']['clip'], ['56', 0])
        self.assertEqual(graph['85']['inputs']['prompt'], '')
        self.assertEqual(graph['53']['inputs']['positive'], ['84', 0])
        self.assertEqual(graph['53']['inputs']['negative'], ['85', 0])
        self.assertEqual(graph['53']['inputs']['model'], ['79', 0])
        self.assertEqual(graph['79']['inputs']['source_image'], ['72', 0])
        self.assertEqual(graph['79']['inputs']['source_latent'], ['73', 0])
        self.assertEqual(graph['79']['inputs']['target_latent'], ['82', 0])
        self.assertEqual(graph['79']['inputs']['fit_mode'], 'fit')
        self.assertEqual(graph['79']['inputs']['ref_boost_a'], 1.0)
        self.assertFalse(any('lora' in node['class_type'].casefold() for node in graph.values()))

    def test_missing_or_empty_gguf_names_exact_required_file_and_blocks_build(self):
        self.profile()
        path = self.paths.models / 'diffusion_models/KREA 2 Edit SNOFS Merge Q5 - Krea2.gguf'
        for state in ['missing', 'empty']:
            with self.subTest(state=state):
                if state == 'missing':
                    path.unlink()
                else:
                    path.write_bytes(b'')
                issues = self.catalog.readiness('krea2')
                self.assertEqual(len(issues), 1)
                self.assertEqual(issues[0]['code'], 'model_missing' if state == 'missing' else 'model_invalid')
                self.assertEqual(issues[0]['path'], str(path))
                self.assertIn('KREA 2 Edit SNOFS Merge Q5 - Krea2.gguf', issues[0]['message'])
                with self.assertRaises(UiError) as caught:
                    self.catalog.build('krea2', {}, {'image': self.image_name()})
                self.assertEqual(caught.exception.code, 'model_missing' if state == 'missing' else 'model_invalid')

    def test_missing_encoder_or_vae_is_reported_without_model_loading(self):
        self.profile()
        for relative in ['text_encoders/qwen3vl_4b_fp8_scaled.safetensors', 'vae/qwen_image_vae.safetensors']:
            with self.subTest(relative=relative):
                path = self.paths.models / relative
                saved = path.read_bytes()
                path.unlink()
                issues = self.catalog.readiness('krea2')
                self.assertEqual([issue['path'] for issue in issues], [str(path)])
                path.write_bytes(saved)

    def test_required_image_and_unapproved_controls_cannot_be_bypassed(self):
        self.profile()
        for images in [{}, {'source': self.image_name()}, {'image': self.image_name(), 'extra': self.image_name()}]:
            with self.subTest(images=images), self.assertRaises(UiError) as caught:
                self.catalog.build('krea2', {}, images)
            self.assertEqual(caught.exception.code, 'images')
        for controls in [{'image_model': 'diffusion_models/other.gguf'}, {'negative': 'new negative'}, {'grounding_px': 512}, {'ref_boost': -1}, {'ref_boost': 1000.01}, {'ref_boost': 0.001}, {'seed': True}]:
            with self.subTest(controls=controls), self.assertRaises(UiError):
                self.catalog.build('krea2', controls, {'image': self.image_name()})

    def test_reference_boost_uses_native_range_without_quality_cap(self):
        self.profile()
        for value in [0, 0.01, 17.25, 1000]:
            with self.subTest(value=value):
                graph = self.catalog.prepared_graph('krea2', {'ref_boost': value})
                self.assertEqual(graph['79']['inputs']['ref_boost'], value)

    def test_gguf_path_cannot_escape_model_folder_through_template(self):
        self.profile()
        graph = json.loads(self.template.read_text(encoding='utf-8'))
        graph['55']['inputs']['unet_name'] = '../escape.gguf'
        (self.paths.models / 'escape.gguf').write_bytes(b'outside selector directory; never loaded')
        self.template.write_text(json.dumps(graph), encoding='utf-8')
        issues = self.catalog.readiness('krea2')
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0]['code'], 'model_selection')
        with self.assertRaises(UiError) as caught:
            self.catalog.build('krea2', {}, {'image': self.image_name()})
        self.assertEqual(caught.exception.code, 'model_selection')


if __name__ == '__main__':
    unittest.main()
