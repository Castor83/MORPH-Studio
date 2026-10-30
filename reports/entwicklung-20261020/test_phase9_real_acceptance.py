"""Offline safety regression for the acceptance operator; no sockets or services."""
import asyncio
import copy
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import uuid

from PIL import Image


HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location('phase9_acceptance_under_test', HERE / 'phase9_real_acceptance.py')
h = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(h)
PROJECT_ID, PARENT_ID, IMAGE_ID, MASK_ID, VERSION_ID = (letter * 32 for letter in 'abcde')
REQUEST_ID = '20261020-0000-4000-8000-000000000001'
JOB_ID = '20261020-0000-4000-8000-000000000002'


def png():
    output = io.BytesIO()
    Image.new('RGB', (2, 2), 'red').save(output, format='PNG')
    return output.getvalue()


def payload():
    return {'request_id': REQUEST_ID, 'workflow_id': 'krea2', 'project_id': PROJECT_ID,
            'parent_version_id': PARENT_ID, 'images': {'image': IMAGE_ID},
            'controls': {'prompt': 'Nur das Hemd blau'},
            'edit_region': {'mask_media_id': MASK_ID, 'source_media_id': IMAGE_ID,
                            'parent_version_id': PARENT_ID}}


def job():
    return dict(payload(), id=JOB_ID, prompt_id=REQUEST_ID, state='completed', outputs=[],
                progress={'connection': 'connected', 'percent': 100}, versions=[{
                    'id': VERSION_ID, 'project_id': PROJECT_ID, 'parent_version_id': PARENT_ID,
                    'status': 'completed', 'metadata': {'workflow_id': 'krea2'}}])


