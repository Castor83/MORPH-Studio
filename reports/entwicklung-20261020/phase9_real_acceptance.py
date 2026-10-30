"""Explicit, single-action MORPH acceptance client. Import and --help do no work.

This file prepares no services and installs nothing. A mutating --action is a real
local operation and must only be run by the authorized Phase-9 operator.
"""
import argparse
import asyncio
from datetime import datetime, timezone
import hashlib
import io
import json
import os
from pathlib import Path
import sys
import time
import uuid


PROJECT = Path(r'E:\MORPH-Studio')
SOURCE = PROJECT / 'ComfyUI_windows_portable/ComfyUI/input/MORPH-KREA2-synthetic-portrait-20261015.png'
BASE = 'http://127.0.0.1:8765'
OUTPUT = PROJECT / 'reports/entwicklung-20261020/phase9-live'
MODEL = 'huihui_ai/qwen3.5-abliterated:9b'
TERMINAL = {'completed', 'cancelled', 'error'}
JOB_ACTIONS = ('edit1', 'edit2', 'branch', 'cancel')
PROMPTS = {
    'edit1': 'Ändere nur das Hemd in Dunkelblau. Erhalte Gesicht, Haare, Haut, Haltung, Hintergrund und Licht.',
    'edit2': 'Ändere nur das Hemd in Dunkelgrün. Erhalte Gesicht, Haare, Haut, Haltung, Hintergrund und Licht.',
    'branch': 'Ändere nur das Hemd in Violett. Erhalte Gesicht, Haare, Haut, Haltung, Hintergrund und Licht.',
    'cancel': 'Ändere nur das Hemd in Dunkelrot. Erhalte Gesicht, Haare, Haut, Haltung, Hintergrund und Licht.',
}
SEEDS = {'edit1': 2026102001, 'edit2': 2026102002, 'branch': 2026102003, 'cancel': 2026102004}


def stamp():
    return datetime.now(timezone.utc).isoformat()


def atomic_json(path, value):
    temporary = path.with_name(path.name + '.' + uuid.uuid4().hex + '.tmp')
    try:
        with temporary.open('x', encoding='utf-8', newline='\n') as handle:
            json.dump(value, handle, ensure_ascii=False, indent=2, allow_nan=False)
            handle.write('\n')
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


class StopAcceptance(RuntimeError):
    pass


async def read_bounded(content, limit, description):
    # StreamReader.read(n) may return just the currently available prefix. Read
    # through EOF while enforcing the bound on the complete body, not a chunk.
    data = bytearray()
    async for chunk in content.iter_chunked(64 * 1024):
        if len(data) + len(chunk) > limit:
            raise StopAcceptance(description + ' exceeds the permitted size; no retry.')
        data.extend(chunk)
    return bytes(data)


class Journal:
    def __init__(self, action):
        OUTPUT.mkdir(parents=True, exist_ok=True)
        self.state_path = OUTPUT / 'acceptance-state.json'
        self.state = (json.loads(self.state_path.read_text(encoding='utf-8'))
                      if self.state_path.exists() else {'schema': 1, 'project_root': str(PROJECT), 'actions': {}})
        if self.state.get('project_root') != str(PROJECT) or self.state.get('schema') != 1:
            raise StopAcceptance('Unexpected acceptance-state schema/root; inspect locally.')
        self.action = action
        self.path = OUTPUT / (action + '-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ') + '.json')
        self.proof = {'schema': 1, 'action': action, 'started_utc': stamp(),
                      'timezone_note': 'UTC; Europe/Berlin on 2026-10-20 is UTC+02:00.',
                      'project_root': str(PROJECT), 'base_url': BASE, 'events': [],
                      'scope': 'One explicit action; no automatic suite or POST retry.',
                      'quality_acceptance': 'UNVERIFIED: requires separate image/semantic review.'}
        self.save()

    def save(self):
        atomic_json(self.path, self.proof)
        atomic_json(self.state_path, self.state)

    def event(self, kind, **fields):
        self.proof['events'].append({'at_utc': stamp(), 'kind': kind, **fields})
        self.save()

    def reserve(self, name):
        if name in self.state['actions']:
            raise StopAcceptance(f'{name} already has a durable attempt. Use observe for jobs; never resubmit blindly.')
        record = {'started_utc': stamp(), 'proof': str(self.path), 'stage': 'reserved'}
        self.state['actions'][name] = record
        self.save()
        return record


