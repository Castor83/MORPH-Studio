export const ACTIVE = new Set(['preparing','submitting','queued','running','unknown']);
export const labels = {preparing:'Wird vorbereitet',submitting:'Wird übergeben',queued:'Wartet auf Berechnung',running:'Berechnung läuft',completed:'Fertig',cancelled:'Abgebrochen',error:'Fehler',unknown:'Status noch unklar'};

export function describeComfyStatus(comfy={}) {
  if (comfy.ready === true) return {label:'Rechendienst bereit',hint:'',warning:false};
  if (comfy.ownership === 'free') return {label:'Startet bei Berechnung',hint:'',warning:false};
  const message=typeof comfy.message==='string' ? comfy.message : '';
  if (comfy.ownership === 'owned' || comfy.ownership === 'compatible') return {label:'Rechendienst noch nicht bereit',hint:message || 'Der Rechendienst startet oder wird noch geprüft. Beim nächsten Start wird die Verbindung erneut geprüft.',warning:true};
  if (comfy.ownership === 'foreign') return {label:'Rechendienst nicht nutzbar',hint:message || 'An Port 8188 wurde kein kompatibler ComfyUI-Dienst erkannt. Bitte den Rechendienst prüfen.',warning:true};
  return {label:'Rechendienst ungeklärt',hint:message || 'Der Rechendienst konnte nicht geprüft werden. Beim nächsten Start wird die Verbindung erneut geprüft.',warning:true};
}

export function renderProjectList(container,projects,selected,onOpen,doc=globalThis.document){
  container.replaceChildren();
  if(!projects.length){const text=doc.createElement('p');text.className='muted';text.textContent='Noch keine Bildprojekte. Wähle ein Ausgangsbild oder sichere ein fertiges Bild als neues Projekt.';container.append(text);}
  for(const project of projects){const button=doc.createElement('button');button.type='button';button.className='quiet small'+(project.id===selected?' selected':'');button.textContent=project.name || 'Bildprojekt';button.setAttribute('aria-pressed',String(project.id===selected));button.addEventListener('click',()=>onOpen(project.id));container.append(button);}
}

export function versionLabel(project,versionId){
  if(project?.original_version_id===versionId)return 'Original';
  const index=(project?.versions || []).filter(version=>version.id!==project.original_version_id).findIndex(version=>version.id===versionId);
  return index<0?'Gewählte Version':'Version '+(index+1);
}

export function renderVersionTree(container,project,onUse,busy=false,doc=globalThis.document,expert=false){
  container.replaceChildren();if(!project)return;
  const heading=doc.createElement('h3');heading.textContent=project.name || 'Bildprojekt';container.append(heading);
  const versions=project.versions || [],seen=new Set();
  const names=new Map(versions.map(version=>[version.id,versionLabel(project,version.id)]));
  const list=doc.createElement('ul');list.className='version-tree';
  const appendVersion=(version,parent)=>{
    if(seen.has(version.id))return;seen.add(version.id);
    const item=doc.createElement('li'),card=doc.createElement('article');card.className='version-card';card.dataset.versionId=version.id;
    const title=doc.createElement('h4');title.textContent=names.get(version.id);card.append(title);
    const lineage=doc.createElement('p');lineage.className='muted small';lineage.textContent=version.parent_version_id?'Abzweig von '+(names.get(version.parent_version_id) || 'gewählter Ausgangsversion'):'Unverändertes Original';card.append(lineage);
    if(version.media){const image=doc.createElement('img');image.src=version.media.url;image.alt=version.media.name;image.loading='lazy';card.append(image);const download=doc.createElement('a');download.href=version.media.url+'?download=1';download.className='text-link';download.textContent='Speichern / Exportieren';card.append(download);}
    if(version.metadata?.prompt){const prompt=doc.createElement('p');prompt.className='version-prompt';prompt.textContent=version.metadata.prompt;card.append(prompt);}
    const actions=doc.createElement('div');actions.className='version-actions';
    for(const label of ['Weiterbearbeiten','Variante erstellen',...(version.id===project.original_version_id?['Original verwenden']:[]),'Vergleichen']){const button=doc.createElement('button');button.type='button';button.className='quiet small';button.textContent=label;button.disabled=label==='Vergleichen'?false:busy;button.addEventListener('click',()=>onUse(version,label));actions.append(button);}card.append(actions);
    const details=doc.createElement('details'),summary=doc.createElement('summary'),pre=doc.createElement('pre');details.hidden=!expert;summary.textContent='Versionsbeleg';pre.textContent=JSON.stringify({id:version.id,parent_version_id:version.parent_version_id,created_at:version.created_at,status:version.status,sha256:version.sha256,metadata:version.metadata},null,2);details.append(summary,pre);card.append(details);
    item.append(card);parent.append(item);const children=versions.filter(candidate=>candidate.parent_version_id===version.id);if(children.length){const branch=doc.createElement('ul');branch.className='version-tree';item.append(branch);for(const child of children)appendVersion(child,branch);}
  };
  for(const version of versions.filter(version=>!version.parent_version_id))appendVersion(version,list);
  for(const version of versions)if(!seen.has(version.id))appendVersion(version,list);
  container.append(list);
}

