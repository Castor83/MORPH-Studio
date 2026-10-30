'use strict';
// One authorized face swap through the actually installed LM Studio provider.
const fs = require('node:fs');
const crypto = require('node:crypto');
const path = require('node:path');
const reportPath = 'D:/MORPH-Studio/reports/reactor-lmstudio/first-face-swap.json';
if (fs.existsSync(reportPath)) throw Error('A first-face-swap receipt already exists; do not submit again.');
const {LMStudioClient, ChatMessage} = require('V:/LMStudio/.lmstudio/extensions/plugins/lmstudio/rag-v1/node_modules/@lmstudio/sdk/dist/index.cjs');
const server = JSON.parse(fs.readFileSync('V:/LMStudio/.lmstudio/.internal/http-server.json', 'utf8'));
if (server.host !== '127.0.0.1' || !Number.isInteger(server.port)) throw Error('Existing loopback server expected');
const cliCode = fs.readFileSync('V:/LMStudio/.lmstudio/bin/lms.exe').toString('latin1');
const literal = cliCode.match(/^var lmsKey = ("(?:[^"\\]|\\.)*");$/m);
if (!literal) throw Error('Existing CLI authentication mechanism not recognized');
const client = new LMStudioClient({baseUrl:`ws://127.0.0.1:${server.port}`, clientIdentifier:'lms-cli',
  clientPasskey:JSON.parse(literal[1]) + fs.readFileSync('V:/LMStudio/.lmstudio/.internal/lms-key-2', 'utf8').trim(),
  logger:{info(){}, error(){}, warn(){}, debug(){}}, verboseErrorMessages:false});
const report = {at:new Date().toISOString(), mode:'installed-native-provider-real-render-no-chat-prediction',
  plugin:'morph/bilder-und-videos', success:false, submissions:0, calls:[],
  source:'D:/sal/Screenshot 2025-03-03 161945 (1).png', target:'D:/sal/LOVESCAPE.png',
  userDirection:'Screenshot face into LOVESCAPE', hostChatPreprocessorInvoked:false};
