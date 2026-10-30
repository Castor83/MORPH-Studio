"""Shared image/language gate regressions. Only isolated fixtures are used."""
import asyncio
import copy
import json
import sys
import unittest
import uuid
from pathlib import Path

from aiohttp.test_utils import TestClient, TestServer

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from morph_ui.catalog import Catalog
from morph_ui.files import FileStore
from morph_ui.jobs import ACTIVE, JobService
from morph_ui.paths import ProjectPaths, UiError
from morph_ui.providers.ollama import OllamaProvider
from morph_ui.server import create_app
from morph_ui.settings import SettingsStore
from support import Sandbox
from test_jobs import Compute
from test_ollama_provider import CHAT_MODEL, OTHER_MODEL, OllamaWire
from test_server import HEADERS


class GateCompute(Compute):
    def __init__(self, paths):
        super().__init__(paths)
        self.stats = {'system': {}, 'devices': [
            {'type': 'cuda', 'name': 'Fixture GPU', 'torch_vram_total': 0}]}
        self.availability = {'ready': True, 'ownership': 'owned'}
        self.read_error = None
        self.frees = 0

    async def status(self):
        return copy.deepcopy(self.availability)

    async def queue(self):
        if self.read_error:
            raise self.read_error
        return await super().queue()

    async def resource_stats(self):
        if self.read_error:
            raise self.read_error
        return copy.deepcopy(self.stats)

    async def free_resources(self):
        self.frees += 1
        return {'accepted': True}


class GateProvider:
    def __init__(self):
        self.calls = []
        self.entered, self.release = asyncio.Event(), asyncio.Event()
        self.delayed = False
        self.residency = {'state': 'clear', 'models': []}

    async def gpu_residency(self):
        return copy.deepcopy(self.residency)

    async def action(self, name):
        self.calls.append(name)
        if self.delayed:
            self.entered.set()
            await self.release.wait()

    async def load(self, model):
        await self.action('load')
        return {'instance_id': model, 'status': 'loaded'}

    async def unload(self, model):
        await self.action('unload')

    async def propose(self, *args):
        await self.action('propose')
        return {'assistant_text': 'Fixture', 'prompt': '', 'controls': {}}

    async def propose_tools(self, *args):
        await self.action('propose_tools')
        return {'assistant_text': 'Fixture', 'steps': []}


class LanguageGateFixture(unittest.IsolatedAsyncioTestCase):
    def make_provider(self):
        return GateProvider()

    async def asyncSetUp(self):
        self.paths = ProjectPaths(Sandbox(self).root)
        self.catalog = Catalog(self.paths)
        self.files = FileStore(self.paths)
        self.comfy = GateCompute(self.paths)
        self.jobs = JobService(self.paths, self.catalog, self.files, self.comfy)
        self.provider = self.make_provider()
        self.settings = SettingsStore(self.paths)
        self.client = TestClient(TestServer(create_app(
            self.paths, self.catalog, self.provider, self.jobs, self.files, self.settings)))
        await self.client.start_server()
        self.addAsyncCleanup(self.client.close)

    def routes(self):
        return [('/api/models/load', {'model_key': CHAT_MODEL}),
                ('/api/models/unload', {'instance_id': CHAT_MODEL}),
                ('/api/proposals', {'instance_id': CHAT_MODEL, 'workflow_id': 'sdxl',
                                    'instruction': 'Eine Tasse', 'controls': {}}),
                ('/api/tool-proposals', {'instance_id': CHAT_MODEL, 'workflow_id': 'sdxl',
                                         'instruction': 'Eine Tasse', 'controls': {}})]

    async def language(self, index=0):
        route, payload = self.routes()[index]
        response = await self.client.post(route, json=payload, headers=HEADERS)
        return response.status, await response.json()

    async def image(self, request_id=None):
        response = await self.client.post('/api/jobs', json={
            'request_id': request_id or str(uuid.uuid4()), 'workflow_id': 'sdxl',
            'controls': {}, 'images': {}}, headers=HEADERS)
        return response.status, await response.json()

    def add_job(self, state):
        key = str(uuid.uuid4())
        job = {'id': key, 'request_id': key, 'prompt_id': key, 'state': state}
        self.jobs.db.execute('INSERT INTO jobs VALUES (?,?,?,?)', (key, key, key, json.dumps(job)))


