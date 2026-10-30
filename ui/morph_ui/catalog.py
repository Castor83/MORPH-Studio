import copy
import json
import math
import re
from pathlib import Path
from .paths import UiError
from .model_library import ModelLibrary
from .edit_region import composite_graph

ENTRIES = {
    'sdxl': ('Bild erstellen', 'Ein neues Bild aus einer Beschreibung erzeugen.', 'Phase2-1-Fotobild-SDXL-api.json', {}),
    'kontext': ('Bild bearbeiten', 'Ein vorhandenes Bild mit einer gezielten Anweisung verändern.', 'LMStudio-Bildbearbeitung-Kontext-api.json', {'image':'Ausgangsbild'}),
    'reactor': ('Gesichtstausch', 'Das Quellgesicht in das gewählte Zielfoto einsetzen.', 'LMStudio-Gesichtstausch-ReActor-api.json', {'target':'Zielfoto', 'source':'Quellgesicht'}),
    'wan': ('Bild zu Video', 'Aus einem Bild einen kurzen Clip mit Bewegung erzeugen.', 'LMStudio-Video-aus-Bild-Wan-api.json', {'image':'Ausgangsbild'}),
    'qwen21': ('Bild mit Qwen erstellen', 'Ein neues Bild mit Qwen Image 2.1 / Noct Q erzeugen.', 'MORPH-Qwen-Image-21-api.json', {}),
    'krea2': ('Bild mit KREA 2 bearbeiten', 'Ein vorhandenes Bild mit KREA 2 Edit SNOFS Merge Q5 gezielt verändern.', 'KREA2-SNOFS-Edit-20261015-api.json', {'image':'Ausgangsbild'}),
}
IMAGE_NODES = {'sdxl':{}, 'kontext':{'image':'4'}, 'reactor':{'target':'1','source':'2'}, 'wan':{'image':'252'}, 'qwen21':{}, 'krea2':{'image':'72'}}
SELECTORS = {'ckpt_name':'checkpoints','unet_name':'diffusion_models','clip_name':'text_encoders','clip_name1':'text_encoders','clip_name2':'text_encoders','vae_name':'vae','swap_model':'insightface','model_name':'upscale_models'}
MODEL_FIELDS = {
    'sdxl': {'image_model':('Bildmodell', 'checkpoint', 'checkpoints', '1','ckpt_name',False)},
    'kontext': {'image_model':('Bildmodell · Kontext', 'kontext', 'diffusion_models', '1','unet_name',False)},
    'wan': {'image_model':('Videomodell · High/Low-Paar', 'wan_high', 'diffusion_models', '135','unet_name',False)},
    'qwen21': {'image_model':('Bildmodell · Qwen Image 2.1', 'qwen_model','diffusion_models','1','unet_name',False), 'image_encoder':('Qwen-Textencoder','qwen_encoder','text_encoders','2','clip_name',True), 'image_vae':('Qwen-Bilddecoder (VAE)','qwen_vae','vae','3','vae_name',True)},
    'krea2': {'image_model':('Bildmodell · KREA 2 GGUF','krea_model','diffusion_models','55','unet_name',False), 'image_encoder':('KREA-Textencoder · Qwen3-VL 4B','krea_encoder','text_encoders','56','clip_name',True)},
}
FAMILY_NAMES = {'sdxl':'SDXL', 'sd15':'SD 1.5', 'flux':'FLUX Kontext', 'wan':'Wan 2.2', 'qwen_image21':'Qwen Image 2.1', 'qwen3_vl8b':'Qwen3-VL 8B', 'qwen_image21_vae':'Qwen Image 2.1 VAE', 'krea2':'KREA 2', 'qwen3_vl4b':'Qwen3-VL 4B'}
PROMPT_PROFILES = {
    'sd15': 'SD 1.5: kurze Motiv-/Stilbegriffe',
    'sdxl': 'SDXL: Motiv, Komposition, Licht',
    'flux': 'FLUX Kontext: gezielte Bildänderung',
    'wan': 'Wan 2.2: Bewegung, Kamera; Bild erhalten',
    'qwen_image21': 'Qwen Image 2.1: Motiv; negativ nur cfg>1',
    'krea2': 'KREA 2: gezielte Referenzbildänderung',
}
UNKNOWN_PROMPT_PROFILE = 'Familie unbestätigt; keine Modellannahmen'
GERMAN_TEXT_DEFAULTS = {
    'sdxl': {'prompt': 'Fotorealistisches Foto einer roten Keramiktasse auf einem Holztisch. Natürliches Licht, klare Details.',
             'negative': 'Unscharf, geringe Qualität, verzerrte Formen, Schrift, Wasserzeichen'},
    'kontext': {'prompt': 'Färbe ausschließlich die Tasse blau. Form, Hintergrund, Beleuchtung und Bildausschnitt sollen erhalten bleiben.'},
    'wan': {'prompt': 'Dezente natürliche Bewegung. Erhalte Personen, Tiere, Kleidung und Hintergrund des Ausgangsbildes. Die Kamera bleibt ruhig.',
            'negative': 'Unscharf, geringe Qualität, verzerrte Gesichter und Hände, zusätzliche Finger oder Gliedmaßen, Flackern, abrupte Kamerabewegung, Schrift, Wasserzeichen'},
    'qwen21': {'prompt': 'Fotorealistisches Foto einer roten Keramiktasse auf einem Holztisch. Natürliches Licht, klare Details.',
               'negative': 'Unscharf, geringe Qualität, verzerrte Formen, Schrift, Wasserzeichen'},
    'krea2': {'prompt': 'Ändere nur das rote Hemd in Dunkelblau. Erhalte Gesicht, Haare, Körperhaltung, Haut, Hintergrund, Beleuchtung und Bildausschnitt.'},
}

