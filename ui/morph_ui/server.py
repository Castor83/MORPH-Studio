import logging
import mimetypes
import os
from pathlib import Path
from urllib.parse import quote
from aiohttp import web
from .paths import UiError
from .settings import SettingsStore

HOSTS = {'127.0.0.1:8877','localhost:8877'}
ORIGINS = {'http://' + host for host in HOSTS}
POLICY = "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' blob: data:; media-src 'self' blob:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"

def create_app(paths, catalog, provider, jobs, files, settings=None, *, versions=None):
    settings = settings or SettingsStore(paths)
    jobs.provider = provider
    frontend = Path(__file__).resolve().parents[1] / 'frontend'

    @web.middleware
    async def guarded(request, handler):
        try:
            if request.host not in HOSTS:
                raise UiError('host', 'Die Oberfläche nimmt nur Anfragen an ihre eigene lokale Adresse an.', status=403)
            if request.method not in {'GET','HEAD'}:
                origin = request.headers.get('Origin')
                if (origin is not None and origin not in ORIGINS) or request.headers.get('X-MORPH-Request') != '1':
                    raise UiError('origin', 'Diese Aktion muss aus der MORPH-Oberfläche ausgelöst werden.', status=403)
                if request.path != '/api/uploads' and request.content_length and request.content_length > 1024**2:
                    raise UiError('request_size', 'Diese Anfrage ist zu groß.', status=413)
            response = await handler(request)
        except UiError as error:
            response = web.json_response({'ok':False,'error':{'code':error.code,'message':error.message,'details':error.details}},status=error.status)
        except web.HTTPException as error:
            response = web.json_response({'ok':False,'error':{'code':'http','message':error.reason}},status=error.status)
        except Exception:
            logging.exception('MORPH UI request failed')
            response = web.json_response({'ok':False,'error':{'code':'internal','message':'Die Aktion konnte nicht abgeschlossen werden. Bitte das lokale Oberflächenprotokoll prüfen.'}},status=500)
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['Content-Security-Policy'] = POLICY
        response.headers['Cache-Control'] = 'no-store'
        return response

    app = web.Application(middlewares=[guarded],client_max_size=65 * 1024**2)
    def result(value):
        return web.json_response({'ok':True,'data':value})

    async def body(request):
        try:
            value = await request.json()
            if not isinstance(value, dict):
                raise ValueError('Not an object')
            return value
        except (ValueError, TypeError) as error:
            raise UiError('request_json', 'Die Anfrage enthält keine gültigen benannten Angaben.') from error

    async def index(request):
        return web.FileResponse(frontend / 'index.html')

    async def static(request):
        name = request.match_info['name']
        if name not in {'styles.css','api.js','forms.js','results.js','app.js','proposals.js','comparison.js','regions.js','resources.js'}:
            raise UiError('asset', 'Diese Oberflächendatei ist nicht verfügbar.',status=404)
        return web.FileResponse(frontend / name)

    async def health(request):
        return result({'app':'morph-ui','version':'1.0','pid':os.getpid(),'project_root':str(paths.root)})

    async def status(request):
        return result({'app':'morph-ui','version':'1.0','pid':os.getpid(),'project_root':str(paths.root),'free_bytes':paths.free_bytes(),'comfy':await jobs.comfy.status(),'provider':settings.read_public()['provider'],'language_state':jobs.language_state()})

    async def workflows(request):
        return result(catalog.list_entries())

    async def image_models(request):
        return result(catalog.model_inventory())

    async def resources(request):
        return result(await jobs.resources())

    async def free_resources(request):
        if await body(request):
            raise UiError('resource_fields', 'Die bewusste Speicherfreigabe benötigt keine Modell- oder Prozessangaben.')
        return result(await jobs.free_resources())

    async def emergency_release(request):
        if await body(request):
            raise UiError('resource_fields', 'Die Notfall-Freigabe benötigt keine Modell- oder Prozessangaben.')
        return result(await jobs.emergency_release())

    async def check_workflow(request):
        data = await body(request)
        workflow_id = request.match_info['id']
        controls = data.get('controls',{})
        issues = catalog.readiness(workflow_id, controls)
        if not issues and (await jobs.comfy.status()).get('ready'):
            try:
                issues = await jobs.comfy.model_readiness(catalog.prepared_graph(workflow_id,controls))
            except UiError as error:
                issues = [{'code':error.code,'message':error.message,'details':error.details}]
        return result({'issues':issues, 'dependencies':catalog.dependencies(workflow_id,controls)})

    async def models(request):
        return result(await provider.list_models())

    async def get_settings(request):
        return result(settings.read_public())

    async def save_settings(request):
        data = await body(request)
        jobs.require_settings_change()
        settings.save(data)
        return result(settings.read_public())

    async def load_model(request):
        data = await body(request)
        receipt = await jobs.language_action(provider, 'load', data.get('model_key'))
        settings.save({'model_key':data.get('model_key'),'instance_id':receipt['instance_id']})
        return result(receipt)

    async def unload_model(request):
        data = await body(request)
        await jobs.language_action(provider, 'unload', data.get('instance_id'))
        settings.save({'instance_id':''})
        return result({'unloaded':True})

    async def propose(request):
        data = await body(request)
        workflow_id = data.get('workflow_id')
        current = catalog.validate_controls(workflow_id,data.get('controls',{}))
        allowed = catalog.controls(workflow_id)
        for name,spec in allowed.items():
            spec['default'] = current[name]
        return result(await jobs.language_action(provider, 'propose', data.get('instance_id'),workflow_id,data.get('instruction'),allowed))

    async def propose_tools(request):
        data = await body(request)
        if set(data) != {'instance_id', 'workflow_id', 'instruction', 'controls'}:
            raise UiError('request_fields', 'Der Werkzeugvorschlag benötigt nur Sprachmodell, Auftrag, aktuelles Werkzeug und dessen Einstellungen.')
        return result(await jobs.language_action(provider, 'propose_tools', data['instance_id'], data['workflow_id'],
                                                   data['instruction'], data['controls']))

    async def upload(request):
        reader = await request.multipart()
        part = await reader.next()
        if part is None or part.name != 'file' or not part.filename:
            raise UiError('upload', 'Bitte eine Bilddatei auswählen.')
        data = bytearray()
        while chunk := await part.read_chunk(64 * 1024):
            data.extend(chunk)
            if len(data) > 64 * 1024**2:
                raise UiError('upload_size', 'Ein Bild darf höchstens 64 MiB groß sein.',status=413)
        if await reader.next() is not None:
            raise UiError('upload', 'Bitte jeweils eine Bilddatei ihrer Rolle zuordnen.')
        return result(files.save_upload(bytes(data),part.filename))

    async def recent_jobs(request):
        return result(jobs.list_recent())

    async def prepare_restart(request):
        await body(request)
        await jobs.prepare_restart()
        return result({'ready':True, 'pid':os.getpid(), 'project_root':str(paths.root)})

    async def get_job(request):
        return result(await jobs.refresh(request.match_info['id']))

    async def start_job(request):
        data = await body(request)
        return result(await jobs.create(data.get('request_id'),data.get('workflow_id'),data.get('controls',{}),data.get('images',{}),
                                        project_id=data.get('project_id'),parent_version_id=data.get('parent_version_id'),
                                        edit_region=data.get('edit_region')))

    def version_store():
        if versions is None:
            raise UiError('versioning_unavailable','Die Bildhistorie ist in diesem Dienst noch nicht verfügbar.',status=503)
        return versions

    async def image_projects(request):
        return result(version_store().list_projects())

    async def create_image_project(request):
        data = await body(request)
        if not {'request_id','original_media_id'} <= set(data) or set(data) - {'request_id','original_media_id','name'}:
            raise UiError('project_fields','Ein Bildprojekt benötigt eine Anforderungskennung und ein bereits vorhandenes Bild.')
        return result(version_store().create_project(data['request_id'],data['original_media_id'],data.get('name','')))

    async def get_image_project(request):
        return result(version_store().get_project(request.match_info['id']))

    async def get_image_version(request):
        return result(version_store().get_version(request.match_info['id']))

    async def prepare_version_input(request):
        if await body(request):
            raise UiError('version_fields','Für die Bildauswahl ist nur die Versionskennung erforderlich.')
        return result(version_store().prepare_input(request.match_info['id']))

    async def cancel_job(request):
        return result(await jobs.cancel(request.match_info['id']))

    async def get_request(request):
        return result(jobs.get_request(request.match_info['id']))

    async def resolve_request(request):
        return result(await jobs.resolve_request(request.match_info['id']))

    async def media(request):
        file_id = request.match_info['id']
        path = files.resolve(file_id)
        content_type = mimetypes.guess_type(path.name)[0] or 'application/octet-stream'
        headers = {'Content-Type':content_type}
        if request.query.get('download') == '1':
            headers['Content-Disposition'] = "attachment; filename*=UTF-8''" + quote(files.info(file_id)['name'],safe='')
        return web.FileResponse(path,headers=headers)

    app.router.add_get('/',index)
    app.router.add_get('/static/{name}',static)
    app.router.add_get('/api/health',health)
    app.router.add_get('/api/requests/{id}',get_request)
    app.router.add_post('/api/requests/{id}/resolve',resolve_request)
    app.router.add_post('/api/workflows/{id}/check',check_workflow)
    app.router.add_get('/api/image-models',image_models)
    app.router.add_get('/api/resources',resources)
    app.router.add_post('/api/resources/free',free_resources)
    app.router.add_post('/api/resources/emergency-release',emergency_release)
    app.router.add_post('/api/service/prepare-restart',prepare_restart)
    app.router.add_get('/api/image-projects',image_projects)
    app.router.add_post('/api/image-projects',create_image_project)
    app.router.add_get('/api/image-projects/{id}',get_image_project)
    app.router.add_get('/api/image-versions/{id}',get_image_version)
    app.router.add_post('/api/image-versions/{id}/input',prepare_version_input)
    for route,handler in [('/api/status',status),('/api/workflows',workflows),('/api/models',models),('/api/settings',get_settings),('/api/jobs',recent_jobs),('/api/jobs/{id}',get_job),('/media/{id}',media)]:
        app.router.add_get(route,handler)
    for route,handler in [('/api/settings',save_settings),('/api/models/load',load_model),('/api/models/unload',unload_model),('/api/proposals',propose),('/api/tool-proposals',propose_tools),('/api/uploads',upload),('/api/jobs',start_job),('/api/jobs/{id}/cancel',cancel_job)]:
        app.router.add_post(route,handler)

    async def cleanup(unused_app):
        if hasattr(provider,'close'):
            await provider.close()
        if hasattr(jobs.comfy,'close'):
            await jobs.comfy.close()
        jobs.close()
        if versions is not None:
            versions.close()
        files.close()
    app.on_cleanup.append(cleanup)
    return app
