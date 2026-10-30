import sys,site,json,asyncio
from pathlib import Path
runtime='D:/MORPH-Studio/tools/comfyui-mcp-runtime'
sys.path.insert(0,runtime);site.addsitedir(runtime)
from mcp.client import ClientSession
from mcp.client.stdio import StdioServerParameters,stdio_client
report=Path('D:/MORPH-Studio/reports/wan-lmstudio')
config=json.loads((report/'lmstudio-mcp-proposed.json').read_text(encoding='utf-8-sig'))['mcpServers']['Wan-ComfyUI']
async def main():
 with (report/'mcp-probe-stderr.log').open('w',encoding='utf-8') as stderr:
  async with stdio_client(StdioServerParameters(**config),errlog=stderr) as (read,write):
   async with ClientSession(read,write) as session:
    init=await session.initialize()
    listing=await session.list_tools()
    names=[t.name for t in listing.tools]
    must={'comfyui_run_workflow','comfyui_poll_workflow','comfyui_get_outputs','comfyui_upload_image','comfyui_list_queue'}
    assert must.issubset(names), names
    result={'handshake':True,'server':init.server_info.model_dump(),'tools':names}
    if '--status' in sys.argv:
     call=await session.call_tool('comfyui_list_queue',{})
     result['queue_result']=call.model_dump(mode='json')
     assert not call.is_error,call
    (report/'mcp-probe.json').write_text(json.dumps(result,indent=2,ensure_ascii=False),encoding='utf-8')
    print(json.dumps({'handshake':True,'tools':len(names),'read_only_queue_test':'--status' in sys.argv}))
asyncio.run(main())

