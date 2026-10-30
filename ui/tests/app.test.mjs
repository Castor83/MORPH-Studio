import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
import {requiredImagesPresent} from '../frontend/forms.js';
import {createStartGuard,pendingRequest,finishRequest} from '../frontend/api.js';
import {prepareProposalStep,renderProposals} from '../frontend/proposals.js';
import * as results from '../frontend/results.js';
import {createComparison} from '../frontend/comparison.js';
import {createRegionEditor} from '../frontend/regions.js';
let resourceModule;try{resourceModule=await import('../frontend/resources.js');}catch(error){if(error.code!=='ERR_MODULE_NOT_FOUND')throw error;}

function harness(requestImpl,realGuard=false,realForms=false,historyRequests=false,realResults=false){
  const elements=new Map(),saved=new Map();
  const storage={getItem:k=>saved.get(k) ?? null,setItem:(k,v)=>saved.set(k,v),removeItem:k=>saved.delete(k)};
  const element=tag=>({tag,children:[],value:'',checked:false,disabled:false,hidden:false,textContent:'',dataset:{},style:{},attributes:{},listeners:{},classList:{add(){},remove(){}},append(...items){this.children.push(...items);},replaceChildren(...items){this.children=[...items];},querySelectorAll(selector){return this.children.flatMap(child=>[...((selector==='[data-expert-only]' ? Object.hasOwn(child.dataset,'expertOnly') : child.tag===selector)?[child]:[]),...child.querySelectorAll(selector)]);},setAttribute(name,value){this.attributes[name]=String(value);},addEventListener(name,callback){this.listeners[name]=callback;},reportValidity(){return true;}});
  const document={getElementById(id){if(!elements.has(id))elements.set(id,element(id));return elements.get(id);},createElement:element};
  const descendants=node=>[node,...node.children.flatMap(descendants)];
  document.getElementById('workflow-form').elements={namedItem:name=>descendants(document.getElementById('controls')).find(node=>node.name===name) ?? null};
  let controlsChange,interval;
  let nextId=0;
  const projects=new Map();let nextProject=0;
  const request=async(path,options={})=>{
    if(!historyRequests && path==='/api/image-projects'){
      if(options.method==='POST'){
        const id='fixture-project-'+(++nextProject),version={id:id+'-original',project_id:id,parent_version_id:null,created_at:'2026-10-20T10:00:00Z',status:'original',media:{id:options.body.original_media_id,name:'original.png',url:'/media/'+options.body.original_media_id,kind:'image'},metadata:{},sha256:'synthetic'};
        const project={id,name:'Testprojekt',original_version_id:version.id,versions:[version]};projects.set(id,project);return project;
      }
      return [...projects.values()];
    }
    if(!historyRequests && path.startsWith('/api/image-projects/'))return projects.get(path.split('/').at(-1));
    return requestImpl(path,options);
  };
  const sandbox={document,console,Map,Set,Object,JSON,Date,createComparison,createRegionEditor,createResources:resourceModule?.createResources,crypto:{randomUUID:()=>`00000000-0000-4000-9000-${String(++nextId).padStart(12,'0')}`},FormData:class{append(){}},localStorage:storage,setTimeout(){},clearTimeout(){},setInterval(callback){interval=callback;},request,prepareProposalStep,renderProposals:(...args)=>renderProposals(...args.slice(0,6),document,args[7]),renderProjectList:(...args)=>results.renderProjectList(...args,document),renderVersionTree:(...args)=>results.renderVersionTree(...args,document),versionLabel:results.versionLabel,
    createStartGuard:post=>realGuard?createStartGuard(post,storage,()=>`00000000-0000-4000-8000-${String(++nextId).padStart(12,'0')}`):post,
    pendingRequest:()=>pendingRequest(storage),finishRequest,requiredImagesPresent,controlValues:()=>({}),modelSelections:()=>({image_model:'checkpoints/new.safetensors'}),fillControls(){},renderControls(container,workflow,onChange){controlsChange=onChange;},describeComfyStatus:results.describeComfyStatus,renderJob(){},ACTIVE:new Set(['preparing','submitting','queued','running','unknown']),labels:{error:'Fehler'}};
  const context=vm.createContext(sandbox);
  if(realResults)vm.runInContext(fs.readFileSync(new URL('../frontend/results.js',import.meta.url),'utf8').replace(/^export /gm,''),context);
  if(realForms){
    const forms=fs.readFileSync(new URL('../frontend/forms.js',import.meta.url),'utf8').replace(/^export /gm,'');
    vm.runInContext(forms,context);
  }
  const code=fs.readFileSync(new URL('../frontend/app.js',import.meta.url),'utf8').replace(/^import .*;\r?\n/gm,'').replace(/\nboot\(\);\s*$/,'')+'\nglobalThis.review={state,chooseWorkflow,updateActions,boot,refreshJobs};';
  vm.runInContext(code,context);
  const view=sandbox.review;view.state.ready=true;
  const workflow={id:'kontext',roles:[{id:'image',label:'Ausgangsbild'}],issues:[],controls:{},name:'Bild bearbeiten',description:''};
  view.chooseWorkflow(workflow);
  return {...view,document,storage,workflow,poll:()=>interval(),field:name=>document.getElementById('workflow-form').elements.namedItem(name),changeControl:event=>realForms?document.getElementById('workflow-form').elements.namedItem(event.target.name).listeners.input(event):controlsChange(event)};
}
const receipt=body=>({id:'synthetic-job',request_id:body.request_id || 'r',workflow_id:'kontext',state:'error',created_at:new Date().toISOString(),outputs:[]});
const settleEvents=()=>new Promise(resolve=>setImmediate(resolve));

test('preparing list receipts render before a held active-job detail request and retain the selected job',async()=>{
  let release;
  const job={id:'PREPARING',request_id:'REQUEST',state:'preparing',phase:'connecting',workflow_id:'kontext',created_at:'2026-10-20T15:00:00Z',outputs:[]};
  const old={id:'OLD',request_id:'OLD-REQUEST',state:'completed',workflow_id:'kontext',created_at:'2026-10-19T15:00:00Z',outputs:[]};
  const view=harness(async path=>{
    if(path==='/api/jobs')return [job,old];
    if(path==='/api/jobs/PREPARING')return new Promise(resolve=>{release=resolve;});
    return [];
  },false,false,false,true);
  view.storage.setItem('morph.pending-request.v1',JSON.stringify({request_id:'REQUEST'}));
  const refreshing=view.refreshJobs();await settleEvents();
  assert.ok(release,'Die Einzelabfrage ist tatsächlich noch offen.');
  assert.equal(view.state.selected,'PREPARING');
  let text=allDescendants(view.document.getElementById('result')).map(node=>node.textContent).join('\n');
  assert.match(text,/Wird vorbereitet/);assert.match(text,/Rechendienst wird verbunden/);
  assert.equal(view.document.getElementById('start').disabled,true);
  await view.document.getElementById('history').children[1].listeners.click();assert.equal(view.state.selected,'OLD');
  release({...job,state:'running',phase:null});await refreshing;
  assert.equal(view.state.selected,'OLD','Eine spätere Einzelantwort darf die bewusst gewählte Ergebnisansicht nicht überschreiben.');
  assert.ok(pendingRequest(view.storage),'Ein laufender Job darf den Startbeleg nicht freigeben.');
  text=allDescendants(view.document.getElementById('result')).map(node=>node.textContent).join('\n');assert.match(text,/Fertig/);
});

test('live source loss retains node observations during polling without resubmitting or closing its receipt',async()=>{
  const calls=[],job={id:'RUNNING',request_id:'REQUEST',state:'running',workflow_id:'kontext',created_at:'2026-10-20T15:00:00Z',outputs:[],progress:{event:'progress',node_id:'12',node_type:'KSampler',value:1,max:4,connection:'connected'}};
  const view=harness(async(path,options={})=>{
    calls.push({path,method:options.method || 'GET'});
    if(path==='/api/jobs')return [job];
    if(path==='/api/jobs/RUNNING')return {...job,progress:{...job.progress,connection:'unavailable'}};
    return [];
  },false,false,false,true);
  view.storage.setItem('morph.pending-request.v1',JSON.stringify({request_id:'REQUEST'}));
  await view.refreshJobs();
  const text=allDescendants(view.document.getElementById('result')).map(node=>node.textContent).join('\n');
  assert.match(text,/Letzte Fortschrittsmeldung/);assert.match(text,/Liveverbindung unterbrochen/);assert.match(text,/25 %/);
  assert.equal(view.state.jobs[0].state,'running');assert.ok(pendingRequest(view.storage));assert.equal(calls.some(call=>call.method==='POST'),false);
});

test('a recovered pending receipt remains the initial selection ahead of older completed jobs',async()=>{
  const job={id:'RECOVERED',request_id:'REQUEST',state:'preparing',phase:'checking',workflow_id:'kontext',created_at:'2026-10-20T15:00:00Z',outputs:[]};
  const old={id:'OLD',request_id:'OLD-REQUEST',state:'completed',workflow_id:'kontext',created_at:'2026-10-19T15:00:00Z',outputs:[]};
  const view=harness(async path=>{
    if(path==='/api/jobs')return [old];
    if(path==='/api/requests/REQUEST' || path==='/api/jobs/RECOVERED')return job;
    return [];
  });
  view.storage.setItem('morph.pending-request.v1',JSON.stringify({request_id:'REQUEST'}));
  await view.refreshJobs();assert.equal(view.state.selected,'RECOVERED');assert.ok(pendingRequest(view.storage));
});

const resourceSnapshot=()=>({available:true,measured_at:'2026-10-20T14:05:06Z',source:'ComfyUI /system_stats',devices:[{name:'RTX 4080',type:'cuda',index:0,vram_total:16*1024**3,vram_free:12*1024**3,vram_used:4*1024**3}],ram:{total:48*1024**3,free:32*1024**3,used:16*1024**3},model_state:'unknown',unload:{allowed:true,reason:''}});
function resourceButton(view,label){const button=allDescendants(view.document.getElementById('resources')).find(node=>node.tag==='button' && node.textContent===label);assert.ok(button,'Ressourcenaktion fehlt: '+label);return button;}
const releaseImageModels='Bildmodelle im Rechendienst freigeben';

