import sys
import unittest
from pathlib import Path
from aiohttp.test_utils import TestClient, TestServer

sys.path[:0] = [str(Path(__file__).resolve().parents[1]), str(Path(__file__).resolve().parent)]
from morph_ui.catalog import Catalog
from morph_ui.files import FileStore
from morph_ui.jobs import JobService
from morph_ui.paths import ProjectPaths
from morph_ui.server import create_app
from support import Sandbox
from test_jobs import Compute
from test_server import Provider, HEADERS


class VersionRoutesTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.paths = ProjectPaths(Sandbox(self).root)
        self.files = FileStore(self.paths)
        self.compute = Compute(self.paths)
        self.jobs = JobService(self.paths,Catalog(self.paths),self.files,self.compute)
        self.project = {'id':'project','name':'Tasse','original_version_id':'original','versions':[]}
        self.created = []
        case = self
        class Versions:
            def list_projects(self): return case.created
            def create_project(self,request_id,original_media_id,name=''):
                case.created.append(dict(case.project,request_id=request_id,source=original_media_id,name=name))
                return case.created[-1]
            def get_project(self,identifier): return case.project
            def get_version(self,identifier): return {'id':identifier,'project_id':'project'}
            def prepare_input(self,identifier):
                return {'project_id':'project','parent_version_id':identifier,'image':{'id':'input','url':'/media/input','kind':'image','name':'kopie.png'}}
            def close(self): pass
        self.versions = Versions()
        app = create_app(self.paths,Catalog(self.paths),Provider(),self.jobs,self.files,versions=self.versions)
        self.client = TestClient(TestServer(app))
        await self.client.start_server()
        self.addAsyncCleanup(self.client.close)

    async def test_project_creation_requires_local_action_and_preserves_requested_identity(self):
        data = {'request_id':'request','original_media_id':'media','name':'Meine Tasse'}
        rejected = await self.client.post('/api/image-projects',json=data,headers={'Host':'127.0.0.1:8765'})
        self.assertEqual(rejected.status,403)
        self.assertEqual(self.created,[])
        response = await self.client.post('/api/image-projects',json=data,headers=HEADERS)
        self.assertEqual(response.status,200)
        project = (await response.json())['data']
        self.assertEqual((project['request_id'],project['source'],project['name']),('request','media','Meine Tasse'))

    async def test_explicit_version_selection_prepares_input_without_starting_a_job(self):
        response = await self.client.post('/api/image-versions/parent/input',json={},headers=HEADERS)
        self.assertEqual(response.status,200)
        context = (await response.json())['data']
        self.assertEqual(context['parent_version_id'],'parent')
        self.assertEqual(context['image']['id'],'input')
        self.assertEqual(self.compute.submissions,[])
