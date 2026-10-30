import sys
import unittest
import uuid
from pathlib import Path

sys.path[:0] = [str(Path(__file__).resolve().parents[1]), str(Path(__file__).resolve().parent)]
from morph_ui.catalog import Catalog
from morph_ui.files import FileStore
from morph_ui.jobs import JobService
from morph_ui.paths import ProjectPaths, UiError
from support import Sandbox, png
from test_jobs import Compute


class VersionsBoundary:
    def __init__(self):
        self.context = {}
        self.error = None
    def validate_job_context(self, project_id, parent_version_id, workflow_id, images):
        if project_id != 'project' or parent_version_id != 'parent':
            raise UiError('version_context','Die gewählte Elternversion passt nicht zum Projekt.')
        return {'project_id':project_id,'parent_version_id':parent_version_id}
    def record_job_outputs(self, job):
        if self.error:
            raise self.error
        return [{'id':'new-version','project_id':job['project_id'],'parent_version_id':job['parent_version_id']}]


class VersionedJobTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.paths = ProjectPaths(Sandbox(self).root)
        self.files = FileStore(self.paths)
        self.addCleanup(self.files.close)
        self.compute = Compute(self.paths)
        self.versions = VersionsBoundary()
        self.jobs = JobService(self.paths,Catalog(self.paths),self.files,self.compute,versions=self.versions)
        self.addCleanup(self.jobs.close)

    async def test_invalid_version_context_is_a_persistent_failure_without_submission(self):
        job = await self.jobs.create(str(uuid.uuid4()),'sdxl',{}, {},project_id='other',parent_version_id='parent')
        self.assertEqual(job['state'],'error')
        self.assertEqual(job['error_code'],'version_context')
        self.assertEqual(self.compute.submissions,[])
        self.assertEqual(self.jobs.get(job['id'])['state'],'error')

    async def test_completed_job_records_version_and_retries_only_metadata_after_storage_error(self):
        job = await self.jobs.create(str(uuid.uuid4()),'sdxl',{}, {},project_id='project',parent_version_id='parent')
        target = self.paths.output/'version.png'
        target.write_bytes(png())
        self.compute.current = {'state':'completed','outputs':[{'filename':'version.png','type':'output'}]}
        self.versions.error = OSError('Disk temporarily unavailable')
        first = await self.jobs.refresh(job['id'])
        self.assertEqual(first['state'],'completed')
        self.assertIn('versioning_error',first)
        self.versions.error = None
        final = await self.jobs.refresh(job['id'])
        self.assertEqual(final['versions'][0]['parent_version_id'],'parent')
        self.assertNotIn('versioning_error',final)
        self.assertEqual(len(self.compute.submissions),1)
        self.assertEqual(final['model_components'][0]['role'],'Bildmodell mit Textencoder und VAE')
        self.assertEqual(final['graph']['5']['inputs']['seed'],42)
