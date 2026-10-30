import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import zlib from 'node:zlib';
import { fileURLToPath } from 'node:url';
import { toolsProvider } from 'file:///C:/Users/USER/.lmstudio/extensions/plugins/morph/bilder-und-videos/src/toolsProxy.mjs';

const folder = path.dirname(fileURLToPath(import.meta.url));
const reportFile = path.join(folder, 'installed-provider-result.json');
const fixture = path.join(folder, 'neutral-upload-test.png');
function crc32(data) {
  let crc = 0xffffffff;
  for (const b of data) {
    crc ^= b;
    for (let i = 0; i < 8; i++) crc = (crc >>> 1) ^ (0xedb88320 & -(crc & 1));
  }
  return (crc ^ 0xffffffff) >>> 0;
}
function chunk(type, data) {
  const tag = Buffer.from(type), size = Buffer.alloc(4), crc = Buffer.alloc(4);
  size.writeUInt32BE(data.length); crc.writeUInt32BE(crc32(Buffer.concat([tag, data])));
  return Buffer.concat([size, tag, data, crc]);
}
const header = Buffer.alloc(13);
header.writeUInt32BE(32, 0); header.writeUInt32BE(32, 4); header[8] = 8; header[9] = 2;
const pixels = Buffer.alloc(32 * (1 + 32 * 3), 255);
for (let row = 0; row < 32; row++) pixels[row * 97] = 0;
fs.writeFileSync(fixture, Buffer.concat([Buffer.from([137,80,78,71,13,10,26,10]),
  chunk('IHDR', header), chunk('IDAT', zlib.deflateSync(pixels)), chunk('IEND', Buffer.alloc(0))]));
const hash = file => crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex');
const result = { at: new Date().toISOString(), fixture, fixtureHash: hash(fixture),
  noModelPrediction: true, noRenderSubmission: true, success: false };
const control = new AbortController();
const context = { signal: control.signal, status: message => console.log('Status:', message), warn: message => console.log('Warning:', message) };
try {
  const tools = await toolsProvider({ abortSignal: control.signal }, definition => definition);
  result.tools = tools.map(tool => tool.name);
  console.log('Registered tools:', tools.length);
  const call = async (name, parameters) => {
    const tool = tools.find(item => item.name === name);
    if (!tool) throw new Error('Missing tool: ' + name);
    const properties = tool.parametersJsonSchema.properties ?? {};
    const args = 'params' in properties ? { params: parameters } : parameters;
    return JSON.parse(await tool.implementation(args, context));
  };
  result.status = await call('check_comfyui_status', {});
  console.log('ComfyUI status:', JSON.stringify(result.status));
  if (!result.status.running) throw new Error('ComfyUI did not become ready');
  if (result.status.queue_running || result.status.queue_pending) throw new Error('Existing queue is not empty; stopping the probe');
  result.upload = await call('comfyui_upload_image', { paths: [fixture], subfolder: 'Diagnose-20261010', overwrite: false });
  console.log('Upload:', JSON.stringify(result.upload));
  if (!result.upload.ok || result.upload.uploaded?.length !== 1 || result.upload.failed?.length) throw new Error('Neutral upload did not complete');
  const key = result.upload.uploaded[0].load_image_name;
  const uploaded = path.resolve('D:/MORPH-Studio/input', key);
  if (!uploaded.startsWith(path.resolve('D:/MORPH-Studio/input') + path.sep)) throw new Error('Unexpected upload destination');
  result.uploadedHash = hash(uploaded);
  if (result.uploadedHash !== result.fixtureHash || hash(fixture) !== result.fixtureHash) throw new Error('Upload bytes changed');
  result.queue = await call('comfyui_list_queue', {});
  if (!result.queue.ok || result.queue.queue_remaining !== 0) throw new Error('Queue check failed');
  result.success = true;
} catch (error) {
  result.error = error.message;
  process.exitCode = 1;
} finally {
  fs.writeFileSync(reportFile, JSON.stringify(result, null, 2) + '\n');
  console.log(JSON.stringify(result, null, 2));
}
