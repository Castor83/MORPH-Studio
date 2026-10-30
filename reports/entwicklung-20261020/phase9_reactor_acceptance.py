"""One explicit local ReActor acceptance action; import/--help perform no requests.

An authorized operator must announce the real single job before invoking reactor.
No service control, downloads, installs, retries, cancellation or model changes.
"""
import argparse
import asyncio
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import sys
import time
import uuid


HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location('phase9_reactor_shared_client', HERE / 'phase9_real_acceptance.py')
base = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(base)

INPUTS = {
    'source': {'path': base.PROJECT / 'input/Phase3-Referenz-Erwachsener.png',
               'sha256': '322448ad502dfc180e3abd0064a29e92acf31704c640b286b71c34353436ad1f',
               'dimensions': [1024, 1024]},
    'target': {'path': base.PROJECT / 'output/Phase3/Kontext_Identitaet_Hemdfarbe_00001_.png',
               'sha256': '19e2024ad5850e07e929f86d746089a5a6fbc04875c4e19bf0c57086b3b636d5',
               'dimensions': [1024, 1024]},
}
LIMIT = 64 * 1024**2


def inspect_png(data, dimensions):
    from PIL import Image
    with Image.open(io.BytesIO(data)) as image:
        if (image.format != 'PNG' or list(image.size) != dimensions
                or getattr(image, 'n_frames', 1) != 1):
            raise base.StopAcceptance('Expected one PNG with the bound target/source dimensions.')
        image.load()
        if image.convert('RGBA').getchannel('A').getextrema() != (255, 255):
            raise base.StopAcceptance('The synthetic acceptance image must remain opaque.')
        return {'dimensions': list(image.size), 'mode': image.mode, 'format': image.format}


def read_input(spec):
    path = spec['path']
    if path.resolve() != path or not path.is_relative_to(base.PROJECT):
        raise base.StopAcceptance('The fixed synthetic input is no longer at its bound project-local path.')
    with path.open('rb') as source:
        data = source.read(LIMIT + 1)
    if len(data) > LIMIT or hashlib.sha256(data).hexdigest() != spec['sha256']:
        raise base.StopAcceptance('The fixed synthetic input hash changed; no substitute or retry.')
    inspect_png(data, spec['dimensions'])
    return data


def validate_job(job, record):
    expected = record.get('payload')
    if (not isinstance(job, dict) or not isinstance(expected, dict)
            or expected.get('workflow_id') != 'reactor'
            or expected.get('request_id') != record.get('request_id')):
        raise base.StopAcceptance('Missing own exact ReActor request context; no further action.')
    try:
        if str(uuid.UUID(job.get('id'))) != job['id']:
            raise ValueError('job ID')
    except (ValueError, TypeError, AttributeError):
        raise base.StopAcceptance('Invalid ReActor job receipt ID.') from None
    if record.get('job_id') not in (None, job['id']):
        raise base.StopAcceptance('The saved ReActor job ID changed.')
    for key in ('request_id', 'workflow_id', 'images', 'controls'):
        if job.get(key) != expected[key]:
            raise base.StopAcceptance('ReActor receipt mismatch: ' + key + '; no retry.')
    if job.get('prompt_id') != record['request_id']:
        raise base.StopAcceptance('ReActor prompt/request binding mismatch.')
    if any(job.get(key) is not None for key in ('project_id', 'parent_version_id', 'edit_region')):
        raise base.StopAcceptance('This normal ReActor job unexpectedly contains a version/mask context.')


async def defaults(client, journal):
    rows = await client.request('GET', '/api/workflows', record=False)
    entries = [entry for entry in rows if isinstance(entry, dict) and entry.get('id') == 'reactor']
    if len(entries) != 1:
        raise base.StopAcceptance('Exactly one existing ReActor workflow is required.')
    entry = entries[0]
    if entry.get('issues'):
        journal.event('reactor_readiness_issues', issues=entry['issues'])
        raise base.StopAcceptance('ReActor components are not ready; no installation or substitute.')
    fields = entry.get('controls')
    if (not isinstance(fields, dict) or set(fields) != {'target_face', 'source_face'}
            or {role.get('id') for role in entry.get('roles', [])} != {'target', 'source'}
            or any(spec.get('kind') != 'faces' or spec.get('default') != '0' for spec in fields.values())):
        raise base.StopAcceptance('The actual ReActor catalog schema/default faces differ; inspect before running.')
    values = {name: spec['default'] for name, spec in fields.items()}
    journal.event('reactor_defaults', controls=values, dependencies=entry.get('dependencies'),
                  source='GET /api/workflows; no model selection or control override')
    return values


