"""Isolated Phase5 browser fixture. Seeded synthetic versions; NO model execution."""
import asyncio
import io
import sys
import unittest
import uuid
from pathlib import Path
from aiohttp import web
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / 'ui'), str(ROOT / 'ui/tests')]
from support import Sandbox
from test_jobs import Compute
from test_server import Provider
from morph_ui.paths import ProjectPaths
from morph_ui.catalog import Catalog
from morph_ui.files import FileStore
from morph_ui.jobs import JobService
from morph_ui.settings import SettingsStore
from morph_ui.versions import VersionStore
import morph_ui.server as server

case = unittest.TestCase()
paths = ProjectPaths(Sandbox(case).root)
files = FileStore(paths)
versions = VersionStore(paths, files)

def picture(color):
    image = Image.new('RGB', (384, 256), '#e8e4dc')
    draw = ImageDraw.Draw(image)
    draw.ellipse((164, 36, 220, 92), fill='#d5a282')
    draw.polygon([(154, 96), (230, 96), (259, 147), (234, 161), (228, 220), (156, 220), (150, 161), (125, 147)], fill=color)
    draw.text((12, 12), 'SIMULATION - KEIN MODELLERGEBNIS', fill='#343c44')
    return image

stream = io.BytesIO()
picture('#b84545').save(stream, format='PNG')
original = files.save_upload(stream.getvalue(), 'SIMULATION-Original.png')
project = versions.create_project(str(uuid.uuid4()), original['id'], 'SIMULATION Vergleich und Maske')
root_version = project['original_version_id']
parent = root_version
for index, color in enumerate(['#376aa8', '#48926c', '#b98c3d']):
    path = paths.output / ('SIMULATION-seed-' + str(index) + '.png')
    picture(color).save(path)
    result = versions.record_job_outputs({
        'id': str(uuid.uuid4()), 'state': 'completed', 'project_id': project['id'],
        'parent_version_id': parent, 'workflow_id': 'krea2',
        'controls': {'prompt': 'SIMULATION: Nur Hemdfarbe ändern.', 'seed': index},
        'graph': {}, 'model_components': [], 'outputs': [files.register_output(path)]})[0]
    parent = result['id'] if index == 0 else parent

class FixtureCompute(Compute):
    async def upload(self, path):
        relative = 'phase5-browser/' + path.name
        target = self.paths.input / relative
        target.parent.mkdir(exist_ok=True)
        target.write_bytes(path.read_bytes())
        return relative

    async def require_region_nodes(self):
        pass

    async def status(self):
        return {'ready': False, 'ownership': 'free', 'message': 'Simulierter Browserdienst, keine echten Modelle.'}

    async def submit(self, graph, prompt_id):
        result = await super().submit(graph, prompt_id)
        generated = picture('#9845af')
        composites = [node for node in graph.values() if node['class_type'] == 'ImageCompositeMasked']
        if composites:
            inputs = composites[0]['inputs']
            source_name = graph[inputs['destination'][0]]['inputs']['image']
            mask_name = graph[inputs['mask'][0]]['inputs']['image']
            with Image.open(self.paths.input / source_name) as source, Image.open(self.paths.input / mask_name) as mask:
                generated = Image.composite(generated.resize(source.size), source.convert('RGB'), mask.convert('L'))
        name = 'SIMULATION-browser-submit-' + str(len(self.submissions)) + '.png'
        generated.save(self.paths.output / name)
        self.current = {'state': 'completed', 'outputs': [{'filename': name, 'type': 'output'}]}
        return result

compute = FixtureCompute(paths)
jobs = JobService(paths, Catalog(paths), files, compute, versions=versions)
server.HOSTS.add('127.0.0.1:8767')
server.ORIGINS.add('http://127.0.0.1:8767')
app = server.create_app(paths, jobs.catalog, Provider(), jobs, files, SettingsStore(paths), versions=versions)
stop_event = asyncio.Event()

async def state(request):
    return web.json_response({'simulation': True, 'submissions': len(compute.submissions),
        'project': versions.get_project(project['id']), 'jobs': jobs.list_recent()})

async def stop(request):
    if request.headers.get('X-MORPH-Request') != '1':
        raise web.HTTPForbidden()
    stop_event.set()
    return web.json_response({'stopped': True, 'submissions': len(compute.submissions)})

app.router.add_get('/_fixture/state', state)
app.router.add_post('/_fixture/stop', stop)

async def main():
    runner = web.AppRunner(app)
    await runner.setup()
    try:
        await web.TCPSite(runner, '127.0.0.1', 8767).start()
        print('PHASE5_ISOLATED_FIXTURE_READY http://127.0.0.1:8767', flush=True)
        await stop_event.wait()
    finally:
        await runner.cleanup()
        case.doCleanups()

asyncio.run(main())
