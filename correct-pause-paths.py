"""One-off, byte-preserving correction of current MORPH pause context paths."""
import json
import hashlib
import importlib.util
from pathlib import Path

root = Path(r'E:\MORPH-Studio')
workspace = Path(__file__).resolve().parent
backup = workspace / 'path-correction-backups' / 'pause'
backup.mkdir(parents=True, exist_ok=True)
state = root / 'PAUSE_STATE.md'
snapshot = root / 'PAUSE_SNAPSHOT.json'
old_state = state.read_bytes()
old_snapshot = snapshot.read_bytes()
old_data = json.loads(old_snapshot)
old_root = b'V:\\MORPH-Studio'
new_root = b'E:\\MORPH-Studio'
assert old_state.count(old_root) == 3, 'Pausentext changed; review before editing'
boundary = b'  "observed": {'
assert old_snapshot.count(boundary) == 1
context, observed = old_snapshot.split(boundary, 1)
assert context.count(b'V:\\\\MORPH-Studio') == 3, 'Pause JSON context changed'
new_state = old_state.replace(old_root, new_root)
new_snapshot = context.replace(b'V:\\\\MORPH-Studio', b'E:\\\\MORPH-Studio') + boundary + observed
new_data = json.loads(new_snapshot)
assert old_data['id'] == new_data['id']
assert old_data['observed'] == new_data['observed']
assert old_data['context']['next_step'] == new_data['context']['next_step']
spec = importlib.util.spec_from_file_location('pause_check', root / 'morph_pause.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
before_matches = old_state.decode('utf-8-sig') == module.render(old_data)
after_matches = new_state.decode('utf-8-sig') == module.render(new_data)
assert before_matches == after_matches, 'Pausentext/JSON consistency changed'
for file, original, replacement in [(state, old_state, new_state), (snapshot, old_snapshot, new_snapshot)]:
    saved = backup / file.name
    if saved.exists():
        assert saved.read_bytes() == original, 'Existing backup differs'
    else:
        saved.write_bytes(original)
    assert file.read_bytes() == original, 'Concurrent change detected'
    file.write_bytes(replacement)
    assert file.read_bytes() == replacement
result = {
    'files': [str(state), str(snapshot)],
    'path_replacements_per_file': 3,
    'snapshot_id_preserved': old_data['id'],
    'observed_preserved': True,
    'next_step_preserved': True,
    'text_matches_snapshot_before': before_matches,
    'text_matches_snapshot_after': after_matches,
    'backup_directory': str(backup),
    'after_sha256': {str(f): hashlib.sha256(f.read_bytes()).hexdigest() for f in (state, snapshot)}
}
(workspace / 'audit-pause-path-correction.json').write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding='utf-8')
print(json.dumps(result, ensure_ascii=False))
