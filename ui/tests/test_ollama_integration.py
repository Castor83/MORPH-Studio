import sys
import unittest
from pathlib import Path
from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from morph_ui.catalog import Catalog
from morph_ui.files import FileStore
from morph_ui.jobs import JobService
from morph_ui.paths import ProjectPaths
from morph_ui.providers.ollama import OllamaProvider
from morph_ui.server import create_app
from morph_ui.settings import SettingsStore
from support import Sandbox
from test_jobs import Compute

HEADERS = {'Host': '127.0.0.1:8765', 'Origin': 'http://127.0.0.1:8765', 'X-MORPH-Request': '1'}


class OllamaIntegrationTests(unittest.IsolatedAsyncioTestCase):
    async def test_native_http_round_trip_preserves_manual_model_and_never_starts_comfy(self):
        # Only this isolated loopback fixture receives model actions.
        loaded, calls = set(), []
        async def native(request):
            calls.append(request.path)
            if request.path == '/api/tags':
                return web.json_response({'models': [{'name': 'local:latest'}]})
            if request.path == '/api/ps':
                return web.json_response({'models': [{'name': name} for name in loaded]})
            data = await request.json()
            if request.path == '/api/show':
                return web.json_response({'capabilities': ['completion']})
            if request.path == '/api/generate':
                self.assertNotIn('prompt', data)
                if data['keep_alive'] == 0:
                    loaded.discard(data['model'])
                else:
                    loaded.add(data['model'])
                return web.json_response({'model': data['model'], 'done': True})
            if request.path == '/api/chat':
                self.assertFalse(data['stream'])
                self.assertFalse(data['think'])
                self.assertNotIn('image_model', data['format']['properties']['controls']['properties'])
                return web.json_response({'model': data['model'], 'done': True, 'done_reason': 'stop',
                    'message': {'role': 'assistant', 'content': '{"assistant_text":"Eine blaue Tasse.","prompt":"A blue mug.","controls":{"seed":42}}'}})
            raise AssertionError('Unexpected native route: ' + request.path)

        backend = web.Application()
        backend.router.add_route('*', '/{tail:.*}', native)
        native_server = TestServer(backend)
        await native_server.start_server()
        self.addAsyncCleanup(native_server.close)
        paths = ProjectPaths(Sandbox(self).root)
        catalog, files, settings = Catalog(paths), FileStore(paths), SettingsStore(paths)
        settings.save({'endpoint': str(native_server.make_url('/'))})
        compute = Compute(paths)
        jobs = JobService(paths, catalog, files, compute)
        provider = OllamaProvider(settings, catalog)
        client = TestClient(TestServer(create_app(paths, catalog, provider, jobs, files, settings)))
        await client.start_server()
        self.addAsyncCleanup(client.close)

        async def api(method, path, body=None):
            response = await client.request(method, path, headers=HEADERS, json=body)
            result = await response.json()
            self.assertEqual(response.status, 200, result)
            self.assertTrue(result['ok'])
            return result['data']

        listed = await api('GET', '/api/models')
        self.assertEqual(listed[0]['loaded_instances'], [])
        self.assertEqual(calls, ['/api/tags', '/api/ps'])
        self.assertEqual((await api('POST', '/api/models/load', {'model_key': 'local:latest'}))['instance_id'], 'local:latest')
        current = await api('GET', '/api/settings')
        self.assertEqual((current['provider'], current['model_key'], current['instance_id']), ('ollama', 'local:latest', 'local:latest'))
        controls = {name: spec['default'] for name, spec in catalog.controls('sdxl').items()}
        selection = controls['image_model']
        proposal = await api('POST', '/api/proposals', {'instance_id': 'local:latest', 'workflow_id': 'sdxl',
            'instruction': 'Eine blaue Tasse, Seed 42.', 'controls': controls})
        self.assertEqual(proposal, {'assistant_text': 'Eine blaue Tasse.', 'prompt': 'A blue mug.', 'controls': {'seed': 42}})
        self.assertEqual(controls['image_model'], selection)
        self.assertEqual(calls.count('/api/chat'), 1)
        await api('POST', '/api/models/unload', {'instance_id': 'local:latest'})
        self.assertEqual((await api('GET', '/api/settings'))['instance_id'], '')
        self.assertEqual(loaded, set())
        self.assertEqual(compute.started, 0)
