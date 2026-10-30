"""Persistent image branches; no backend, provider or computation side effects."""

from contextlib import closing
from datetime import datetime, timezone
import hashlib
import io
import json
import os
import re
import sqlite3
import uuid
import warnings

from PIL import Image

from .paths import UiError


IMAGE_LIMIT = 64 * 1024**2
PRIMARY_ROLES = {'kontext': 'image', 'krea2': 'image', 'reactor': 'target', 'wan': 'image'}


def timestamp():
    return datetime.now(timezone.utc).isoformat()


def serialized(value):
    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False)
    except (TypeError, ValueError) as error:
        raise UiError('version_metadata', 'Die Bildmetadaten sind nicht vollständig speicherbar.') from error


class VersionStore:
    def __init__(self, paths, files):
        self.paths, self.files = paths, files
        self.db = sqlite3.connect(paths.database)
        self.db.row_factory = sqlite3.Row
        try:
            self.db.execute('PRAGMA foreign_keys=ON')
            existing = {row[0] for row in self.db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            if not {'image_projects', 'image_versions'}.issubset(existing):
                # SQLite's backup API captures committed data, including a possible WAL.
                folder = paths.inside(paths.data, 'backups')
                folder.mkdir(parents=True, exist_ok=True)
                target = paths.inside(folder, 'before-image-versions-' +
                                      datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ-') +
                                      uuid.uuid4().hex + '.sqlite3')
                with closing(sqlite3.connect(target)) as backup:
                    self.db.backup(backup)
            self.db.executescript('''
                BEGIN;
                CREATE TABLE IF NOT EXISTS image_projects (
                    id TEXT PRIMARY KEY,
                    request_id TEXT NOT NULL UNIQUE,
                    original_source_media_id TEXT NOT NULL REFERENCES media(id),
                    name TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS image_versions (
                    id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL REFERENCES image_projects(id),
                    parent_version_id TEXT,
                    media_id TEXT NOT NULL REFERENCES media(id),
                    source_media_id TEXT NOT NULL REFERENCES media(id),
                    job_id TEXT,
                    created_at TEXT NOT NULL,
                    status TEXT NOT NULL CHECK(status IN ('original','completed')),
                    metadata_json TEXT NOT NULL,
                    sha256 TEXT NOT NULL,
                    input_media_id TEXT REFERENCES media(id),
                    UNIQUE(project_id,id),
                    UNIQUE(job_id,source_media_id),
                    FOREIGN KEY(project_id,parent_version_id) REFERENCES image_versions(project_id,id),
                    CHECK((status='original' AND parent_version_id IS NULL AND job_id IS NULL)
                       OR (status='completed' AND parent_version_id IS NOT NULL AND job_id IS NOT NULL))
                );
                CREATE UNIQUE INDEX IF NOT EXISTS image_versions_original
                    ON image_versions(project_id) WHERE parent_version_id IS NULL;
                COMMIT;
            ''')
        except Exception:
            self.db.close()
            raise

    def close(self):
        self.db.close()

    @staticmethod
    def _id(value, kind):
        if not isinstance(value, str) or not re.fullmatch('[a-f0-9]{32}', value):
            raise UiError('version_id', 'Diese Bild-' + kind + ' gehört nicht zur MORPH-Historie.', status=404)
        return value

    @staticmethod
    def _request(value):
        try:
            return str(uuid.UUID(value))
        except (ValueError, AttributeError, TypeError) as error:
            raise UiError('version_request', 'Die Bildhistorie benötigt eine eindeutige Anforderungskennung.') from error

    def _row(self, version_id):
        row = self.db.execute('SELECT * FROM image_versions WHERE id=?',
                              (self._id(version_id, 'Version'),)).fetchone()
        if row is None:
            raise UiError('version_missing', 'Diese Bildversion ist nicht gespeichert.', status=404)
        return row

    def _image(self, media_id):
        info = self.files.info(media_id)
        path = self.files.resolve(media_id)
        if info['kind'] != 'image':
            raise UiError('version_image', 'Die Bildhistorie benötigt ein einzelnes PNG-, JPEG- oder WebP-Bild.')
        try:
            with path.open('rb') as source:
                before = os.fstat(source.fileno())
                if not 0 < before.st_size <= IMAGE_LIMIT:
                    raise ValueError('Image size')
                data = source.read(IMAGE_LIMIT + 1)
                after = os.fstat(source.fileno())
            identity = lambda stat: (stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns)
            if len(data) != before.st_size or identity(before) != identity(after):
                raise ValueError('Image changed')
            with warnings.catch_warnings():
                warnings.simplefilter('error', Image.DecompressionBombWarning)
                with Image.open(io.BytesIO(data)) as image:
                    if (image.format not in {'PNG', 'JPEG', 'WEBP'} or image.width * image.height > 64_000_000
                            or getattr(image, 'n_frames', 1) != 1):
                        raise ValueError('Unsupported image')
                    extension = {'PNG': '.png', 'JPEG': '.jpg', 'WEBP': '.webp'}[image.format]
                    image.verify()
        except (OSError, ValueError, Image.DecompressionBombWarning, Image.DecompressionBombError) as error:
            raise UiError('version_image', 'Das Bild ist nicht als unveränderlicher Zwischenstand lesbar '
                          '(PNG, JPEG oder WebP, höchstens 64 MiB und 64 Millionen Bildpunkte).') from error
        return data, extension, hashlib.sha256(data).hexdigest()

    def _snapshot(self, project_id, version_id, source_media_id):
        data, extension, digest = self._image(source_media_id)
        target = self.paths.inside(self.paths.output,
                                  'MORPH-UI/versions/' + project_id + '/' + version_id + extension)
        if target.exists():
            # A retry can find a copy committed before its version row. Never overwrite it.
            with target.open('rb') as existing:
                saved = existing.read(IMAGE_LIMIT + 1)
            if hashlib.sha256(saved).hexdigest() != digest:
                raise UiError('version_changed', 'Eine gespeicherte Versionsdatei wurde verändert. '
                              'Sie wird nicht überschrieben.', status=409)
        else:
            self.paths.require_space(len(data) + 1024**2)
            target.parent.mkdir(parents=True, exist_ok=True)
            partial = target.with_suffix(extension + '.' + uuid.uuid4().hex + '.part')
            try:
                with partial.open('xb') as output:
                    output.write(data)
                    output.flush()
                    os.fsync(output.fileno())
                # On Windows rename refuses an existing destination, including a concurrent copy.
                partial.rename(target)
            finally:
                partial.unlink(missing_ok=True)
        return self.files.register_output(target), digest

    def _insert(self, version_id, project_id, parent, media, source_id, job_id, status, metadata, digest):
        self.db.execute('''INSERT INTO image_versions
            (id,project_id,parent_version_id,media_id,source_media_id,job_id,created_at,status,metadata_json,sha256)
            VALUES (?,?,?,?,?,?,?,?,?,?)''',
            (version_id, project_id, parent, media['id'], source_id, job_id, timestamp(), status,
             serialized(metadata), digest))

    def create_project(self, request_id, original_media_id, name=''):
        request_id = self._request(request_id)
        if not isinstance(name, str) or len(name) > 160 or any(ord(char) < 32 for char in name):
            raise UiError('version_name', 'Bitte einen kurzen, lesbaren Namen für das Bildprojekt verwenden.')
        existing = self.db.execute('SELECT * FROM image_projects WHERE request_id=?', (request_id,)).fetchone()
        if existing:
            if existing['original_source_media_id'] != original_media_id or existing['name'] != name:
                raise UiError('version_request_conflict', 'Diese Anforderungskennung gehört bereits zu einem '
                              'anderen Bildprojektauftrag.', status=409)
            return self.get_project(existing['id'])
        project_id = uuid.uuid5(uuid.NAMESPACE_URL, 'morph-image-project:' + request_id).hex
        version_id = uuid.uuid5(uuid.NAMESPACE_URL, 'morph-image-original:' + project_id).hex
        media, digest = self._snapshot(project_id, version_id, original_media_id)
        metadata = {'prompt': None, 'workflow_id': None, 'controls': {}, 'graph': {}, 'model_components': []}
        with self.db:
            self.db.execute('INSERT INTO image_projects VALUES (?,?,?,?,?)',
                            (project_id, request_id, original_media_id, name, timestamp()))
            self._insert(version_id, project_id, None, media, original_media_id, None, 'original', metadata, digest)
        return self.get_project(project_id)

    def list_projects(self):
        return [dict(row) for row in self.db.execute('''SELECT p.id,p.name,p.created_at,
            v.id AS original_version_id,
            (SELECT COUNT(*) FROM image_versions WHERE project_id=p.id) AS version_count
            FROM image_projects p JOIN image_versions v ON v.project_id=p.id AND v.parent_version_id IS NULL
            ORDER BY p.rowid DESC''')]

    def get_project(self, project_id):
        row = self.db.execute('SELECT id,name,created_at FROM image_projects WHERE id=?',
                              (self._id(project_id, 'Projektkennung'),)).fetchone()
        if row is None:
            raise UiError('version_project', 'Dieses Bildprojekt ist nicht gespeichert.', status=404)
        versions = [self.get_version(item['id']) for item in self.db.execute(
            'SELECT id FROM image_versions WHERE project_id=? ORDER BY rowid', (project_id,)).fetchall()]
        return dict(row, original_version_id=next(item['id'] for item in versions if item['parent_version_id'] is None),
                    versions=versions)

    def get_version(self, version_id):
        row = self._row(version_id)
        unused_data, unused_extension, digest = self._image(row['media_id'])
        if digest != row['sha256']:
            raise UiError('version_changed', 'Diese Bildversion wurde außerhalb der Historie verändert. '
                          'Sie wird nicht überschrieben.', status=409)
        return {'id': row['id'], 'project_id': row['project_id'], 'parent_version_id': row['parent_version_id'],
                'media': self.files.info(row['media_id']), 'created_at': row['created_at'], 'status': row['status'],
                'metadata': json.loads(row['metadata_json']), 'sha256': row['sha256']}

    def prepare_input(self, version_id):
        version = self.get_version(version_id)
        row = self._row(version_id)
        input_id = row['input_media_id']
        if input_id:
            unused_data, unused_extension, digest = self._image(input_id)
            if digest != version['sha256']:
                raise UiError('version_changed', 'Die vorbereitete Eingabekopie wurde verändert. '
                              'Bitte den gespeicherten Zwischenstand prüfen.', status=409)
            image = self.files.info(input_id)
            if image['category'] != 'input':
                raise UiError('version_image', 'Die vorbereitete Kopie ist kein freigegebenes Eingabebild.')
        else:
            data, unused_extension, unused_digest = self._image(version['media']['id'])
            input_id = uuid.uuid5(uuid.NAMESPACE_URL, 'morph-version-input:' + version_id).hex
            image = self.files.save_upload(data, version['media']['name'], stable_id=input_id)
            with self.db:
                self.db.execute('UPDATE image_versions SET input_media_id=? WHERE id=?', (image['id'], version_id))
        return {'project_id': version['project_id'], 'parent_version_id': version_id, 'image': image}

    def validate_job_context(self, project_id, parent_version_id, workflow_id, images):
        if project_id is None and parent_version_id is None:
            return {}
        if project_id is None or parent_version_id is None:
            raise UiError('version_context', 'Bildprojekt und gewählter Zwischenstand müssen zusammen angegeben werden.')
        self._id(project_id, 'Projektkennung')
        parent = self.get_version(parent_version_id)
        if parent['project_id'] != project_id:
            raise UiError('version_context', 'Der Zwischenstand gehört zu einem anderen Bildprojekt.')
        role = PRIMARY_ROLES.get(workflow_id)
        if not role or not isinstance(images, dict) or role not in images:
            raise UiError('version_context', 'Dieses Werkzeug benötigt eine ausdrücklich gewählte Bildeingabe.')
        source_id = images[role]
        if self.files.info(source_id)['category'] != 'input':
            raise UiError('version_context', 'Bitte den gewählten Zwischenstand zuerst als Eingabe übernehmen.')
        unused_data, unused_extension, digest = self._image(source_id)
        if digest != parent['sha256']:
            raise UiError('version_context', 'Das Eingabebild stimmt nicht mit dem gewählten Zwischenstand überein.')
        return {'project_id': project_id, 'parent_version_id': parent_version_id}

    def record_job_outputs(self, job):
        if job.get('state') != 'completed' or (job.get('project_id') is None and job.get('parent_version_id') is None):
            return []
        project_id = self._id(job.get('project_id'), 'Projektkennung')
        parent = self.get_version(job.get('parent_version_id'))
        if parent['project_id'] != project_id:
            raise UiError('version_context', 'Der Ergebnisauftrag gehört nicht zum gewählten Bildprojekt.')
        job_id = self._request(job.get('id'))
        controls = job.get('controls', {})
        if not isinstance(controls, dict):
            raise UiError('version_metadata', 'Die gespeicherten Auftragseinstellungen sind unvollständig.')
        metadata = json.loads(serialized({'prompt': controls.get('prompt'), 'workflow_id': job.get('workflow_id'),
            'controls': controls, 'graph': job.get('graph', {}), 'model_components': job.get('model_components', []),
            **({'edit_region': job['edit_region']} if job.get('edit_region') is not None else {})}))
        pending, result_ids, seen = [], [], set()
        for output in job.get('outputs', []):
            source_id = output.get('id') if isinstance(output, dict) else None
            if source_id in seen:
                continue
            seen.add(source_id)
            existing = self.db.execute('SELECT * FROM image_versions WHERE job_id=? AND source_media_id=?',
                                       (job_id, source_id)).fetchone()
            if existing:
                if (existing['project_id'] != project_id or existing['parent_version_id'] != parent['id']
                        or existing['metadata_json'] != serialized(metadata)):
                    raise UiError('version_job_conflict', 'Dieser Ergebnisauftrag besitzt bereits andere '
                                  'unveränderliche Bildmetadaten.', status=409)
                self.get_version(existing['id'])
                result_ids.append(existing['id'])
                continue
            info = self.files.info(source_id)
            if info['kind'] != 'image' or self.files.resolve(source_id).suffix.lower() not in {'.png', '.jpg', '.jpeg', '.webp'}:
                continue
            version_id = uuid.uuid5(uuid.NAMESPACE_URL, 'morph-image-result:' + job_id + ':' + source_id).hex
            media, digest = self._snapshot(project_id, version_id, source_id)
            pending.append((version_id, project_id, parent['id'], media, source_id, job_id, 'completed', metadata, digest))
            result_ids.append(version_id)
        # All image copies/media commits precede the atomic metadata batch. An interrupted
        # batch leaves only recoverable extra files, never damaged existing versions.
        with self.db:
            for args in pending:
                self._insert(*args)
        return [self.get_version(version_id) for version_id in result_ids]