test('resource measurement failure on boot leaves ordinary image jobs available',async()=>{
  const calls=[],view=harness(async(path,options={})=>{calls.push({path,options});if(path==='/api/resources')throw new Error('Rechendienst offline');if(path==='/api/workflows')return [editableWorkflow()];if(path==='/api/settings')return {};if(path==='/api/status')return {project_root:'E:\\MORPH-Studio',free_bytes:1024**3,comfy:{ready:false,ownership:'free'}};if(path==='/api/jobs' && options.method==='POST')return receipt(options.body);return [];},false,true);
  await view.boot();await settleEvents();assert.equal(view.state.ready,true);assert.equal(view.document.getElementById('start').disabled,false);
  assert.match(allDescendants(view.document.getElementById('resources')).map(node=>node.textContent).join('\n'),/Ressourcen.*nicht verfügbar/);
  await view.document.getElementById('workflow-form').listeners.submit({preventDefault(){}});assert.equal(calls.filter(call=>call.path==='/api/jobs' && call.options.method==='POST').length,1);assert.equal(calls.some(call=>call.path==='/api/resources/free'),false);
});

test('a pending manual resource measurement does not block an ordinary compute submission',async()=>{
  let finishRead,submitted;const view=harness(async(path,options={})=>{if(path==='/api/resources')return new Promise(resolve=>finishRead=resolve);if(path==='/api/jobs' && options.method==='POST'){submitted=options.body;return receipt(options.body);}return [];});
  view.state.images.image={id:'SOURCE',url:'/media/SOURCE'};view.updateActions();const refreshing=resourceButton(view,'Ressourcen aktualisieren').listeners.click();
  assert.equal(view.document.getElementById('start').disabled,false);await view.document.getElementById('workflow-form').listeners.submit({preventDefault(){}});assert.equal(submitted.images.image,'SOURCE');finishRead(resourceSnapshot());await refreshing;
});

test('an explicit in-flight image-model release blocks submit and releases that block before the next read completes',async()=>{
  let finishFree,finishRead,reads=0,starts=0;const view=harness(async(path,options={})=>{if(path==='/api/resources')return ++reads===1?resourceSnapshot():new Promise(resolve=>finishRead=resolve);if(path==='/api/resources/free')return new Promise(resolve=>finishFree=resolve);if(path==='/api/jobs' && options.method==='POST'){starts++;return receipt(options.body);}return [];});
  view.state.images.image={id:'SOURCE',url:'/media/SOURCE'};view.updateActions();await resourceButton(view,'Ressourcen aktualisieren').listeners.click();const freeing=resourceButton(view,releaseImageModels).listeners.click();
  assert.equal(view.document.getElementById('start').disabled,true);await view.document.getElementById('workflow-form').listeners.submit({preventDefault(){}});assert.equal(starts,0);
  finishFree({accepted:true,completed:false,message:'Freigabe angefordert'});await settleEvents();assert.equal(view.document.getElementById('start').disabled,false);await view.document.getElementById('workflow-form').listeners.submit({preventDefault(){}});assert.equal(starts,1);finishRead(resourceSnapshot());await freeing;
});

test('active uploads, image starts, unresolved receipts and active jobs cannot trigger retained resource release actions',async()=>{
  for(const block of ['upload','starting','pending','job']){
    const calls=[],view=harness(async(path,options={})=>{calls.push({path,options});return path==='/api/resources'?resourceSnapshot():[];});await resourceButton(view,'Ressourcen aktualisieren').listeners.click();
    if(block==='upload')view.state.uploads.add({generation:view.state.generation});if(block==='starting')view.state.starting=true;if(block==='pending')view.storage.setItem('morph.pending-request.v1',JSON.stringify({request_id:'still-unknown'}));if(block==='job')view.state.jobs=[{id:'ACTIVE',state:'unknown'}];view.updateActions();
    const button=resourceButton(view,releaseImageModels);assert.equal(button.disabled,true,block);await button.listeners.click();assert.equal(calls.some(call=>call.path==='/api/resources/free'),false,block);
  }
});

for(const action of ['load','unload','propose'])test(`an in-flight language ${action} immediately rejects image and resource clicks without a deferred submission`,async()=>{
  const calls=[];let finishLanguage;
  const route=action==='propose'?'/api/tool-proposals':'/api/models/'+action;
  const view=harness(async(path,options={})=>{
    calls.push({path,options});
    if(path===route && options.method==='POST')return new Promise(resolve=>finishLanguage=resolve);
    if(path==='/api/resources')return resourceSnapshot();
    if(path==='/api/settings')return {model_key:'manual-language-model',instance_id:action==='unload'?'':'loaded-instance'};
    if(path==='/api/models')return view.state.models;
    if(path==='/api/jobs' && options.method==='POST')return receipt(options.body);
    return [];
  },true,true);
  enableProposals(view,[editableWorkflow()]);
  if(action==='load')view.document.getElementById('instance').value='';
  view.field('seed').value=73;view.updateActions();
  await resourceButton(view,'Ressourcen aktualisieren').listeners.click();
  const button=view.document.getElementById(action==='propose'?'propose':action+'-model');
  assert.equal(button.disabled,false);const language=button.listeners.click();
  try{
    assert.equal(typeof finishLanguage,'function');
    assert.equal(view.document.getElementById('start').disabled,true);
    assert.match(view.document.getElementById('start-hint').textContent,/Sprachmodell|Vorschlag/);
    await view.document.getElementById('workflow-form').listeners.submit({preventDefault(){}});
    const free=resourceButton(view,releaseImageModels);assert.equal(free.disabled,true);await free.listeners.click();
    assert.equal(calls.some(call=>call.path==='/api/jobs' && call.options.method==='POST'),false);
    assert.equal(calls.some(call=>call.path==='/api/resources/free'),false);
    assert.equal(pendingRequest(view.storage),null,'Ein gesperrter Bildstart darf keinen Startbeleg erzeugen.');
  }finally{finishLanguage(action==='propose'?plan:{});await language;}
  await settleEvents();
  assert.equal(view.document.getElementById('start').disabled,false);
  assert.equal(view.field('seed').value,73);
  assert.equal(calls.some(call=>call.path==='/api/jobs' && call.options.method==='POST'),false,'Der gesperrte Klick darf später nicht automatisch starten.');
  assert.equal(calls.some(call=>call.path==='/api/resources/free'),false);
  await view.document.getElementById('workflow-form').listeners.submit({preventDefault(){}});
  assert.equal(calls.filter(call=>call.path==='/api/jobs' && call.options.method==='POST').length,1);
});

test('every unresolved image state immediately rejects retained language handlers and resource release without later work',async()=>{
  for(const block of ['preparing','submitting','queued','running','unknown','starting','pending','resolving']){
    const calls=[],view=harness(async(path,options={})=>{calls.push({path,options});return path==='/api/resources'?resourceSnapshot():path==='/api/models'?view.state.models:plan;},false,true);
    enableProposals(view,[editableWorkflow()]);await resourceButton(view,'Ressourcen aktualisieren').listeners.click();
    if(block==='starting')view.state.starting=true;
    else if(block==='resolving')view.state.resolving=true;
    else if(block==='pending')view.storage.setItem('morph.pending-request.v1',JSON.stringify({request_id:'unresolved'}));
    else view.state.jobs=[{id:'IMAGE',state:block}];
    view.updateActions();
    for(const action of ['load','unload','propose']){
      view.document.getElementById('instance').value=action==='load'?'':'loaded-instance';view.updateActions();
      const button=view.document.getElementById(action==='propose'?'propose':action+'-model');
      assert.equal(button.disabled,true,`${block} blocks ${action}`);await button.listeners.click();
    }
    const free=resourceButton(view,releaseImageModels);assert.equal(free.disabled,true,block);await free.listeners.click();
    assert.equal(calls.some(call=>call.options.method==='POST'),false,block);
    view.state.jobs=[];view.state.starting=false;view.state.resolving=false;view.storage.removeItem('morph.pending-request.v1');view.updateActions();await settleEvents();
    assert.equal(calls.some(call=>call.options.method==='POST'),false,'Keine Sprachaktion darf nach der Entsperrung automatisch beginnen.');
    assert.equal(view.document.getElementById('propose').disabled,false);
  }
});

test('an image request blocks language actions before its first receipt and never schedules them after completion',async()=>{
  const calls=[];let finishImage;
  const view=harness(async(path,options={})=>{
    calls.push({path,options});if(path==='/api/jobs' && options.method==='POST')return new Promise(resolve=>finishImage=()=>resolve(receipt(options.body)));
    return path==='/api/models'?view.state.models:[];
  },true,true);
  enableProposals(view,[editableWorkflow()]);
  const image=view.document.getElementById('workflow-form').listeners.submit({preventDefault(){}});await settleEvents();
  try{
    assert.equal(typeof finishImage,'function');
    for(const action of ['load','unload','propose']){
      view.document.getElementById('instance').value=action==='load'?'':'loaded-instance';view.updateActions();
      const button=view.document.getElementById(action==='propose'?'propose':action+'-model');
      assert.equal(button.disabled,true,action);await button.listeners.click();
    }
    assert.equal(calls.filter(call=>call.options.method==='POST').length,1);
  }finally{finishImage();await image;}
  await settleEvents();assert.equal(calls.filter(call=>call.options.method==='POST').length,1);
});

test('an in-flight resource release rejects all language actions and does not trigger them after its receipt',async()=>{
  const calls=[];let finishFree;
  const view=harness(async(path,options={})=>{calls.push({path,options});if(path==='/api/resources/free')return new Promise(resolve=>finishFree=resolve);return path==='/api/resources'?resourceSnapshot():path==='/api/models'?view.state.models:[];},false,true);
  enableProposals(view,[editableWorkflow()]);await resourceButton(view,'Ressourcen aktualisieren').listeners.click();
  const freeing=resourceButton(view,releaseImageModels).listeners.click();
  try{
    for(const action of ['load','unload','propose']){
      view.document.getElementById('instance').value=action==='load'?'':'loaded-instance';view.updateActions();
      const button=view.document.getElementById(action==='propose'?'propose':action+'-model');
      assert.equal(button.disabled,true,action);await button.listeners.click();
    }
    assert.equal(calls.filter(call=>call.options.method==='POST').length,1);
  }finally{finishFree({accepted:true,completed:false});await freeing;}
  await settleEvents();assert.equal(calls.filter(call=>call.options.method==='POST').length,1);
  assert.equal(view.document.getElementById('propose').disabled,false);
});

