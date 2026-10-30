"""Twelve-connection manifest-pinned ComfyUI weight downloader; run only after the old writer has exited.

Only manifest-pinned files are accepted. A .part with a range journal MUST NOT be
resumed with curl --continue-at: its length may include unconfirmed holes.
No dependencies outside Python's standard library. --self-test uses localhost.
"""

import argparse
from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED
import ctypes
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import re
import shutil
import tempfile
import threading
import time
import urllib.error
import urllib.parse
import urllib.request


REPORT_ROOT = Path(__file__).resolve().parent
AUTHORIZED_REPORT_ROOT = Path(r'D:\MORPH-Studio\reports\wan-lmstudio')
AUTHORIZED_MODEL_ROOT = Path(r'D:\MORPH-Studio\ComfyUI_windows_portable\ComfyUI\models')
RESERVE_BYTES = 5_000_000_000
BLOCK_BYTES = 64 * 1024 * 1024
BUFFER_BYTES = 128 * 1024
STATE_HEADROOM_BYTES = 2 * 1024 * 1024
WORKERS = 12
ATTEMPTS = 3
REQUEST_DEADLINE = 180


class DownloadError(RuntimeError):
    """Deliberately excludes redirect URLs and credentials from error text."""


def safe_error(error):
    if isinstance(error, DownloadError):
        return str(error)
    if isinstance(error, urllib.error.HTTPError):
        return 'Range request failed with HTTP ' + str(error.code)
    if isinstance(error, urllib.error.URLError):
        return 'Range connection failed (' + type(error.reason).__name__ + ')'
    return type(error).__name__ + ': local operation failed'


def atomic_json(path, value):
    temporary = path.with_name(path.name + '.tmp')
    if not path.resolve().is_relative_to(REPORT_ROOT) or not temporary.resolve().is_relative_to(REPORT_ROOT):
        raise DownloadError('JSON output escapes the authorized report folder')
    with temporary.open('w', encoding='utf-8', newline='\n') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write('\n')
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


def exclusive_open(path):
    """Deny shared read/write; allow rename while holding the same file handle."""
    if os.name == 'nt':
        import msvcrt
        from ctypes import wintypes
        kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        create = kernel.CreateFileW
        create.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                           wintypes.LPVOID, wintypes.DWORD, wintypes.DWORD,
                           wintypes.HANDLE]
        create.restype = wintypes.HANDLE
        handle = create(str(path), 0x80000000 | 0x40000000, 4, None, 4, 0x80, None)
        if handle == ctypes.c_void_p(-1).value:
            code = ctypes.get_last_error()
            if code in (32, 33):
                raise DownloadError('Partial file is still open by another process; no process stopped')
            raise DownloadError('Exclusive partial-file open failed (Windows error ' + str(code) + ')')
        try:
            descriptor = msvcrt.open_osfhandle(handle, os.O_RDWR | os.O_BINARY)
        except BaseException:
            kernel.CloseHandle.argtypes = [wintypes.HANDLE]
            kernel.CloseHandle(handle)
            raise
        return os.fdopen(descriptor, 'r+b', buffering=0)
    # The production target is Windows. This branch permits isolated POSIX tests.
    import fcntl
    descriptor = os.open(path, os.O_RDWR | os.O_CREAT, 0o600)
    try:
        fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return os.fdopen(descriptor, 'r+b', buffering=0)
    except BaseException:
        os.close(descriptor)
        raise DownloadError('Partial-file lock unavailable; no process stopped')


def digest_region(stream, start, length):
    stream.seek(start)
    digest = hashlib.sha256()
    remaining = length
    while remaining:
        data = stream.read(min(BUFFER_BYTES, remaining))
        if not data:
            raise DownloadError('Partial file is shorter than a journal-confirmed region')
        digest.update(data)
        remaining -= len(data)
    return digest.hexdigest()


def check_file(path, entry):
    if path.stat().st_size != entry['bytes']:
        raise DownloadError('File length differs from pinned source metadata')
    with path.open('rb') as stream:
        digest = digest_region(stream, 0, entry['bytes'])
    if digest != entry['sha256']:
        raise DownloadError('SHA256 differs from pinned source metadata')
    return digest


