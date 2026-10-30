import argparse, copy, hashlib, json, subprocess, time, urllib.request
from pathlib import Path
import numpy as np
import psutil
from PIL import Image, ImageStat

ROOT=Path(r'E:\MORPH-Studio')
BASE='http://127.0.0.1:8188'
parser=argparse.ArgumentParser()
parser.add_argument('test',choices=['sdxl','kontext','variation'])
args=parser.parse_args()
name='Phase2-1-Fotobild-SDXL' if args.test=='sdxl' else 'Phase2-2-Bildbearbeitung-Kontext'
prompt=json.loads((ROOT/'workflows'/(name+'-api.json')).read_text())
save_id='7' if args.test=='sdxl' else '14'
size=(1024,1024)
if args.test=='variation':
    prompt['7']['inputs']['text']='Change the red ceramic mug to a glossy emerald green ceramic mug. Keep the mug shape, handle, table, window, lighting and composition unchanged. Maintain a realistic photograph.'
    prompt['11']['inputs'].update(width=768,height=768)
    prompt['12']['inputs'].update(seed=84,steps=24)
    prompt['14']['inputs']['filename_prefix']='Phase2/Kontext_Variation'
    size=(768,768)

def request(path,data=None):
    req=urllib.request.Request(BASE+path,data=None if data is None else json.dumps(data).encode(),headers={'Content-Type':'application/json'})
    with urllib.request.urlopen(req,timeout=30) as response: return json.load(response)

server=None
expected=str(ROOT/'ComfyUI_windows_portable'/'python_embeded'/'python.exe').lower()
for process in psutil.process_iter(['pid','exe','cmdline']):
    try:
        if (process.info['exe'] or '').lower()==expected and any('main.py' in value for value in process.info['cmdline'] or []):
            server=process
            break
    except (psutil.AccessDenied,psutil.NoSuchProcess): pass
assert server is not None,'MORPH server not found'
start=time.perf_counter()
result=request('/prompt',{'prompt':prompt,'client_id':'morph-phase2-'+args.test})
assert not result.get('node_errors'),result
pid=result['prompt_id']
print('Test '+args.test+' eingereiht: '+pid,flush=True)
samples=[]
deadline=time.monotonic()+1200
while time.monotonic()<deadline:
    gpu=subprocess.run(['nvidia-smi','--query-gpu=memory.used,utilization.gpu','--format=csv,noheader,nounits'],capture_output=True,text=True,check=True)
    used,util=[int(value.strip()) for value in gpu.stdout.splitlines()[0].split(',')]
    samples.append(dict(seconds=time.perf_counter()-start,gpu_used_mib=used,gpu_util_percent=util,server_rss_bytes=server.memory_info().rss,system_available_ram=psutil.virtual_memory().available))
    history=request('/history/'+pid)
    if pid in history:
        item=history[pid]
        report=dict(test=args.test,prompt_id=pid,elapsed_seconds=time.perf_counter()-start,status=item['status'],history=item,prompt=prompt,samples=samples,peak_gpu_used_mib=max(s['gpu_used_mib'] for s in samples),peak_server_rss_bytes=max(s['server_rss_bytes'] for s in samples),min_system_available_ram=min(s['system_available_ram'] for s in samples))
        outputs=item.get('outputs',{}).get(save_id,{}).get('images',[])
        images=[]
        for output in outputs:
            path=ROOT/'output'/output['subfolder']/output['filename']
            with Image.open(path) as image:
                image.load()
                assert image.size==size,(image.size,size)
                deviation=ImageStat.Stat(image.convert('RGB')).stddev
                assert max(deviation)>5,'Blank output'
                arr=np.asarray(image.convert('RGB'),dtype=np.float32)/255
                blue=((arr[:,:,2]>arr[:,:,0]*1.4)&(arr[:,:,2]>arr[:,:,1]*1.1)&(arr[:,:,2]>.2)).mean()
                green=((arr[:,:,1]>arr[:,:,0]*1.3)&(arr[:,:,1]>arr[:,:,2]*1.15)&(arr[:,:,1]>.2)).mean()
                images.append(dict(path=str(path),size=image.size,stddev=deviation,blue_fraction=float(blue),green_fraction=float(green),sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
        report['images']=images
        report['technical_passed']=item['status']['status_str']=='success' and item['status']['completed'] and bool(images)
        (ROOT/'reports'/('phase2-test-'+args.test+'.json')).write_text(json.dumps(report,indent=2),encoding='utf-8')
        assert report['technical_passed'],item
        print(json.dumps({key:value for key,value in report.items() if key not in ['history','prompt','samples']},indent=2),flush=True)
        break
    time.sleep(1)
else:
    raise TimeoutError('1200-second test limit reached; inspect queue before further action')