test('an in-flight proposal also rejects load and unload handlers until its response completes',async()=>{
  const calls=[];let finishProposal;
  const view=harness(async(path,options={})=>{calls.push({path,options});if(path==='/api/tool-proposals')return new Promise(resolve=>finishProposal=resolve);return path==='/api/models'?view.state.models:[];},false,true);
  enableProposals(view,[editableWorkflow()]);const proposing=view.document.getElementById('propose').listeners.click();
  try{
    for(const action of ['load','unload']){
      view.document.getElementById('instance').value=action==='load'?'':'loaded-instance';view.updateActions();
      const button=view.document.getElementById(action+'-model');assert.equal(button.disabled,true,action);await button.listeners.click();
    }
    assert.equal(calls.filter(call=>call.options.method==='POST').length,1);
  }finally{finishProposal(plan);await proposing;}
  await settleEvents();assert.equal(calls.filter(call=>call.options.method==='POST').length,1);
});

test('a permitted image start displays optional language residency warnings without extra mutations or retries',async()=>{
  const warning='Ollama ist nicht erreichbar. Der GPU-Speicher des Sprachmodells ist unbekannt; der Bildstart bleibt erlaubt.';
  const calls=[],view=harness(async(path,options={})=>{
    calls.push({path,options});
    if(path==='/api/jobs' && options.method==='POST')return {...receipt(options.body),state:'queued',warnings:[warning]};
    return [];
  },true,true,false,true);
  view.chooseWorkflow(editableWorkflow());
  await view.document.getElementById('workflow-form').listeners.submit({preventDefault(){}});await settleEvents();
  assert.ok(allDescendants(view.document.getElementById('result')).some(node=>node.tag==='p' && node.textContent.includes(warning)));
  assert.equal(view.state.jobs[0].state,'queued');assert.ok(pendingRequest(view.storage));
  assert.equal(calls.filter(call=>call.options.method==='POST').length,1);
  assert.equal(calls.find(call=>call.options.method==='POST').path,'/api/jobs');
});

test('a persisted unknown language target without loaded models requires a deliberate release of that exact instance',async()=>{
  const target='saved-uncertain-model',calls=[];let uncertain=true,finishUnload;
  const view=harness(async(path,options={})=>{
    calls.push({path,options});
    if(path==='/api/workflows')return [editableWorkflow()];
    if(path==='/api/settings')return {};
    if(path==='/api/status')return {project_root:'E:\\MORPH-Studio',free_bytes:1024**3,comfy:{ready:false,ownership:'free'},language_state:{busy:false,uncertain_instances:uncertain?[target]:[]}};
    if(path==='/api/resources')return resourceSnapshot();
    if(path==='/api/models/unload')return new Promise(resolve=>finishUnload=()=>{uncertain=false;resolve({});});
    if(path==='/api/jobs' && options.method==='POST')return receipt(options.body);
    return [];
  },true,true);
  await view.boot();await settleEvents();
  assert.equal(view.state.models.length,0);assert.equal(view.document.getElementById('instance').value,'');
  assert.equal(view.document.getElementById('start').disabled,true);
  assert.equal(view.document.getElementById('load-model').disabled,true);
  assert.equal(view.document.getElementById('propose').disabled,true);
  assert.equal(view.document.getElementById('unload-model').disabled,false);
  assert.match(view.document.getElementById('model-info').textContent,/unbekannt|unbestätigt/i);
  assert.match(view.document.getElementById('model-info').textContent,/saved-uncertain-model/);
  assert.equal(resourceButton(view,releaseImageModels).disabled,true);
  await view.document.getElementById('workflow-form').listeners.submit({preventDefault(){}});
  await view.document.getElementById('load-model').listeners.click();
  await view.document.getElementById('propose').listeners.click();
  assert.equal(calls.some(call=>call.options.method==='POST'),false,'Ein gespeicherter unbekannter Zustand darf weder automatisch laden noch freigeben.');
  const releasing=view.document.getElementById('unload-model').listeners.click();
  try{
    const release=calls.find(call=>call.path==='/api/models/unload');assert.ok(release);
    assert.equal(release.options.body.instance_id,target);assert.equal(view.document.getElementById('start').disabled,true);
  }finally{finishUnload();await releasing;}
  assert.equal(view.document.getElementById('start').disabled,false);
  assert.equal(view.document.getElementById('unload-model').disabled,true);
  assert.equal(calls.filter(call=>call.options.method==='POST').length,1);
  await view.document.getElementById('workflow-form').listeners.submit({preventDefault(){}});
  assert.equal(calls.filter(call=>call.path==='/api/jobs' && call.options.method==='POST').length,1);
});

test('a timed-out model load refreshes its saved unknown target and exposes explicit recovery without retrying the load',async()=>{
  const target='manual-language-model',calls=[];let uncertain=false;
  const view=harness(async(path,options={})=>{
    calls.push({path,options});
    if(path==='/api/models/load'){uncertain=true;throw new Error('Antwortzeit überschritten. Der Ladezustand ist unbekannt.');}
    if(path==='/api/status')return {comfy:{ready:false,ownership:'free'},language_state:{busy:false,uncertain_instances:uncertain?[target]:[]}};
    return [];
  },true,true);
  enableProposals(view,[editableWorkflow()]);view.document.getElementById('instance').value='';view.updateActions();
  await view.document.getElementById('load-model').listeners.click();
  assert.ok(calls.some(call=>call.path==='/api/status'),'Nach der unbestätigten Mutation muss ihr serverseitiger Zustand frisch gelesen werden.');
  assert.equal(calls.filter(call=>call.path==='/api/models/load').length,1);
  assert.equal(view.document.getElementById('start').disabled,true);
  assert.equal(view.document.getElementById('unload-model').disabled,false);
  assert.match(view.document.getElementById('model-info').textContent,/manual-language-model/);
  assert.equal(calls.some(call=>call.path==='/api/models/unload' || call.path==='/api/jobs'),false);
});

test('a busy language action observed from server status disables all GPU mutations without inventing a recovery target',async()=>{
  const calls=[],view=harness(async(path,options={})=>{
    calls.push({path,options});if(path==='/api/workflows')return [editableWorkflow()];if(path==='/api/settings')return {};
    if(path==='/api/status')return {project_root:'E:\\MORPH-Studio',free_bytes:1024**3,comfy:{ready:false,ownership:'free'},language_state:{busy:true,uncertain_instances:[]}};
    if(path==='/api/resources')return resourceSnapshot();return [];
  },false,true);
  await view.boot();
  for(const id of ['start','load-model','unload-model','propose'])assert.equal(view.document.getElementById(id).disabled,true,id);
  assert.equal(resourceButton(view,releaseImageModels).disabled,true);
  assert.match(view.document.getElementById('model-info').textContent,/Sprachmodell.*läuft|Sprachmodellaktion/i);
  assert.equal(calls.some(call=>call.options.method==='POST'),false);
});

test('pending or uncertain language work fences retained selection and connection handlers without deferring a settings change',async()=>{
  for(const block of ['proposing','remote-busy','unknown']){
    const calls=[],view=harness(async(path,options={})=>{calls.push({path,options});return options.body || {};},false,true);
    enableProposals(view,[editableWorkflow()]);
    if(block==='proposing')view.state.proposing=true;
    else view.state.languageState={busy:block==='remote-busy',uncertain_instances:block==='unknown'?['saved-uncertain-model']:[]};
    let dialogs=0;view.document.getElementById('settings-dialog').showModal=()=>dialogs++;view.document.getElementById('settings-dialog').close=()=>{};
    view.updateActions();
    for(const id of ['model','instance','settings-open'])assert.equal(view.document.getElementById(id).disabled,true,`${block} blocks ${id}`);
    await view.document.getElementById('model').listeners.change();await view.document.getElementById('instance').listeners.change();
    await view.document.getElementById('settings-open').listeners.click();
    await view.document.getElementById('settings-form').listeners.submit({preventDefault(){}});
    assert.equal(dialogs,0,block);assert.equal(calls.some(call=>call.path==='/api/settings'),false,block);
    view.state.proposing=false;view.state.languageState={busy:false,uncertain_instances:[]};view.updateActions();await settleEvents();
    assert.equal(calls.some(call=>call.path==='/api/settings'),false,'Die gesperrte Einstellungsänderung darf später nicht nachgeholt werden.');
  }
});

test('a busy status observed during model loading cannot suppress its confirmed fresh instance list',async()=>{
  const target='manual-language-model',calls=[];let loaded=false,busy=false,finishLoad;
  const model=()=>({key:target,name:'Mein Sprachmodell',loaded_instances:loaded?[{id:'confirmed-instance'}]:[]});
  const view=harness(async(path,options={})=>{
    calls.push({path,options});
    if(path==='/api/models/load'){busy=true;return new Promise(resolve=>finishLoad=()=>{loaded=true;busy=false;resolve({instance_id:'confirmed-instance'});});}
    if(path==='/api/settings')return {model_key:target,instance_id:loaded?'confirmed-instance':''};
    if(path==='/api/models')return [model()];
    if(path==='/api/status')return {comfy:{ready:false,ownership:'free'},language_state:{busy,uncertain_instances:[]}};
    return [];
  },false,true);
  enableProposals(view,[editableWorkflow()]);view.state.models=[model()];view.document.getElementById('instance').value='';view.updateActions();
  const loading=view.document.getElementById('load-model').listeners.click();await view.refreshJobs();
  assert.equal(view.state.languageState.busy,true);
  finishLoad();await loading;
  assert.equal(view.state.languageState.busy,false);
  assert.equal(view.document.getElementById('instance').value,'confirmed-instance');
  assert.equal(view.state.models[0].loaded_instances[0]?.id,'confirmed-instance');
  assert.equal(view.document.getElementById('propose').disabled,false);
  assert.equal(calls.filter(call=>call.path==='/api/models/load').length,1);
});