function renderJobProgress(container,job){
  if(!ACTIVE.has(job.state))return;
  const block=document.createElement('section');block.className='job-progress';block.setAttribute('aria-live','polite');
  const append=(text,className='')=>{const line=document.createElement('p');line.className=className;line.textContent=text;block.append(line);};
  const phases={connecting:'Rechendienst wird verbunden und bei Bedarf gestartet.',checking:'Workflow wird geprüft.',uploading:'Eingabebilder werden übertragen.',submitting:'Auftrag wird an den Rechendienst übergeben.'};
  if(job.state==='preparing' || job.state==='submitting')append(phases[job.phase] || (job.state==='submitting'?phases.submitting:'Der Auftrag wird vorbereitet.'));
  else if(job.state==='queued')append('Der Auftrag wartet auf die Berechnung.');
  const progress=job.progress;
  if(progress && (job.state==='running' || job.state==='unknown')){
    const disconnected=['reconnecting','unavailable','closed'].includes(progress.connection);
    if(disconnected)append('Letzte Fortschrittsmeldung · Liveverbindung unterbrochen. Status wird geprüft.','job-progress-source muted');
    else if(progress.connection==='connecting')append('Die Liveverbindung wird aufgebaut. Status wird geprüft.','job-progress-source muted');
    const nodeId=typeof progress.node_id==='string' && progress.node_id.trim() ? progress.node_id : typeof progress.node_id==='number' && Number.isFinite(progress.node_id) ? String(progress.node_id) : '';
    const nodeType=typeof progress.node_type==='string' ? progress.node_type : '';
    const node=nodeId?(nodeType?nodeType+' (Knoten '+nodeId+')':'Knoten '+nodeId):'';
    if(['executing','progress'].includes(progress.event) && node){
      const modelLoader=/(?:checkpoint|unet|diffusion|clip|vae|lora|model).*loader|loader.*(?:checkpoint|unet|diffusion|clip|vae|lora|model)/i.test(nodeType);
      append((modelLoader?(disconnected?'Zuletzt gemeldeter Modellknoten: ':'Modellknoten wird ausgeführt: '):(disconnected?'Zuletzt gemeldeter Knoten: ':'Aktueller Knoten: '))+node+'.');
      const {value,max}=progress;
      if(progress.event==='progress' && Number.isFinite(value) && Number.isFinite(max) && max>0 && value>=0 && value<=max){
        const percent=Math.round(value/max*1000)/10;
        append('Knotenfortschritt: '+percent.toLocaleString('de-DE')+' %','job-progress-label');
        const bar=document.createElement('progress');bar.max=max;bar.value=value;bar.setAttribute('aria-label','Knotenfortschritt');block.append(bar);
        append('Schritt '+value+' von '+max+' im aktuellen Knoten.','muted');
      }
    }else if(progress.event==='execution_cached' && Array.isArray(progress.cached_nodes))append(progress.cached_nodes.length+' Knoten aus dem Zwischenspeicher übernommen.','muted');
    else if(progress.event==='execution_success')append('Der Rechendienst meldet das Ende der Ausführung. Status wird geprüft.');
    else if(progress.event==='execution_error')append('Der Rechendienst meldet einen Ausführungsfehler. Status wird geprüft.');
    else if(progress.event==='execution_interrupted')append('Der Rechendienst meldet eine Unterbrechung. Status wird geprüft.');
    else if(progress.event==='execution_start')append('Die Ausführung wurde gemeldet. Knotenschritte liegen noch nicht vor.');
  }
  if(!block.children.length && job.state==='running')append('Der Rechendienst bearbeitet den Auftrag. Knotenschritte wurden noch nicht gemeldet.','muted');
  if(block.children.length)container.append(block);
}

