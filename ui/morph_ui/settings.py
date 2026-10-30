import base64
import ctypes
import ipaddress
import json
import os
import uuid
from ctypes import wintypes
from urllib.parse import urlsplit
from .paths import UiError

class Blob(ctypes.Structure):
    _fields_ = [('size', wintypes.DWORD), ('data', ctypes.POINTER(ctypes.c_ubyte))]

def protect(data, decrypt=False):
    buffer = ctypes.create_string_buffer(data)
    source = Blob(len(data), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_ubyte)))
    target = Blob()
    crypt = ctypes.WinDLL('crypt32', use_last_error=True)
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    function = crypt.CryptUnprotectData if decrypt else crypt.CryptProtectData
    function.argtypes = [ctypes.POINTER(Blob), ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(Blob)]
    function.restype = wintypes.BOOL
    kernel.LocalFree.argtypes = [ctypes.c_void_p]
    if not function(ctypes.byref(source), None, None, None, None, 1, ctypes.byref(target)):
        raise UiError('secret_store', 'Der Zugangsschlüssel konnte mit dem Windows-Benutzerkonto nicht gespeichert oder gelesen werden.')
    try:
        return ctypes.string_at(target.data, target.size)
    finally:
        kernel.LocalFree(target.data)

def local_endpoint(value):
    try:
        url = urlsplit(value)
        hostname = '127.0.0.1' if url.hostname == 'localhost' else url.hostname
        address = ipaddress.ip_address(hostname)
        port = url.port if url.port is not None else 80
        if url.scheme != 'http' or not address.is_loopback or url.username or url.password or url.path not in ['', '/'] or url.query or url.fragment or not 1 <= port <= 65535:
            raise ValueError('Not a local HTTP endpoint')
        host = '[' + str(address) + ']' if address.version == 6 else str(address)
        return f'http://{host}:{port}'
    except (ValueError, TypeError) as error:
        raise UiError('endpoint', 'Bitte eine lokale Serveradresse verwenden, zum Beispiel http://127.0.0.1:11434.') from error

class SettingsStore:
    def __init__(self, paths):
        self.paths = paths
        self.path = paths.inside(paths.data, 'settings.json')

    def _load_saved(self):
        try:
            raw = self.path.read_bytes()
        except FileNotFoundError:
            return None, None
        except OSError as error:
            raise UiError('settings', 'Die MORPH-Verbindungseinstellungen sind nicht lesbar.') from error
        try:
            saved = json.loads(raw.decode('utf-8-sig'))
            if not isinstance(saved, dict):
                raise ValueError('Settings must be an object')
            if 'provider' in saved and saved['provider'] not in ('lmstudio', 'ollama'):
                raise ValueError('Unsupported provider')
            for name in ['endpoint', 'model_key', 'instance_id']:
                if name in saved and (not isinstance(saved[name], str) or len(saved[name]) > 512):
                    raise ValueError('Invalid connection setting')
            if 'endpoint' in saved:
                local_endpoint(saved['endpoint'])
            if 'token_protected' in saved:
                if not isinstance(saved['token_protected'], str):
                    raise ValueError('Invalid protected token')
                base64.b64decode(saved['token_protected'], validate=True)
        except (ValueError, TypeError, UnicodeError) as error:
            raise UiError('settings', 'Die MORPH-Verbindungseinstellungen sind beschädigt oder verwenden einen nicht unterstützten Anbieter.') from error
        return raw, saved

    def _effective(self, saved):
        defaults = {'provider':'ollama','endpoint':'http://127.0.0.1:11434','model_key':'','instance_id':''}
        if saved is None:
            return defaults
        if saved.get('provider') == 'ollama':
            config = defaults | saved
        else:
            config = saved | defaults
            config.pop('token_protected', None)
        config['endpoint'] = local_endpoint(config['endpoint'])
        return config

    def read(self):
        _, saved = self._load_saved()
        return self._effective(saved)

    def _persist(self, config):
        target = self.paths.inside(self.paths.data, 'settings.json')
        temporary = self.paths.inside(self.paths.data, 'settings-' + uuid.uuid4().hex + '.tmp')
        try:
            with temporary.open('x', encoding='utf-8') as stream:
                stream.write(json.dumps(config, ensure_ascii=False, indent=2))
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, target)
        except OSError as error:
            raise UiError('settings', 'Die MORPH-Verbindungseinstellungen konnten nicht sicher gespeichert werden.') from error
        finally:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass

    def migrate_to_ollama(self):
        raw, saved = self._load_saved()
        current = self._effective(saved)
        if saved is None or saved.get('provider') == 'ollama':
            return current
        backup = self.paths.inside(self.paths.data, 'settings-lmstudio-backup-' + uuid.uuid4().hex + '.json')
        try:
            with backup.open('xb') as stream:
                stream.write(raw)
                stream.flush()
                os.fsync(stream.fileno())
        except OSError as error:
            raise UiError('settings', 'Die bisherigen LM-Studio-Einstellungen konnten nicht gesichert werden. Die Umstellung wurde nicht gespeichert.') from error
        self._persist(current)
        return current

    def token(self):
        encrypted = self.read().get('token_protected')
        return protect(base64.b64decode(encrypted), True).decode('utf-8') if encrypted else ''

    def read_public(self):
        config = self.read()
        return {key:config[key] for key in ['provider','endpoint','model_key','instance_id']} | {'has_token':bool(config.get('token_protected'))}

    def save(self, config):
        if not isinstance(config, dict) or set(config) - {'endpoint','model_key','instance_id','token'}:
            raise UiError('settings', 'Unbekannte Verbindungseinstellung.')
        changes = dict(config)
        for name in ['endpoint','model_key','instance_id']:
            if name in changes:
                if not isinstance(changes[name], str) or len(changes[name]) > 512:
                    raise UiError('settings', 'Ungültige Verbindungseinstellung.')
        if 'endpoint' in changes:
            changes['endpoint'] = local_endpoint(changes['endpoint'])
        if 'token' in changes:
            value = changes['token']
            if not isinstance(value, str) or len(value) > 4096:
                raise UiError('token', 'Ungültiger Zugangsschlüssel.')
        current = self.migrate_to_ollama()
        if 'endpoint' in changes and changes['endpoint'] != current['endpoint']:
            current['model_key'] = ''
            current['instance_id'] = ''
        for name in ['endpoint','model_key','instance_id']:
            if name in changes:
                current[name] = changes[name]
        if 'token' in changes:
            value = changes['token']
            if value:
                current['token_protected'] = base64.b64encode(protect(value.encode('utf-8'))).decode('ascii')
            else:
                current.pop('token_protected', None)
        self._persist(current)
