"""ReActor operator tests: temporary local files and transport doubles only."""
import argparse
import asyncio
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image

HERE = Path(__file__).resolve().parent
HELPER = HERE / 'phase9_reactor_acceptance.py'
SOURCE_ID, TARGET_ID, OUTPUT_ID = ('a' * 32, 'b' * 32, 'c' * 32)
JOB_ID = '20261020-0000-4000-8000-000000000003'


def png(color, size=(2, 2)):
    output = io.BytesIO()
    Image.new('RGB', size, color).save(output, format='PNG')
    return output.getvalue()


class ReactorCase(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        asyncio.get_running_loop().slow_callback_duration = 5

    def setUp(self):
        self.assertTrue(HELPER.is_file(), 'The separate reactor helper is not implemented yet.')
        spec = importlib.util.spec_from_file_location('reactor_under_test', HELPER)
        self.h = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.h)
        self.folder = tempfile.TemporaryDirectory(prefix='phase9-reactor-offline-', dir=HERE)
        self.addCleanup(self.folder.cleanup)
        self.output = Path(self.folder.name)
        self.source, self.target, self.result = png('red'), png('blue'), png('green')
        inputs = {}
        for role, data in [('source', self.source), ('target', self.target)]:
            path = self.output / (role + '.png')
            path.write_bytes(data)
            inputs[role] = {'path': path, 'sha256': hashlib.sha256(data).hexdigest(), 'dimensions': [2, 2]}
        self.inputs_patch = patch.object(self.h, 'INPUTS', inputs)
        self.inputs_patch.start()
        self.addCleanup(self.inputs_patch.stop)
        self.output_patch = patch.object(self.h.base, 'OUTPUT', self.output)
        self.output_patch.start()
        self.addCleanup(self.output_patch.stop)

    def journal(self):
        return self.h.base.Journal('reactor')

    def client(self, journal, *, lose_response=False, corrupt_upload=False, wrong_job=False, wrong_size=False):
        case = self

        class Client:
            def __init__(self):
                self.posts, self.gets, self.uploads, self.media_reads = [], [], [], []

            async def request(self, method, path, **kwargs):
                case.assertEqual(method, 'GET')
                self.gets.append(path)
                if path == '/api/workflows':
                    return [{'id': 'reactor', 'roles': [{'id': 'target'}, {'id': 'source'}],
                             'controls': {'target_face': {'kind': 'faces', 'default': '0'},
                                          'source_face': {'kind': 'faces', 'default': '0'}},
                             'issues': [], 'dependencies': [{'name': 'inswapper_128.onnx', 'role': 'Gesichtstausch'}]}]
                if path.startswith('/api/requests/'):
                    return self.job
                if path == '/api/jobs/' + JOB_ID:
                    return dict(self.job, state='completed', outputs=[{
                        'id': OUTPUT_ID, 'kind': 'image', 'category': 'output', 'url': '/media/' + OUTPUT_ID}])
                if path == '/api/resources':
                    return {'available': False}
                raise AssertionError(path)

            async def upload(self, path):
                self.uploads.append(path)
                role = path.stem
                return {'id': SOURCE_ID if role == 'source' else TARGET_ID,
                        'kind': 'image', 'category': 'input'}

            async def image(self, media_id):
                self.media_reads.append(media_id)
                if media_id == SOURCE_ID:
                    return b'corrupt upload' if corrupt_upload else case.source
                if media_id == TARGET_ID:
                    return case.target
                if media_id == OUTPUT_ID:
                    return png('green', (2, 3)) if wrong_size else case.result
                raise AssertionError(media_id)

            async def post(self, path, payload=None, **kwargs):
                case.assertEqual(path, '/api/jobs')
                durable = json.loads(journal.state_path.read_text(encoding='utf-8'))['actions']['reactor']
                case.assertEqual(durable['request_id'], payload['request_id'])
                case.assertEqual(durable['payload'], payload)
                self.posts.append((path, payload))
                self.job = dict(payload, id=JOB_ID, prompt_id=payload['request_id'], state='queued', outputs=[])
                if wrong_job:
                    self.job['images'] = {'source': TARGET_ID, 'target': SOURCE_ID}
                if lose_response:
                    raise TimeoutError('deliberately missing response; existing receipt remains')
                return self.job

        client = Client()
        client.journal = journal
        return client

    async def test_exact_one_submit_and_complete_output_are_bound_to_own_ids(self):
        journal = self.journal()
        client = self.client(journal)
        await self.h.reactor(client, journal, 1)
        self.assertEqual(len(client.posts), 1)
        payload = client.posts[0][1]
        self.assertEqual(set(payload), {'request_id', 'workflow_id', 'controls', 'images'})
        self.assertEqual(payload['workflow_id'], 'reactor')
        self.assertEqual(payload['images'], {'source': SOURCE_ID, 'target': TARGET_ID})
        self.assertEqual(payload['controls'], {'source_face': '0', 'target_face': '0'})
        record = journal.state['actions']['reactor']
        self.assertEqual(record['stage'], 'completed')
        self.assertEqual(record['output_sha256'], hashlib.sha256(self.result).hexdigest())
        self.assertEqual(record['output_dimensions'], [2, 2])
        self.assertEqual(Path(record['output_copy']).read_bytes(), self.result)
        self.assertEqual(client.media_reads, [SOURCE_ID, TARGET_ID, OUTPUT_ID])

    async def test_lost_submit_response_uses_get_receipt_and_never_resubmits(self):
        journal = self.journal()
        client = self.client(journal, lose_response=True)
        await self.h.reactor(client, journal, 1)
        self.assertEqual(len(client.posts), 1)
        self.assertIn('/api/requests/' + client.posts[0][1]['request_id'], client.gets)
        self.assertEqual(journal.state['actions']['reactor']['stage'], 'completed')

    async def test_wrong_upload_bytes_stop_before_submit(self):
        journal = self.journal()
        client = self.client(journal, corrupt_upload=True)
        with self.assertRaises(self.h.base.StopAcceptance):
            await self.h.reactor(client, journal, 1)
        self.assertEqual(client.posts, [])

    async def test_swapped_receipt_roles_stop_before_polling_or_output(self):
        journal = self.journal()
        client = self.client(journal, wrong_job=True)
        with self.assertRaises(self.h.base.StopAcceptance):
            await self.h.reactor(client, journal, 1)
        self.assertEqual(len(client.posts), 1)
        self.assertNotIn('/api/jobs/' + JOB_ID, client.gets)
        self.assertNotIn(OUTPUT_ID, client.media_reads)

    async def test_second_reserved_action_is_blocked_before_any_transport(self):
        journal = self.journal()
        journal.reserve('reactor')
        client = self.client(journal)
        with self.assertRaises(self.h.base.StopAcceptance):
            await self.h.reactor(client, journal, 1)
        self.assertEqual(client.posts + client.gets + client.uploads, [])

    async def test_existing_shared_lock_remains_and_prevents_start(self):
        lock = self.output / 'acceptance-action.lock'
        marker = '{"pid":12345,"action":"edit1"}'
        lock.write_text(marker, encoding='utf-8')
        args = argparse.Namespace(action='reactor', deadline=30, poll_interval=1)
        with self.assertRaises(self.h.base.StopAcceptance):
            await self.h.run(args)
        self.assertEqual(lock.read_text(encoding='utf-8'), marker)
        self.assertFalse((self.output / 'acceptance-state.json').exists())

    async def test_wrong_output_geometry_is_not_completed(self):
        journal = self.journal()
        client = self.client(journal, wrong_size=True)
        with self.assertRaises(self.h.base.StopAcceptance):
            await self.h.reactor(client, journal, 1)
        self.assertNotEqual(journal.state['actions']['reactor']['stage'], 'completed')

    def test_action_is_explicitly_required(self):
        with self.assertRaises(SystemExit) as result:
            self.h.main([])
        self.assertEqual(result.exception.code, 2)


if __name__ == '__main__':
    unittest.main(verbosity=2)