class LanguageGateTests(LanguageGateFixture):
    async def test_settings_cannot_change_during_language_action(self):
        self.provider.delayed = True
        before = self.settings.read_public()
        language = asyncio.create_task(self.language())
        await self.provider.entered.wait()
        try:
            response = await self.client.post('/api/settings', json={
                'endpoint': 'http://127.0.0.1:9999'}, headers=HEADERS)
            self.assertEqual(response.status, 409, await response.json())
            self.assertEqual(self.settings.read_public(), before)
        finally:
            self.provider.release.set()
            await language


    async def test_all_four_routes_reject_every_unresolved_job_before_provider_call(self):
        for state in ACTIVE | {'unexpected'}:
            for route_index in range(4):
                with self.subTest(state=state, route=route_index):
                    self.jobs.db.execute('DELETE FROM jobs')
                    self.add_job(state)
                    for unused in range(31):
                        self.add_job('completed')
                    self.jobs.db.commit()
                    status, answer = await self.language(route_index)
                    self.assertEqual(status, 409, answer)
                    self.assertEqual(answer['error']['code'], 'active_job')
        self.assertEqual(self.provider.calls, [])

    async def test_corrupt_persisted_job_rejects_all_four_routes(self):
        self.jobs.db.execute("INSERT INTO jobs VALUES ('bad','bad','bad','not-json')")
        self.jobs.db.commit()
        for route_index in range(4):
            status, answer = await self.language(route_index)
            self.assertEqual(status, 409, answer)
        self.assertEqual(self.provider.calls, [])

    async def test_busy_language_rejects_image_and_free_immediately_without_delayed_submit(self):
        self.provider.delayed = True
        language = asyncio.create_task(self.language())
        await self.provider.entered.wait()
        image = asyncio.create_task(self.image())
        free = asyncio.create_task(self.client.post('/api/resources/free', json={}, headers=HEADERS))
        try:
            done, pending = await asyncio.wait({image, free}, timeout=2)
            self.assertFalse(pending, 'Actions must reject before the language action is released')
            status, answer = await image
            self.assertEqual(status, 409, answer)
            self.assertEqual(answer['error']['code'], 'language_busy')
            response = await free
            self.assertEqual(response.status, 409)
        finally:
            self.provider.release.set()
            await asyncio.gather(language, image, free)
        self.assertEqual(self.comfy.submissions, [])
        self.assertEqual(self.comfy.started, 0)
        self.assertEqual(self.comfy.frees, 0)

    async def test_image_preparation_rejects_language_without_later_provider_execution(self):
        entered, release = asyncio.Event(), asyncio.Event()
        async def delay():
            entered.set()
            await release.wait()
        self.comfy.ensure_ready = delay
        image = asyncio.create_task(self.image())
        await entered.wait()
        language = asyncio.create_task(self.language())
        try:
            done, pending = await asyncio.wait({language}, timeout=2)
            self.assertFalse(pending, 'Language must reject before image preparation is released')
            status, answer = await language
            self.assertEqual(status, 409, answer)
        finally:
            release.set()
            await asyncio.gather(image, language)
        self.assertEqual(self.provider.calls, [])

    async def test_positive_ollama_gpu_residency_blocks_before_comfy_start(self):
        self.provider.residency = {'state': 'resident', 'models': [CHAT_MODEL]}
        status, answer = await self.image()
        receipt = answer.get('data', {})
        self.assertEqual(receipt.get('state'), 'error', answer)
        self.assertEqual(receipt.get('error_code'), 'language_gpu_busy', answer)
        self.assertIn(CHAT_MODEL, receipt['error'])
        self.assertEqual(self.comfy.started, 0)
        self.assertEqual(self.comfy.submissions, [])
        self.assertEqual(self.provider.calls, [])

    async def test_ollama_unknown_only_warns_and_does_not_block_optional_image_work(self):
        self.provider.residency = {'state': 'unknown', 'models': []}
        status, answer = await self.image()
        self.assertEqual(answer['data']['state'], 'queued', answer)
        self.assertTrue(answer['data'].get('warnings'), answer)
        self.assertEqual(len(self.comfy.submissions), 1)

    async def test_completed_duplicate_receipt_remains_idempotent_while_language_busy(self):
        request_id = str(uuid.uuid4())
        unused, original = await self.image(request_id)
        job = original['data']
        job['state'] = 'completed'
        self.jobs.store(job)
        self.provider.delayed = True
        language = asyncio.create_task(self.language())
        await self.provider.entered.wait()
        try:
            status, duplicate = await asyncio.wait_for(self.image(request_id), 2)
            self.assertEqual(status, 200)
            self.assertEqual(duplicate['data']['id'], job['id'])
        finally:
            self.provider.release.set()
            await language
        self.assertEqual(len(self.comfy.submissions), 1)

    async def test_comfy_gpu_reservation_blocks_load_and_proposals_but_allows_manual_language_unload(self):
        self.comfy.stats['devices'][0]['torch_vram_total'] = 1024
        for index in [0, 2, 3]:
            status, answer = await self.language(index)
            self.assertEqual(status, 409, answer)
            self.assertEqual(answer['error']['code'], 'image_gpu_busy')
        status, answer = await self.language(1)
        self.assertEqual(status, 200, answer)
        self.assertEqual(self.provider.calls, ['unload'])
        self.assertEqual(self.comfy.frees, 0)

    async def test_comfy_cpu_ram_reservation_does_not_count_as_gpu(self):
        self.comfy.stats['devices'] = [{'type': 'cpu', 'name': 'CPU', 'torch_vram_total': 48 * 1024**3}]
        status, answer = await self.language()
        self.assertEqual(status, 200, answer)
        self.assertEqual(self.provider.calls, ['load'])

    async def test_foreign_queue_blocks_optional_language(self):
        self.comfy.foreign = True
        status, answer = await self.language()
        self.assertEqual(status, 409, answer)
        self.assertEqual(answer['error']['code'], 'queue_busy')
        self.assertEqual(self.provider.calls, [])

    async def test_comfy_offline_and_free_port_allows_language_without_starting_service(self):
        self.comfy.read_error = UiError('comfy_connection', 'Fixture offline')
        self.comfy.availability = {'ready': False, 'ownership': 'free'}
        status, answer = await self.language()
        self.assertEqual(status, 200, answer)
        self.assertEqual(self.comfy.started, 0)

    async def test_reachable_unreadable_queue_or_gpu_stats_blocks_optional_language(self):
        for stats in [None, {}, {'system': {}, 'devices': []},
                      {'system': {}, 'devices': [{'type': 'cuda', 'torch_vram_total': None}]}]:
            self.comfy.stats = stats
            status, answer = await self.language()
            self.assertEqual(status, 409, answer)
        self.comfy.read_error = UiError('comfy_queue', 'Fixture malformed queue')
        status, answer = await self.language()
        self.assertEqual(status, 409, answer)
        self.assertEqual(self.provider.calls, [])