test('a stale busy status or status failure cannot replace the fresh status after a completed language action',async()=>{
  for(const outcome of ['busy','failure']){
    const target='manual-language-model';let finishLoad,finishOldStatus,failOldStatus,reads=0,loaded=false;
    const view=harness(async(path,options={})=>{
      if(path==='/api/models/load')return new Promise(resolve=>finishLoad=()=>{loaded=true;resolve({instance_id:'confirmed-instance'});});
      if(path==='/api/settings')return {model_key:target,instance_id:loaded?'confirmed-instance':''};
      if(path==='/api/models')return [{key:target,name:target,loaded_instances:loaded?[{id:'confirmed-instance'}]:[]}];
      if(path==='/api/status')return ++reads===1?new Promise((resolve,reject)=>{finishOldStatus=resolve;failOldStatus=reject;}):{comfy:{ready:true,ownership:'owned'},language_state:{busy:false,uncertain_instances:[]}};
      return [];
    },false,true);
    enableProposals(view,[editableWorkflow()]);view.document.getElementById('instance').value='';view.updateActions();
    const loading=view.document.getElementById('load-model').listeners.click(),older=view.refreshJobs();await settleEvents();
    try{assert.equal(typeof finishOldStatus,'function');finishLoad();await loading;assert.equal(view.document.getElementById('propose').disabled,false);}
    finally{
      if(outcome==='busy')finishOldStatus({comfy:{ready:false,ownership:'unknown'},language_state:{busy:true,uncertain_instances:[]}});
      else failOldStatus(new Error('Veraltete Statusabfrage ohne Antwort.'));
      await older;
    }
    assert.equal(view.state.languageState.busy,false,outcome);
    assert.equal(view.state.comfy.ready,true,outcome);
    assert.equal(view.document.getElementById('start').disabled,false,outcome);
    assert.equal(view.document.getElementById('propose').disabled,false,outcome);
  }
});

test('a page opened during remote language work polls until its completion and refreshes model availability using reads',async()=>{
  for(const initial of ['busy','unknown']){
    const target='manual-language-model',calls=[];let remote=true;
    const view=harness(async(path,options={})=>{
      calls.push({path,options});
      if(path==='/api/workflows')return [editableWorkflow()];
      if(path==='/api/settings')return {model_key:target,instance_id:initial==='busy'?'confirmed-instance':''};
      if(path==='/api/status')return {project_root:'E:\\MORPH-Studio',free_bytes:1024**3,comfy:{ready:false,ownership:'free'},language_state:{busy:remote && initial==='busy',uncertain_instances:remote && initial==='unknown'?[target]:[]}};
      if(path==='/api/models')return [{key:target,name:target,loaded_instances:initial==='busy'?[{id:'confirmed-instance'}]:[]}];
      return [];
    },false,true);
    await view.boot();view.document.getElementById('instruction').value='Ein Bild beschreiben.';view.updateActions();
    assert.equal(view.document.getElementById('start').disabled,true);
    const readsBefore=calls.filter(call=>call.path==='/api/models').length;remote=false;
    await view.poll();await settleEvents();
    assert.equal(view.state.languageState.busy,false,initial);assert.equal(view.state.languageState.uncertain_instances.length,0,initial);
    assert.equal(view.document.getElementById('start').disabled,false,initial);
    assert.equal(calls.filter(call=>call.path==='/api/models').length,readsBefore+1,initial);
    if(initial==='busy')assert.equal(view.document.getElementById('propose').disabled,false);
    else assert.equal(view.document.getElementById('load-model').disabled,false);
    assert.equal(calls.some(call=>call.options.method==='POST'),false,'Nur frische Leseabfragen dürfen den fremden Abschluss übernehmen.');
  }
});

test('replacing a picture blocks start until the new picture is assigned',async()=>{
  let releaseUpload,submitted;
  const view=harness(async(path,{body}={})=>{
    if(path==='/api/uploads')return new Promise(resolve=>releaseUpload=resolve);
    if(path==='/api/jobs'){submitted=body;return receipt(body);}
    return [];
  });
  view.state.images.image={id:'OLD',url:'/media/OLD',name:'old.png'};view.updateActions();
  const file=view.document.getElementById('image-roles').children[0].children[1].children[1];
  file.files=[{name:'new.png',type:'image/png',size:1024}];const uploading=file.listeners.change();
  assert.equal(view.document.getElementById('start').disabled,true);
  await view.document.getElementById('workflow-form').listeners.submit({preventDefault(){}});
  assert.equal(submitted,undefined);
  releaseUpload({id:'NEW',url:'/media/NEW',name:'new.png'});await uploading;
  assert.equal(view.document.getElementById('start').disabled,false);
  await view.document.getElementById('workflow-form').listeners.submit({preventDefault(){}});
  assert.equal(submitted.images.image,'NEW');
});

test('stale upload response after workflow change cannot assign a picture',async()=>{
  let release;
  const view=harness(async()=>new Promise(resolve=>release=resolve));
  const file=view.document.getElementById('image-roles').children[0].children[1].children[1];file.files=[{name:'old.png',type:'image/png',size:1024}];const upload=file.listeners.change();
  view.chooseWorkflow({...view.workflow,id:'reactor',roles:[{id:'target',label:'Zielfoto'},{id:'source',label:'Quellgesicht'}]});
  release({id:'OLD-FLOW',url:'/media/OLD-FLOW',name:'old.png'});await upload;
  assert.deepEqual(Object.keys(view.state.images),[]);
});

test('missing model display includes its exact expected path',()=>{
  const view=harness(async()=>[]);
  view.chooseWorkflow({...view.workflow,issues:[{message:'Modell fehlt: example.safetensors',path:'E:\\MORPH-Studio\\models\\example.safetensors'}]});
  assert.match(view.document.getElementById('workflow-issues').textContent,/E:\\MORPH-Studio\\models\\example\.safetensors/);
});

test('explicit request resolution releases a start that never reached the service',async()=>{
  let starts=0;
  const view=harness(async(path,{body,method}={})=>{
    if(path==='/api/jobs' && method==='POST'){starts++;if(starts===1)throw new Error('Dienst war offline');return receipt(body);}
    if(path==='/api/jobs')return [];
    if(path.endsWith('/resolve'))return {id:'closed',request_id:pendingRequest(view.storage).request_id,workflow_id:'unreceived',state:'error',error_code:'request_not_received',created_at:new Date().toISOString(),outputs:[]};
    if(path.startsWith('/api/requests/'))return null;
    return [];
  },true);
  view.state.images.image={id:'ONE',url:'/media/ONE',name:'one.png'};view.updateActions();
  await view.document.getElementById('workflow-form').listeners.submit({preventDefault(){}});
  assert.ok(pendingRequest(view.storage));assert.equal(view.document.getElementById('start').disabled,true);
  assert.equal(typeof view.document.getElementById('resolve-request').listeners.click,'function');
  await view.document.getElementById('resolve-request').listeners.click();
  assert.equal(pendingRequest(view.storage),null);assert.equal(view.document.getElementById('start').disabled,false);
  await view.document.getElementById('workflow-form').listeners.submit({preventDefault(){}});
  assert.equal(starts,2);
});

test('model readiness blocks start and stale response cannot affect another workflow',async()=>{
  let release;
  const view=harness(async()=>new Promise(resolve=>release=resolve));
  view.chooseWorkflow({...view.workflow,id:'sdxl',roles:[],controls:{image_model:{kind:'model'}}});
  const checking=view.changeControl({target:{name:'image_model'}});
  assert.equal(view.document.getElementById('start').disabled,true);
  view.chooseWorkflow({...view.workflow,id:'qwen21',roles:[],controls:{}});
  assert.equal(view.document.getElementById('start').disabled,false);
  release({issues:[{message:'Altes Modell fehlt'}]});await checking;
  assert.equal(view.document.getElementById('workflow-issues').hidden,true);
  assert.equal(view.document.getElementById('start').disabled,false);
});

function editableWorkflow(id='sdxl',roles=[]){
  return {id,name:'Bild erstellen',description:'',roles,issues:[],controls:{
    prompt:{kind:'text',label:'Beschreibung',default:'Before refresh'},
    seed:{kind:'integer',label:'Seed',default:11,min:0,max:999999},
    width:{kind:'integer',label:'Breite',default:512,min:256,max:2048},
    image_model:{kind:'model',label:'Bildmodell',default:'checkpoints/base.safetensors',options:[
      {id:'checkpoints/base.safetensors',label:'Base'},
      {id:'checkpoints/alternative.safetensors',label:'Alternative'}]},
  }};
}

test('model refresh preserves form edits made while its requests are pending',async()=>{
  let releaseWorkflows;
  const view=harness(async path=>{
    if(path==='/api/workflows')return new Promise(resolve=>releaseWorkflows=resolve);
    if(path.endsWith('/check'))return {issues:[]};
    return [];
  },false,true);
  const workflow=editableWorkflow();view.chooseWorkflow(workflow);
  const refresh=view.document.getElementById('refresh-image-models').listeners.click();
  for(const [name,value] of Object.entries({prompt:'Edited while refresh was waiting',seed:'29',width:'640',image_model:'checkpoints/alternative.safetensors'})){
    view.field(name).value=value;await view.changeControl({target:{name}});
  }
  await settleEvents();
  assert.equal(view.state.modelChecking,false);
  assert.equal(view.document.getElementById('start').disabled,true);
  assert.equal(view.document.getElementById('refresh-image-models').disabled,true);
  releaseWorkflows([editableWorkflow()]);await refresh;
  assert.equal(view.field('prompt').value,'Edited while refresh was waiting');
  assert.equal(Number(view.field('seed').value),29);
  assert.equal(Number(view.field('width').value),640);
  assert.equal(view.field('image_model').value,'checkpoints/alternative.safetensors');
  assert.equal(view.document.getElementById('start').disabled,false);
});

test('an older refresh cannot finish another workflow current model check',async()=>{
  let releaseWorkflows,releaseCheck;
  const view=harness(async path=>{
    if(path==='/api/workflows')return new Promise(resolve=>releaseWorkflows=resolve);
    if(path.endsWith('/check'))return new Promise(resolve=>releaseCheck=resolve);
    return [];
  },false,true);
  view.chooseWorkflow(editableWorkflow());
  const refresh=view.document.getElementById('refresh-image-models').listeners.click();
  view.chooseWorkflow(editableWorkflow('qwen21'));
  view.changeControl({target:{name:'image_model'}});
  releaseWorkflows([editableWorkflow(),editableWorkflow('qwen21')]);await refresh;
  assert.equal(view.state.modelChecking,true);
  assert.equal(view.document.getElementById('start').disabled,true);
  assert.equal(view.document.getElementById('refresh-image-models').disabled,true);
  releaseCheck({issues:[]});await settleEvents();
  assert.equal(view.state.modelChecking,false);
  assert.equal(view.document.getElementById('start').disabled,false);
  assert.equal(view.document.getElementById('refresh-image-models').disabled,false);
});

