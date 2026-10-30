import asyncio
import copy
import json
import sys
import unittest
import uuid
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from morph_ui.paths import ProjectPaths, UiError
from morph_ui.catalog import Catalog
from morph_ui.files import FileStore
from support import Sandbox, png
try:
    from morph_ui.jobs import JobService
    from morph_ui.comfy import ComfyClient
except ModuleNotFoundError:
    JobService = None

class Compute:
    def __init__(self, paths):
        self.paths, self.submissions, self.cancellations = paths, [], []
        self.foreign = self.lost = False
        self.current = {'state':'queued','outputs':[]}
        self.started = 0
    async def ensure_ready(self):
        self.started += 1
    async def model_readiness(self, graph):
        return []
    async def resource_stats(self):
        return {'system':{}, 'devices':[{'type':'cuda', 'name':'Fixture GPU', 'torch_vram_total':0}]}
    async def status(self):
        return {'ready':True, 'ownership':'owned'}
    async def queue(self):
        return {'queue_running':[[1,'foreign-job',{}, {}, []]] if self.foreign else [],'queue_pending':[]}
    async def upload(self, path):
        target = self.paths.input / 'exact-subfolder/returned-image.png'
        target.parent.mkdir(exist_ok=True)
        target.write_bytes(path.read_bytes())
        return 'exact-subfolder/returned-image.png'
    async def submit(self, graph, prompt_id):
        self.submissions.append((copy.deepcopy(graph),prompt_id))
        await asyncio.sleep(0.01)
        if self.lost:
            raise UiError('connection','Antwort verloren.',status=503)
        return prompt_id
    async def poll(self, prompt_id):
        return copy.deepcopy(self.current)
    async def download_output(self, item, prompt_id):
        base = self.paths.output if item.get('type','output') == 'output' else self.paths.inside(self.paths.temp,'comfyui')
        name = '/'.join(part for part in [item.get('subfolder',''),item['filename']] if part)
        return self.paths.inside(base,name,True)
    async def cancel(self, prompt_id):
        self.cancellations.append(prompt_id)
        return True

class JobTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.assertIsNotNone(JobService, 'Auftragsverwaltung noch nicht implementiert')
        self.box = Sandbox(self)
        self.paths = ProjectPaths(self.box.root)
        self.catalog = Catalog(self.paths)
        self.files = FileStore(self.paths)
        self.addCleanup(self.files.close)
        self.compute = Compute(self.paths)
        self.jobs = JobService(self.paths,self.catalog,self.files,self.compute)
        self.addCleanup(self.jobs.close)

    async def test_simultaneous_duplicate_start_submits_only_once_and_persists(self):
        request_id = str(uuid.uuid4())
        first, second = await asyncio.gather(self.jobs.create(request_id,'sdxl',{},{}),self.jobs.create(request_id,'sdxl',{},{}))
        self.assertEqual(first['id'], second['id'])
        self.assertEqual(len(self.compute.submissions),1)
        self.assertEqual(self.compute.submissions[0][1], first['prompt_id'])
        restored = JobService(self.paths,self.catalog,self.files,self.compute)
        self.addCleanup(restored.close)
        self.assertEqual(restored.get(first['id'])['request_id'], request_id)
        await restored.create(request_id,'sdxl',{}, {})
        self.assertEqual(len(self.compute.submissions),1)

    async def test_lost_submit_response_stays_unknown_until_receipt_is_found(self):
        self.compute.lost = True
        request_id = str(uuid.uuid4())
        job = await self.jobs.create(request_id,'sdxl',{}, {})
        self.assertEqual(job['state'], 'unknown')
        await self.jobs.create(request_id,'sdxl',{}, {})
        self.assertEqual(len(self.compute.submissions),1)
        self.compute.current = {'state':'running','outputs':[]}
        refreshed = await self.jobs.refresh(job['id'])
        self.assertEqual(refreshed['state'], 'running')

    async def test_foreign_queue_and_missing_images_prevent_submission(self):
        self.compute.foreign = True
        job = await self.jobs.create(str(uuid.uuid4()),'sdxl',{}, {})
        self.assertEqual(job['state'], 'error')
        self.assertEqual(self.compute.submissions, [])
        job = await self.jobs.create(str(uuid.uuid4()),'kontext',{}, {})
        self.assertEqual(job['state'], 'error')
        self.assertEqual(self.compute.started,1)

    async def test_actual_upload_response_is_inserted_in_graph(self):
        image = self.files.save_upload(png(),'picture.png')
        await self.jobs.create(str(uuid.uuid4()),'kontext',{}, {'image':image['id']})
        self.assertEqual(self.compute.submissions[0][0]['4']['inputs']['image'], 'exact-subfolder/returned-image.png')

    async def test_unreceived_request_is_closed_and_late_post_never_submits(self):
        request_id = str(uuid.uuid4())
        self.assertIsNone(self.jobs.get_request(request_id))
        resolved = await self.jobs.resolve_request(request_id)
        self.assertEqual(resolved['state'], 'error')
        self.assertEqual(resolved['error_code'], 'request_not_received')
        late = await self.jobs.create(request_id,'sdxl',{}, {})
        self.assertEqual(late['id'],resolved['id'])
        self.assertEqual(self.compute.submissions, [])
        self.assertEqual(self.compute.started, 0)
        next_job = await self.jobs.create(str(uuid.uuid4()),'sdxl',{}, {})
        self.assertEqual(next_job['state'], 'queued')
        self.assertEqual(len(self.compute.submissions), 1)

    async def test_lookup_resolves_saved_receipt_beyond_recent_history(self):
        request_id = str(uuid.uuid4())
        original = await self.jobs.create(request_id,'sdxl',{}, {})
        for unused in range(31):
            await self.jobs.create(str(uuid.uuid4()),'kontext',{}, {})
        self.assertNotIn(original['id'],[job['id'] for job in self.jobs.list_recent()])
        found = self.jobs.get_request(request_id)
        self.assertEqual(found['id'],original['id'])
        resolved = await self.jobs.resolve_request(request_id)
        self.assertEqual(resolved['id'],original['id'])
        self.assertEqual(len(self.compute.submissions), 1)

    async def test_second_cancel_cannot_erase_confirmed_receipt(self):
        job = await self.jobs.create(str(uuid.uuid4()),'sdxl',{}, {})
        first = await self.jobs.cancel(job['id'])
        self.assertTrue(first['cancel_requested'])
        async def no_longer_present(prompt_id):
            self.compute.cancellations.append(prompt_id)
            return False
        self.compute.cancel = no_longer_present
        second = await self.jobs.cancel(job['id'])
        self.assertTrue(second['cancel_requested'])
        self.compute.current = {'state':'absent','outputs':[]}
        final = await self.jobs.refresh(job['id'])
        self.assertEqual(final['state'],'cancelled')

    async def test_status_during_preparation_cannot_claim_submission(self):
        started, release = asyncio.Event(), asyncio.Event()
        async def delayed_start():
            started.set()
            await release.wait()
        self.compute.ensure_ready = delayed_start
        task = asyncio.create_task(self.jobs.create(str(uuid.uuid4()),'sdxl',{},{}))
        await started.wait()
        try:
            job = self.jobs.list_recent()[0]
            self.assertEqual((await self.jobs.refresh(job['id']))['state'], 'preparing')
        finally:
            release.set()
            await task

    async def test_status_response_cannot_erase_concurrent_cancel_receipt(self):
        job = await self.jobs.create(str(uuid.uuid4()),'sdxl',{}, {})
        started, release = asyncio.Event(), asyncio.Event()
        async def delayed_poll(prompt_id):
            started.set()
            await release.wait()
            return {'state':'running','outputs':[]}
        self.compute.poll = delayed_poll
        refresh = asyncio.create_task(self.jobs.refresh(job['id']))
        await started.wait()
        cancel = asyncio.create_task(self.jobs.cancel(job['id']))
        await asyncio.sleep(0.02)
        release.set()
        await asyncio.gather(refresh,cancel)
        self.assertTrue(self.jobs.get(job['id'])['cancel_requested'])

    async def test_targeted_cancel_never_cancels_foreign_or_finished_job(self):
        with self.assertRaises(UiError):
            await self.jobs.cancel(str(uuid.uuid4()))
        self.assertEqual(self.compute.cancellations, [])
        job = await self.jobs.create(str(uuid.uuid4()),'sdxl',{}, {})
        await self.jobs.cancel(job['id'])
        self.assertEqual(self.compute.cancellations, [job['prompt_id']])
        self.assertTrue(self.jobs.get(job['id'])['cancel_requested'])
        self.compute.current = {'state':'absent','outputs':[]}
        self.assertEqual((await self.jobs.refresh(job['id']))['state'], 'cancelled')
        await self.jobs.cancel(job['id'])
        self.assertEqual(len(self.compute.cancellations),1)

    async def test_real_output_is_registered_and_escape_is_rejected(self):
        job = await self.jobs.create(str(uuid.uuid4()),'sdxl',{}, {})
        output = self.paths.output / 'result.png'
        output.write_bytes(png())
        self.compute.current = {'state':'completed','outputs':[{'filename':'result.png','subfolder':'','type':'output'}]}
        complete = await self.jobs.refresh(job['id'])
        self.assertEqual(complete['state'], 'completed')
        self.assertEqual(self.files.resolve(complete['outputs'][0]['id']).read_bytes(), png())
        other = await self.jobs.create(str(uuid.uuid4()),'sdxl',{}, {})
        self.compute.current = {'state':'completed','outputs':[{'filename':'../outside.png','subfolder':'','type':'output'}]}
        self.assertEqual((await self.jobs.refresh(other['id']))['state'], 'error')

    async def test_failed_result_transfer_can_recover_without_recalculating(self):
        job = await self.jobs.create(str(uuid.uuid4()),'sdxl',{}, {})
        output = self.paths.output / 'result.png'
        output.write_bytes(png())
        self.compute.current = {'state':'completed','outputs':[{'filename':'result.png','type':'output'}]}
        download = self.compute.download_output
        async def disconnected(item, prompt_id):
            raise UiError('comfy_output','Ergebnisverbindung unterbrochen.',status=503)
        self.compute.download_output = disconnected
        interrupted = await self.jobs.refresh(job['id'])
        self.assertEqual(interrupted['state'],'unknown')
        self.assertEqual(interrupted['outputs'],[])
        self.compute.download_output = download
        recovered = await self.jobs.refresh(job['id'])
        self.assertEqual(recovered['state'],'completed')
        self.assertEqual(len(recovered['outputs']),1)
        self.assertNotIn('error_code',recovered)
        self.assertNotIn('details',recovered)
        self.assertEqual(len(self.compute.submissions),1)

    async def test_partial_result_import_is_persistent_and_not_duplicated_on_reconnection(self):
        job = await self.jobs.create(str(uuid.uuid4()),'sdxl',{}, {})
        self.compute.current = {'state':'completed','outputs':[{'filename':'one.png','type':'output'},{'filename':'two.png','type':'output'}]}
        calls = []
        failures = 2
        async def download(item, prompt_id):
            nonlocal failures
            calls.append(item['filename'])
            if item['filename'] == 'two.png' and failures:
                failures -= 1
                raise UiError('comfy_output','Unterbrochen.',status=503)
            path = self.paths.output / (uuid.uuid4().hex + '.png')
            path.write_bytes(png())
            return path
        self.compute.download_output = download
        first = await self.jobs.refresh(job['id'])
        self.assertEqual(first['state'],'unknown')
        self.assertEqual(len(first['outputs']),1)
        first_id = first['outputs'][0]['id']
        await self.jobs.refresh(job['id'])
        final = await self.jobs.refresh(job['id'])
        self.assertEqual(final['state'],'completed')
        self.assertEqual(final['outputs'][0]['id'],first_id)
        self.assertEqual(calls,['one.png','two.png','two.png','two.png'])
        self.assertEqual(len(list(self.paths.output.glob('*.png'))),2)
        self.assertEqual(len(self.compute.submissions),1)

class ComfyHttpTests(unittest.IsolatedAsyncioTestCase):
    async def test_cancel_uses_exact_atomic_endpoint_and_keeps_false(self):
        self.assertIsNotNone(JobService, 'Comfy-Anbindung noch nicht implementiert')
        from aiohttp import web
        from aiohttp.test_utils import TestServer
        box = Sandbox(self)
        paths = ProjectPaths(box.root)
        calls = []
        async def cancel(request):
            calls.append(request.path)
            return web.json_response({'cancelled':False})
        app = web.Application()
        app.router.add_post('/api/jobs/{id}/cancel',cancel)
        server = TestServer(app)
        await server.start_server()
        self.addAsyncCleanup(server.close)
        client = ComfyClient(paths, base_url=str(server.make_url('/')).rstrip('/'))
        self.addAsyncCleanup(client.close)
        identifier = str(uuid.uuid4())
        self.assertFalse(await client.cancel(identifier))
        self.assertEqual(calls, ['/api/jobs/' + identifier + '/cancel'])
