import shutil
from pathlib import Path

class UiError(Exception):
    def __init__(self, code, message, details=None, status=400):
        super().__init__(message)
        self.code, self.message, self.details, self.status = code, message, details, status

class ProjectPaths:
    def __init__(self, root):
        self.root = Path(root).resolve(strict=True)
        self.workflows = self.inside(self.root, 'workflows')
        self.models = self.inside(self.root, 'ComfyUI_windows_portable/ComfyUI/models')
        self.python = self.inside(self.root, 'ComfyUI_windows_portable/python_embeded/python.exe')
        for name in ['input','output','user','temp','logs']:
            path = self.inside(self.root, name)
            path.mkdir(parents=True, exist_ok=True)
            setattr(self, name, path)
        self.data = self.inside(self.user, 'morph-ui')
        self.data.mkdir(exist_ok=True)
        self.database = self.data / 'jobs.sqlite3'

    def inside(self, base, relative, must_exist=False):
        base = Path(base).resolve()
        relative = Path(relative)
        if relative.is_absolute() or relative.drive or '..' in relative.parts:
            raise UiError('unsafe_path', 'Der Dateipfad verlässt den freigegebenen Projektbereich.')
        try:
            candidate = (base / relative).resolve(strict=must_exist)
        except OSError as error:
            raise UiError('missing_file', 'Die benötigte Datei ist nicht lesbar.', str(relative), 404) from error
        if not base.is_relative_to(self.root) or not candidate.is_relative_to(base):
            raise UiError('unsafe_path', 'Eine Dateiverknüpfung verlässt den freigegebenen Projektbereich.')
        return candidate

    def free_bytes(self):
        return shutil.disk_usage(self.root).free

    def require_space(self, needed):
        free = self.free_bytes()
        if free < needed:
            raise UiError('space', f'Zu wenig freier Speicher: {free / 2**30:.1f} GiB verfügbar, mindestens {needed / 2**30:.1f} GiB benötigt.')
