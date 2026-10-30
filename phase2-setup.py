import json, shutil, urllib.request
from pathlib import Path

ROOT = Path(r'E:\MORPH-Studio')
BASE = 'http://127.0.0.1:8188'

def node(kind, **inputs):
    return {'class_type': kind, 'inputs': inputs}

def build_ui(prompt, name, positions):
    info = {}
    for kind in {v['class_type'] for v in prompt.values()}:
        with urllib.request.urlopen(BASE+'/object_info/'+kind, timeout=30) as response:
            info.update(json.load(response))
    graph, lookup, links = [], {}, []
    for order, (node_id, item) in enumerate(prompt.items()):
        schema = info[item['class_type']]
        inputs, widgets = [], []
        specifications = dict(schema['input'].get('required', {}))
        specifications.update(schema['input'].get('optional', {}))
        for key, spec in specifications.items():
            if key not in item['inputs']:
                continue
            value = item['inputs'][key]
            if isinstance(value, list):
                inputs.append({'name': key, 'type': spec[0], 'link': None})
            else:
                widgets.append(value)
                if item['class_type']=='KSampler' and key=='seed':
                    widgets.append('fixed')
        outputs = [dict(name=n, type=t, links=[]) for n,t in zip(schema['output_name'],schema['output'])]
        title = {'LoadImage':'1 · Eingabebild wählen','CLIPTextEncode':'Text / Bearbeitungsanweisung','EmptySD3LatentImage':'Ausgabegröße','EmptyLatentImage':'Ausgabegröße','KSampler':'Seed · Schritte · Sampling','FluxGuidance':'Anweisungsstärke'}.get(item['class_type'])
        entry = dict(id=int(node_id),type=item['class_type'],pos=positions[node_id],size=[320,240],flags={},order=order,mode=0,inputs=inputs,outputs=outputs,properties={'Node name for S&R':item['class_type']},widgets_values=widgets)
        if title: entry['title']=title
        if item['class_type']=='SaveImage': entry['size']=[400,500]
        graph.append(entry)
        lookup[node_id]=entry
    for node_id,item in prompt.items():
        for slot,inp in enumerate(lookup[node_id]['inputs']):
            source,source_slot=item['inputs'][inp['name']]
            number=len(links)+1
            inp['link']=number
            lookup[source]['outputs'][source_slot]['links'].append(number)
            links.append([number,int(source),source_slot,int(node_id),slot,inp['type']])
    workflow=dict(last_node_id=max(map(int,prompt)),last_link_id=len(links),nodes=graph,links=links,groups=[],config={},extra={'ds':{'scale':0.55,'offset':[20,20]}},version=0.4)
    for directory in [ROOT/'workflows', ROOT/'user'/'default'/'workflows']:
        directory.mkdir(parents=True,exist_ok=True)
        (directory/(name+'.json')).write_text(json.dumps(workflow,indent=2,ensure_ascii=False),encoding='utf-8')
    (ROOT/'workflows'/(name+'-api.json')).write_text(json.dumps(prompt,indent=2),encoding='utf-8')
    return workflow

source=ROOT/'input'/'Phase2-Eingabe-rote-Tasse.png'
if not source.exists():
    shutil.copy2(ROOT/'output'/'MORPH_Phase1_GPU_Test_00001_.png',source)

sdxl={
 '1':node('CheckpointLoaderSimple',ckpt_name='sd_xl_base_1.0.safetensors'),
 '2':node('CLIPTextEncode',clip=['1',1],text='Professional product photograph of a glossy red ceramic mug on a natural oak table beside a large window, soft morning sunlight, realistic reflections and shadows, shallow depth of field, sharp details, no text'),
 '3':node('CLIPTextEncode',clip=['1',1],text='illustration, cartoon, drawing, low quality, blurry, watermark, text, distorted object'),
 '4':node('EmptyLatentImage',width=1024,height=1024,batch_size=1),
 '5':node('KSampler',model=['1',0],positive=['2',0],negative=['3',0],latent_image=['4',0],seed=42,steps=30,cfg=6.5,sampler_name='dpmpp_2m',scheduler='karras',denoise=1.0),
 '6':node('VAEDecode',samples=['5',0],vae=['1',2]),
 '7':node('SaveImage',images=['6',0],filename_prefix='Phase2/SDXL_Fotobild')
}
kontext={
 '1':node('UNETLoader',unet_name='flux1-dev-kontext_fp8_scaled.safetensors',weight_dtype='default'),
 '2':node('DualCLIPLoader',clip_name1='clip_l.safetensors',clip_name2='t5xxl_fp8_e4m3fn_scaled.safetensors',type='flux',device='default'),
 '3':node('VAELoader',vae_name='ae.safetensors'),
 '4':node('LoadImage',image=source.name),
 '5':node('FluxKontextImageScale',image=['4',0]),
 '6':node('VAEEncode',pixels=['5',0],vae=['3',0]),
 '7':node('CLIPTextEncode',clip=['2',0],text='Change the red ceramic mug to a glossy cobalt blue ceramic mug. Keep the shape of the mug, its handle, the camera angle, the window, lighting, wooden table and background unchanged. Maintain a realistic photograph.'),
 '8':node('ReferenceLatent',conditioning=['7',0],latent=['6',0]),
 '9':node('FluxGuidance',conditioning=['8',0],guidance=2.5),
 '10':node('ConditioningZeroOut',conditioning=['7',0]),
 '11':node('EmptySD3LatentImage',width=1024,height=1024,batch_size=1),
 '12':node('KSampler',model=['1',0],positive=['9',0],negative=['10',0],latent_image=['11',0],seed=42,steps=20,cfg=1.0,sampler_name='euler',scheduler='simple',denoise=1.0),
 '13':node('VAEDecode',samples=['12',0],vae=['3',0]),
 '14':node('SaveImage',images=['13',0],filename_prefix='Phase2/Kontext_Edit')
}
build_ui(sdxl,'Phase2-1-Fotobild-SDXL',{'1':[20,250],'2':[380,30],'3':[380,290],'4':[380,550],'5':[740,240],'6':[1100,240],'7':[1460,240]})
build_ui(kontext,'Phase2-2-Bildbearbeitung-Kontext',{'1':[20,30],'2':[20,300],'3':[20,590],'4':[380,30],'5':[740,30],'6':[1100,30],'7':[380,380],'8':[1100,350],'9':[1460,350],'10':[740,650],'11':[1460,30],'12':[1820,240],'13':[2180,240],'14':[2540,240]})
print('Zwei native Phase-2-Workflows und Eingabebild gespeichert.')
