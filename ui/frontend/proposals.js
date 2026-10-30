export function prepareProposalStep(step,workflows,currentWorkflow,currentControls,currentImages) {
  const workflow=workflows.find(item=>item.id===step.workflow_id);
  if(!workflow)throw new Error('Das vorgeschlagene Werkzeug ist nicht mehr verfügbar. Bitte einen neuen Vorschlag erstellen.');
  const changedTool=workflow.id!==currentWorkflow.id;
  const controls=changedTool ? Object.fromEntries(Object.entries(workflow.controls).map(([name,spec])=>[name,spec.default])) : {...currentControls};
  for(const [name,value] of Object.entries(step.controls || {})) {
    if(workflow.controls[name] && workflow.controls[name].kind!=='model' && name!=='prompt')controls[name]=value;
  }
  if(Object.hasOwn(workflow.controls,'prompt'))controls.prompt=step.prompt;
  return {workflow,controls,images:changedTool ? {} : currentImages,changedTool};
}

export function renderProposals(container,proposal,workflows,currentWorkflow,images,onApply,documentRef=globalThis.document,applied=new Set()) {
  const make=(tag,text,className)=>{
    const node=documentRef.createElement(tag);
    if(text!==undefined)node.textContent=text;
    if(className)node.className=className;
    return node;
  };
  container.replaceChildren();
  const display=value=>value===undefined || value===null ? 'Nicht gesetzt' : typeof value==='number' ? value.toLocaleString('de-DE',{maximumFractionDigits:8,useGrouping:false}) : String(value);
  const original=proposal.original;
  if(original){
    const section=make('section',undefined,'proposal-original');
    section.append(make('h3','Dein ursprünglicher Auftrag'),make('p',original.instruction));
    const source=workflows.find(item=>item.id===original.workflow_id);
    section.append(make('h4',`Formular bei der Anfrage${source ? ' · '+source.name : ''}`));
    const values=make('dl',undefined,'proposal-original-controls');
    for(const [name,value] of Object.entries(original.controls)){
      const spec=source?.controls[name];
      if(!spec || spec.kind==='model')continue;
      values.append(make('dt',spec.label),make('dd',display(value)));
    }
    if(values.children.length)section.append(values);
    container.append(section);
  }
  const response=make('section',undefined,'proposal-response');
  response.append(make('h3','Antwort des Prompt-Assistenten'),make('p',proposal.assistant_text));
  container.append(response);
  proposal.steps.forEach((step,index)=>{
    const workflow=workflows.find(item=>item.id===step.workflow_id);
    if(!workflow)return;
    const card=make('article',undefined,'proposal-step');
    card.append(make('p',`SCHRITT ${index+1}`,'eyebrow'),make('h3',workflow.name),make('p',step.reason,'proposal-reason'));
    if(workflow.controls.prompt){
      const prompt=make('section',undefined,'proposal-prompt');
      prompt.append(make('strong','Vorgeschlagener Bild-/Videoprompt'),make('p',step.prompt));
      if(original && step.prompt.trim()===original.instruction.trim()){
        prompt.append(make('p','Das Sprachmodell hat deinen Auftrag wortgleich als Prompt zurückgegeben.','muted small'));
      }
      card.append(prompt);
    }
    const baseline=original?.workflow_id===workflow.id ? original.controls : original?.workflow_defaults?.[workflow.id] || Object.fromEntries(Object.entries(workflow.controls).map(([name,spec])=>[name,spec.default]));
    const proposed={...(workflow.controls.prompt ? {prompt:step.prompt} : {}),...Object.fromEntries(Object.entries(step.controls || {}).filter(([name])=>name!=='prompt'))};
    const values=make('dl',undefined,'proposal-changes');
    for(const [name,value] of Object.entries(proposed)) {
      const spec=workflow.controls[name];
      if(!spec || spec.kind==='model' || Object.is(value,baseline[name]))continue;
      const pair=make('dd');
      pair.append(make('span',`Vorher: ${display(baseline[name])}`,'proposal-before'),make('span',`Nachher: ${display(value)}`,'proposal-after'));
      values.append(make('dt',spec.label),pair);
    }
    if(values.children.length)card.append(make('h4','Vorgeschlagene Änderungen'),values);
    else card.append(make('p','Dieser Schritt ändert keine Formularwerte.','muted small'));
    const missing=workflow.roles.filter(role=>workflow.id!==currentWorkflow.id || !images[role.id]?.id);
    card.append(make('p',missing.length ? `Bitte auswählen: ${missing.map(role=>role.label).join(' und ')}.` : workflow.roles.length ? 'Benötigte Bilder sind ausgewählt.' : 'Für dieses Werkzeug brauchst du kein Eingabebild.','proposal-requirements'));
    if(workflow.id!==currentWorkflow.id)card.append(make('p','Beim Übernehmen öffnet sich das Werkzeug mit seinen Grundeinstellungen. Wähle die Bilder danach passend zu den Bildfeldern aus.','muted small'));
    card.append(make('p',workflow.issues?.length ? `Modellhinweis: ${workflow.issues.map(issue=>issue.message || 'Eine Modelldatei fehlt.').join(' ')}` : 'Modellzuordnung vorhanden. Die Startbereitschaft wird im Formular geprüft.',workflow.issues?.length ? 'proposal-availability warning' : 'proposal-availability muted'));
    const button=make('button',applied.has(index) ? 'Schritt ins Formular übernommen' : 'Diesen Schritt übernehmen','secondary full');
    button.type='button';button.disabled=applied.has(index);
    button.addEventListener('click',()=>{if(!applied.has(index))return onApply(index);});card.append(button);container.append(card);
  });
}