class Client:
    def __init__(self, session, journal, aiohttp):
        self.session, self.journal, self.aiohttp = session, journal, aiohttp
        self.pid = None

    async def request(self, method, path, *, payload=None, form=None, timeout=20, record=True):
        if not path.startswith('/api/') or '?' in path or '..' in path:
            raise StopAcceptance('Client accepts only fixed local API paths.')
        started = time.monotonic()
        attempt_id = str(uuid.uuid4())
        # A local UUID covers every transport attempt, including API mutations
        # without server-side request_id support. It is NOT an idempotency key.
        self.journal.event('http_attempt', attempt_id=attempt_id, method=method, path=path,
                           **({'payload': payload} if payload is not None else {}))

        async def receive():
            kwargs = {'timeout': self.aiohttp.ClientTimeout(total=timeout, connect=5), 'allow_redirects': False}
            if form is not None:
                kwargs['data'] = form
            elif payload is not None:
                kwargs['json'] = payload
            async with self.session.request(method, BASE + path, **kwargs) as response:
                raw = await read_bounded(response.content, 8 * 1024**2, 'API response')
                try:
                    envelope = json.loads(raw)
                except ValueError as error:
                    raise StopAcceptance(f'Non-JSON HTTP {response.status} for {path}; no retry.') from error
                if not isinstance(envelope, dict):
                    raise StopAcceptance(f'Invalid API envelope for {path}.')
                data = envelope.get('data')
                safe = data
                if path == '/api/settings' and isinstance(data, dict):
                    safe = {key: data.get(key) for key in ('provider', 'model_key', 'instance_id')}
                self.journal.event('http_response', attempt_id=attempt_id, method=method, path=path, status=response.status,
                                   elapsed_seconds=round(time.monotonic() - started, 3),
                                   **({'data': safe} if record else {}),
                                   **({'error_code': (envelope.get('error') or {}).get('code')}
                                      if not envelope.get('ok') and isinstance(envelope.get('error'), dict) else {}))
                if response.status < 200 or response.status >= 300 or envelope.get('ok') is not True:
                    raise StopAcceptance(f'API rejected {method} {path}: HTTP {response.status}; inspect proof, no retry.')
                return data

        task = asyncio.create_task(receive())
        try:
            while not task.done():
                done, _ = await asyncio.wait({task}, timeout=10)
                if not done:
                    print(f'{stamp()} waiting {method} {path}, {time.monotonic() - started:.0f}s; no resubmit', flush=True)
            return await task
        except BaseException:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
            self.journal.event('http_unconfirmed', attempt_id=attempt_id, method=method, path=path,
                               elapsed_seconds=round(time.monotonic() - started, 3), no_retry=True)
            raise

    async def verify(self):
        data = await self.request('GET', '/api/status')
        if (not isinstance(data, dict) or data.get('app') != 'morph-ui'
                or not isinstance(data.get('project_root'), str)
                or Path(data['project_root']).resolve() != PROJECT.resolve()
                or type(data.get('pid')) is not int or data['pid'] <= 0):
            raise StopAcceptance('API identity/root was not confirmed. No mutation allowed.')
        if self.pid is not None and data['pid'] != self.pid:
            raise StopAcceptance('UI process changed during this action. Inspect before continuing.')
        self.pid = data['pid']
        return data

    async def post(self, path, payload=None, *, form=None, timeout=180):
        await self.verify()
        return await self.request('POST', path, payload=payload, form=form, timeout=timeout)

    async def image(self, media_id):
        # IDs originate only from this project's API receipts; no user-supplied URL.
        if not isinstance(media_id, str) or len(media_id) != 32 or any(c not in '0123456789abcdef' for c in media_id):
            raise StopAcceptance('Invalid API media ID.')
        async with self.session.get(BASE + '/media/' + media_id,
                                    timeout=self.aiohttp.ClientTimeout(total=20, connect=5),
                                    allow_redirects=False) as response:
            if response.status != 200:
                raise StopAcceptance('Selected source image could not be read.')
            return await read_bounded(response.content, 64 * 1024**2, 'Selected image')

    async def upload(self, path):
        form = self.aiohttp.FormData()
        with path.open('rb') as source:
            form.add_field('file', source, filename=path.name, content_type='image/png')
            return await self.post('/api/uploads', form=form, timeout=60)


