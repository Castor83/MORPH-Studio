import test from 'node:test';
import assert from 'node:assert/strict';
import { EventEmitter } from 'node:events';
import { PassThrough, Writable } from 'node:stream';

let transport;
try { transport = await import('../src/mcpTransport.mjs'); } catch (error) {
  if (error.code !== 'ERR_MODULE_NOT_FOUND') throw error;
}

function fakeProcess(mode = 'ok') {
  const child = new EventEmitter();
  child.stdout = new PassThrough(); child.stderr = new PassThrough();
  child.messages = []; child.closed = false; child.kills = 0;
  child.stdin = new Writable({ write(chunk, encoding, callback) {
    const message = JSON.parse(chunk.toString()); child.messages.push(message); callback();
    if (!message.id || mode === 'silent') return;
    queueMicrotask(() => {
      const result = message.method === 'initialize' ? { protocolVersion: '2024-11-05', capabilities: { tools: {} }, serverInfo: { name: 'fake', version: '1' } }
        : message.method === 'tools/list' ? { tools: [{ name: 'queue', inputSchema: { type: 'object' } }] }
          : { content: [{ type: 'text', text: 'exact text' }] };
      child.stdout.write(JSON.stringify(mode === 'rpcError' && message.method === 'tools/call'
        ? { jsonrpc: '2.0', id: message.id, error: { code: -32602, message: 'bad params' } }
        : { jsonrpc: '2.0', id: message.id, result }) + '\n');
    });
  }, final(callback) { child.closed = true; callback(); queueMicrotask(() => child.emit('close', 0)); } });
  child.kill = () => { child.kills++; child.closed = true; child.emit('close', null); return true; };
  return child;
}

function setup(mode = 'ok', options = {}) {
  assert.ok(transport, 'Der lokale MCP-Transport fehlt noch.');
  const child = fakeProcess(mode);
  let spawned;
  const settings = { spawnProcess: (...args) => { spawned = args; return child; }, startupTimeoutMs: 30,
    callTimeoutMs: 30, closeTimeoutMs: 30, ...options };
  return { child, settings, spawned: () => spawned };
}

test('initialize, initialized notification, tools/list then tools/call use hidden fixed local Python and close', async () => {
  const { child, settings, spawned } = setup();
  const result = await transport.withMcpSession(async session => {
    assert.equal((await session.request('tools/list', {})).tools[0].name, 'queue');
    return session.request('tools/call', { name: 'queue', arguments: { params: {} } });
  }, {}, settings);
  assert.equal(result.content[0].text, 'exact text');
  assert.deepEqual(child.messages.map(message => message.method), ['initialize', 'notifications/initialized', 'tools/list', 'tools/call']);
  assert.equal(child.messages[0].params.protocolVersion, '2024-11-05');
  assert.equal(spawned()[0], 'E:/MORPH-Studio/ComfyUI_windows_portable/python_embeded/python.exe');
  assert.deepEqual(spawned()[1], ['-s', '-X', 'utf8', 'E:/MORPH-Studio/tools/lmstudio-wan-chat/start_mcp.py']);
  assert.equal(spawned()[2].windowsHide, true); assert.equal(spawned()[2].cwd, 'E:/MORPH-Studio');
  assert.equal(spawned()[2].env.TEMP, 'E:/MORPH-Studio/temp');
  assert.equal(child.closed, true);
});

test('discovery can initialize and list schemas when ComfyUI startup is unavailable', async () => {
  let child, spawned;
  const result = await transport.withMcpSession(session => session.request('tools/list', {}), {}, {
    startComfy: false, startupTimeoutMs: 30, callTimeoutMs: 30, closeTimeoutMs: 30,
    spawnProcess: (...args) => {
      spawned = args;
      child = fakeProcess(args[1].includes('--no-autostart') ? 'ok' : 'silent');
      return child;
    },
  });
  assert.equal(result.tools[0].name, 'queue');
  assert.deepEqual(spawned[1], ['-s', '-X', 'utf8',
    'E:/MORPH-Studio/tools/lmstudio-wan-chat/start_mcp.py', '--no-autostart']);
  assert.deepEqual(child.messages.map(message => message.method), ['initialize', 'notifications/initialized', 'tools/list']);
  assert.equal(child.closed, true);
});

test('JSONRPC error closes its child and is not retried', async () => {
  const { child, settings } = setup('rpcError');
  await assert.rejects(transport.withMcpSession(session => session.request('tools/call', { name: 'queue' }), {}, settings), /bad params/);
  assert.equal(child.messages.filter(message => message.method === 'tools/call').length, 1);
  assert.equal(child.closed, true);
});

test('abort during pending startup cancels session and already-aborted request never spawns', async () => {
  const { child, settings } = setup('silent');
  const abort = new AbortController();
  const pending = transport.withMcpSession(() => assert.fail('must not invoke'), { signal: abort.signal }, settings);
  abort.abort();
  await assert.rejects(pending, { name: 'AbortError' }); assert.equal(child.closed, true);
  const before = child.messages.length;
  await assert.rejects(transport.withMcpSession(() => {}, { signal: abort.signal }, settings), { name: 'AbortError' });
  assert.equal(child.messages.length, before);
});

test('timeout and malformed/oversized stdout fail closed and dispose the child', async () => {
  const silent = setup('silent');
  await assert.rejects(transport.withMcpSession(() => {}, {}, silent.settings), /timeout/i);
  assert.equal(silent.child.closed, true);
  for (const text of ['not JSON\n', 'x'.repeat(1024)]) {
    const local = setup('silent', { maxStdoutBytes: 512 });
    const pending = transport.withMcpSession(() => {}, {}, local.settings);
    local.child.stdout.write(text);
    await assert.rejects(pending, /protocol|stdout/i); assert.equal(local.child.closed, true);
  }
});

test('optional progress/log notifications reach status and warn without contaminating responses', async () => {
  const { child, settings } = setup(); const status = [], warnings = [];
  await transport.withMcpSession(async session => {
    child.stdout.write(JSON.stringify({ jsonrpc: '2.0', method: 'notifications/progress', params: { progress: 1, total: 2, message: 'working' } }) + '\n');
    child.stdout.write(JSON.stringify({ jsonrpc: '2.0', method: 'notifications/message', params: { level: 'warning', data: 'careful' } }) + '\n');
    await session.request('tools/list', {});
  }, { status: text => status.push(text), warn: text => warnings.push(text) }, settings);
  assert.deepEqual(status, ['working']); assert.deepEqual(warnings, ['careful']);
});

test('LM host plugin authentication stays in parent and is never forwarded to Python MCP', async () => {
  const keys = ['LMS_PLUGIN_CLIENT_PASSKEY', 'LMS_PLUGIN_CLIENT_IDENTIFIER', 'LMS_PLUGIN_BASE_URL'];
  const original = keys.map(key => process.env[key]);
  try {
    for (const key of keys) process.env[key] = 'test-only-parent-value';
    const { settings, spawned } = setup();
    await transport.withMcpSession(session => session.request('tools/list', {}), {}, settings);
    for (const key of keys) {
      assert.equal(key in spawned()[2].env, false);
      assert.equal(process.env[key], 'test-only-parent-value');
    }
  } finally {
    keys.forEach((key, index) => { if (original[index] === undefined) delete process.env[key]; else process.env[key] = original[index]; });
  }
});