test('an upload started during model refresh keeps its form generation and result',async()=>{
  let releaseWorkflows,releaseUpload;
  const view=harness(async path=>{
    if(path==='/api/workflows')return new Promise(resolve=>releaseWorkflows=resolve);
    if(path==='/api/uploads')return new Promise(resolve=>releaseUpload=resolve);
    if(path.endsWith('/check'))return {issues:[]};
    return [];
  },false,true);
  const workflow=editableWorkflow('kontext',[{id:'image',label:'Ausgangsbild'}]);view.chooseWorkflow(workflow);
  view.state.images.image={id:'OLD',url:'/media/OLD',name:'old.png'};view.updateActions();
  const generation=view.state.generation;
  const refresh=view.document.getElementById('refresh-image-models').listeners.click();
  const file=view.document.getElementById('image-roles').children[0].children[1].children[1];
  file.files=[{name:'new.png',type:'image/png',size:1024}];const uploading=file.listeners.change();
  releaseWorkflows([editableWorkflow('kontext',workflow.roles)]);await refresh;
  assert.equal(view.state.generation,generation);
  assert.equal(view.document.getElementById('image-roles').children[0].children[1].children[1],file);
  assert.equal(view.document.getElementById('start').disabled,true);
  assert.equal(view.document.getElementById('refresh-image-models').disabled,true);
  assert.match(view.document.getElementById('feedback').textContent,/Bild.*(?:übernahme|übernommen)|Bildübernahme/i);
  releaseUpload({id:'NEW',url:'/media/NEW',name:'new.png'});await uploading;
  assert.equal(view.state.images.image.id,'NEW');
  assert.equal(view.document.getElementById('start').disabled,false);
  assert.equal(view.document.getElementById('refresh-image-models').disabled,false);
});

const allDescendants=node=>[node,...node.children.flatMap(allDescendants)];
function enableProposals(view,workflows){
  view.state.workflows=workflows;view.chooseWorkflow(workflows[0]);
  view.state.models=[{key:'manual-language-model',name:'Mein Sprachmodell',loaded_instances:[{id:'loaded-instance'}]}];
  view.document.getElementById('model').value='manual-language-model';view.document.getElementById('instance').value='loaded-instance';
  view.document.getElementById('instruction').value='Bearbeite das Foto und mache danach einen Film daraus.';view.updateActions();
}
const plan={assistant_text:'Bitte beide Schritte einzeln prüfen.',steps:[{workflow_id:'sdxl',prompt:'Eine blaue Tasse',controls:{width:1024},reason:'Zuerst ein Bild erstellen.'},{workflow_id:'wan',prompt:'Die Kamera bewegt sich langsam.',controls:{width:640},reason:'Danach ein ausgewähltes Bild bewegen.'}]};

test('proposal request can choose other tools and applying each step only changes its form',async()=>{
  const calls=[];
  const view=harness(async(path,options)=>{calls.push({path,body:options?.body});return path.endsWith('/check') ? {issues:[]} : plan;},false,true);
  const first=editableWorkflow(),second=editableWorkflow('wan',[{id:'image',label:'Startbild'}]);second.name='Bild in Bewegung bringen';
  enableProposals(view,[first,second]);
  view.field('seed').value=73;view.field('image_model').value='checkpoints/alternative.safetensors';
  await view.document.getElementById('propose').listeners.click();
  assert.equal(calls[0].path,'/api/tool-proposals');
  assert.equal(calls[0].body.workflow_id,'sdxl');
  const buttons=()=>allDescendants(view.document.getElementById('proposal-steps')).filter(node=>node.tag==='button');
  assert.equal(buttons().length,2);
  await buttons()[0].listeners.click();
  assert.equal(view.field('prompt').value,'Eine blaue Tasse');assert.equal(Number(view.field('seed').value),73);
  assert.equal(view.field('image_model').value,'checkpoints/alternative.safetensors');
  assert.equal(view.document.getElementById('proposal').hidden,false);
  await buttons()[1].listeners.click();
  assert.equal(view.state.workflow.id,'wan');assert.equal(Number(view.field('width').value),640);
  assert.equal(view.field('image_model').value,'checkpoints/base.safetensors');
  assert.deepEqual(Object.keys(view.state.images),[]);assert.equal(view.document.getElementById('start').disabled,true);
  assert.equal(calls.some(call=>call.path==='/api/jobs' || call.path.startsWith('/api/models/')),false);
});

test('request-time originals remain visible and immutable after multiple explicit proposal adoptions',async()=>{
  const calls=[];let release;
  const view=harness(async(path,options={})=>{
    calls.push({path,body:options.body});
    if(path==='/api/tool-proposals')return new Promise(resolve=>release=resolve);
    return path.endsWith('/check') ? {issues:[]} : [];
  },false,true);
  const first=editableWorkflow(),second=editableWorkflow('wan',[{id:'image',label:'Startbild'}]);
  enableProposals(view,[first,second]);
  const instruction='Nur die Tasse blau färben.\nDer Hintergrund bleibt erhalten.';
  view.document.getElementById('instruction').value=instruction;
  view.field('prompt').value='Mein ursprünglicher roter Becher';view.field('width').value=640;view.field('seed').value=73;
  view.field('image_model').value='checkpoints/alternative.safetensors';
  const pending=view.document.getElementById('propose').listeners.click();
  // A programmatic field change has no input event; the receipt must still use request-time values.
  view.field('prompt').value='Spätere Formularanzeige';
  release(plan);await pending;
  const original=view.state.proposal.original;
  assert.ok(original,'Der ursprüngliche Auftrag und Formularstand fehlen.');
  assert.equal(original.instruction,instruction);assert.equal(original.workflow_id,'sdxl');
  assert.equal(original.controls.prompt,'Mein ursprünglicher roter Becher');assert.equal(original.controls.width,640);
  assert.equal(original.controls.seed,73);assert.equal(original.controls.image_model,'checkpoints/alternative.safetensors');
  assert.equal(original.workflow_defaults.wan.width,512);
  assert.equal(Object.isFrozen(original),true);assert.equal(Object.isFrozen(original.controls),true);assert.equal(Object.isFrozen(original.workflow_defaults.wan),true);
  const buttons=()=>allDescendants(view.document.getElementById('proposal-steps')).filter(node=>node.tag==='button');
  await buttons()[0].listeners.click();await buttons()[1].listeners.click();
  assert.equal(view.state.proposal.original,original);
  assert.equal(view.field('prompt').value,'Die Kamera bewegt sich langsam.');
  assert.equal(view.document.getElementById('instruction').value,instruction);
  const originalPanel=allDescendants(view.document.getElementById('proposal-steps')).find(node=>node.className==='proposal-original');
  assert.ok(originalPanel,'Der Originalbeleg muss auch nach Übernahmen sichtbar bleiben.');
  const originalText=allDescendants(originalPanel).map(node=>node.textContent).join('\n');
  assert.match(originalText,/Mein ursprünglicher roter Becher/);assert.match(originalText,/Nur die Tasse blau färben/);
  assert.doesNotMatch(originalText,/Spätere Formularanzeige|Die Kamera bewegt sich langsam/);
  assert.equal(calls.filter(call=>call.path==='/api/tool-proposals').length,1);
  assert.equal(calls.some(call=>call.path==='/api/jobs' || call.path.startsWith('/api/models/')),false);
});

test('form edits while a proposal is pending prevent its late step cards from appearing',async()=>{
  let release;
  const view=harness(async path=>path==='/api/tool-proposals'?new Promise(resolve=>release=resolve):{},false,true);
  enableProposals(view,[editableWorkflow()]);
  const pending=view.document.getElementById('propose').listeners.click();
  view.field('width').value=640;view.changeControl({target:{name:'width'}});
  release(plan);await pending;
  assert.equal(view.document.getElementById('proposal').hidden,true);
  assert.equal(view.state.proposal,null);
  assert.equal(Number(view.field('width').value),640);
});

test('a retained step button cannot apply after the selected language instance changes',async()=>{
  const view=harness(async()=>plan,false,true);enableProposals(view,[editableWorkflow()]);
  await view.document.getElementById('propose').listeners.click();
  const button=allDescendants(view.document.getElementById('proposal-steps')).find(node=>node.tag==='button');
  assert.ok(button,'Schrittauswahl fehlt');
  view.document.getElementById('instance').value='different-instance';
  await button.listeners.click();
  assert.equal(view.field('prompt').value,'Before refresh');
  assert.equal(view.state.proposal,null);
});

test('applying a step while a picture upload is pending leaves that form untouched',async()=>{
  const view=harness(async()=>plan,false,true);enableProposals(view,[editableWorkflow()]);
  await view.document.getElementById('propose').listeners.click();
  const button=allDescendants(view.document.getElementById('proposal-steps')).find(node=>node.tag==='button');
  assert.ok(button,'Schrittauswahl fehlt');
  view.state.uploads.add({generation:view.state.generation});view.updateActions();
  assert.equal(button.disabled,true);
  await button.listeners.click();
  assert.equal(view.field('prompt').value,'Before refresh');
});

test('saving a language model selection fences refresh and load until the new selection is saved',async()=>{
  let releaseSave,modelReads=0;
  const view=harness(async(path,{body}={})=>{
    if(path==='/api/settings')return new Promise(resolve=>releaseSave=()=>resolve(body));
    if(path==='/api/models'){modelReads++;return view.state.models;}
    return [];
  });
  view.state.models=[{key:'old',name:'Old',loaded_instances:[]},{key:'new',name:'New',loaded_instances:[]}];
  view.state.settings={model_key:'old',instance_id:''};
  view.document.getElementById('model').value='new';
  const saving=view.document.getElementById('model').listeners.change();
  assert.equal(view.document.getElementById('refresh-models').disabled,true);
  assert.equal(view.document.getElementById('load-model').disabled,true);
  await view.document.getElementById('refresh-models').listeners.click();
  assert.equal(modelReads,0,'refresh must not restore a stale saved selection');
  releaseSave();await saving;
  assert.equal(view.document.getElementById('model').value,'new');
  assert.equal(view.state.settings.model_key,'new');
  assert.equal(view.document.getElementById('load-model').disabled,false);
});