async def poll(client, journal, record, interval):
    started, next_resources = time.monotonic(), 0.0
    while True:
        job = await client.request('GET', '/api/jobs/' + record['job_id'])
        validate_job(job, record)
        state, progress = job.get('state'), job.get('progress') or {}
        record.update(last_state=state, last_checked_utc=base.stamp())
        journal.save()
        print(f"{base.stamp()} reactor job={job['id']} state={state} node={progress.get('node_type')} "
              f"step={progress.get('value')}/{progress.get('max')} ws={progress.get('connection')} "
              f"elapsed={time.monotonic() - started:.1f}s", flush=True)
        if time.monotonic() >= next_resources or state in base.TERMINAL:
            try:
                resources = await client.request('GET', '/api/resources')
                journal.event('reactor_resource_sample', job_id=job['id'], prompt_id=job['prompt_id'], resources=resources)
            except Exception as error:
                journal.event('reactor_resource_sample_unavailable', error_type=type(error).__name__)
            next_resources = time.monotonic() + 10
        if state in base.TERMINAL:
            record.update(stage='terminal', terminal_state=state, terminal_utc=base.stamp())
            journal.event('reactor_terminal_receipt', job=job, authority='Exact prompt_id history; WS is supplementary.')
            if state != 'completed':
                raise base.StopAcceptance('ReActor did not complete; preserve its negative receipt, no retry.')
            return job
        await asyncio.sleep(interval)


async def reactor(client, journal, interval):
    record = journal.reserve('reactor')
    # Validate the fixed synthetic originals before any upload or job mutation.
    for spec in INPUTS.values():
        read_input(spec)
    record['inputs'] = {role: {'path': str(spec['path']), 'sha256': spec['sha256'],
                               'dimensions': spec['dimensions']} for role, spec in INPUTS.items()}
    journal.save()
    controls = await defaults(client, journal)
    images = {}
    for role in ('source', 'target'):
        uploaded = await client.upload(INPUTS[role]['path'])
        if (not isinstance(uploaded, dict) or uploaded.get('kind') != 'image'
                or uploaded.get('category') != 'input'):
            raise base.StopAcceptance('ReActor upload did not confirm an input image.')
        record.setdefault('uploads', {})[role] = uploaded
        journal.save()
        data = await client.image(uploaded['id'])
        if hashlib.sha256(data).hexdigest() != INPUTS[role]['sha256']:
            raise base.StopAcceptance('ReActor uploaded ' + role + ' bytes differ from the fixed synthetic original.')
        images[role] = uploaded['id']
    if images['source'] == images['target']:
        raise base.StopAcceptance('Source and target must have separate own upload receipts.')
    request_id = str(uuid.uuid4())
    payload = {'request_id': request_id, 'workflow_id': 'reactor', 'controls': controls, 'images': images}
    record.update(stage='post_reserved', request_id=request_id, payload=payload)
    journal.save()  # Durable exact UUID and payload before the one POST /api/jobs.
    print(f'{base.stamp()} reactor: one explicit submit; original synthetic source/target; no version context', flush=True)
    try:
        job = await client.post('/api/jobs', payload)
    except Exception:
        record['stage'] = 'response_uncertain'
        journal.save()
        job = await client.request('GET', '/api/requests/' + request_id)
        if job is None:
            raise base.StopAcceptance('No own durable ReActor receipt yet. Read the saved request ID; never resubmit.')
    validate_job(job, record)
    record['job_id'] = job['id']
    journal.save()
    job = await poll(client, journal, record, interval)
    outputs = job.get('outputs')
    if not isinstance(outputs, list) or len(outputs) != 1:
        raise base.StopAcceptance('Exactly one ReActor output was not confirmed.')
    output = outputs[0]
    if (not isinstance(output, dict) or output.get('kind') != 'image' or output.get('category') != 'output'
            or output.get('id') in images.values()):
        raise base.StopAcceptance('ReActor did not return a separate output image receipt.')
    # The shared client accepts only a validated 32-hex API media ID, never the
    # returned URL, filename or a backend/local path as authority.
    data = await client.image(output['id'])
    decoded = inspect_png(data, INPUTS['target']['dimensions'])
    digest = hashlib.sha256(data).hexdigest()
    copy = base.OUTPUT / ('reactor-output-' + output['id'] + '.png')
    with copy.open('xb') as saved:
        saved.write(data)
        saved.flush()
        os.fsync(saved.fileno())
    record.update(output_media_id=output['id'], output_sha256=digest, output_dimensions=decoded['dimensions'],
                  output_copy=str(copy), output_bytes=len(data))
    journal.save()
    for spec in INPUTS.values():
        read_input(spec)
    record.update(stage='completed', finished_utc=base.stamp(), originals_unchanged=True)
    journal.event('reactor_output_decoded', media_id=output['id'], sha256=digest, **decoded,
                  quality='UNVERIFIED; similar synthetic figure variants, no different-identity or biometric claim')


