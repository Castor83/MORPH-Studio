import {versionLabel} from './results.js';

export function comparisonPair(project,pair,focus){
  const versions=project?.versions || [],ids=new Set(versions.map(version=>version.id));
  const original=ids.has(project?.original_version_id)?project.original_version_id:versions[0]?.id || '';
  if(focus && ids.has(focus)){
    const version=versions.find(item=>item.id===focus);
    return {left:version.parent_version_id || original,right:focus===original?versions.at(-1)?.id || original:focus};
  }
  return {left:ids.has(pair?.left)?pair.left:original,right:ids.has(pair?.right)?pair.right:versions.at(-1)?.id || original};
}

export function boundedViewport(view){
  const zoom=Math.max(1,Math.min(6,Number(view.zoom) || 1)),limit=(zoom-1)/2;
  return {zoom,x:Math.max(-limit,Math.min(limit,Number(view.x) || 0)),y:Math.max(-limit,Math.min(limit,Number(view.y) || 0))};
}

export function createComparison(container,doc=globalThis.document){
  let project,pair={left:'',right:''},view={zoom:1,x:0,y:0},drag;
  const make=(tag,text,className)=>{const node=doc.createElement(tag);if(text)node.textContent=text;if(className)node.className=className;return node;};
  const heading=make('h3','Versionen vergleichen'),help=make('p','Wähle zwei Versionen. Zoom und Verschieben gelten für beide Ansichten. Der Vergleich ändert dein Ausgangsbild nicht.','muted small');
  const choices=make('div',null,'comparison-choices'),panes=make('div',null,'comparison-panes'),selectors={},images={},captions={};
  for(const [side,label] of [['left','Vorher / links'],['right','Nachher / rechts']]){
    const field=make('label',null,'field'),title=make('span',label),select=make('select');select.setAttribute('aria-label',label);field.append(title,select);choices.append(field);selectors[side]=select;
    const figure=make('figure'),pane=make('div',null,'comparison-viewport'),image=make('img'),caption=make('figcaption');pane.tabIndex=0;pane.setAttribute('aria-label',label+' · zum Verschieben ziehen oder Pfeiltasten verwenden');image.draggable=false;pane.append(image);figure.append(pane,caption);panes.append(figure);images[side]=image;captions[side]=caption;
    select.addEventListener('change',()=>{pair[side]=select.value;drawImages();});
    image.addEventListener('error',()=>{caption.textContent='Bild kann nicht angezeigt werden. Bitte Version und lokale Datei prüfen.';});
    pane.addEventListener('pointerdown',event=>{if(event.button!==0)return;const bounds=pane.getBoundingClientRect();drag={pointer:event.pointerId,x:event.clientX,y:event.clientY,width:bounds.width,height:bounds.height,view:{...view}};pane.setPointerCapture?.(event.pointerId);event.preventDefault();});
    pane.addEventListener('pointermove',event=>{if(!drag || drag.pointer!==event.pointerId)return;setView({...view,x:drag.view.x+(event.clientX-drag.x)/drag.width,y:drag.view.y+(event.clientY-drag.y)/drag.height});});
    const release=()=>{drag=null;};pane.addEventListener('pointerup',release);pane.addEventListener('pointercancel',release);pane.addEventListener('lostpointercapture',release);
    pane.addEventListener('keydown',event=>{const moves={ArrowLeft:[.05,0],ArrowRight:[-.05,0],ArrowUp:[0,.05],ArrowDown:[0,-.05]};if(!moves[event.key])return;event.preventDefault();const [x,y]=moves[event.key];setView({...view,x:view.x+x,y:view.y+y});});
  }
  const toolbar=make('div',null,'comparison-toolbar'),zoomLabel=make('label','Zoom'),zoom=make('input'),zoomValue=make('output','100 %');zoom.type='range';zoom.min=100;zoom.max=600;zoom.step=10;zoom.value=100;zoom.setAttribute('aria-label','Gemeinsamer Zoom');zoomLabel.append(zoom,zoomValue);toolbar.append(zoomLabel);
  const button=(label,action)=>{const node=make('button',label,'quiet small');node.type='button';node.addEventListener('click',action);toolbar.append(node);return node;};
  button('Alles zeigen',()=>setView({zoom:1,x:0,y:0}));button('Ansichten tauschen',()=>{pair={left:pair.right,right:pair.left};drawImages();});button('Original links',()=>{pair.left=project.original_version_id;drawImages();});button('Elternversion links',()=>{const right=project.versions.find(item=>item.id===pair.right);pair.left=right?.parent_version_id || project.original_version_id;drawImages();});
  zoom.addEventListener('input',()=>setView({...view,zoom:Number(zoom.value)/100}));
  container.append(heading,help,choices,toolbar,panes);container.hidden=true;
  function setView(next){view=boundedViewport(next);zoom.value=Math.round(view.zoom*100);zoomValue.textContent=zoom.value+' %';for(const image of Object.values(images))image.style.transform=`translate(${view.x*100}%,${view.y*100}%) scale(${view.zoom})`;}
  function drawImages(){for(const side of ['left','right']){const version=project?.versions.find(item=>item.id===pair[side]);selectors[side].value=pair[side];const url=version?.media?.url || '';if(images[side].dataset.mediaUrl!==url){images[side].src=url;images[side].dataset.mediaUrl=url;}images[side].alt=versionLabel(project,version?.id);captions[side].textContent=versionLabel(project,version?.id);}setView(view);}
  function setProject(next,focus){if(next===project && !focus)return;if(!next?.versions?.length){project=null;container.hidden=true;return;}const changed=project?.id!==next.id;project=next;pair=comparisonPair(project,changed?null:pair,focus);if(changed || focus){view={zoom:1,x:0,y:0};drag=null;}for(const select of Object.values(selectors)){select.replaceChildren();for(const version of project.versions){const option=make('option',versionLabel(project,version.id));option.value=version.id;select.append(option);}}container.hidden=false;drawImages();}
  return {setProject,compare(version){setProject(project,version.id);container.scrollIntoView?.({block:'nearest',behavior:'smooth'});}};
}
