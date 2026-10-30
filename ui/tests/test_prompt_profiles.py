"""Prompt-context regressions with synthetic headers and offline provider wires."""
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from morph_ui.catalog import Catalog, ENTRIES
from morph_ui.paths import ProjectPaths, UiError
from morph_ui.providers.ollama import OllamaProvider
from morph_ui.providers.lmstudio import LMStudioProvider
from model_fixtures import write_model
from support import Sandbox
from test_ollama_provider import CHAT_MODEL, OllamaWire
from test_provider import Wire
from test_tool_proposals import plan


class CatalogPromptProfileTests(unittest.TestCase):
    def setUp(self):
        self.paths = ProjectPaths(Sandbox(self).root)
        self.catalog = Catalog(self.paths)
        self.selected = 'checkpoints/private-photo-model.safetensors'
        write_model(self.paths.models / self.selected, 'sd15')

    def test_selected_family_changes_profile_within_the_same_workflow(self):
        default = self.catalog.prompt_profile('sdxl')
        selected = self.catalog.prompt_profile('sdxl', {'image_model': self.selected})
        self.assertIn('SDXL', default)
        self.assertIn('SD 1.5', selected)
        self.assertNotIn('SDXL', selected)
        self.assertNotEqual(default, selected)
        for profile in [default, selected]:
            self.assertNotIn(self.selected, profile)
            self.assertNotIn('.safetensors', profile)
            self.assertNotIn(str(self.paths.root), profile)

    def test_unavailable_or_unknown_selection_does_not_claim_default_family(self):
        unknown = 'checkpoints/unsupported.safetensors'
        write_model(self.paths.models / unknown, 'unknown')
        for selected in ['checkpoints/missing.safetensors', unknown]:
            with self.subTest(selected=selected):
                profile = self.catalog.prompt_profile('sdxl', {'image_model': selected})
                self.assertIn('unbestätigt', profile)
                self.assertNotIn('SDXL', profile)
                self.assertNotIn('SD 1.5', profile)
                self.assertNotIn(selected, profile)


class ProviderPromptProfileTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.paths = ProjectPaths(Sandbox(self).root)
        self.catalog = Catalog(self.paths)
        self.selected = 'checkpoints/private-photo-model.safetensors'
        write_model(self.paths.models / self.selected, 'sd15')

    def providers(self):
        ollama, lmstudio = OllamaWire(), Wire()
        ollama.chat['message']['content'] = lmstudio.content = json.dumps(plan())
        return [(OllamaProvider(None, self.catalog, ollama), CHAT_MODEL),
                (LMStudioProvider(None, self.catalog, lmstudio), 'chosen-instance')]

    def assert_preservation_rule(self, system):
        for word in ['gewünschte Änderungen', 'nicht Genanntes erhalten',
                     'Person', 'Gesicht', 'Pose', 'Haare', 'Hintergrund']:
            self.assertIn(word, system)

    async def test_both_tool_providers_use_selected_profile_and_preserve_visible_text(self):
        controls = {'image_model': self.selected, 'prompt': 'Eine Frau mit roten Haaren.',
                    'negative': 'Unscharf; fremde Person.'}
        instruction = 'Ändere nur die Jacke in Blau.'
        for provider, instance in self.providers():
            with self.subTest(provider=type(provider).__name__):
                await provider.propose_tools(instance, 'sdxl', instruction, controls)
                payload = provider.wire.calls[-1][2]
                system = payload['messages'][0]['content']
                current_row = next(line for line in system.splitlines() if line.startswith('sdxl:'))
                self.assertIn('SD 1.5', current_row)
                self.assertNotIn('SDXL:', current_row)
                context = payload['messages'][1]['content']
                for name in ['prompt', 'negative']:
                    self.assertNotIn(controls[name], system)
                    self.assertIn(controls[name], context)
                self.assertEqual(payload['messages'][-1]['content'], instruction)
                self.assertNotIn(self.selected, json.dumps(payload))
                self.assert_preservation_rule(system)

    async def test_profiles_of_other_tools_use_their_defaults_and_missing_models_remain_optional(self):
        for provider, instance in self.providers():
            with self.subTest(provider=type(provider).__name__):
                await provider.propose_tools(instance, 'kontext', 'Tasse blau.', {})
                system = provider.wire.calls[-1][2]['messages'][0]['content']
                sdxl = next(line for line in system.splitlines() if line.startswith('sdxl:'))
                self.assertIn('SDXL', sdxl)
                self.assertNotIn('SD 1.5', sdxl)
        for path in self.paths.models.rglob('*'):
            if path.is_file():
                path.unlink()
        for provider, instance in self.providers():
            with self.subTest(provider=type(provider).__name__, missing=True):
                await provider.propose_tools(instance, 'kontext', 'Tasse blau.', {})
                system = provider.wire.calls[-1][2]['messages'][0]['content']
                self.assertIn('unbestätigt', system)
                self.assertNotIn('.safetensors', system)

    async def test_every_default_tool_request_keeps_complete_text_inside_existing_byte_limit(self):
        for workflow in ENTRIES:
            for provider, instance in self.providers():
                with self.subTest(workflow=workflow, provider=type(provider).__name__):
                    await provider.propose_tools(instance, workflow, 'Bitte einen Vorschlag.', {})
                    payload = provider.wire.calls[-1][2]
                    self.assertLessEqual(len(json.dumps(payload).encode('utf-8')), 8192)
                    self.assertEqual(payload['messages'][-1]['content'], 'Bitte einen Vorschlag.')
                    visible = self.catalog.validate_controls(workflow, {}, validate_models=False)
                    for name in ['prompt', 'negative']:
                        if name in visible:
                            self.assertIn(visible[name], payload['messages'][1]['content'])

    async def test_native_single_proposal_uses_profile_without_model_paths_or_controls(self):
        wire = OllamaWire()
        provider = OllamaProvider(None, self.catalog, wire)
        allowed = self.catalog.controls('sdxl')
        allowed['image_model']['default'] = self.selected
        allowed['prompt']['default'] = 'Eine Frau mit roten Haaren.'
        allowed['negative']['default'] = 'Unscharf; fremde Person.'
        await provider.propose(CHAT_MODEL, 'sdxl', 'Nur die Jacke blau.', allowed)
        payload = wire.calls[-1][2]
        system = payload['messages'][0]['content']
        self.assertIn('SD 1.5', system)
        self.assertNotIn('SDXL:', system)
        self.assert_preservation_rule(system)
        for name in ['prompt', 'negative']:
            self.assertIn(allowed[name]['default'], system)
        self.assertNotIn(self.selected, json.dumps(payload))
        self.assertNotIn('.safetensors', json.dumps(payload))
        self.assertNotIn('image_model', system)
        self.assertNotIn('image_model', payload['format']['properties']['controls']['properties'])
        self.assertEqual(payload['options']['num_ctx'], 4096)

    async def test_native_single_request_guard_preserves_text_and_rejects_before_io(self):
        wire = OllamaWire()
        provider = OllamaProvider(None, self.catalog, wire)
        allowed = self.catalog.controls('kontext')
        allowed['prompt']['default'] = 'Ein unveränderter Ausgangstext.'
        await provider.propose(CHAT_MODEL, 'kontext', 'Blau', allowed)
        size = len(json.dumps(wire.calls[-1][2]).encode('utf-8'))
        instruction = 'Blau' + 'x' * (8192 - size)
        wire.calls.clear()
        await provider.propose(CHAT_MODEL, 'kontext', instruction, allowed)
        payload = wire.calls[-1][2]
        self.assertEqual(len(json.dumps(payload).encode('utf-8')), 8192)
        self.assertEqual(payload['messages'][-1]['content'], instruction)
        self.assertIn(allowed['prompt']['default'], payload['messages'][0]['content'])
        wire.calls.clear()
        with self.assertRaises(UiError) as caught:
            await provider.propose(CHAT_MODEL, 'kontext', instruction + 'x', allowed)
        self.assertEqual(caught.exception.code, 'proposal_context')
        self.assertEqual(wire.calls, [])


if __name__ == '__main__':
    unittest.main()