async def defaults(client):
    rows = await client.request('GET', '/api/workflows', record=False)
    entries = [row for row in rows if row.get('id') == 'krea2']
    if len(entries) != 1:
        raise StopAcceptance('Exactly one existing KREA workflow is required.')
    entry = entries[0]
    if entry.get('issues'):
        client.journal.event('krea_readiness_issues', issues=entry['issues'])
        raise StopAcceptance('KREA has reported readiness issues; no substitute model or retry.')
    fields = entry['controls']
    controls = {name: spec['default'] for name, spec in fields.items()}
    client.journal.event('krea_defaults', controls=controls, dependencies=entry.get('dependencies'),
                         model_fields={name: controls[name] for name, spec in fields.items() if spec.get('kind') == 'model'})
    return controls


async def prepare(client, journal):
    from PIL import Image
    record = journal.reserve('prepare')
    if SOURCE.resolve() != SOURCE or not SOURCE.is_file():
        raise StopAcceptance('The known project-local synthetic portrait is unavailable.')
    original = SOURCE.read_bytes()
    with Image.open(io.BytesIO(original)) as source:
        source.load()
        if source.size != (1024, 1024) or source.convert('RGBA').getchannel('A').getextrema() != (255, 255):
            raise StopAcceptance('Known portrait must remain opaque, 1024x1024.')
        rgb = source.convert('RGB')
        values = bytearray(1024 * 1024)
        for index, (red, green, blue) in enumerate(rgb.getdata()):
            if index // 1024 > 640 and red > 1.6 * green and red > 1.4 * blue and red > 35:
                values[index] = 255
        mask = Image.frombytes('L', rgb.size, bytes(values))
        if mask.getbbox() is None:
            raise StopAcceptance('Conservative red-shirt mask is empty; inspect the input.')
        mask_path = OUTPUT / ('shirt-mask-' + uuid.uuid4().hex + '.png')
        with mask_path.open('xb') as handle:
            mask.save(handle, format='PNG')
        record.update(source_path=str(SOURCE), source_sha256=hashlib.sha256(original).hexdigest(),
                      mask_path=str(mask_path), mask_sha256=hashlib.sha256(mask_path.read_bytes()).hexdigest(),
                      dimensions=[1024, 1024], mask_bounds=list(mask.getbbox()),
                      white_pixels=values.count(255), mask_rule='y>640; R>1.6G; R>1.4B; R>35; opaque L PNG')
        journal.save()
    upload = await client.upload(SOURCE)
    record['original_upload'] = upload
    journal.save()
    if hashlib.sha256(await client.image(upload['id'])).hexdigest() != record['source_sha256']:
        raise StopAcceptance('Uploaded portrait differs from the mask source; no project/run.')
    mask_upload = await client.upload(mask_path)
    record['mask_upload'] = mask_upload
    journal.save()
    if hashlib.sha256(await client.image(mask_upload['id'])).hexdigest() != record['mask_sha256']:
        raise StopAcceptance('Uploaded mask differs from the saved L PNG; no project/run.')
    request_id = str(uuid.uuid4())
    project_id = uuid.uuid5(uuid.NAMESPACE_URL, 'morph-image-project:' + request_id).hex
    record.update(request_id=request_id, project_id=project_id, stage='project_post_reserved')
    journal.save()
    try:
        project = await client.post('/api/image-projects', {'request_id': request_id,
                                    'original_media_id': upload['id'], 'name': 'LIVEABNAHME20Oct-' + request_id[:8]})
    except Exception:
        # Deterministic project ID permits read-only recovery; never POST twice.
        record['stage'] = 'project_response_uncertain'
        journal.save()
        project = await client.request('GET', '/api/image-projects/' + project_id)
    if project.get('id') != project_id:
        raise StopAcceptance('Project receipt ID mismatch.')
    record.update(stage='prepared', original_version_id=project['original_version_id'])
    journal.state.update(project_id=project_id, original_version_id=project['original_version_id'],
                         mask_media_id=mask_upload['id'], mask_path=str(mask_path), mask_dimensions=[1024, 1024],
                         mask_sha256=record['mask_sha256'])
    journal.event('prepared', project=project, source_sha256=record['source_sha256'],
                  mask_sha256=record['mask_sha256'], no_computation=True)


