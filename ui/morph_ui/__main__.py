import argparse
import json
import logging
from pathlib import Path
import sys

if not __package__:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from aiohttp import web
from morph_ui.paths import ProjectPaths
from morph_ui.catalog import Catalog
from morph_ui.files import FileStore
from morph_ui.settings import SettingsStore
from morph_ui.providers.ollama import OllamaProvider
from morph_ui.comfy import ComfyClient
from morph_ui.jobs import JobService
from morph_ui.server import create_app

def main():
    parser = argparse.ArgumentParser(description='Lokale MORPH-Oberfläche')
    parser.add_argument('--check',action='store_true',help='Nur Workflow-Dateien und Modellpfade prüfen; keine Dienste starten.')
    args = parser.parse_args()
    paths = ProjectPaths(Path(__file__).resolve().parents[2])
    catalog = Catalog(paths)
    if args.check:
        entries = catalog.list_entries()
        print(json.dumps({'project_root':str(paths.root),'workflows':len(entries),'issues':{x['id']:x['issues'] for x in entries if x['issues']}},ensure_ascii=False))
        return
    logdir = paths.inside(paths.logs,'morph-ui')
    logdir.mkdir(exist_ok=True)
    logging.basicConfig(filename=str(logdir / 'server.log'),level=logging.INFO,format='%(asctime)s %(levelname)s %(message)s')
    settings = SettingsStore(paths)
    settings.migrate_to_ollama()
    files = FileStore(paths)
    from morph_ui.versions import VersionStore
    versions = VersionStore(paths,files)
    comfy = ComfyClient(paths)
    jobs = JobService(paths,catalog,files,comfy,versions=versions)
    provider = OllamaProvider(settings,catalog)
    app = create_app(paths,catalog,provider,jobs,files,settings,versions=versions)
    web.run_app(app,host='127.0.0.1',port=8877,access_log=None)

if __name__ == '__main__':
    main()