async def run(args):
    import aiohttp
    if Path(__file__).resolve().parents[2] != base.PROJECT.resolve():
        raise base.StopAcceptance('ReActor helper must remain inside the authorized project report directory.')
    base.OUTPUT.mkdir(parents=True, exist_ok=True)
    lock = base.OUTPUT / 'acceptance-action.lock'
    try:
        handle = lock.open('x', encoding='utf-8')
    except FileExistsError as error:
        raise base.StopAcceptance('A shared acceptance action lock exists. Inspect PID/state; never remove automatically.') from error
    try:
        with handle:
            handle.write(json.dumps({'pid': os.getpid(), 'action': 'reactor', 'utc': base.stamp()}))
            handle.flush()
            os.fsync(handle.fileno())
        journal = base.Journal('reactor')
        journal.proof.update(harness_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                             shared_client_sha256=hashlib.sha256((HERE / 'phase9_real_acceptance.py').read_bytes()).hexdigest(),
                             identity_scope='Similar synthetic figure variants; technical regression only.')
        journal.save()
        print('Proof: ' + str(journal.path), flush=True)
        try:
            async with aiohttp.ClientSession(trust_env=False,
                    headers={'Origin': base.BASE, 'X-MORPH-Request': '1'}) as session:
                client = base.Client(session, journal, aiohttp)
                async with asyncio.timeout(args.deadline):
                    await client.verify()
                    await reactor(client, journal, args.poll_interval)
            journal.proof.update(outcome='ACTION_RETURNED', finished_utc=base.stamp())
            journal.save()
            print('ReActor action returned; visual/semantic quality remains UNVERIFIED. Proof: ' + str(journal.path), flush=True)
        except BaseException as error:
            journal.proof.update(outcome='CLIENT_STOPPED_REMOTE_STATE_UNCONFIRMED', finished_utc=base.stamp(),
                                 error_type=type(error).__name__, error=str(error),
                                 recovery='Only GET the saved own request/job receipt. No repeat action, retry, interrupt or deletion.')
            journal.save()
            raise
    finally:
        lock.unlink(missing_ok=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--action', required=True, choices=('reactor',))
    parser.add_argument('--deadline', type=int, default=900, help='Whole action deadline, 30..900 seconds.')
    parser.add_argument('--poll-interval', type=float, default=3, help='Read-only polling interval, 1..30 seconds.')
    args = parser.parse_args(argv)
    if not 30 <= args.deadline <= 900 or not 1 <= args.poll_interval <= 30:
        parser.error('deadline must be 30..900, poll interval 1..30')
    try:
        asyncio.run(run(args))
    except KeyboardInterrupt:
        print('Client ended; remote actions may continue. No cancellation or retry was sent.', file=sys.stderr, flush=True)
        return 130
    except Exception as error:
        print(type(error).__name__ + ': ' + str(error), file=sys.stderr, flush=True)
        print('Client ended; remote actions may continue. Inspect saved request/job IDs; no resubmit.', file=sys.stderr, flush=True)
        return 2
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