class RangeDownload:
    def __init__(self, partial, journal_path, entry, revision, disk_root,
                 block_bytes=BLOCK_BYTES, reserve=RESERVE_BYTES,
                 disk_free=None, retry_delay=1.0):
        self.partial = partial
        self.journal_path = journal_path
        self.entry = entry
        self.total = entry['bytes']
        self.disk_root = disk_root
        self.reserve = reserve
        self.disk_free = disk_free or (lambda: shutil.disk_usage(disk_root).free)
        self.retry_delay = retry_delay
        self.lock = threading.RLock()
        self.stop = threading.Event()
        self.stream = None
        self.identity = {'source_url': entry['url'], 'revision': revision,
                         'bytes': self.total, 'sha256': entry['sha256'],
                         'partial': str(partial.resolve())}
        try:
            if not journal_path.resolve().is_relative_to(REPORT_ROOT):
                raise DownloadError('Range journal escapes the authorized report folder')
            # Acquire exclusive ownership BEFORE reading length or changing a journal.
            self.stream = exclusive_open(partial)
            actual_length = os.fstat(self.stream.fileno()).st_size
            if actual_length > self.total:
                raise DownloadError('Partial file exceeds pinned source length')
            self.require_space(max(0, self.total - actual_length))
            if journal_path.exists():
                self.journal = json.loads(journal_path.read_text(encoding='utf-8'))
                self.validate_journal(actual_length)
            else:
                self.journal = {'version': 1, 'identity': self.identity,
                                'prefix_bytes': actual_length,
                                'prefix_sha256': digest_region(self.stream, 0, actual_length),
                                'block_bytes': block_bytes, 'completed': {},
                                'finalized': False}
                atomic_json(journal_path, self.journal)
            self.prefix = self.journal['prefix_bytes']
            self.block_bytes = self.journal['block_bytes']
            self.count = (self.total - self.prefix + self.block_bytes - 1) // self.block_bytes
        except BaseException:
            self.close()
            raise

    def require_space(self, additional):
        if self.disk_free() < self.reserve + additional + STATE_HEADROOM_BYTES:
            raise DownloadError('Insufficient free space while preserving the 5 GB reserve')

    def bounds(self, index):
        start = self.prefix + index * self.block_bytes
        return start, min(start + self.block_bytes, self.total) - 1

    def validate_journal(self, actual_length):
        state = self.journal
        if state.get('version') != 1 or state.get('identity') != self.identity:
            raise DownloadError('Range journal belongs to different pinned metadata')
        prefix = state.get('prefix_bytes')
        block = state.get('block_bytes')
        completed = state.get('completed')
        if type(prefix) is not int or not 0 <= prefix <= self.total:
            raise DownloadError('Invalid journal prefix')
        if type(block) is not int or not 1024 <= block <= BLOCK_BYTES:
            raise DownloadError('Invalid journal block size')
        if not isinstance(completed, dict) or actual_length < prefix:
            raise DownloadError('Invalid journal regions or truncated partial file')
        if digest_region(self.stream, 0, prefix) != state.get('prefix_sha256'):
            raise DownloadError('Original contiguous prefix changed since journal creation')
        count = (self.total - prefix + block - 1) // block
        for key, digest in completed.items():
            if not isinstance(key, str) or not key.isdigit() or str(int(key)) != key:
                raise DownloadError('Invalid journal block index')
            index = int(key)
            if not 0 <= index < count or not isinstance(digest, str) or not re.fullmatch('[0-9a-f]{64}', digest):
                raise DownloadError('Invalid journal block confirmation')
            start = prefix + index * block
            length = min(block, self.total - start)
            if actual_length < start + length or digest_region(self.stream, start, length) != digest:
                raise DownloadError('Journal-confirmed block is missing or changed')

    def confirmed_bytes(self):
        with self.lock:
            return self.prefix + sum(self.bounds(int(key))[1] - self.bounds(int(key))[0] + 1
                                     for key in self.journal['completed'])

    def request_once(self, index):
        start, end = self.bounds(index)
        expected = end - start + 1
        # Only the canonical pinned URL is retained, never a signed redirect URL.
        parsed = urllib.parse.urlsplit(self.entry['url'])
        query = urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
        # Distinct resolve cache keys prevent a redirect minted for one Range
        # from being reused by another Range. The journal keeps the canonical URL.
        query = [(key, value) for key, value in query
                 if key not in ('download', 'range_start', 'range_end')]
        query += [('download', 'true'), ('range_start', str(start)), ('range_end', str(end))]
        url = urllib.parse.urlunsplit(parsed._replace(query=urllib.parse.urlencode(query)))
        request = urllib.request.Request(url, headers={
            'Range': 'bytes=' + str(start) + '-' + str(end),
            'Accept-Encoding': 'identity', 'User-Agent': 'pinned-comfy-model-range-download/1.0'})
        deadline = time.monotonic() + REQUEST_DEADLINE
        with urllib.request.urlopen(request, timeout=30) as response:
            if response.status != 206:
                raise DownloadError('Server did not return HTTP 206 for requested range')
            header = response.headers.get('Content-Range', '')
            if header != 'bytes ' + str(start) + '-' + str(end) + '/' + str(self.total):
                raise DownloadError('Content-Range differs from the exact requested range')
            encoding = response.headers.get('Content-Encoding', 'identity').lower()
            if encoding != 'identity':
                raise DownloadError('Compressed HTTP range response refused')
            length_header = response.headers.get('Content-Length')
            if length_header is not None and length_header != str(expected):
                raise DownloadError('Content-Length differs from requested byte count')
            received = 0
            digest = hashlib.sha256()
            while received < expected:
                if self.stop.is_set():
                    raise DownloadError('Range operation cancelled after another failure')
                if time.monotonic() >= deadline:
                    raise DownloadError('Range request exceeded its bounded time limit')
                data = response.read(min(BUFFER_BYTES, expected - received))
                if not data:
                    raise DownloadError('Range response ended before all requested bytes arrived')
                with self.lock:
                    current_length = os.fstat(self.stream.fileno()).st_size
                    # An offset write can allocate the entire intervening hole on NTFS.
                    growth = max(len(data), start + received + len(data) - current_length)
                    self.require_space(growth)
                    self.stream.seek(start + received)
                    if self.stream.write(data) != len(data):
                        raise DownloadError('Partial-file write did not persist all bytes')
                digest.update(data)
                received += len(data)
            if response.read(1):
                raise DownloadError('Range response exceeded its requested byte count')
        with self.lock:
            self.stream.flush()
            os.fsync(self.stream.fileno())
            self.require_space(0)
            self.journal['completed'][str(index)] = digest.hexdigest()
            atomic_json(self.journal_path, self.journal)

    def download_block(self, index):
        for attempt in range(ATTEMPTS):
            try:
                self.request_once(index)
                return
            except DownloadError as error:
                # Only a transient short transport is retried; metadata and ownership remain strict.
                if str(error) != 'Range response ended before all requested bytes arrived' or self.stop.is_set() or attempt + 1 == ATTEMPTS:
                    raise
                if self.stop.wait(self.retry_delay * (attempt + 1)):
                    raise DownloadError('Range retry cancelled')
            except Exception as error:
                if self.stop.is_set() or attempt + 1 == ATTEMPTS:
                    raise DownloadError(safe_error(error)) from None
                if self.stop.wait(self.retry_delay * (attempt + 1)):
                    raise DownloadError('Range retry cancelled')

    def download(self):
        pending_indices = iter(index for index in range(self.count)
                               if str(index) not in self.journal['completed'])
        with ThreadPoolExecutor(max_workers=WORKERS) as executor:
            running = set()
            for _ in range(WORKERS):
                index = next(pending_indices, None)
                if index is not None:
                    running.add(executor.submit(self.download_block, index))
            previous = self.confirmed_bytes()
            previous_time = time.monotonic()
            try:
                while running:
                    done, running = wait(running, timeout=1, return_when=FIRST_COMPLETED)
                    for future in done:
                        future.result()
                        index = next(pending_indices, None)
                        if index is not None:
                            running.add(executor.submit(self.download_block, index))
                    now = time.monotonic()
                    if now - previous_time >= 20:
                        current = self.confirmed_bytes()
                        speed = (current - previous) / (now - previous_time)
                        print('CONFIRMED %.1f%% %.2f/%.2f GB %.1f MB/s' %
                              (current * 100 / self.total, current / 1e9,
                               self.total / 1e9, speed / 1e6), flush=True)
                        previous, previous_time = current, now
            except BaseException:
                self.stop.set()
                for future in running:
                    future.cancel()
                raise
        if self.confirmed_bytes() != self.total:
            raise DownloadError('Not every source byte is journal-confirmed')

    def verify_open(self):
        if self.confirmed_bytes() != self.total:
            raise DownloadError('Final verification refused: missing confirmed ranges')
        with self.lock:
            self.stream.flush()
            os.fsync(self.stream.fileno())
            if os.fstat(self.stream.fileno()).st_size != self.total:
                raise DownloadError('Final partial-file length differs from pinned size')
            digest = digest_region(self.stream, 0, self.total)
            if digest != self.entry['sha256']:
                raise DownloadError('SHA256 differs from pinned source metadata')
            self.require_space(0)
            return digest

    def close(self):
        if self.stream is not None:
            self.stream.close()
            self.stream = None