async def receipt(client, record):
    job = await client.request('GET', '/api/requests/' + record['request_id'])
    if not job:
        raise StopAcceptance('No durable job receipt yet. No resubmit; inspect again with observe.')
    validate_job(job, record)
    record['job_id'] = job['id']
    client.journal.save()
    return job


def validate_job(job, record):
    """Only the saved exact request may authorize observation or cancellation."""
    expected = record.get('payload')
    if not isinstance(job, dict) or not isinstance(expected, dict):
        raise StopAcceptance('Missing exact saved job context; inspect locally, no further mutation.')
    try:
        if str(uuid.UUID(job.get('id'))) != job['id']:
            raise ValueError('job ID')
    except (ValueError, TypeError, AttributeError):
        raise StopAcceptance('Invalid job receipt ID; no further mutation.') from None
    if record.get('job_id') not in (None, job['id']):
        raise StopAcceptance('Saved job ID changed; no further mutation.')
    for key in ('request_id', 'workflow_id', 'project_id', 'parent_version_id', 'images', 'controls'):
        if job.get(key) != expected.get(key):
            raise StopAcceptance('Job receipt context mismatch: ' + key + '; no further mutation.')
    if job.get('prompt_id') != record['request_id']:
        raise StopAcceptance('Job prompt/request binding mismatch; no further mutation.')
    region = job.get('edit_region')
    if not isinstance(region, dict) or any(region.get(key) != value for key, value in expected['edit_region'].items()):
        raise StopAcceptance('Job mask/source/parent context mismatch; no further mutation.')
    for key in ('mask_sha256', 'source_sha256'):
        if record.get(key) and region.get(key) != record[key]:
            raise StopAcceptance('Job input bytes differ from the saved ' + key + '; no further mutation.')


def validate_completed_version(job, record):
    versions = job.get('versions')
    if job.get('versioning_error') or not isinstance(versions, list) or len(versions) != 1:
        raise StopAcceptance('Exactly one persisted completed image version was not proven.')
    version, expected = versions[0], record['payload']
    if (not isinstance(version, dict) or version.get('project_id') != expected['project_id']
            or version.get('parent_version_id') != expected['parent_version_id']
            or version.get('status') != 'completed'
            or version.get('metadata', {}).get('workflow_id') != expected['workflow_id']
            or not isinstance(version.get('id'), str) or len(version['id']) != 32
            or any(char not in '0123456789abcdef' for char in version['id'])):
        raise StopAcceptance('Completed version project/parent/workflow binding mismatch.')


