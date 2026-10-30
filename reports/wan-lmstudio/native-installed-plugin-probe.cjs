'use strict';
const fs = require('node:fs');
const crypto = require('node:crypto');
const path = require('node:path');
const {LMStudioClient, ChatMessage} = require('V:/LMStudio/.lmstudio/extensions/plugins/lmstudio/rag-v1/node_modules/@lmstudio/sdk/dist/index.cjs');
const server = JSON.parse(fs.readFileSync('V:/LMStudio/.lmstudio/.internal/http-server.json','utf8'));
if (server.host !== '127.0.0.1' || !Number.isInteger(server.port)) throw new Error('Existing loopback server expected');
const cliCode=fs.readFileSync('V:/LMStudio/.lmstudio/bin/lms.exe').toString('latin1');
const literal=cliCode.match(/^var lmsKey = ("(?:[^"\\]|\\.)*");$/m);
if(!literal)throw new Error('Existing CLI authentication mechanism not recognized');
const client=new LMStudioClient({baseUrl:`ws://127.0.0.1:${server.port}`,clientIdentifier:'lms-cli',clientPasskey:JSON.parse(literal[1])+fs.readFileSync('V:/LMStudio/.lmstudio/.internal/lms-key-2','utf8').trim(),logger:{info(){},error(){},warn(){},debug(){}},verboseErrorMessages:false});
const report={at:new Date().toISOString(),mode:'no-model-no-render',authentication:'existing-local-CLI-mechanism-in-memory',plugin:'morph/bilder-und-videos',buildReceiptAt:JSON.parse(fs.readFileSync('D:/MORPH-Studio/reports/wan-lmstudio/native-offline-install.json','utf8')).at,calls:[],preprocessorNativeInvocation:'No public SDK invocation for a preprocessor without a prediction step was found; host chat invocation not tested.',priorFailureReceipt:'D:/MORPH-Studio/reports/wan-lmstudio/native-installed-plugin-probe-permission-failure.json'};
const scrub=e=>String(e?.message??e).replace(/sk-lm-[^\s"']+/g,'[redacted-token]').replace(/clientPasskey[^\n]*/g,'[redacted-passkey]');
function deadline(promise,ms=60000){let timer;return Promise.race([promise,new Promise((_,reject)=>{timer=setTimeout(()=>reject(Error('Native probe timeout')),ms)})]).finally(()=>clearTimeout(timer));}
const sha=p=>crypto.createHash('sha256').update(fs.readFileSync(p)).digest('hex');
function resultJson(result){const text=typeof result==='string'?result:(Array.isArray(result)?result:result.content??[]).filter(b=>b.type==='text').map(b=>b.text).join('\n');return JSON.parse(text);}
(async()=>{
 let session, preparedPath;
 try{
  report.loadedBefore=(await deadline(client.llm.listLoaded())).map(m=>({identifier:m.identifier,modelKey:m.modelKey}));
  if(!process.argv.includes('--after-reindex')){await deadline(client.plugins.reindexPlugins());report.reindexRequested=true;await new Promise(resolve=>setTimeout(resolve,1500));}
  else {report.reindexRequestedEarlier=true;await new Promise(resolve=>setTimeout(resolve,1000));}
  session=await deadline(client.plugins.pluginTools(report.plugin,{workingDirectory:'D:/MORPH-Studio'}));
  report.tools=session.tools.map(t=>({name:t.name,type:t.type,pluginIdentifier:t.pluginIdentifier,parametersJsonSchema:t.parametersJsonSchema}));
  if(session.tools.length!==7)throw Error('Expected exactly seven native provider tools');
  async function call(name,args){
   const tool=session.tools.find(t=>t.name===name);
   if(!tool)throw Error('Expected tool absent: '+name);
   tool.checkParameters(args);
   const statuses=[];
   const result=await deadline(tool.implementation(args,{status:x=>statuses.push(x),warn:x=>statuses.push(x),signal:new AbortController().signal,callId:report.calls.length+1}));
   const parsed=resultJson(result);
   report.calls.push({name,result:parsed,statuses});
   if(parsed.ok===false)throw Error(name+' returned a failed backend result');
   return parsed;
  }
  for(const [name,args] of [['check_comfyui_status',{}],['comfyui_list_queue',{}],['comfyui_get_outputs',{params:{prompt_id:'63eff82b-6edd-46da-89dd-6d33d2c95476'}}]]){
   const parsed=await call(name,args);
   if(name==='check_comfyui_status'&&!parsed.running)throw Error('ComfyUI status not running');
   if(name==='comfyui_get_outputs'&&(parsed.status!=='completed'||parsed.output_count!==3||!parsed.outputs.every(o=>o.exists)))throw Error('Expected completed job with three existing outputs');
  }
  const source='C:/Users/USER/Desktop/rtzu/589682038_17903637102306091_4752592283070689792_n.jpg';
  const sourceHash=sha(source);
  const file=await deadline(client.files.prepareImage(source));
  preparedPath=await deadline(file.getFilePath());
  const message=ChatMessage.create('user','No-render image attachment integration test.');
  message.appendFile(file);
  const {preprocess}=await import('file:///V:/LMStudio/.lmstudio/extensions/plugins/morph/bilder-und-videos/src/promptPreprocessor.mjs');
  const processed=await preprocess({client,abortSignal:new AbortController().signal},message);
  const retained=processed.getFiles(client);
  const attachment={mode:'standalone-real-SDK-preprocessor',hostChatPreprocessorInvoked:false,sourcePath:source,preparedFilePath:preparedPath,retainedFiles:retained.length,sameFileIdentifier:retained[0]?.identifier===file.identifier,sourceHash,preparedHash:sha(preparedPath),exactPreparedPathAddedToText:processed.getText().includes(JSON.stringify([preparedPath])),toolUsed:'comfyui_upload_image',subfolder:'lmstudio/probe',overwrite:false};
  report.attachment=attachment;
  if(attachment.retainedFiles!==1||!attachment.sameFileIdentifier||!attachment.exactPreparedPathAddedToText||attachment.sourceHash!==attachment.preparedHash)throw Error('Real SDK attachment preprocessor assertions failed');
  const upload=await call('comfyui_upload_image',{params:{paths:[preparedPath],subfolder:attachment.subfolder,overwrite:false}});
  attachment.upload=upload;
  if(upload.uploaded_count!==1||upload.failed_count!==0)throw Error('Expected one uploaded attachment and no failures');
  const imageName=upload.uploaded[0].load_image_name;
  const inputRoot=path.resolve('D:/MORPH-Studio/input');
  const uploadedPath=path.resolve(inputRoot,imageName);
  if(!uploadedPath.toLowerCase().startsWith(inputRoot.toLowerCase()+path.sep)||!imageName.startsWith('lmstudio/probe/'))throw Error('Upload response path outside exact probe folder');
  attachment.uploadedPath=uploadedPath;
  attachment.uploadedHash=sha(uploadedPath);
  attachment.sourceHashAfter=sha(source);
  attachment.hashMatch=attachment.sourceHash===attachment.preparedHash&&attachment.sourceHash===attachment.uploadedHash&&attachment.sourceHash===attachment.sourceHashAfter;
  if(!attachment.hashMatch)throw Error('Attachment byte-preservation assertions failed');
  report.success=true;
 }catch(error){report.success=false;report.error=scrub(error);}
 finally{
  if(session){session[Symbol.dispose]();report.sessionDisposed=true;}
  try{report.loadedAfter=(await deadline(client.llm.listLoaded())).map(m=>({identifier:m.identifier,modelKey:m.modelKey}));}catch(error){report.loadedAfterError=scrub(error);}
  await client[Symbol.asyncDispose]();
  report.clientDisposed=true;
  if(preparedPath){await new Promise(resolve=>setTimeout(resolve,500));(report.attachment??={}).preparedTemporaryExistsAfterDisconnect=fs.existsSync(preparedPath);}
  report.finishedAt=new Date().toISOString();
  fs.writeFileSync('D:/MORPH-Studio/reports/wan-lmstudio/native-installed-plugin-probe.json',JSON.stringify(report,null,2)+'\n');
  console.log(JSON.stringify(report,null,2));
 }
})().catch(error=>{console.log(scrub(error));process.exitCode=1;});