class OllamaGateTests(LanguageGateFixture):
    def make_provider(self):
        self.wire = OllamaWire()
        return OllamaProvider(None, self.catalog, self.wire)

    async def test_load_timeout_exposes_exact_recovery_target_without_assuming_loaded_state(self):
        original = self.wire.request
        async def timeout(method, path, payload=None):
            if path == '/api/generate':
                self.wire.calls.append((method, path, copy.deepcopy(payload)))
                raise UiError('model_connection', 'Fixture timeout')
            return await original(method, path, payload)
        self.wire.request = timeout
        self.wire.ps = {'models': []}
        status, answer = await self.language()
        self.assertEqual(answer['error']['code'], 'language_mutation_unknown', answer)
        self.assertEqual(self.settings.read_public()['instance_id'], '')
        response = await self.client.get('/api/status', headers=HEADERS)
        self.assertEqual((await response.json())['data']['language_state'], {
            'busy': False, 'uncertain_instances': [CHAT_MODEL]})
        response = await self.client.post('/api/models/unload', json={
            'instance_id': OTHER_MODEL}, headers=HEADERS)
        self.assertEqual(response.status, 409)
        self.assertEqual(sum(call[1] == '/api/generate' for call in self.wire.calls), 1)
        self.wire.request = original
        status, answer = await self.language(1)
        self.assertEqual(status, 200, answer)
        self.assertEqual(self.jobs.language_state()['uncertain_instances'], [])

    async def test_uncertain_mutation_binds_endpoint_and_blocks_settings_changes(self):
        self.provider.settings = self.settings
        original = self.wire.request
        async def timeout(method, path, payload=None):
            if path == '/api/chat':
                self.wire.calls.append((method, path, copy.deepcopy(payload)))
                raise UiError('model_connection', 'Fixture timeout')
            return await original(method, path, payload)
        self.wire.request = timeout
        status, answer = await self.language(2)
        self.assertEqual(answer['error']['code'], 'language_mutation_unknown', answer)
        response = await self.client.post('/api/settings', json={
            'endpoint': 'http://127.0.0.1:9999'}, headers=HEADERS)
        self.assertEqual(response.status, 409, await response.json())
        # Simulate an external edit across a service restart, outside the UI lock.
        self.settings.save({'endpoint': 'http://127.0.0.1:9999'})
        self.wire.request = original
        self.wire.calls.clear()
        status, answer = await self.language(1)
        self.assertEqual(status, 409, answer)
        self.assertEqual(answer['error']['code'], 'language_endpoint_changed')
        self.assertFalse(any(call[1] == '/api/generate' for call in self.wire.calls))

    async def test_read_only_provider_failure_does_not_create_uncertain_mutation(self):
        self.wire.failure = UiError('model_connection', 'Fixture offline')
        status, answer = await self.language()
        self.assertEqual(answer['error']['code'], 'model_connection', answer)
        self.assertEqual(self.jobs.language_state()['uncertain_instances'], [])
        status, answer = await self.image()
        self.assertEqual(answer['data']['state'], 'queued', answer)
        self.assertTrue(answer['data']['warnings'])

    async def test_confirmed_but_invalid_proposal_is_finished_without_automatic_unload(self):
        self.wire.chat['message']['content'] = '{invalid json'
        status, answer = await self.language(2)
        self.assertEqual(answer['error']['code'], 'proposal_invalid', answer)
        self.assertEqual(self.jobs.language_state()['uncertain_instances'], [])
        status, answer = await self.image()
        self.assertEqual(answer['data']['error_code'], 'language_gpu_busy')
        self.assertFalse(any(call[1] == '/api/generate' for call in self.wire.calls))

    async def test_reconcile_unload_requires_a_valid_fresh_ps_before_clearing_unknown(self):
        original = self.wire.request
        async def timeout(method, path, payload=None):
            if path == '/api/chat':
                self.wire.calls.append((method, path, copy.deepcopy(payload)))
                raise UiError('model_connection', 'Fixture timeout')
            return await original(method, path, payload)
        self.wire.request = timeout
        status, answer = await self.language(2)
        self.assertEqual(answer['error']['code'], 'language_mutation_unknown', answer)
        self.wire.ps = {'models': []}
        async def invalid_after_unload(method, path, payload=None):
            if path == '/api/generate':
                self.wire.calls.append((method, path, copy.deepcopy(payload)))
                self.wire.ps = {'models': [{}]}
                return {'model': CHAT_MODEL, 'done': True}
            return await original(method, path, payload)
        self.wire.request = invalid_after_unload
        status, answer = await self.language(1)
        self.assertEqual(status, 409, answer)
        self.assertEqual(answer['error']['code'], 'language_mutation_unknown')
        self.assertEqual(self.jobs.language_state()['uncertain_instances'], [CHAT_MODEL])
        status, answer = await self.image()
        self.assertEqual(status, 409, answer)
        self.assertEqual(self.comfy.submissions, [])
        # A genuinely empty list after a newly confirmed explicit unload is valid.
        self.wire.ps = {'models': []}
        self.wire.request = original
        status, answer = await self.language(1)
        self.assertEqual(status, 200, answer)
        self.assertEqual(self.jobs.language_state()['uncertain_instances'], [])

    async def test_started_timed_out_chat_stays_blocked_across_service_recreation_until_same_unload(self):
        original_request = self.wire.request
        async def timed_out(method, path, payload=None):
            if path == '/api/chat':
                self.wire.calls.append((method, path, copy.deepcopy(payload)))
                raise UiError('model_connection', 'Fixture timed out', status=503)
            return await original_request(method, path, payload)
        self.wire.request = timed_out
        status, answer = await self.language(2)
        self.assertEqual(answer['error']['code'], 'language_mutation_unknown', answer)
        restored = JobService(self.paths, self.catalog, self.files, self.comfy)
        restored.provider = self.provider
        self.addCleanup(restored.close)
        for ps in [{'models': []}, None]:
            self.wire.ps = ps
            with self.assertRaises(UiError) as blocked:
                await restored.create(str(uuid.uuid4()), 'sdxl', {}, {})
            self.assertEqual(blocked.exception.code, 'language_mutation_unknown')
        self.assertEqual(self.comfy.started, 0)
        self.assertEqual(sum(call[1] == '/api/chat' for call in self.wire.calls), 1)
        status, answer = await self.language(0)
        self.assertEqual(status, 409, answer)
        self.wire.ps = {'models': []}
        status, answer = await self.language(1)
        self.assertEqual(status, 200, answer)
        status, answer = await self.image()
        self.assertEqual(answer['data']['state'], 'queued', answer)
        mutations = [call for call in self.wire.calls if call[1] == '/api/generate']
        self.assertEqual(mutations, [('POST', '/api/generate', {
            'model': CHAT_MODEL, 'stream': False, 'keep_alive': 0})])


