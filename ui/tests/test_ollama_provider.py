import copy
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from morph_ui.catalog import Catalog
from morph_ui.paths import ProjectPaths, UiError
from support import Sandbox

try:
    from morph_ui.providers.ollama import OllamaProvider
except ModuleNotFoundError:
    OllamaProvider = None


CHAT_MODEL = 'qwen3.5:9b'
OTHER_MODEL = 'gemma3:4b'


class OllamaWire:
    """Native API fixtures; no model server or model execution is involved."""
    def __init__(self):
        self.calls = []
        self.tags = {'models': [
            {'name': CHAT_MODEL, 'model': CHAT_MODEL, 'size': 6000000000,
             'digest': 'local-chat-digest', 'details': {'family': 'qwen35'}},
            {'name': OTHER_MODEL, 'model': OTHER_MODEL, 'size': 3000000000,
             'digest': 'local-other-digest', 'details': {'family': 'gemma3'}},
            {'name': 'nomic-embed-text:latest', 'model': 'nomic-embed-text:latest',
             'size': 274000000, 'digest': 'local-embedding-digest',
             'details': {'family': 'nomic-bert'}},
            {'name': 'cloud-proxy:latest', 'model': 'cloud-proxy:latest',
             'remote_host': 'https://ollama.com', 'remote_model': 'large:cloud',
             'details': {'family': 'qwen3'}},
        ]}
        self.ps = {'models': [
            {'name': CHAT_MODEL, 'model': CHAT_MODEL, 'size': 6000000000,
             'size_vram': 6000000000, 'context_length': 4096,
             'details': {'family': 'qwen35'}},
            {'name': 'foreign:latest', 'model': 'foreign:latest',
             'size': 2000000000, 'context_length': 4096},
        ]}
        self.show = {'capabilities': ['completion', 'thinking'],
                     'details': {'family': 'qwen35'}, 'model_info': {}}
        self.generated = {'model': OTHER_MODEL, 'response': '',
                          'done': True, 'done_reason': 'load'}
        self.chat = {'model': CHAT_MODEL, 'done': True, 'done_reason': 'stop',
                     'message': {'role': 'assistant', 'content': json.dumps({
                         'assistant_text': 'Die Tasse blau färben.',
                         'prompt': 'Change only the mug to blue.',
                         'controls': {'width': 768}})}}
        self.confirm_state = True
        self.failure = None
        self.closed = False

    async def request(self, method, path, payload=None):
        self.calls.append((method, path, copy.deepcopy(payload)))
        if self.failure:
            raise self.failure
        if (method, path) == ('GET', '/api/tags'):
            return copy.deepcopy(self.tags)
        if (method, path) == ('GET', '/api/ps'):
            return copy.deepcopy(self.ps)
        if (method, path) == ('POST', '/api/show'):
            return copy.deepcopy(self.show)
        if (method, path) == ('POST', '/api/generate'):
            if self.confirm_state:
                if payload['keep_alive'] == 0:
                    self.ps['models'] = [x for x in self.ps['models']
                                         if x['name'] != payload['model']]
                elif not any(x['name'] == payload['model'] for x in self.ps['models']):
                    self.ps['models'].append({'name': payload['model'], 'model': payload['model']})
            answer = copy.deepcopy(self.generated)
            if isinstance(answer, dict) and answer.get('model') == OTHER_MODEL:
                answer['model'] = payload['model']
            return answer
        if (method, path) == ('POST', '/api/chat'):
            return copy.deepcopy(self.chat)
        raise AssertionError('Unexpected native Ollama route: ' + path)

    async def close(self):
        self.closed = True


class OllamaProviderTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.assertIsNotNone(OllamaProvider, 'Nativer Ollama-Adapter fehlt')
        self.paths = ProjectPaths(Sandbox(self).root)
        self.catalog = Catalog(self.paths)
        self.wire = OllamaWire()
        self.provider = OllamaProvider(None, self.catalog, self.wire)

    def prediction_calls(self):
        return [call for call in self.wire.calls if call[1] == '/api/chat']

    def set_proposal(self, result):
        self.wire.chat['message']['content'] = json.dumps(result)

    async def propose(self, workflow='kontext', allowed=None, model=CHAT_MODEL, instruction='Tasse blau färben'):
        return await self.provider.propose(model, workflow, instruction,
                                           allowed if allowed is not None else self.catalog.controls(workflow))

    async def test_listing_combines_installed_and_loaded_without_loading(self):
        result = await self.provider.list_models()
        self.assertEqual(result, [
            {'key': CHAT_MODEL, 'name': CHAT_MODEL,
             'loaded_instances': [{'id': CHAT_MODEL}], 'capabilities': None},
            {'key': OTHER_MODEL, 'name': OTHER_MODEL,
             'loaded_instances': [], 'capabilities': None},
        ])
        self.assertEqual(self.wire.calls, [('GET', '/api/tags', None), ('GET', '/api/ps', None)])

    async def test_listing_filters_explicit_embedding_capability(self):
        self.wire.tags['models'].append({'name': 'custom-embedding:latest', 'capabilities': ['embedding']})
        result = await self.provider.list_models()
        self.assertNotIn('custom-embedding:latest', [x['key'] for x in result])

    async def test_malformed_model_lists_are_rejected(self):
        for attribute, value in [('tags', []), ('tags', {'models': {}}), ('ps', {}), ('ps', {'models': None})]:
            with self.subTest(attribute=attribute, value=value):
                wire = OllamaWire()
                setattr(wire, attribute, value)
                provider = OllamaProvider(None, self.catalog, wire)
                with self.assertRaises(UiError):
                    await provider.list_models()
                self.assertFalse(any(call[0] == 'POST' for call in wire.calls))

    async def test_load_uses_exact_installed_name_and_confirms_loaded_state(self):
        result = await self.provider.load(OTHER_MODEL)
        self.assertEqual(result, {'status': 'loaded', 'instance_id': OTHER_MODEL})
        self.assertIn(('POST', '/api/show', {'model': OTHER_MODEL}), self.wire.calls)
        self.assertEqual([x for x in self.wire.calls if x[1] == '/api/generate'], [
            ('POST', '/api/generate', {'model': OTHER_MODEL, 'stream': False,
                                      'keep_alive': '5m', 'options': {'num_ctx': 4096}})])
        self.assertEqual(self.wire.calls[-1], ('GET', '/api/ps', None))
        self.assertIn('foreign:latest', [x['name'] for x in self.wire.ps['models']])

    async def test_unknown_embedding_cloud_and_non_string_keys_never_load(self):
        for key in ['missing:latest', 'gemma3', 'nomic-embed-text:latest', 'cloud-proxy:latest', None, []]:
            with self.subTest(key=key):
                self.wire.calls.clear()
                with self.assertRaises(UiError):
                    await self.provider.load(key)
                self.assertFalse(any(x[1] == '/api/generate' for x in self.wire.calls))

    async def test_show_rejects_remote_embedding_and_unconfirmed_capability(self):
        for detail in [None, {}, {'capabilities': ['embedding']},
                       {'capabilities': ['completion', 42]},
                       {'capabilities': ['completion'], 'remote_host': 'https://ollama.com'},
                       {'capabilities': ['completion'], 'remote_model': 'qwen:cloud'}]:
            with self.subTest(detail=detail):
                self.wire.show = detail
                self.wire.calls.clear()
                with self.assertRaises(UiError):
                    await self.provider.load(OTHER_MODEL)
                self.assertFalse(any(x[1] == '/api/generate' for x in self.wire.calls))

    async def test_load_requires_done_and_ps_confirmation_without_retry(self):
        for answer, confirm in [(None, True), ({}, True), ({'done': False}, True),
                                ({'done': 1}, True), ({'done': True}, False)]:
            with self.subTest(answer=answer, confirm=confirm):
                wire = OllamaWire()
                wire.generated, wire.confirm_state = answer, confirm
                provider = OllamaProvider(None, self.catalog, wire)
                with self.assertRaises(UiError):
                    await provider.load(OTHER_MODEL)
                self.assertEqual(sum(x[1] == '/api/generate' for x in wire.calls), 1)

    async def test_unload_targets_only_selected_loaded_model_and_confirms_absence(self):
        await self.provider.unload(CHAT_MODEL)
        self.assertEqual([x for x in self.wire.calls if x[1] == '/api/generate'], [
            ('POST', '/api/generate', {'model': CHAT_MODEL, 'stream': False, 'keep_alive': 0})])
        self.assertEqual(self.wire.calls[-1], ('GET', '/api/ps', None))
        self.assertEqual([x['name'] for x in self.wire.ps['models']], ['foreign:latest'])

    async def test_unload_rejects_foreign_and_unloaded_names_without_generation(self):
        for key in ['foreign:latest', OTHER_MODEL, None, []]:
            with self.subTest(key=key):
                self.wire.calls.clear()
                with self.assertRaises(UiError):
                    await self.provider.unload(key)
                self.assertFalse(any(x[1] == '/api/generate' for x in self.wire.calls))

    async def test_unload_requires_done_and_ps_confirmation(self):
        for answer, confirm in [({'done': False}, True), ({'done': True}, False)]:
            with self.subTest(answer=answer, confirm=confirm):
                wire = OllamaWire()
                wire.generated, wire.confirm_state = answer, confirm
                provider = OllamaProvider(None, self.catalog, wire)
                with self.assertRaises(UiError):
                    await provider.unload(CHAT_MODEL)
                self.assertEqual(sum(x[1] == '/api/generate' for x in wire.calls), 1)

    async def test_generate_error_or_foreign_model_never_confirms_success(self):
        for answer in [{'done': True, 'error': 'backend failed'},
                       {'done': True, 'model': 'foreign:latest'}]:
            with self.subTest(answer=answer):
                wire = OllamaWire()
                wire.generated = answer
                provider = OllamaProvider(None, self.catalog, wire)
                with self.assertRaises(UiError):
                    await provider.load(OTHER_MODEL)
                self.assertEqual(sum(x[1] == '/api/generate' for x in wire.calls), 1)

    async def test_proposal_native_schema_and_bounded_generation_preserve_contract(self):
        result = await self.propose()
        self.assertEqual(result, {'assistant_text': 'Die Tasse blau färben.',
                                  'prompt': 'Change only the mug to blue.', 'controls': {'width': 768}})
        payload = self.prediction_calls()[0][2]
        self.assertEqual(payload['model'], CHAT_MODEL)
        self.assertIs(payload['stream'], False)
        self.assertIs(payload['think'], False)
        self.assertEqual(payload['keep_alive'], '5m')
        self.assertEqual(payload['options'], {'num_predict': 1024, 'num_ctx': 4096, 'temperature': 0.2})
        self.assertEqual(payload['format']['required'], ['assistant_text', 'prompt', 'controls'])
        self.assertIs(payload['format']['additionalProperties'], False)
        self.assertNotIn('image_model', payload['format']['properties']['controls']['properties'])
        self.assertNotIn('response_format', payload)
        self.assertEqual(payload['messages'][-1], {'role': 'user', 'content': 'Tasse blau färben'})
        self.assertEqual(len(self.prediction_calls()), 1)

    async def test_proposal_requires_installed_loaded_local_completion_model(self):
        for key, show in [(OTHER_MODEL, {'capabilities': ['completion']}),
                          ('foreign:latest', {'capabilities': ['completion']}),
                          (CHAT_MODEL, {'capabilities': ['embedding']}),
                          (CHAT_MODEL, {'capabilities': ['completion'], 'remote_host': 'https://ollama.com'})]:
            with self.subTest(key=key, show=show):
                self.wire.show, self.wire.calls = show, []
                with self.assertRaises(UiError):
                    await self.propose(model=key)
                self.assertEqual(self.prediction_calls(), [])

    async def test_invalid_instruction_blocks_all_network_requests(self):
        for instruction in [None, '', '  ', 'x' * 8001]:
            with self.subTest(instruction=repr(instruction)[:40]):
                self.wire.calls.clear()
                with self.assertRaises(UiError):
                    await self.propose(instruction=instruction)
                self.assertEqual(self.wire.calls, [])

    async def test_malformed_truncated_and_non_assistant_chat_never_retry(self):
        for patch in [None, {}, {'done': False}, {'done': 1}, {'done_reason': 'length'},
                      {'done_reason': None}, {'message': {'role': 'user', 'content': '{}'}},
                      {'message': {'role': 'assistant', 'content': '{"prompt":'}},
                      {'message': {'role': 'assistant', 'content': None}},
                      {'remote_model': 'foreign:cloud'}, {'error': 'backend failed'},
                      {'model': 'foreign:latest'}]:
            with self.subTest(patch=patch):
                wire = OllamaWire()
                if patch is None or not patch:
                    wire.chat = patch
                else:
                    wire.chat.update(patch)
                provider = OllamaProvider(None, self.catalog, wire)
                with self.assertRaises(UiError):
                    await provider.propose(CHAT_MODEL, 'kontext', 'Blau', self.catalog.controls('kontext'))
                self.assertEqual(sum(x[1] == '/api/chat' for x in wire.calls), 1)

    async def test_proposal_rejects_extra_fields_model_changes_and_invalid_controls(self):
        invalid = [[], {'assistant_text': 'ok', 'prompt': 'A mug.', 'controls': {}, 'command': 'run'},
                   {'assistant_text': 'ok', 'prompt': 'A mug.', 'controls': {'image_model': 'diffusion_models/other.safetensors'}},
                   {'assistant_text': 'ok', 'prompt': 'A mug.', 'controls': {'width': 17}},
                   {'assistant_text': 'ok', 'prompt': 'A mug.', 'controls': {'width': 999999}},
                   {'assistant_text': 'ok', 'prompt': 'A mug.', 'controls': {'width': True}},
                   {'assistant_text': 'ok', 'prompt': 'A mug.', 'controls': {'shell': 'run'}},
                   {'assistant_text': 'x' * 2001, 'prompt': 'A mug.', 'controls': {}},
                   {'assistant_text': 'ok', 'prompt': 'x' * 8001, 'controls': {}}]
        for result in invalid:
            with self.subTest(result=repr(result)[:100]):
                self.set_proposal(result)
                self.wire.calls.clear()
                with self.assertRaises(UiError):
                    await self.propose()
                self.assertEqual(len(self.prediction_calls()), 1)

    async def test_current_wan_steps_and_split_are_used_for_validation(self):
        allowed = self.catalog.controls('wan')
        allowed['steps']['default'], allowed['split']['default'] = 6, 2
        self.set_proposal({'assistant_text': 'Vier Schritte.', 'prompt': 'A calm scene.', 'controls': {'steps': 4}})
        result = await self.propose('wan', allowed)
        self.assertEqual(result['controls'], {'steps': 4})
        self.set_proposal({'assistant_text': 'Zwei Schritte.', 'prompt': 'A calm scene.', 'controls': {'steps': 2}})
        with self.assertRaises(UiError):
            await self.propose('wan', allowed)

    async def test_face_swap_rejects_prompt_and_accepts_only_face_indices(self):
        self.set_proposal({'assistant_text': 'Erstes Gesicht verwenden.', 'prompt': '', 'controls': {'target_face': '0'}})
        self.assertEqual((await self.propose('reactor'))['controls'], {'target_face': '0'})
        self.set_proposal({'assistant_text': 'Text.', 'prompt': 'Change a face.', 'controls': {}})
        with self.assertRaises(UiError):
            await self.propose('reactor')

    async def test_connection_failure_is_not_retried(self):
        self.wire.failure = UiError('model_connection', 'Nicht erreichbar.', status=503)
        with self.assertRaises(UiError):
            await self.provider.list_models()
        self.assertEqual(len(self.wire.calls), 1)

    async def test_close_releases_owned_http_transport(self):
        await self.provider.close()
        self.assertTrue(self.wire.closed)


if __name__ == '__main__':
    unittest.main()
