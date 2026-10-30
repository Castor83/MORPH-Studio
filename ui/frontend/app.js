import {request,createStartGuard,pendingRequest,finishRequest} from './api.js';
import {requiredImagesPresent,controlValues,modelSelections,fillControls,renderControls} from './forms.js';
import {ACTIVE,labels,renderJob,describeComfyStatus,renderProjectList,renderVersionTree,versionLabel} from './results.js';
import {prepareProposalStep,renderProposals} from './proposals.js';
import {createComparison} from './comparison.js';
import {createRegionEditor} from './regions.js';
import {createResources} from './resources.js';

const $=id=>document.getElementById(id);
const state={workflows:[],workflow:null,generation:0,uploads:new Set(),images:{},models:[],imageModels:[],imageModelsBusy:false,modelIssues:[],modelChecking:false,modelCheck:0,settings:{},jobs:[],selected:null,proposal:null,revision:0,starting:false,resolving:false,modelBusy:false,modelRefreshing:false,modelSaving:false,proposing:false,polling:false,ready:false,expert:false,comfy:{ready:false,ownership:'unknown'}};
Object.assign(state,{projects:[],project:null,projectContext:null,projectSave:null,projectError:'',historyError:'',historyRevision:0,inputRevision:0,versionBusy:false,outputProjectBusy:false,originalReceipts:new Map(),languageState:{busy:false,uncertain_instances:[]}});
const startRequest=createStartGuard(body=>request('/api/jobs',{method:'POST',body}));
const comparison=createComparison($('version-comparison'),document);
const regionEditor=createRegionEditor($('edit-region'),{doc:document,onChange:updateActions,getControls:()=>state.workflow?controlValues($('workflow-form'),state.workflow):{},onDimensions:values=>{fillControls($('workflow-form'),values,state.workflow);clearProposal();feedback('Die Bildgröße passt jetzt zum Seitenverhältnis deines Ausgangsbildes.');},uploadMask:async blob=>{const body=new FormData();body.append('file',blob,'bearbeitungsbereich.png');return request('/api/uploads',{method:'POST',body});}});
const resources=createResources($('resources'),{doc:document,request,onChange:updateActions});
let noticeTimer,serviceStatusRevision=0;
function feedback(message,error=false) {
  $('feedback').textContent=message; $('feedback').className='feedback'+(error?' error':''); $('feedback').hidden=false;
  clearTimeout(noticeTimer);noticeTimer=setTimeout(()=>$('feedback').hidden=true,error?14000:6500);
}
function fail(error){feedback(error.message || String(error),true);}
function setExpertMode(expert){
  state.expert=Boolean(expert);$('expert-mode').checked=state.expert;
  $('expert-settings').hidden=!state.expert;
  for(const group of $('controls').querySelectorAll('[data-expert-only]'))group.hidden=!state.expert;
  $('mode-help').textContent=state.expert?'Experte: Modelle, Größe und Berechnung gezielt einstellen. Deine Eingaben bleiben beim Umschalten erhalten.':'Einfach: Bild zuordnen, Auftrag beschreiben und selbst starten. Passende Voreinstellungen bleiben erhalten.';
  drawImageHistory();
}
function primaryRole(workflow=state.workflow){
  const role=workflow?.id==='reactor'?'target':['kontext','krea2','wan'].includes(workflow?.id)?'image':null;
  return role && workflow.roles.some(item=>item.id===role)?role:null;
}
function currentProjectContext(){
  const context=state.projectContext,role=primaryRole();
  return context && context.workflow_id===state.workflow?.id && context.role===role && context.image_id===state.images[role]?.id?context:null;
}
function drawImageHistory(){
  renderProjectList($('image-projects'),state.projects,state.project?.id,openImageProject);
  const uploading=[...state.uploads].some(upload=>upload.generation===state.generation);
  renderVersionTree($('image-versions'),state.project,useImageVersion,state.versionBusy || state.starting || Boolean(state.projectSave) || uploading,document,state.expert);
  comparison.setProject(state.project);
  $('project-error').textContent=state.projectError || state.historyError;$('project-error').hidden=!$('project-error').textContent;
  $('save-original').hidden=!state.projectError;$('save-original').disabled=Boolean(state.projectSave) || state.starting;
  const context=currentProjectContext();
  const project=context && (state.project?.id===context.project_id?state.project:state.projects.find(item=>item.id===context.project_id));
  $('image-context').textContent=state.projectSave?'Das Original wird unverändert im Bildprojekt gesichert …':context?'Nächste Berechnung: '+versionLabel(project,context.parent_version_id)+' als Ausgangsbild. Deine gewählte Eingabe bleibt erhalten.':'Noch keine Version als Ausgangsbild gewählt.';
}
function rememberProject(project){
  const index=state.projects.findIndex(item=>item.id===project.id);if(index<0)state.projects.unshift(project);else state.projects[index]=project;
}
async function refreshImageProjects(){
  try{const projects=await request('/api/image-projects');if(!Array.isArray(projects))throw new Error('Die Bildprojektliste ist nicht lesbar.');state.projects=projects;state.historyError='';}
  catch(error){state.historyError=error.message;}
  drawImageHistory();
}
async function openImageProject(projectId){
  const revision=++state.historyRevision;
  try{const project=await request('/api/image-projects/'+encodeURIComponent(projectId));if(revision!==state.historyRevision)return;if(!project?.id || !Array.isArray(project.versions))throw new Error('Der Bildverlauf ist nicht lesbar.');state.project=project;rememberProject(project);state.historyError='';}
  catch(error){if(revision===state.historyRevision)state.historyError=error.message;}
  drawImageHistory();
}
async function saveOriginal(image,role=primaryRole()){
  if(!role || state.images[role]?.id!==image.id)return;
  let requestId=state.originalReceipts.get(image.id);if(!requestId){requestId=crypto.randomUUID();state.originalReceipts.set(image.id,requestId);}
  const token={revision:state.inputRevision,image_id:image.id,workflow_id:state.workflow.id,role};
  state.projectSave=token;state.projectError='';state.projectContext=null;updateActions();
  try{
    const project=await request('/api/image-projects',{method:'POST',body:{request_id:requestId,original_media_id:image.id,name:image.name}});
    if(state.projectSave!==token || token.revision!==state.inputRevision || state.images[role]?.id!==image.id || state.workflow.id!==token.workflow_id)return;
    if(!project?.id || !project.original_version_id)throw new Error('Die Originalsicherung wurde nicht eindeutig bestätigt. Bitte erneut prüfen.');
    state.projectContext={project_id:project.id,parent_version_id:project.original_version_id,image_id:image.id,workflow_id:state.workflow.id,role};
    state.historyRevision++;state.project=project;rememberProject(project);state.historyError='';
  }catch(error){if(state.projectSave===token && token.revision===state.inputRevision){state.projectError='Original noch nicht gesichert: '+error.message;fail(error);}}
  finally{if(state.projectSave===token)state.projectSave=null;updateActions();}
}
async function useImageVersion(version,intent){
  if(intent==='Vergleichen'){comparison.compare(version);return;}
  if(state.versionBusy || state.starting || pending() || state.projectSave || [...state.uploads].some(upload=>upload.generation===state.generation))return;
  const revision=++state.inputRevision;state.versionBusy=true;state.historyError='';updateActions();
  try{
    const prepared=await request('/api/image-versions/'+encodeURIComponent(version.id)+'/input',{method:'POST',body:{}});
    if(revision!==state.inputRevision)return;
    if(prepared.project_id!==version.project_id || prepared.parent_version_id!==version.id || !prepared.image?.id)throw new Error('Die gewählte Version wurde nicht eindeutig als Eingabe bestätigt.');
    const workflow=primaryRole()?state.workflow:state.workflows.find(item=>item.id==='krea2') || state.workflows.find(item=>item.id==='kontext');
    const role=primaryRole(workflow);if(!role)throw new Error('Für dieses Bild ist kein passendes Bearbeitungswerkzeug verfügbar.');
    const same=workflow===state.workflow,controls=same?controlValues($('workflow-form'),workflow):{};
    const images=same?{...state.images,[role]:prepared.image}:{[role]:prepared.image};
    chooseWorkflow(workflow,{controls,images},{project_id:prepared.project_id,parent_version_id:prepared.parent_version_id,image_id:prepared.image.id,workflow_id:workflow.id,role});
    feedback(intent+': Das Ausgangsbild ist gewählt. Passe den Auftrag an und starte die Berechnung selbst.');
  }catch(error){if(revision===state.inputRevision){state.historyError=error.message;fail(error);}}
  finally{state.versionBusy=false;updateActions();}
}
async function projectFromOutput(image){
  if(state.outputProjectBusy)return;state.outputProjectBusy=true;
  let requestId=state.originalReceipts.get(image.id);if(!requestId){requestId=crypto.randomUUID();state.originalReceipts.set(image.id,requestId);}
  try{const project=await request('/api/image-projects',{method:'POST',body:{request_id:requestId,original_media_id:image.id,name:image.name}});if(!project?.id)throw new Error('Das Bildprojekt wurde nicht bestätigt.');state.historyRevision++;state.project=project;rememberProject(project);state.historyError='';feedback('Das fertige Bild ist als neues Original gesichert. Wähle „Weiterbearbeiten“, wenn du es verwenden möchtest.');}
  catch(error){state.historyError=error.message;fail(error);}finally{state.outputProjectBusy=false;drawImageHistory();}
}
async function refreshVersionedJob(jobId){
  try{rememberJob(await request('/api/jobs/'+encodeURIComponent(jobId)));drawJobs();await refreshProjectAfterJobs();}
  catch(error){fail(error);}
}
async function refreshProjectAfterJobs(){
  const projectId=state.project?.id;
  if(projectId && state.jobs.some(job=>job.state==='completed' && job.project_id===projectId))await openImageProject(projectId);
}
function showServiceStatus(comfy,languageState){
  if(languageState && typeof languageState==='object'){
    const previous=languageStateReason();
    state.languageState={busy:languageState.busy===true,uncertain_instances:Array.isArray(languageState.uncertain_instances)?languageState.uncertain_instances.filter(value=>typeof value==='string' && value.trim()):[]};
    if(previous || languageStateReason())drawInstances();
  }
  state.comfy=comfy || {ready:false,ownership:'unknown'};
  const status=describeComfyStatus(state.comfy);
  $('comfy-state').textContent=status.label;$('comfy-state').title=status.hint;
  $('comfy-state').className='subtle-badge'+(status.warning?' danger':'');
  updateActions();
}
async function refreshServiceStatus(){
  const revision=++serviceStatusRevision;
  try{
    const status=await request('/api/status');if(revision!==serviceStatusRevision)return;
    const previouslyBlocked=Boolean(languageStateReason());showServiceStatus(status.comfy,status.language_state);
    if(previouslyBlocked && !languageStateReason() && !state.modelBusy && !state.proposing)await refreshModels();
  }
  catch(error){if(revision===serviceStatusRevision)showServiceStatus({ready:false,ownership:'unknown',message:error.message});}
}
function clearProposal(){state.proposal=null;state.revision++;$('proposal').hidden=true;}
function selectedModel(){return state.models.find(model=>model.key===$('model').value);}
function selectedInstance(){return $('instance').value;}
function unloadInstance(){const uncertain=state.languageState.uncertain_instances;return uncertain.length===1?uncertain[0]:uncertain.length?'':selectedInstance();}
function languageStateReason(){return state.languageState.busy?'Eine Sprachmodellaktion läuft. Bitte warten.':state.languageState.uncertain_instances.length?'Der Zustand der Sprachmodellaktion ist unbekannt: '+state.languageState.uncertain_instances.join(', ')+'. Bitte dieses unbestätigte Sprachmodell bewusst freigeben, bevor du weiterarbeitest.':'';}
function proposalContext(){return {revision:state.revision,generation:state.generation,workflow:state.workflow,instance:selectedInstance(),model:$('model').value};}
function proposalCurrent(context){return context && context.revision===state.revision && context.generation===state.generation && context.workflow===state.workflow && context.instance===selectedInstance() && context.model===$('model').value;}
function proposalBlocked(){return state.proposing || state.modelBusy || state.modelRefreshing || state.modelSaving || state.imageModelsBusy || state.modelChecking || Boolean(imageBusyReason()) || Boolean(languageStateReason()) || resources.freeing || [...state.uploads].some(upload=>upload.generation===state.generation);}
function pending(){try{return pendingRequest();}catch(error){fail(error);return {request_id:'invalid'};}}
function imageBusyReason(){return !state.ready?'Die Oberfläche wird noch verbunden.':state.starting?'Ein Auftrag wird übergeben.':state.jobs.some(job=>ACTIVE.has(job.state))?'Ein Auftrag läuft oder wird noch geprüft.':pending() || state.resolving?'Ein Startbeleg ist noch ungeklärt.':'';}
function selectionBlocked(){return state.modelBusy || state.modelRefreshing || state.modelSaving || state.proposing || Boolean(languageStateReason()) || Boolean(imageBusyReason()) || resources.freeing;}
function updateActions(){
  const role=primaryRole();regionEditor.setSource({workflow:state.workflow,image:state.images[role],context:currentProjectContext()});
  const active=state.jobs.some(job=>ACTIVE.has(job.state));
  const missing=state.workflow && !requiredImagesPresent(state.workflow,state.images);
  const uploading=[...state.uploads].some(upload=>upload.generation===state.generation);
  resources.setBlocked(imageBusyReason() || languageStateReason() || (uploading?'Ein Bild wird übernommen.':state.projectSave?'Das Original wird gesichert.':state.versionBusy?'Eine Version wird als Eingabe vorbereitet.':state.modelBusy?'Das Sprachmodell wird geladen oder freigegeben.':state.proposing?'Ein Vorschlag wird erstellt.':''));
  $('start').disabled=!state.ready || state.starting || active || Boolean(pending()) || uploading || missing || state.imageModelsBusy || state.modelChecking || Boolean(state.modelIssues.length) || Boolean(state.projectSave) || Boolean(state.projectError) || state.versionBusy || regionEditor.blocked || resources.freeing || state.modelBusy || state.proposing || Boolean(languageStateReason());
  $('start').textContent=state.starting?'Auftrag wird übergeben …':'Berechnung starten ↗';
  $('start-hint').textContent=active?'Ein Auftrag läuft oder wird noch geprüft.':pending()?'Der letzte Startbeleg ist noch offen. Du kannst ihn gezielt klären.':state.modelBusy?'Das Sprachmodell wird geladen oder freigegeben. Bitte warten.':state.proposing?'Ein Vorschlag wird erstellt. Bitte warten.':state.projectSave?'Bitte warten, bis dein Original gesichert ist.':state.projectError?'Bitte die Originalsicherung im Bildverlauf erneut prüfen.':state.versionBusy?'Die gewählte Version wird als Eingabe vorbereitet.':uploading?'Bitte warten, bis das ausgewählte Bild übernommen wurde.':state.imageModelsBusy?'Die Modellliste wird aktualisiert.':state.modelChecking?'Die Modellzuordnung wird geprüft.':state.modelIssues.length?'Bitte die Modellhinweise oben prüfen.':missing?'Bitte zuerst alle benötigten Bilder auswählen.':describeComfyStatus(state.comfy).hint || 'Ein Klick startet die Berechnung mit deinen Einstellungen.';
  if(regionEditor.blocked)$('start-hint').textContent=regionEditor.hint;
  if(resources.freeing)$('start-hint').textContent='Bitte warten, bis die Freigabe der Bildmodelle angefordert wurde.';
  if(languageStateReason())$('start-hint').textContent=languageStateReason();
  $('refresh-image-models').disabled=!state.ready || state.imageModelsBusy || state.modelChecking || uploading || state.starting;
  $('resolve-request').hidden=!pending();$('resolve-request').disabled=state.starting || state.resolving;
  $('resolve-request').textContent=state.resolving?'Startbeleg wird geklärt …':'Startbeleg klären';
  const hasModel=Boolean(selectedModel()),hasInstance=Boolean(selectedInstance());
  const modelPending=state.modelBusy || state.modelRefreshing || state.modelSaving || state.proposing || state.languageState.busy;
  const languageBlocked=Boolean(imageBusyReason()) || resources.freeing || state.proposing || Boolean(languageStateReason());
  $('load-model').disabled=!hasModel || hasInstance || modelPending || languageBlocked;
  $('unload-model').disabled=!unloadInstance() || modelPending || Boolean(imageBusyReason()) || resources.freeing || state.proposing || state.languageState.busy;
  for(const id of ['load-model','propose'])$(id).title=imageBusyReason() || languageStateReason() || (resources.freeing?'Bildmodelle werden freigegeben. Bitte warten.':'');
  $('unload-model').textContent=state.languageState.uncertain_instances.length?'Unbestätigtes Sprachmodell freigeben':'Freigeben';
  $('unload-model').title=imageBusyReason() || (state.languageState.busy?'Eine Sprachmodellaktion läuft. Bitte warten.':resources.freeing?'Bildmodelle werden freigegeben. Bitte warten.':state.languageState.uncertain_instances.length?'Gezielt freigeben: '+unloadInstance():'');
  $('model').disabled=selectionBlocked(); $('instance').disabled=selectionBlocked();
  $('refresh-models').disabled=modelPending;
  $('settings-open').disabled=selectionBlocked();
  $('propose').disabled=!hasInstance || proposalBlocked() || !$('instruction').value.trim() || !state.ready;
  $('propose').textContent=state.proposing?'Vorschlag wird erstellt …':'✦ Vorschlag erstellen';
  if(state.proposal)for(const [index,button] of [...$('proposal-steps').querySelectorAll('button')].entries())button.disabled=proposalBlocked() || state.proposal.applied.has(index);
  const job=state.jobs.find(item=>item.id===state.selected);
  $('cancel').hidden=!job || !['queued','running','unknown'].includes(job.state);
  $('cancel').disabled=Boolean(job?.cancel_requested);
  drawImageHistory();
}
function drawWorkflows(){
  const icons={sdxl:'▧',kontext:'◈',reactor:'◎',wan:'▷',qwen21:'✧',krea2:'◈'};
  const captions={sdxl:'SDXL oder SD 1.5 auswählen',kontext:'Ein Bild gezielt verändern',reactor:'Zwei Bilder verbinden',wan:'Ein Bild in Bewegung bringen',qwen21:'Mit Qwen / Noct Q gestalten',krea2:'Mit KREA 2 / SNOFS bearbeiten'};
  $('workflows').replaceChildren();
  for(const workflow of state.workflows){
    const button=document.createElement('button');button.type='button';button.className='workflow-card'+(state.workflow?.id===workflow.id?' active':'');button.setAttribute('aria-pressed',state.workflow?.id===workflow.id);
    const icon=document.createElement('span');icon.className='card-icon';icon.textContent=icons[workflow.id];icon.setAttribute('aria-hidden','true');
    const copy=document.createElement('span');const title=document.createElement('strong');title.textContent=workflow.name;const small=document.createElement('small');small.textContent=captions[workflow.id];copy.append(title,small);button.append(icon,copy);
    button.addEventListener('click',()=>chooseWorkflow(workflow));$('workflows').append(button);
  }
}
function drawModelIssues(){
  $('workflow-issues').hidden=!state.modelIssues.length;
  $('workflow-issues').textContent=state.modelIssues.map(issue=>[issue.message || 'Modelldatei fehlt',issue.path].filter(Boolean).join('\n')).join('\n\n');
}
function drawWorkflowModels(dependencies=[]){
  $('workflow-models').replaceChildren();
  $('workflow-model-details').hidden=!dependencies.length;
  for(const item of dependencies){
    const row=document.createElement('div');row.className='model-file';
    const name=document.createElement('strong');name.textContent=[item.role,item.name].filter(Boolean).join(' · ');
    const path=document.createElement('small');path.textContent=item.path;
    row.append(name,path);$('workflow-models').append(row);
  }
}
async function checkImageModels(){
  const workflow=state.workflow,generation=state.generation,check=++state.modelCheck;
  state.modelChecking=true;drawWorkflowModels();updateActions();
  try{
    const result=await request('/api/workflows/'+encodeURIComponent(workflow.id)+'/check',{method:'POST',body:{controls:modelSelections($('workflow-form'),workflow)}});
    if(check!==state.modelCheck || generation!==state.generation)return;
    state.modelIssues=result.issues;drawModelIssues();drawWorkflowModels(result.dependencies);
  }catch(error){if(check===state.modelCheck && generation===state.generation){state.modelIssues=[{message:error.message}];drawModelIssues();}}
  finally{if(check===state.modelCheck && generation===state.generation){state.modelChecking=false;updateActions();}}
}
function chooseWorkflow(workflow,restore,projectContext=null){
  if(restore)workflow={...workflow,controls:Object.fromEntries(Object.entries(workflow.controls).map(([name,spec])=>[name,{...spec,default:Object.hasOwn(restore.controls,name)?restore.controls[name]:spec.default}]))};
  state.workflow=workflow;state.generation++;state.modelCheck++;state.modelChecking=false;state.modelIssues=workflow.issues;state.images=restore?.images || {};clearProposal();drawWorkflows();
  state.inputRevision++;state.projectSave=null;state.projectError='';state.projectContext=projectContext;
  $('workflow-title').textContent=workflow.name;$('workflow-description').textContent=workflow.description;
  drawModelIssues();drawWorkflowModels(workflow.dependencies);
  renderControls($('controls'),workflow,event=>{clearProposal();if(workflow.controls[event?.target?.name]?.kind==='model')return checkImageModels();updateActions();},state.expert);
  $('image-roles').replaceChildren();
  for(const role of workflow.roles){
    const slot=document.createElement('div');slot.className='image-slot';const title=document.createElement('strong');title.textContent=role.label;
    const picker=document.createElement('label');picker.className='upload-label';const text=document.createElement('span');text.textContent='+ Bild auswählen';
    const file=document.createElement('input');file.type='file';file.accept='image/png,image/jpeg,image/webp';file.setAttribute('aria-label',role.label+' auswählen');picker.append(text,file);
    const preview=document.createElement('img');preview.hidden=true;preview.alt=role.label;const name=document.createElement('span');name.className='image-name';name.textContent='PNG, JPEG oder WebP · bis 64 MiB';
    const hint=document.createElement('span');hint.className='drop-hint';hint.textContent='Ein Bild hierher ziehen oder über „Bild auswählen“ zuordnen.';
    const errorText=document.createElement('p');errorText.className='error-text';errorText.id='upload-error-'+role.id;errorText.hidden=true;errorText.setAttribute('role','alert');file.setAttribute('aria-describedby',errorText.id);
    if(state.images[role.id]){preview.src=state.images[role.id].url;preview.hidden=false;name.textContent=state.images[role.id].name;text.textContent='Anderes Bild auswählen';}
    const generation=state.generation;let currentUpload;
    const current=()=>state.workflow===workflow && state.generation===generation;
    const showUploadError=message=>{if(!current())return;errorText.textContent=message;errorText.hidden=false;fail(new Error(role.label+': '+message));};
    const uploadImage=async chosen=>{
      if(!chosen || !current())return;
      if(!['image/png','image/jpeg','image/webp'].includes(chosen.type) && !(chosen.type==='' && /\.(png|jpe?g|webp)$/i.test(chosen.name))){showUploadError('Bitte ein PNG-, JPEG- oder WebP-Bild auswählen.');return;}
      if(chosen.size>64*1024**2){showUploadError('Ein Bild darf höchstens 64 MiB groß sein.');return;}
      if(currentUpload)state.uploads.delete(currentUpload);
      if(role.id===primaryRole(workflow)){state.inputRevision++;state.projectSave=null;state.projectError='';state.projectContext=null;}
      const upload={generation,role:role.id};currentUpload=upload;state.uploads.add(upload);delete state.images[role.id];preview.hidden=true;name.textContent=chosen.name;errorText.hidden=true;file.disabled=true;text.textContent='Bild wird übernommen …';clearProposal();updateActions();
      try{const body=new FormData();body.append('file',chosen);const image=await request('/api/uploads',{method:'POST',body});
        if(!current() || currentUpload!==upload)return;
        state.images[role.id]=image;preview.src=image.url;preview.hidden=false;name.textContent=image.name;text.textContent='Anderes Bild auswählen';clearProposal();
        if(role.id===primaryRole(workflow))await saveOriginal(image,role.id);
      }catch(error){if(current() && currentUpload===upload){showUploadError(error.message || 'Das Bild konnte nicht übernommen werden. Bitte erneut auswählen.');text.textContent='+ Bild auswählen';}}
      finally{state.uploads.delete(upload);if(currentUpload===upload){file.disabled=false;file.value='';}updateActions();}
    };
    file.addEventListener('change',()=>uploadImage(file.files?.[0]));
    slot.addEventListener('dragover',event=>{event.preventDefault();if(event.dataTransfer)event.dataTransfer.dropEffect='copy';slot.classList.add('drag-over');});
    slot.addEventListener('dragleave',()=>slot.classList.remove('drag-over'));
    slot.addEventListener('drop',event=>{
      event.preventDefault();event.stopPropagation();slot.classList.remove('drag-over');
      const files=Array.from(event.dataTransfer?.files || []);
      if(files.length!==1){showUploadError('Bitte genau ein Bild in diese Bildrolle ziehen.');return;}
      return uploadImage(files[0]);
    });
    slot.append(title,picker,preview,name,hint,errorText);$('image-roles').append(slot);
  }
  updateActions();
}
function drawImageLibrary(){
  $('image-model-files').replaceChildren();
  const kinds={checkpoint:'Bildmodell mit Textencoder und Decoder',diffusion_model:'Bild-/Videomodell · benötigt passende Komponenten',text_encoder:'Textencoder · Zusatzkomponente',vae:'Bilddecoder (VAE) · Zusatzkomponente',lora:'LoRA · Zusatzmodell, noch kein LoRA-Werkzeug',unknown:'Modelltyp noch nicht zugeordnet',invalid:'Datei nicht verwendbar'};
  for(const item of state.imageModels){
    const line=document.createElement('div');line.className='model-file';const title=document.createElement('strong');title.textContent=item.name;
    const text=document.createElement('p');text.textContent=kinds[item.kind] || item.kind;
    const use=Array.isArray(item.used_by) ? item.used_by.length ? 'Werkzeug: ' + item.used_by.map(tool=>tool.name).join(', ') : 'Derzeit von keinem der sechs Werkzeuge verwendet.' : '';
    const path=document.createElement('small');path.textContent=[use,item.path,item.reason,item.aliases?.length?'Zusätzlicher Dateiverweis auf dieselben Gewichte, keine zweite Modellkopie.':''].filter(Boolean).join('\n');
    line.append(title,text,path);$('image-model-files').append(line);
  }
  $('image-model-count').textContent=state.imageModels.length+' Modelldateien';
}
async function refreshImageModels(){
  if(state.imageModelsBusy)return;
  const workflow=state.workflow;
  state.imageModelsBusy=true;updateActions();
  try{
    const [workflows,models]=await Promise.all([request('/api/workflows'),request('/api/image-models')]);
    state.workflows=workflows;state.imageModels=models;drawImageLibrary();
    if(state.workflow===workflow){
      if([...state.uploads].some(upload=>upload.generation===state.generation)){
        drawWorkflows();feedback('Die Modellliste ist aktualisiert. Das Formular bleibt während der Bildübernahme erhalten. Aktualisiere danach erneut, um neue Modelloptionen zu übernehmen.');
      }else{
        const restore={controls:controlValues($('workflow-form'),workflow),images:state.images};
        const context=currentProjectContext(),originalError=state.projectError;
        chooseWorkflow(workflows.find(item=>item.id===workflow.id),restore,context);state.projectError=originalError;await checkImageModels();
      }
    }else drawWorkflows();
  }catch(error){fail(error);}finally{state.imageModelsBusy=false;updateActions();}
}
function drawModels(){
  const desired=state.settings.model_key;$('model').replaceChildren();
  const first=document.createElement('option');first.value='';first.textContent=state.models.length?'Sprachmodell auswählen':'Kein Sprachmodell erreichbar';$('model').append(first);
  for(const model of state.models){const option=document.createElement('option');option.value=model.key;option.textContent=model.name;$('model').append(option);}
  if(state.models.some(model=>model.key===desired))$('model').value=desired;
  drawInstances();
}
function drawInstances(){
  const model=selectedModel();const instances=model?.loaded_instances || [];$('instance').replaceChildren();
  for(const instance of instances){const option=document.createElement('option');option.value=instance.id;option.textContent=instance.id;$('instance').append(option);}
  if(instances.some(instance=>instance.id===state.settings.instance_id))$('instance').value=state.settings.instance_id;
  $('instance').hidden=instances.length<2;$('instance-label').hidden=instances.length<2;
  $('model-info').textContent=languageStateReason() || (instances.length?'Bereit für Vorschläge. Modellfähigkeiten werden bei der Anfrage geprüft.':model?'Noch nicht geladen. Lade das Modell, wenn du einen Vorschlag möchtest.':'Ollama starten, dann die Modellliste aktualisieren.');
  updateActions();
}
async function refreshModels(allowBusy=false){
  if(state.modelSaving || state.modelRefreshing || state.proposing || (state.languageState.busy || state.modelBusy) && allowBusy!==true)return;
  const before=selectedInstance(),model=$('model').value;
  state.modelRefreshing=true;$('refresh-models').disabled=true;updateActions();
  try{state.models=await request('/api/models');drawModels();}
  catch(error){state.models=[];drawModels();$('model-info').textContent=languageStateReason() || error.message;}
  finally{if(before!==selectedInstance() || model!==$('model').value)clearProposal();state.modelRefreshing=false;$('refresh-models').disabled=false;updateActions();}
}
async function saveSelection(redraw=true){
  if(selectionBlocked())return;
  clearProposal();if(redraw)drawInstances();
  const body={model_key:$('model').value,instance_id:selectedInstance()};
  state.modelSaving=true;updateActions();
  try{state.settings=await request('/api/settings',{method:'POST',body});}
  finally{state.modelSaving=false;updateActions();}
}
function drawJobs(){
  $('history').replaceChildren();
  if(!state.jobs.length){const empty=document.createElement('p');empty.className='muted';empty.textContent='Noch keine Aufträge.';$('history').append(empty);}
  for(const job of state.jobs){
    const button=document.createElement('button');button.className='history-item'+(job.id===state.selected?' selected':'');
    const title=document.createElement('span');title.textContent=state.workflows.find(w=>w.id===job.workflow_id)?.name || 'Auftrag';
    const detail=document.createElement('small');const date=new Date(job.created_at);detail.textContent=`${labels[job.state] || job.state} · ${date.toLocaleString('de-DE',{day:'2-digit',month:'2-digit',hour:'2-digit',minute:'2-digit'})}`;
    button.append(title,detail);button.addEventListener('click',()=>{state.selected=job.id;drawJobs();});$('history').append(button);
  }
  renderJob($('result'),state.jobs.find(job=>job.id===state.selected),{onProject:projectFromOutput,onRefresh:refreshVersionedJob});updateActions();
}
function rememberJob(job){
  const index=state.jobs.findIndex(item=>item.id===job.id);if(index<0)state.jobs.unshift(job);else state.jobs[index]=job;
  if(!ACTIVE.has(job.state))finishRequest(localStorage,job.request_id);
}
async function refreshJobs(){
  if(state.polling)return;state.polling=true;
  try{
    const selectInitially=!state.selected;
    state.jobs=await request('/api/jobs');
    if(!state.selected)state.selected=state.jobs.find(job=>ACTIVE.has(job.state))?.id || state.jobs[0]?.id;
    const listedSelection=state.selected;
    drawJobs();
    const pendingId=pending()?.request_id;
    if(pendingId && !state.jobs.some(job=>job.request_id===pendingId)){
      const receipt=await request('/api/requests/'+encodeURIComponent(pendingId));if(receipt)rememberJob(receipt);
      if(!state.selected || selectInitially && state.selected===listedSelection)state.selected=receipt?.id || state.selected;
      drawJobs();
    }
    for(const job of [...state.jobs]){
      if(ACTIVE.has(job.state) || job.state==='completed' && job.versioning_error){rememberJob(await request('/api/jobs/'+encodeURIComponent(job.id)));drawJobs();}
      else finishRequest(localStorage,job.request_id);
    }
    if(!state.selected)state.selected=state.jobs.find(job=>ACTIVE.has(job.state))?.id || state.jobs[0]?.id;
    drawJobs();
    await refreshProjectAfterJobs();
  }catch(error){fail(error);}
  finally{state.polling=false;updateActions();await refreshServiceStatus();}
}
$('workflow-form').addEventListener('submit',async event=>{
  event.preventDefault();if($('start').disabled || state.modelBusy || state.proposing || resources.freeing || languageStateReason() || !$('workflow-form').reportValidity())return;
  const body={workflow_id:state.workflow.id,controls:controlValues($('workflow-form'),state.workflow),images:Object.fromEntries(Object.entries(state.images).map(([role,image])=>[role,image.id]))};
  const context=currentProjectContext();if(context){body.project_id=context.project_id;body.parent_version_id=context.parent_version_id;}
  if(regionEditor.request)body.edit_region=regionEditor.request;
  state.starting=true;updateActions();
  try{const job=await startRequest(body);rememberJob(job);state.selected=job.id;drawJobs();feedback(job.error || 'Auftrag übergeben.',Boolean(job.error));await refreshProjectAfterJobs();}
  catch(error){fail(error);await refreshJobs();}
  finally{state.starting=false;updateActions();await refreshServiceStatus();}
});
$('instruction').addEventListener('input',()=>{clearProposal();updateActions();});
function drawProposal(){
  const proposal=state.proposal;if(!proposal)return;
  renderProposals($('proposal-steps'),proposal,state.workflows,state.workflow,state.images,applyProposalStep,document,proposal.applied);
  $('proposal').hidden=false;updateActions();
}
async function applyProposalStep(index){
  const proposal=state.proposal;
  if(!proposal)return;
  if(!proposalCurrent(proposal.context)){clearProposal();feedback('Die Auswahl wurde inzwischen geändert. Bitte einen neuen Vorschlag erstellen.');return;}
  if(proposalBlocked() || proposal.applied.has(index))return;
  const step=proposal.steps[index];if(!step)return;
  try{
    const prepared=prepareProposalStep(step,state.workflows,state.workflow,controlValues($('workflow-form'),state.workflow),state.images);
    if(prepared.changedTool)chooseWorkflow(prepared.workflow,{controls:prepared.controls,images:prepared.images});
    else{fillControls($('workflow-form'),prepared.controls,state.workflow);clearProposal();}
    proposal.applied.add(index);proposal.context=proposalContext();state.proposal=proposal;drawProposal();
    if(prepared.changedTool)await checkImageModels();
    feedback(prepared.changedTool && prepared.workflow.roles.length ? 'Schritt übernommen. Wähle die benötigten Bilder und prüfe die Einstellungen. Die Berechnung startest du anschließend selbst.' : 'Schritt übernommen. Prüfe die Einstellungen und starte die Berechnung selbst.');
  }catch(error){fail(error);}
  updateActions();
}
$('propose').addEventListener('click',async()=>{
  if($('propose').disabled || proposalBlocked())return;
  const context=proposalContext(),workflow=state.workflow;
  const original=Object.freeze({instruction:$('instruction').value,workflow_id:workflow.id,
    controls:Object.freeze({...controlValues($('workflow-form'),workflow)}),
    workflow_defaults:Object.freeze(Object.fromEntries(state.workflows.map(item=>[item.id,Object.freeze(Object.fromEntries(Object.entries(item.controls).map(([name,spec])=>[name,spec.default])))])))});
  state.proposing=true;updateActions();
  try{
    const proposal=await request('/api/tool-proposals',{method:'POST',body:{instance_id:context.instance,workflow_id:workflow.id,instruction:original.instruction,controls:original.controls}});
    if(!proposalCurrent(context)){feedback('Die Einstellungen wurden inzwischen geändert. Der alte Vorschlag wird nicht übernommen.');return;}
    state.proposal={...proposal,original,context,applied:new Set()};drawProposal();
  }catch(error){fail(error);}finally{await refreshServiceStatus();state.proposing=false;updateActions();}
});
$('refresh-image-models').addEventListener('click',refreshImageModels);
$('model').addEventListener('change',()=>saveSelection().catch(fail));
$('instance').addEventListener('change',()=>saveSelection(false).catch(fail));
$('refresh-models').addEventListener('click',refreshModels);
for(const action of ['load','unload'])$(''+action+'-model').addEventListener('click',async()=>{
  if($(''+action+'-model').disabled || imageBusyReason() || resources.freeing || state.proposing || state.languageState.busy || action==='load' && languageStateReason())return;
  const instance=unloadInstance();
  state.modelBusy=true;clearProposal();updateActions();
  try{await request('/api/models/'+action,{method:'POST',body:action==='load'?{model_key:$('model').value}:{instance_id:instance}});state.settings=await request('/api/settings');await refreshModels(true);feedback(action==='load'?'Sprachmodell geladen.':'Sprachmodell freigegeben.');}
  catch(error){fail(error);}finally{await refreshServiceStatus();state.modelBusy=false;updateActions();}
});
$('cancel').addEventListener('click',async()=>{
  $('cancel').disabled=true;
  try{const job=await request('/api/jobs/'+encodeURIComponent(state.selected)+'/cancel',{method:'POST',body:{}});rememberJob(job);drawJobs();feedback(job.cancel_message || 'Zustand wird geprüft.');}
  catch(error){fail(error);updateActions();}
});
$('refresh-jobs').addEventListener('click',refreshJobs);
$('resolve-request').addEventListener('click',async()=>{
  const requestId=pending()?.request_id;if(!requestId || state.starting || state.resolving)return;
  state.resolving=true;updateActions();
  try{const job=await request('/api/requests/'+encodeURIComponent(requestId)+'/resolve',{method:'POST',body:{}});rememberJob(job);state.selected=job.id;drawJobs();feedback(job.error_code==='request_not_received'?'Der Start ist nicht eingegangen und wurde sicher abgeschlossen. Du kannst jetzt neu starten.':'Der gespeicherte Auftrag wurde gefunden. Sein tatsächlicher Zustand wird angezeigt.');}
  catch(error){fail(error);}finally{state.resolving=false;updateActions();}
});
$('settings-open').addEventListener('click',async()=>{
  if(selectionBlocked())return;
  try{const settings=await request('/api/settings');if(selectionBlocked())return;state.settings=settings;$('endpoint').value=state.settings.endpoint;$('token').value='';$('remove-token').checked=false;$('token-info').textContent=state.settings.has_token?'Ein Zugangsschlüssel ist geschützt gespeichert.':'Es ist kein Zugangsschlüssel gespeichert.';$('settings-error').hidden=true;$('settings-dialog').showModal();}
  catch(error){fail(error);}
});
$('settings-close').addEventListener('click',()=>$('settings-dialog').close());
$('settings-form').addEventListener('submit',async event=>{
  event.preventDefault();if(selectionBlocked())return;const body={endpoint:$('endpoint').value};if($('remove-token').checked)body.token='';else if($('token').value)body.token=$('token').value;
  try{state.settings=await request('/api/settings',{method:'POST',body});$('token').value='';$('settings-dialog').close();clearProposal();await refreshModels();feedback('Verbindung gespeichert.');}
  catch(error){$('settings-error').textContent=error.message;$('settings-error').hidden=false;}
});
async function boot(){
  renderJob($('result'),null);updateActions();
  void resources.refresh();
  try{
    const [workflows,settings,status,imageModels]=await Promise.all([request('/api/workflows'),request('/api/settings'),request('/api/status'),request('/api/image-models')]);
    state.workflows=workflows;state.imageModels=imageModels;state.settings=settings;state.ready=true;drawImageLibrary();chooseWorkflow(workflows[0]);
    $('storage-info').textContent=`${status.project_root} · ${(status.free_bytes/1024**3).toFixed(1)} GB frei`;
    showServiceStatus(status.comfy,status.language_state);
    await Promise.all([refreshModels(),refreshJobs(),refreshImageProjects()]);
  }catch(error){fail(error);}
}
$('expert-mode').addEventListener('change',()=>setExpertMode($('expert-mode').checked));
$('refresh-projects').addEventListener('click',refreshImageProjects);
$('save-original').addEventListener('click',()=>{const role=primaryRole(),image=state.images[role];if(image && !state.projectSave)return saveOriginal(image,role);});
setExpertMode(false);
setInterval(()=>{if(state.jobs.some(job=>ACTIVE.has(job.state)) || pending() || state.languageState.busy || state.languageState.uncertain_instances.length)return refreshJobs();},4000);
boot();
