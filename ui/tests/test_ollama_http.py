import sys
import unittest
from pathlib import Path
from aiohttp import web
from aiohttp.test_utils import TestServer

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from morph_ui.paths import ProjectPaths, UiError
from morph_ui.providers.base import LocalHttp
from morph_ui.settings import SettingsStore
from support import Sandbox


class OllamaHttpTests(unittest.IsolatedAsyncioTestCase):
    async def start_transport(self, handler):
        box = Sandbox(self)
        settings = SettingsStore(ProjectPaths(box.root))
        app = web.Application()
        app.router.add_route('*', '/{tail:.*}', handler)
        server = TestServer(app)
        await server.start_server()
        self.addAsyncCleanup(server.close)
        settings.save({'endpoint': str(server.make_url('/'))})
        transport = LocalHttp(settings)
        self.addAsyncCleanup(transport.close)
        return transport

    async def test_native_api_authentication_errors_identify_ollama_without_retry(self):
        calls = []
        async def answer(request):
            calls.append(request.path)
            return web.json_response({'error': 'private server detail'}, status=401)
        transport = await self.start_transport(answer)
        with self.assertRaises(UiError) as caught:
            await transport.request('GET', '/api/tags')
        self.assertEqual(caught.exception.code, 'authentication')
        self.assertIn('Ollama', caught.exception.message)
        self.assertNotIn('private server detail', caught.exception.message)
        self.assertEqual(calls, ['/api/tags'])

    async def test_invalid_native_response_is_reported_without_retry(self):
        calls = []
        async def answer(request):
            calls.append(request.path)
            return web.Response(text='<html>unexpected</html>')
        transport = await self.start_transport(answer)
        with self.assertRaises(UiError) as caught:
            await transport.request('GET', '/api/ps')
        self.assertEqual(caught.exception.code, 'model_response')
        self.assertIn('Ollama', caught.exception.message)
        self.assertEqual(calls, ['/api/ps'])

    async def test_redirect_is_rejected_without_following_it(self):
        calls = []
        async def answer(request):
            calls.append(request.path)
            return web.Response(status=302, headers={'Location': '/redirect-target'})
        transport = await self.start_transport(answer)
        with self.assertRaises(UiError):
            await transport.request('GET', '/api/tags')
        self.assertEqual(calls, ['/api/tags'])
