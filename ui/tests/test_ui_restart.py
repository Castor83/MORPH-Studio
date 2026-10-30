import json
import sys
import unittest
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from morph_ui.paths import UiError
import test_server as server_cases
from test_server import HEADERS


class UiRestartTests(unittest.IsolatedAsyncioTestCase):
    asyncSetUp = server_cases.ServerTests.asyncSetUp

    def record(self, state):
        identifier = str(uuid.uuid4())
        data = {'id':identifier, 'request_id':identifier, 'state':state}
        self.jobs.db.execute('INSERT INTO jobs VALUES (?,?,?,?)', (identifier,identifier,identifier,json.dumps(data)))
        self.jobs.db.commit()

    async def test_restart_refuses_unknown_job_outside_recent_history(self):
        self.record('unknown')
        for _ in range(30):
            self.record('error')
        response = await self.client.post('/api/service/prepare-restart', json={}, headers=HEADERS)
        self.assertEqual(response.status, 409)
        self.assertEqual((await response.json())['error']['code'], 'active_job')

    async def test_idle_restart_fences_new_submissions_without_starting_comfy(self):
        response = await self.client.post('/api/service/prepare-restart', json={}, headers=HEADERS)
        self.assertEqual(response.status, 200)
        self.assertTrue((await response.json())['data']['ready'])
        with self.assertRaises(UiError) as caught:
            await self.jobs.create(str(uuid.uuid4()), 'sdxl', {}, {})
        self.assertEqual(caught.exception.code, 'ui_restarting')
        self.assertEqual(self.compute.started, 0)
        self.assertEqual(self.compute.submissions, [])


if __name__ == '__main__':
    unittest.main()
