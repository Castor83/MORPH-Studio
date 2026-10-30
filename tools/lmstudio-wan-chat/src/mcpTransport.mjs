import { spawn } from 'node:child_process';

const root = 'E:/MORPH-Studio';
const python = root + '/ComfyUI_windows_portable/python_embeded/python.exe';
const wrapper = root + '/tools/lmstudio-wan-chat/start_mcp.py';

function localEnvironment() {
  const inherited = Object.fromEntries(Object.entries(process.env)
    .filter(([key]) => !key.toUpperCase().startsWith('LMS_PLUGIN_')));
  return { ...inherited, TEMP: root + '/temp', TMP: root + '/temp',
    PYTHONUTF8: '1', PYTHONIOENCODING: 'utf-8', PYTHONPYCACHEPREFIX: root + '/cache/pycache',
    HF_HOME: root + '/cache/huggingface', HF_HUB_CACHE: root + '/cache/huggingface/hub',
    TORCH_HOME: root + '/cache/torch', PIP_CACHE_DIR: root + '/cache/pip',
    XDG_CACHE_HOME: root + '/cache', CUDA_CACHE_PATH: root + '/cache/cuda',
    TRITON_CACHE_DIR: root + '/cache/triton', HF_HUB_OFFLINE: '1', TRANSFORMERS_OFFLINE: '1' };
}

class LocalSession {
  constructor(context, options) {
    this.context = context;
    this.options = { spawnProcess: spawn, startComfy: true, startupTimeoutMs: 180000, callTimeoutMs: 20000,
      closeTimeoutMs: 2000, maxStdoutBytes: 4 * 1024 * 1024, ...options };
    this.pending = new Map(); this.nextId = 1; this.buffer = ''; this.received = 0;
    const args = ['-s', '-X', 'utf8', wrapper];
    if (this.options.startComfy === false) args.push('--no-autostart');
    this.child = this.options.spawnProcess(python, args, {
      cwd: root, windowsHide: true, stdio: ['pipe', 'pipe', 'pipe'], env: localEnvironment(),
    });
    this.closed = new Promise(resolve => { this.resolveClosed = resolve; });
    this.child.stdout.setEncoding('utf8');
    this.child.stderr.setEncoding('utf8');
    this.stderr = '';
    this.child.stderr.on('data', chunk => { this.stderr = (this.stderr + chunk).slice(-8192); });
    this.child.stdout.on('data', chunk => this.receive(chunk));
    this.child.stdout.on('error', error => this.fail(error));
    this.child.stdin.on('error', error => this.fail(error));
    this.child.on('error', error => this.fail(error));
    this.child.on('close', (code, signal) => {
      this.exited = true;
      if (!this.closing) this.fail(new Error('Local MCP exited before completion (' + (code ?? signal) + '). ' + this.stderr));
      this.resolveClosed();
    });
    this.abort = () => this.fail(context.signal.reason ?? new DOMException('Aborted', 'AbortError'));
    context.signal?.addEventListener('abort', this.abort, { once: true });
  }

  fail(error) {
    this.failure ??= error;
    for (const item of this.pending.values()) { clearTimeout(item.timer); item.reject(this.failure); }
    this.pending.clear();
  }

  receive(chunk) {
    if (this.failure || this.closing) return;
    this.received += Buffer.byteLength(chunk);
    if (this.received > this.options.maxStdoutBytes) {
      this.fail(new Error('MCP stdout exceeded its permitted size.')); return;
    }
    this.buffer += chunk;
    while (this.buffer.includes('\n')) {
      const index = this.buffer.indexOf('\n');
      const line = this.buffer.slice(0, index).trim(); this.buffer = this.buffer.slice(index + 1);
      if (!line) continue;
      try {
        const message = JSON.parse(line);
        if (!message || message.jsonrpc !== '2.0') throw new Error('Invalid JSONRPC envelope');
        if (message.id !== undefined) {
          const item = this.pending.get(message.id);
          if (!item) continue;
          this.pending.delete(message.id); clearTimeout(item.timer);
          if (message.error) item.reject(new Error('MCP JSONRPC error ' + message.error.code + ': ' + message.error.message));
          else if ('result' in message) item.resolve(message.result);
          else item.reject(new Error('Invalid MCP protocol response.'));
        } else if (message.method === 'notifications/progress') {
          const data = message.params ?? {};
          this.context.status?.(data.message ?? ('MCP progress: ' + data.progress + (data.total === undefined ? '' : '/' + data.total)));
        } else if (message.method === 'notifications/message') {
          const data = message.params ?? {};
          const text = typeof data.data === 'string' ? data.data : JSON.stringify(data.data);
          if (['warning', 'error', 'critical', 'alert', 'emergency'].includes(data.level)) this.context.warn?.(text);
          else this.context.status?.(text);
        }
      } catch (error) { this.fail(new Error('Invalid MCP stdout protocol: ' + error.message)); return; }
    }
  }

  write(message) {
    if (this.failure) throw this.failure;
    this.context.signal?.throwIfAborted();
    this.child.stdin.write(JSON.stringify(message) + '\n', error => { if (error) this.fail(error); });
  }

  request(method, params, timeout = this.options.callTimeoutMs) {
    if (this.failure) return Promise.reject(this.failure);
    if (this.context.signal?.aborted) return Promise.reject(this.context.signal.reason);
    const id = this.nextId++;
    return new Promise((resolve, reject) => {
      const timer = setTimeout(() => this.fail(new Error('MCP ' + method + ' timeout.')), timeout);
      this.pending.set(id, { resolve, reject, timer });
      try { this.write({ jsonrpc: '2.0', id, method, params }); } catch (error) { this.fail(error); }
    });
  }

  async initialize() {
    const result = await this.request('initialize', { protocolVersion: '2024-11-05', capabilities: {},
      clientInfo: { name: 'morph-lmstudio-chat', version: '1.0.0' } }, this.options.startupTimeoutMs);
    if (result?.protocolVersion !== '2024-11-05') throw new Error('Unsupported MCP protocol version: ' + result?.protocolVersion);
    this.write({ jsonrpc: '2.0', method: 'notifications/initialized' });
  }

  async close() {
    this.closing = true;
    this.context.signal?.removeEventListener('abort', this.abort);
    this.fail(new Error('MCP session closed.'));
    if (this.exited) return;
    // EOF normally closes the MCP wrapper; any forced termination targets this child only.
    if (!this.child.stdin.destroyed) this.child.stdin.end();
    const timer = setTimeout(() => { if (!this.exited) this.child.kill(); }, this.options.closeTimeoutMs);
    try { await this.closed; } finally { clearTimeout(timer); }
  }
}

export async function withMcpSession(operation, context = {}, options = {}) {
  context.signal?.throwIfAborted();
  const session = new LocalSession(context, options);
  try { await session.initialize(); return await operation(session); }
  finally { await session.close(); }
}