const scrub = e => String(e?.message ?? e).replace(/sk-lm-[^\s"']+/g, '[redacted-token]').replace(/clientPasskey[^\n]*/g, '[redacted-passkey]');
const sha = p => crypto.createHash('sha256').update(fs.readFileSync(p)).digest('hex');
const save = () => fs.writeFileSync(reportPath, JSON.stringify(report, null, 2) + '\n');
function deadline(promise, ms=90000) { let timer; return Promise.race([promise, new Promise((_,reject) => {
  timer=setTimeout(() => reject(Error('Native tool call timeout')), ms);
})]).finally(() => clearTimeout(timer)); }
function resultJson(result) { const txt = typeof result === 'string' ? result :
  (Array.isArray(result) ? result : result.content ?? []).filter(b => b.type === 'text').map(b => b.text).join('\n'); return JSON.parse(txt); }
(async () => {
  let session;
  const tempPaths=[];
  try {
    report.loadedBefore = (await deadline(client.llm.listLoaded())).map(m => ({identifier:m.identifier, modelKey:m.modelKey}));
    session = await deadline(client.plugins.pluginTools(report.plugin, {workingDirectory:'D:/MORPH-Studio'}));
    async function call(name, args) {
      const tool = session.tools.find(t => t.name === name);
      if (!tool) throw Error('Tool not available: ' + name);
      tool.checkParameters(args);
      const result = resultJson(await deadline(tool.implementation(args, {status(){}, warn(){},
        signal:new AbortController().signal, callId:report.calls.length + 1})));
      report.calls.push({at:new Date().toISOString(), name, result}); save();
      if (result.ok === false) throw Error(name + ': ' + result.error);
      return result;
    }
    const queue = await call('comfyui_list_queue', {});
    if (queue.queue_remaining !== 0) throw Error('Queue is busy; no job submitted');
    const message = ChatMessage.create('user', 'Das Gesicht aus dem Screenshot in das LOVESCAPE-Bild einsetzen. Erhalte die übrige Szene.');
    report.attachments=[];
    for (const [role, original] of [['source', report.source], ['target', report.target]]) {
      const file = await deadline(client.files.prepareImage(original));
      const prepared = await deadline(file.getFilePath()); tempPaths.push(prepared);
      message.appendFile(file);
      report.attachments.push({role, original, prepared, originalHash:sha(original), preparedHash:sha(prepared)});
    }
    const {preprocess} = await import('file:///V:/LMStudio/.lmstudio/extensions/plugins/morph/bilder-und-videos/src/promptPreprocessor.mjs');
    const processed = await preprocess({client, abortSignal:new AbortController().signal}, message);
    report.retainedFiles = processed.getFiles(client).length;
    report.resolvedPathsAdded = processed.getText().includes(JSON.stringify(tempPaths));
    if (report.retainedFiles !== 2 || !report.resolvedPathsAdded) throw Error('Two-image attachment preprocessing failed');
    const upload = await call('comfyui_upload_image', {params:{paths:tempPaths, subfolder:'lmstudio/reactor', overwrite:false}});
    if (upload.uploaded_count !== 2 || upload.failed_count !== 0) throw Error('Expected two successful image uploads');
    for (const attachment of report.attachments) {
      const uploaded = upload.uploaded.find(item => path.resolve(item.path).toLowerCase() === path.resolve(attachment.prepared).toLowerCase());
      if (!uploaded) throw Error('Upload role could not be matched by file path');
      attachment.load_image_name = uploaded.load_image_name;
      const inputRoot = path.resolve('D:/MORPH-Studio/input');
      const copy = path.resolve(inputRoot, attachment.load_image_name);
      if (!copy.toLowerCase().startsWith(inputRoot.toLowerCase() + path.sep)) throw Error('Upload escaped input directory');
      attachment.uploadedHash = sha(copy);
      if (attachment.originalHash !== attachment.preparedHash || attachment.originalHash !== attachment.uploadedHash) throw Error('Image bytes changed during attachment upload');
    }
    const source = report.attachments.find(a => a.role === 'source');
    const target = report.attachments.find(a => a.role === 'target');
    const freshQueue = await call('comfyui_list_queue', {});
    if (freshQueue.queue_remaining !== 0) throw Error('Queue became busy; no job submitted');
    const params = {workflow_path:'D:/MORPH-Studio/workflows/LMStudio-Gesichtstausch-ReActor-api.json',
      overrides:{'1.image':target.load_image_name, '2.image':source.load_image_name,
        '4.filename_prefix':'LMStudio/LOVESCAPE-Gesichtstausch'}, label:'Screenshot-Gesicht in LOVESCAPE'};
    report.request=params; report.submissions=1; save();
    const submitted = await call('comfyui_run_workflow', {params});
    report.prompt_id = submitted.prompt_id; save();
    console.log(JSON.stringify({state:'submitted', prompt_id:report.prompt_id}));
    const until=Date.now()+600000;
    let lastState;
    while (Date.now() < until) {
      const poll = await call('comfyui_poll_workflow', {params:{prompt_id:report.prompt_id}});
      report.status=poll.status; save();
      if (lastState !== poll.status) { console.log(JSON.stringify({state:poll.status, prompt_id:report.prompt_id})); lastState=poll.status; }
      if (poll.status === 'failed' || poll.status === 'error' || poll.status === 'cancelled') throw Error('Face swap ended: ' + JSON.stringify(poll));
      if (poll.status === 'completed') {
        report.outputs=await call('comfyui_get_outputs', {params:{prompt_id:report.prompt_id}});
        if (report.outputs.output_count !== 1 || !report.outputs.outputs[0].exists) throw Error('Expected one existing output');
        report.success=true; break;
      }
      await new Promise(resolve => setTimeout(resolve, 15000));
    }
    if (!report.success) throw Error('Job still unfinished after bounded polling; do not resubmit');
  } catch (error) { report.error=scrub(error); }
  finally {
    if (session) { session[Symbol.dispose](); report.sessionDisposed=true; }
    try { report.loadedAfter=(await deadline(client.llm.listLoaded())).map(m => ({identifier:m.identifier,modelKey:m.modelKey})); } catch(error) { report.loadedAfterError=scrub(error); }
    for (const attachment of report.attachments ?? []) attachment.originalHashAfter=sha(attachment.original);
    await client[Symbol.asyncDispose](); report.clientDisposed=true;
    report.finishedAt=new Date().toISOString(); save();
    console.log(JSON.stringify({success:report.success, status:report.status, prompt_id:report.prompt_id,
      outputs:report.outputs, error:report.error}));
    if (!report.success) process.exitCode=1;
  }
})().catch(error => { console.log(scrub(error)); process.exitCode=1; });
