import copy
import json
import sys
import unittest
import asyncio
from aiohttp import web
from aiohttp.test_utils import TestServer
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from morph_ui.paths import ProjectPaths, UiError
from morph_ui.catalog import Catalog
from support import Sandbox
try:
    from morph_ui.settings import SettingsStore
    from morph_ui.providers.lmstudio import LMStudioProvider
except ModuleNotFoundError:
    LMStudioProvider = None

MODELS = {'models':[
    {'key':'publisher/chat-model','display_name':'Chat Modell','type':'llm','loaded_instances':[{'id':'chosen-instance','config':{}}]},
    {'key':'publisher/embedding','display_name':'Embedding','type':'embedding','loaded_instances':[]},
    {'key':'publisher/other','display_name':'Anderes Modell','type':'llm','loaded_instances':[]},
]}

class Wire:
    def __init__(self):
        self.calls = []
        self.content = json.dumps({'assistant_text':'Nur die Tasse blau färben.','prompt':'Change only the mug to blue.','controls':{'width':768}})
        self.fail = False
    async def request(self, method, path, payload=None):
        self.calls.append((method,path,copy.deepcopy(payload)))
        if self.fail:
            raise UiError('authentication','Zugangsschlüssel prüfen.',status=401)
        if path == '/api/v1/models':
            return copy.deepcopy(MODELS)
        if path == '/api/v1/models/load':
            return {'type':'llm','instance_id':'new-instance','status':'loaded','load_time_seconds':0.1,'load_config':{}}
        if path == '/api/v1/models/unload':
            return {}
        if path == '/v1/chat/completions':
            return {'choices':[{'index':0,'message':{'role':'assistant','content':self.content},'finish_reason':'stop'}]}
        raise AssertionError('Unexpected network route: ' + path)

class ProviderTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.assertIsNotNone(LMStudioProvider, 'Sprachmodell-Adapter noch nicht implementiert')
        box = Sandbox(self)
        self.paths = ProjectPaths(box.root)
        self.catalog = Catalog(self.paths)
        self.settings = SettingsStore(self.paths)
        self.wire = Wire()
        self.provider = LMStudioProvider(self.settings,self.catalog,self.wire)

    async def test_listing_filters_embeddings_and_never_predicts(self):
        models = await self.provider.list_models()
        self.assertEqual([x['key'] for x in models], ['publisher/chat-model','publisher/other'])
        self.assertEqual(models[0]['loaded_instances'][0]['id'], 'chosen-instance')
        self.assertEqual(self.wire.calls, [('GET','/api/v1/models',None)])
        self.assertIsNone(models[1]['capabilities'])

    async def test_load_uses_key_and_unload_uses_instance(self):
        result = await self.provider.load('publisher/other')
        self.assertEqual(result['instance_id'], 'new-instance')
        self.assertIn(('POST','/api/v1/models/load',{'model':'publisher/other','echo_load_config':True}), self.wire.calls)
        await self.provider.unload('chosen-instance')
        self.assertEqual(self.wire.calls[-1], ('POST','/api/v1/models/unload',{'instance_id':'chosen-instance'}))

    async def test_proposal_uses_loaded_instance_and_checks_controls(self):
        result = await self.provider.propose('chosen-instance','kontext','Tasse blau färben',self.catalog.controls('kontext'))
        self.assertEqual(result['controls']['width'], 768)
        self.assertEqual(result['prompt'], 'Change only the mug to blue.')
        payload = self.wire.calls[-1][2]
        self.assertEqual(payload['model'], 'chosen-instance')
        self.assertFalse(payload['stream'])
        self.assertEqual(payload['response_format']['type'], 'json_schema')

    async def test_bad_and_truncated_content_has_no_second_prediction(self):
        for content in ['{"prompt":', json.dumps({'assistant_text':'ok','prompt':'Test','controls':{'shell':'run'}})]:
            self.wire.content = content
            self.wire.calls.clear()
            with self.assertRaises(UiError):
                await self.provider.propose('chosen-instance','kontext','Test',self.catalog.controls('kontext'))
            self.assertEqual(sum(x[1] == '/v1/chat/completions' for x in self.wire.calls), 1)

    async def test_unloaded_instance_blocks_prediction(self):
        with self.assertRaises(UiError):
            await self.provider.propose('publisher/other','sdxl','Test',self.catalog.controls('sdxl'))
        self.assertFalse(any(x[1] == '/v1/chat/completions' for x in self.wire.calls))

    async def test_authentication_error_is_not_retried(self):
        self.wire.fail = True
        with self.assertRaises(UiError):
            await self.provider.list_models()
        self.assertEqual(len(self.wire.calls), 1)

    async def test_settings_keep_secret_private_and_reject_remote_addresses(self):
        self.settings.save({'endpoint':'http://127.0.0.1:1234','token':'own-test-secret'})
        self.assertNotIn('own-test-secret', json.dumps(self.settings.read_public()))
        self.assertNotIn('own-test-secret', (self.paths.data / 'settings.json').read_text())
        self.assertEqual(SettingsStore(self.paths).token(), 'own-test-secret')
        for endpoint in ['https://example.org','http://127.0.0.1:1234@evil.example','http://127.0.0.1:1234/path','http://127.0.0.1:1234?token=abc']:
            with self.assertRaises(UiError):
                self.settings.save({'endpoint':endpoint})

    async def test_explicit_zero_port_is_rejected(self):
        with self.assertRaises(UiError):
            self.settings.save({'endpoint':'http://127.0.0.1:0'})

    async def test_proposal_validates_against_visible_current_controls(self):
        allowed = self.catalog.controls('wan')
        allowed['steps']['default'] = 6
        allowed['split']['default'] = 2
        self.wire.content = json.dumps({'assistant_text':'Vier Schritte.','prompt':'A calm scene.','controls':{'steps':4}})
        result = await self.provider.propose('chosen-instance','wan','Vier Schritte',allowed)
        self.assertEqual(result['controls'], {'steps':4})

    async def test_real_http_transport_reads_whole_fragmented_answer(self):
        from morph_ui.providers.base import LocalHttp
        async def answer(request):
            response = web.StreamResponse(headers={'Content-Type':'application/json'})
            await response.prepare(request)
            await response.write(b'{"models":')
            await asyncio.sleep(0.03)
            await response.write(b'[]}')
            await response.write_eof()
            return response
        app = web.Application()
        app.router.add_get('/api/v1/models', answer)
        server = TestServer(app)
        await server.start_server()
        self.addAsyncCleanup(server.close)
        self.settings.save({'endpoint':str(server.make_url('/'))})
        transport = LocalHttp(self.settings)
        self.addAsyncCleanup(transport.close)
        try:
            result = await transport.request('GET','/api/v1/models')
        except UiError as error:
            self.fail('Vollständige gültige Teilstückantwort wurde verworfen: ' + str(error))
        self.assertEqual(result, {'models':[]})
