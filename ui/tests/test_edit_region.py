import copy
import hashlib
import io
import sys
import unittest
import uuid
from pathlib import Path

from PIL import Image
from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer

sys.path[:0] = [str(Path(__file__).resolve().parents[1]), str(Path(__file__).resolve().parent)]
from morph_ui.catalog import Catalog
from morph_ui.comfy import ComfyClient
from morph_ui.files import FileStore
from morph_ui.jobs import JobService
from morph_ui.paths import ProjectPaths, UiError
from morph_ui.server import create_app
from morph_ui.versions import VersionStore
from support import Sandbox
from test_jobs import Compute
from test_server import HEADERS, Provider


def image_bytes(size=(48, 32), mode='RGB', color=(120, 80, 30), *, format='PNG', orientation=None, transparency=None):
    image = Image.new(mode, size, color)
    data = io.BytesIO()
    options = {}
    if transparency is not None:
        options['transparency'] = transparency
    if orientation is not None:
        exif = image.getexif()
        exif[274] = orientation
        options['exif'] = exif
    image.save(data, format=format, **options)
    return data.getvalue()


def mask_bytes(size=(48, 32)):
    image = Image.new('L', size, 0)
    image.putpixel((1, 1), 255)
    data = io.BytesIO()
    image.save(data, format='PNG')
    return data.getvalue()


class RegionCompute(Compute):
    def __init__(self, paths):
        super().__init__(paths)
        self.uploads = []
        self.region_checks = 0
        self.region_error = None
        self.after_region_check = None

    async def require_region_nodes(self):
        self.region_checks += 1
        if self.region_error:
            raise self.region_error
        if self.after_region_check:
            self.after_region_check()

    async def upload(self, path):
        name = 'confirmed/' + str(len(self.uploads)) + '-' + path.name
        self.uploads.append((path, name))
        return name


class EditRegionJobsTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.paths = ProjectPaths(Sandbox(self).root)
        self.files = FileStore(self.paths)
        self.addCleanup(self.files.close)
        self.versions = VersionStore(self.paths, self.files)
        self.addCleanup(self.versions.close)
        self.catalog = Catalog(self.paths)
        self.compute = RegionCompute(self.paths)
        self.jobs = JobService(self.paths, self.catalog, self.files, self.compute, self.versions)
        self.addCleanup(self.jobs.close)
        source = self.files.save_upload(image_bytes(), 'original.png')
        project = self.versions.create_project(str(uuid.uuid4()), source['id'], 'Bereich')
        self.context = self.versions.prepare_input(project['original_version_id'])
        self.mask = self.files.save_upload(mask_bytes(), 'maske.png')
        self.region = {'mask_media_id': self.mask['id'], 'source_media_id': self.context['image']['id'],
                       'parent_version_id': self.context['parent_version_id']}

    async def create(self, *, workflow='kontext', region=None, controls=None, context=None):
        context = self.context if context is None else context
        return await self.jobs.create(str(uuid.uuid4()), workflow,
            {'width': 768, 'height': 512} if controls is None else controls,
            {'image': context['image']['id']}, project_id=context['project_id'],
            parent_version_id=context['parent_version_id'], edit_region=self.region if region is None else region)

    async def test_masked_job_binds_parent_hash_and_uses_confirmed_upload_names(self):
        job = await self.create()
        self.assertEqual(job['state'], 'queued')
        graph = self.compute.submissions[0][0]
        composites = [node for node in graph.values() if node['class_type'] == 'ImageCompositeMasked']
        self.assertEqual(len(composites), 1)
        inputs = composites[0]['inputs']
        self.assertEqual(inputs['destination'], ['4', 0])
        self.assertEqual(inputs['source'], ['13', 0])
        self.assertTrue(inputs['resize_source'])
        loader = graph[inputs['mask'][0]]
        self.assertEqual(loader['inputs'], {'image': self.compute.uploads[1][1], 'channel': 'red'})
        self.assertEqual(graph['4']['inputs']['image'], self.compute.uploads[0][1])
        self.assertNotEqual(graph['14']['inputs']['images'], ['13', 0])
        region = job['edit_region']
        self.assertEqual(region['mode'], 'masked_composite')
        self.assertEqual((region['width'], region['height']), (48, 32))
        self.assertEqual(region['mask_sha256'], hashlib.sha256(mask_bytes()).hexdigest())
        self.assertEqual(region['source_sha256'], hashlib.sha256(image_bytes()).hexdigest())

    async def test_krea_keeps_sampler_and_reference_patch_and_changes_only_saved_composite(self):
        job = await self.create(workflow='krea2')
        self.assertEqual(job['state'], 'queued')
        graph = job['graph']
        original = self.catalog.build('krea2', {'width': 768, 'height': 512}, {'image': self.compute.uploads[0][1]}, uploaded=True)
        for node in ['53', '73', '79', '82', '84', '85']:
            self.assertEqual(graph[node], original[node])
        composite = graph[graph['29']['inputs']['images'][0]]
        self.assertEqual(composite['inputs']['destination'], ['72', 0])
        self.assertEqual(composite['inputs']['source'], ['54', 0])

    async def test_stale_mask_context_and_unsupported_workflow_fail_before_service(self):
        bad_regions = [dict(self.region, source_media_id=self.mask['id']),
                       dict(self.region, parent_version_id='0' * 32),
                       dict(self.region, command='ignore'), {}, 'mask']
        for region in bad_regions:
            with self.subTest(region=region):
                job = await self.create(region=region)
                self.assertEqual(job['state'], 'error')
                self.assertTrue(job['error_code'].startswith('edit_region'))
        job = await self.create(workflow='wan')
        self.assertEqual(job['error_code'], 'edit_region_workflow')
        self.assertEqual(self.compute.started, 0)
        self.assertEqual(self.compute.uploads, [])
        self.assertEqual(self.compute.submissions, [])

    async def test_mask_requires_version_context(self):
        job = await self.jobs.create(str(uuid.uuid4()), 'kontext', {'width': 768, 'height': 512},
                                     {'image': self.context['image']['id']}, edit_region=self.region)
        self.assertEqual(job['error_code'], 'edit_region_context')
        self.assertEqual(self.compute.started, 0)

    async def test_mask_validation_rejects_wrong_size_empty_color_alpha_and_jpeg(self):
        examples = [mask_bytes((32, 48)), image_bytes(mode='L', color=0),
                    image_bytes(color=(255, 0, 0)), image_bytes(mode='RGBA', color=(255, 255, 255, 0)),
                    image_bytes(mode='L', color=255, format='JPEG')]
        for data in examples:
            mask = self.files.save_upload(data, 'maske.png')
            job = await self.create(region=dict(self.region, mask_media_id=mask['id']))
            self.assertEqual(job['state'], 'error')
            self.assertTrue(job['error_code'].startswith('edit_region'))
        self.assertEqual(self.compute.started, 0)

    async def test_canvas_opaque_rgba_grayscale_is_accepted(self):
        mask = self.files.save_upload(image_bytes(mode='RGBA', color=(255, 255, 255, 255)), 'canvas.png')
        job = await self.create(region=dict(self.region, mask_media_id=mask['id']))
        self.assertEqual(job['state'], 'queued')

    async def assert_transparent_source_rejected(self, data):
        source = self.files.save_upload(data, 'transparent.png')
        project = self.versions.create_project(str(uuid.uuid4()), source['id'], 'Transparenz')
        context = self.versions.prepare_input(project['original_version_id'])
        region = dict(self.region, source_media_id=context['image']['id'], parent_version_id=context['parent_version_id'])
        job = await self.create(context=context, region=region)
        self.assertEqual(job['state'], 'error')
        self.assertEqual(job['error_code'], 'edit_region_transparency')
        self.assertEqual(self.compute.started, 0)
        # Uploads and ordinary full-image jobs retain their existing contract.
        ordinary = await self.jobs.create(str(uuid.uuid4()), 'kontext', {'width': 768, 'height': 512},
            {'image': context['image']['id']}, project_id=context['project_id'], parent_version_id=context['parent_version_id'])
        self.assertEqual(ordinary['state'], 'queued')

    async def test_transparent_rgba_source_is_rejected_only_for_region_jobs(self):
        await self.assert_transparent_source_rejected(image_bytes(mode='RGBA', color=(120, 80, 30, 128)))

    async def test_source_png_trns_transparency_is_rejected_before_service(self):
        await self.assert_transparent_source_rejected(image_bytes(transparency=(120, 80, 30)))

    async def test_mask_png_trns_transparency_is_rejected_before_service(self):
        for mode, color in [('L', 255), ('RGB', (255, 255, 255))]:
            with self.subTest(mode=mode):
                mask = self.files.save_upload(image_bytes(mode=mode, color=color, transparency=color), 'transparent-mask.png')
                job = await self.create(region=dict(self.region, mask_media_id=mask['id']))
                self.assertEqual(job['state'], 'error')
                self.assertEqual(job['error_code'], 'edit_region_mask')
                self.assertEqual(self.compute.started, 0)

    async def test_aspect_mismatch_is_an_actionable_preflight_failure(self):
        job = await self.create(controls={'width': 512, 'height': 512})
        self.assertEqual(job['error_code'], 'edit_region_geometry')
        self.assertIn('Seitenverhältnis', job['error'])
        self.assertEqual(self.compute.started, 0)

    async def test_rotated_source_requires_explicit_normalization(self):
        source = self.files.save_upload(image_bytes(format='JPEG', orientation=6), 'rotated.jpg')
        project = self.versions.create_project(str(uuid.uuid4()), source['id'], 'Drehung')
        context = self.versions.prepare_input(project['original_version_id'])
        region = dict(self.region, source_media_id=context['image']['id'], parent_version_id=context['parent_version_id'])
        job = await self.create(context=context, region=region)
        self.assertEqual(job['error_code'], 'edit_region_orientation')
        self.assertEqual(self.compute.started, 0)

    async def test_missing_region_node_stops_before_upload_and_submission(self):
        self.compute.region_error = UiError('comfy_region_node', 'Bereichsknoten fehlt.')
        job = await self.create()
        self.assertEqual(job['error_code'], 'comfy_region_node')
        self.assertEqual(self.compute.uploads, [])
        self.assertEqual(self.compute.submissions, [])

    async def test_changed_mask_after_preflight_is_rejected_before_upload(self):
        self.compute.after_region_check = lambda: self.files.resolve(self.mask['id']).write_bytes(mask_bytes((32, 48)))
        job = await self.create()
        self.assertEqual(job['error_code'], 'edit_region_changed')
        self.assertEqual(self.compute.uploads, [])

    async def test_source_changed_during_parent_validation_cannot_rebind_the_mask(self):
        validate = self.versions.validate_job_context
        def changed_after_parent(*args):
            context = validate(*args)
            self.files.resolve(self.context['image']['id']).write_bytes(image_bytes(color=(10, 20, 30)))
            return context
        self.versions.validate_job_context = changed_after_parent
        job = await self.create()
        self.assertEqual(job['error_code'], 'edit_region_context')
        self.assertEqual(self.compute.started, 0)

    async def test_completed_result_freezes_mask_metadata_in_version(self):
        job = await self.create()
        target = self.paths.output / 'region.png'
        target.write_bytes(image_bytes())
        self.compute.current = {'state': 'completed', 'outputs': [{'filename': target.name, 'type': 'output'}]}
        result = await self.jobs.refresh(job['id'])
        self.assertEqual(result['state'], 'completed')
        self.assertEqual(result['versions'][0]['metadata']['edit_region'], job['edit_region'])

    async def test_post_jobs_forwards_region_contract(self):
        app = create_app(self.paths, self.catalog, Provider(), self.jobs, self.files, versions=self.versions)
        client = TestClient(TestServer(app))
        await client.start_server()
        try:
            response = await client.post('/api/jobs', json={'request_id': str(uuid.uuid4()), 'workflow_id': 'kontext',
                'controls': {'width': 768, 'height': 512}, 'images': {'image': self.context['image']['id']},
                'project_id': self.context['project_id'], 'parent_version_id': self.context['parent_version_id'],
                'edit_region': self.region}, headers=HEADERS)
            self.assertEqual(response.status, 200)
            self.assertEqual((await response.json())['data']['edit_region']['mask_media_id'], self.mask['id'])
            for module in ['comparison.js', 'regions.js']:
                response = await client.get('/static/' + module, headers=HEADERS)
                self.assertEqual(response.status, 200, module)
        finally:
            await client.close()