class ResidencyTests(unittest.IsolatedAsyncioTestCase):
    async def test_model_listing_rejects_ps_entries_that_cannot_prove_loaded_names(self):
        for item in [{}, None, [], 'model', {'name': ''}, {'name': ' spaced '},
                     {'name': 7}, {'name': CHAT_MODEL, 'model': OTHER_MODEL},
                     {'name': CHAT_MODEL, 'model': None}]:
            with self.subTest(item=item):
                wire = OllamaWire()
                wire.ps = {'models': [item]}
                provider = OllamaProvider(None, None, wire)
                with self.assertRaises(UiError):
                    await provider.list_models()
                self.assertFalse(any(call[0] == 'POST' for call in wire.calls))

    async def test_native_ps_residency_uses_only_confirmed_positive_size_vram(self):
        wire = OllamaWire()
        provider = OllamaProvider(None, None, wire)
        for ps, state, names in [
                ({'models': [{'name': CHAT_MODEL, 'size_vram': 1}]}, 'resident', [CHAT_MODEL]),
                ({'models': [{'name': CHAT_MODEL, 'size_vram': 0}]}, 'clear', []),
                ({'models': []}, 'clear', []),
                (None, 'unknown', []),
                ({'models': [{'name': CHAT_MODEL, 'size_vram': True}]}, 'unknown', []),
                ({'models': [{'name': CHAT_MODEL}]}, 'unknown', [])]:
            with self.subTest(ps=ps):
                wire.ps = ps
                method = getattr(provider, 'gpu_residency', None)
                self.assertTrue(callable(method), 'Fresh read-only residency check is missing')
                result = await method()
                self.assertEqual((result['state'], result['models']), (state, names))
        wire.failure = UiError('model_connection', 'Fixture offline')
        self.assertEqual((await provider.gpu_residency())['state'], 'unknown')
        self.assertFalse(any(call[0] == 'POST' for call in wire.calls))
