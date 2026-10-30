"""Read the accepted job through the configured LM Studio MCP connection."""
import asyncio
import json
import site
import sys
from pathlib import Path

runtime = 'D:/MORPH-Studio/tools/comfyui-mcp-runtime'
sys.path.insert(0, runtime)
site.addsitedir(runtime)
from mcp.client import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

report = Path('D:/MORPH-Studio/reports/wan-lmstudio')
config = json.loads(Path('V:/LMStudio/.lmstudio/mcp.json').read_text(encoding='utf-8-sig'))['mcpServers']['Wan-ComfyUI']
receipt = json.loads((report / 'first-video-submitted.json').read_text(encoding='utf-8-sig'))
prompt_id = receipt['prompt_id']

async def main():
    with (report / 'first-video-inspection-stderr.log').open('w', encoding='utf-8') as stderr:
        async with stdio_client(StdioServerParameters(**config), errlog=stderr) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                async def call(name):
                    response = await session.call_tool(name, {'params': {'prompt_id': prompt_id}})
                    assert not response.is_error, response
                    data = json.loads(next(c.text for c in response.content if c.type == 'text'))
                    assert data.get('ok'), data
                    return data
                status = await call('comfyui_poll_workflow')
                (report / 'first-video-poll-mcp.json').write_text(json.dumps(status, indent=2, ensure_ascii=False), encoding='utf-8')
                print(json.dumps(status, ensure_ascii=False))
                if status.get('status') == 'completed':
                    outputs = await call('comfyui_get_outputs')
                    (report / 'first-video-outputs-mcp.json').write_text(json.dumps(outputs, indent=2, ensure_ascii=False), encoding='utf-8')
                    print(json.dumps(outputs, ensure_ascii=False))

asyncio.run(main())
