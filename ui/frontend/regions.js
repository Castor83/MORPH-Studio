const gcd=(a,b)=>b?gcd(b,a%b):a;
const lcm=(a,b)=>a/gcd(a,b)*b;
const bindingKey=b=>b?JSON.stringify([b.workflow_id,b.source_media_id,b.parent_version_id,b.project_id]):'';

export function compatibleRaster(width,height,controls,preferred){
  if(!Number.isInteger(width) || !Number.isInteger(height) || width<1 || height<1)return null;
  const divisor=gcd(width,height),x=width/divisor,y=height/divisor,w=controls?.width,h=controls?.height;if(!w || !h)return null;
  const unit=lcm((w.step || 1)/gcd(x,w.step || 1),(h.step || 1)/gcd(y,h.step || 1));
  const min=Math.ceil(Math.max((w.min || 1)/x,(h.min || 1)/y)/unit),max=Math.floor(Math.min(w.max/x,h.max/y)/unit);
  if(max<min)return null;
  const target=Math.sqrt((Number(preferred?.width) || width)*(Number(preferred?.height) || height)/(x*y));
  const scale=Math.max(min,Math.min(max,Math.round(target/unit)))*unit;
  return {width:x*scale,height:y*scale};
}

export function regionRequest(binding,receipt,dirty){
  if(dirty || !binding || !receipt?.mask_media_id || bindingKey(binding)!==bindingKey(receipt))return null;
  return {mask_media_id:receipt.mask_media_id,source_media_id:binding.source_media_id,parent_version_id:binding.parent_version_id};
}

