from abc import ABC, abstractmethod
import json
import aiohttp
from ..paths import UiError

class LanguageProvider(ABC):
    @abstractmethod
    async def list_models(self): ...
    @abstractmethod
    async def load(self, model_key): ...
    @abstractmethod
    async def unload(self, instance_id): ...
    @abstractmethod
    async def propose(self, instance_id, workflow_id, instruction, allowed_controls): ...
    @abstractmethod
    async def propose_tools(self, instance_id, workflow_id, instruction, controls): ...

class LocalHttp:
    def __init__(self, settings, service_name='Ollama'):
        self.settings, self.session = settings, None
        self.service_name = service_name

    async def request(self, method, path, payload=None):
        if self.session is None:
            self.session = aiohttp.ClientSession(trust_env=False)
        config = self.settings.read_public()
        token = self.settings.token()
        headers = {'Authorization':'Bearer ' + token} if token else {}
        timeout = 180 if path.endswith('/load') or path == '/api/generate' else 120 if path.endswith('/completions') or path == '/api/chat' else 10
        try:
            async with self.session.request(method, config['endpoint'] + path, json=payload, headers=headers, timeout=aiohttp.ClientTimeout(total=timeout), allow_redirects=False) as response:
                if response.status in [401,403]:
                    raise UiError('authentication', f'{self.service_name} verlangt einen gültigen Zugangsschlüssel. Bitte die Verbindungseinstellungen prüfen.', status=401)
                if not 200 <= response.status < 300:
                    raise UiError('model_server', f'{self.service_name} hat die Anfrage abgelehnt (HTTP {response.status}).', status=502)
                data = bytearray()
                async for chunk in response.content.iter_chunked(64 * 1024):
                    data.extend(chunk)
                    if len(data) > 2 * 1024**2:
                        raise UiError('model_response', 'Die Sprachmodell-Antwort ist zu groß.', status=502)
                try:
                    return json.loads(data) if data else {}
                except ValueError as error:
                    raise UiError('model_response', f'{self.service_name} hat keine lesbare Antwort geliefert.', status=502) from error
        except (aiohttp.ClientError, OSError, TimeoutError) as error:
            raise UiError('model_connection', f'{self.service_name} ist unter {config["endpoint"]} nicht erreichbar. Bitte den Dienst starten oder die Adresse in „Verbindung“ prüfen.', status=503) from error

    async def close(self):
        if self.session:
            await self.session.close()
