"""Emergency release contracts; temporary DB, transport/native-handle doubles only."""
import asyncio
from contextlib import ExitStack
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, Mock, patch

from aiohttp.test_utils import TestClient, TestServer

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from morph_ui.comfy import ComfyClient
from morph_ui.jobs import ACTIVE, JobService
from morph_ui.paths import ProjectPaths, UiError
from morph_ui.server import create_app
from test_server import HEADERS

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('emergency_guard_fixture', ROOT / 'tools/lmstudio-wan-chat/start_mcp.py')
guard = importlib.util.module_from_spec(spec)
spec.loader.exec_module(guard)


class EmergencyReleaseTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='emergency-release-', dir=ROOT / 'temp')
        self.addCleanup(self.temp.cleanup)
        self.paths = ProjectPaths(self.temp.name)
        self.comfy = ComfyClient(self.paths)
        self.comfy.guard = guard
        self.addAsyncCleanup(self.comfy.close)
        self.jobs = JobService(self.paths, None, None, self.comfy)
        self.addCleanup(self.jobs.close)
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(patch.object(guard, 'ROOT', self.paths.root))
        self.stack.enter_context(patch.object(guard, 'PYTHON', self.paths.python))
        self.stack.enter_context(patch.object(guard, 'REPORT_DIR', self.paths.root / 'receipts'))
        guard.REPORT_DIR.mkdir()
        self.receipt = {'schema_version':1, 'managed':True, 'state':'running', 'pid':12345,
                        'creation_filetime':'134055000000000123', 'project_root':str(self.paths.root),
                        'python':str(self.paths.python),
                        'script':str(self.paths.root / 'ComfyUI_windows_portable/ComfyUI/main.py')}
        guard.save_owned_receipt(dict(self.receipt))
        self.handle = object()
        self.live, self.native_confirmed, self.rebound = True, True, False
        self.events = []
        def wait(handle, timeout):
            self.assertIs(handle, self.handle)
            return 258 if self.live or not self.native_confirmed else 0
        def terminate(handle, code):
            self.assertIs(handle, self.handle)
            self.events.append('terminate')
            self.live = False
            return True
        def inspect():
            self.events.append('inspect')
            if self.rebound and not self.live:
                return {'ownership':'foreign', 'pid':999, 'message':'Another listener'}
            return {'ownership':'owned' if self.live else 'free', 'pid':12345 if self.live else None}
        self.kernel = SimpleNamespace(WaitForSingleObject=Mock(side_effect=wait),
                                      TerminateProcess=Mock(side_effect=terminate))
        for name, value in [('process_kernel', Mock(return_value=self.kernel)),
                            ('open_process_for_stop', Mock(return_value=self.handle)),
                            ('process_creation_filetime', Mock(return_value=self.receipt['creation_filetime'])),
                            ('process_executable', Mock(return_value=str(self.paths.python))),
                            ('inspect_listener_details', Mock(side_effect=inspect)),
                            ('close_process_handle', Mock()),
                            ('ensure_comfy', Mock(side_effect=AssertionError('No automatic restart')))]:
            self.stack.enter_context(patch.object(guard, name, value))
        self.queue_reads = 0
        async def request(method, endpoint, payload=None):
            self.assertEqual((method, endpoint), ('GET', '/queue'))
            self.queue_reads += 1
            self.events.append('queue')
            return {'queue_running':[], 'queue_pending':[]}
        self.comfy.request = AsyncMock(side_effect=request)

    async def release(self):
        self.assertTrue(callable(getattr(self.jobs, 'emergency_release', None)), 'Emergency stop is missing')
        return await self.jobs.emergency_release()

    def add_job(self, state):
        key = str(self.jobs.db.execute('SELECT COUNT(*) FROM jobs').fetchone()[0])
        self.jobs.db.execute('INSERT INTO jobs VALUES (?,?,?,?)', (key,key,key,json.dumps({'state':state})))

    async def test_idle_owned_stops_one_exact_handle_with_queue_and_final_identity_checks(self):
        result = await self.release()
        self.assertEqual({key:result[key] for key in ('completed','stopped','old_pid')},
                         {'completed':True,'stopped':True,'old_pid':12345})
        self.assertFalse(self.live)
        self.assertEqual(self.events.count('terminate'), 1)
        self.assertEqual(self.queue_reads, 2)
        self.assertEqual(self.events[-2:], ['terminate','inspect'])
        self.assertEqual(self.events[self.events.index('terminate') - 1], 'inspect')
        guard.close_process_handle.assert_called_once_with(self.handle)
        guard.ensure_comfy.assert_not_called()
        self.assertFalse(json.loads((guard.REPORT_DIR / 'mcp-comfy-owned.json').read_text())['managed'])

    async def test_all_old_unknown_and_corrupt_job_records_deny_before_native_access(self):
        for state in ACTIVE | {'unexpected'}:
            with self.subTest(state=state):
                self.jobs.db.execute('DELETE FROM jobs')
                self.add_job(state)
                for unused in range(31):
                    self.add_job('completed')
                self.jobs.db.commit()
                with self.assertRaises(UiError):
                    await self.release()
        for data in ('not-json', '[]', '{}'):
            self.jobs.db.execute('DELETE FROM jobs')
            self.jobs.db.execute('INSERT INTO jobs VALUES (?,?,?,?)', ('bad','bad','bad',data))
            self.jobs.db.commit()
            with self.assertRaises(UiError):
                await self.release()
        guard.open_process_for_stop.assert_not_called()
        self.assertEqual(self.queue_reads, 0)

    async def test_busy_language_and_persisted_unknown_even_foreign_endpoint_deny(self):
        self.comfy.resource_stats = AsyncMock(return_value={
            'system':{'ram_total':1000,'ram_free':500},
            'devices':[{'name':'Fixture GPU','type':'cuda','vram_total':100,'vram_free':50}]})
        self.comfy.resource_control = AsyncMock(return_value={'allowed':True})
        self.jobs.language_busy = True
        with self.assertRaises(UiError) as caught:
            await self.release()
        self.assertEqual(caught.exception.code, 'language_busy')
        self.assertFalse((await self.jobs.resources())['unload']['allowed'])
        self.jobs.language_busy = False
        for data in ('not-json', json.dumps({'instance_id':'foreign-model','endpoint':'http://127.0.0.1:9999'})):
            self.jobs.db.execute('INSERT OR REPLACE INTO language_operation VALUES (1,?)', (data,))
            self.jobs.db.commit()
            with self.assertRaises(UiError) as caught:
                await self.release()
            self.assertEqual(caught.exception.code, 'language_mutation_unknown')
            self.assertFalse((await self.jobs.resources())['unload']['allowed'])
        guard.open_process_for_stop.assert_not_called()

    async def test_external_idle_ollama_model_is_neither_queried_nor_unloaded(self):
        self.jobs.provider = SimpleNamespace(gpu_residency=AsyncMock(side_effect=AssertionError('Optional service')),
                                             unload=AsyncMock(side_effect=AssertionError('Foreign model')))
        self.assertTrue((await self.release())['completed'])
        self.jobs.provider.gpu_residency.assert_not_awaited()
        self.jobs.provider.unload.assert_not_awaited()

    async def test_queue_changing_at_second_read_or_unreadable_queue_never_stops(self):
        for second in ({'queue_running':[[1]],'queue_pending':[]}, {'queue_running':[], 'queue_pending':[[1]]},
                       UiError('comfy_connection','Disconnected'), {'invalid':'queue'}):
            with self.subTest(second=second):
                self.comfy.request = AsyncMock(side_effect=[{'queue_running':[], 'queue_pending':[]}, second])
                with self.assertRaises(UiError):
                    await self.release()
                self.assertTrue(self.live)
        self.assertNotIn('terminate', self.events)

    async def test_listener_change_during_last_queue_read_never_stops(self):
        async def request(method, endpoint, payload=None):
            self.queue_reads += 1
            if self.queue_reads == 2:
                guard.inspect_listener_details.side_effect = None
                guard.inspect_listener_details.return_value = {'ownership':'foreign','pid':999}
            return {'queue_running':[], 'queue_pending':[]}
        self.comfy.request = AsyncMock(side_effect=request)
        with self.assertRaises(UiError):
            await self.release()
        self.assertNotIn('terminate', self.events)

    async def test_wrong_endpoint_never_opens_native_handle(self):
        self.comfy.base_url = 'http://127.0.0.1:9999'
        with self.assertRaises(UiError):
            await self.release()
        guard.open_process_for_stop.assert_not_called()

    async def test_adopted_or_wrong_receipt_and_reused_native_identity_never_stop(self):
        for change in ({'managed':False}, {'project_root':'D:/other'}, {'creation_filetime':'134055000000000122'},
                       {'python':'C:/other/python.exe'}, {'pid':True}):
            with self.subTest(change=change):
                guard.save_owned_receipt(dict(self.receipt, **change))
                with self.assertRaises(UiError):
                    await self.release()
                self.assertTrue(self.live)
        self.assertNotIn('terminate', self.events)

    async def test_unconfirmed_native_exit_has_no_false_completion_or_second_termination(self):
        self.native_confirmed = False
        with self.assertRaises(UiError) as caught:
            await self.release()
        self.assertEqual(self.events.count('terminate'), 1)
        self.assertIn('nicht', caught.exception.message)
        guard.close_process_handle.assert_called_once_with(self.handle)

    async def test_rebound_port_after_confirmed_exit_is_error_without_another_stop(self):
        self.rebound = True
        with self.assertRaises(UiError) as caught:
            await self.release()
        self.assertFalse(self.live)
        self.assertEqual(self.events.count('terminate'), 1)
        self.assertIn('beendet', caught.exception.message)
        self.assertIn('nicht', caught.exception.message)

    async def test_duplicate_and_image_language_settings_actions_reject_while_emergency_runs(self):
        entered, finish = asyncio.Event(), asyncio.Event()
        async def delayed():
            entered.set()
            await finish.wait()
            return {'completed':True,'stopped':True,'old_pid':12345}
        self.comfy.emergency_release = delayed
        self.assertTrue(callable(getattr(self.jobs, 'emergency_release', None)), 'Emergency stop is missing')
        task = asyncio.create_task(self.jobs.emergency_release())
        await entered.wait()
        try:
            for operation in (self.jobs.emergency_release(), self.jobs.free_resources(), self.jobs.create('20261020-0000-4000-8000-000000000001','sdxl',{},{}),
                              self.jobs.language_action(SimpleNamespace(), 'load', 'model')):
                with self.assertRaises(UiError):
                    await asyncio.wait_for(operation, .5)
            with self.assertRaises(UiError):
                self.jobs.require_settings_change()
            self.assertTrue(self.jobs.lock.locked())
            self.assertFalse((await self.jobs.resources())['unload']['allowed'])
        finally:
            finish.set()
            await task
        self.assertFalse(self.jobs.lock.locked())

    async def test_cancelled_client_keeps_shared_gate_until_exact_stop_task_returns(self):
        entered, finish = asyncio.Event(), asyncio.Event()
        async def delayed():
            entered.set()
            await finish.wait()
            return {'completed':True,'stopped':True,'old_pid':12345}
        self.comfy.emergency_release = delayed
        self.assertTrue(callable(getattr(self.jobs, 'emergency_release', None)), 'Emergency stop is missing')
        task = asyncio.create_task(self.jobs.emergency_release())
        await entered.wait()
        task.cancel()
        await asyncio.sleep(0)
        try:
            self.assertTrue(self.jobs.lock.locked(), 'Client cancellation must not detach native stop from the shared gate')
            with self.assertRaises(UiError):
                await self.jobs.emergency_release()
        finally:
            finish.set()
            await asyncio.gather(task, return_exceptions=True)
        self.assertFalse(self.jobs.lock.locked())

    async def test_existing_start_lock_prevents_stop_without_waiting_or_native_access(self):
        with guard.StartLock(timeout=0):
            with self.assertRaises(UiError):
                await self.release()
        guard.open_process_for_stop.assert_not_called()


class EmergencyRouteTests(unittest.IsolatedAsyncioTestCase):
    async def test_route_requires_explicit_empty_action_and_preserves_confirmation(self):
        jobs = SimpleNamespace(emergency_release=AsyncMock(return_value={
            'completed':True,'stopped':True,'old_pid':12345,'message':'Stopped'}),
            comfy=SimpleNamespace(), close=lambda:None)
        app = create_app(None, None, SimpleNamespace(), jobs, SimpleNamespace(close=lambda:None),
                         settings=SimpleNamespace())
        client = TestClient(TestServer(app))
        await client.start_server()
        self.addAsyncCleanup(client.close)
        for headers, data, want in ((HEADERS|{'Origin':'https://foreign.example'}, {}, 403),
                                    ({'Host':'127.0.0.1:8765'}, {}, 403),
                                    (HEADERS, {'pid':999}, 400), (HEADERS, {}, 200)):
            response = await client.post('/api/resources/emergency-release', headers=headers, json=data)
            self.assertEqual(response.status,want)
        self.assertEqual((await response.json())['data']['old_pid'],12345)
        jobs.emergency_release.assert_awaited_once()


if __name__ == '__main__':
    unittest.main()
