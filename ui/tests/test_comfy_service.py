import sys
import unittest
import uuid
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

from aiohttp import web
from aiohttp.test_utils import TestServer

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from morph_ui.comfy import ComfyClient
from morph_ui.paths import ProjectPaths, UiError
from morph_ui.catalog import Catalog
from morph_ui.files import FileStore
from morph_ui.jobs import JobService
from support import Sandbox, png


class ComfyServiceTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.paths = ProjectPaths(Sandbox(self).root)

    async def client_for(self, app):
        server = TestServer(app)
        await server.start_server()
        self.addAsyncCleanup(server.close)
        client = ComfyClient(self.paths, str(server.make_url('/')).rstrip('/'))
        self.addAsyncCleanup(client.close)
        return client

    async def test_compatible_api_remains_usable_without_process_metadata(self):
        client = ComfyClient(self.paths)
        client.guard = SimpleNamespace(
            inspect_listener_details=Mock(side_effect=RuntimeError('Metadaten nicht lesbar')),
            service_ready=lambda: True)
        status = await client.status()
        self.assertTrue(status['ready'])
        self.assertEqual(status['ownership'], 'compatible')

    async def test_blocked_service_status_keeps_specific_diagnostic(self):
        client = ComfyClient(self.paths)
        client.guard = SimpleNamespace(
            inspect_listener_details=lambda: {'ownership':'foreign','pid':19,'message':'Port 8188: kein ComfyUI.'},
            service_ready=lambda: False)
        status = await client.status()
        self.assertEqual(status['pid'], 19)
        self.assertIn('kein ComfyUI', status['message'])
        self.assertFalse(status['ready'])

    async def test_upload_accepts_confirmed_backend_name_without_local_backend_file(self):
        app = web.Application()
        async def upload(request):
            reader = await request.multipart()
            while (part := await reader.next()) is not None:
                await part.read()
            return web.json_response({'name':'external.png','type':'input','subfolder':'morph-ui/jobs'})
        app.router.add_post('/upload/image', upload)
        client = await self.client_for(app)
        source = self.paths.input / 'source.png'
        source.write_bytes(png())
        self.assertEqual(await client.upload(source), 'morph-ui/jobs/external.png')
        self.assertFalse((self.paths.input / 'morph-ui/jobs/external.png').exists())

    async def test_backend_output_is_imported_from_view_without_trusting_local_names(self):
        app = web.Application()
        async def view(request):
            self.assertEqual(dict(request.query), {'filename':'remote.png','subfolder':'elsewhere','type':'output'})
            return web.Response(body=png(), content_type='image/png')
        app.router.add_get('/view', view)
        client = await self.client_for(app)
        local = self.paths.output / 'elsewhere/remote.png'
        local.parent.mkdir()
        local.write_bytes(b'other instance, same relative filename')
        target = await client.download_output({'filename':'remote.png','subfolder':'elsewhere','type':'output'},str(uuid.uuid4()))
        self.assertEqual(target.read_bytes(), png())
        self.assertNotEqual(target, local)
        self.assertTrue(target.is_relative_to(self.paths.output))
        self.assertEqual(local.read_bytes(), b'other instance, same relative filename')

    async def test_output_traversal_is_rejected_before_http(self):
        client = ComfyClient(self.paths)
        for item in [{'filename':'../escape.png','type':'output'},
                     {'filename':'safe.png','subfolder':'../escape','type':'temp'},
                     {'filename':'safe.png','type':'input'}]:
            with self.subTest(item=item), self.assertRaises(UiError):
                await client.download_output(item,str(uuid.uuid4()))

    async def test_missing_output_response_never_creates_a_success_file(self):
        app = web.Application()
        async def missing(request):
            return web.Response(status=404)
        app.router.add_get('/view', missing)
        client = await self.client_for(app)
        with self.assertRaises(UiError):
            await client.download_output({'filename':'missing.png','type':'output'},str(uuid.uuid4()))
        self.assertEqual(list(self.paths.output.rglob('*.png')), [])

    async def test_oversized_or_redirected_output_is_not_followed_or_saved(self):
        app = web.Application()
        async def view(request):
            if request.query['filename'] == 'large.png':
                return web.Response(headers={'Content-Length':str(512*1024**2+1)})
            return web.Response(status=302,headers={'Location':'http://192.0.2.1/private'})
        app.router.add_get('/view',view)
        client = await self.client_for(app)
        for filename in ['large.png','redirect.png']:
            with self.subTest(filename=filename), self.assertRaises(UiError):
                await client.download_output({'filename':filename,'type':'output'},str(uuid.uuid4()))
        self.assertEqual(list(self.paths.output.rglob('*')), [])

    async def test_job_can_upload_submit_and_retrieve_from_another_backend_directory(self):
        catalog = Catalog(self.paths)
        files = FileStore(self.paths)
        self.addCleanup(files.close)
        source = files.save_upload(png(),'original.png')
        graph = catalog.prepared_graph('kontext',{})
        sent = []
        app = web.Application()
        async def queue(request):
            return web.json_response({'queue_running':[],'queue_pending':[]})
        async def schema(request):
            kind = request.match_info['kind']
            inputs = {key:[[value]] for node in graph.values() if node['class_type']==kind
                      for key,value in node['inputs'].items() if isinstance(value,str)}
            return web.json_response({kind:{'input':{'required':inputs}}})
        async def upload(request):
            reader = await request.multipart()
            while (part := await reader.next()) is not None:
                await part.read()
            return web.json_response({'name':'backend-input.png','subfolder':'morph-ui/jobs','type':'input'})
        async def submit(request):
            body = await request.json()
            sent.append(body)
            return web.json_response({'prompt_id':body['prompt_id']})
        async def history(request):
            return web.json_response({request.match_info['id']:{'status':{'completed':True},
                'outputs':{'output':{'images':[{'filename':'backend-output.png','subfolder':'foreign','type':'output'}]}}}})
        async def view(request):
            return web.Response(body=png(),content_type='image/png')
        app.router.add_get('/queue',queue)
        app.router.add_get('/object_info/{kind}',schema)
        app.router.add_post('/upload/image',upload)
        app.router.add_post('/prompt',submit)
        app.router.add_get('/history/{id}',history)
        app.router.add_get('/view',view)
        client = await self.client_for(app)
        client.guard = SimpleNamespace(ensure_comfy=lambda:None)
        jobs = JobService(self.paths,catalog,files,client)
        self.addCleanup(jobs.close)
        job = await jobs.create(str(uuid.uuid4()),'kontext',{}, {'image':source['id']})
        self.assertEqual(job['state'],'queued',job.get('error'))
        self.assertEqual(sent[0]['prompt']['4']['inputs']['image'],'morph-ui/jobs/backend-input.png')
        result = await jobs.refresh(job['id'])
        self.assertEqual(result['state'],'completed',result.get('error'))
        self.assertEqual(files.resolve(result['outputs'][0]['id']).read_bytes(),png())
        self.assertFalse((self.paths.output/'foreign/backend-output.png').exists())
