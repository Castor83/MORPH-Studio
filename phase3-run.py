import argparse, hashlib, json, os, time, urllib.request
from datetime import datetime, timezone
from pathlib import Path
import psutil
from PIL import Image, ImageStat

ROOT = Path(r'E:\MORPH-Studio')
BASE = 'http://127.0.0.1:8188'
parser = argparse.ArgumentParser()
parser.add_argument('stage', choices=['reference', 'edit'])
args = parser.parse_args()
name = 'Phase3-1-Erwachsenenportraet-SDXL' if args.stage == 'reference' else 'Phase3-1-Identitaet-Kontext'
report_path = ROOT / 'reports' / ('phase3-run-' + args.stage + '.json')
receipt_path = ROOT / 'reports' / ('phase3-receipt-' + args.stage + '.json')
if receipt_path.exists() or report_path.exists():
    raise RuntimeError('Stage already has a receipt or report; no automatic repetition allowed')

def get(path, body=None):
    req = urllib.request.Request(BASE + path, data=None if body is None else json.dumps(body).encode(), headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=15) as response:
        return json.load(response)

def write(path, data, exclusive=False):
    with path.open('x' if exclusive else 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

listeners = [c for c in psutil.net_connections(kind='tcp') if c.status == psutil.CONN_LISTEN and c.laddr.port == 8188]
assert listeners and all(c.laddr.ip == '127.0.0.1' for c in listeners), 'Expected loopback listener missing'
expected = str(ROOT / 'ComfyUI_windows_portable' / 'python_embeded' / 'python.exe').lower()
owners = []
for c in listeners:
    p = psutil.Process(c.pid)
    cmd = p.cmdline()
    assert p.exe().lower() == expected and '--offline' in cmd and 'ComfyUI\\main.py' in cmd, 'Listener is not expected MORPH service'
    for option, value in [('--input-directory', 'input'), ('--output-directory', 'output'), ('--user-directory', 'user'), ('--temp-directory', 'temp/comfyui')]:
        assert Path(cmd[cmd.index(option)+1]).resolve() == (ROOT/value).resolve(), 'Unexpected project path'
    owners.append({'pid': c.pid, 'exe': p.exe(), 'cmdline': cmd})
queue = get('/queue')
assert queue.get('queue_running') == [] and queue.get('queue_pending') == [], 'Queue is not empty; do not submit'
workflow_path = ROOT / 'workflows' / (name + '-api.json')
prompt = json.loads(workflow_path.read_text(encoding='utf-8'))
report = {'stage': args.stage, 'started_at_utc': datetime.now(timezone.utc).isoformat(), 'workflow': str(workflow_path), 'workflow_sha256': digest(workflow_path), 'service_owners': owners, 'queue_before': queue, 'prompt': prompt, 'technical_passed': False}
if args.stage == 'edit':
    gate = json.loads((ROOT/'reports'/'phase3-reference-visual-gate.json').read_text(encoding='utf-8'))
    assert gate['reference_suitable'] is True, 'Reference visual gate not passed'
    reference_path = ROOT/'input'/prompt['4']['inputs']['image']
    assert digest(reference_path) == gate['reference_sha256'], 'Reference changed since visual check'
    report['reference_sha256'] = digest(reference_path)
    report['reference_path'] = str(reference_path)
# Receipt written before POST: interrupted requests must be inspected, never resubmitted automatically.
write(receipt_path, {**report, 'submission_state': 'attempting_once'}, exclusive=True)
start = time.monotonic()
try:
    result = get('/prompt', {'prompt': prompt, 'client_id': 'morph-phase3-' + args.stage})
    report['submission'] = result
    assert not result.get('node_errors') and result.get('prompt_id'), result
    prompt_id = result['prompt_id']
    write(receipt_path, {**report, 'submission_state': 'submitted'})
    print('Submitted ' + args.stage + ': ' + prompt_id, flush=True)
    deadline = time.monotonic() + 1200
    while time.monotonic() < deadline:
        history = get('/history/' + prompt_id)
        if prompt_id in history:
            item = history[prompt_id]
            report['history'] = item
            report['elapsed_seconds'] = time.monotonic() - start
            images = []
            for output in item.get('outputs', {}).get('7' if args.stage == 'reference' else '14', {}).get('images', []):
                assert output['type'] == 'output'
                path = (ROOT/'output'/output['subfolder']/output['filename']).resolve()
                assert path.is_relative_to((ROOT/'output'/'Phase3').resolve()), 'Output outside Phase3'
                with Image.open(path) as im:
                    im.load()
                    assert im.size == (1024,1024) and im.format == 'PNG', 'Unexpected image dimensions or format'
                    stddev = ImageStat.Stat(im.convert('RGB')).stddev
                    assert max(stddev) > 5, 'Blank output'
                    images.append({'path': str(path), 'size': im.size, 'sha256': digest(path), 'stddev': stddev})
            report['images'] = images
            report['technical_passed'] = item['status']['status_str'] == 'success' and item['status']['completed'] and len(images) == 1
            report['queue_after'] = get('/queue')
            write(report_path, report, exclusive=True)
            assert report['technical_passed'], 'Technical run failed; inspect report, no retry'
            print(json.dumps({k:v for k,v in report.items() if k not in ['history', 'prompt']}, indent=2), flush=True)
            break
        time.sleep(2)
    else:
        raise TimeoutError('1200-second deadline; inspect current queue, do not resubmit')
except Exception as error:
    if not report_path.exists():
        report['error'] = repr(error)
        report['elapsed_seconds'] = time.monotonic() - start
        write(report_path, report, exclusive=True)
    raise