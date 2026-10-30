'use strict';
const fs = require('node:fs');
const crypto = require('node:crypto');
const {LMStudioClient, ChatMessage, Chat} = require('V:/LMStudio/.lmstudio/extensions/plugins/lmstudio/rag-v1/node_modules/@lmstudio/sdk/dist/index.cjs');
const server = JSON.parse(fs.readFileSync('V:/LMStudio/.lmstudio/.internal/http-server.json','utf8'));
if (server.host !== '127.0.0.1' || !Number.isInteger(server.port)) throw new Error('Expected existing loopback internal server.');
const baseUrl = `ws://127.0.0.1:${server.port}`;
const cliMode=process.argv.includes('--existing-cli-auth');
const reportPath = `D:/MORPH-Studio/reports/wan-lmstudio/native-sdk-no-render-probe${cliMode?'-cli':''}.json`;
let authOptions={};
if(cliMode){
  const cliCode=fs.readFileSync('V:/LMStudio/.lmstudio/bin/lms.exe').toString('latin1');
  const literal=cliCode.match(/^var lmsKey = ("(?:[^"\\]|\\.)*");$/m);
  if(!literal)throw new Error('Installed CLI authentication constant format not recognized.');
  const prefix=JSON.parse(literal[1]);
  const localKey=fs.readFileSync('V:/LMStudio/.lmstudio/.internal/lms-key-2','utf8').trim();
  authOptions={clientIdentifier:'lms-cli',clientPasskey:prefix+localKey};
}
const report = {at:new Date().toISOString(), sdkVersion:'1.5.0', baseUrl, authentication:cliMode?'existing-local-CLI-mechanism':'default-guest', mode:'no-model-no-render', tools:[], attachment:null};
const silentLogger = {info(){},warn(){},error(){},debug(){}};
function scrub(value) { return String(value).replace(/sk-lm-[^\s"']+/g,'[redacted-token]').replace(/clientPasskey[^\n]*/g,'[redacted-passkey]'); }
function timeout(promise, ms=12000) { let timer; return Promise.race([promise,new Promise((_,reject)=>{timer=setTimeout(()=>reject(new Error('Probe timeout')),ms)})]).finally(()=>clearTimeout(timer)); }
async function usingClient(task) {
  const client = new LMStudioClient({baseUrl,...authOptions,logger:silentLogger,verboseErrorMessages:false});
  try {return await task(client);} finally {await client[Symbol.asyncDispose]();}
}
(async()=>{
  try {
    report.loadedBefore = await usingClient(client=>timeout(client.llm.listLoaded())).then(models=>models.map(m=>({identifier:m.identifier,modelKey:m.modelKey})));
  } catch(error) {report.connectionError=scrub(error.message);}
  for (const id of ['mcp/wan-comfy-ui','mcp/Wan-ComfyUI']) {
    const entry = {id}; report.tools.push(entry);
    try {
      await usingClient(async client=>{
        const session = await timeout(client.plugins.pluginTools(id));
        try {
          entry.definitions=session.tools.map(tool=>({name:tool.name,type:tool.type,pluginIdentifier:tool.pluginIdentifier,parametersJsonSchema:tool.parametersJsonSchema}));
          entry.calls=[];
          for (const name of ['check_comfyui_status','comfyui_list_queue']) {
            const tool=session.tools.find(tool=>tool.name===name);
            if (!tool) {entry.calls.push({name,error:'Exact named read-only tool not found'});continue;}
            tool.checkParameters({});
            const statuses=[];
            const result=await timeout(tool.implementation({}, {status:text=>statuses.push(text),warn:text=>statuses.push(text),signal:new AbortController().signal,callId:entry.calls.length+1}));
            entry.calls.push({name,result,statuses});
          }
        } finally {session[Symbol.dispose](); entry.sessionDisposed=true;}
      });
    } catch(error) {entry.error=scrub(error.message);}
  }
  if(!cliMode)try {
    await usingClient(async client=>{
      const source='C:/Users/USER/Desktop/rtzu/589682038_17903637102306091_4752592283070689792_n.jpg';
      const file=await timeout(client.files.prepareImage(source));
      const local=await timeout(file.getFilePath());
      const message=ChatMessage.create('user','No-render attachment test');
      message.appendFile(file);
      const retained=message.getFiles(client);
      const chat=Chat.empty(); chat.append(message);
      report.attachment={name:file.name,type:file.type,sizeBytes:file.sizeBytes,localPath:local,retainedFiles:retained.length,chatFiles:chat.getAllFiles(client).length,sameIdentifier:retained[0]?.identifier===file.identifier,sourceHash:crypto.createHash('sha256').update(fs.readFileSync(source)).digest('hex'),preparedHash:crypto.createHash('sha256').update(fs.readFileSync(local)).digest('hex')};
    });
  } catch(error) {report.attachment={error:scrub(error.message)};}
  try {report.loadedAfter=await usingClient(client=>timeout(client.llm.listLoaded())).then(models=>models.map(m=>({identifier:m.identifier,modelKey:m.modelKey})));} catch(error){report.loadedAfterError=scrub(error.message);}
  fs.writeFileSync(reportPath,JSON.stringify(report,null,2)+'\n');
  console.log(JSON.stringify(report,null,2));
})().catch(error=>{report.fatalError=scrub(error.message);fs.writeFileSync(reportPath,JSON.stringify(report,null,2)+'\n');console.log(JSON.stringify(report,null,2));process.exitCode=1;});
