import json
import math

from .base import LanguageProvider, LocalHttp
from ..paths import UiError
from ..tool_planning import ToolPlanning, invalid_proposal, PRESERVE_UNSPECIFIED


class OllamaProvider(LanguageProvider):
    def __init__(self, settings, catalog, wire=None):
        self.settings, self.catalog = settings, catalog
        self.wire = wire or LocalHttp(settings)
        self.mutation_observer = None

    async def close(self):
        if hasattr(self.wire, 'close'):
            await self.wire.close()

    @staticmethod
    def _models(data):
        if not isinstance(data, dict) or not isinstance(data.get('models'), list):
            raise UiError('models', 'Die Modellliste von Ollama ist unvollständig.')
        return data['models']

    @staticmethod
    def _name(item):
        if not isinstance(item, dict):
            return None
        name = item.get('name') or item.get('model')
        return name if isinstance(name, str) and name.strip() == name and name else None

    @staticmethod
    def _remote(item):
        return any(item.get(key) not in (None, '') for key in ['remote_host', 'remote_model'])

    @staticmethod
    def _embedding_only(item):
        capabilities = item.get('capabilities')
        if isinstance(capabilities, list) and 'embedding' in capabilities and 'completion' not in capabilities:
            return True
        details = item.get('details')
        family = details.get('family') if isinstance(details, dict) else None
        if family in ['bert', 'nomic-bert', 'nomic-bert-moe']:
            return True
        name = OllamaProvider._name(item)
        base = name.rsplit('/', 1)[-1].split(':', 1)[0].lower() if name else ''
        return base in ['nomic-embed-text', 'nomic-embed-text-v2-moe', 'mxbai-embed-large',
                        'all-minilm', 'snowflake-arctic-embed', 'snowflake-arctic-embed2',
                        'embeddinggemma', 'qwen3-embedding', 'bge-m3', 'bge-large',
                        'granite-embedding', 'paraphrase-multilingual']

    async def _loaded_names(self):
        data = await self.wire.request('GET', '/api/ps')
        names = set()
        for item in self._models(data):
            name = self._name(item)
            if (not name or any(key in item and item[key] != name for key in ('name', 'model'))):
                raise UiError('models', 'Ollama hat die geladenen Modellnamen nicht vollständig und eindeutig bestätigt.')
            names.add(name)
        return names

    async def gpu_residency(self):
        """Only fresh native ps measurements establish positive GPU residency."""
        names, unknown = [], False
        try:
            for item in self._models(await self.wire.request('GET', '/api/ps')):
                name = self._name(item)
                size = item.get('size_vram') if isinstance(item, dict) else None
                if (not name or type(size) not in (int, float)
                        or not math.isfinite(size) or size < 0):
                    unknown = True
                elif size > 0:
                    names.append(name)
        except Exception:
            unknown = True
        return {'state': 'resident' if names else 'unknown' if unknown else 'clear',
                'models': sorted(set(names))}

    async def _mutate(self, path, payload):
        model = payload['model']
        if self.mutation_observer:
            self.mutation_observer('started', model)
        response = await self.wire.request('POST', path, payload)
        if self._confirmed(response, model) and self.mutation_observer:
            self.mutation_observer('completed', model)
        return response

    async def list_models(self):
        data = await self.wire.request('GET', '/api/tags')
        installed = self._models(data)
        loaded = await self._loaded_names()
        result, seen = [], set()
        for item in installed:
            name = self._name(item)
            if not name or name in seen or self._remote(item) or self._embedding_only(item):
                continue
            seen.add(name)
            result.append({'key': name, 'name': name,
                           'loaded_instances': [{'id': name}] if name in loaded else [],
                           'capabilities': item.get('capabilities')})
        return result

    async def _require_local_completion(self, model_name):
        # /api/show reads metadata; it does not load or execute the model.
        data = await self.wire.request('POST', '/api/show', {'model': model_name})
        if not isinstance(data, dict) or self._remote(data):
            raise UiError('model_local', 'Bitte ein vollständig lokal verfügbares Ollama-Sprachmodell auswählen.')
        capabilities = data.get('capabilities')
        if (not isinstance(capabilities, list) or not all(isinstance(value, str) for value in capabilities)
                or 'completion' not in capabilities):
            raise UiError('model_capability', 'Ollama hat für dieses Modell keine Textgenerierung bestätigt.')

    @classmethod
    def _confirmed(cls, data, model_name):
        return (isinstance(data, dict) and 'error' not in data and data.get('done') is True
                and data.get('model') == model_name and not cls._remote(data))

    async def load(self, model_key):
        if not isinstance(model_key, str) or model_key not in {x['key'] for x in await self.list_models()}:
            raise UiError('model_key', 'Das gewählte Sprachmodell steht im lokalen Ollama-Server nicht zur Verfügung.')
        await self._require_local_completion(model_key)
        result = await self._mutate('/api/generate', {
            'model': model_key, 'stream': False, 'keep_alive': '5m', 'options': {'num_ctx': 4096}})
        if not self._confirmed(result, model_key) or model_key not in await self._loaded_names():
            raise UiError('model_load', 'Ollama hat den Ladezustand nicht bestätigt.')
        return {'status': 'loaded', 'instance_id': model_key}

    async def require_instance(self, instance_id):
        if not isinstance(instance_id, str) or instance_id not in {
                x['id'] for model in await self.list_models() for x in model['loaded_instances']}:
            raise UiError('model_unloaded', 'Bitte das gewählte Sprachmodell zuerst über „Modell laden“ bereitstellen.')

    async def unload(self, instance_id, *, reconcile=False):
        if reconcile:
            # Only JobService's exact persisted uncertain target may use this path.
            if not isinstance(instance_id, str) or instance_id not in {x['key'] for x in await self.list_models()}:
                raise UiError('model_key', 'Das betroffene lokale Sprachmodell ist nicht mehr eindeutig verfügbar.')
        else:
            await self.require_instance(instance_id)
        result = await self._mutate('/api/generate', {
            'model': instance_id, 'stream': False, 'keep_alive': 0})
        if not self._confirmed(result, instance_id) or instance_id in await self._loaded_names():
            raise UiError('model_unload', 'Ollama hat das Entladen des gewählten Sprachmodells nicht bestätigt.')

    async def propose(self, instance_id, workflow_id, instruction, allowed_controls):
        if not isinstance(instruction, str) or not instruction.strip() or len(instruction) > 8000:
            raise UiError('instruction', 'Bitte einen Auftrag eingeben (höchstens 8.000 Zeichen).')
        fields = self.catalog.controls(workflow_id)
        current = {name: spec['default'] for name, spec in allowed_controls.items() if name in fields}
        visible = {name: value for name, value in current.items() if fields[name]['kind'] != 'model'}
        profile = self.catalog.prompt_profile(workflow_id, current)
        properties = {}
        for name, spec in fields.items():
            if name == 'prompt' or spec['kind'] == 'model':
                continue
            prop = {'type': 'string' if spec['kind'] in ['text', 'faces'] else spec['kind'],
                    'description': spec['label']}
            if 'min' in spec:
                prop.update(minimum=spec['min'], maximum=spec['max'])
            properties[name] = prop
        schema = {
            'type': 'object', 'properties': {
                'assistant_text': {'type': 'string', 'maxLength': 2000},
                'prompt': {'type': 'string', 'maxLength': 8000 if 'prompt' in fields else 0},
                'controls': {'type': 'object', 'properties': properties, 'additionalProperties': False}},
            'required': ['assistant_text', 'prompt', 'controls'], 'additionalProperties': False}
        payload = {
            'model': instance_id, 'stream': False, 'think': False, 'keep_alive': '5m',
            'options': {'num_predict': 1024, 'num_ctx': 4096, 'temperature': 0.2}, 'format': schema,
            'messages': [
                {'role': 'system', 'content':
                 'Du hilfst bei MORPH. Erstelle nur einen prüfbaren Vorschlag, führe nichts aus. '
                 'assistant_text und prompt auf Deutsch; prompt als präzise Bild-/Videoanweisung. '
                 + PRESERVE_UNSPECIFIED +
                 'Übernimm nur ausdrücklich gewünschte Einstellungen. Keine Dateipfade, Befehle '
                 'oder neuen Knoten/Modellwechsel. Bei Gesichtstausch ist prompt leer. Workflow: ' + workflow_id
                 + '. Profil: ' + profile
                 + '. Sichtbare Einstellungen: ' + json.dumps(visible, ensure_ascii=False)},
                {'role': 'user', 'content': instruction}]}
        ToolPlanning.validate_request(payload)
        await self.require_instance(instance_id)
        await self._require_local_completion(instance_id)
        response = await self._mutate('/api/chat', payload)
        try:
            if not self._confirmed(response, instance_id) or response.get('done_reason') != 'stop':
                raise ValueError('Incomplete answer')
            message = response.get('message')
            if not isinstance(message, dict) or message.get('role') != 'assistant':
                raise ValueError('Invalid assistant message')
            result = json.loads(message['content'])
            if (not isinstance(result, dict) or set(result) != {'assistant_text', 'prompt', 'controls'}
                    or not isinstance(result['assistant_text'], str) or len(result['assistant_text']) > 2000
                    or not isinstance(result['prompt'], str) or len(result['prompt']) > 8000
                    or not isinstance(result['controls'], dict) or set(result['controls']) - set(properties)):
                raise ValueError('Invalid proposal')
            controls = dict(current)
            controls.update(result['controls'])
            if 'prompt' in fields:
                controls['prompt'] = result['prompt']
            elif result['prompt']:
                raise ValueError('Prompt is unavailable')
            self.catalog.validate_controls(workflow_id, controls)
            return result
        except (KeyError, IndexError, TypeError, ValueError) as error:
            raise UiError('proposal_invalid', 'Das Sprachmodell hat keinen vollständigen, verwendbaren Vorschlag '
                          'geliefert. Es wurde nichts übernommen und keine Anfrage wiederholt.') from error

    async def propose_tools(self, instance_id, workflow_id, instruction, controls):
        planning = ToolPlanning(self.catalog, workflow_id, instruction, controls)
        payload = {
            'model': instance_id, 'stream': False, 'think': False, 'keep_alive': '5m',
            'options': {'num_predict': 1024, 'num_ctx': 4096, 'temperature': 0.2},
            'format': planning.schema(),
            'messages': planning.messages()}
        planning.validate_request(payload)
        await self.require_instance(instance_id)
        await self._require_local_completion(instance_id)
        response = await self._mutate('/api/chat', payload)
        try:
            if not self._confirmed(response, instance_id) or response.get('done_reason') != 'stop':
                raise ValueError('Incomplete answer')
            message = response.get('message')
            if not isinstance(message, dict) or message.get('role') != 'assistant':
                raise ValueError('Invalid assistant message')
            return planning.parse(message['content'])
        except (KeyError, TypeError, ValueError) as error:
            raise invalid_proposal() from error
