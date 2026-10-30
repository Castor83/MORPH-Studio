import asyncio
import copy
import json
import sys
import unittest
import uuid
from pathlib import Path

from aiohttp import web
from aiohttp.test_utils import TestServer

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from morph_ui.comfy import ComfyClient
from morph_ui.paths import ProjectPaths
from morph_ui.catalog import Catalog
from morph_ui.files import FileStore
from morph_ui.jobs import JobService
from support import Sandbox, png
from test_jobs import Compute


GRAPH = {'1': {'class_type': 'KSampler', 'inputs': {}},
         '2': {'class_type': 'SaveImage', 'inputs': {}}}


class ProgressTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.paths = ProjectPaths(Sandbox(self).root)
        self.prompt_id, self.client_id = str(uuid.uuid4()), str(uuid.uuid4())
        self.events = []
        loop, errors = asyncio.get_running_loop(), []
        previous_handler = loop.get_exception_handler()
        loop.set_exception_handler(lambda unused_loop, context: errors.append(context))
        async def check_cleanup():
            try:
                await asyncio.sleep(.02)
                self.assertEqual(errors, [], 'Socket cleanup raised an event-loop exception')
                self.assertFalse([task for task in asyncio.all_tasks() if task is not asyncio.current_task()
                                  and task.get_name().startswith('morph-progress-')])
            finally:
                loop.set_exception_handler(previous_handler)
        self.addAsyncCleanup(check_cleanup)

    async def client_for(self, app):
        server = TestServer(app)
        await server.start_server()
        self.addAsyncCleanup(server.close)
        client = ComfyClient(self.paths, str(server.make_url('/')).rstrip('/'))
        self.addAsyncCleanup(client.close)
        self.assertTrue(hasattr(client, 'watch_progress'), 'Live-Knotenfortschritt fehlt')
        return client

    async def watch(self, client):
        await client.watch_progress(self.prompt_id, self.client_id, GRAPH, self.events.append)

    async def until(self, predicate):
        async with asyncio.timeout(2):
            while not predicate():
                await asyncio.sleep(.005)

    async def test_socket_is_connected_before_submit_with_exact_persisted_client(self):
        order = []
        app = web.Application()
        async def ws_handler(request):
            self.assertEqual(request.query['clientId'], self.client_id)
            # A healthy handshake slower than the former 300ms observer deadline.
            await asyncio.sleep(.4)
            ws = web.WebSocketResponse()
            await ws.prepare(request)
            order.append('ws')
            async for unused in ws:
                pass
            return ws
        async def submit(request):
            body = await request.json()
            self.assertEqual(body['client_id'], self.client_id)
            self.assertEqual(body['prompt_id'], self.prompt_id)
            order.append('submit')
            return web.json_response({'prompt_id': self.prompt_id})
        app.router.add_get('/ws', ws_handler)
        app.router.add_post('/prompt', submit)
        client = await self.client_for(app)
        await self.watch(client)
        await client.submit(GRAPH, self.prompt_id, client_id=self.client_id)
        self.assertEqual(order, ['ws', 'submit'])

    async def test_events_filter_prompt_node_numbers_and_binary_and_reset_node_percent(self):
        app = web.Application()
        messages = [
            {'type': 'status', 'data': {'prompt_id': self.prompt_id, 'value': 9}},
            {'type': 'executing', 'data': {'node': '1'}},
            {'type': 'progress', 'data': {'prompt_id': str(uuid.uuid4()), 'node': '1', 'value': 1, 'max': 2}},
            {'type': 'progress', 'data': {'prompt_id': self.prompt_id, 'node': 'foreign', 'value': 1, 'max': 2}},
        ]
        for value, maximum in [(True, 4), (1, False), (float('nan'), 3), (1, float('inf')), (-1, 4), (5, 4), (0, 0), ('1', 4)]:
            messages.append({'type': 'progress', 'data': {'prompt_id': self.prompt_id, 'node': '1', 'value': value, 'max': maximum}})
        messages += [
            {'type': 'execution_start', 'data': {'prompt_id': self.prompt_id}},
            {'type': 'execution_cached', 'data': {'prompt_id': self.prompt_id, 'nodes': ['2', 'foreign']}},
            {'type': 'progress', 'data': {'prompt_id': self.prompt_id, 'node': '1', 'value': 2, 'max': 4}},
            {'type': 'executing', 'data': {'prompt_id': self.prompt_id, 'node': '2'}},
            {'type': 'execution_interrupted', 'data': {'prompt_id': self.prompt_id, 'node_id': '2'}},
            {'type': 'execution_success', 'data': {'prompt_id': self.prompt_id}},
        ]
        async def ws_handler(request):
            ws = web.WebSocketResponse()
            await ws.prepare(request)
            await ws.send_bytes(b'preview ignored')
            await ws.send_str('malformed json')
            for message in messages:
                await ws.send_str(json.dumps(message))
            async for unused in ws:
                pass
            return ws
        app.router.add_get('/ws', ws_handler)
        client = await self.client_for(app)
        await self.watch(client)
        await self.until(lambda: any(e.get('event') == 'execution_success' for e in self.events))
        events = [e for e in self.events if e.get('event')]
        self.assertEqual([e['event'] for e in events], ['execution_start', 'execution_cached', 'progress', 'executing', 'execution_interrupted', 'execution_success'])
        self.assertEqual(events[1]['cached_nodes'], ['2'])
        self.assertEqual(events[2]['percent'], 50)
        self.assertEqual(events[2]['node_type'], 'KSampler')
        self.assertIsNone(events[3]['percent'])
        self.assertIsNone(events[3]['value'])
        self.assertEqual(events[3]['node_type'], 'SaveImage')

    async def test_disconnect_reconnect_reuses_client_without_resubmitting_and_closes_tasks(self):
        app, clients, sockets = web.Application(), [], []
        second = asyncio.Event()
        async def ws_handler(request):
            clients.append(request.query['clientId'])
            ws = web.WebSocketResponse()
            await ws.prepare(request)
            sockets.append(ws)
            if len(clients) == 1:
                await ws.close()
            else:
                await ws.send_json({'type': 'executing', 'data': {'node': '1'}})
                second.set()
                async for unused in ws:
                    pass
            return ws
        app.router.add_get('/ws', ws_handler)
        client = await self.client_for(app)
        await self.watch(client)
        await asyncio.wait_for(second.wait(), 2)
        self.assertEqual(clients, [self.client_id, self.client_id])
        self.assertFalse(any(e.get('event') for e in self.events))
        await client.close()
        self.assertFalse(client.progress_watchers)
        self.assertFalse([t for t in asyncio.all_tasks() if t is not asyncio.current_task() and t.get_name().startswith('morph-progress-')])

    async def test_unavailable_socket_is_bounded_and_does_not_break_polling(self):
        app, calls = web.Application(), []
        async def unavailable(request):
            calls.append('ws')
            return web.Response(status=404)
        async def queue(request):
            return web.json_response({'queue_running': [[0, self.prompt_id]], 'queue_pending': []})
        async def history(request):
            return web.json_response({})
        app.router.add_get('/ws', unavailable)
        app.router.add_get('/queue', queue)
        app.router.add_get('/history/{id}', history)
        client = await self.client_for(app)
        await self.watch(client)
        self.assertEqual((await client.poll(self.prompt_id))['state'], 'running')
        await self.until(lambda: any(e['connection'] == 'unavailable' for e in self.events))
        before = len(calls)
        await self.watch(client)
        self.assertEqual(len(calls), before, 'Repeated reads must not reset an exhausted retry budget')

    async def test_real_job_client_binds_saved_identity_before_socket_and_keeps_history_authority(self):
        app, sockets, submitted = web.Application(), {}, []
        files = FileStore(self.paths)
        self.addCleanup(files.close)
        async def ws_handler(request):
            ws = web.WebSocketResponse()
            await ws.prepare(request)
            sockets[request.query['clientId']] = ws
            async for unused in ws:
                pass
            return ws
        async def queue(request):
            return web.json_response({'queue_running': [[0, submitted[0]]] if submitted else [], 'queue_pending': []})
        async def submit(request):
            body = await request.json()
            self.assertIn(body['client_id'], sockets, 'Submission preceded websocket connection')
            saved = jobs.list_recent()[0]
            self.assertEqual(saved['client_id'], body['client_id'])
            self.assertEqual(saved['prompt_id'], body['prompt_id'])
            submitted.append(body['prompt_id'])
            sampler = next(node for node, spec in body['prompt'].items() if spec['class_type'] == 'KSampler')
            await sockets[body['client_id']].send_json({'type': 'progress', 'data': {
                'prompt_id': body['prompt_id'], 'node': sampler, 'value': 2, 'max': 8}})
            await sockets[body['client_id']].send_json({'type': 'execution_success', 'data': {'prompt_id': body['prompt_id']}})
            await asyncio.sleep(.02)
            return web.json_response({'prompt_id': body['prompt_id']})
        async def history(request):
            return web.json_response({})
        app.router.add_get('/ws', ws_handler)
        app.router.add_get('/queue', queue)
        app.router.add_get('/history/{id}', history)
        app.router.add_post('/prompt', submit)
        client = await self.client_for(app)
        async def no_start():
            pass
        async def no_models(graph):
            return []
        client.ensure_ready, client.model_readiness = no_start, no_models
        jobs = JobService(self.paths, Catalog(self.paths), files, client)
        self.addCleanup(jobs.close)
        created = await jobs.create(str(uuid.uuid4()), 'sdxl', {}, {})
        self.assertEqual(created['progress']['event'], 'execution_success')
        self.assertEqual(created['state'], 'queued')
        self.assertEqual((await jobs.refresh(created['id']))['state'], 'running')
        self.assertEqual(submitted, [created['prompt_id']])
        await client.close()

    async def test_pre_submit_queue_rejection_closes_socket_without_waiting_for_event(self):
        app, connected, closed = web.Application(), asyncio.Event(), asyncio.Event()
        async def ws_handler(request):
            ws = web.WebSocketResponse()
            await ws.prepare(request)
            connected.set()
            try:
                async for unused in ws:
                    pass
            finally:
                closed.set()
            return ws
        async def queue(request):
            return web.json_response({'queue_running': [[0, 'foreign']] if connected.is_set() else [], 'queue_pending': []})
        app.router.add_get('/ws', ws_handler)
        app.router.add_get('/queue', queue)
        client = await self.client_for(app)
        async def no_start():
            pass
        async def no_models(graph):
            return []
        client.ensure_ready, client.model_readiness = no_start, no_models
        files = FileStore(self.paths)
        self.addCleanup(files.close)
        jobs = JobService(self.paths, Catalog(self.paths), files, client)
        self.addCleanup(jobs.close)
        created = await jobs.create(str(uuid.uuid4()), 'sdxl', {}, {})
        self.assertEqual(created['state'], 'error')
        self.assertEqual(created['error_code'], 'queue_busy')
        await asyncio.wait_for(closed.wait(), 1)
        await self.until(lambda: all(w.task.done() for w in client.progress_watchers.values()))
        self.assertFalse(client.session.closed, 'The watcher should close independently of app shutdown')