test('refreshing the language model list fences model loading',async()=>{
  let release;
  const view=harness(async()=>new Promise(resolve=>release=resolve));
  view.state.models=[{key:'local',name:'Local',loaded_instances:[]}];
  view.state.settings={model_key:'local',instance_id:''};
  view.document.getElementById('model').value='local';view.updateActions();
  assert.equal(view.document.getElementById('load-model').disabled,false);
  const refresh=view.document.getElementById('refresh-models').listeners.click();
  assert.equal(view.document.getElementById('load-model').disabled,true);
  release(view.state.models);await refresh;
  assert.equal(view.document.getElementById('load-model').disabled,false);
});

test('selected image model readiness refreshes the visible exact tool dependencies',async()=>{
  const view=harness(async()=>({issues:[],dependencies:[{name:'chosen.safetensors',path:'E:\\models\\chosen.safetensors',role:'Bildmodell',loader:'UNETLoader',node:'1'}]}),false,true);
  const workflow=editableWorkflow();workflow.dependencies=[{name:'base.safetensors',path:'E:\\models\\base.safetensors',role:'Bildmodell',loader:'UNETLoader',node:'1'}];
  view.chooseWorkflow(workflow);
  const dependencyText=()=>allDescendants(view.document.getElementById('workflow-models')).map(node=>node.textContent).join('\n');
  assert.match(dependencyText(),/base\.safetensors/);
  view.field('image_model').value='checkpoints/alternative.safetensors';
  await view.changeControl({target:{name:'image_model'}});
  await settleEvents();
  assert.match(dependencyText(),/chosen\.safetensors/);
  assert.match(dependencyText(),/E:\\models\\chosen\.safetensors/);
  assert.doesNotMatch(dependencyText(),/base\.safetensors/);
});

test('image model manager shows assigned tools separately from unused components',async()=>{
  const view=harness(async path=>path==='/api/workflows' ? [editableWorkflow()] : path.endsWith('/check') ? {issues:[],dependencies:[]} : [
    {name:'krea.gguf',kind:'diffusion_model',path:'E:\\models\\krea.gguf',used_by:[{id:'krea2',name:'Bild mit KREA 2 bearbeiten'}]},
    {name:'spare-encoder.safetensors',kind:'text_encoder',path:'E:\\models\\spare-encoder.safetensors',used_by:[]},
  ],false,true);
  view.chooseWorkflow(editableWorkflow());
  await view.document.getElementById('refresh-image-models').listeners.click();
  const text=allDescendants(view.document.getElementById('image-model-files')).map(node=>node.textContent).join('\n');
  assert.match(text,/Werkzeug: Bild mit KREA 2 bearbeiten/);
  assert.match(text,/Derzeit von keinem der sechs Werkzeuge verwendet/);
  assert.match(text,/Textencoder/);
});

test('service status distinguishes compatibility and transient failures without preventing reconnection',async()=>{
  const cases=[
    {comfy:{ready:true,ownership:'compatible',pid:15608},label:/Rechendienst bereit/},
    {comfy:{ready:false,ownership:'free',pid:null},label:/Startet bei Berechnung/},
    {comfy:{ready:false,ownership:'owned',pid:15608,message:'Der eigene Dienst startet noch.'},label:/noch nicht bereit/,hint:/eigene Dienst startet noch/},
    {comfy:{ready:false,ownership:'foreign',pid:15608,message:'Port 8188 antwortet mit einer fremden API.'},label:/nicht nutzbar/,hint:/fremden API/},
    {comfy:{ready:false,ownership:'unknown',pid:null,message:'Prozessinformationen sind nicht lesbar.'},label:/ungeklärt/,hint:/nicht lesbar/},
  ];
  for(const {comfy,label,hint} of cases){
    const view=harness(async path=>{
      if(path==='/api/workflows')return [view.workflow];
      if(path==='/api/settings')return {};
      if(path==='/api/status')return {project_root:'E:\\MORPH-Studio',free_bytes:1024**3,comfy};
      return [];
    });
    await view.boot();
    assert.match(view.document.getElementById('comfy-state').textContent,label);
    view.state.images.image={id:'ONE',url:'/media/ONE',name:'one.png'};view.updateActions();
    assert.equal(view.document.getElementById('start').disabled,false,'Ein vorübergehender Status darf die erneute Verbindungsprüfung nicht sperren.');
    if(hint)assert.match(view.document.getElementById('start-hint').textContent,hint);
  }
});

test('job completion and history refresh update service status using reads without resubmission',async()=>{
  const calls=[];let comfy={ready:true,ownership:'compatible',pid:15608};
  const view=harness(async(path,options={})=>{
    calls.push({path,method:options.method || 'GET'});
    if(path==='/api/workflows')return [view.workflow];
    if(path==='/api/settings')return {};
    if(path==='/api/status')return {project_root:'E:\\MORPH-Studio',free_bytes:1024**3,comfy};
    if(path==='/api/jobs' && options.method==='POST')return {...receipt(options.body),error:'Dienst nicht erreichbar.',error_code:'comfy_start',details:'Verbindung abgelehnt.'};
    return [];
  },true);
  await view.boot();
  view.state.images.image={id:'ONE',url:'/media/ONE',name:'one.png'};view.updateActions();
  const initialReads=calls.filter(call=>call.path==='/api/status').length;
  comfy={ready:false,ownership:'unknown',pid:null,message:'Verbindung abgelehnt.'};
  await view.document.getElementById('workflow-form').listeners.submit({preventDefault(){}});
  assert.ok(calls.filter(call=>call.path==='/api/status').length>initialReads,'Der Status muss nach dem Startversuch neu gelesen werden.');
  assert.match(view.document.getElementById('comfy-state').textContent,/ungeklärt/);
  assert.equal(pendingRequest(view.storage),null,'Ein bestätigter Fehlerauftrag schließt seinen Startbeleg.');
  comfy={ready:true,ownership:'compatible',pid:15608};
  await view.refreshJobs();
  assert.match(view.document.getElementById('comfy-state').textContent,/Rechendienst bereit/);
  assert.equal(calls.filter(call=>call.path==='/api/jobs' && call.method==='POST').length,1);
  assert.ok(calls.filter(call=>call.path==='/api/status').every(call=>call.method==='GET'));
  assert.equal(calls.some(call=>call.path==='/api/models/load'),false);
});

test('a delayed status read cannot keep a confirmed failed start locked',async()=>{
  let releaseStatus;
  const view=harness(async(path,options={})=>{
    if(path==='/api/jobs' && options.method==='POST')return {...receipt(options.body),error:'Dienst noch nicht bereit.',error_code:'comfy_start'};
    if(path==='/api/status')return new Promise(resolve=>releaseStatus=resolve);
    return [];
  },true);
  view.state.images.image={id:'ONE',url:'/media/ONE',name:'one.png'};view.updateActions();
  const starting=view.document.getElementById('workflow-form').listeners.submit({preventDefault(){}});
  await settleEvents();
  try{
    assert.equal(pendingRequest(view.storage),null);
    assert.equal(view.document.getElementById('start').disabled,false,'Nur die Berechnung und ihr Startbeleg dürfen diesen Start sperren, nicht eine verspätete Statusantwort.');
  }finally{
    releaseStatus({comfy:{ready:false,ownership:'unknown',pid:null}});await starting;
  }
});

test('switching simple and expert mode preserves edited fields pictures proposals and pending receipts',async()=>{
  const calls=[];const view=harness(async(path,options)=>{calls.push({path,options});return [];},true,true);
  const tool=editableWorkflow('kontext',[{id:'image',label:'Ausgangsbild'}]);view.chooseWorkflow(tool);
  const prompt=view.field('prompt'),width=view.field('width'),seed=view.field('seed'),model=view.field('image_model');
  prompt.value='Mein unveränderter Auftrag';width.value='768';seed.value='123';model.value='checkpoints/alternative.safetensors';
  view.state.images.image={id:'ORIGINAL',name:'original.png',url:'/media/ORIGINAL'};
  view.state.proposal={steps:[],applied:new Set()};const proposal=view.state.proposal;
  view.storage.setItem('morph.pending-request.v1',JSON.stringify({request_id:'existing-start'}));
  view.updateActions();
  const receiptBefore=view.storage.getItem('morph.pending-request.v1'),generation=view.state.generation;
  const technical=view.document.getElementById('controls').querySelectorAll('[data-expert-only]')[0];
  assert.ok(technical,'Technische Einstellungen brauchen eine eigene Gruppe.');
  assert.equal(technical.hidden,true);assert.equal(view.document.getElementById('expert-settings').hidden,true);
  const toggle=view.document.getElementById('expert-mode');
  assert.equal(toggle.checked,false);
  toggle.checked=true;await toggle.listeners.change();
  assert.equal(technical.hidden,false);assert.equal(view.document.getElementById('expert-settings').hidden,false);
  toggle.checked=false;await toggle.listeners.change();
  assert.equal(technical.hidden,true);
  assert.equal(view.field('prompt'),prompt);assert.equal(prompt.value,'Mein unveränderter Auftrag');
  assert.equal(width.value,'768');assert.equal(seed.value,'123');assert.equal(model.value,'checkpoints/alternative.safetensors');
  assert.equal(view.state.images.image.id,'ORIGINAL');assert.equal(view.state.proposal,proposal);
  assert.equal(view.state.generation,generation);assert.equal(view.storage.getItem('morph.pending-request.v1'),receiptBefore);
  assert.equal(view.document.getElementById('start').disabled,true,'Ein Moduswechsel darf den offenen Startbeleg nicht entsperren.');
  assert.deepEqual(calls,[]);
});

const picture=(name='new.png')=>({name,type:'image/png',size:1024});
const dropEvent=files=>({dataTransfer:{files,dropEffect:'none'},preventDefault(){this.prevented=true;},stopPropagation(){}});
const uploadSlot=view=>view.document.getElementById('image-roles').children[0];

test('dropping a picture uses the role upload and never starts a calculation',async()=>{
  const calls=[];const view=harness(async(path,options)=>{calls.push({path,options});return {id:'DROPPED',url:'/media/DROPPED',name:'dropped.png'};});
  const slot=uploadSlot(view),event=dropEvent([picture('dropped.png')]);
  assert.equal(typeof slot.listeners.drop,'function');await slot.listeners.drop(event);
  assert.equal(event.prevented,true);assert.equal(view.state.images.image.id,'DROPPED');
  assert.equal(calls.length,1);assert.equal(calls[0].path,'/api/uploads');assert.equal(calls[0].options.method,'POST');
  assert.equal(view.document.getElementById('start').disabled,false);
});