async def poll(client, journal, record, action, interval):
    started = time.monotonic()
    next_resources = 0.0
    while True:
        job = await client.request('GET', '/api/jobs/' + record['job_id'])
        validate_job(job, record)
        if job.get('request_id') != record['request_id'] or job.get('project_id') != journal.state.get('project_id'):
            raise StopAcceptance('Job ownership/context mismatch.')
        record.update(last_state=job.get('state'), last_checked_utc=stamp())
        progress = job.get('progress', {})
        print(f"{stamp()} {action} job={job['id']} state={job.get('state')} node={progress.get('node_type')} "
              f"step={progress.get('value')}/{progress.get('max')} percent={progress.get('percent')} "
              f"ws={progress.get('connection')} elapsed={time.monotonic() - started:.1f}s", flush=True)
        journal.save()
        if time.monotonic() >= next_resources or job.get('state') in TERMINAL:
            try:
                resources = await client.request('GET', '/api/resources')
                journal.event('job_resource_sample', job_id=job['id'], prompt_id=job.get('prompt_id'), resources=resources)
            except Exception as error:
                journal.event('resource_sample_unavailable', error_type=type(error).__name__)
            next_resources = time.monotonic() + 10
        if job.get('state') in TERMINAL:
            journal.event('terminal_history_receipt', job=job,
                          authority='Job refresh uses exact prompt_id history; WS percent is supplementary.')
            if action != 'cancel' and job['state'] == 'completed':
                validate_completed_version(job, record)
            record.update(stage='terminal', terminal_state=job['state'], finished_utc=stamp(),
                          version_ids=[version['id'] for version in job.get('versions', [])],
                          outputs=job.get('outputs', []))
            if action == 'cancel':
                record['cancel_test_result'] = ('PASS' if job['state'] == 'cancelled' else
                    'RACE_COMPLETED' if job['state'] == 'completed' else 'FAIL')
                journal.save()
                if record['cancel_test_result'] != 'PASS':
                    raise StopAcceptance('Cancellation was not proven. Terminal state retained; no automatic rerun.')
            elif job['state'] != 'completed':
                raise StopAcceptance('A completed, persisted image version was not proven. Inspect proof.')
            return job
        await asyncio.sleep(interval)


async def submit_edit(client, journal, action, interval):
    from PIL import Image
    if (not journal.state.get('project_id') or not journal.state.get('mask_media_id')
            or not journal.state.get('mask_sha256')):
        raise StopAcceptance('Run the separate prepare action first.')
    if action == 'edit1':
        parent_id = journal.state['original_version_id']
    else:
        previous = journal.state['actions'].get('edit1', {})
        if previous.get('terminal_state') != 'completed' or len(previous.get('version_ids', [])) != 1:
            raise StopAcceptance('edit1 must have exactly one confirmed completed version.')
        parent_id = previous['version_ids'][0]
    record = journal.reserve(action)
    parent = await client.request('GET', '/api/image-versions/' + parent_id)
    if parent.get('project_id') != journal.state['project_id']:
        raise StopAcceptance('Parent project mismatch.')
    selected = await client.post('/api/image-versions/' + parent_id + '/input', {})
    if selected.get('parent_version_id') != parent_id or selected.get('project_id') != journal.state['project_id']:
        raise StopAcceptance('Explicit parent-input selection was not confirmed.')
    image_id = selected['image']['id']
    image_data = await client.image(image_id)
    with Image.open(io.BytesIO(image_data)) as image:
        image.load()
        if list(image.size) != journal.state['mask_dimensions']:
            raise StopAcceptance('Parent geometry differs from mask; no run.')
    if hashlib.sha256(image_data).hexdigest() != parent['sha256']:
        raise StopAcceptance('Selected input does not match its immutable parent.')
    if hashlib.sha256(await client.image(journal.state['mask_media_id'])).hexdigest() != journal.state['mask_sha256']:
        raise StopAcceptance('Uploaded mask bytes changed since preparation; no run.')
    controls = await defaults(client)
    controls.update(width=768, height=768, steps=8, ref_boost=1, seed=SEEDS[action], prompt=PROMPTS[action])
    request_id = str(uuid.uuid4())
    payload = {'request_id': request_id, 'workflow_id': 'krea2', 'controls': controls,
               'images': {'image': image_id}, 'project_id': journal.state['project_id'],
               'parent_version_id': parent_id,
               'edit_region': {'mask_media_id': journal.state['mask_media_id'],
                               'source_media_id': image_id, 'parent_version_id': parent_id}}
    record.update(stage='post_reserved', request_id=request_id, parent_version_id=parent_id,
                   source_media_id=image_id, source_sha256=parent['sha256'],
                   mask_sha256=journal.state['mask_sha256'], payload=payload)
    journal.save()  # Durable UUID and exact payload BEFORE the sole submit attempt.
    print(f'{stamp()} {action}: one KREA submit, 768x768, 8 steps, seed={SEEDS[action]}, parent={parent_id}', flush=True)
    try:
        job = await client.post('/api/jobs', payload)
    except Exception:
        record['stage'] = 'response_uncertain'
        journal.save()
        job = await receipt(client, record)  # GET only, never another POST /api/jobs.
    validate_job(job, record)
    record['job_id'] = job['id']
    journal.save()
    if action == 'cancel':
        record['cancel_attempt_utc'] = stamp()
        journal.save()
        # This path is the only cancellation; there is no /interrupt fallback.
        await client.post('/api/jobs/' + job['id'] + '/cancel', {})
    return await poll(client, journal, record, action, interval)