class JournalCase(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        asyncio.get_running_loop().slow_callback_duration = 5

    def setUp(self):
        self.folder = tempfile.TemporaryDirectory(prefix='phase9-offline-', dir=HERE)
        self.output = Path(self.folder.name)
        self.replace_output = patch.object(h, 'OUTPUT', self.output)
        self.replace_output.start()
        self.addCleanup(self.replace_output.stop)
        self.addCleanup(self.folder.cleanup)

    def journal(self, action):
        journal = h.Journal(action)
        journal.state.update(project_id=PROJECT_ID, original_version_id=PARENT_ID,
                             mask_media_id=MASK_ID, mask_dimensions=[2, 2],
                             mask_sha256=hashlib.sha256(png()).hexdigest())
        return journal

    async def test_uncertain_proposal_never_sends_cleanup_unload(self):
        journal = self.journal('language')
        posts = []

        class Client:
            async def request(self, method, path, **kwargs):
                if path == '/api/settings':
                    return {'provider': 'ollama', 'model_key': h.MODEL, 'instance_id': ''}
                if path == '/api/workflows':
                    return [{'id': 'krea2', 'controls': {}, 'issues': [], 'dependencies': []}]
                if path == '/api/models':
                    loaded = bool(posts)
                    return [{'key': h.MODEL, 'name': h.MODEL,
                             'loaded_instances': [{'id': h.MODEL}] if loaded else []}]
                raise AssertionError(path)

            async def post(self, path, data=None, **kwargs):
                posts.append(path)
                if path == '/api/models/load':
                    return {'status': 'loaded', 'instance_id': h.MODEL}
                if path == '/api/tool-proposals':
                    raise TimeoutError('remote response not confirmed')
                if path == '/api/models/unload':
                    return {'unloaded': True}
                raise AssertionError(path)

        client = Client()
        client.journal = journal
        with self.assertRaises((TimeoutError, h.StopAcceptance)):
            await h.language(client, journal)
        self.assertEqual(posts, ['/api/models/load', '/api/tool-proposals'])
        self.assertTrue(journal.state['actions']['language']['loaded_by_this_action'])

    async def test_cancel_rejects_wrong_parent_before_any_cancel(self):
        journal = self.journal('cancel')
        journal.state['actions']['edit1'] = {'terminal_state': 'completed', 'version_ids': [PARENT_ID]}
        posts = []
        parent_bytes = png()

        class Client:
            async def request(self, method, path, **kwargs):
                if path == '/api/image-versions/' + PARENT_ID:
                    return {'id': PARENT_ID, 'project_id': PROJECT_ID,
                            'sha256': hashlib.sha256(parent_bytes).hexdigest()}
                if path == '/api/workflows':
                    return [{'id': 'krea2', 'controls': {}, 'issues': [], 'dependencies': []}]
                if path.startswith('/api/jobs/'):
                    return self.received
                if path == '/api/resources':
                    return {'available': False}
                raise AssertionError(path)

            async def post(self, path, data=None, **kwargs):
                posts.append(path)
                if path.endswith('/input'):
                    return {'project_id': PROJECT_ID, 'parent_version_id': PARENT_ID, 'image': {'id': IMAGE_ID}}
                if path == '/api/jobs':
                    self.received = dict(data, id=JOB_ID, state='completed',
                                         parent_version_id='f' * 32, versions=[], outputs=[])
                    return self.received
                if path.endswith('/cancel'):
                    return self.received
                raise AssertionError(path)

            async def image(self, image_id):
                return parent_bytes

        client = Client()
        client.journal = journal
        with self.assertRaises(h.StopAcceptance):
            await h.submit_edit(client, journal, 'cancel', 1)
        self.assertFalse(any(path.endswith('/cancel') for path in posts), posts)

    async def test_terminal_version_from_other_parent_is_not_accepted(self):
        journal = self.journal('edit1')
        record = {'job_id': JOB_ID, 'request_id': REQUEST_ID, 'payload': payload()}
        received = job()
        received['versions'][0]['parent_version_id'] = 'f' * 32

        class Client:
            async def request(self, method, path, **kwargs):
                return received if path.startswith('/api/jobs/') else {'available': False}

        with self.assertRaises(h.StopAcceptance):
            await h.poll(Client(), journal, record, 'edit1', 1)

    async def test_receipt_rejects_mask_context_mismatch(self):
        journal = self.journal('observe')
        record = {'job_id': JOB_ID, 'request_id': REQUEST_ID, 'payload': payload()}
        received = job()
        received['edit_region']['source_media_id'] = 'f' * 32

        class Client:
            async def request(self, method, path, **kwargs):
                return received

        client = Client()
        client.journal = journal
        with self.assertRaises(h.StopAcceptance):
            await h.receipt(client, record)

    async def test_post_has_durable_attempt_uuid_before_transport_and_error_is_redacted(self):
        journal = self.journal('resources')
        captured = []

        class Content:
            async def iter_chunked(self, limit):
                yield json.dumps({'ok': False, 'error': {
                    'code': 'fixture_failure', 'message': 'secret-value C:\\private\\fixture.png',
                    'details': {'api_key': 'secret-value'}}}).encode()

        class Response:
            status, content = 500, Content()
            async def __aenter__(self):
                return self
            async def __aexit__(self, *args):
                pass

        class Session:
            def request(self, method, url, **kwargs):
                durable = json.loads(journal.path.read_text(encoding='utf-8'))
                captured.append(durable['events'][-1])
                return Response()

        class Aiohttp:
            class ClientTimeout:
                def __init__(self, **kwargs):
                    pass

        client = h.Client(Session(), journal, Aiohttp)
        with self.assertRaises(h.StopAcceptance):
            await client.request('POST', '/api/resources/free', payload={})
        self.assertIn('attempt_id', captured[0])
        self.assertEqual(str(uuid.UUID(captured[0]['attempt_id'])), captured[0]['attempt_id'])
        proof = journal.path.read_text(encoding='utf-8')
        self.assertNotIn('secret-value', proof)
        self.assertNotIn('C:\\\\private', proof)

    async def test_explicit_unload_reconciles_only_own_saved_unknown_load_even_when_absent(self):
        journal = self.journal('language-unload')
        journal.state['actions']['language'] = {
            'load_attempt_utc': '2026-10-20T17:00:00Z', 'load_instance_id': h.MODEL, 'loaded_before': []}
        posts = []

        class Client:
            async def request(self, method, path, **kwargs):
                if path == '/api/status':
                    return {'language_state': {'busy': False, 'uncertain_instances': [h.MODEL] if not posts else []}}
                if path == '/api/settings':
                    return {'provider': 'ollama', 'model_key': h.MODEL, 'instance_id': ''}
                if path == '/api/models':
                    return [{'key': h.MODEL, 'name': h.MODEL, 'loaded_instances': []}]
                raise AssertionError(path)

            async def post(self, path, data=None, **kwargs):
                posts.append((path, data))
                return {'unloaded': True}

        try:
            await h.language_unload(Client(), journal)
        except h.StopAcceptance as error:
            self.fail('Exact own uncertain target must support explicit reconciliation: ' + str(error))
        self.assertEqual(posts, [('/api/models/unload', {'instance_id': h.MODEL})])
        self.assertTrue(journal.state['actions']['language-unload']['unload_confirmed'])

    async def test_explicit_unload_without_backend_unknown_will_not_claim_timedout_load_ownership(self):
        journal = self.journal('language-unload')
        journal.state['actions']['language'] = {
            'load_attempt_utc': '2026-10-20T17:00:00Z', 'load_instance_id': h.MODEL, 'loaded_before': []}

        class Client:
            async def request(self, method, path, **kwargs):
                if path == '/api/status':
                    return {'language_state': {'busy': False, 'uncertain_instances': []}}
                if path == '/api/settings':
                    return {'provider': 'ollama', 'model_key': h.MODEL, 'instance_id': ''}
                if path == '/api/models':
                    return [{'key': h.MODEL, 'name': h.MODEL, 'loaded_instances': [{'id': h.MODEL}]}]
                raise AssertionError(path)

            async def post(self, *args, **kwargs):
                self.fail('No own confirmed load or matching backend unknown: no unload allowed')

        with self.assertRaises(h.StopAcceptance):
            await h.language_unload(Client(), journal)

    async def test_completed_exact_job_context_and_one_version_are_accepted(self):
        journal = self.journal('edit1')
        record = {'job_id': JOB_ID, 'request_id': REQUEST_ID, 'payload': payload()}
        received = job()

        class Client:
            async def request(self, method, path, **kwargs):
                return received if path.startswith('/api/jobs/') else {'available': False}

        result = await h.poll(Client(), journal, record, 'edit1', 1)
        self.assertEqual(result['id'], JOB_ID)
        self.assertEqual(record['version_ids'], [VERSION_ID])

    async def test_request_receipt_rejects_changed_mask_bytes(self):
        journal = self.journal('observe')
        record = {'job_id': JOB_ID, 'request_id': REQUEST_ID, 'payload': payload(), 'mask_sha256': 'a' * 64}
        received = job()
        received['edit_region']['mask_sha256'] = 'f' * 64

        class Client:
            async def request(self, method, path, **kwargs):
                return received

        client = Client()
        client.journal = journal
        with self.assertRaises(h.StopAcceptance):
            await h.receipt(client, record)

    async def test_api_receives_all_chunks_before_json_decoding(self):
        journal = self.journal('resources')
        fragments = [b'{"ok":true,', b'"data":{"available":false}}']

        class Content:
            async def read(self, limit):
                return fragments[0]  # StreamReader.read(n) is allowed to return before EOF.
            async def iter_chunked(self, limit):
                for fragment in fragments:
                    yield fragment

        class Response:
            status, content = 200, Content()
            async def __aenter__(self):
                return self
            async def __aexit__(self, *args):
                pass

        class Session:
            def request(self, *args, **kwargs):
                return Response()

        class Aiohttp:
            class ClientTimeout:
                def __init__(self, **kwargs):
                    pass

        client = h.Client(Session(), journal, Aiohttp)
        try:
            result = await client.request('GET', '/api/resources')
        except h.StopAcceptance as error:
            self.fail('A complete chunked JSON document must be accepted: ' + str(error))
        self.assertEqual(result, {'available': False})

    async def test_image_receives_all_chunks_before_hash_or_decode(self):
        journal = self.journal('resources')
        complete = png()
        fragments = [complete[:20], complete[20:45], complete[45:]]

        class Content:
            async def read(self, limit):
                return fragments[0]
            async def iter_chunked(self, limit):
                for fragment in fragments:
                    yield fragment

        class Response:
            status, content = 200, Content()
            async def __aenter__(self):
                return self
            async def __aexit__(self, *args):
                pass

        class Session:
            def get(self, *args, **kwargs):
                return Response()

        class Aiohttp:
            class ClientTimeout:
                def __init__(self, **kwargs):
                    pass

        client = h.Client(Session(), journal, Aiohttp)
        self.assertEqual(await client.image(IMAGE_ID), complete)


if __name__ == '__main__':
    unittest.main(verbosity=2)
