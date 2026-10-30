"""Read-only service evidence plus a consistent pre-migration SQLite backup."""
import asyncio
from contextlib import closing
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import sqlite3
import subprocess
import uuid

import aiohttp

ROOT = Path(r'E:\MORPH-Studio')
REPORT = ROOT / 'reports/entwicklung-20261020'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def database_facts(connection):
    tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    facts = {'integrity': connection.execute('PRAGMA integrity_check').fetchone()[0],
             'tables': sorted(tables), 'rows': {}}
    for table in ('jobs', 'media'):
        if table in tables:
            rows = connection.execute('SELECT * FROM ' + table).fetchall()
            facts['rows'][table] = {
                str(row[0]): hashlib.sha256(json.dumps(row, ensure_ascii=False,
                    sort_keys=True, default=str).encode()).hexdigest() for row in rows}
    facts['counts'] = {key: len(value) for key, value in facts['rows'].items()}
    return facts


async def main():
    now = datetime.now(timezone.utc)
    tag = now.strftime('%Y%m%dT%H%M%SZ') + '-' + uuid.uuid4().hex[:8]
    output = REPORT / ('phase9-preflight-' + tag + '.json')
    backup = REPORT / ('jobs-before-live-' + tag + '.sqlite3')
    result = {'captured_at_utc': now.isoformat(), 'root': str(ROOT),
              'head': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT,
                                             text=True).strip(),
              'free_bytes': shutil.disk_usage(ROOT).free,
              'backup': str(backup), 'services': {}, 'file_hashes': {}}
    for path in (ROOT / 'user/morph-ui/settings.json', ROOT / 'PAUSE_STATE.md',
                 ROOT / 'PAUSE_SNAPSHOT.json'):
        if path.is_file():
            result['file_hashes'][str(path)] = digest(path)
    source = ROOT / 'user/morph-ui/jobs.sqlite3'
    with closing(sqlite3.connect(source.as_uri() + '?mode=ro', uri=True)) as live:
        result['before'] = database_facts(live)
        with backup.open('xb'):
            pass
        with closing(sqlite3.connect(backup)) as saved:
            live.backup(saved)
            result['saved'] = database_facts(saved)
    result['backup_sha256'] = digest(backup)
    result['backup_matches'] = result['before'] == result['saved']
    endpoints = {'ui': 'http://127.0.0.1:8765/api/status',
                 'comfy_stats': 'http://127.0.0.1:8188/system_stats',
                 'comfy_queue': 'http://127.0.0.1:8188/queue',
                 'ollama_ps': 'http://127.0.0.1:11434/api/ps'}
    async with aiohttp.ClientSession(trust_env=False,
            timeout=aiohttp.ClientTimeout(total=4)) as session:
        for name, endpoint in endpoints.items():
            try:
                async with session.get(endpoint, allow_redirects=False) as response:
                    raw = bytearray()
                    async for chunk in response.content.iter_chunked(64 * 1024):
                        raw.extend(chunk)
                        if len(raw) > 1024 * 1024:
                            raise ValueError('oversize')
                    result['services'][name] = {'http_status': response.status,
                                               'data': json.loads(raw)}
            except Exception as error:
                result['services'][name] = {'available': False, 'error_type': type(error).__name__}
    result['gpu_csv'] = subprocess.check_output(['nvidia-smi',
        '--query-gpu=name,memory.total,memory.used,memory.free',
        '--format=csv,noheader,nounits'], text=True).strip()
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'evidence': str(output), 'backup': str(backup),
        'integrity': result['saved']['integrity'], 'counts': result['saved']['counts'],
        'backup_matches': result['backup_matches'], 'services': result['services'],
        'free_bytes': result['free_bytes'], 'gpu_csv': result['gpu_csv']}, ensure_ascii=False))


if __name__ == '__main__':
    asyncio.run(main())
