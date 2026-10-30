import json
from .base import LanguageProvider, LocalHttp
from ..paths import UiError
from ..tool_planning import ToolPlanning, invalid_proposal

class LMStudioProvider(LanguageProvider):
    def __init__(self, settings, catalog, wire=None):
        self.settings, self.catalog = settings, catalog
        self.wire = wire or LocalHttp(settings, service_name='LM Studio')

    async def close(self):
        if hasattr(self.wire, 'close'):
            await self.wire.close()

    async def list_models(self):
        data = await self.wire.request('GET','/api/v1/models')
        if not isinstance(data, dict) or not isinstance(data.get('models'), list):
            raise UiError('models', 'Die Modellliste von LM Studio ist unvollständig.')
        result = []
        for item in data['models']:
            if not isinstance(item, dict) or item.get('type') != 'llm' or not isinstance(item.get('key'), str):
                continue
            loaded = item.get('loaded_instances', [])
            result.append({'key':item['key'],'name':item.get('display_name') or item['key'], 'loaded_instances':[x for x in loaded if isinstance(x, dict) and isinstance(x.get('id'), str)] if isinstance(loaded, list) else [], 'capabilities':item.get('capabilities')})
        return result

    async def load(self, model_key):
        if model_key not in {x['key'] for x in await self.list_models()}:
            raise UiError('model_key', 'Das gewählte Sprachmodell steht im lokalen Server nicht zur Verfügung.')
        result = await self.wire.request('POST','/api/v1/models/load',{'model':model_key,'echo_load_config':True})
        if not isinstance(result, dict) or not isinstance(result.get('instance_id'), str) or result.get('status') != 'loaded':
            raise UiError('model_load', 'LM Studio hat den Ladezustand nicht bestätigt.')
        return result

    async def require_instance(self, instance_id):
        if not isinstance(instance_id, str) or instance_id not in {x['id'] for model in await self.list_models() for x in model['loaded_instances']}:
            raise UiError('model_unloaded', 'Bitte das gewählte Sprachmodell zuerst über „Modell laden“ bereitstellen.')

    async def unload(self, instance_id):
        await self.require_instance(instance_id)
        await self.wire.request('POST','/api/v1/models/unload',{'instance_id':instance_id})

    async def propose(self, instance_id, workflow_id, instruction, allowed_controls):
        if not isinstance(instruction, str) or not instruction.strip() or len(instruction) > 8000:
            raise UiError('instruction', 'Bitte einen Auftrag eingeben (höchstens 8.000 Zeichen).')
        await self.require_instance(instance_id)
        fields = self.catalog.controls(workflow_id)
        properties = {}
        for name, spec in fields.items():
            if name == 'prompt' or spec['kind'] == 'model':
                continue
            prop = {'type':'string' if spec['kind'] in ['text','faces'] else spec['kind'], 'description':spec['label']}
            if 'min' in spec:
                prop.update(minimum=spec['min'], maximum=spec['max'])
            properties[name] = prop
        schema = {'type':'object','properties':{'assistant_text':{'type':'string','maxLength':2000}, 'prompt':{'type':'string','maxLength':8000 if 'prompt' in fields else 0}, 'controls':{'type':'object','properties':properties,'additionalProperties':False}},'required':['assistant_text','prompt','controls'],'additionalProperties':False}
        payload = {'model':instance_id,'stream':False,'max_tokens':1024,'response_format':{'type':'json_schema','json_schema':{'name':'morph_proposal','schema':schema}}, 'messages':[{'role':'system','content':'Du hilfst bei MORPH. Erstelle nur einen prüfbaren Vorschlag, führe nichts aus. assistant_text und prompt auf Deutsch; prompt als präzise Bild-/Videoanweisung. Übernimm nur ausdrücklich gewünschte Einstellungen. Keine Dateipfade, Befehle oder neuen Knoten. Bei Gesichtstausch ist prompt leer. Workflow: ' + workflow_id + '. Erlaubte Einstellungen: ' + json.dumps(allowed_controls, ensure_ascii=False)}, {'role':'user','content':instruction}]}
        response = await self.wire.request('POST','/v1/chat/completions',payload)
        try:
            choice = response['choices'][0]
            if choice.get('finish_reason') not in ['stop', None]:
                raise ValueError('Truncated answer')
            result = json.loads(choice['message']['content'])
            if not isinstance(result, dict) or set(result) != {'assistant_text','prompt','controls'} or not isinstance(result['assistant_text'], str) or len(result['assistant_text']) > 2000 or not isinstance(result['prompt'], str) or len(result['prompt']) > 8000 or not isinstance(result['controls'], dict) or set(result['controls']) - set(properties):
                raise ValueError('Invalid proposal')
            controls = {name:spec['default'] for name,spec in allowed_controls.items() if name in fields}
            controls.update(result['controls'])
            if 'prompt' in fields:
                controls['prompt'] = result['prompt']
            elif result['prompt']:
                raise ValueError('Prompt is unavailable')
            self.catalog.validate_controls(workflow_id, controls)
            return result
        except (KeyError, IndexError, TypeError, ValueError) as error:
            raise UiError('proposal_invalid', 'Das Sprachmodell hat keinen vollständigen, verwendbaren Vorschlag geliefert. Es wurde nichts übernommen und keine Anfrage wiederholt.') from error

    async def propose_tools(self, instance_id, workflow_id, instruction, controls):
        planning = ToolPlanning(self.catalog, workflow_id, instruction, controls)
        payload = {
            'model': instance_id, 'stream': False, 'max_tokens': 1024, 'temperature': 0.2,
            'response_format': {'type': 'json_schema', 'json_schema': {
                'name': 'morph_tool_proposal', 'schema': planning.schema()}},
            'messages': planning.messages()}
        planning.validate_request(payload)
        await self.require_instance(instance_id)
        response = await self.wire.request('POST', '/v1/chat/completions', payload)
        try:
            if (not isinstance(response, dict) or 'error' in response
                    or not isinstance(response.get('choices'), list) or len(response['choices']) != 1):
                raise ValueError('Invalid response')
            choice = response['choices'][0]
            if not isinstance(choice, dict) or choice.get('finish_reason') != 'stop':
                raise ValueError('Incomplete answer')
            message = choice.get('message')
            if not isinstance(message, dict) or message.get('role') != 'assistant':
                raise ValueError('Invalid assistant message')
            return planning.parse(message['content'])
        except (KeyError, TypeError, ValueError) as error:
            raise invalid_proposal() from error
