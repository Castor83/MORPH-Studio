import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from morph_ui.comfy import ComfyClient
import test_server as server_cases
from test_server import HEADERS
from model_fixtures import write_model


class ModelRoutesTests(unittest.IsolatedAsyncioTestCase):
    asyncSetUp = server_cases.ServerTests.asyncSetUp

    async def test_model_check_uses_selected_alternative_and_never_starts(self):
        write_model(self.paths.models / 'checkpoints/sd15.safetensors', 'sd15')
        (self.paths.models / 'checkpoints/sd_xl_base_1.0.safetensors').unlink()
        response = await self.client.post('/api/workflows/sdxl/check', json={'controls':{'image_model':'checkpoints/sd15.safetensors'}}, headers=HEADERS)
        self.assertEqual(response.status, 200, 'Modellprüfung fehlt')
        self.assertEqual((await response.json())['data']['issues'], [])
        self.assertEqual(self.compute.started, 0)
        self.assertEqual(self.compute.submissions, [])

    async def test_inventory_reports_partial_models_as_components(self):
        write_model(self.paths.models / 'checkpoints/encoder-only.safetensors', 'qwen_encoder')
        response = await self.client.get('/api/image-models', headers=HEADERS)
        self.assertEqual(response.status, 200, 'Bildmodell-Inventar fehlt')
        item = next(x for x in (await response.json())['data'] if x['name']=='encoder-only.safetensors')
        self.assertEqual(item['kind'], 'text_encoder')
        self.assertEqual(self.compute.started, 0)

    async def test_live_loader_missing_selection_prevents_false_readiness(self):
        self.assertTrue(hasattr(ComfyClient, 'model_readiness'), 'Rechendienst-Zuordnung wird noch nicht geprüft')
        client = ComfyClient(self.paths)
        async def wire(method, endpoint, payload=None, form=None):
            return {'UNETLoader':{'input':{'required':{'unet_name':[['other.safetensors'],{}]}}}}
        client.request = wire
        graph = {'1':{'class_type':'UNETLoader','inputs':{'unet_name':'morph-ui-qwen21/model.safetensors'}}}
        issues = await client.model_readiness(graph)
        self.assertTrue(issues)
        self.assertIn('model.safetensors', issues[0]['message'])
        async def available(method, endpoint, payload=None, form=None):
            return {'UNETLoader':{'input':{'required':{'unet_name':[['morph-ui-qwen21\\model.safetensors'],{}]}}}}
        client.request = available
        self.assertEqual(await client.model_readiness(graph), [])


if __name__ == '__main__':
    unittest.main()
