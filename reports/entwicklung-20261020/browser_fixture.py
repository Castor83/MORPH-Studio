"""Isolated UI verification: temporary database, tiny fixtures, no model runtime."""
import asyncio
import sys
import unittest
from pathlib import Path
from aiohttp import web

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT/'ui'), str(ROOT/'ui/tests')]
from support import Sandbox
from test_jobs import Compute
from test_server import Provider
from morph_ui.paths import ProjectPaths
from morph_ui.catalog import Catalog
from morph_ui.files import FileStore
from morph_ui.jobs import JobService
from morph_ui.settings import SettingsStore
from morph_ui.versions import VersionStore
from PIL import Image, ImageDraw
import morph_ui.server as server

case = unittest.TestCase()
box = Sandbox(case)
paths = ProjectPaths(box.root)
catalog = Catalog(paths)
files = FileStore(paths)
class FixtureCompute(Compute):
    async def submit(self,graph,prompt_id):
        result = await super().submit(graph,prompt_id)
        name = 'simulated-' + str(len(self.submissions)) + '.png'
        image = Image.new('RGB',(384,256),'#e6e4de')
        draw = ImageDraw.Draw(image)
        draw.rectangle((112,65,250,205),fill=['#517ba4','#4a9371','#c59b35'][len(self.submissions)%3])
        draw.text((15,15),'SIMULIERTER BROWSERTEST',fill='#31383e')
        image.save(paths.output/name)
        self.current = {'state':'completed','outputs':[{'filename':name,'type':'output'}]}
        return result
compute = FixtureCompute(paths)
async def status():
    return {'ready':False,'ownership':'free','message':'Simulierter Dienst; keine Modellberechnung.'}
compute.status = status
versions = VersionStore(paths,files)
jobs = JobService(paths,catalog,files,compute,versions=versions)
server.HOSTS.add('127.0.0.1:8767')
server.ORIGINS.add('http://127.0.0.1:8767')
app = server.create_app(paths,catalog,Provider(),jobs,files,SettingsStore(paths),versions=versions)
stop_event = asyncio.Event()
async def stop(request):
    if request.headers.get('X-MORPH-Request') != '1':
        raise web.HTTPForbidden()
    stop_event.set()
    return web.json_response({'stopped':True,'submissions':len(compute.submissions)})
app.router.add_post('/_fixture/stop',stop)
async def main():
    runner = web.AppRunner(app)
    await runner.setup()
    try:
        await web.TCPSite(runner,'127.0.0.1',8767).start()
        print('ISOLATED_FIXTURE_READY http://127.0.0.1:8767',flush=True)
        await stop_event.wait()
    finally:
        await runner.cleanup()
        case.doCleanups()
asyncio.run(main())
