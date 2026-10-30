import sys,site,json,asyncio,time,urllib.request
from pathlib import Path
runtime='D:/MORPH-Studio/tools/comfyui-mcp-runtime'
sys.path.insert(0,runtime);site.addsitedir(runtime)
from mcp.client import ClientSession
from mcp.client.stdio import StdioServerParameters,stdio_client
root=Path('D:/MORPH-Studio');report=root/'reports/wan-lmstudio'
config=json.loads(Path('V:/LMStudio/.lmstudio/mcp.json').read_text(encoding='utf-8-sig'))['mcpServers']['Wan-ComfyUI']
request=json.loads((report/'first-video-request.json').read_text(encoding='utf-8'))
marker=report/'first-video-submission-started.json'
async def main():
 while True:
  state=json.loads((report/'models-ranges-session.json').read_text(encoding='utf-8'))
  if state.get('complete'):break
  if state.get('error'):raise RuntimeError('Model download session did not finish; no video submitted')
  await asyncio.sleep(15)
 manifest=json.loads((report/'models-manifest.json').read_text(encoding='utf-8-sig'))
 by_path={entry['path']:entry for entry in state['files']}
 for model in manifest:
  path=root/'ComfyUI_windows_portable/ComfyUI/models'/model['folder']/model['name']
  receipt=by_path.get(str(path))
  assert receipt and receipt['verified'] and receipt['sha256']==model['sha256']
  assert path.is_file() and path.stat().st_size==model['bytes']
 with urllib.request.urlopen('http://127.0.0.1:8188/queue',timeout=15) as response:queue=json.load(response)
 assert not queue['queue_running'] and not queue['queue_pending'],'Existing ComfyUI job is active'
 with marker.open('x',encoding='utf-8') as stream:json.dump({'started_at':time.time(),'request':str(report/'first-video-request.json')},stream)
 with (report/'first-video-mcp-stderr.log').open('w',encoding='utf-8') as stderr:
  async with stdio_client(StdioServerParameters(**config),errlog=stderr) as (read,write):
   async with ClientSession(read,write) as session:
    await session.initialize()
    response=await session.call_tool('comfyui_run_workflow',request)
    data=json.loads(next(c.text for c in response.content if c.type=='text'))
    (report/'first-video-submitted.json').write_text(json.dumps(data,indent=2,ensure_ascii=False),encoding='utf-8')
    assert not response.is_error and data.get('ok'),data
    print(json.dumps({'submitted':True,'result':data},ensure_ascii=True),flush=True)
asyncio.run(main())