export function createRegionEditor(container,{uploadMask,onChange=()=>{},onDimensions=()=>{},getControls=()=>({}),doc=globalThis.document}={}){
  let binding=null,key='',epoch=0,revision=0,receipt=null,dirty=false,saving=false,loading=false,error='',dimensions=null,workflow=null,drawing=null,marks=false,erase=false;
  const make=(tag,text,className)=>{const node=doc.createElement(tag);if(text)node.textContent=text;if(className)node.className=className;return node;};
  const detail=make('details'),summary=make('summary','Nur markierten Bereich übernehmen'),help=make('p','Male den gewünschten Bereich weiß aus. Das Modell sieht das ganze Ausgangsbild. Anschließend werden nur markierte Pixel aus dem erzeugten Bild übernommen; außen bleibt das Ausgangsbild erhalten. Innerhalb der Markierung können Details und Übergänge abweichen.','muted small');
  const status=make('p',null,'muted small'),errorText=make('p',null,'error-text');errorText.setAttribute('role','alert');
  const stage=make('div',null,'region-stage'),canvas=make('canvas');canvas.setAttribute('aria-label','Bearbeitungsbereich mit gedrückter Maustaste weiß markieren');
  const tools=make('div',null,'region-tools'),brushLabel=make('label','Pinselgröße '),brush=make('input');brush.type='range';brush.min=1;brush.max=15;brush.step=1;brush.value=5;brush.setAttribute('aria-label','Pinselgröße in Prozent der kurzen Bildseite');brushLabel.append(brush);tools.append(brushLabel);
  const button=(label,action)=>{const node=make('button',label,'quiet small');node.type='button';node.addEventListener('click',action);tools.append(node);return node;};
  const mode=button('Radierer verwenden',()=>{erase=!erase;mode.textContent=erase?'Pinsel verwenden':'Radierer verwenden';mode.setAttribute('aria-pressed',String(erase));});
  const clear=button('Ganzes Bild bearbeiten',()=>{if(saving)return;resetMask();onChange();});
  const size=button('Passende Bildgröße übernehmen',()=>{const next=dimensions && compatibleRaster(dimensions.width,dimensions.height,workflow?.controls,getControls());if(next){onDimensions(next);drawStatus();onChange();}});
  const apply=button('Bereich übernehmen',save);detail.append(summary,help,status,stage,tools,errorText);container.append(detail);container.hidden=true;
  function context(){return canvas.getContext('2d',{willReadFrequently:true});}
  function fillBlack(){const ctx=context();if(ctx){ctx.fillStyle='black';ctx.fillRect(0,0,canvas.width,canvas.height);}}
  function resetMask(){revision++;receipt=null;dirty=false;marks=false;error='';fillBlack();drawStatus();}
  function geometryError(){if(!dimensions)return '';const values=getControls();if(Number(values.width)*dimensions.height===Number(values.height)*dimensions.width)return '';const next=compatibleRaster(dimensions.width,dimensions.height,workflow?.controls,values);return next?`Die Bildgröße muss zum Ausgangsbild passen. Übernimm ${next.width} × ${next.height}, bevor du den Bereich sicherst oder berechnest.`:'Dieses Seitenverhältnis passt in keine unterstützte Bildgröße. Speichere eine passend zugeschnittene PNG-Datei als neues Ausgangsbild oder wähle „Ganzes Bild bearbeiten“.';}
  function drawStatus(){const geometry=geometryError();status.textContent=loading?'Ausgangsbild wird für die Markierung geöffnet …':saving?'Markierung wird lokal gesichert …':dirty?'Markierung noch nicht übernommen. Übernimm den Bereich oder wähle „Ganzes Bild bearbeiten“.':receipt?'Markierter Bereich ist übernommen. Starte die Berechnung selbst.':dimensions?`Ausgangsbild: ${dimensions.width} × ${dimensions.height}. Weiß = aus dem erzeugten Bild übernehmen.`:'Wähle ein gesichertes Ausgangsbild für die Bereichsauswahl.';errorText.textContent=error || (marks || receipt ? geometry : '');errorText.hidden=!errorText.textContent;canvas.style.pointerEvents=loading || saving || !dimensions?'none':'auto';apply.disabled=loading || saving || !dimensions || !marks || !dirty || Boolean(geometry);mode.disabled=loading || saving || !dimensions;clear.disabled=saving;size.hidden=!geometry;size.disabled=saving || !dimensions || !compatibleRaster(dimensions.width,dimensions.height,workflow?.controls,getControls());}
  function point(event){const rect=canvas.getBoundingClientRect();return {x:Math.max(0,Math.min(canvas.width,(event.clientX-rect.left)*canvas.width/rect.width)),y:Math.max(0,Math.min(canvas.height,(event.clientY-rect.top)*canvas.height/rect.height))};}
  function paint(from,to){const notify=!dirty,ctx=context(),radius=Math.max(1,Math.min(canvas.width,canvas.height)*Number(brush.value)/100);ctx.strokeStyle=ctx.fillStyle=erase?'black':'white';ctx.lineWidth=radius;ctx.lineCap='round';ctx.lineJoin='round';ctx.beginPath();ctx.moveTo(from.x,from.y);ctx.lineTo(to.x,to.y);ctx.stroke();ctx.beginPath();ctx.arc(to.x,to.y,radius/2,0,Math.PI*2);ctx.fill();dirty=true;receipt=null;revision++;marks=true;error='';drawStatus();if(notify)onChange();}
  canvas.addEventListener('pointerdown',event=>{if(event.button!==0 || saving || loading || !dimensions)return;event.preventDefault();const current=point(event);drawing={pointer:event.pointerId,point:current};canvas.setPointerCapture?.(event.pointerId);paint(current,current);});
  canvas.addEventListener('pointermove',event=>{if(!drawing || drawing.pointer!==event.pointerId)return;const next=point(event);paint(drawing.point,next);drawing.point=next;});
  for(const name of ['pointerup','pointercancel','lostpointercapture'])canvas.addEventListener(name,()=>{drawing=null;});
  async function save(){
    if(apply.disabled)return;const token={key,epoch,revision,binding:{...binding}};saving=true;error='';drawStatus();onChange();
    try{const pixels=context().getImageData(0,0,canvas.width,canvas.height).data;let nonempty=false;for(let index=0;index<pixels.length;index+=4)if(pixels[index]){nonempty=true;break;}if(!nonempty)throw new Error('Die Markierung ist leer. Male einen Bereich weiß aus oder wähle „Ganzes Bild bearbeiten“.');
      const blob=await new Promise((resolve,reject)=>canvas.toBlob(value=>value?resolve(value):reject(new Error('Die PNG-Markierung konnte nicht gespeichert werden.')),'image/png'));
      if(token.key!==key || token.epoch!==epoch || token.revision!==revision)return;
      const media=await uploadMask(blob);if(token.key!==key || token.epoch!==epoch || token.revision!==revision)return;if(!media?.id)throw new Error('Die Markierung wurde nicht eindeutig bestätigt.');receipt={...token.binding,mask_media_id:media.id};dirty=false;
    }catch(cause){if(token.key===key && token.epoch===epoch)error=cause.message || 'Die Markierung konnte nicht übernommen werden.';}
    finally{if(token.key===key && token.epoch===epoch){saving=false;drawStatus();onChange();}}
  }
  function setSource(source){
    const next=source && ['krea2','kontext'].includes(source.workflow?.id) && source.image?.id && source.context?{workflow_id:source.workflow.id,source_media_id:source.image.id,parent_version_id:source.context.parent_version_id,project_id:source.context.project_id}:null;
    const nextKey=bindingKey(next);workflow=source?.workflow || null;if(nextKey===key){drawStatus();return;}binding=next;key=nextKey;epoch++;revision++;saving=false;loading=false;dimensions=null;receipt=null;dirty=false;marks=false;error='';drawing=null;container.hidden=!next;stage.hidden=true;if(!next){drawStatus();return;}
    const token=epoch,image=make('img');image.alt='Aktuelles Ausgangsbild für Bereichsauswahl';stage.replaceChildren(image,canvas);loading=true;image.onload=()=>{if(token!==epoch)return;const width=image.naturalWidth,height=image.naturalHeight;if(!width || !height || width*height>64000000){loading=false;error='Dieses Bild ist für die Bereichsauswahl zu groß oder nicht lesbar.';drawStatus();onChange();return;}dimensions={width,height};canvas.width=width;canvas.height=height;fillBlack();stage.hidden=false;loading=false;drawStatus();onChange();};image.onerror=()=>{if(token!==epoch)return;loading=false;error='Das Ausgangsbild kann für die Markierung nicht geöffnet werden.';drawStatus();onChange();};image.src=source.image.url;drawStatus();
  }
  return {setSource,refresh:drawStatus,get blocked(){return saving || dirty || Boolean(receipt && geometryError());},get hint(){return saving?'Bitte warten, bis die Markierung gesichert ist.':dirty?'Bitte den markierten Bereich übernehmen oder „Ganzes Bild bearbeiten“ wählen.':receipt?geometryError():'';},get request(){return regionRequest(binding,receipt,dirty);}};
}
