import asyncio
from datetime import datetime, timezone
import json
import math
import sqlite3
import uuid
from .paths import UiError
from .edit_region import validate_region, verify_region
from .resources import snapshot

ACTIVE = {'preparing','submitting','queued','running','unknown'}
TERMINAL = {'completed','cancelled','error'}

def stamp():
    return datetime.now(timezone.utc).isoformat()

def request_key(value):
    try:
        return str(uuid.UUID(value))
    except (ValueError, TypeError, AttributeError) as error:
        raise UiError('request_id', 'Der Start benötigt eine eindeutige Anforderungskennung.') from error

class JobService:
    def __init__(self, paths, catalog, files, comfy, versions=None):
        self.paths, self.catalog, self.files, self.comfy = paths, catalog, files, comfy
        self.versions = versions
        self.lock = asyncio.Lock()
        self.language_busy = False
        self.emergency_running = False
        self.provider = None
        self.accepting = True
        self.closed = False
        self.progress_started = set()
        self.progress_starts = set()
        self.db = sqlite3.connect(paths.database)
        self.db.execute('CREATE TABLE IF NOT EXISTS jobs (id TEXT PRIMARY KEY, request_id TEXT UNIQUE, prompt_id TEXT UNIQUE, data TEXT)')
        self.db.execute('CREATE TABLE IF NOT EXISTS language_operation (id INTEGER PRIMARY KEY CHECK (id=1), data TEXT NOT NULL)')
        for row in self.db.execute('SELECT data FROM jobs').fetchall():
            job = json.loads(row[0])
            if job['state'] in ['preparing','submitting']:
                job['state'] = 'unknown' if job['state'] == 'submitting' else 'error'
                job['error'] = 'Der Oberflächendienst wurde während der Übergabe beendet. Bitte den Zustand prüfen.'
                self.store(job)
        self.db.commit()

    def close(self):
        self.closed = True
        for task in self.progress_starts:
            task.cancel()
        self.db.close()

    def store(self, job):
        row = self.db.execute('SELECT data FROM jobs WHERE id=?', (job['id'],)).fetchone()
        if row:
            current = json.loads(row[0])
            # Runtime events can arrive while a caller awaits submit/poll/import/cancel.
            if current.get('progress', {}).get('revision', 0) > job.get('progress', {}).get('revision', 0):
                job['progress'] = current['progress']
            job['cancel_requested'] = bool(job.get('cancel_requested') or current.get('cancel_requested'))
        job['updated_at'] = stamp()
        self.db.execute('UPDATE jobs SET data=? WHERE id=?', (json.dumps(job, ensure_ascii=False),job['id']))
        self.db.commit()
        if job['state'] in TERMINAL and hasattr(self.comfy, 'stop_progress'):
            self.comfy.stop_progress(job['prompt_id'])
        return job

    def get(self, job_id):
        row = self.db.execute('SELECT data FROM jobs WHERE id=?', (job_id,)).fetchone()
        if row is None:
            raise UiError('job_id', 'Dieser Auftrag gehört nicht zur MORPH-Oberfläche.', status=404)
        job = json.loads(row[0])
        self.resume_progress(job)
        return job

    def list_recent(self):
        jobs = [json.loads(row[0]) for row in self.db.execute('SELECT data FROM jobs ORDER BY rowid DESC LIMIT 30')]
        for job in jobs:
            self.resume_progress(job)
        return jobs

    def update_progress(self, job_id, fields):
        if self.closed:
            return False
        row = self.db.execute('SELECT data FROM jobs WHERE id=?', (job_id,)).fetchone()
        if row is None:
            return False
        job = json.loads(row[0])
        if job['state'] not in ACTIVE:
            return False
        progress = dict(job.get('progress', {}))
        progress.update(fields)
        progress['revision'] = job.get('progress', {}).get('revision', 0) + 1
        job['progress'] = progress
        self.store(job)
        return True

    async def watch_progress(self, job):
        if not hasattr(self.comfy, 'watch_progress'):
            return
        self.progress_started.add(job['id'])
        try:
            await self.comfy.watch_progress(job['prompt_id'], job['client_id'], job['graph'],
                                           lambda fields: self.update_progress(job['id'], fields))
        except Exception:
            self.update_progress(job['id'], {'connection':'unavailable'})

    def resume_progress(self, job):
        if (self.closed or job['id'] in self.progress_started or job['state'] not in {'queued','running','unknown'}
                or not job.get('client_id') or not isinstance(job.get('graph'), dict)
                or not hasattr(self.comfy, 'watch_progress')):
            return
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return
        self.progress_started.add(job['id'])
        task = loop.create_task(self.watch_progress(job), name='morph-progress-start-' + job['id'])
        self.progress_starts.add(task)
        task.add_done_callback(self.progress_starts.discard)

    def has_unresolved_jobs(self):
        # Resource controls must inspect every persisted job, not only the UI's recent page.
        for row in self.db.execute('SELECT data FROM jobs'):
            try:
                job = json.loads(row[0])
                if not isinstance(job, dict) or job.get('state') not in TERMINAL:
                    return True
            except (ValueError, TypeError):
                return True
        return False

    def language_pending(self):
        row = self.db.execute('SELECT data FROM language_operation WHERE id=1').fetchone()
        if row is None:
            return None
        try:
            value = json.loads(row[0])
            if isinstance(value, dict) and isinstance(value.get('instance_id'), str):
                return value
        except (ValueError, TypeError):
            pass
        return {'instance_id': None}

    def language_state(self):
        pending = self.language_pending()
        return {'busy': self.language_busy,
                'uncertain_instances': [pending['instance_id']] if pending and pending['instance_id'] else []}

    def require_language_idle(self):
        if self.language_busy:
            raise UiError('language_busy', 'Eine Sprachmodellaktion läuft. Bitte deren Abschluss abwarten und anschließend bewusst neu starten.', status=409)
        pending = self.language_pending()
        if pending is not None:
            name = pending.get('instance_id') or 'das betroffene Sprachmodell'
            raise UiError('language_mutation_unknown', 'Der Abschluss der begonnenen Sprachmodellaktion ist unklar. Bitte „' + name + '“ bewusst freigeben; es wird nichts automatisch wiederholt.', status=409)

    def require_settings_change(self):
        self.require_language_idle()
        if self.lock.locked():
            raise UiError('active_job', 'Eine Bild-/Speicheraktion läuft. Verbindungseinstellungen können erst danach bewusst geändert werden.', status=409)

    @staticmethod
    def language_endpoint(provider):
        settings = getattr(provider, 'settings', None)
        return settings.read_public()['endpoint'] if settings is not None else None

    async def require_language_capacity(self):
        try:
            await self.require_empty_queue()
            stats = await self.comfy.resource_stats()
        except Exception as error:
            if isinstance(error, UiError) and error.code == 'queue_busy':
                raise
            status = await self.comfy.status()
            if status.get('ready') is False and status.get('ownership') == 'free':
                return
            raise UiError('image_resources_unknown', 'Die erreichbare ComfyUI-Instanz oder ihre Warteschlange ist nicht zuverlässig prüfbar. Sprachhilfe bleibt bis zur Klärung gesperrt.', status=409) from error
        if not isinstance(stats, dict) or not isinstance(stats.get('devices'), list) or not stats['devices']:
            raise UiError('image_resources_unknown', 'Die ComfyUI-GPU-Reservierung ist nicht zuverlässig prüfbar. Sprachhilfe bleibt bis zur Klärung gesperrt.', status=409)
        for device in stats['devices']:
            if isinstance(device, dict) and device.get('type') == 'cpu':
                continue
            reserved = device.get('torch_vram_total') if isinstance(device, dict) else None
            if (not isinstance(device, dict) or not isinstance(device.get('type'), str)
                    or type(reserved) not in (int, float) or not math.isfinite(reserved) or reserved < 0):
                raise UiError('image_resources_unknown', 'Die ComfyUI-GPU-Reservierung ist nicht zuverlässig prüfbar. Sprachhilfe bleibt bis zur Klärung gesperrt.', status=409)
            if reserved > 0:
                raise UiError('image_gpu_busy', 'ComfyUI hält noch Bildmodelle oder GPU-Speicher bereit. Bitte die Bildmodelle zuerst bewusst über „Speicher freigeben“ entladen.', status=409)

    async def language_action(self, provider, action, instance_id, *args):
        if self.language_busy:
            self.require_language_idle()
        # Never queue an optional language action behind an image/free action.
        if self.lock.locked() or self.has_unresolved_jobs():
            raise UiError('active_job', 'MORPH hat laufende oder ungeklärte Bild-/Speicheraktionen. Sprachmodellaktion gesperrt.', status=409)
        async with self.lock:
            if not self.accepting:
                raise UiError('ui_restarting', 'Die Oberfläche wird gerade neu gestartet. Bitte anschließend die Seite neu laden.', status=503)
            pending = self.language_pending()
            if pending is not None and (action != 'unload' or instance_id != pending.get('instance_id')):
                self.require_language_idle()
            endpoint = self.language_endpoint(provider)
            if pending is not None and pending.get('endpoint') != endpoint:
                raise UiError('language_endpoint_changed', 'Die Verbindung wurde außerhalb der Oberfläche geändert. Die unklare Sprachmodellaktion gehört zum ursprünglichen Endpunkt; vor ihrer bewussten Freigabe muss genau diese Verbindung wiederhergestellt werden.', status=409)
            self.language_busy = True
            previous = getattr(provider, 'mutation_observer', None)
            confirmed = False
            def observe(event, model):
                nonlocal confirmed
                if event == 'started':
                    confirmed = False
                    self.db.execute('INSERT OR REPLACE INTO language_operation VALUES (1,?)',
                                    (json.dumps({'instance_id':model, 'action':action, 'endpoint':endpoint, 'started_at':stamp()}),))
                    self.db.commit()
                elif event == 'completed':
                    confirmed = True
                    if action != 'unload':
                        self.db.execute('DELETE FROM language_operation WHERE id=1')
                        self.db.commit()
            provider.mutation_observer = observe
            try:
                if action != 'unload':
                    await self.require_language_capacity()
                method = getattr(provider, action)
                if action == 'unload' and pending is not None:
                    receipt = await method(instance_id, reconcile=True)
                else:
                    receipt = await method(instance_id, *args)
                if action == 'unload' and confirmed:
                    self.db.execute('DELETE FROM language_operation WHERE id=1')
                    self.db.commit()
                return receipt
            except Exception as error:
                if self.language_pending() is not None:
                    # A GET outage alone never reaches this branch with a new receipt.
                    self.language_busy = False
                    try:
                        self.require_language_idle()
                    except UiError as unknown:
                        raise unknown from error
                raise
            finally:
                provider.mutation_observer = previous
                self.language_busy = False

    async def image_language_warnings(self):
        if self.provider is None or not hasattr(self.provider, 'gpu_residency'):
            residency = {'state':'unknown', 'models':[]}
        else:
            residency = await self.provider.gpu_residency()
        if residency['state'] == 'resident':
            raise UiError('language_gpu_busy', 'Ollama hält GPU-Speicher für „' + '“, „'.join(residency['models']) + '“ bereit. Bitte das Sprachmodell zuerst bewusst freigeben und anschließend erneut starten.', status=409)
        if residency['state'] == 'unknown':
            return ['Der GPU-Belegungszustand von Ollama ist momentan unbekannt. Die optionale Sprachhilfe wurde nicht vorausgesetzt; es wurde kein Sprachmodell automatisch geladen oder entladen.']
        return []

    async def resources(self):
        if self.emergency_running:
            result = snapshot()
            result['unload'] = {'allowed':False, 'reason':'Die Notfall-Freigabe läuft. Bitte ihren Abschluss abwarten.'}
            return result
        async with self.lock:
            try:
                result = snapshot(await self.comfy.resource_stats())
            except Exception:
                result = snapshot()
            if self.language_busy or self.language_pending() is not None:
                result['unload'] = {'allowed':False, 'reason':'Eine Sprachmodellaktion läuft oder ihr Abschluss ist unklar.'}
            elif self.has_unresolved_jobs():
                result['unload'] = {'allowed':False, 'reason':'MORPH hat laufende oder ungeklärte Aufträge.'}
            elif result['available']:
                result['unload'] = await self.comfy.resource_control()
            return result

    async def free_resources(self):
        self.require_language_idle()
        if self.emergency_running:
            raise UiError('active_job', 'Die Notfall-Freigabe läuft. Bitte ihren Abschluss abwarten.', status=409)
        async with self.lock:
            self.require_language_idle()
            if self.has_unresolved_jobs():
                raise UiError('active_job', 'MORPH hat laufende oder ungeklärte Aufträge. Freigabe gesperrt.', status=409)
            return await self.comfy.free_resources()

    async def emergency_release(self):
        self.require_language_idle()
        if self.lock.locked() or self.emergency_running:
            raise UiError('active_job', 'Eine Bild-, Sprach- oder Speicheraktion läuft. Notfall-Freigabe gesperrt.', status=409)
        async with self.lock:
            self.require_language_idle()
            if not self.accepting:
                raise UiError('ui_restarting', 'Die Oberfläche wird gerade neu gestartet. Notfall-Freigabe gesperrt.', status=503)
            if self.has_unresolved_jobs():
                raise UiError('active_job', 'MORPH hat laufende oder ungeklärte Aufträge. Notfall-Freigabe gesperrt.', status=409)
            self.emergency_running = True
            try:
                # A cancelled HTTP client must not release the shared gate or
                # close a handle while its native stop thread is still running.
                operation = asyncio.create_task(self.comfy.emergency_release())
                try:
                    return await asyncio.shield(operation)
                except asyncio.CancelledError:
                    while not operation.done():
                        try:
                            await asyncio.shield(operation)
                        except asyncio.CancelledError:
                            continue
                        except Exception:
                            break
                    if not operation.cancelled():
                        operation.exception()
                    raise
            finally:
                self.emergency_running = False

    async def prepare_restart(self):
        if self.language_busy:
            self.require_language_idle()
        async with self.lock:
            if any(json.loads(row[0])['state'] in ACTIVE for row in self.db.execute('SELECT data FROM jobs')):
                raise UiError('active_job', 'Die Oberfläche hat laufende oder ungeklärte Aufträge. Neustart erst nach deren Abschluss.', status=409)
            self.accepting = False

    def get_request(self, request_id):
        row = self.db.execute('SELECT data FROM jobs WHERE request_id=?', (request_key(request_id),)).fetchone()
        return json.loads(row[0]) if row else None

    async def resolve_request(self, request_id):
        request_id = request_key(request_id)
        async with self.lock:
            existing = self.get_request(request_id)
            if existing:
                return await self._refresh(existing['id'])
            # A durable closed receipt also fences a delayed original POST.
            job = {'id':str(uuid.uuid4()),'request_id':request_id,'prompt_id':request_id,'workflow_id':'unreceived','controls':{},'images':{},'state':'error','outputs':[],'cancel_requested':False,'created_at':stamp(),'updated_at':stamp(),'error':'Der Start ist nicht eingegangen. Seine Kennung wurde ohne Berechnung abgeschlossen; ein verspäteter Start wird ignoriert.','error_code':'request_not_received'}
            self.db.execute('INSERT INTO jobs VALUES (?,?,?,?)',(job['id'],request_id,request_id,json.dumps(job,ensure_ascii=False)))
            self.db.commit()
            return job

    async def create(self, request_id, workflow_id, controls, image_ids, *, project_id=None, parent_version_id=None, edit_region=None):
        request_id = request_key(request_id)
        existing = self.get_request(request_id)
        if existing:
            return existing
        if self.emergency_running:
            raise UiError('active_job', 'Die Notfall-Freigabe läuft. Bitte danach bewusst neu starten.', status=409)
        self.require_language_idle()
        async with self.lock:
            self.require_language_idle()
            if not self.accepting:
                raise UiError('ui_restarting', 'Die Oberfläche wird gerade neu gestartet. Bitte anschließend die Seite neu laden.', status=503)
            existing = self.db.execute('SELECT data FROM jobs WHERE request_id=?', (request_id,)).fetchone()
            if existing:
                return json.loads(existing[0])
            job = {'id':str(uuid.uuid4()),'request_id':request_id,'prompt_id':request_id,'client_id':str(uuid.uuid4()),'workflow_id':workflow_id,'controls':controls,'images':image_ids,'state':'preparing','phase':'preparing','outputs':[],'cancel_requested':False,'created_at':stamp(),'updated_at':stamp(),'error':None}
            try:
                self.db.execute('INSERT INTO jobs VALUES (?,?,?,?)',(job['id'],request_id,request_id,json.dumps(job, ensure_ascii=False)))
                self.db.commit()
            except sqlite3.IntegrityError:
                return json.loads(self.db.execute('SELECT data FROM jobs WHERE request_id=?', (request_id,)).fetchone()[0])
            transferring = False
            try:
                if project_id is not None or parent_version_id is not None:
                    if self.versions is None:
                        raise UiError('version_context','Die Bildhistorie ist in diesem Dienst noch nicht verfügbar.')
                    job.update(self.versions.validate_job_context(project_id,parent_version_id,workflow_id,image_ids))
                values = self.catalog.validate_controls(workflow_id, controls)
                if not isinstance(image_ids, dict):
                    raise UiError('images', 'Bitte Bilder ihren Rollen zuordnen.')
                region_mask = None
                if edit_region is not None:
                    job['edit_region'] = validate_region(self.files, workflow_id, values, image_ids,
                                                         project_id, parent_version_id, edit_region)
                    if job['edit_region']['source_sha256'] != self.versions.get_version(parent_version_id)['sha256']:
                        raise UiError('edit_region_context', 'Das Ausgangsbild hat sich seit der Auswahl des Zwischenstands geändert. Bitte den Zwischenstand erneut übernehmen und den Bereich neu zeichnen.')
                    region_mask = self.files.info(job['edit_region']['mask_media_id'])['relative_path']
                names = {}
                for role,file_id in image_ids.items():
                    info = self.files.info(file_id)
                    if info['category'] != 'input':
                        raise UiError('image_role', 'Bitte ein hochgeladenes Eingabebild verwenden.')
                    names[role] = info['relative_path']
                graph = self.catalog.build(workflow_id, values, names, region_mask=region_mask)
                for row in self.db.execute('SELECT data FROM jobs WHERE id != ?', (job['id'],)).fetchall():
                    if json.loads(row[0])['state'] in ACTIVE:
                        raise UiError('active_job', 'Es gibt bereits einen laufenden oder ungeklärten Auftrag. Bitte dessen Zustand zuerst prüfen.')
                needed = 2 * 1024**3 + values.get('width', 512) * values.get('height', 512) * values.get('frames', 1) * 16
                self.paths.require_space(needed)
                job['controls'] = values
                job['model_components'] = self.catalog.dependencies(workflow_id,values)
                job['warnings'] = await self.image_language_warnings()
                job['phase'] = 'connecting'
                self.store(job)
                await self.comfy.ensure_ready()
                job['phase'] = 'checking'
                self.store(job)
                await self.require_empty_queue()
                issues = await self.comfy.model_readiness(graph)
                if issues:
                    raise UiError('comfy_model', issues[0]['message'], issues)
                if region_mask is not None:
                    await self.comfy.require_region_nodes()
                    verify_region(self.files, job['edit_region'])
                job['phase'] = 'uploading'
                self.store(job)
                uploaded = {role:await self.comfy.upload(self.files.resolve(file_id)) for role,file_id in image_ids.items()}
                if region_mask is not None:
                    region_mask = await self.comfy.upload(self.files.resolve(job['edit_region']['mask_media_id']))
                    verify_region(self.files, job['edit_region'])
                graph = self.catalog.build(workflow_id, values, uploaded, uploaded=True, region_mask=region_mask)
                job.update(state='submitting', phase='submitting', graph=graph)
                self.store(job)
                await self.watch_progress(job)
                # Observer setup awaits I/O; preserve the final foreign-queue fence.
                await self.require_empty_queue()
                transferring = True
                if hasattr(self.comfy, 'watch_progress'):
                    confirmed = await self.comfy.submit(graph, job['prompt_id'], client_id=job['client_id'])
                else:
                    confirmed = await self.comfy.submit(graph, job['prompt_id'])
                if confirmed != job['prompt_id']:
                    raise UiError('receipt', 'Der Rechendienst hat eine andere Auftragskennung zurückgegeben.')
                job['state'] = 'queued'
                job.pop('phase', None)
                job['node_errors'] = getattr(self.comfy, 'last_node_errors', {})
            except Exception as error:
                rejected = isinstance(error, UiError) and error.code == 'comfy_rejected' and 400 <= error.status < 500
                job['state'] = 'unknown' if transferring and not rejected else 'error'
                job['error'] = str(error)
                if isinstance(error, UiError):
                    job['error_code'], job['details'] = error.code, error.details
                job.pop('phase', None)
            return self.store(job)

    async def require_empty_queue(self):
        queue = await self.comfy.queue()
        if queue['queue_running'] or queue['queue_pending']:
            raise UiError('queue_busy', 'ComfyUI bearbeitet bereits einen Auftrag oder hat eine Warteschlange. Bitte zuerst warten.', status=409)

    async def refresh(self, job_id):
        current = self.get(job_id)
        if current['state'] in {'preparing','submitting'}:
            return current
        async with self.lock:
            return await self._refresh(job_id)

    async def _refresh(self, job_id):
        job = self.get(job_id)
        if job['state'] in TERMINAL:
            if job['state'] == 'completed' and self.versions is not None and job.get('project_id'):
                self.record_versions(job)
                return self.store(job)
            return job
        try:
            receipt = await self.comfy.poll(job['prompt_id'])
            state = receipt['state']
            if state == 'absent':
                if job['cancel_requested']:
                    job['state'] = 'cancelled'
                else:
                    job['state'] = 'unknown'
                    job['error'] = 'Die Auftragskennung ist momentan weder in Warteschlange noch Verlauf nachweisbar. Es wird nichts erneut eingereicht.'
            elif state in {'queued','running','completed','cancelled','error'}:
                job['state'] = 'unknown' if state == 'completed' else state
                if 'details' in receipt:
                    job['details'] = receipt['details']
                if state == 'completed':
                    outputs = []
                    imported = job.setdefault('output_imports', {})
                    for item in receipt.get('outputs', []):
                        kind = item.get('type','output')
                        if kind not in ['output','temp'] or not isinstance(item.get('filename'), str) or not isinstance(item.get('subfolder',''), str):
                            raise UiError('output_path', 'Eine Ausgabedatei ist nicht eindeutig zugeordnet.')
                        reference = json.dumps({'filename':item['filename'],'subfolder':item.get('subfolder',''),'type':kind},sort_keys=True)
                        saved = imported.get(reference)
                        if saved:
                            try:
                                info = self.files.info(saved['id'])
                            except UiError as error:
                                if error.code not in {'file_id','missing_file'}:
                                    raise
                                saved = None
                        if not saved:
                            path = await self.comfy.download_output(item, job['prompt_id'])
                            info = self.files.register_output(path)
                            imported[reference] = info
                        if not any(output['id'] == info['id'] for output in outputs):
                            outputs.append(info)
                        job['outputs'] = outputs
                        self.store(job)
                    job['outputs'] = outputs
                    job['state'] = 'completed'
                    job['error'] = None
                    job.pop('error_code',None)
                    job.pop('details',None)
                    self.record_versions(job)
                elif state == 'error':
                    job['error'] = 'Der Rechendienst meldet einen Berechnungsfehler. Details stehen im gespeicherten Auftragsbeleg.'
            else:
                raise UiError('job_state', 'Der Rechendienst hat einen unbekannten Zustand gemeldet.')
        except UiError as error:
            if error.code in {'unsafe_path','output_path','unsafe_output','missing_file','output_format'}:
                job['state'] = 'error'
            job['error'], job['error_code'], job['details'] = error.message, error.code, error.details
        return self.store(job)

    def record_versions(self, job):
        if self.versions is None or not job.get('project_id'):
            return
        try:
            job['versions'] = self.versions.record_job_outputs(job)
            job.pop('versioning_error',None)
        except (UiError,OSError,sqlite3.Error) as error:
            job['versioning_error'] = 'Das Ergebnis ist fertig, seine Bildversion konnte noch nicht gespeichert werden. Mit „Aktualisieren“ nur die Speicherung erneut prüfen. ' + str(error)

    async def cancel(self, job_id):
        async with self.lock:
            return await self._cancel(job_id)

    async def _cancel(self, job_id):
        job = self.get(job_id)
        if job['state'] in TERMINAL:
            return job
        accepted = await self.comfy.cancel(job['prompt_id'])
        job['cancel_requested'] = job['cancel_requested'] or bool(accepted)
        job['cancel_message'] = 'Abbruch angefordert; Zustand wird weiter geprüft.' if job['cancel_requested'] else 'Der Dienst hat keinen aktiven Auftrag mit dieser Kennung abgebrochen. Bitte den Zustand prüfen.'
        return self.store(job)
