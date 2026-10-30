import test from 'node:test';
import assert from 'node:assert/strict';
import { preprocess } from '../src/promptPreprocessor.mjs';

function message(text, files = []) {
  return { text, files, hasFiles() { return this.files.length > 0; }, getText() { return this.text; }, getFiles() { return this.files; }, appendText(value) { this.text += value; } };
}
const ctl = { client: {}, abortSignal: new AbortController().signal };
const image = path => ({ isImage: () => true, getFilePath: async () => path });

test('annotates exact Windows attachment path while retaining text and vision attachment', async () => {
  const path = 'C:\\Fotos\\Kleidung & Katze ü (1).jpg';
  const file = image(path);
  const msg = message('Ändere nur die Jacke.', [file]);
  assert.equal(await preprocess(ctl, msg), msg);
  assert.ok(msg.getText().startsWith('Ändere nur die Jacke.'));
  assert.ok(msg.getText().includes(JSON.stringify([path])));
  assert.deepEqual(msg.files, [file]);
  assert.match(msg.getText(), /comfyui_upload_image/);
});

test('does not alter ordinary text or document-only messages', async () => {
  const msg = message('Was ist auf dem Bild?', [{ isImage: () => false }]);
  await preprocess(ctl, msg);
  assert.equal(msg.text, 'Was ist auf dem Bild?');
  const plain = message('Hallo');
  await preprocess(ctl, plain);
  assert.equal(plain.text, 'Hallo');
});

test('multiple images remain explicit choices and are not silently reduced to the first', async () => {
  const msg = message('Vergleiche diese Bilder', [image('C:\\a.jpg'), image('C:\\b.png')]);
  await preprocess(ctl, msg);
  assert.ok(msg.text.includes(JSON.stringify(['C:\\a.jpg', 'C:\\b.png'])));
  assert.match(msg.text, /mehreren Bildern/);
});

test('failed attachment resolution is disclosed without discarding the image', async () => {
  const file = { isImage: () => true, getFilePath: async () => { throw new Error('Not implemented'); } };
  const msg = message('Mach daraus ein Video', [file]);
  await preprocess(ctl, msg);
  assert.match(msg.text, /Bildpfad.*nicht/);
  assert.equal(msg.files[0], file);
  assert.ok(!msg.text.includes('589682038'));
});

test('annotating the same message twice is idempotent', async () => {
  const msg = message('Andere Kleidung', [image('C:\\a.jpg')]);
  await preprocess(ctl, msg);
  const once = msg.text;
  await preprocess(ctl, msg);
  assert.equal(msg.text, once);
});

test('aborted send does not annotate or process an attachment', async () => {
  const abort = new AbortController(); abort.abort();
  let accessed = false;
  const msg = message('Video', [{ isImage: () => true, getFilePath: async () => { accessed = true; return 'C:\\a.jpg'; } }]);
  await assert.rejects(preprocess({ ...ctl, abortSignal: abort.signal }, msg), { name: 'AbortError' });
  assert.equal(accessed, false);
});
