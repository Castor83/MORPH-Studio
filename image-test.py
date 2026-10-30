import json, time, urllib.request
from pathlib import Path
root = Path(r'E:\MORPH-Studio')
base = 'http://127.0.0.1:8188'
def request(path, data=None):
    body = None if data is None else json.dumps(data).encode()
    req = urllib.request.Request(base+path, data=body, headers={'Content-Type':'application/json'})
    with urllib.request.urlopen(req, timeout=30) as response:
        return json.load(response)
prompt = {
 '4': {'class_type':'CheckpointLoaderSimple','inputs':{'ckpt_name':'v1-5-pruned-emaonly-fp16.safetensors'}},
 '5': {'class_type':'EmptyLatentImage','inputs':{'width':512,'height':512,'batch_size':1}},
 '6': {'class_type':'CLIPTextEncode','inputs':{'text':'photograph of a red ceramic mug on a wooden table beside a window, warm morning sunlight, detailed, sharp focus','clip':['4',1]}},
 '7': {'class_type':'CLIPTextEncode','inputs':{'text':'blurry, low quality, text, watermark','clip':['4',1]}},
 '3': {'class_type':'KSampler','inputs':{'seed':42,'steps':20,'cfg':7.0,'sampler_name':'euler','scheduler':'normal','denoise':1.0,'model':['4',0],'positive':['6',0],'negative':['7',0],'latent_image':['5',0]}},
 '8': {'class_type':'VAEDecode','inputs':{'samples':['3',0],'vae':['4',2]}},
 '9': {'class_type':'SaveImage','inputs':{'filename_prefix':'MORPH_Phase1_GPU_Test','images':['8',0]}}
}
(root/'workflows'/'phase1-test-api.json').write_text(json.dumps(prompt,indent=2),encoding='utf-8')
start = time.perf_counter()
submitted = request('/prompt',{'prompt':prompt,'client_id':'morph-phase1-test'})
print(json.dumps(submitted),flush=True)
assert not submitted.get('node_errors'), submitted
pid = submitted['prompt_id']
deadline = time.monotonic()+300
while time.monotonic()<deadline:
    history = request('/history/'+pid)
    if pid in history:
        result = history[pid]
        assert result['status']['status_str']=='success', result
        assert result['status']['completed'], result
        images = result['outputs']['9']['images']
        paths = [root/'output'/img['subfolder']/img['filename'] for img in images]
        from PIL import Image, ImageStat
        for path in paths:
            with Image.open(path) as image:
                assert image.size==(512,512)
                assert max(ImageStat.Stat(image.convert('RGB')).stddev)>5, 'Blank output'
                image.verify() if image.mode == 'P' else None
        report = dict(passed=True,elapsed_seconds=time.perf_counter()-start,prompt_id=pid,images=[str(p) for p in paths],history=result,system_stats=request('/system_stats'))
        (root/'reports'/'image-test.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
        print(json.dumps({k:v for k,v in report.items() if k!='history'},indent=2),flush=True)
        break
    time.sleep(1)
else:
    raise TimeoutError('Image test did not finish in 300 seconds')
