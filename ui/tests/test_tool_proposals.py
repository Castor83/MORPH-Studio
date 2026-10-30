import copy
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, Mock

from aiohttp.test_utils import TestClient, TestServer

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from morph_ui.catalog import Catalog, ENTRIES
from morph_ui.files import FileStore
from morph_ui.jobs import JobService
from morph_ui.paths import ProjectPaths, UiError
from morph_ui.providers.ollama import OllamaProvider
from morph_ui.providers.lmstudio import LMStudioProvider
from morph_ui.server import create_app
from support import Sandbox
from test_ollama_provider import CHAT_MODEL, OllamaWire
from test_provider import Wire
from test_server import HEADERS
from test_jobs import Compute


def plan(workflow='kontext', controls=None, prompt='Färbe ausschließlich die Tasse blau.'):
    proposed_controls = dict(controls or {})
    if workflow in {'sdxl', 'wan', 'qwen21'}:
        proposed_controls.setdefault('negative', '')
    return {'assistant_text': 'Ich schlage diese Arbeitsschritte vor.', 'steps': [{
        'workflow_id': workflow, 'prompt': prompt, 'controls': proposed_controls,
        'reason': 'Dieses Werkzeug kann die gewünschte Änderung ausführen.'}]}


class ToolProposalTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.paths = ProjectPaths(Sandbox(self).root)
        self.catalog = Catalog(self.paths)
        self.wire = OllamaWire()
        self.provider = OllamaProvider(None, self.catalog, self.wire)
        self.catalog.readiness = Mock(side_effect=AssertionError('No readiness during planning'))
        self.catalog.prepared_graph = Mock(side_effect=AssertionError('No graph during planning'))
        self.set_plan(plan())

    def set_plan(self, value):
        self.wire.chat['message']['content'] = json.dumps(value)

    async def propose(self, workflow='kontext', controls=None, instruction='Tasse blau färben'):
        method = getattr(self.provider, 'propose_tools', None)
        self.assertTrue(callable(method), 'Der begrenzte Werkzeugvorschlag fehlt.')
        return await method(CHAT_MODEL, workflow, instruction, controls or {})

    def chat_calls(self):
        return [call for call in self.wire.calls if call[1] == '/api/chat']

    async def test_new_instruction_has_priority_and_old_free_text_is_only_user_context(self):
        old = 'ALTPROMPT: Ein rotes Auto auf einer Straße.'
        negative = 'ALTNEGATIV: keine blauen Gegenstände'
        instruction = '\n  NEUER AUFTRAG: Erstelle eine blaue Tasse ohne Auto.\n'
        lm_wire = Wire()
        lm_wire.content = json.dumps(plan())
        for provider, instance in [(self.provider, CHAT_MODEL),
                                   (LMStudioProvider(None, self.catalog, lm_wire), 'chosen-instance')]:
            with self.subTest(provider=type(provider).__name__):
                await provider.propose_tools(instance, 'sdxl', instruction,
                                             {'prompt':old, 'negative':negative})
                payload = provider.wire.calls[-1][2]
                messages = payload['messages']
                self.assertNotIn(old, messages[0]['content'])
                self.assertNotIn(negative, messages[0]['content'])
                self.assertEqual([m['role'] for m in messages], ['system', 'user', 'user'])
                self.assertIn(old, messages[1]['content'])
                self.assertIn(negative, messages[1]['content'])
                self.assertEqual(messages[1]['content'].count(old), 1)
                self.assertEqual(messages[1]['content'].count(negative), 1)
                self.assertEqual(messages[-1], {'role':'user', 'content':instruction})
                self.assertIn('letzten Nutzernachricht', messages[0]['content'])
                self.assertIn('Bei Widersprüchen gilt der neue Auftrag', messages[0]['content'])
                self.assertIn('negative: Auftragswidersprüche entfernen', messages[0]['content'])
                self.assertEqual(len([c for c in provider.wire.calls
                                      if c[1] in ('/api/chat','/v1/chat/completions')]), 1)

    async def test_selects_existing_tools_with_german_schema_and_no_execution(self):
        value = plan('krea2', {'width': 768})
        value['steps'].append(plan('reactor', {'target_face': '0'}, '')['steps'][0])
        self.set_plan(value)
        result = await self.propose()
        self.assertEqual(result['assistant_text'], value['assistant_text'])
        self.assertEqual([step['workflow_id'] for step in result['steps']], ['krea2', 'reactor'])
        self.assertEqual(result['steps'][0]['controls']['width'], 768)
        self.assertEqual(result['steps'][1]['controls'], {'target_face': '0', 'source_face': '0'})
        self.assertNotIn('image_model', result['steps'][0]['controls'])
        self.assertEqual(len(self.chat_calls()), 1)
        payload = self.chat_calls()[0][2]
        self.assertEqual(payload['options'], {'num_predict': 1024, 'num_ctx': 4096, 'temperature': 0.2})
        self.assertIs(payload['think'], False)
        self.assertEqual(payload['keep_alive'], '5m')
        schema = payload['format']
        self.assertEqual(schema['required'], ['assistant_text', 'steps'])
        self.assertFalse(schema['additionalProperties'])
        self.assertEqual(schema['properties']['steps']['minItems'], 1)
        self.assertEqual(schema['properties']['steps']['maxItems'], 4)
        variants = schema['properties']['steps']['items']['anyOf']
        self.assertEqual({v['properties']['workflow_id']['enum'][0] for v in variants}, set(ENTRIES))
        for variant in variants:
            workflow = variant['properties']['workflow_id']['enum'][0]
            controls = variant['properties']['controls']
            self.assertFalse(controls['additionalProperties'])
            for name, spec in self.catalog.controls(workflow).items():
                if name == 'prompt' or spec['kind'] == 'model':
                    self.assertNotIn(name, controls['properties'])
        system = payload['messages'][0]['content']
        self.assertIn('Alle Texte', system)
        self.assertIn('Deutsch', system)
        self.assertNotIn('englische', system)
        for entry in ENTRIES.values():
            self.assertIn(entry[0], system)
        self.assertIn('Quellgesicht', system)
        self.assertNotIn('image_model', system)
        self.assertNotIn('image_encoder', system)
        self.assertNotIn('.safetensors', system)
        self.assertEqual(payload['messages'][-1], {'role': 'user', 'content': 'Tasse blau färben'})
        self.assertFalse(any(call[1] == '/api/generate' for call in self.wire.calls))

    async def test_single_instruction_echo_is_rejected_without_a_retry_in_both_providers(self):
        instruction = 'Färbe die Tasse blau.'
        for copied in [instruction, '  FÄRBE  die Tasse blau.\n']:
            for provider_type, wire_type, instance in [(OllamaProvider, OllamaWire, CHAT_MODEL),
                                                       (LMStudioProvider, Wire, 'chosen-instance')]:
                with self.subTest(provider=provider_type.__name__, copied=copied):
                    wire = wire_type()
                    content = json.dumps(plan(prompt=copied))
                    if isinstance(wire, OllamaWire):
                        wire.chat['message']['content'] = content
                    else:
                        wire.content = content
                    provider = provider_type(None, self.catalog, wire)
                    with self.assertRaises(UiError) as caught:
                        await provider.propose_tools(instance, 'kontext', instruction, {})
                    self.assertEqual(caught.exception.code, 'proposal_echo')
                    self.assertIn('nur wiederholt', caught.exception.message)
                    self.assertEqual(len([c for c in wire.calls
                                          if c[1] in ('/api/chat','/v1/chat/completions')]), 1)

    async def test_finished_prompt_contract_is_sent_without_displacing_the_new_instruction(self):
        await self.propose(instruction='Färbe die Tasse blau.')
        payload = self.chat_calls()[0][2]
        system = payload['messages'][0]['content']
        for expected in ['Fertige Prompts', 'Bildbeschreibung', 'Änderung plus Erhalt',
                         'Bewegung/Kamera', 'Beispiel Edit:', 'Bildausschnitt']:
            self.assertIn(expected, system)
        self.assertEqual(payload['messages'][-1]['content'], 'Färbe die Tasse blau.')

    async def test_negative_text_is_explicit_in_schema_and_never_inherited_when_missing(self):
        for provider_type, wire_type, instance in [(OllamaProvider, OllamaWire, CHAT_MODEL),
                                                   (LMStudioProvider, Wire, 'chosen-instance')]:
            with self.subTest(provider=provider_type.__name__):
                wire = wire_type()
                provider = provider_type(None, self.catalog, wire)
                missing = plan('sdxl', {}, 'Eine blaue Keramiktasse ohne Auto.')
                missing['steps'][0]['controls'].pop('negative', None)
                content = json.dumps(missing)
                if isinstance(wire, OllamaWire):
                    wire.chat['message']['content'] = content
                else:
                    wire.content = content
                with self.assertRaises(UiError) as caught:
                    await provider.propose_tools(instance, 'sdxl', 'Blaue Tasse ohne Auto.',
                                                 {'negative': 'Keine blauen Gegenstände.'})
                self.assertEqual(caught.exception.code, 'proposal_invalid')
                calls = [c for c in wire.calls if c[1] in ('/api/chat','/v1/chat/completions')]
                self.assertEqual(len(calls), 1)
                payload = calls[0][2]
                schema = payload.get('format') or payload['response_format']['json_schema']['schema']
                variants = schema['properties']['steps']['items']['anyOf']
                for variant in variants:
                    workflow = variant['properties']['workflow_id']['enum'][0]
                    required = variant['properties']['controls'].get('required', [])
                    self.assertEqual('negative' in required, workflow in {'sdxl', 'wan', 'qwen21'})

    async def test_explicit_empty_or_new_negative_replaces_old_text(self):
        for negative in ['', 'Unscharf, Wasserzeichen']:
            with self.subTest(negative=negative):
                self.set_plan(plan('sdxl', {'negative': negative}, 'Eine blaue Keramiktasse ohne Auto.'))
                result = await self.propose('sdxl', {'negative': 'Keine blauen Gegenstände.'},
                                            'Blaue Tasse ohne Auto.')
                self.assertEqual(result['steps'][0]['controls']['negative'], negative)

    async def test_unchanged_prompt_for_settings_and_intermediate_steps_remains_valid(self):
        old = 'Eine blaue Keramiktasse auf einem Tisch.'
        self.set_plan(plan('kontext', {'steps': 12}, old))
        result = await self.propose('kontext', {'prompt': old}, 'Nur zwölf Rechenschritte verwenden.')
        self.assertEqual(result['steps'][0]['prompt'], old)
        value = plan('kontext', {}, 'Färbe die Tasse blau.')
        value['steps'].append(plan('wan', {}, 'Die Kamera fährt langsam um die Tasse.')['steps'][0])
        self.set_plan(value)
        self.assertEqual(len((await self.propose(instruction='Färbe die Tasse blau.'))['steps']), 2)

    async def test_current_wan_controls_are_context_and_coupled_validation_base(self):
        self.set_plan(plan('wan', {'steps': 4}, 'Eine ruhige Kamerafahrt.'))
        values = (await self.propose('wan', {'steps': 6, 'split': 2}))['steps'][0]['controls']
        self.assertEqual((values['steps'], values['split']), (4, 2))
        system = self.chat_calls()[0][2]['messages'][0]['content']
        self.assertIn('"steps":6', system)
        self.assertIn('"split":2', system)
        self.set_plan(plan('wan', {'steps': 2}, 'Eine ruhige Kamerafahrt.'))
        with self.assertRaises(UiError):
            await self.propose('wan', {'steps': 6, 'split': 2})

    async def test_other_workflow_uses_its_own_defaults(self):
        self.set_plan(plan('wan', {'steps': 2}, 'Eine ruhige Kamerafahrt.'))
        with self.assertRaises(UiError):
            await self.propose('sdxl', {'steps': 6})

    async def test_same_tool_steps_can_be_adopted_individually_or_in_sequence(self):
        value = plan('wan', {'steps': 4}, 'Eine ruhige Kamerafahrt.')
        value['steps'].append(plan('wan', {'split': 5}, 'Eine zweite Kamerafahrt.')['steps'][0])
        self.set_plan(value)
        result = await self.propose('wan', {'steps': 6, 'split': 2})
        first, second = result['steps']
        self.assertEqual((first['controls'].get('steps'), first['controls'].get('split')), (4, 2))
        self.assertEqual((second['controls'].get('steps'), second['controls'].get('split')), (6, 5))
        for sequence in [(first,), (second,), (first, second), (second, first)]:
            current = {'steps': 6, 'split': 2}
            for step in sequence:
                current.update(step['controls'])
                current['prompt'] = step['prompt']
                self.catalog.validate_controls('wan', current, validate_models=False)

    async def test_whole_request_limit_rejects_combined_text_before_any_provider_request(self):
        for provider, instance in [(self.provider, CHAT_MODEL),
                                   (LMStudioProvider(None, self.catalog, Wire()), 'chosen-instance')]:
            with self.subTest(provider=type(provider).__name__):
                wire = provider.wire
                with self.assertRaises(UiError) as caught:
                    await provider.propose_tools(instance, 'sdxl', 'a' * 4000,
                                                 {'prompt': 'b' * 4000, 'negative': 'c' * 4000})
                self.assertEqual(caught.exception.code, 'proposal_context')
                self.assertEqual(wire.calls, [])

    async def test_request_byte_boundary_counts_schema_and_preserves_text_without_truncation(self):
        lm_wire = Wire()
        lm_wire.content = json.dumps(plan())
        for provider, instance in [(self.provider, CHAT_MODEL),
                                   (LMStudioProvider(None, self.catalog, lm_wire), 'chosen-instance')]:
            with self.subTest(provider=type(provider).__name__):
                wire = provider.wire
                controls = {'prompt': 'Ändere nur die Tasse.'}
                await provider.propose_tools(instance, 'kontext', 'Tasse', controls)
                payload = wire.calls[-1][2]
                size = len(json.dumps(payload).encode('utf-8'))
                self.assertLess(size, 8192)
                instruction = 'Tasse' + 'x' * (8192 - size)
                wire.calls.clear()
                await provider.propose_tools(instance, 'kontext', instruction, controls)
                payload = wire.calls[-1][2]
                self.assertEqual(len(json.dumps(payload).encode('utf-8')), 8192)
                self.assertEqual(payload['messages'][-1]['content'], instruction)
                self.assertIn(controls['prompt'], payload['messages'][1]['content'])
                wire.calls.clear()
                with self.assertRaises(UiError) as caught:
                    await provider.propose_tools(instance, 'kontext', instruction + 'x', controls)
                self.assertEqual(caught.exception.code, 'proposal_context')
                self.assertEqual(wire.calls, [])

    async def test_missing_image_models_do_not_block_proposals(self):
        for path in self.paths.models.rglob('*'):
            if path.is_file():
                path.unlink()
        self.set_plan(plan('qwen21', {'width': 768}, 'Eine rote Tasse auf einem Tisch.'))
        self.assertEqual((await self.propose())['steps'][0]['workflow_id'], 'qwen21')

    async def test_manual_image_model_is_preserved_in_validation_but_hidden_from_llm(self):
        selection = 'diffusion_models/eigene-manuelle-auswahl.safetensors'
        self.catalog.validate_controls = Mock(wraps=self.catalog.validate_controls)
        await self.propose(controls={'image_model': selection})
        validated = self.catalog.validate_controls.call_args_list[-1]
        self.assertEqual(validated.args[1]['image_model'], selection)
        self.assertEqual(validated.kwargs, {'validate_models': False})
        self.assertNotIn(selection, self.chat_calls()[0][2]['messages'][0]['content'])

    async def test_unloaded_and_remote_language_models_are_never_predicted(self):
        for instance, metadata in [('gemma3:4b', {'capabilities': ['completion']}),
                                   (CHAT_MODEL, {'capabilities': ['embedding']}),
                                   (CHAT_MODEL, {'capabilities': ['completion'], 'remote_host': 'https://ollama.com'})]:
            with self.subTest(instance=instance, metadata=metadata):
                self.wire.calls.clear()
                self.wire.show = metadata
                with self.assertRaises(UiError):
                    await self.provider.propose_tools(instance, 'kontext', 'Tasse blau färben', {})
                self.assertEqual(self.chat_calls(), [])
                self.assertFalse(any(call[1] == '/api/generate' for call in self.wire.calls))

    async def test_invalid_instruction_or_context_never_predicts(self):
        cases = [(None, 'kontext', {}), ('', 'kontext', {}), ('x' * 8001, 'kontext', {}),
                 ('Test', [], {}), ('Test', 'unknown', {}), ('Test', 'kontext', []),
                 ('Test', 'kontext', {'width': True}), ('Test', 'kontext', {'command': 'run'})]
        for instruction, workflow, controls in cases:
            with self.subTest(instruction=str(instruction)[:20], workflow=workflow, controls=controls):
                self.wire.calls.clear()
                with self.assertRaises(UiError):
                    method = getattr(self.provider, 'propose_tools', None)
                    self.assertTrue(callable(method), 'Der begrenzte Werkzeugvorschlag fehlt.')
                    await method(CHAT_MODEL, workflow, instruction, controls)
                self.assertEqual(self.wire.calls, [])

    async def test_structural_injections_bad_bounds_types_and_lengths_are_rejected_once(self):
        invalid = [[], {}, plan() | {'command': 'run'}, plan() | {'steps': []},
                   plan() | {'steps': plan()['steps'] * 5}, plan() | {'assistant_text': 'x' * 2001},
                   plan() | {'assistant_text': ''}, plan() | {'steps': 'run'}]
        for updates in [{'workflow_id': 'not-registered'}, {'workflow_id': ['sdxl']},
                        {'workflow_id': '../sdxl'}, {'command': 'run'}, {'path': 'E:/secret'},
                        {'controls': {'shell': 'run'}}, {'controls': {'image_model': 'checkpoints/other.safetensors'}},
                        {'controls': {'prompt': 'Doppelter Text'}}, {'controls': {'width': True}},
                        {'controls': {'width': 17}}, {'controls': {'width': 999999}},
                        {'controls': {'width': 10 ** 400}},
                        {'controls': {'width': '768'}}, {'controls': {'guidance': float('nan')}},
                        {'controls': []}, {'reason': 'x' * 2001}, {'reason': ''},
                        {'prompt': 'x' * 8001}, {'prompt': ''}]:
            value = plan()
            value['steps'][0].update(updates)
            invalid.append(value)
        invalid.append(plan('reactor', {}, 'Nicht leer'))
        invalid.append(plan('reactor', {'source_face': 'x'}, ''))
        invalid.append(plan('reactor', {'source_face': '1' * 65}, ''))
        for value in invalid:
            with self.subTest(value=repr(value)[:130]):
                self.set_plan(value)
                self.wire.calls.clear()
                with self.assertRaises(UiError) as caught:
                    await self.propose()
                self.assertEqual(caught.exception.code, 'proposal_invalid')
                self.assertEqual(len(self.chat_calls()), 1)

    async def test_malformed_or_oversized_json_and_incomplete_envelopes_never_retry(self):
        for text in ['{"steps":', ' ' * 65537, '{"assistant_text":"A","assistant_text":"B","steps":[]}']:
            with self.subTest(text=text[:40]):
                self.wire.chat['message']['content'] = text
                self.wire.calls.clear()
                with self.assertRaises(UiError):
                    await self.propose()
                self.assertEqual(len(self.chat_calls()), 1)
        for patch in [{'done_reason': 'length'}, {'message': {'role': 'user', 'content': '{}'}},
                      {'model': 'foreign:latest'}, {'done': False}]:
            with self.subTest(patch=patch):
                self.wire = OllamaWire()
                self.provider = OllamaProvider(None, self.catalog, self.wire)
                self.set_plan(plan())
                self.wire.chat.update(patch)
                with self.assertRaises(UiError):
                    await self.propose()
                self.assertEqual(len(self.chat_calls()), 1)

    async def test_lmstudio_uses_same_schema_and_german_plan_validation(self):
        wire = Wire()
        wire.content = json.dumps(plan())
        provider = LMStudioProvider(None, self.catalog, wire)
        method = getattr(provider, 'propose_tools', None)
        self.assertTrue(callable(method), 'LM Studio benötigt denselben Vorschlagsvertrag.')
        self.assertEqual(await method('chosen-instance', 'kontext', 'Tasse blau färben', {}),
                         plan(controls={'width': 1024, 'height': 1024, 'seed': 31002,
                                        'steps': 20, 'guidance': 2.5}))
        payload = wire.calls[-1][2]
        self.assertEqual(payload['max_tokens'], 1024)
        self.assertEqual(payload['temperature'], 0.2)
        self.assertEqual(payload['response_format']['json_schema']['schema']['properties']['steps']['maxItems'], 4)
        self.assertIn('Alle Texte', payload['messages'][0]['content'])
        wire.content = json.dumps(plan('unknown'))
        with self.assertRaises(UiError):
            await method('chosen-instance', 'kontext', 'Tasse blau färben', {})

    async def test_lmstudio_rejects_incomplete_malformed_and_non_assistant_envelopes_once(self):
        valid_message = {'role': 'assistant', 'content': json.dumps(plan())}
        responses = [None, [], {}, {'choices': {}}, {'choices': [None]},
                     {'choices': [{'finish_reason': None, 'message': valid_message}]},
                     {'choices': [{'finish_reason': 'length', 'message': valid_message}]},
                     {'choices': [{'finish_reason': 'stop', 'message': {'role': 'user', 'content': json.dumps(plan())}}]},
                     {'choices': [{'finish_reason': 'stop', 'message': []}]},
                     {'choices': [{'finish_reason': 'stop', 'message': valid_message}], 'error': 'failed'}]
        for response in responses:
            with self.subTest(response=response):
                wire = Wire()
                original = wire.request

                async def request(method, path, payload=None):
                    if path == '/v1/chat/completions':
                        wire.calls.append((method, path, copy.deepcopy(payload)))
                        return response
                    return await original(method, path, payload)

                wire.request = request
                provider = LMStudioProvider(None, self.catalog, wire)
                with self.assertRaises(UiError) as caught:
                    await provider.propose_tools('chosen-instance', 'kontext', 'Tasse blau färben', {})
                self.assertEqual(caught.exception.code, 'proposal_invalid')
                self.assertEqual(sum(c[1] == '/v1/chat/completions' for c in wire.calls), 1)

    async def test_legacy_proposals_also_request_german_prompts(self):
        self.set_plan({'assistant_text': 'Die Tasse blau färben.',
                       'prompt': 'Färbe die Tasse blau.', 'controls': {}})
        for provider, instance, wire, content_field in [
                (self.provider, CHAT_MODEL, self.wire, 'chat'),
                (LMStudioProvider(None, self.catalog, Wire()), 'chosen-instance', None, 'content')]:
            if wire is None:
                wire = provider.wire
            await provider.propose(instance, 'kontext', 'Tasse blau färben', self.catalog.controls('kontext'))
            system = wire.calls[-1][2]['messages'][0]['content']
            self.assertIn('prompt auf Deutsch', system)
            self.assertNotIn('englische', system)


class ProposalEndpointTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.paths = ProjectPaths(Sandbox(self).root)
        self.catalog = Catalog(self.paths)
        self.wire = OllamaWire()
        self.wire.chat['message']['content'] = json.dumps(plan('krea2'))
        self.provider = OllamaProvider(None, self.catalog, self.wire)
        self.files = FileStore(self.paths)
        self.compute = Compute(self.paths)
        self.jobs = JobService(self.paths, self.catalog, self.files, self.compute)
        self.client = TestClient(TestServer(create_app(self.paths, self.catalog, self.provider, self.jobs, self.files)))
        await self.client.start_server()
        self.addAsyncCleanup(self.client.close)

    async def test_endpoint_gates_proposal_without_starting_or_submitting_image_work(self):
        response = await self.client.post('/api/tool-proposals', json={
            'instance_id': CHAT_MODEL, 'workflow_id': 'kontext',
            'instruction': 'Tasse blau färben', 'controls': {}}, headers=HEADERS)
        self.assertEqual(response.status, 200)
        self.assertEqual((await response.json())['data'], plan('krea2', {
            'width': 768, 'height': 768, 'seed': 20261015, 'steps': 8, 'cfg': 1.0, 'ref_boost': 1.0}))
        self.assertEqual(self.jobs.list_recent(), [])
        self.assertEqual(self.compute.started, 0)
        self.assertEqual(self.compute.submissions, [])
        self.assertEqual(sum(c[1] == '/api/chat' for c in self.wire.calls), 1)

    async def test_request_structure_rejected_before_provider(self):
        request = {'instance_id': CHAT_MODEL, 'workflow_id': 'kontext', 'instruction': 'Tasse blau färben', 'controls': {}}
        for value in [request | {'command': 'run'}, request | {'images': {'image': '../x'}},
                      {k: v for k, v in request.items() if k != 'workflow_id'}]:
            response = await self.client.post('/api/tool-proposals', json=value, headers=HEADERS)
            self.assertEqual(response.status, 400)
            self.assertEqual(self.wire.calls, [])


if __name__ == '__main__':
    unittest.main()