test('a newer dropped picture wins over a late picker response for the same role',async()=>{
  const pending=[];const view=harness(async path=>path==='/api/uploads'?new Promise(resolve=>pending.push(resolve)):[]);
  const slot=uploadSlot(view),file=slot.children[1].children[1];file.files=[picture('old.png')];
  const oldUpload=file.listeners.change();
  assert.equal(typeof slot.listeners.drop,'function');const newUpload=slot.listeners.drop(dropEvent([picture('new.png')]));
  pending[1]({id:'NEW',url:'/media/NEW',name:'new.png'});await newUpload;
  assert.equal(view.state.images.image.id,'NEW');assert.equal(view.document.getElementById('start').disabled,false);
  pending[0]({id:'OLD',url:'/media/OLD',name:'old.png'});await oldUpload;
  assert.equal(view.state.images.image.id,'NEW');assert.equal(slot.children[2].src,'/media/NEW');
});

test('a dropped picture from a previous workflow cannot enter the current picture roles',async()=>{
  let release;const view=harness(async()=>new Promise(resolve=>release=resolve));const slot=uploadSlot(view);
  assert.equal(typeof slot.listeners.drop,'function');const uploading=slot.listeners.drop(dropEvent([picture()]));
  view.chooseWorkflow({...view.workflow,id:'reactor',roles:[{id:'target',label:'Zielfoto'},{id:'source',label:'Quellgesicht'}]});
  release({id:'STALE',url:'/media/STALE',name:'old.png'});await uploading;
  assert.deepEqual(Object.keys(view.state.images),[]);assert.equal(view.document.getElementById('start').disabled,true);
});

test('invalid drops leave the assigned picture intact and show a role-specific error',async()=>{
  let calls=0;const view=harness(async()=>{calls++;return [];});view.state.images.image={id:'KEEP',url:'/media/KEEP',name:'keep.png'};view.updateActions();
  const slot=uploadSlot(view);assert.equal(typeof slot.listeners.drop,'function');
  for(const [files,message] of [ [[picture(),picture('second.png')],/ein Bild/i],[[{name:'notes.txt',type:'text/plain',size:50}],/PNG.*JPEG.*WebP/],[[{...picture(),size:64*1024**2+1}],/64 MiB/] ]){
    await slot.listeners.drop(dropEvent(files));
    const error=slot.children.find(node=>node.attributes.role==='alert');
    assert.ok(error);assert.equal(error.hidden,false);assert.match(error.textContent,message);
    assert.equal(view.state.images.image.id,'KEEP');
  }
  assert.equal(calls,0);
});

test('failed picture upload explains the error inside its slot and allows another selection',async()=>{
  const view=harness(async()=>{throw new Error('Das Bild ist beschädigt.');});const slot=uploadSlot(view),file=slot.children[1].children[1];
  file.files=[picture()];await file.listeners.change();
  const error=slot.children.find(node=>node.attributes.role==='alert');
  assert.ok(error);assert.equal(error.hidden,false);assert.match(error.textContent,/beschädigt/);
  assert.equal(file.disabled,false);assert.deepEqual(Object.keys(view.state.images),[]);
  assert.equal(view.document.getElementById('start').disabled,true);
});

test('an unavailable optional language service leaves picture creation available',async()=>{
  const view=harness(async path=>{if(path==='/api/models')throw new Error('Ollama ist nicht erreichbar.');return [];});
  view.state.images.image={id:'ONE',url:'/media/ONE',name:'one.png'};view.updateActions();
  await view.document.getElementById('refresh-models').listeners.click();
  assert.match(view.document.getElementById('model-info').textContent,/Ollama.*nicht erreichbar/);
  assert.equal(view.document.getElementById('start').disabled,false);
  assert.equal(view.document.getElementById('propose').disabled,true);
});

const savedProject=(id='P',original='ORIGINAL',versions=[])=>({id,name:'Mein Bildprojekt',original_version_id:id+'-v0',versions:[{id:id+'-v0',project_id:id,parent_version_id:null,created_at:'2026-10-20T10:00:00Z',status:'original',media:{id:original,name:'original.png',url:'/media/'+original,kind:'image'},metadata:{},sha256:'original-hash'},...versions]});

test('saving an uploaded original fences start and binds the submitted parent to that exact picture',async()=>{
  let finishSave,submitted;const calls=[];
  const view=harness(async(path,options={})=>{
    calls.push({path,options});
    if(path==='/api/uploads')return {id:'UPLOADED',name:'original.png',url:'/media/UPLOADED',kind:'image'};
    if(path==='/api/image-projects' && options.method==='POST')return new Promise(resolve=>finishSave=resolve);
    if(path==='/api/jobs' && options.method==='POST'){submitted=options.body;return receipt(options.body);}
    return [];
  },true,false,true);
  const file=uploadSlot(view).children[1].children[1];file.files=[picture()];const uploading=file.listeners.change();await settleEvents();
  try{
    assert.equal(typeof finishSave,'function','Das Original muss nach der Bildübernahme gesichert werden.');
    assert.equal(view.document.getElementById('start').disabled,true);
    await view.document.getElementById('workflow-form').listeners.submit({preventDefault(){}});assert.equal(submitted,undefined);
  }finally{if(finishSave)finishSave(savedProject('P','UPLOADED'));await uploading;}
  assert.equal(view.document.getElementById('start').disabled,false);
  assert.match(view.document.getElementById('image-context').textContent,/Original/);assert.doesNotMatch(view.document.getElementById('image-context').textContent,/P-v0/);
  await view.document.getElementById('workflow-form').listeners.submit({preventDefault(){}});
  assert.equal(submitted.project_id,'P');assert.equal(submitted.parent_version_id,'P-v0');assert.equal(submitted.images.image,'UPLOADED');
  const saved=calls.find(call=>call.path==='/api/image-projects' && call.options.method==='POST').options.body;
  assert.equal(saved.original_media_id,'UPLOADED');assert.match(saved.request_id,/^[0-9a-f-]{36}$/);
});

test('a late original project response cannot attach its context to a replacement picture',async()=>{
  const saves=[];let uploadCount=0;
  const view=harness(async(path,options={})=>{
    if(path==='/api/uploads'){const id='IMAGE'+(++uploadCount);return {id,name:id+'.png',url:'/media/'+id,kind:'image'};}
    if(path==='/api/image-projects' && options.method==='POST')return new Promise(resolve=>saves.push(resolve));
    return [];
  },false,false,true);
  const slot=uploadSlot(view);const first=slot.listeners.drop(dropEvent([picture('first.png')]));await settleEvents();
  assert.equal(saves.length,1,'Die erste Sicherung muss laufen.');
  const second=slot.listeners.drop(dropEvent([picture('second.png')]));await settleEvents();
  saves[1](savedProject('NEW','IMAGE2'));await second;
  saves[0](savedProject('OLD','IMAGE1'));await first;
  assert.equal(view.state.images.image.id,'IMAGE2');assert.equal(view.state.projectContext.project_id,'NEW');assert.equal(view.state.projectContext.image_id,'IMAGE2');
});

test('reopening a persisted project is read only and selecting a branch explicitly prepares its input',async()=>{
  const child={id:'P-v1',project_id:'P',parent_version_id:'P-v0',created_at:'2026-10-20T11:00:00Z',status:'completed',media:{id:'CHILD',name:'branch.png',url:'/media/CHILD',kind:'image'},metadata:{prompt:'Blau',workflow_id:'kontext',controls:{seed:17}},sha256:'child-hash'};
  const project=savedProject('P','ORIGINAL',[child]),calls=[];
  const view=harness(async(path,options={})=>{
    calls.push({path,options});
    if(path==='/api/image-projects')return [project];
    if(path==='/api/image-projects/P')return project;
    if(path==='/api/image-versions/P-v1/input')return {project_id:'P',parent_version_id:'P-v1',image:{id:'COPY',name:'branch.png',url:'/media/COPY',kind:'image'}};
    return [];
  },false,true,true);
  view.state.workflows=[editableWorkflow('sdxl'),editableWorkflow('krea2',[{id:'image',label:'Ausgangsbild'}])];view.chooseWorkflow(view.state.workflows[0]);
  const refresh=view.document.getElementById('refresh-projects');assert.equal(typeof refresh.listeners.click,'function');await refresh.listeners.click();
  const projectButton=allDescendants(view.document.getElementById('image-projects')).find(node=>node.tag==='button');assert.ok(projectButton);await projectButton.listeners.click();
  assert.equal(view.state.project.id,'P');assert.deepEqual(Object.keys(view.state.images),[]);
  assert.equal(calls.some(call=>call.options.method==='POST'),false,'Öffnen darf kein Bild übernehmen.');
  const versionCard=allDescendants(view.document.getElementById('image-versions')).find(node=>node.dataset.versionId==='P-v1');assert.ok(versionCard);
  await allDescendants(versionCard).find(node=>node.tag==='button' && node.textContent==='Variante erstellen').listeners.click();
  assert.equal(view.state.workflow.id,'krea2');assert.equal(view.state.images.image.id,'COPY');assert.equal(view.state.projectContext.parent_version_id,'P-v1');
  assert.match(view.document.getElementById('image-context').textContent,/Version 1/);assert.doesNotMatch(view.document.getElementById('image-context').textContent,/P-v1/);
  assert.equal(calls.filter(call=>call.path==='/api/image-versions/P-v1/input').length,1);
  assert.equal(calls.some(call=>call.path==='/api/jobs'),false);
});

