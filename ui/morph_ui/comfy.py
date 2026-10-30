import asyncio
import importlib.util
import json
import uuid
from pathlib import PurePosixPath
from urllib.parse import urlencode
import aiohttp
from .paths import UiError
from .settings import local_endpoint
from .catalog import SELECTORS
from .progress import ProgressWatcher

class ComfyClient:
    def __init__(self, paths, base_url='http://127.0.0.1:8188'):
        self.paths, self.base_url = paths, local_endpoint(base_url)
        self.session, self.guard = None, None
        self.last_node_errors = {}
        self.progress_watchers = {}
        self.closed = False

    def starter(self):
        if self.guard is None:
            path = self.paths.inside(self.paths.root, 'tools/lmstudio-wan-chat/start_mcp.py', True)
            spec = importlib.util.spec_from_file_location('morph_ui_guarded_starter', path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            module.ROOT = self.paths.root
            module.PYTHON = self.paths.python
            module.START_SCRIPT = self.paths.root / 'start-morph.ps1'
            module.REPORT_DIR = self.paths.root / 'reports/wan-lmstudio'
            self.guard = module
        return self.guard

    async def status(self):
        try:
            guard = self.starter()
            ready = await asyncio.to_thread(guard.service_ready)
            try:
                result = await asyncio.to_thread(guard.inspect_listener_details)
            except Exception as error:
                result = {'ownership':'unknown','pid':None,'message':str(error)}
            if ready:
                result = dict(result, ownership='owned' if result['ownership'] == 'owned' else 'compatible',
                              message='Kompatibler lokaler ComfyUI-Rechendienst bereit.')
            return dict(result, ready=ready)
        except Exception as error:
            return {'ready':False,'ownership':'unknown','pid':None,'message':'Der Rechendienst konnte nicht geprüft werden.','details':str(error)}

    async def ensure_ready(self):
        try:
            await asyncio.to_thread(self.starter().ensure_comfy)
        except Exception as error:
            raise UiError('comfy_start', 'MORPH konnte seinen Rechendienst nicht bereitstellen. Bitte die Startprotokolle prüfen.', str(error), 503) from error

    def network(self):
        if self.session is None:
            self.session = aiohttp.ClientSession(trust_env=False)
        return self.session

    async def request(self, method, endpoint, payload=None, form=None):
        try:
            async with self.network().request(method, self.base_url + endpoint, json=payload if form is None else None, data=form, timeout=aiohttp.ClientTimeout(total=30), allow_redirects=False) as response:
                data = bytearray()
                async for chunk in response.content.iter_chunked(64 * 1024):
                    data.extend(chunk)
                    if len(data) > 8 * 1024**2:
                        raise UiError('comfy_response', 'Die Antwort des Rechendienstes ist zu groß.', status=502)
                try:
                    result = json.loads(data) if data else {}
                except ValueError as error:
                    raise UiError('comfy_response', 'Der Rechendienst hat keine lesbare Antwort geliefert.', status=502) from error
                if not 200 <= response.status < 300:
                    raise UiError('comfy_rejected', f'Der Rechendienst hat die Anfrage abgelehnt (HTTP {response.status}).', result, response.status)
                return result
        except (aiohttp.ClientError, OSError, TimeoutError) as error:
            raise UiError('comfy_connection', 'Die Verbindung zum MORPH-Rechendienst wurde unterbrochen. Es wird kein Auftrag automatisch wiederholt.', status=503) from error

    async def queue(self):
        value = await self.request('GET','/queue')
        if not isinstance(value, dict) or not isinstance(value.get('queue_running'), list) or not isinstance(value.get('queue_pending'), list):
            raise UiError('comfy_queue', 'Die Warteschlange konnte nicht zuverlässig geprüft werden.')
        return value

    async def resource_stats(self):
        return await self.request('GET', '/system_stats')

    async def resource_control(self):
        try:
            guard = self.starter()
            if self.base_url != guard.COMFY_URL:
                return {'allowed':False, 'reason':'Der API-Endpunkt entspricht nicht der quittierten Instanz.'}
            await asyncio.to_thread(guard.inspect_managed_listener)
        except Exception:
            return {'allowed':False, 'reason':'Keine gültige eigene Startquittung und Prozessidentität nachgewiesen.'}
        try:
            queue = await self.queue()
        except Exception:
            return {'allowed':False, 'reason':'Die Warteschlange ist nicht zuverlässig lesbar.'}
        if queue['queue_running'] or queue['queue_pending']:
            return {'allowed':False, 'reason':'ComfyUI hat laufende oder wartende Aufträge.'}
        return {'allowed':True, 'reason':'Eigene verwaltete Instanz ist momentan frei; bei der Aktion wird erneut geprüft.'}

    async def emergency_release(self):
        guard, handle, acquired, stopped = self.starter(), None, False, False
        start_lock = guard.StartLock(timeout=0)
        try:
            if self.base_url != guard.COMFY_URL:
                raise UiError('resource_endpoint', 'Der API-Endpunkt entspricht nicht der quittierten Instanz. Notfall-Freigabe gesperrt.', status=409)
            await asyncio.to_thread(start_lock.__enter__)
            acquired = True
            receipt, handle = await asyncio.to_thread(guard.open_managed_stop_listener)
            for final in (False, True):
                queue = await self.queue()
                if queue['queue_running'] or queue['queue_pending']:
                    raise UiError('queue_busy', 'ComfyUI hat laufende oder wartende Aufträge. Notfall-Freigabe gesperrt.', status=409)
                if not final:
                    await asyncio.to_thread(guard.verify_managed_listener, receipt, handle)
            # The helper repeats the final native-handle/listener check immediately
            # before termination and confirms exit on that same handle.
            await asyncio.to_thread(guard.stop_verified_managed_listener, receipt, handle)
            stopped = True
            listener = await asyncio.to_thread(guard.inspect_listener_details)
            if listener.get('ownership') != 'free':
                raise UiError('emergency_port_unconfirmed', 'Der eigene Rechendienst wurde beendet, aber Port 8188 ist nicht bestätigt frei. Kein weiterer Prozess wird beendet.', status=409)
            return {'completed':True, 'stopped':True, 'old_pid':receipt['pid'],
                    'message':'Der eigene Rechendienst wurde beendet. Die nächste bewusste Bildberechnung startet ihn bei Bedarf neu.'}
        except UiError as error:
            if error.code in {'queue_busy', 'resource_endpoint', 'emergency_port_unconfirmed'}:
                raise
            raise UiError('emergency_unconfirmed', 'Die Notfall-Freigabe wurde nicht bestätigt. Der eigene Rechendienst kann bereits beendet sein. Bitte Zustand prüfen; kein automatischer Wiederholungsversuch.', status=409) from error
        except Exception as error:
            message = ('Der eigene Rechendienst wurde beendet, aber sein Folgezustand ist nicht bestätigt.' if stopped else
                       'Die Notfall-Freigabe wurde nicht bestätigt. Der eigene Rechendienst kann bereits beendet sein.')
            raise UiError('emergency_unconfirmed', message + ' Bitte Zustand prüfen; kein weiterer Prozess wird beendet und nichts automatisch wiederholt.', status=409) from error
        finally:
            try:
                if handle is not None:
                    await asyncio.to_thread(guard.close_process_handle, handle)
            finally:
                if acquired:
                    await asyncio.to_thread(start_lock.__exit__, None, None, None)

    async def free_resources(self):
        guard, handle = self.starter(), None
        try:
            if self.base_url != guard.COMFY_URL:
                raise UiError('resource_endpoint', 'Der API-Endpunkt entspricht nicht der quittierten Instanz. Freigabe gesperrt.', status=409)
            receipt, handle = await asyncio.to_thread(guard.open_managed_listener)
            for final in (False, True):
                queue = await self.queue()
                if queue['queue_running'] or queue['queue_pending']:
                    raise UiError('queue_busy', 'ComfyUI hat laufende oder wartende Aufträge. Freigabe gesperrt.', status=409)
                if not final:
                    await asyncio.to_thread(guard.verify_managed_listener, receipt, handle)
            # Recheck the listener too: its owner may change during the queue read.
            await asyncio.to_thread(guard.verify_managed_listener, receipt, handle)
            # Direct Comfy clients bypass the MORPH job lock; this HTTP gap cannot be atomic.
            await self.request('POST', '/free', {'unload_models':True, 'free_memory':True})
            return {'accepted':True, 'completed':False, 'message':'Freigabe angefordert'}
        except UiError as error:
            if error.code in {'queue_busy', 'resource_endpoint'}:
                raise
            raise UiError(error.code, 'Die Speicherfreigabe wurde nicht eindeutig bestätigt. Bitte Verbindung und aktuellen Zustand prüfen; kein automatischer Wiederholungsversuch.', status=error.status) from error
        except Exception as error:
            raise UiError('resource_ownership', 'Freigabe gesperrt: Die eigene verwaltete Instanz konnte nicht eindeutig nachgewiesen werden.', status=409) from error
        finally:
            if handle is not None:
                await asyncio.to_thread(guard.close_process_handle, handle)

    async def model_readiness(self, graph):
        """Read loader enums only; no model is loaded or executed."""
        schemas, issues = {}, []
        for node in graph.values():
            selected = {key:value for key,value in node['inputs'].items() if key in SELECTORS and isinstance(value,str)}
            if not selected:
                continue
            kind = node['class_type']
            if kind not in schemas:
                data = await self.request('GET','/object_info/' + kind)
                if not isinstance(data,dict) or not isinstance(data.get(kind),dict):
                    raise UiError('comfy_node', 'Der Rechendienst kennt einen benötigten Workflow-Knoten nicht.', kind)
                schemas[kind] = data[kind].get('input',{})
            for key,value in selected.items():
                spec = schemas[kind].get('required',{}).get(key) or schemas[kind].get('optional',{}).get(key)
                if not isinstance(spec,list) or not spec or not isinstance(spec[0],list):
                    raise UiError('comfy_schema', 'Die Modellzuordnung konnte nicht zuverlässig geprüft werden.', kind + '.' + key)
                if value.replace('\\','/') not in {name.replace('\\','/') for name in spec[0] if isinstance(name,str)}:
                    relative = SELECTORS[key] + '/' + value.replace('\\','/')
                    issues.append({'code':'comfy_model','message':'Im Rechendienst noch nicht verfügbar: ' + value + '. Bitte Modellordner und Verbindung prüfen.','path':str(self.paths.models / relative)})
        return issues

    async def require_region_nodes(self):
        """Validate the two native compositor node signatures without executing them."""
        signatures = {
            'LoadImageMask': ({'channel': None, 'image': None}, 'MASK'),
            'ImageCompositeMasked': ({'destination': 'IMAGE', 'source': 'IMAGE', 'x': 'INT', 'y': 'INT',
                                      'resize_source': 'BOOLEAN', 'mask': 'MASK'}, 'IMAGE')}
        for kind, (expected, output) in signatures.items():
            data = await self.request('GET', '/object_info/' + kind)
            schema = data.get(kind) if isinstance(data, dict) else None
            try:
                inputs = schema['input']
                fields = dict(inputs.get('required', {}), **inputs.get('optional', {}))
                if schema['output'][0] != output:
                    raise ValueError('Output type')
                for key, value in expected.items():
                    spec = fields[key]
                    if not isinstance(spec, list) or not spec or (value is not None and spec[0] != value):
                        raise ValueError('Input type')
                if kind == 'LoadImageMask' and (not isinstance(fields['channel'][0], list) or 'red' not in fields['channel'][0]):
                    raise ValueError('Mask channel')
            except (KeyError, TypeError, IndexError, ValueError, AttributeError):
                raise UiError('comfy_region_node', 'Der Rechendienst unterstützt die benötigte Bereichskomposition noch nicht. Bitte den vorhandenen MORPH-Rechendienst und seine Knoten prüfen.', kind) from None

    async def upload(self, path):
        form = aiohttp.FormData()
        with path.open('rb') as source:
            form.add_field('image', source, filename=path.name, content_type='application/octet-stream')
            form.add_field('type','input')
            form.add_field('subfolder','morph-ui/jobs')
            form.add_field('overwrite','false')
            result = await self.request('POST','/upload/image', form=form)
        if not isinstance(result, dict) or not isinstance(result.get('name'), str) or result.get('type') != 'input' or not isinstance(result.get('subfolder',''), str):
            raise UiError('comfy_upload', 'Der Rechendienst hat den Bildnamen nicht bestätigt.')
        if result.get('subfolder') != 'morph-ui/jobs':
            raise UiError('comfy_upload', 'Der Rechendienst hat einen unerwarteten Eingabeordner zurückgegeben.')
        self.output_reference({'filename':result['name'],'subfolder':result['subfolder'],'type':'output'})
        name = result['subfolder'] + '/' + result['name']
        return name

    @staticmethod
    def output_reference(item):
        if not isinstance(item,dict) or item.get('type','output') not in {'output','temp'}:
            raise UiError('output_path', 'Die Ausgabe gehört nicht zu einem freigegebenen Backendbereich.')
        filename, subfolder = item.get('filename'), item.get('subfolder','')
        if (not isinstance(filename,str) or not filename or not isinstance(subfolder,str)
                or any(char in filename for char in '/\\:\x00') or filename in {'.','..'}
                or '\x00' in subfolder or ':' in subfolder or '\\' in subfolder
                or subfolder.startswith('/') or '..' in PurePosixPath(subfolder).parts):
            raise UiError('output_path', 'Der Rechendienst hat einen unsicheren Dateiverweis zurückgegeben.')
        return {'filename':filename,'subfolder':subfolder,'type':item.get('type','output')}

    async def download_output(self, item, prompt_id):
        reference = self.output_reference(item)
        suffix = PurePosixPath(reference['filename']).suffix.lower()
        if suffix not in {'.png','.jpg','.jpeg','.webp','.gif','.mp4','.webm'}:
            raise UiError('output_format', 'Dieses Ausgabeformat unterstützt keine Vorschau.')
        try:
            identifier = str(uuid.UUID(prompt_id))
        except (ValueError, TypeError, AttributeError) as error:
            raise UiError('output_path', 'Der Ausgabe fehlt eine gültige Auftragskennung.') from error
        target = self.paths.inside(self.paths.output, 'MORPH-UI/imports/' + identifier + '-' + uuid.uuid4().hex + suffix)
        partial = target.with_suffix(target.suffix + '.part')
        limit = 512 * 1024**2
        try:
            async with self.network().get(self.base_url + '/view?' + urlencode(reference),
                    timeout=aiohttp.ClientTimeout(total=120), allow_redirects=False) as response:
                if response.status != 200:
                    raise UiError('comfy_output', f'Das Ergebnis konnte nicht übernommen werden (HTTP {response.status}).', status=502)
                if response.content_length is not None and response.content_length > limit:
                    raise UiError('comfy_output', 'Die Ergebnisdatei überschreitet 512 MiB.', status=502)
                target.parent.mkdir(parents=True, exist_ok=True)
                total = 0
                with partial.open('xb') as output:
                    async for chunk in response.content.iter_chunked(64 * 1024):
                        total += len(chunk)
                        if total > limit:
                            raise UiError('comfy_output', 'Die Ergebnisdatei überschreitet 512 MiB.', status=502)
                        output.write(chunk)
                if total == 0:
                    raise UiError('comfy_output', 'Der Rechendienst hat eine leere Ergebnisdatei geliefert.', status=502)
                partial.rename(target)
            return target
        except (aiohttp.ClientError, OSError, TimeoutError) as error:
            raise UiError('comfy_output', 'Das Ergebnis konnte nicht vollständig übernommen werden. Der Auftrag wird nicht erneut berechnet.', str(error), 503) from error
        finally:
            partial.unlink(missing_ok=True)

    async def watch_progress(self, prompt_id, client_id, graph, callback):
        if self.closed:
            return
        identifier, connection = str(uuid.UUID(prompt_id)), str(uuid.UUID(client_id))
        watcher = self.progress_watchers.get(identifier)
        if watcher is None:
            watcher = ProgressWatcher(self.network, self.base_url + '/ws', identifier, connection, graph, callback)
            self.progress_watchers[identifier] = watcher
        await watcher.wait_initial()

    def stop_progress(self, prompt_id):
        watcher = self.progress_watchers.get(prompt_id)
        if watcher is not None:
            watcher.stop()

    async def submit(self, graph, prompt_id, client_id=None):
        self.last_node_errors = {}
        connection = str(uuid.UUID(client_id)) if client_id is not None else 'morph-ui'
        result = await self.request('POST','/prompt', {'prompt':graph,'prompt_id':str(uuid.UUID(prompt_id)),'client_id':connection})
        if not isinstance(result, dict) or result.get('prompt_id') != prompt_id:
            raise UiError('comfy_receipt', 'Die Auftragskennung wurde nicht eindeutig bestätigt.', result, 502)
        self.last_node_errors = result.get('node_errors', {})
        return result['prompt_id']

    async def poll(self, prompt_id):
        identifier = str(uuid.UUID(prompt_id))
        queue = await self.queue()
        history = await self.request('GET','/history/' + identifier)
        if not isinstance(history, dict):
            raise UiError('comfy_history', 'Der Auftragsverlauf ist unvollständig.')
        entry = history.get(identifier)
        if entry is not None:
            if not isinstance(entry, dict) or not isinstance(entry.get('status'), dict):
                raise UiError('comfy_history', 'Der Auftragsverlauf ist unvollständig.')
            status = entry['status']
            messages = status.get('messages', [])
            interrupted = any(isinstance(x, list) and x and x[0] == 'execution_interrupted' for x in messages)
            if interrupted:
                return {'state':'cancelled','outputs':[],'details':status}
            if status.get('status_str') == 'error':
                return {'state':'error','outputs':[],'details':status}
            if status.get('completed') is True:
                outputs = []
                for node in entry.get('outputs', {}).values():
                    for key in ['images','gifs','videos']:
                        for item in node.get(key, []):
                            if isinstance(item, dict) and isinstance(item.get('filename'), str):
                                outputs.append(item)
                return {'state':'completed','outputs':outputs}
        for key,state in [('queue_running','running'),('queue_pending','queued')]:
            if any(isinstance(row, list) and len(row) > 1 and row[1] == identifier for row in queue[key]):
                return {'state':state,'outputs':[]}
        return {'state':'absent','outputs':[]}

    async def cancel(self, prompt_id):
        result = await self.request('POST','/api/jobs/' + str(uuid.UUID(prompt_id)) + '/cancel', {})
        if not isinstance(result, dict) or type(result.get('cancelled')) is not bool:
            raise UiError('comfy_cancel', 'Der gezielte Abbruch wurde nicht eindeutig bestätigt. Bitte den Auftragszustand prüfen.')
        return result['cancelled']

    async def close(self):
        self.closed = True
        watchers = list(self.progress_watchers.values())
        if watchers:
            await asyncio.gather(*(watcher.close() for watcher in watchers), return_exceptions=True)
        self.progress_watchers.clear()
        if self.session:
            await self.session.close()
