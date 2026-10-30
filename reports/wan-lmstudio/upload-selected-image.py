import sys,site,json,asyncio
from pathlib import Path
runtime='D:/MORPH-Studio/tools/comfyui-mcp-runtime'
sys.path.insert(0,runtime);site.addsitedir(runtime)
from mcp.client import ClientSession
from mcp.client.stdio import StdioServerParameters,stdio_client
report=Path('D:/MORPH-Studio/reports/wan-lmstudio')
config=json.loads(Path('V:/LMStudio/.lmstudio/mcp.json').read_text(encoding='utf-8-sig'))['mcpServers']['Wan-ComfyUI']
async def main():
 with (report/'image-upload-mcp-stderr.log').open('w',encoding='utf-8') as stderr:
  async with stdio_client(StdioServerParameters(**config),errlog=stderr) as (read,write):
   async with ClientSession(read,write) as session:
    await session.initialize()
    response=await session.call_tool('comfyui_upload_image',{'params':{'paths':['C:/Users/USER/Desktop/rtzu/589682038_17903637102306091_4752592283070689792_n.jpg'],'subfolder':'lmstudio','overwrite':False}})
    assert not response.is_error,response
    data=json.loads(next(c.text for c in response.content if c.type=='text'))
    assert data['ok'] and data['uploaded_count']==1 and data['failed_count']==0,data
    (report/'image-upload-mcp.json').write_text(json.dumps(data,indent=2,ensure_ascii=False),encoding='utf-8')
    print(json.dumps({'uploaded':data['uploaded'][0]['load_image_name'],'bytes':data['uploaded'][0]['bytes']}))
asyncio.run(main())