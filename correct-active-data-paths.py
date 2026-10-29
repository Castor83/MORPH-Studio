"""Relocate active model destinations and the pause check's project anchor."""
import copy
import hashlib
import json
from pathlib import Path

workspace = Path(__file__).resolve().parent
root = Path(r'E:\MORPH-Studio')
backup = workspace / 'path-correction-backups'
manifest = root / 'reports/phase2-model-manifest.json'
before = manifest.read_bytes()
old_items = json.loads(before)
assert len(old_items) == 5
new_items = copy.deepcopy(old_items)
for item in new_items:
    old = item['destination']
    assert old.startswith('V:\\MORPH-Studio\\')
    item['destination'] = 'E:' + old[2:]
    target = Path(item['destination'])
    assert target.resolve(strict=True).is_relative_to(root)
    assert target.stat().st_size == item['bytes']
replacement = before.replace(b'V:\\\\MORPH-Studio', b'E:\\\\MORPH-Studio')
assert json.loads(replacement) == new_items
saved = backup / 'reports' / manifest.name
saved.parent.mkdir(parents=True, exist_ok=True)
assert not saved.exists()
saved.write_bytes(before)
assert manifest.read_bytes() == before
manifest.write_bytes(replacement)
assert manifest.read_bytes() == replacement

snapshot = root / 'PAUSE_SNAPSHOT.json'
before_snapshot = snapshot.read_bytes()
old_snapshot = json.loads(before_snapshot)
assert old_snapshot['observed']['root'] == r'V:\MORPH-Studio'
old_line = b'    "root": "V:\\\\MORPH-Studio",'
new_line = b'    "root": "E:\\\\MORPH-Studio",'
assert before_snapshot.count(old_line) == 1
new_snapshot_bytes = before_snapshot.replace(old_line, new_line)
expected = copy.deepcopy(old_snapshot)
expected['observed']['root'] = str(root)
assert json.loads(new_snapshot_bytes) == expected
assert (backup / 'pause' / snapshot.name).exists()
assert snapshot.read_bytes() == before_snapshot
snapshot.write_bytes(new_snapshot_bytes)
assert snapshot.read_bytes() == new_snapshot_bytes
result = {
    'manifest': str(manifest),
    'model_destinations_relocated': len(new_items),
    'model_sizes_match': True,
    'manifest_sources_versions_hashes_preserved': True,
    'snapshot': str(snapshot),
    'snapshot_anchor_before': old_snapshot['observed']['root'],
    'snapshot_anchor_after': expected['observed']['root'],
    'other_snapshot_fields_preserved': True,
    'historical_process_paths_preserved': True,
    'reason': 'V project junction no longer visible; check must work without it',
    'backup_directory': str(backup),
    'after_sha256': {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in (manifest, snapshot)}
}
(workspace / 'audit-active-data-path-correction.json').write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding='utf-8')
print(json.dumps(result, ensure_ascii=False))
