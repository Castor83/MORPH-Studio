import asyncio
from datetime import datetime
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, Mock

from aiohttp.test_utils import TestClient, TestServer

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from morph_ui.comfy import ComfyClient
from morph_ui.jobs import JobService, ACTIVE
from morph_ui.paths import ProjectPaths, UiError
from morph_ui.server import create_app

HEADERS = {'Host':'127.0.0.1:8765', 'Origin':'http://127.0.0.1:8765', 'X-MORPH-Request':'1'}
STATS = {'system':{'ram_total':1000, 'ram_free':400, 'argv':['private-path']},
         'devices':[{'name':'GPU fixture', 'type':'cuda', 'index':0, 'vram_total':100, 'vram_free':25},
                    {'name':'CPU fixture', 'type':'cpu', 'index':None, 'vram_total':1000, 'vram_free':400}]}


class ResourceTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        base = Path(__file__).resolve().parents[2] / 'temp'
        self.temp = tempfile.TemporaryDirectory(prefix='resources-', dir=base)
        self.addCleanup(self.temp.cleanup)
        self.paths = ProjectPaths(self.temp.name)
        self.comfy = ComfyClient(self.paths)
        self.addAsyncCleanup(self.comfy.close)
        self.handle = object()
        self.guard = SimpleNamespace(
            COMFY_URL='http://127.0.0.1:8188',
            open_managed_listener=Mock(return_value=({'pid':123}, self.handle)),
            verify_managed_listener=Mock(), verify_managed_handle=Mock(),
            inspect_managed_listener=Mock(return_value={'managed':True, 'pid':123}),
            close_process_handle=Mock(), ensure_comfy=Mock(side_effect=AssertionError('no start')),
            stop_managed=Mock(side_effect=AssertionError('no stop')))
        self.comfy.guard = self.guard
        self.calls = []

        async def request(method, endpoint, payload=None):
            self.calls.append((method, endpoint, payload))
            if endpoint == '/system_stats':
                return STATS
            if endpoint == '/queue':
                return {'queue_running':[], 'queue_pending':[]}
            if endpoint == '/free':
                return {}
            raise AssertionError(endpoint)

        self.comfy.request = AsyncMock(side_effect=request)
        self.jobs = JobService(self.paths, None, None, self.comfy)
        self.addCleanup(self.jobs.close)

    def add_job(self, state, index=0):
        job = {'id':str(index), 'state':state}
        self.jobs.db.execute('INSERT INTO jobs VALUES (?,?,?,?)',
                             (str(index), 'request'+str(index), 'prompt'+str(index), json.dumps(job)))

    async def test_reads_real_stats_fields_with_source_timestamp_and_unknown_models(self):
        self.assertTrue(callable(getattr(self.jobs, 'resources', None)), 'Ressourcenabfrage fehlt')
        result = await self.jobs.resources()
        self.assertTrue(result['available'])
        self.assertEqual(result['source'], 'ComfyUI /system_stats')
        datetime.fromisoformat(result['measured_at'])
        self.assertEqual(result['devices'][0]['vram_used'], 75)
        self.assertEqual(result['devices'][1]['type'], 'cpu')
        self.assertEqual(result['ram'], {'total':1000, 'free':400, 'used':600})
        self.assertEqual(result['model_state'], 'unknown')
        self.assertTrue(result['unload']['allowed'])
        self.assertNotIn('private-path', json.dumps(result))
        self.assertTrue(all(call[0] == 'GET' for call in self.calls))
        self.guard.ensure_comfy.assert_not_called()
        self.guard.stop_managed.assert_not_called()

    async def test_malformed_missing_or_inconsistent_numbers_are_never_invented(self):
        self.assertTrue(callable(getattr(self.jobs, 'resources', None)), 'Ressourcenabfrage fehlt')
        for number in [True, '100', -1, float('nan'), float('inf'), None]:
            with self.subTest(number=number):
                self.comfy.request = AsyncMock(return_value={'system':{'ram_total':number, 'ram_free':2},
                    'devices':[{'vram_total':100, 'vram_free':200}]})
                result = await self.jobs.resources()
                self.assertIsNone(result['ram']['total'])
                self.assertIsNone(result['ram']['used'])
                self.assertIsNone(result['devices'][0]['vram_free'])
                self.assertIsNone(result['devices'][0]['vram_used'])
                json.dumps(result, allow_nan=False)

    async def test_offline_status_is_nonfatal_and_does_not_start_anything(self):
        self.assertTrue(callable(getattr(self.jobs, 'resources', None)), 'Ressourcenabfrage fehlt')
        self.comfy.request = AsyncMock(side_effect=UiError('comfy_connection', 'Nicht erreichbar', status=503))
        result = await self.jobs.resources()
        self.assertFalse(result['available'])
        self.assertIsNone(result['measured_at'])
        self.assertEqual(result['devices'], [])
        self.assertFalse(result['unload']['allowed'])
        self.guard.ensure_comfy.assert_not_called()

    async def test_compatible_or_adopted_service_can_show_stats_but_cannot_free(self):
        self.assertTrue(callable(getattr(self.jobs, 'resources', None)), 'Ressourcenabfrage fehlt')
        self.guard.inspect_managed_listener.side_effect = RuntimeError('Keine eigene Startquittung')
        result = await self.jobs.resources()
        self.assertTrue(result['available'])
        self.assertFalse(result['unload']['allowed'])
        self.guard.open_managed_listener.side_effect = RuntimeError('Keine eigene Startquittung')
        with self.assertRaises(UiError):
            await self.jobs.free_resources()
        self.assertFalse(any(call[0] == 'POST' for call in self.calls))

    async def test_every_active_state_and_old_job_beyond_recent_thirty_blocks_free(self):
        self.assertTrue(callable(getattr(self.jobs, 'free_resources', None)), 'Bewusste Freigabe fehlt')
        for state in ACTIVE | {'unrecognized'}:
            with self.subTest(state=state):
                self.jobs.db.execute('DELETE FROM jobs')
                self.add_job(state)
                for index in range(1, 32):
                    self.add_job('completed', index)
                self.jobs.db.commit()
                self.assertTrue(all(job['state'] == 'completed' for job in self.jobs.list_recent()))
                self.assertFalse((await self.jobs.resources())['unload']['allowed'])
                with self.assertRaises(UiError):
                    await self.jobs.free_resources()
        self.assertFalse(any(call[0] == 'POST' for call in self.calls))

    async def test_corrupt_job_record_blocks_free(self):
        self.assertTrue(callable(getattr(self.jobs, 'free_resources', None)), 'Bewusste Freigabe fehlt')
        self.jobs.db.execute("INSERT INTO jobs VALUES ('broken','r','p','not-json')")
        self.jobs.db.commit()
        with self.assertRaises(UiError):
            await self.jobs.free_resources()
        self.assertFalse((await self.jobs.resources())['unload']['allowed'])

    async def test_busy_or_unreadable_queue_blocks_free_even_after_initial_empty_queue(self):
        self.assertTrue(callable(getattr(self.jobs, 'free_resources', None)), 'Bewusste Freigabe fehlt')
        for queue in [{'queue_running':[[1,'foreign']], 'queue_pending':[]},
                      {'queue_running':[], 'queue_pending':[[1,'foreign']]}, {},
                      {'queue_running':None, 'queue_pending':[]}]:
            with self.subTest(queue=queue):
                self.calls.clear()
                self.comfy.request = AsyncMock(side_effect=[{'queue_running':[], 'queue_pending':[]}, queue])
                with self.assertRaises(UiError):
                    await self.jobs.free_resources()
                self.assertTrue(all(call.args[0] == 'GET' for call in self.comfy.request.call_args_list))
                self.guard.close_process_handle.assert_called_with(self.handle)

    async def test_manual_free_has_same_handle_final_checks_and_only_acceptance_receipt(self):
        self.assertTrue(callable(getattr(self.jobs, 'free_resources', None)), 'Bewusste Freigabe fehlt')
        result = await self.jobs.free_resources()
        self.assertEqual(result, {'accepted':True, 'completed':False, 'message':'Freigabe angefordert'})
        self.assertEqual(self.calls, [('GET','/queue',None), ('GET','/queue',None),
                                     ('POST','/free',{'unload_models':True, 'free_memory':True})])
        self.assertEqual(self.guard.verify_managed_listener.call_count, 2)
        self.assertTrue(all(call.args == ({'pid':123}, self.handle)
                            for call in self.guard.verify_managed_listener.call_args_list))
        self.guard.close_process_handle.assert_called_once_with(self.handle)
        self.guard.stop_managed.assert_not_called()

    async def test_changed_listener_before_free_blocks_mutation_and_closes_handle(self):
        self.assertTrue(callable(getattr(self.jobs, 'free_resources', None)), 'Bewusste Freigabe fehlt')
        self.guard.verify_managed_listener.side_effect = RuntimeError('Listener geändert')
        with self.assertRaises(UiError):
            await self.jobs.free_resources()
        self.assertFalse(any(call[0] == 'POST' for call in self.calls))
        self.guard.close_process_handle.assert_called_once_with(self.handle)

    async def test_process_receipt_for_8188_cannot_authorize_another_http_target(self):
        self.comfy.base_url = 'http://127.0.0.1:9999'
        self.assertFalse((await self.jobs.resources())['unload']['allowed'])
        with self.assertRaises(UiError):
            await self.jobs.free_resources()
        self.assertFalse(any(call[0] == 'POST' for call in self.calls))
        self.guard.open_managed_listener.assert_not_called()

    async def test_listener_change_during_final_queue_read_blocks_free(self):
        queue_reads = 0
        async def request(method, endpoint, payload=None):
            nonlocal queue_reads
            self.calls.append((method, endpoint, payload))
            if endpoint == '/queue':
                queue_reads += 1
                if queue_reads == 2:
                    self.guard.verify_managed_listener.side_effect = RuntimeError('Listener während Queueabfrage gewechselt')
                return {'queue_running':[], 'queue_pending':[]}
            return {}
        self.comfy.request = AsyncMock(side_effect=request)
        with self.assertRaises(UiError):
            await self.jobs.free_resources()
        self.assertFalse(any(call[0] == 'POST' for call in self.calls))
        self.guard.close_process_handle.assert_called_once_with(self.handle)

    async def test_timeout_is_never_retried_and_handle_is_closed(self):
        self.assertTrue(callable(getattr(self.jobs, 'free_resources', None)), 'Bewusste Freigabe fehlt')
        self.comfy.request = AsyncMock(side_effect=[{'queue_running':[], 'queue_pending':[]},
            {'queue_running':[], 'queue_pending':[]}, UiError('comfy_connection','Unklar',status=503)])
        with self.assertRaises(UiError):
            await self.jobs.free_resources()
        self.assertEqual(self.comfy.request.await_count, 3)
        self.guard.close_process_handle.assert_called_once_with(self.handle)

    async def test_backend_error_details_are_not_exposed_in_resource_errors(self):
        self.comfy.request = AsyncMock(side_effect=[{'queue_running':[], 'queue_pending':[]},
            {'queue_running':[], 'queue_pending':[]},
            UiError('comfy_rejected','Backend abgelehnt', {'private_path':'E:/private/model'}, status=500)])
        with self.assertRaises(UiError) as context:
            await self.jobs.free_resources()
        self.assertIsNone(context.exception.details)
        self.assertEqual(self.comfy.request.await_count, 3)

    async def test_free_holds_job_lock_until_backend_receipt(self):
        self.assertTrue(callable(getattr(self.jobs, 'free_resources', None)), 'Bewusste Freigabe fehlt')
        entered, release = asyncio.Event(), asyncio.Event()
        async def free():
            self.assertTrue(self.jobs.lock.locked())
            entered.set()
            await release.wait()
            return {'accepted':True, 'completed':False, 'message':'Freigabe angefordert'}
        self.comfy.free_resources = free
        task = asyncio.create_task(self.jobs.free_resources())
        await entered.wait()
        competitor = asyncio.create_task(self.jobs.prepare_restart())
        await asyncio.sleep(0)
        self.assertFalse(competitor.done())
        release.set()
        await task
        await competitor


class ResourceRouteTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.jobs = SimpleNamespace(resources=AsyncMock(return_value={'available':False}),
            free_resources=AsyncMock(return_value={'accepted':True, 'completed':False, 'message':'Freigabe angefordert'}),
            comfy=SimpleNamespace(), close=lambda:None)
        app = create_app(None, None, SimpleNamespace(), self.jobs, SimpleNamespace(close=lambda:None),
                         settings=SimpleNamespace())
        self.client = TestClient(TestServer(app))
        await self.client.start_server()
        self.addAsyncCleanup(self.client.close)

    async def test_resource_routes_require_explicit_empty_manual_action(self):
        response = await self.client.get('/api/resources', headers=HEADERS)
        self.assertEqual(response.status, 200)
        self.jobs.free_resources.assert_not_awaited()
        for headers, body, status in [(HEADERS | {'Origin':'https://foreign.example'}, {}, 403),
                                      ({'Host':'127.0.0.1:8765'}, {}, 403),
                                      (HEADERS, {'model':'other'}, 400), (HEADERS, {}, 200)]:
            response = await self.client.post('/api/resources/free', headers=headers, json=body)
            self.assertEqual(response.status, status)
        self.jobs.free_resources.assert_awaited_once()
        self.assertFalse((await response.json())['data']['completed'])


if __name__ == '__main__':
    unittest.main()