class RegionNodeCapabilityTests(unittest.IsolatedAsyncioTestCase):
    async def test_schema_checks_mask_channel_composite_signature_and_output_types(self):
        paths = ProjectPaths(Sandbox(self).root)
        schemas = {
            'LoadImageMask': {'input': {'required': {'image': [[], {}], 'channel': [['red', 'alpha']]}}, 'output': ['MASK']},
            'ImageCompositeMasked': {'input': {'required': {'destination': ['IMAGE'], 'source': ['IMAGE'], 'x': ['INT'],
                'y': ['INT'], 'resize_source': ['BOOLEAN']}, 'optional': {'mask': ['MASK']}}, 'output': ['IMAGE']}}
        app = web.Application()
        async def schema(request):
            kind = request.match_info['kind']
            return web.json_response({kind: schemas[kind]} if kind in schemas else {})
        app.router.add_get('/object_info/{kind}', schema)
        server = TestServer(app)
        await server.start_server()
        self.addAsyncCleanup(server.close)
        client = ComfyClient(paths, str(server.make_url('/')).rstrip('/'))
        self.addAsyncCleanup(client.close)
        await client.require_region_nodes()
        original = copy.deepcopy(schemas)
        for kind, modify in [('LoadImageMask', lambda s: s['input']['required'].update(channel=[['alpha']])),
                             ('ImageCompositeMasked', lambda s: s['input']['optional'].pop('mask')),
                             ('ImageCompositeMasked', lambda s: s.update(output=['LATENT']))]:
            schemas.clear()
            schemas.update(copy.deepcopy(original))
            modify(schemas[kind])
            with self.assertRaises(UiError) as error:
                await client.require_region_nodes()
            self.assertEqual(error.exception.code, 'comfy_region_node')
