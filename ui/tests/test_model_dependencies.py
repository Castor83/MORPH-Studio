import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from morph_ui.catalog import Catalog
from morph_ui.paths import ProjectPaths
from model_fixtures import write_model
from support import Sandbox
import test_server as server_cases
from test_server import HEADERS


class DependencyTests(unittest.TestCase):
    def setUp(self):
        self.box = Sandbox(self)
        self.paths = ProjectPaths(self.box.root)
        self.catalog = Catalog(self.paths)

    def test_selected_checkpoint_is_shown_instead_of_template_default(self):
        write_model(self.paths.models / 'checkpoints/alternative.safetensors', 'sd15')
        entry = next(x for x in self.catalog.list_entries() if x['id'] == 'sdxl')
        self.assertIn('dependencies', entry)
        selected = self.catalog.dependencies('sdxl', {'image_model': 'checkpoints/alternative.safetensors'})
        self.assertEqual([x['name'] for x in selected], ['alternative.safetensors'])
        self.assertEqual(selected[0]['path'], str(self.paths.models / 'checkpoints/alternative.safetensors'))

    def test_fixed_krea_models_and_wan_interpolator_have_actual_loader_paths(self):
        self.assertTrue(hasattr(self.catalog, 'dependencies'))
        self.assertEqual([x['name'] for x in self.catalog.dependencies('krea2')], [
            'KREA 2 Edit SNOFS Merge Q5 - Krea2.gguf',
            'qwen3vl_4b_fp8_scaled.safetensors', 'qwen_image_vae.safetensors'])
        rife = next(x for x in self.catalog.dependencies('wan') if x['name'] == 'flownet.pkl')
        self.assertEqual(rife['path'], str(self.paths.root / 'ComfyUI_windows_portable/ComfyUI/custom_nodes/ComfyUI-VFI/rife/train_log/flownet.pkl'))
        self.assertEqual(len(self.catalog.dependencies('reactor')), 6)

    def test_inventory_names_real_workflow_use_without_assigning_lora_as_base(self):
        self.assertTrue(hasattr(self.catalog, 'model_inventory'))
        write_model(self.paths.models / 'loras/addon.safetensors', 'lora')
        items = {x['id']: x for x in self.catalog.model_inventory()}
        self.assertEqual(items['text_encoders/clip_l.safetensors']['used_by'], [{'id': 'kontext', 'name': 'Bild bearbeiten'}])
        self.assertEqual(items['loras/addon.safetensors']['used_by'], [])

    def test_missing_main_model_keeps_fixed_component_associations_visible(self):
        (self.paths.models / 'diffusion_models/KREA 2 Edit SNOFS Merge Q5 - Krea2.gguf').unlink()
        self.assertIn('qwen3vl_4b_fp8_scaled.safetensors', [x['name'] for x in self.catalog.dependencies('krea2')])
        encoder = next(x for x in self.catalog.model_inventory() if x['name'] == 'qwen3vl_4b_fp8_scaled.safetensors')
        self.assertEqual(encoder['used_by'], [{'id': 'krea2', 'name': 'Bild mit KREA 2 bearbeiten'}])
        self.assertTrue(self.catalog.readiness('krea2'))

    def test_repeated_inventory_reuses_headers_but_selection_revalidates_file(self):
        library = self.catalog.library
        with patch.object(library, '_inspect', wraps=library._inspect) as inspect:
            first = library.inventory()
            count = inspect.call_count
            self.assertEqual(library.inventory(), first)
            self.assertEqual(inspect.call_count, count)
            library.resolve('checkpoints/sd_xl_base_1.0.safetensors', 'checkpoint')
            self.assertEqual(inspect.call_count, count + 1)

    def test_alternative_wan_pair_assigns_both_halves_but_orphan_is_unused(self):
        for name in ['alternative_high.safetensors','alternative_low.safetensors','orphan_high.safetensors']:
            write_model(self.paths.models / 'diffusion_models' / name, 'wan')
        items = {x['name']: x for x in self.catalog.model_inventory()}
        self.assertEqual(items['alternative_low.safetensors']['used_by'], [{'id':'wan','name':'Bild zu Video'}])
        self.assertEqual(items['alternative_high.safetensors']['used_by'], [{'id':'wan','name':'Bild zu Video'}])
        self.assertEqual(items['orphan_high.safetensors']['used_by'], [])


class DependencyRouteTests(unittest.IsolatedAsyncioTestCase):
    asyncSetUp = server_cases.ServerTests.asyncSetUp

    async def test_check_returns_selected_dependency_without_loading_or_starting(self):
        write_model(self.paths.models / 'checkpoints/alternative.safetensors', 'sd15')
        response = await self.client.post('/api/workflows/sdxl/check', json={'controls': {'image_model': 'checkpoints/alternative.safetensors'}}, headers=HEADERS)
        data = (await response.json())['data']
        self.assertEqual(data['issues'], [])
        self.assertEqual([x['name'] for x in data.get('dependencies', [])], ['alternative.safetensors'])
        self.assertEqual((self.provider.loads, self.provider.proposals, self.compute.started), (0, 0, 0))
        self.assertEqual(self.compute.submissions, [])


if __name__ == '__main__':
    unittest.main()