export function renderJob(container,job,actions={}) {
  container.replaceChildren();
  if (!job) {
    const empty = document.createElement('div'); empty.className='result-empty';
    const symbol = document.createElement('div'); symbol.className='result-symbol'; symbol.textContent='◈';
    const title = document.createElement('h3'); title.textContent='Platz für deine nächste Idee';
    const text = document.createElement('p'); text.textContent='Wähle einen Workflow, passe die Einstellungen an und starte die Berechnung.';
    empty.append(symbol,title,text); container.append(empty); return;
  }
  const badge=document.createElement('span'); badge.className='status-badge state-'+job.state; badge.textContent=labels[job.state] || job.state;
  container.append(badge);
  renderJobProgress(container,job);
  for(const warning of Array.isArray(job.warnings)?job.warnings:[]){
    if(typeof warning!=='string' || !warning.trim())continue;
    const text=document.createElement('p');text.className='warning';text.textContent='Hinweis: '+warning.trim();container.append(text);
  }
  if (job.cancel_requested && ACTIVE.has(job.state)) {
    const message=document.createElement('p'); message.textContent='Abbruch angefordert. Die Bestätigung steht noch aus.';container.append(message);
  }
  if (job.error) {
    const text=document.createElement('p');text.className='error-text';text.textContent=typeof job.error==='string' ? job.error : job.error.message || 'Bitte den Fehlerbeleg ansehen.';container.append(text);
  }
  if (job.error_code || (job.details !== undefined && job.details !== null && job.details !== '')) {
    const details=document.createElement('details');const summary=document.createElement('summary');summary.textContent='Fehlerdetails';
    const pre=document.createElement('pre');
    const cause=typeof job.details==='string' ? job.details : job.details == null ? '' : JSON.stringify(job.details,null,2);
    pre.textContent=[job.error_code ? 'Fehlercode: '+job.error_code : '',cause].filter(Boolean).join('\n\n');
    details.append(summary,pre);container.append(details);
  }
  if (job.node_errors && Object.keys(job.node_errors).length) {
    const details=document.createElement('details'); const summary=document.createElement('summary');summary.textContent='Hinweise zum Workflow';
    const pre=document.createElement('pre');pre.textContent=JSON.stringify(job.node_errors,null,2);details.append(summary,pre);container.append(details);
  }
  if(job.versioning_error){const text=document.createElement('p');text.className='error-text';text.textContent='Das Bild ist fertig. Die Versionsspeicherung ist noch offen: '+job.versioning_error;container.append(text);if(actions.onRefresh){const retry=document.createElement('button');retry.type='button';retry.className='quiet small';retry.textContent='Versionsspeicherung erneut prüfen';retry.addEventListener('click',()=>actions.onRefresh(job.id));container.append(retry);}}
  for (const file of job.outputs || []) {
    const figure=document.createElement('figure');
    const media=document.createElement(file.kind==='video' ? 'video' : 'img');
    media.src=file.url;
    if (file.kind==='video') {media.controls=true;media.preload='metadata';}
    else {media.alt=file.name;media.loading='lazy';}
    const caption=document.createElement('figcaption');const title=document.createElement('span');title.textContent=file.name;
    const link=document.createElement('a');link.href=file.url+'?download=1';link.textContent='Speichern';link.className='text-link';
    caption.append(title,link);figure.append(media,caption);
    if(file.kind==='image' && !job.project_id && actions.onProject){const button=document.createElement('button');button.type='button';button.className='quiet small';button.textContent='Als neues Bildprojekt sichern';button.addEventListener('click',()=>actions.onProject(file));figure.append(button);}
    container.append(figure);
  }
  if (!(job.outputs || []).length && ACTIVE.has(job.state)) {
    const p=document.createElement('p');p.className='muted';p.textContent=job.state==='unknown' ? 'Die Übergabe wird geprüft. Bitte keinen zweiten Auftrag starten.' : 'Ergebnisse erscheinen hier, sobald sie vorliegen.';container.append(p);
  }
}
