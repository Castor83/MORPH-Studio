import sys
import os
import unittest
import uuid
from pathlib import Path
from aiohttp import FormData
from aiohttp.test_utils import TestClient, TestServer
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from morph_ui.paths import ProjectPaths
from morph_ui.catalog import Catalog
from morph_ui.files import FileStore
from morph_ui.jobs import JobService
from morph_ui.settings import SettingsStore
from test_jobs import Compute
from support import Sandbox, png
try:
    from morph_ui.server import create_app
except ModuleNotFoundError:
    create_app = None

HEADERS = {'Host':'127.0.0.1:8765','Origin':'http://127.0.0.1:8765','X-MORPH-Request':'1'}

class Provider:
    def __init__(self):
        self.loads = self.proposals = 0
    async def list_models(self):
        return [{'key':'local-model','name':'Testmodell','loaded_instances':[],'capabilities':None}]
    async def load(self, key):
        self.loads += 1
        return {'status':'loaded','instance_id':'test-instance'}
    async def unload(self, instance):
        pass
    async def propose(self, *args):
        self.proposals += 1
        return {'assistant_text':'Test','prompt':'A red cup','controls':{}}
    async def close(self):
        pass

class ServerTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.assertIsNotNone(create_app, 'Oberflächendienst noch nicht implementiert')
        box = Sandbox(self)
        self.paths = ProjectPaths(box.root)
        self.catalog = Catalog(self.paths)
        self.files = FileStore(self.paths)
        self.settings = SettingsStore(self.paths)
        self.compute = Compute(self.paths)
        async def status():
            return {'ready':False,'ownership':'free'}
        self.compute.status = status
        self.jobs = JobService(self.paths,self.catalog,self.files,self.compute)
        self.provider = Provider()
        self.app = create_app(self.paths,self.catalog,self.provider,self.jobs,self.files,self.settings)
        self.client = TestClient(TestServer(self.app))
        await self.client.start_server()
        self.addAsyncCleanup(self.client.close)

    async def test_status_and_model_listing_do_not_start_or_predict(self):
        response = await self.client.get('/api/status',headers=HEADERS)
        self.assertEqual(response.status,200)
        self.assertEqual((await response.json())['data']['app'],'morph-ui')
        await self.client.get('/api/models',headers=HEADERS)
        self.assertEqual(self.compute.started,0)
        self.assertEqual(self.provider.loads,0)
        self.assertEqual(self.provider.proposals,0)

    async def test_health_identifies_ui_without_optional_service_or_settings_checks(self):
        async def forbidden():
            raise AssertionError('UI health must not inspect ComfyUI')
        def forbidden_sync():
            raise AssertionError('UI health must not inspect settings or storage')
        self.compute.status = forbidden
        self.settings.read_public = forbidden_sync
        self.paths.free_bytes = forbidden_sync
        response = await self.client.get('/api/health', headers=HEADERS)
        self.assertEqual(response.status, 200)
        self.assertEqual((await response.json())['data'], {
            'app':'morph-ui', 'version':'1.0', 'pid':os.getpid(),
            'project_root':str(self.paths.root)})
        self.assertEqual(self.compute.started, 0)
        self.assertEqual(self.provider.loads, 0)
        self.assertEqual(self.provider.proposals, 0)
        foreign = await self.client.get('/api/health', headers={'Host':'foreign.example'})
        self.assertEqual(foreign.status, 403)

    async def test_foreign_origin_and_missing_action_header_cannot_mutate(self):
        before = self.settings.read_public()
        for headers in [HEADERS | {'Origin':'https://foreign.example'}, {'Host':'127.0.0.1:8765','Origin':'http://127.0.0.1:8765'}]:
            response = await self.client.post('/api/settings',json={'endpoint':'http://127.0.0.1:9999'},headers=headers)
            self.assertEqual(response.status,403)
        self.assertEqual(self.settings.read_public(), before)
        response = await self.client.get('/api/status',headers={'Host':'foreign.example'})
        self.assertEqual(response.status,403)

    async def test_public_settings_never_return_secret(self):
        response = await self.client.post('/api/settings',json={'token':'local-test-secret'},headers=HEADERS)
        self.assertEqual(response.status,200)
        response = await self.client.get('/api/settings',headers=HEADERS)
        data = await response.json()
        self.assertTrue(data['data']['has_token'])
        self.assertNotIn('local-test-secret',str(data))

    async def test_upload_and_only_registered_media_are_available(self):
        form = FormData()
        form.add_field('file',png(),filename='../original.png',content_type='image/png')
        response = await self.client.post('/api/uploads',data=form,headers=HEADERS)
        self.assertEqual(response.status,200)
        item = (await response.json())['data']
        response = await self.client.get(item['url'],headers=HEADERS)
        self.assertEqual(await response.read(),png())
        response = await self.client.get('/media/' + '0' * 32,headers=HEADERS)
        self.assertEqual(response.status,404)
        self.assertEqual(self.compute.started,0)

    async def test_video_preview_supports_partial_download_and_correct_type(self):
        video = self.paths.output / 'own-preview.mp4'
        video.write_bytes(b'own small HTTP range fixture')
        item = self.files.register_output(video)
        response = await self.client.get(item['url'],headers=HEADERS | {'Range':'bytes=0-7'})
        self.assertEqual(response.status,206)
        self.assertEqual(await response.read(),b'own smal')
        self.assertEqual(response.headers['Content-Type'],'video/mp4')

    async def test_duplicate_http_start_returns_same_persistent_receipt(self):
        body = {'request_id':str(uuid.uuid4()),'workflow_id':'sdxl','controls':{},'images':{}}
        first = await self.client.post('/api/jobs',json=body,headers=HEADERS)
        second = await self.client.post('/api/jobs',json=body,headers=HEADERS)
        one,two = (await first.json())['data'],(await second.json())['data']
        self.assertEqual(one['id'],two['id'])
        self.assertEqual(len(self.compute.submissions),1)
        response = await self.client.get('/api/jobs',headers=HEADERS)
        self.assertEqual((await response.json())['data'][0]['id'],one['id'])

    async def test_request_resolution_closes_missing_receipt_without_computing(self):
        request_id = str(uuid.uuid4())
        response = await self.client.get('/api/requests/' + request_id,headers=HEADERS)
        self.assertEqual(response.status,200)
        self.assertIsNone((await response.json())['data'])
        response = await self.client.post('/api/requests/' + request_id + '/resolve',json={},headers=HEADERS)
        self.assertEqual(response.status,200)
        resolved = (await response.json())['data']
        response = await self.client.post('/api/jobs',json={'request_id':request_id,'workflow_id':'sdxl','controls':{},'images':{}},headers=HEADERS)
        late = (await response.json())['data']
        self.assertEqual(late['id'],resolved['id'])
        self.assertEqual(self.compute.submissions,[])
        self.assertEqual(self.compute.started,0)
        response = await self.client.get('/api/jobs',headers=HEADERS)
        self.assertEqual((await response.json())['data'][0]['id'],resolved['id'])
