"""Offline size audit of actual saved workflow defaults; never opens a provider socket."""
import asyncio
import json
import sys
from pathlib import Path
from unittest.mock import Mock

PROJECT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(PROJECT / 'ui'), str(PROJECT / 'ui/tests')]
from morph_ui.catalog import Catalog, ENTRIES
from morph_ui.paths import ProjectPaths, UiError
from morph_ui.providers.ollama import OllamaProvider
from morph_ui.providers.lmstudio import LMStudioProvider
from test_ollama_provider import CHAT_MODEL, OllamaWire
from test_provider import Wire
from test_tool_proposals import plan

INSTRUCTION = 'Bitte einen Vorschlag.'
FAMILIES = {'checkpoint': 'sdxl', 'kontext': 'flux', 'wan_high': 'wan',
            'qwen_model': 'qwen_image21', 'krea_model': 'krea2'}


def known_family(model_id, role):
    return {'id': model_id, 'family': FAMILIES.get(role, 'unknown')}


async def audit():
    catalog = Catalog(ProjectPaths(PROJECT))
    # Model fields are excluded from requests. Replace discovery and role
    # resolution with declared fixtures: only the saved workflow JSON is read.
    catalog.model_options = Mock(return_value=[])
    catalog.library.resolve = Mock(side_effect=known_family)
    catalog.wan_low = Mock(return_value={'id': 'diffusion_models/fixture-low.safetensors'})
    rows = []
    for mode in ['known_family_fixture', 'unconfirmed_family_fixture']:
        catalog.library.resolve.side_effect = (known_family if mode == 'known_family_fixture'
                                              else UiError('model_missing', 'Offline fixture missing'))
        for workflow in ENTRIES:
            for provider_name in ['Ollama', 'LM Studio']:
                wire = OllamaWire() if provider_name == 'Ollama' else Wire()
                content = json.dumps(plan())
                if provider_name == 'Ollama':
                    wire.chat['message']['content'] = content
                    provider, instance = OllamaProvider(None, catalog, wire), CHAT_MODEL
                else:
                    wire.content = content
                    provider, instance = LMStudioProvider(None, catalog, wire), 'chosen-instance'
                await provider.propose_tools(instance, workflow, INSTRUCTION, {})
                payload = wire.calls[-1][2]
                size = len(json.dumps(payload).encode('utf-8'))
                assert size <= 8192
                rows.append({'workflow': workflow, 'entrypoint': 'tool_plan',
                             'provider': provider_name, 'profile_source': mode,
                             'serialized_request_bytes': size, 'remaining_bytes': 8192 - size})
            if mode == 'known_family_fixture':
                wire = OllamaWire()
                wire.chat['message']['content'] = json.dumps({
                    'assistant_text': 'Ein prüfbarer Vorschlag.',
                    'prompt': '' if workflow == 'reactor' else 'Eine rote Tasse.', 'controls': {}})
                provider = OllamaProvider(None, catalog, wire)
                await provider.propose(CHAT_MODEL, workflow, INSTRUCTION, catalog.controls(workflow))
                size = len(json.dumps(wire.calls[-1][2]).encode('utf-8'))
                assert size <= 8192
                rows.append({'workflow': workflow, 'entrypoint': 'single_proposal',
                             'provider': 'Ollama', 'profile_source': mode,
                             'serialized_request_bytes': size, 'remaining_bytes': 8192 - size})
    return {'size_limit_bytes': 8192, 'token_context': 4096, 'tokenizer_guarantee': False,
            'instruction': INSTRUCTION,
            'scope': 'Actual saved workflow defaults; declared known/unconfirmed family fixtures; '
                     'no model discovery, weights, services, network or inference.',
            'rows': rows}


if __name__ == '__main__':
    result = asyncio.run(audit())
    output = Path(__file__).with_name('phase6-request-sizes.json')
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(result, ensure_ascii=True, indent=2))