MANIFEST_SHA256 = '411455936b3782329a151dd8290f79e3f91644d0c07b2b795931e6c3e3aad724'

def validate_manifest(index):
    if REPORT_ROOT != AUTHORIZED_REPORT_ROOT.resolve() or REPORT_ROOT.drive.upper() != 'D:':
        raise DownloadError('Helper must run from the authorized D: report folder')
    manifest_path = REPORT_ROOT / 'models-manifest.json'
    raw = manifest_path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != MANIFEST_SHA256:
        raise DownloadError('Installation manifest changed after helper preparation')
    plan = json.loads(raw.decode('utf-8-sig'))
    if not isinstance(plan, list) or len(plan) != 5 or not 0 <= index < len(plan):
        raise DownloadError('Model index is outside the authorized five-file manifest')
    model_root = AUTHORIZED_MODEL_ROOT.resolve()
    if model_root.drive.upper() != 'D:':
        raise DownloadError('Model root resolves outside authorized D: drive')
    entry = dict(plan[index])
    if type(entry.get('bytes')) is not int or entry['bytes'] < 4:
        raise DownloadError('Invalid pinned file size')
    if not re.fullmatch('[0-9a-f]{64}', entry.get('sha256', '')):
        raise DownloadError('Invalid pinned SHA256')
    name = entry.get('name', '')
    if not isinstance(name, str) or not name or Path(name).name != name or '/' in name or '\\' in name or ':' in name or not name.lower().endswith(('.safetensors', '.pth')):
        raise DownloadError('Invalid authorized model filename')
    folder = entry.get('folder')
    if folder not in {'text_encoders','diffusion_models','vae','upscale_models'}:
        raise DownloadError('Model subfolder is outside the authorized manifest folders')
    parsed = urllib.parse.urlsplit(entry.get('url', ''))
    parts = parsed.path.split('/')
    if parsed.scheme != 'https' or parsed.netloc != 'huggingface.co' or parsed.query or parsed.fragment or len(parts) < 6 or parts[3] != 'resolve' or not re.fullmatch('[0-9a-f]{40}', parts[4]) or urllib.parse.unquote(parts[-1]) != name:
        raise DownloadError('Source URL is not a pinned official HF resolve URL')
    destination = model_root / folder / name
    for path in (destination, destination.with_suffix(destination.suffix + '.part')):
        resolved = path.resolve()
        if not resolved.is_relative_to(model_root) or resolved.drive.upper() != 'D:':
            raise DownloadError('Model destination escapes the authorized D: model root')
    entry['destination'] = str(destination)
    return model_root, {'label': name, 'revision': parts[4], 'files': [entry]}

