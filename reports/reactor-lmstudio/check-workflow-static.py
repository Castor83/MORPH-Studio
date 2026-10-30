import ast
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

root = Path('D:/MORPH-Studio')
reports = root / 'reports/reactor-lmstudio'
def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))
def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

ui_path = root / 'workflows/LMStudio-Gesichtstausch-ReActor.json'
api_path = root / 'workflows/LMStudio-Gesichtstausch-ReActor-api.json'
ui, api = read(ui_path), read(api_path)
source_path = root / 'tools/reactor-source/nodes.py'
module = ast.parse(source_path.read_text(encoding='utf-8-sig'))
reactor = next(n for n in module.body if isinstance(n, ast.ClassDef) and n.name == 'reactor')
input_types = next(n for n in reactor.body if isinstance(n, ast.FunctionDef) and n.name == 'INPUT_TYPES')
returned = next(n.value for n in ast.walk(input_types) if isinstance(n, ast.Return))
groups = {ast.literal_eval(k): v for k, v in zip(returned.keys, returned.values)}
field_defs = {
    group: {ast.literal_eval(k): v for k, v in zip(value.keys, value.values)}
    for group, value in groups.items()
}
required, optional = field_defs['required'], field_defs['optional']
swap = api['3']['inputs']
assert set(required) <= set(swap), 'Missing source-defined required fields'
assert set(swap) <= set(required) | set(optional), 'Unexpected ReActor input field'
assert swap['input_image'] == ['1', 0] and swap['source_image'] == ['2', 0]
assert swap['swap_model'] == 'inswapper_128.onnx' and swap['face_restore_model'] == 'none'
assert swap['input_faces_index'] == swap['source_faces_index'] == '0'
assert api['1']['inputs']['image'] == api['2']['inputs']['image'] == ''
assert api['4']['inputs'] == {'images': ['3', 0], 'filename_prefix': 'LMStudio/Gesichtstausch'}
widget_keys = [key for key, value in required.items()
               if not (isinstance(value.elts[0], ast.Constant) and value.elts[0].value == 'IMAGE')]
swap_ui = next(n for n in ui['nodes'] if n['id'] == 3)
assert swap_ui['widgets_values'] == [swap[key] for key in widget_keys], 'UI widget order differs from source'
for key, definition in required.items():
    first = definition.elts[0]
    if isinstance(first, ast.List):
        assert swap[key] in ast.literal_eval(first), f'Literal source enum invalid: {key}'
    if isinstance(first, ast.Constant):
        kind = first.value
        if kind == 'BOOLEAN':
            assert isinstance(swap[key], bool)
        elif kind == 'STRING':
            assert isinstance(swap[key], str)
        elif kind in ('FLOAT', 'INT'):
            assert isinstance(swap[key], (int, float)) and not isinstance(swap[key], bool)
            ranges = ast.literal_eval(definition.elts[1])
            assert ranges.get('min', float('-inf')) <= swap[key] <= ranges.get('max', float('inf'))
nodes = {node['id']: node for node in ui['nodes']}
assert len(nodes) == len(api) == 4
assert {n['type'] for n in ui['nodes']} == {'LoadImage', 'ReActorFaceSwap', 'SaveImage'}
for link_id, src, src_slot, dst, dst_slot, kind in ui['links']:
    assert nodes[src]['outputs'][src_slot]['type'] == nodes[dst]['inputs'][dst_slot]['type'] == kind
    assert link_id in nodes[src]['outputs'][src_slot]['links']
    assert nodes[dst]['inputs'][dst_slot]['link'] == link_id
    assert api[str(dst)]['inputs'][nodes[dst]['inputs'][dst_slot]['name']] == [str(src), src_slot]
assert all(n['widgets_values'][0] == '' for n in ui['nodes'] if n['type'] == 'LoadImage')
assert len(ui['links']) == 3
preset_path = Path('V:/LMStudio/.lmstudio/config-presets/morph-wan-video.preset.json')
preset = read(preset_path)
before = read(reports / 'preset-before-face-route.json')
for name in ('identifier', 'name', 'changed', 'load'):
    assert preset[name] == before[name]
field = next(f['value'] for f in preset['operation']['fields'] if f['key'] == 'llm.prediction.systemPrompt')
for required_text in ['Zielfoto', 'Quellbild', 'anhand seines path',
                      'LMStudio-Gesichtstausch-ReActor-api.json', '"1.image"', '"2.image"',
                      '"3.input_faces_index"', '"3.source_faces_index"', 'kein video ohne',
                      'keinen direkten Gesichtstausch', 'Bei Lauf-/Werkzeugfehlern']:
    assert required_text.casefold() in field.casefold(), f'Preset route missing {required_text}'
assert 'hat derzeit keinen installierten Workflow' not in field
provenance = read(reports / 'workflow-source.json')
assert sha(provenance['path']) == provenance['sha256'] and provenance['bytes'] == 7732
assert sha(ui_path) == provenance['adaptation']['uiSha256']
assert sha(api_path) == provenance['adaptation']['apiSha256']
guide_path = root / 'LMStudio-Wan-Bedienung.md'
guide = guide_path.read_text(encoding='utf-8-sig')
assert 'noch nicht eingerichtet**' not in guide
assert 'zwei Bilder anhängen' in guide and '**Zielfoto**' in guide and '**Quellbild**' in guide
assert 'Die bisherigen Kontext- und Wan-Abläufe' in guide
report = {
    'at': datetime.now(timezone.utc).isoformat(),
    'mode': 'static-source-and-saved-graph-check-no-import-no-render',
    'success': True,
    'workflow': {
        'uiPath': str(ui_path), 'apiPath': str(api_path), 'nodes': 4, 'links': 3,
        'imageRoles': {'1': 'target', '2': 'source'}, 'imageDefaultsEmpty': True,
        'allRequiredReactorInputsPresent': True, 'literalTypesEnumsRangesMatchSource': True,
        'uiWidgetOrderMatchesSource': True, 'uiApiLinksMatch': True,
        'noImpactOrBlendedIdentityNodes': True, 'restoreModel': 'none',
        'faceIndices': ['0', '0'], 'outputPrefix': 'LMStudio/Gesichtstausch',
    },
    'preset': {
        'path': str(preset_path), 'twoRolesRequired': True,
        'uploadResultsMappedByOriginalPath': True, 'existingOtherPresetFieldsPreserved': True,
        'combinedFaceSwapThenVideoRequiresExplicitRequest': True,
        'directVideoFaceSwapNotPromised': True, 'sha256': sha(preset_path),
    },
    'guide': {'path': str(guide_path), 'newRegistrationAndRenderUnverified': True,
              'sha256': sha(guide_path)},
    'sourceReceipt': 'workflow-source.json',
    'notVerified': ['Live ReActor registration and model dropdowns',
                    'Actual face-swap render and visual quality',
                    'Normal LM Studio chat model decisions'],
}
(reports / 'workflow-graph-check.json').write_text(
    json.dumps(report, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
print(json.dumps(report, indent=2, ensure_ascii=False))
