'use strict';
// Exactly one authorized clothed dance render via the installed LM Studio provider.
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const reportPath = 'D:/MORPH-Studio/reports/wan-lmstudio/flower-hip-dance.json';
if (fs.existsSync(reportPath)) throw Error('Flower hip dance receipt already exists; do not submit again.');
const repair = JSON.parse(fs.readFileSync('D:/MORPH-Studio/reports/wan-lmstudio/repair-no-render-probe.json', 'utf8'));
if (!repair.success) throw Error('Successful installed-provider repair probe required before rendering.');
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
  source:'C:/Users/USER/Desktop/rtzu/Screenshot 2025-03-03 162438.png',
  userIntent:'Approximately seven seconds of dancing and circling hips from the flower-shop photo, existing clothing preserved',
  hostChatPreprocessorInvoked:false, automaticModelToolDecisionTested:false};
const scrub = e => String(e?.message ?? e).replace(/sk-lm-[^\s"']+/g, '[redacted-token]').replace(/clientPasskey[^\n]*/g, '[redacted-passkey]');
const sha = p => crypto.createHash('sha256').update(fs.readFileSync(p)).digest('hex');
const save = () => fs.writeFileSync(reportPath, JSON.stringify(report,null,2)+'\n');
function deadline(promise, ms=90000) {let timer; return Promise.race([promise,new Promise((_,reject) => {
  timer=setTimeout(() => reject(Error('Native tool call timeout; do not repeat submission')),ms);
})]).finally(() => clearTimeout(timer));}
function resultJson(result) {const txt=typeof result==='string'?result:
  (Array.isArray(result)?result:result.content??[]).filter(b=>b.type==='text').map(b=>b.text).join('\n'); return JSON.parse(txt);}
(async () => {
  let session;
  try {
    report.loadedBefore=(await deadline(client.llm.listLoaded())).map(m=>({identifier:m.identifier,modelKey:m.modelKey}));
    session=await deadline(client.plugins.pluginTools(report.plugin,{workingDirectory:'D:/MORPH-Studio'}));
    async function call(name,args) {
      const tool=session.tools.find(t=>t.name===name);
      if(!tool)throw Error('Tool unavailable: '+name);
      tool.checkParameters(args);
      const result=resultJson(await deadline(tool.implementation(args,{status(){},warn(){},
        signal:new AbortController().signal,callId:report.calls.length+1})));
      report.calls.push({at:new Date().toISOString(),name,result});save();
      if(result.ok===false)throw Error(name+': '+result.error);
      return result;
    }
    const queue=await call('comfyui_list_queue',{});
    if(queue.queue_remaining!==0)throw Error('Queue busy; no job submitted.');
    const file=await deadline(client.files.prepareImage(report.source));
    const prepared=await deadline(file.getFilePath());
    report.attachment={originalHash:sha(report.source),preparedHash:sha(prepared),prepared};
    const message=ChatMessage.create('user','Erstelle aus diesem Foto ein etwa sieben Sekunden langes Tanzvideo. Sie tanzt mit sichtbar kreisenden Hüftbewegungen. Erhalte ihre graue Kleidung, die Stiefel, den Blumenladen und den Besen. Die Kamera bleibt ruhig und zeigt sie vollständig.');
    message.appendFile(file);
    const {preprocess}=await import('file:///V:/LMStudio/.lmstudio/extensions/plugins/morph/bilder-und-videos/src/promptPreprocessor.mjs');
    const processed=await preprocess({client,abortSignal:new AbortController().signal},message);
    report.attachment.retainedFiles=processed.getFiles(client).length;
    report.attachment.pathResolved=processed.getText().includes(JSON.stringify([prepared]));
    if(report.attachment.retainedFiles!==1||!report.attachment.pathResolved)throw Error('Image attachment preprocessing failed.');
    const upload=await call('comfyui_upload_image',{params:{paths:[prepared],subfolder:'lmstudio/flower-hip-dance',overwrite:false}});
    if(upload.uploaded_count!==1||upload.failed_count!==0)throw Error('Expected one successful source upload.');
    const imageName=upload.uploaded[0].load_image_name;
    const inputRoot=path.resolve('D:/MORPH-Studio/input'),uploadedPath=path.resolve(inputRoot,imageName);
    if(!uploadedPath.toLowerCase().startsWith(inputRoot.toLowerCase()+path.sep))throw Error('Upload outside MORPH input directory.');
    report.attachment.uploadedPath=uploadedPath;report.attachment.uploadedHash=sha(uploadedPath);
    if(report.attachment.originalHash!==report.attachment.preparedHash||report.attachment.originalHash!==report.attachment.uploadedHash)throw Error('Source bytes changed in attachment transfer.');
    const workflowPath='D:/MORPH-Studio/workflows/LMStudio-Video-aus-Bild-Wan-api.json';
    const graph=JSON.parse(fs.readFileSync(workflowPath,'utf8'));
    const positive='Full-body shot of the same woman dancing in the flower shop. She makes clearly visible smooth circular hip movements, moving her hips forward, right, backward and left in repeated natural circles, with small knee bends and gentle weight shifts. One hand holds the broom handle and the other rests on her waist. Preserve her face, long hair, gray long-sleeved turtleneck dress, dark leggings, boots and the flower-shop background. Her clothes remain fully on. Keep her whole body and feet visible. Static camera, stable lighting, continuous natural motion.';
    const params={workflow_path:workflowPath,label:'Blumenladen - Hueften kreisen beim Tanz - etwa sieben Sekunden',overrides:{
      '252.image':imageName,'6.text':positive,
      '7.text':graph['7'].inputs.text+', nudity, removing clothing, torn clothing, cropped feet, cropped head, body distortion, sliding feet, frozen body',
      '226.filename_prefix':'LMStudio/Blumenladen-Huefttanz-Original',
      '254.filename_prefix':'LMStudio/Blumenladen-Huefttanz-RIFE',
      '256.filename_prefix':'LMStudio/Blumenladen-Huefttanz-Upscale',
      '131.value':384,'130.value':592,'132.value':113,'118.method':'pad',
      '226.frame_rate':16,'253.source_fps':16,
    }};
    for(const key of Object.keys(params.overrides)) {
      const index=key.lastIndexOf('.'),node=key.slice(0,index),input=key.slice(index+1);
      if(!Object.hasOwn(graph[node]?.inputs??{},input))throw Error('Invalid workflow override: '+key);
    }
    report.workflowHash=sha(workflowPath);report.request=params;
    report.parameters={width:384,height:592,frames:113,steps:8,seed:graph['105'].inputs.seed,
      originalFps:params.overrides['226.frame_rate'],rifeSourceFps:params.overrides['253.source_fps']};
    const freshQueue=await call('comfyui_list_queue',{});
    if(freshQueue.queue_remaining!==0)throw Error('Queue became busy; no job submitted.');
    report.submissions=1;save();
    const submitted=await call('comfyui_run_workflow',{params});
    if(!submitted.prompt_id)throw Error('Submission returned no job ID; do not repeat.');
    report.prompt_id=submitted.prompt_id;save();
    console.log(JSON.stringify({state:'submitted',prompt_id:report.prompt_id,receipt:reportPath}));
    const until=Date.now()+2400000;let lastState;
    while(Date.now()<until) {
      const poll=await call('comfyui_poll_workflow',{params:{prompt_id:report.prompt_id}});
      report.status=poll.status;save();
      if(lastState!==poll.status){console.log(JSON.stringify({state:poll.status,prompt_id:report.prompt_id}));lastState=poll.status;}
      if(['failed','error','cancelled'].includes(poll.status))throw Error('Dance job ended: '+JSON.stringify(poll));
      if(poll.status==='completed') {
        report.outputs=await call('comfyui_get_outputs',{params:{prompt_id:report.prompt_id}});
        if(report.outputs.output_count!==3||!report.outputs.outputs.every(o=>o.exists&&o.filename?.startsWith('Blumenladen-Huefttanz-')))throw Error('Expected three new existing flower-shop dance outputs.');
        report.success=true;break;
      }
      await new Promise(resolve=>setTimeout(resolve,15000));
    }
    if(!report.success)throw Error('Job unfinished after bounded polling; do not resubmit.');
  } catch(error) {report.error=scrub(error);}
  finally {
    if(session){session[Symbol.dispose]();report.sessionDisposed=true;}
    try{report.loadedAfter=(await deadline(client.llm.listLoaded())).map(m=>({identifier:m.identifier,modelKey:m.modelKey}));}catch(error){report.loadedAfterError=scrub(error);}
    if(report.attachment)report.attachment.originalHashAfter=sha(report.source);
    await client[Symbol.asyncDispose]();report.clientDisposed=true;
    report.finishedAt=new Date().toISOString();save();
    console.log(JSON.stringify({success:report.success,status:report.status,prompt_id:report.prompt_id,outputs:report.outputs,error:report.error}));
    if(!report.success)process.exitCode=1;
  }
})().catch(error=>{console.log(scrub(error));process.exitCode=1;});
