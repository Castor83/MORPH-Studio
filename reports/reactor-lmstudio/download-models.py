"""Download only the pinned public models needed by the current ReActor setup."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import time
import uuid
import zipfile

ROOT = Path(r'D:\MORPH-Studio')
MODELS = ROOT / 'ComfyUI_windows_portable/ComfyUI/models'
REPORT = ROOT / 'reports/reactor-lmstudio/models.json'
G = 'https://huggingface.co/datasets/Gourieff/ReActor/resolve/788477a1c8088e664f10a74b95ce65dcdd3c56dc/models/'
N = 'https://huggingface.co/AdamCodd/vit-base-nsfw-detector/resolve/8587de998f441aac03fdd57a85d2e4cb808c7d64/'
items = [
    (G + 'inswapper_128.onnx', MODELS / 'insightface/inswapper_128.onnx', 554253681, 'e4a3f08c753cb72d04e10aa0f7dbe3deebbf39567d4ead6dce08e98aa49e16af'),
    (G + 'buffalo_l.zip', ROOT / 'downloads/reactor/buffalo_l.zip', 288621354, '80ffe37d8a5940d59a7384c201a2a38d4741f2f3c51eef46ebb28218a7b0ca2f'),
    (G + 'facerestore_models/GPEN-BFR-512.onnx', MODELS / 'facerestore_models/GPEN-BFR-512.onnx', 284244491, 'bf80acb8e91ba8852e3f012505be2c3b6cd6b3eed5ec605e3db87863c4e74d4e'),
    (N + 'model.safetensors', MODELS / 'nsfw_detector/vit-base-nsfw-detector/model.safetensors', 344391328, '266efb8bf67c1e865a577222fbbd6ddb149b9e00ba0d2b50466a034837f026a4'),
    (N + 'config.json', MODELS / 'nsfw_detector/vit-base-nsfw-detector/config.json', 715, '604d1da5e3cc8b6dc3f2768a911ed61a44a331cfcee9ecde2ce2cba9a1e7972b'),
    (N + 'preprocessor_config.json', MODELS / 'nsfw_detector/vit-base-nsfw-detector/preprocessor_config.json', 232, 'f2ca775909d2237bd31440280cefcaceb3ac66753c19f7a344e385e68982a9b2'),
]

def file_hash(path):
    with path.open('rb') as source:
        return hashlib.file_digest(source, 'sha256').hexdigest()

def download(item):
    url, target, size, expected = item
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        if target.stat().st_size != size or file_hash(target) != expected:
            raise RuntimeError('Unexpected existing file, left untouched: ' + str(target))
        return {'path': str(target), 'url': url, 'bytes': size, 'sha256': expected, 'reused': True}
    partial = target.with_suffix(target.suffix + '.part-reactor')
    # A fresh unsigned query avoids a stale cached redirect to an expired public signed URL.
    fresh_url = url + '?download=true&reactor_task=' + uuid.uuid4().hex
    print('Downloading ' + target.name, flush=True)
    # Windows curl uses the existing Windows trust store; TLS verification stays enabled.
    command = [r'C:\Windows\System32\curl.exe', '--fail', '--location', '--silent', '--show-error',
               '--connect-timeout', '20', '--max-time', '1800', '--output', str(partial), fresh_url]
    transfer = subprocess.run(command, capture_output=True, text=True, timeout=1810,
                              creationflags=subprocess.CREATE_NO_WINDOW)
    if transfer.returncode:
        raise RuntimeError('Verified HTTPS download failed: ' + target.name + ': ' + transfer.stderr[:800])
    received = partial.stat().st_size
    actual = file_hash(partial)
    if received != size or actual != expected:
        raise RuntimeError('New download failed size/hash check: ' + target.name)
    partial.replace(target)
    print('Verified ' + target.name + ' (' + str(received) + ' bytes)', flush=True)
    return {'path': str(target), 'url': url, 'bytes': received, 'sha256': actual, 'reused': False}

started = datetime.now(timezone.utc).isoformat()
results = []
with ThreadPoolExecutor(max_workers=2) as pool:
    for result in pool.map(download, items):
        results.append(result)
        REPORT.write_text(json.dumps({'startedAt': started, 'complete': False, 'files': results}, indent=2), encoding='utf-8')

archive = ROOT / 'downloads/reactor/buffalo_l.zip'
destination = MODELS / 'insightface/models/buffalo_l'
destination.mkdir(parents=True, exist_ok=True)
required = {'det_10g.onnx', 'w600k_r50.onnx', 'genderage.onnx', '2d106det.onnx', '1k3d68.onnx'}
extracted = []
with zipfile.ZipFile(archive) as zip_file:
    entries = [entry for entry in zip_file.infolist() if not entry.is_dir()]
    if {Path(entry.filename).name for entry in entries} != required:
        raise RuntimeError('Unexpected buffalo_l archive contents; not extracted.')
    for entry in entries:
        target = destination / Path(entry.filename).name
        if target.exists():
            raise RuntimeError('Existing buffalo_l file left untouched: ' + str(target))
        with zip_file.open(entry) as source, target.open('wb') as output:
            shutil.copyfileobj(source, output, 4 * 1024 * 1024)
        extracted.append({'path': str(target), 'bytes': target.stat().st_size})

receipt = {'startedAt': started, 'finishedAt': datetime.now(timezone.utc).isoformat(),
           'complete': True, 'downloadBytes': sum(item[2] for item in items),
           'files': results, 'buffaloExtracted': extracted, 'filtersModified': False}
REPORT.write_text(json.dumps(receipt, indent=2), encoding='utf-8')
print(json.dumps({'complete': True, 'downloadBytes': receipt['downloadBytes'], 'files': len(results)}, indent=2))