def run_model(index):
    result_path = REPORT_ROOT / ('download-ranges-' + str(index) + '.json')
    result = {'index': index, 'complete': False, 'workers': WORKERS,
              'block_bytes': BLOCK_BYTES, 'reserve_bytes': RESERVE_BYTES, 'files': []}
    try:
        model_root, model = validate_manifest(index)
        result.update(model=model['label'], revision=model['revision'])
        print('START RANGE HELPER ' + model['label'], flush=True)
        for entry in model['files']:
            destination = Path(entry['destination'])
            destination.parent.mkdir(parents=True, exist_ok=True)
            partial = destination.with_suffix(destination.suffix + '.part')
            journal = REPORT_ROOT / ('ranges-' + str(index) + '-' + destination.name + '.json')
            if destination.exists():
                digest = check_file(destination, entry)
            else:
                engine = RangeDownload(partial, journal, entry, model['revision'], model_root)
                try:
                    print('CONTINUE %s; original prefix %.2f GB; confirmed %.2f GB' %
                          (destination.name, engine.prefix / 1e9,
                           engine.confirmed_bytes() / 1e9), flush=True)
                    engine.download()
                    print('VERIFY EXACT SIZE + SHA256 ' + destination.name, flush=True)
                    digest = engine.verify_open()
                    if destination.exists():
                        raise DownloadError('Destination appeared during download; refusing overwrite')
                    # Keep the deny-read/write handle through Windows rename. No writer
                    # can change the verified bytes between hashing and publication.
                    if os.name != 'nt':
                        raise DownloadError('Production rename requires the authorized Windows host')
                    partial.rename(destination)
                    engine.journal['finalized'] = True
                    atomic_json(journal, engine.journal)
                finally:
                    engine.close()
            result['files'].append({'path': str(destination), 'bytes': entry['bytes'],
                                    'sha256': digest, 'source_url': entry['url'], 'verified': True})
            atomic_json(result_path, result)
            print('VERIFIED ' + destination.name, flush=True)
        result['complete'] = True
        result['free_bytes_d'] = shutil.disk_usage(model_root).free
        atomic_json(result_path, result)
        print('COMPLETE ' + model['label'], flush=True)
        return 0
    except Exception as error:
        result['error'] = safe_error(error)
        if REPORT_ROOT == AUTHORIZED_REPORT_ROOT.resolve():
            atomic_json(result_path, result)
        print('FAILED ' + result['error'], flush=True)
        return 1