async def language(client, journal):
    record = journal.reserve('language')
    settings = await client.request('GET', '/api/settings')
    if (settings.get('provider') != 'ollama' or settings.get('model_key') != MODEL
            or settings.get('instance_id') not in ('', MODEL)):
        raise StopAcceptance('Current selected Ollama model/instance differs from the agreed 9B model.')
    models = await client.request('GET', '/api/models')
    choices = [model for model in models if model.get('key') == MODEL]
    if len(choices) != 1:
        raise StopAcceptance('Agreed model is absent from installed-model inventory. No downloads.')
    loaded = {instance['id'] for model in models for instance in model.get('loaded_instances', [])}
    record['loaded_before'] = sorted(loaded)
    journal.save()
    if MODEL not in loaded:
        if loaded:
            raise StopAcceptance('Other loaded models exist; preserve them and resolve manually before loading.')
        record.update(load_attempt_utc=stamp(), load_instance_id=MODEL)
        journal.save()
        result = await client.post('/api/models/load', {'model_key': MODEL}, timeout=210)
        if result.get('instance_id') != MODEL or result.get('status') != 'loaded':
            raise StopAcceptance('Own model load was not confirmed; inspect state, no retry/unload guess.')
        record['loaded_by_this_action'] = True
        journal.save()
    after = await client.request('GET', '/api/models')
    if not any(model.get('key') == MODEL and any(instance.get('id') == MODEL
               for instance in model.get('loaded_instances', [])) for model in after):
        raise StopAcceptance('The selected model is not confirmed loaded.')
    controls = await defaults(client)
    controls.update(width=768, height=768, steps=8, ref_boost=1, seed=SEEDS['edit1'])
    instruction = 'Nur das Hemd dunkelblau färben. Gesicht, Haare, Haut, Hintergrund und Haltung erhalten.'
    payload = {'instance_id': MODEL, 'workflow_id': 'krea2', 'instruction': instruction, 'controls': controls}
    record.update(stage='proposal_attempted', instruction_utf8_bytes=len(instruction.encode('utf-8')),
                  proposal_attempt_utc=stamp())
    journal.save()
    result = await client.post('/api/tool-proposals', payload, timeout=150)
    journal.event('language_proposal', result=result, adopted=False, job_submitted=False,
                  semantic_quality='UNVERIFIED: operator must assess German, chosen tool and edit preservation.')
    record['stage'] = 'proposal_received'
    # No finally mutation: timeout, cancellation and schema errors must preserve
    # the original evidence. A consciously invoked language-unload is separate.
    journal.save()