class Catalog:
    def __init__(self, paths):
        self.paths = paths
        self.library = ModelLibrary(paths)

    def model_options(self, role, directory):
        result = []
        for item in self.library.choices(role):
            if not item['id'].startswith(directory + '/'):
                continue
            note = ''
            if role == 'wan_high':
                try:
                    low = self.wan_low(item['id'])
                    note = 'Zusammengehöriges High-/Low-Paar: ' + low['name']
                except UiError:
                    continue
            option = dict(item, label=FAMILY_NAMES.get(item['family'], item['family']) + ' · ' + item['name'], note=note)
            if item['family'] in ['sdxl','sd15']:
                option['recommended_size'] = 512 if item['family'] == 'sd15' else 1024
            result.append(option)
        return result

    def wan_low(self, model_id):
        candidates = self.library.choices('wan_low')
        parent, separator, name = model_id.rpartition('/')
        paired = parent + separator + re.sub(r'(?i)(?<![a-z])high(?![a-z])', 'low', name)
        matches = [item for item in candidates if item['id'].casefold() == paired.casefold()]
        if len(matches) != 1:
            raise UiError('model_pair', 'Für dieses Videomodell fehlt das zugehörige Low-Modell.', model_id)
        return self.library.resolve(matches[0]['id'], 'wan_low')

    def graph(self, workflow_id):
        if workflow_id not in ENTRIES:
            raise UiError('workflow', 'Bitte einen vorhandenen Workflow auswählen.')
        path = self.paths.inside(self.paths.workflows, ENTRIES[workflow_id][2], True)
        try:
            graph = json.loads(path.read_text(encoding='utf-8-sig'))
            if not isinstance(graph, dict) or not all(isinstance(v, dict) and isinstance(v.get('inputs'), dict) and isinstance(v.get('class_type'), str) for v in graph.values()):
                raise ValueError('No API graph')
            return graph
        except (ValueError, OSError) as error:
            raise UiError('workflow_file', 'Die Workflow-Vorlage ist nicht lesbar.', str(path)) from error

    def controls(self, workflow_id):
        graph = self.graph(workflow_id)
        fields = {}
        for name,(label,role,directory,node,key,advanced) in MODEL_FIELDS.get(workflow_id,{}).items():
            fields[name] = {'label':label,'kind':'model','default':directory + '/' + graph[node]['inputs'][key].replace('\\','/'),'node':node,'input':key,'role':role,'directory':directory,'advanced':advanced,'options':self.model_options(role,directory)}
        def field(name, label, node, key, kind='integer', minimum=None, maximum=None, step=None, advanced=False, default=None):
            try:
                value = graph[node]['inputs'][key] if default is None else default
            except KeyError as error:
                raise UiError('workflow_node', f'Der Workflow benötigt Knoten {node} mit Feld {key}.') from error
            value = GERMAN_TEXT_DEFAULTS.get(workflow_id, {}).get(name, value)
            fields[name] = {'label':label,'kind':kind,'default':value,'node':node,'input':key,'advanced':advanced}
            if minimum is not None:
                fields[name].update(min=minimum, max=maximum, step=step)
        if workflow_id == 'reactor':
            field('target_face','Gesicht im Zielfoto (ab 0)','3','input_faces_index','faces',advanced=True)
            field('source_face','Quellgesicht (ab 0)','3','source_faces_index','faces',advanced=True)
            return fields
        prompt_node = {'sdxl':'2','kontext':'7','wan':'6','qwen21':'6','krea2':'84'}[workflow_id]
        field('prompt','Bildbeschreibung / Anweisung (Deutsch)',prompt_node,'prompt' if workflow_id in ['qwen21','krea2'] else 'text','text')
        if workflow_id in ['sdxl','wan','qwen21']:
            field('negative','Unerwünschte Inhalte' + (' · wirkt erst bei Textstärke über 1' if workflow_id == 'qwen21' else ''), '6' if workflow_id == 'qwen21' else '3' if workflow_id == 'sdxl' else '7','negative_prompt' if workflow_id == 'qwen21' else 'text','text',advanced=True)
        size_node = {'sdxl':'4','kontext':'11','wan':'131','qwen21':'4','krea2':'82'}[workflow_id]
        size_max = 4096 if workflow_id == 'wan' else 16384
        size_step = 8 if workflow_id == 'sdxl' else 16
        field('width','Breite',size_node,'value' if workflow_id == 'wan' else 'width',minimum=16,maximum=size_max,step=size_step)
        field('height','Höhe','130' if workflow_id == 'wan' else size_node,'value' if workflow_id == 'wan' else 'height',minimum=16,maximum=size_max,step=size_step)
        sampler = {'sdxl':'5','kontext':'12','wan':'105','qwen21':'5','krea2':'53'}[workflow_id]
        field('seed','Zufallsstartwert (Seed)',sampler,'seed',minimum=0,maximum=2**50,step=1,advanced=True)
        field('steps','Berechnungsschritte','68' if workflow_id == 'wan' else sampler,'value' if workflow_id == 'wan' else 'steps',minimum=1,maximum=10000,step=1,advanced=True)
        if workflow_id in ['sdxl','krea2']:
            field('cfg','Textstärke',sampler,'cfg','number',0,100,0.1,True)
        if workflow_id == 'krea2':
            field('ref_boost','Referenzstärke · Ausgangswert 1','79','ref_boost','number',0,1000,0.01,True)
        if workflow_id == 'qwen21':
            field('cfg','Textstärke · empfohlen 1','5','cfg','number',1,2,0.1,True)
        if workflow_id == 'kontext':
            field('guidance','Anweisungsstärke','9','guidance','number',0,100,0.1,True)
        if workflow_id == 'wan':
            field('frames','Anzahl Videobilder (4n + 1)','132','value',minimum=1,maximum=4093,step=4)
            field('split','Wechsel zwischen den Videomodellen','67','value',minimum=1,maximum=9999,step=1,advanced=True)
            field('motion','Bewegungsstärke','255','motion_amplitude','number',1,2,0.05,True)
            field('base_fps','Basis-Bildrate','226','frame_rate','number',1,120,0.1,True)
            field('output_fps','Ausgabe-Bildrate','253','target_fps','number',1,240,0.1,True)
        return fields

    def proposal_entries(self):
        return [{'id': key, 'name': entry[0], 'description': entry[1],
                 'roles': [{'id': name, 'label': label} for name, label in entry[3].items()],
                 'controls': {name: spec for name, spec in self.controls(key).items()
                              if spec['kind'] != 'model'}}
                for key, entry in ENTRIES.items()]

    def prompt_profile(self, workflow_id, controls=None):
        """Read-only family guidance; never disclose model IDs or require readiness."""
        if workflow_id not in ENTRIES:
            raise UiError('workflow', 'Bitte einen vorhandenen Workflow auswählen.')
        if workflow_id == 'reactor':
            return 'Gesichtstausch: nur Gesichtsnummern'
        _, role, directory, node, key, _ = MODEL_FIELDS[workflow_id]['image_model']
        selected = (controls or {}).get('image_model')
        if selected is None:
            selected = directory + '/' + self.graph(workflow_id)[node]['inputs'][key].replace('\\', '/')
        try:
            model = self.library.resolve(selected, role)
        except UiError:
            # Missing or unconfirmed selections are prerequisites, not grounds
            # to block the optional assistant or silently assume another model.
            return UNKNOWN_PROMPT_PROFILE
        return PROMPT_PROFILES.get(model['family'], UNKNOWN_PROMPT_PROFILE)

    def validate_controls(self, workflow_id, controls, *, validate_models=True):
        if not isinstance(controls, dict):
            raise UiError('controls', 'Die Einstellungen müssen benannte Felder enthalten.')
        fields = self.controls(workflow_id)
        if set(controls) - set(fields):
            raise UiError('controls', 'Der Vorschlag enthält eine nicht erlaubte Einstellung.', sorted(set(controls) - set(fields)))
        values = {name: spec['default'] for name, spec in fields.items()}
        values.update(controls)
        for name, value in values.items():
            spec = fields[name]
            if spec['kind'] == 'model':
                if (not isinstance(value, str) or not value.startswith(spec['directory'] + '/')
                        or '\\' in value or ':' in value or '\x00' in value
                        or any(part in ['', '.', '..'] for part in value.split('/'))):
                    raise UiError('model_selection', 'Bitte ein Modell aus dem passenden Projektordner auswählen.', value)
                if validate_models:
                    self.library.resolve(value, spec['role'])
                    if spec['role'] == 'wan_high':
                        self.wan_low(value)
            elif spec['kind'] in ['text','faces']:
                if not isinstance(value, str) or len(value) > 8000 or (name == 'prompt' and not value.strip()):
                    raise UiError('controls', f'Bitte einen gültigen Text für „{spec["label"]}“ eingeben.')
                if spec['kind'] == 'faces' and (len(value) > 64 or not re.fullmatch(r'\d+(?:\s*,\s*\d+)*', value)):
                    raise UiError('controls', 'Gesichtsnummern als 0 oder 0,1 eingeben.')
            else:
                valid_type = type(value) is int if spec['kind'] == 'integer' else type(value) in [int,float]
                if not valid_type or not spec['min'] <= value <= spec['max'] or not math.isfinite(value):
                    raise UiError('controls', f'„{spec["label"]}“ muss zwischen {spec["min"]} und {spec["max"]} liegen.')
                if abs((value - spec['min']) / spec['step'] - round((value - spec['min']) / spec['step'])) > 1e-6:
                    raise UiError('controls', f'„{spec["label"]}“ benötigt Schritte von {spec["step"]}.')
        if workflow_id == 'wan' and not values['split'] < values['steps']:
            raise UiError('controls', 'Der Modellwechsel muss vor dem letzten Berechnungsschritt liegen.')
        return values

    def prepared_graph(self, workflow_id, controls):
        values = self.validate_controls(workflow_id, controls)
        graph = copy.deepcopy(self.graph(workflow_id))
        for name,spec in self.controls(workflow_id).items():
            value = values[name]
            if spec['kind'] == 'model':
                value = str(Path(value).relative_to(spec['directory']))
            graph[spec['node']]['inputs'][spec['input']] = value
        if workflow_id == 'wan':
            low = self.wan_low(values['image_model'])
            graph['136']['inputs']['unet_name'] = str(Path(low['id']).relative_to('diffusion_models'))
            graph['253']['inputs']['source_fps'] = values['base_fps']
            graph['254']['inputs']['frame_rate'] = values['output_fps']
            graph['256']['inputs']['frame_rate'] = values['output_fps']
        if workflow_id == 'krea2':
            graph['29']['inputs']['filename_prefix'] = 'MORPH-UI/Krea2'
        return graph

    def readiness(self, workflow_id, controls=None):
        try:
            graph = self.prepared_graph(workflow_id, controls or {})
        except UiError as error:
            return [{'code':error.code,'message':error.message,'path':str(self.paths.models / error.details) if isinstance(error.details,str) and not Path(error.details).is_absolute() and '..' not in Path(error.details).parts else error.details}]
        expected = []
        for node in graph.values():
            for field, directory in SELECTORS.items():
                value = node['inputs'].get(field)
                if isinstance(value, str) and value.endswith(('.safetensors','.onnx','.pth','.ckpt','.gguf')):
                    expected.append((self.paths.models, directory + '/' + value))
        if workflow_id == 'reactor':
            expected.extend((self.paths.models, 'insightface/models/buffalo_l/' + n) for n in ['1k3d68.onnx','2d106det.onnx','det_10g.onnx','genderage.onnx','w600k_r50.onnx'])
        if workflow_id == 'wan':
            expected.append((self.paths.root, 'ComfyUI_windows_portable/ComfyUI/custom_nodes/ComfyUI-VFI/rife/train_log/flownet.pkl'))
        issues = []
        for base, relative in expected:
            path = base / relative
            try:
                path = self.paths.inside(base, relative, True)
                if not path.is_file() or path.stat().st_size == 0:
                    raise OSError('Empty/missing model')
            except (UiError, OSError):
                issues.append({'code':'model_file','message':'Benötigte Modelldatei nicht verfügbar: ' + PathName(relative),'path':str(path)})
        return issues

    def dependencies(self, workflow_id, controls=None):
        """Describe selected loader inputs without opening weights or starting ComfyUI."""
        try:
            values = self.validate_controls(workflow_id, controls or {}, validate_models=False)
            graph = copy.deepcopy(self.graph(workflow_id))
            for name, spec in self.controls(workflow_id).items():
                if spec['kind'] == 'model':
                    graph[spec['node']]['inputs'][spec['input']] = str(Path(values[name]).relative_to(spec['directory']))
            if workflow_id == 'wan':
                parent, _, name = values['image_model'].rpartition('/')
                paired = parent + '/' + re.sub(r'(?i)(?<![a-z])high(?![a-z])', 'low', name)
                graph['136']['inputs']['unet_name'] = str(Path(paired).relative_to('diffusion_models'))
        except UiError:
            return []
        result = []
        roles = {'ckpt_name':'Bildmodell mit Textencoder und VAE', 'unet_name':'Bild-/Videomodell',
                 'clip_name':'Textencoder', 'clip_name1':'Textencoder', 'clip_name2':'Textencoder',
                 'vae_name':'Bilddecoder (VAE)', 'swap_model':'Gesichtstausch', 'model_name':'Vergrößerung'}
        for node_id, node in graph.items():
            for field, directory in SELECTORS.items():
                value = node['inputs'].get(field)
                if not isinstance(value, str) or not value.endswith(('.safetensors','.onnx','.pth','.ckpt','.gguf','.pkl')):
                    continue
                base, relative, role = self.paths.models, directory + '/' + value.replace('\\','/'), roles[field]
                if node['class_type'] == 'RIFEInterpolation' and field == 'model_name':
                    base = self.paths.root
                    relative = 'ComfyUI_windows_portable/ComfyUI/custom_nodes/ComfyUI-VFI/rife/train_log/' + value
                    role = 'Zwischenbildberechnung'
                try:
                    path = self.paths.inside(base, relative)
                except UiError:
                    continue
                result.append({'name':PathName(value),'path':str(path),'role':role,'loader':node['class_type'],'node':node_id})
        if workflow_id == 'reactor':
            for name in ['1k3d68.onnx','2d106det.onnx','det_10g.onnx','genderage.onnx','w600k_r50.onnx']:
                result.append({'name':name,'path':str(self.paths.models / 'insightface/models/buffalo_l' / name),
                               'role':'Gesichtserkennung / Analyse','loader':'InsightFace buffalo_l','node':'3'})
        return result

    def model_inventory(self):
        items = self.library.inventory()
        used = {item['id']: [] for item in items}
        for workflow_id, entry in ENTRIES.items():
            paths = {item['path'].casefold() for item in self.dependencies(workflow_id)}
            selectable_ids = {option['id'] for _,role,directory,*_ in MODEL_FIELDS.get(workflow_id, {}).values()
                              for option in self.model_options(role,directory)}
            if workflow_id == 'wan':
                selectable_ids.update(self.wan_low(model_id)['id'] for model_id in list(selectable_ids))
            for item in items:
                aliases = [item['id']] + item.get('aliases', [])
                referenced = any(str(self.paths.models / alias).casefold() in paths for alias in aliases)
                selectable = bool(selectable_ids.intersection(aliases))
                if referenced or selectable:
                    used[item['id']].append({'id':workflow_id, 'name':entry[0]})
        return [dict(item, used_by=used[item['id']]) for item in items]

    def list_entries(self):
        return [{'id':key,'name':value[0],'description':value[1],'roles':[{'id':k,'label':v} for k,v in value[3].items()], 'controls':self.controls(key),'issues':self.readiness(key),'dependencies':self.dependencies(key)} for key,value in ENTRIES.items()]

    def build(self, workflow_id, controls, images, *, uploaded=False, region_mask=None):
        values = self.validate_controls(workflow_id, controls)
        roles = IMAGE_NODES[workflow_id]
        if not isinstance(images, dict) or set(images) != set(roles):
            raise UiError('images', 'Bitte alle erforderlichen Bilder ihren richtigen Rollen zuordnen.', list(roles))
        issues = self.readiness(workflow_id, values)
        if issues:
            raise UiError('models_missing', issues[0]['message'], issues)
        graph = self.prepared_graph(workflow_id, values)
        for role,node in roles.items():
            if not isinstance(images[role], str):
                raise UiError('image_name', 'Ungültiger Bildname.')
            path = self.paths.inside(self.paths.input, images[role], not uploaded)
            if not uploaded and not path.is_file():
                raise UiError('image_file', 'Das gewählte Eingabebild ist nicht lesbar.')
            graph[node]['inputs']['image'] = images[role]
        if region_mask is not None:
            if not isinstance(region_mask, str) or not region_mask:
                raise UiError('edit_region_mask', 'Die Bereichsmaske benötigt einen gültigen Eingabenamen.')
            mask_path = self.paths.inside(self.paths.input, region_mask, not uploaded)
            if not uploaded and not mask_path.is_file():
                raise UiError('edit_region_mask', 'Die Bereichsmaske ist nicht lesbar.')
            graph = composite_graph(graph, workflow_id, region_mask)
        return graph

def PathName(value):
    return value.replace('\\','/').rsplit('/',1)[-1]
