import { withMcpSession } from './mcpTransport.mjs';

const relevant = new Set([
  'check_comfyui_status', 'comfyui_run_workflow', 'comfyui_poll_workflow',
  'comfyui_get_outputs', 'comfyui_list_queue', 'comfyui_upload_image',
  'comfyui_list_input_images',
]);

function textContent(result) {
  return (result.content ?? []).filter(block => block.type === 'text').map(block => block.text).join('\n');
}

export async function toolsProvider(ctl, rawFunctionTool, connect = withMcpSession) {
  const discovery = await connect(session => session.request('tools/list', {}), { signal: ctl.abortSignal }, { startComfy: false });
  const definitions = discovery.tools.filter(tool => relevant.has(tool.name));
  const missing = [...relevant].filter(name => !definitions.some(tool => tool.name === name));
  if (missing.length) throw new Error('MCP tools unavailable: ' + missing.join(', '));
  return definitions.map(definition => rawFunctionTool({
    name: definition.name,
    description: definition.description,
    parametersJsonSchema: definition.inputSchema,
    implementation: async (params, ctx) => {
      ctx.signal?.throwIfAborted();
      const result = await connect(session => session.request('tools/call', {
        name: definition.name, arguments: params,
      }), ctx);
      const text = textContent(result);
      if (result.isError) throw new Error(text || 'MCP tool error: ' + definition.name);
      return text;
    },
  }));
}

