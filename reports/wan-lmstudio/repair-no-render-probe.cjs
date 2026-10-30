'use strict';
const fs = require('node:fs');
const {LMStudioClient} = require('V:/LMStudio/.lmstudio/extensions/plugins/lmstudio/rag-v1/node_modules/@lmstudio/sdk/dist/index.cjs');
const server = JSON.parse(fs.readFileSync('V:/LMStudio/.lmstudio/.internal/http-server.json', 'utf8'));
if (server.host !== '127.0.0.1' || !Number.isInteger(server.port)) throw Error('Existing loopback server expected');
const cliCode = fs.readFileSync('V:/LMStudio/.lmstudio/bin/lms.exe').toString('latin1');
const literal = cliCode.match(/^var lmsKey = ("(?:[^"\\]|\\.)*");$/m);
if (!literal) throw Error('Existing CLI authentication mechanism not recognized');
const client = new LMStudioClient({baseUrl:`ws://127.0.0.1:${server.port}`, clientIdentifier:'lms-cli',
  clientPasskey:JSON.parse(literal[1]) + fs.readFileSync('V:/LMStudio/.lmstudio/.internal/lms-key-2', 'utf8').trim(),
  logger:{info(){}, error(){}, warn(){}, debug(){}}, verboseErrorMessages:false});
const report = {at:new Date().toISOString(), mode:'installed-native-provider-no-render-no-prediction',
  plugin:'morph/bilder-und-videos', calls:[], success:false, hostChatTested:false};
const scrub = e => String(e?.message ?? e).replace(/sk-lm-[^\s"']+/g, '[redacted-token]').replace(/clientPasskey[^\n]*/g, '[redacted-passkey]');
function deadline(promise, ms=60000) {let timer; return Promise.race([promise, new Promise((_,reject) => {
  timer=setTimeout(() => reject(Error('Native probe timeout')), ms);
})]).finally(() => clearTimeout(timer));}
function resultJson(result) { const txt = typeof result === 'string' ? result :
  (Array.isArray(result) ? result : result.content ?? []).filter(b => b.type === 'text').map(b => b.text).join('\n'); return JSON.parse(txt); }
(async () => {
  let session;
  try {
    report.loadedBefore = (await deadline(client.llm.listLoaded())).map(m => ({identifier:m.identifier,modelKey:m.modelKey}));
    await deadline(client.plugins.reindexPlugins()); report.reindexRequested=true;
    await new Promise(resolve => setTimeout(resolve, 1500));
    const start=Date.now();
    session=await deadline(client.plugins.pluginTools(report.plugin, {workingDirectory:'D:/MORPH-Studio'}));
    report.discoveryMs=Date.now()-start; report.tools=session.tools.map(t => t.name);
    if (report.tools.length !== 7) throw Error('Expected exactly seven native tools');
    for (const name of ['check_comfyui_status', 'comfyui_list_queue']) {
      const tool=session.tools.find(t => t.name===name); tool.checkParameters({});
      const started=Date.now();
      const result=resultJson(await deadline(tool.implementation({}, {status(){}, warn(){}, signal:new AbortController().signal, callId:report.calls.length+1})));
      report.calls.push({name, durationMs:Date.now()-started, result});
      if (result.ok===false || (name==='check_comfyui_status' && !result.running)) throw Error('Backend not ready: '+name);
    }
    report.success=true;
  } catch(error) {report.error=scrub(error); process.exitCode=1;}
  finally {
    if(session){session[Symbol.dispose](); report.sessionDisposed=true;}
    try {report.loadedAfter=(await deadline(client.llm.listLoaded())).map(m => ({identifier:m.identifier,modelKey:m.modelKey}));} catch(error){report.loadedAfterError=scrub(error);}
    await client[Symbol.asyncDispose](); report.clientDisposed=true;
    report.finishedAt=new Date().toISOString();
    fs.writeFileSync('D:/MORPH-Studio/reports/wan-lmstudio/repair-no-render-probe.json', JSON.stringify(report,null,2)+'\n');
    console.log(JSON.stringify(report,null,2));
  }
})().catch(error => {console.log(scrub(error)); process.exitCode=1;});
