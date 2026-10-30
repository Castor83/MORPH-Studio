import io
import ntpath
import os
import re
import sqlite3
import uuid
import warnings
from pathlib import Path
from PIL import Image
from .paths import UiError

class FileStore:
    def __init__(self, paths):
        self.paths = paths
        self.db = sqlite3.connect(paths.database)
        self.db.execute('CREATE TABLE IF NOT EXISTS media (id TEXT PRIMARY KEY, path TEXT UNIQUE, name TEXT, kind TEXT, category TEXT, bytes INTEGER)')
        self.db.commit()

    def close(self):
        self.db.close()

    def save_upload(self, data, original_name, *, stable_id=None):
        if not isinstance(data, bytes) or not 0 < len(data) <= 64 * 1024**2:
            raise UiError('image_size', 'Ein Bild darf höchstens 64 MiB groß sein.')
        try:
            with warnings.catch_warnings():
                warnings.simplefilter('error', Image.DecompressionBombWarning)
                with Image.open(io.BytesIO(data)) as image:
                    if image.format not in ['PNG','JPEG','WEBP'] or image.width * image.height > 64_000_000:
                        raise ValueError('Unsupported image')
                    extension = {'PNG':'.png','JPEG':'.jpg','WEBP':'.webp'}[image.format]
                    image.verify()
        except (OSError, ValueError, Image.DecompressionBombWarning, Image.DecompressionBombError) as error:
            raise UiError('image_format', 'Bitte ein gültiges PNG-, JPEG- oder WebP-Bild auswählen (maximal 64 Millionen Bildpunkte).') from error
        if stable_id is not None and (not isinstance(stable_id,str) or not re.fullmatch(r'[a-f0-9]{32}',stable_id)):
            raise UiError('file_id', 'Die interne Eingabekopie benötigt eine gültige Medienkennung.')
        file_id = stable_id if stable_id is not None else uuid.uuid4().hex
        target = self.paths.inside(self.paths.input, 'morph-ui/' + file_id + extension)
        relative = str(target.relative_to(self.paths.root))
        if stable_id is not None:
            if target != self.paths.input / ('morph-ui/' + file_id + extension):
                raise UiError('unsafe_path', 'Die Eingabekopie darf keine Dateiverknüpfung verwenden.')
            existing = self.db.execute('SELECT id,path,name,kind,category,bytes FROM media WHERE id=?', (file_id,)).fetchone()
            owner = self.db.execute('SELECT id FROM media WHERE path=?', (relative,)).fetchone()
            if ((existing and (existing[1] != relative or existing[3:6] != ('image','input',len(data))))
                    or (owner and owner[0] != file_id)):
                raise UiError('file_conflict', 'Diese Eingabekennung oder Datei gehört bereits zu einem anderen Medienbeleg.', status=409)
            if existing or target.exists():
                if not target.is_file():
                    raise UiError('file_conflict', 'Die vorhandene Eingabekopie ist nicht lesbar.', status=409)
                with target.open('rb') as source:
                    unchanged = source.read(len(data) + 1) == data
                if not unchanged:
                    raise UiError('file_conflict', 'Die vorhandene Eingabekopie hat einen anderen Inhalt. Sie wird nicht überschrieben.', status=409)
                if existing:
                    return self.info(file_id)
        target.parent.mkdir(parents=True, exist_ok=True)
        if stable_id is None or not target.exists():
            partial = target.with_suffix(target.suffix + '.' + uuid.uuid4().hex + '.part')
            try:
                with partial.open('xb') as output:
                    output.write(data)
                    output.flush()
                    os.fsync(output.fileno())
                # Windows rename refuses an existing destination; never replace another copy.
                partial.rename(target)
            finally:
                partial.unlink(missing_ok=True)
        name = re.sub(r'[\x00-\x1f]', '', ntpath.basename(str(original_name)))[:160] or 'Bild' + extension
        with self.db:
            self.db.execute('INSERT INTO media VALUES (?,?,?,?,?,?)', (file_id,relative,name,'image','input',len(data)))
        return self.info(file_id)

    def register_output(self, path):
        path = Path(path).resolve(strict=True)
        if path.is_relative_to(self.paths.output):
            category, base = 'output', self.paths.output
        else:
            category, base = 'temp', self.paths.inside(self.paths.temp, 'comfyui')
        if not path.is_relative_to(base) or not path.is_file():
            raise UiError('unsafe_output', 'Die Ausgabedatei liegt außerhalb des freigegebenen Bereichs.')
        suffix = path.suffix.lower()
        if suffix not in ['.png','.jpg','.jpeg','.webp','.gif','.mp4','.webm']:
            raise UiError('output_format', 'Dieses Ausgabeformat unterstützt keine Vorschau.')
        relative = str(path.relative_to(self.paths.root))
        existing = self.db.execute('SELECT id FROM media WHERE path=?', (relative,)).fetchone()
        if existing:
            return self.info(existing[0])
        file_id = uuid.uuid4().hex
        self.db.execute('INSERT INTO media VALUES (?,?,?,?,?,?)', (file_id,relative,path.name,'video' if suffix in ['.mp4','.webm'] else 'image',category,path.stat().st_size))
        self.db.commit()
        return self.info(file_id)

    def row(self, file_id):
        if not isinstance(file_id, str) or not re.fullmatch(r'[a-f0-9]{32}', file_id):
            raise UiError('file_id', 'Diese Datei gehört nicht zur MORPH-Auswahl.', status=404)
        row = self.db.execute('SELECT id,path,name,kind,category,bytes FROM media WHERE id=?', (file_id,)).fetchone()
        if row is None:
            raise UiError('file_id', 'Diese Datei gehört nicht zur MORPH-Auswahl.', status=404)
        return row

    def resolve(self, file_id):
        row = self.row(file_id)
        base = {'input':self.paths.input,'output':self.paths.output,'temp':self.paths.inside(self.paths.temp, 'comfyui')}[row[4]]
        relative = Path(row[1])
        candidate = self.paths.inside(self.paths.root, relative, True)
        if not candidate.is_relative_to(base) or not candidate.is_file():
            raise UiError('unsafe_path', 'Die Datei liegt außerhalb des freigegebenen Bereichs.', status=404)
        return candidate

    def info(self, file_id):
        row = self.row(file_id)
        path = self.resolve(file_id)
        result = {'id':row[0],'name':row[2],'kind':row[3],'category':row[4],'bytes':row[5],'url':'/media/' + row[0]}
        if row[4] == 'input':
            result['relative_path'] = path.relative_to(self.paths.input).as_posix()
        return result