def run_all():
    summary_path = REPORT_ROOT / 'models-ranges-session.json'
    summary = {'complete': False, 'workers': WORKERS, 'pid': os.getpid(),
               'manifest_sha256': MANIFEST_SHA256, 'order': [3,4,0,1,2], 'files': []}
    try:
        for index in summary['order']:
            validate_manifest(index)
        with exclusive_open(REPORT_ROOT / 'models-range-session.lock'):
            atomic_json(summary_path, summary)
            for index in summary['order']:
                summary['active_index'] = index
                atomic_json(summary_path, summary)
                if run_model(index):
                    raise DownloadError('A manifest file failed; details in its range receipt')
                receipt = json.loads((REPORT_ROOT / ('download-ranges-' + str(index) + '.json')).read_text(encoding='utf-8'))
                summary['files'].extend(receipt['files'])
                atomic_json(summary_path, summary)
            summary.pop('active_index', None)
            summary['complete'] = True
            atomic_json(REPORT_ROOT / 'models-installed.json', summary['files'])
            atomic_json(summary_path, summary)
            print('ALL MANIFEST FILES VERIFIED', flush=True)
            return 0
    except Exception as error:
        summary['error'] = safe_error(error)
        atomic_json(summary_path, summary)
        print('SESSION FAILED ' + summary['error'], flush=True)
        return 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('index', type=int, nargs='?')
    parser.add_argument('--all', action='store_true')
    parser.add_argument('--validate-only', action='store_true')
    options = parser.parse_args()
    if options.validate_only:
        for index in range(5):
            root, model = validate_manifest(index)
            print('VALIDATED ' + str(index) + ' ' + model['label'], flush=True)
        return 0
    if options.all:
        if options.index is not None:
            parser.error('--all does not accept an index')
        return run_all()
    if options.index is None:
        parser.error('Supply a manifest index or --all')
    return run_model(options.index)


if __name__ == '__main__':
    raise SystemExit(main())