class ProgressCompute(Compute):
    def __init__(self, paths):
        super().__init__(paths)
        self.watches, self.callbacks, self.clients = [], {}, []
        self.before_submit = self.during_poll = self.during_cancel = None

    async def watch_progress(self, prompt_id, client_id, graph, callback):
        self.watches.append((prompt_id, client_id, copy.deepcopy(graph)))
        self.callbacks[prompt_id] = callback
        callback({'connection': 'connected'})

    async def submit(self, graph, prompt_id, client_id=None):
        self.clients.append(client_id)
        if self.before_submit:
            self.before_submit(prompt_id)
        return await super().submit(graph, prompt_id)

    async def poll(self, prompt_id):
        if self.during_poll:
            self.during_poll(prompt_id)
        return await super().poll(prompt_id)

    async def cancel(self, prompt_id):
        if self.during_cancel:
            self.during_cancel(prompt_id)
        return await super().cancel(prompt_id)


class JobProgressTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.paths = ProjectPaths(Sandbox(self).root)
        self.catalog, self.files = Catalog(self.paths), FileStore(self.paths)
        self.addCleanup(self.files.close)
        self.compute = ProgressCompute(self.paths)
        self.jobs = JobService(self.paths, self.catalog, self.files, self.compute)
        self.addCleanup(self.jobs.close)

    def emit(self, prompt_id, **fields):
        event = dict(event='progress', node_id='3', node_type='KSampler', value=1, max=4, percent=25, connection='connected')
        event.update(fields)
        self.compute.callbacks[prompt_id](event)

    async def test_ids_are_durable_unique_and_callback_during_submit_is_not_overwritten(self):
        self.compute.before_submit = lambda pid: self.emit(pid)
        first = await self.jobs.create(str(uuid.uuid4()), 'sdxl', {}, {})
        self.assertIn('client_id', first, 'Per-job websocket identity missing')
        self.assertEqual(first['client_id'], self.compute.clients[0])
        self.assertEqual(first['progress']['percent'], 25)
        self.assertEqual(first['state'], 'queued')
        self.assertEqual(self.compute.watches[0][:2], (first['prompt_id'], first['client_id']))
        self.assertEqual(self.jobs.get(first['id'])['client_id'], first['client_id'])
        self.compute.current = {'state': 'completed', 'outputs': []}
        await self.jobs.refresh(first['id'])
        second = await self.jobs.create(str(uuid.uuid4()), 'sdxl', {}, {})
        self.assertNotEqual(first['client_id'], second['client_id'])

    async def test_poll_cancel_and_terminal_preserve_progress_and_history_authority(self):
        job = await self.jobs.create(str(uuid.uuid4()), 'sdxl', {}, {})
        self.assertTrue(self.compute.callbacks, 'Progress observer missing')
        self.compute.callbacks[job['prompt_id']]({'event': 'execution_success', 'connection': 'connected'})
        self.assertEqual(self.jobs.get(job['id'])['state'], 'queued')
        self.compute.during_poll = lambda pid: self.emit(pid)
        refreshed = await self.jobs.refresh(job['id'])
        self.assertEqual(refreshed['progress']['percent'], 25)
        self.compute.during_cancel = lambda pid: self.emit(pid, value=2, percent=50)
        cancelled = await self.jobs.cancel(job['id'])
        self.assertTrue(cancelled['cancel_requested'])
        self.assertEqual(cancelled['progress']['percent'], 50)
        self.assertEqual(self.compute.cancellations, [job['prompt_id']])
        self.compute.current = {'state': 'cancelled', 'outputs': []}
        terminal = await self.jobs.refresh(job['id'])
        before = copy.deepcopy(terminal['progress'])
        self.emit(job['prompt_id'], value=3, percent=75)
        self.assertEqual(self.jobs.get(job['id'])['progress'], before)

    async def test_reopen_active_job_resumes_observer_without_submit_and_legacy_still_polls(self):
        job = await self.jobs.create(str(uuid.uuid4()), 'sdxl', {}, {})
        self.assertIn('client_id', job, 'Saved progress identity missing')
        restored_compute = ProgressCompute(self.paths)
        restored = JobService(self.paths, self.catalog, self.files, restored_compute)
        self.addCleanup(restored.close)
        restored.list_recent()
        await asyncio.sleep(.01)
        self.assertEqual(len(restored_compute.watches), 1)
        self.assertEqual(restored_compute.watches[0][:2], (job['prompt_id'], job['client_id']))
        self.assertEqual(restored_compute.submissions, [])
        legacy = restored.get(job['id'])
        legacy.pop('client_id')
        restored.store(legacy)
        count = len(restored_compute.watches)
        self.assertEqual((await restored.refresh(job['id']))['state'], 'queued')
        self.assertEqual(len(restored_compute.watches), count)

    async def test_setup_phase_visible_while_service_start_is_pending(self):
        entered, release = asyncio.Event(), asyncio.Event()
        async def ensure_ready():
            entered.set()
            await release.wait()
        self.compute.ensure_ready = ensure_ready
        creating = asyncio.create_task(self.jobs.create(str(uuid.uuid4()), 'sdxl', {}, {}))
        await asyncio.wait_for(entered.wait(), 2)
        try:
            current = self.jobs.list_recent()[0]
            self.assertEqual(current.get('phase'), 'connecting')
            self.assertEqual((await self.jobs.refresh(current['id']))['phase'], 'connecting')
        finally:
            release.set()
            await creating

    async def test_queue_that_becomes_busy_during_socket_handshake_prevents_submit(self):
        original = self.compute.watch_progress
        async def occupied_during_watch(*args):
            await original(*args)
            self.compute.foreign = True
        self.compute.watch_progress = occupied_during_watch
        job = await self.jobs.create(str(uuid.uuid4()), 'sdxl', {}, {})
        self.assertEqual(self.compute.submissions, [], 'Foreign queue arrived during observer connection')
        self.assertEqual(job['state'], 'error')
        self.assertEqual(job['error_code'], 'queue_busy')

    async def test_output_import_await_does_not_erase_newer_node_observation(self):
        job = await self.jobs.create(str(uuid.uuid4()), 'sdxl', {}, {})
        target = self.paths.output / 'sample.png'
        target.write_bytes(png())
        original = self.compute.download_output
        async def observed_during_download(item, prompt_id):
            self.emit(prompt_id, value=3, percent=75)
            return await original(item, prompt_id)
        self.compute.download_output = observed_during_download
        self.compute.current = {'state': 'completed', 'outputs': [{'filename': 'sample.png'}]}
        completed = await self.jobs.refresh(job['id'])
        self.assertEqual(completed['state'], 'completed')
        self.assertEqual(completed['progress']['percent'], 75)
        self.assertEqual(len(completed['outputs']), 1)


if __name__ == '__main__':
    unittest.main()
