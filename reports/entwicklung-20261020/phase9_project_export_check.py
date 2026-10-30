"""Read-only local project/export/pixel evidence; no model or API mutations."""
import hashlib
import io
import json
import re
import urllib.request
from pathlib import Path
from datetime import datetime, timezone
import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent / 'phase9-live'
class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args):
        raise RuntimeError('Redirect refused')
opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
def get(path):
    with opener.open('http://127.0.0.1:8765' + path, timeout=15) as response:
        data = response.read(64 * 1024**2 + 1)
        assert len(data) <= 64 * 1024**2
        return data, dict(response.headers)

state = json.loads((ROOT / 'acceptance-state.json').read_text(encoding='utf-8'))
project = json.loads(get('/api/image-projects/' + state['project_id'])[0])['data']
assert project['id'] == state['project_id']
(ROOT / 'project-latest.json').write_text(json.dumps(project, ensure_ascii=False, indent=2), encoding='utf-8')
mask = np.asarray(Image.open(state['mask_path']).convert('L')) > 0
images, rows = {}, []
for version in project['versions']:
    media_url = version['media']['url']
    assert re.fullmatch(r'/media/[0-9a-f]{32}', media_url)
    data, headers = get(media_url + '?download=1')
    assert headers.get('Content-Disposition', '').startswith('attachment;')
    assert hashlib.sha256(data).hexdigest() == version['sha256']
    path = ROOT / ('export-' + version['id'] + '.png')
    if path.exists():
        assert path.read_bytes() == data
    else:
        with path.open('xb') as output:
            output.write(data)
    image = np.asarray(Image.open(io.BytesIO(data)).convert('RGB'))
    assert image.shape == (1024, 1024, 3)
    images[version['id']] = image
    rows.append({'id':version['id'], 'parent':version['parent_version_id'],
                 'path':str(path), 'sha256':version['sha256'], 'size':[1024,1024],
                 'status':version['status'], 'independent_download':True})
for row in rows:
    if row['parent']:
        image, parent = images[row['id']], images[row['parent']]
        delta = np.abs(image.astype(np.int16) - parent.astype(np.int16))
        row.update(outside_changed_pixels=int(np.count_nonzero(np.any(delta[~mask]>0,axis=1))),
                   outside_max_delta=int(delta[~mask].max()),
                   inside_changed_pixels=int(np.count_nonzero(np.any(delta[mask]>0,axis=1))),
                   inside_mean_rgb=np.mean(image[mask],axis=0).round(2).tolist())
proof = {'utc':datetime.now(timezone.utc).isoformat(), 'project_id':project['id'],
         'mask_pixels':int(mask.sum()), 'versions':rows}
(ROOT / 'project-export-analysis.json').write_text(json.dumps(proof, indent=2), encoding='utf-8')
print(json.dumps(proof))