async def language_unload(client, journal):
    own = journal.state['actions'].get('language', {})
    record = journal.reserve('language-unload')
    settings = await client.request('GET', '/api/settings')
    if settings.get('provider') != 'ollama' or settings.get('model_key') != MODEL:
        raise StopAcceptance('Selected provider/model changed; no automatic settings correction or unload.')
    status = await client.request('GET', '/api/status')
    language_state = status.get('language_state', {})
    uncertain = language_state.get('uncertain_instances')
    if language_state.get('busy') is not False or not isinstance(uncertain, list):
        raise StopAcceptance('Language state is busy or unverified; no unload attempt.')
    if uncertain and uncertain != [MODEL]:
        raise StopAcceptance('A different uncertain model action exists; preserve it.')
    own_unknown_load = (uncertain == [MODEL] and own.get('load_attempt_utc')
                        and own.get('load_instance_id') == MODEL and own.get('loaded_before') == [])
    if own.get('loaded_by_this_action') is not True and not own_unknown_load:
        raise StopAcceptance('No confirmed own load or exact saved own uncertain load. Preserve existing models.')
    models = await client.request('GET', '/api/models')
    loaded = {instance['id'] for model in models for instance in model.get('loaded_instances', [])}
    record.update(loaded_before=sorted(loaded), stage='state_checked')
    journal.save()
    if MODEL not in loaded and not uncertain:
        record.update(stage='already_absent', unload_confirmed=False)
        journal.event('own_language_model_already_absent', model=MODEL, unload_sent=False)
        return
    record['stage'] = 'unload_attempted'
    journal.save()
    response = await client.post('/api/models/unload', {'instance_id': MODEL}, timeout=210)
    if not isinstance(response, dict) or response.get('unloaded') is not True:
        raise StopAcceptance('Own model unload response was not confirmed; no retry.')
    after = await client.request('GET', '/api/models')
    absent = not any(instance.get('id') == MODEL for model in after for instance in model.get('loaded_instances', []))
    final_status = await client.request('GET', '/api/status')
    final_language = final_status.get('language_state', {})
    absent = absent and final_language.get('busy') is False and final_language.get('uncertain_instances') == []
    record.update(stage='unloaded' if absent else 'unconfirmed', unload_confirmed=absent)
    journal.save()
    if not absent:
        raise StopAcceptance('Fresh inventory did not confirm own model absence; no retry.')


async def free_resources(client, journal):
    record = journal.reserve('free')
    for name in JOB_ACTIONS:
        own = journal.state['actions'].get(name, {})
        if own.get('request_id'):
            job = await receipt(client, own)
            current = await client.request('GET', '/api/jobs/' + job['id'])
            if current.get('state') not in TERMINAL:
                raise StopAcceptance('An own job is active/unclear; resource release is blocked.')
    before = await client.request('GET', '/api/resources')
    if before.get('unload', {}).get('allowed') is not True:
        raise StopAcceptance('Server has not confirmed managed ownership, empty queue and no unresolved jobs.')
    record['stage'] = 'free_attempted'
    journal.save()
    response = await client.post('/api/resources/free', {})
    journal.event('free_async_receipt', response=response, completion_claimed=False)
    await asyncio.sleep(2)
    after = await client.request('GET', '/api/resources')
    record['stage'] = 'requested'
    journal.event('free_later_read', resources=after, completion_claimed=False)