test('using a version in face editing preserves the source picture and targets the target role',async()=>{
  const project=savedProject();const calls=[];
  const view=harness(async(path,options={})=>{calls.push({path,options});if(path==='/api/image-projects')return [project];if(path==='/api/image-projects/P')return project;if(path.endsWith('/input'))return {project_id:'P',parent_version_id:'P-v0',image:{id:'COPY',url:'/media/COPY',name:'original.png',kind:'image'}};return [];},false,true,true);
  const reactor=editableWorkflow('reactor',[{id:'target',label:'Zielfoto'},{id:'source',label:'Quellgesicht'}]);view.state.workflows=[reactor];view.chooseWorkflow(reactor);view.state.images.source={id:'SOURCE',name:'face.png',url:'/media/SOURCE'};
  const refresh=view.document.getElementById('refresh-projects');assert.equal(typeof refresh.listeners.click,'function');await refresh.listeners.click();await allDescendants(view.document.getElementById('image-projects')).find(node=>node.tag==='button').listeners.click();
  await allDescendants(view.document.getElementById('image-versions')).find(node=>node.tag==='button' && node.textContent==='Original verwenden').listeners.click();
  assert.equal(view.state.workflow.id,'reactor');assert.equal(view.state.images.source.id,'SOURCE');assert.equal(view.state.images.target.id,'COPY');
  assert.equal(calls.some(call=>call.path==='/api/jobs'),false);
});

test('refreshing a completed job with a version error retries its metadata without submitting again',async()=>{
  const calls=[],failed={id:'JOB',request_id:'REQUEST',state:'completed',workflow_id:'kontext',outputs:[{id:'DONE',name:'done.png',url:'/media/DONE',kind:'image'}],versioning_error:'Speicher vorübergehend gesperrt.',created_at:'2026-10-20T10:00:00Z'};
  const view=harness(async(path,options={})=>{
    calls.push({path,method:options.method || 'GET'});
    if(path==='/api/jobs')return [failed];
    if(path==='/api/jobs/JOB'){const {versioning_error,...recovered}=failed;return {...recovered,versions:[{id:'RECOVERED'}]};}
    return [];
  });
  await view.document.getElementById('refresh-jobs').listeners.click();
  assert.equal(view.state.jobs[0].versioning_error,undefined,'Aktualisieren muss den tatsächlichen Metadatenbeleg nachholen.');
  assert.equal(view.state.jobs[0].outputs[0].id,'DONE');assert.equal(view.state.jobs[0].versions[0].id,'RECOVERED');
  assert.equal(calls.filter(call=>call.path==='/api/jobs/JOB' && call.method==='GET').length,1);
  assert.equal(calls.some(call=>call.method==='POST'),false);
});

test('a failed original save requires an explicit retry with the same idempotency receipt',async()=>{
  const saves=[];const view=harness(async(path,options={})=>{
    if(path==='/api/uploads')return {id:'ORIGINAL',url:'/media/ORIGINAL',name:'original.png',kind:'image'};
    if(path==='/api/image-projects' && options.method==='POST'){saves.push(options.body);if(saves.length===1)throw new Error('Keine Antwort.');return savedProject();}
    return [];
  },false,false,true);
  await uploadSlot(view).listeners.drop(dropEvent([picture()]));
  assert.equal(saves.length,1);assert.equal(view.document.getElementById('start').disabled,true);
  assert.equal(view.document.getElementById('save-original').hidden,false);
  await view.document.getElementById('save-original').listeners.click();
  assert.equal(saves.length,2);assert.equal(saves[0].request_id,saves[1].request_id);
  assert.equal(view.document.getElementById('start').disabled,false);assert.equal(view.state.projectContext.project_id,'P');
});

test('a late explicit version input cannot replace a newer uploaded original or its project context',async()=>{
  let finishInput;const project=savedProject(),calls=[];
  const view=harness(async(path,options={})=>{
    calls.push({path,options});
    if(path==='/api/image-projects' && options.method==='POST')return savedProject('NEW','NEWIMAGE');
    if(path==='/api/image-projects')return [project];if(path==='/api/image-projects/P')return project;
    if(path.endsWith('/input'))return new Promise(resolve=>finishInput=resolve);
    if(path==='/api/uploads')return {id:'NEWIMAGE',name:'new.png',url:'/media/NEWIMAGE',kind:'image'};
    return [];
  },false,false,true);
  await view.document.getElementById('refresh-projects').listeners.click();await allDescendants(view.document.getElementById('image-projects')).find(node=>node.tag==='button').listeners.click();
  const using=allDescendants(view.document.getElementById('image-versions')).find(node=>node.tag==='button' && node.textContent==='Weiterbearbeiten').listeners.click();
  await settleEvents();await uploadSlot(view).listeners.drop(dropEvent([picture()]));
  finishInput({project_id:'P',parent_version_id:'P-v0',image:{id:'LATE',name:'late.png',url:'/media/LATE',kind:'image'}});await using;
  assert.equal(view.state.images.image.id,'NEWIMAGE');assert.equal(view.state.projectContext.project_id,'NEW');
  assert.equal(calls.some(call=>call.path==='/api/jobs'),false);
});

test('a retained version action cannot invalidate an original while its save is still running',async()=>{
  let finishSave;const calls=[],project=savedProject('OLDER','OLDIMAGE');
  const view=harness(async(path,options={})=>{
    calls.push({path,options});
    if(path==='/api/image-projects' && options.method==='POST')return new Promise(resolve=>finishSave=resolve);
    if(path==='/api/image-projects')return [project];if(path==='/api/image-projects/OLDER')return project;
    if(path==='/api/uploads')return {id:'NEWIMAGE',url:'/media/NEWIMAGE',name:'new.png',kind:'image'};
    if(path.endsWith('/input'))throw new Error('Eingabe derzeit nicht lesbar.');return [];
  },false,false,true);
  await view.document.getElementById('refresh-projects').listeners.click();await allDescendants(view.document.getElementById('image-projects')).find(node=>node.tag==='button').listeners.click();
  const retained=allDescendants(view.document.getElementById('image-versions')).find(node=>node.tag==='button' && node.textContent==='Weiterbearbeiten');
  const uploading=uploadSlot(view).listeners.drop(dropEvent([picture()]));await settleEvents();
  try{await retained.listeners.click();assert.equal(calls.some(call=>call.path.endsWith('/input')),false,'Eine laufende Originalsicherung muss ihre technische Bildzuordnung behalten.');}
  finally{finishSave(savedProject('NEW','NEWIMAGE'));await uploading;}
  assert.equal(view.state.projectContext.project_id,'NEW');assert.equal(view.document.getElementById('start').disabled,false);
});

test('a new page loads persisted image projects without restoring or submitting an input automatically',async()=>{
  const project=savedProject(),calls=[];const tool={id:'kontext',name:'Bild bearbeiten',description:'',roles:[{id:'image',label:'Ausgangsbild'}],issues:[],controls:{}};
  const view=harness(async(path,options={})=>{
    calls.push({path,options});if(path==='/api/image-projects')return [project];if(path==='/api/image-projects/P')return project;
    if(path==='/api/workflows')return [tool];if(path==='/api/settings')return {};if(path==='/api/status')return {project_root:'E:\\MORPH-Studio',free_bytes:1024**3,comfy:{ready:false,ownership:'free',pid:null}};return [];
  },false,false,true);
  await view.boot();
  const button=allDescendants(view.document.getElementById('image-projects')).find(node=>node.tag==='button');assert.ok(button,'Ein Neuladen muss gespeicherte Projekte erneut anbieten.');await button.listeners.click();
  assert.equal(view.state.project.id,'P');assert.equal(view.state.projectContext,null);assert.deepEqual(Object.keys(view.state.images),[]);
  assert.equal(calls.some(call=>call.options.method==='POST'),false);
});

test('comparing a saved version changes neither the active input nor the compute queue',async()=>{
  const calls=[],project=savedProject();const view=harness(async(path,options={})=>{calls.push({path,options});return [];});
  view.state.project=project;view.state.images.image={id:'CURRENT',url:'/media/CURRENT'};view.updateActions();
  const compare=allDescendants(view.document.getElementById('image-versions')).find(node=>node.tag==='button' && node.textContent==='Vergleichen');assert.ok(compare);await compare.listeners.click();
  assert.equal(view.state.images.image.id,'CURRENT');assert.equal(view.state.projectContext,null);assert.equal(calls.length,0);assert.equal(view.document.getElementById('version-comparison').hidden,false);
});

test('dirty regional edits block submit and a saved mask is sent only on explicit compute',async()=>{
  const calls=[];let submitted;const view=harness(async(path,options={})=>{calls.push({path,options});if(path==='/api/uploads')return {id:'MASK'};if(path==='/api/jobs' && options.method==='POST'){submitted=options.body;return receipt(options.body);}return [];},false,true);
  const workflow={id:'krea2',name:'KREA',description:'',roles:[{id:'image',label:'Ausgangsbild'}],issues:[],controls:{prompt:{kind:'text',label:'Anweisung',default:'Nur Kleidung ändern'},width:{kind:'integer',label:'Breite',default:768,min:16,max:16384,step:16},height:{kind:'integer',label:'Höhe',default:512,min:16,max:16384,step:16}}};
  view.chooseWorkflow(workflow);view.state.images.image={id:'SOURCE',url:'/media/SOURCE'};view.state.projectContext={project_id:'PROJECT',parent_version_id:'PARENT',workflow_id:'krea2',role:'image',image_id:'SOURCE'};view.updateActions();
  const region=view.document.getElementById('edit-region'),nodes=allDescendants(region),image=nodes.find(node=>node.tag==='img'),canvas=nodes.find(node=>node.tag==='canvas');
  const context={fillRect(){},beginPath(){},moveTo(){},lineTo(){},stroke(){},arc(){},fill(){},getImageData(){return {data:[255,255,255,255]};}};canvas.getContext=()=>context;canvas.getBoundingClientRect=()=>({left:0,top:0,width:384,height:256});canvas.toBlob=fn=>fn({type:'image/png'});image.naturalWidth=384;image.naturalHeight=256;image.onload();
  canvas.listeners.pointerdown({button:0,pointerId:1,clientX:150,clientY:100,preventDefault(){}});canvas.listeners.pointerup();assert.equal(view.document.getElementById('start').disabled,true);
  await view.document.getElementById('workflow-form').listeners.submit({preventDefault(){}});assert.equal(submitted,undefined);
  await nodes.find(node=>node.tag==='button' && node.textContent==='Bereich übernehmen').listeners.click();assert.equal(submitted,undefined);assert.equal(view.document.getElementById('start').disabled,false);
  await view.document.getElementById('workflow-form').listeners.submit({preventDefault(){}});assert.equal(submitted.images.image,'SOURCE');assert.deepEqual({...submitted.edit_region},{mask_media_id:'MASK',source_media_id:'SOURCE',parent_version_id:'PARENT'});
  assert.equal(calls.filter(call=>call.path==='/api/jobs' && call.options.method==='POST').length,1);
});
