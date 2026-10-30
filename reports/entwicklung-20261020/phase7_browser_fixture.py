"""Disposable browser fixture for prompt evidence and resources; no real models/services."""
import asyncio
import sys
import unittest
from pathlib import Path
from aiohttp import web

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / 'ui'), str(ROOT / 'ui/tests')]
from support import Sandbox
from test_jobs import Compute
from test_server import Provider
from morph_ui.paths import ProjectPaths, UiError
from morph_ui.catalog import Catalog
from morph_ui.files import FileStore
from morph_ui.jobs import JobService
from morph_ui.settings import SettingsStore
from morph_ui.versions import VersionStore
import morph_ui.server as server

case = unittest.TestCase()
paths = ProjectPaths(Sandbox(case).root)
files, catalog, settings = FileStore(paths), Catalog(paths), SettingsStore(paths)
versions = VersionStore(paths, files)
settings.save({'model_key': 'simulation-model', 'instance_id': 'simulation-instance'})

class FixtureCompute(Compute):
    def __init__(self, paths):
        super().__init__(paths)
        self.free_requests, self.offline = 0, False
    async def status(self):
        return {'ready': False, 'ownership': 'free', 'message': 'Simulation, kein echter Rechendienst.'}
    async def resource_stats(self):
        if self.offline:
            raise UiError('comfy_connection', 'SIMULATION: Ressourcen nicht erreichbar.', status=503)
        return {'system': {'ram_total': 48 * 2**30, 'ram_free': 28 * 2**30}, 'devices': [
            {'name': 'SIMULATION GPU', 'type': 'cuda', 'index': 0, 'vram_total': 16 * 2**30,
             'vram_free': (14 if self.free_requests else 4) * 2**30}]}
    async def resource_control(self):
        return {'allowed': not self.offline, 'reason': 'Nur simulierte eigene Instanz.'}
    async def free_resources(self):
        self.free_requests += 1
        return {'accepted': True, 'completed': False, 'message': 'Freigabe angefordert.'}

class FixtureProvider(Provider):
    async def list_models(self):
        return [{'key': 'simulation-model', 'name': 'SIMULATION Sprache',
                 'loaded_instances': [{'id': 'simulation-instance'}], 'capabilities': ['completion']}]
    async def propose_tools(self, instance, workflow, instruction, controls):
        self.proposals += 1
        return {'assistant_text': 'SIMULATION: Ein einzeln übernehmbarer Vorschlag.', 'steps': [
            {'workflow_id': workflow, 'prompt': 'SIMULATION: Eine blaue Keramiktasse auf einem Holztisch.',
             'controls': {'seed': 9}, 'reason': 'SIMULATION: Nur die gewünschte Farbe ändern.'}]}

compute, provider = FixtureCompute(paths), FixtureProvider()
jobs = JobService(paths, catalog, files, compute, versions=versions)
server.HOSTS.add('127.0.0.1:8767')
server.ORIGINS.add('http://127.0.0.1:8767')
app = server.create_app(paths, catalog, provider, jobs, files, settings, versions=versions)
stopping = asyncio.Event()

async def state(request):
    return web.json_response({'simulation': True, 'free_requests': compute.free_requests,
        'proposals': provider.proposals, 'submissions': len(compute.submissions), 'offline': compute.offline})
async def offline(request):
    if request.headers.get('X-MORPH-Request') != '1':
        raise web.HTTPForbidden()
    compute.offline = True
    return web.json_response({'simulation': True, 'offline': True})
async def stop(request):
    if request.headers.get('X-MORPH-Request') != '1':
        raise web.HTTPForbidden()
    stopping.set()
    return await state(request)
app.router.add_get('/_fixture/state', state)
app.router.add_post('/_fixture/offline', offline)
app.router.add_post('/_fixture/stop', stop)

async def main():
    runner = web.AppRunner(app)
    await runner.setup()
    try:
        await web.TCPSite(runner, '127.0.0.1', 8767).start()
        print('PHASE7_ISOLATED_FIXTURE_READY http://127.0.0.1:8767', flush=True)
        await stopping.wait()
    finally:
        await runner.cleanup()
        case.doCleanups()
asyncio.run(main())
