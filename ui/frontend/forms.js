export function requiredImagesPresent(workflow,images) {
  const roles = workflow.roles.map(role=>role.id);
  return Object.keys(images).length === roles.length && roles.every(role=>Boolean(images[role]?.id));
}

export function controlValues(form,workflow) {
  const values = {};
  for (const [name,spec] of Object.entries(workflow.controls)) {
    const value = form.elements.namedItem(name).value;
    values[name] = ['integer','number'].includes(spec.kind) ? Number(value) : value;
  }
  return values;
}

export function modelSelections(form,workflow) {
  return Object.fromEntries(Object.entries(workflow.controls).filter(([,spec])=>spec.kind==='model').map(([name])=>[name,form.elements.namedItem(name).value]));
}

export function fillControls(form,values,workflow) {
  for (const [name,value] of Object.entries(values)) {
    if (workflow?.controls[name]?.kind==='model') continue;
    const field = form.elements.namedItem(name);
    if (field) field.value = value;
  }
}

export function renderControls(container,workflow,onChange,expert=false) {
  container.replaceChildren();
  const basics = document.createElement('div'); basics.className='field-grid';
  const details = document.createElement('details'); details.className='advanced';details.dataset.expertOnly='';details.hidden=!expert;details.open=true;
  const summary = document.createElement('summary'); summary.textContent='Modelle und technische Einstellungen';
  const more = document.createElement('div'); more.className='field-grid';
  details.append(summary,more);
  for (const [name,spec] of Object.entries(workflow.controls)) {
    const label = document.createElement('label'); label.className='field';
    if (['text','model'].includes(spec.kind)) label.classList.add('wide');
    const title = document.createElement('span'); title.textContent=spec.label;
    const field = document.createElement(spec.kind==='model' ? 'select' : spec.kind==='text' ? 'textarea' : 'input');
    field.name=name; field.id='control-'+name;
    let hint;
    if (spec.kind==='model') {
      for(const item of spec.options){const option=document.createElement('option');option.value=item.id;option.textContent=item.label;field.append(option);}
      if(!spec.options.some(item=>item.id===spec.default)){const option=document.createElement('option');option.value=spec.default;option.textContent='Bisheriges Modell nicht verfügbar';field.append(option);}
      hint=document.createElement('small');hint.className='model-hint';
    }
    field.value=spec.default;
    if (spec.kind==='text') { field.rows=name==='prompt' ? 4 : 2; field.maxLength=8000; field.required=name==='prompt'; }
    else if (spec.kind==='faces') { field.type='text'; field.pattern='[0-9]+(,[0-9]+)*'; field.maxLength=64; field.required=true; }
    else if(spec.kind!=='model') { field.type='number'; field.min=spec.min; field.max=spec.max; field.step=spec.step ?? 1; field.required=true; }
    const describe=()=>{if(!hint)return;const item=spec.options.find(item=>item.id===field.value);hint.textContent=item ? [item.recommended_size ? `Empfohlene Größe: ${item.recommended_size} × ${item.recommended_size}. Deine Werte bleiben erhalten.` : '',item.note,item.path].filter(Boolean).join('\n') : 'Bitte ein vorhandenes, passendes Modell auswählen.';};
    field.addEventListener('input',event=>{describe();onChange(event);});
    label.append(title,field); (name==='prompt' ? basics : more).append(label);
    if(hint){label.append(hint);describe();}
  }
  container.append(basics);
  if (more.children.length) container.append(details);
}
