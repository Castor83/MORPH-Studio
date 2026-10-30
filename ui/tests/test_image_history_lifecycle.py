import io
import sys
import unittest
import uuid
from pathlib import Path

from aiohttp import FormData
from aiohttp.test_utils import TestClient, TestServer
from PIL import Image

sys.path[:0] = [str(Path(__file__).resolve().parents[1]),str(Path(__file__).resolve().parent)]
from morph_ui.catalog import Catalog
from morph_ui.files import FileStore
from morph_ui.jobs import JobService
from morph_ui.paths import ProjectPaths
from morph_ui.server import create_app
from morph_ui.versions import VersionStore
from support import Sandbox
from test_jobs import Compute
from test_server import Provider, HEADERS


def picture(color):
    stream = io.BytesIO()
    Image.new('RGB',(8,8),color).save(stream,format='PNG')
    return stream.getvalue()


class ImageHistoryLifecycleTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.paths = ProjectPaths(Sandbox(self).root)
        self.files = FileStore(self.paths)
        self.versions = VersionStore(self.paths,self.files)
        self.compute = Compute(self.paths)
        self.jobs = JobService(self.paths,Catalog(self.paths),self.files,self.compute,versions=self.versions)
        app = create_app(self.paths,Catalog(self.paths),Provider(),self.jobs,self.files,versions=self.versions)
        self.client = TestClient(TestServer(app))
        await self.client.start_server()
        self.addAsyncCleanup(self.client.close)

    async def post(self,path,body):
        response = await self.client.post(path,json=body,headers=HEADERS)
        data = await response.json()
        self.assertEqual(response.status,200,data)
        self.assertTrue(data['ok'])
        return data['data']

    async def get(self,path):
        response = await self.client.get(path,headers=HEADERS)
        data = await response.json()
        self.assertEqual(response.status,200,data)
        return data['data']

    async def project(self):
        body = FormData()
        body.add_field('file',picture('red'),filename='original.png',content_type='image/png')
        response = await self.client.post('/api/uploads',data=body,headers=HEADERS)
        image = (await response.json())['data']
        return await self.post('/api/image-projects',{'request_id':str(uuid.uuid4()),'original_media_id':image['id'],'name':'Verzweigte Tasse'})

    async def edit(self,parent,color):
        context = await self.post('/api/image-versions/'+parent+'/input',{})
        self.compute.current = {'state':'queued','outputs':[]}
        job = await self.post('/api/jobs',{'request_id':str(uuid.uuid4()),'workflow_id':'krea2',
            'controls':{'prompt':'Nur die Testfarbe ändern: '+color},'images':{'image':context['image']['id']},
            'project_id':context['project_id'],'parent_version_id':context['parent_version_id']})
        self.assertEqual(job['state'],'queued',job.get('error'))
        name = color+'-'+uuid.uuid4().hex+'.png'
        (self.paths.output/name).write_bytes(picture(color))
        self.compute.current = {'state':'completed','outputs':[{'filename':name,'type':'output'}]}
        return await self.get('/api/jobs/'+job['id'])

    async def test_original_two_edits_and_branch_are_independent_persisted_versions(self):
        project = await self.project()
        original = project['original_version_id']
        first = await self.edit(original,'blue')
        first_id = first['versions'][0]['id']
        second = await self.edit(first_id,'green')
        second_id = second['versions'][0]['id']
        branch = await self.edit(first_id,'yellow')
        branch_id = branch['versions'][0]['id']
        saved = await self.get('/api/image-projects/'+project['id'])
        self.assertEqual(len(saved['versions']),4)
        parents = {version['id']:version['parent_version_id'] for version in saved['versions']}
        self.assertEqual(parents,{original:None,first_id:original,second_id:first_id,branch_id:first_id})
        self.assertEqual(len({version['media']['id'] for version in saved['versions']}),4)
        self.assertEqual(len({version['sha256'] for version in saved['versions']}),4)
        self.assertEqual(len(self.compute.submissions),3)
        await self.client.close()
        files = FileStore(self.paths)
        self.addCleanup(files.close)
        versions = VersionStore(self.paths,files)
        self.addCleanup(versions.close)
        reopened = versions.get_project(project['id'])
        self.assertEqual({version['id'] for version in reopened['versions']},set(parents))
        self.assertEqual(files.resolve(reopened['versions'][0]['media']['id']).read_bytes(),picture('red'))

    async def test_failed_metadata_commit_can_recover_through_job_api_without_resubmission(self):
        project = await self.project()
        insert = self.versions._insert
        def unavailable(*args):
            raise OSError('Simulierter Speicherausfall')
        self.versions._insert = unavailable
        failed = await self.edit(project['original_version_id'],'blue')
        self.assertEqual(failed['state'],'completed')
        self.assertIn('versioning_error',failed)
        self.assertEqual(len(self.versions.get_project(project['id'])['versions']),1)
        self.versions._insert = insert
        recovered = await self.get('/api/jobs/'+failed['id'])
        self.assertEqual(len(recovered['versions']),1)
        self.assertNotIn('versioning_error',recovered)
        self.assertEqual(len(self.compute.submissions),1)