async def run(args):
    # Runtime dependencies are imported only after argparse has accepted an action.
    import aiohttp
    if Path(__file__).resolve().parents[2] != PROJECT.resolve():
        raise StopAcceptance('Harness must remain under the authorized E: project report directory.')
    OUTPUT.mkdir(parents=True, exist_ok=True)
    lock = OUTPUT / 'acceptance-action.lock'
    try:
        handle = lock.open('x', encoding='utf-8')
    except FileExistsError as error:
        raise StopAcceptance('Another action or interrupted action lock exists. Inspect it; no automatic lock removal.') from error
    try:
        with handle:
            handle.write(json.dumps({'pid': os.getpid(), 'action': args.action, 'utc': stamp()}))
            handle.flush()
            os.fsync(handle.fileno())
        journal = Journal(args.action)
        journal.proof['harness_sha256'] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
        journal.proof['source_sha256'] = {name: hashlib.sha256((PROJECT / 'ui/morph_ui' / name).read_bytes()).hexdigest()
                                        for name in ('server.py', 'jobs.py', 'versions.py', 'edit_region.py', 'catalog.py')}
        journal.save()
        print(f'Proof: {journal.path}', flush=True)
        try:
            async with aiohttp.ClientSession(trust_env=False,
                    headers={'Origin': BASE, 'X-MORPH-Request': '1'}) as session:
                client = Client(session, journal, aiohttp)
                async with asyncio.timeout(args.deadline):
                    await client.verify()
                    if args.action == 'prepare':
                        await prepare(client, journal)
                    elif args.action in JOB_ACTIONS:
                        await submit_edit(client, journal, args.action, args.poll_interval)
                    elif args.action == 'language':
                        await language(client, journal)
                    elif args.action == 'language-unload':
                        await language_unload(client, journal)
                    elif args.action == 'resources':
                        await client.request('GET', '/api/resources')
                    elif args.action == 'free':
                        await free_resources(client, journal)
                    elif args.action == 'observe':
                        record = journal.state['actions'].get(args.target_action, {})
                        if not record.get('request_id'):
                            raise StopAcceptance('The named own action has no saved request UUID.')
                        await receipt(client, record)
                        await poll(client, journal, record, args.target_action, args.poll_interval)
            journal.proof.update(outcome='ACTION_RETURNED', finished_utc=stamp())
            journal.save()
            print(f'{args.action}: action returned; image/semantic acceptance remains separate. Proof: {journal.path}', flush=True)
        except BaseException as error:
            journal.proof.update(outcome='CLIENT_STOPPED_REMOTE_STATE_UNCONFIRMED', finished_utc=stamp(),
                                 error_type=type(error).__name__, error=str(error),
                                 recovery='No automatic POST retry or interrupt. Inspect saved IDs; use observe for an own job.')
            journal.save()
            raise
    finally:
        lock.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--action', required=True,
                        choices=('prepare', *JOB_ACTIONS, 'language', 'language-unload', 'resources', 'free', 'observe'),
                        help='Exactly one explicit action; there is no default computation or suite.')
    parser.add_argument('--target-action', choices=JOB_ACTIONS,
                        help='Required only with observe: read/poll an already saved own job, never resubmit.')
    parser.add_argument('--deadline', type=int, default=900, help='Whole action deadline, 30..900 seconds (default 900).')
    parser.add_argument('--poll-interval', type=float, default=3, help='Read-only polling interval, 1..30 seconds.')
    args = parser.parse_args()
    if (args.action == 'observe') != (args.target_action is not None):
        parser.error('--target-action is required exactly with --action observe')
    if not 30 <= args.deadline <= 900 or not 1 <= args.poll_interval <= 30:
        parser.error('deadline must be 30..900, poll interval 1..30')
    try:
        asyncio.run(run(args))
    except KeyboardInterrupt:
        print('Client stopped; no remote cancellation was sent. Inspect saved job/request IDs.', file=sys.stderr, flush=True)
        return 130
    except Exception as error:
        print(f'{type(error).__name__}: {error}', file=sys.stderr, flush=True)
        print('Client ended; remote actions may continue. No remote cancellation or automatic retry was sent.',
              file=sys.stderr, flush=True)
        return 2
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
