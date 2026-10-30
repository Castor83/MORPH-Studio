import test from 'node:test';
import assert from 'node:assert/strict';
import { toolsProvider } from '../src/toolsProxy.mjs';

const names = ['check_comfyui_status', 'comfyui_run_workflow', 'comfyui_poll_workflow',
  'comfyui_get_outputs', 'comfyui_list_queue', 'comfyui_upload_image', 'comfyui_list_input_images'];
const schema = { type: 'object', properties: { params: { type: 'object' } }, required: ['params'] };
const ctl = { get client() { throw new Error('Host plugin API forbidden'); } };
const ctx = { signal: new AbortController().signal, status() {}, warn() {}, callId: 1 };
const factory = value => value;

function backend({ error = false, unavailableComfy = false } = {}) {
  const state = { opened: 0, closed: 0, calls: [] };
  const connect = async (operation, context, options) => {
    context?.signal?.throwIfAborted();
    state.opened++;
    try {
      if (unavailableComfy && options?.startComfy !== false) throw new Error('ComfyUI startup unavailable');
      return await operation({ request: async (method, args) => {
        if (method === 'tools/list') return { tools: [...names, 'generate_image'].map(name => ({ name, description: name, inputSchema: schema })) };
        state.calls.push({ method, args, context, options });
        if (error) throw new Error('MCP failure');
        return { content: [{ type: 'text', text: '{ "ok": true }' }, { type: 'text', text: 'second' }] };
      } });
    } finally { state.closed++; }
  };
  return { connect, state };
}

test('seven relevant tools keep actual inputSchema and discovery closes without host plugin API', async () => {
  const { connect, state } = backend();
  const tools = await toolsProvider(ctl, factory, connect);
  assert.deepEqual(tools.map(tool => tool.name), names);
  assert.equal(tools[0].parametersJsonSchema, schema);
  assert.equal(state.opened, 1); assert.equal(state.closed, 1);
});

test('discovery publishes schemas without ComfyUI startup and execution still requires it', async () => {
  const { connect, state } = backend({ unavailableComfy: true });
  const discoveryCtl = Object.create(ctl); discoveryCtl.abortSignal = ctx.signal;
  const tools = await toolsProvider(discoveryCtl, factory, connect);
  assert.deepEqual(tools.map(tool => tool.name), names);
  assert.equal(tools[1].parametersJsonSchema, schema);
  assert.equal(state.opened, 1); assert.equal(state.closed, 1);
  await assert.rejects(tools[1].implementation({ params: {} }, ctx), /ComfyUI startup unavailable/);
  assert.equal(state.calls.length, 0);
  assert.equal(state.opened, 2); assert.equal(state.closed, 2);
});

test('fresh call forwards exact MCP arguments and unchanged TextContent with context then closes', async () => {
  const { connect, state } = backend();
  const tools = await toolsProvider(ctl, factory, connect);
  const params = { params: { prompt_id: 'existing-job' } };
  assert.equal(await tools[2].implementation(params, ctx), '{ "ok": true }\nsecond');
  assert.deepEqual(state.calls[0].args, { name: 'comfyui_poll_workflow', arguments: params });
  assert.equal(state.calls[0].context, ctx);
  assert.equal(state.calls[0].options, undefined);
  assert.equal(state.opened, 2); assert.equal(state.closed, 2);
});

test('backend error closes session without retry and already-aborted call never opens one', async () => {
  const { connect, state } = backend({ error: true });
  const [tool] = await toolsProvider(ctl, factory, connect);
  await assert.rejects(tool.implementation({}, ctx), /MCP failure/);
  assert.equal(state.calls.length, 1); assert.equal(state.closed, 2);
  const aborted = new AbortController(); aborted.abort();
  await assert.rejects(tool.implementation({}, { ...ctx, signal: aborted.signal }), { name: 'AbortError' });
  assert.equal(state.opened, 2);
});

test('MCP isError TextContent becomes a tool error with no automatic retry', async () => {
  let closed = 0;
  const connect = async operation => {
    try { return await operation({ request: async method => method === 'tools/list'
      ? { tools: names.map(name => ({ name, inputSchema: schema })) }
      : { isError: true, content: [{ type: 'text', text: 'exact failure' }] } }); }
    finally { closed++; }
  };
  const [tool] = await toolsProvider(ctl, factory, connect);
  await assert.rejects(tool.implementation({}, ctx), /exact failure/);
  assert.equal(closed, 2);
});

