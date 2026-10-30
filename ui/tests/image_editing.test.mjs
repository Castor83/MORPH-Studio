import test from 'node:test';
import assert from 'node:assert/strict';
let comparison,regions;
try{comparison=await import('../frontend/comparison.js');}catch(error){if(error.code!=='ERR_MODULE_NOT_FOUND')throw error;}
try{regions=await import('../frontend/regions.js');}catch(error){if(error.code!=='ERR_MODULE_NOT_FOUND')throw error;}

test('comparison keeps any selected pair on refresh and uses parent as convenient before view',()=>{
  assert.ok(comparison,'Versionsvergleich fehlt');
  const project={id:'P',original_version_id:'O',versions:[{id:'O'},{id:'A',parent_version_id:'O'},{id:'B',parent_version_id:'A'},{id:'C',parent_version_id:'A'}]};
  assert.deepEqual(comparison.comparisonPair(project,null,'C'),{left:'A',right:'C'});
  assert.deepEqual(comparison.comparisonPair(project,{left:'B',right:'C'}),{left:'B',right:'C'});
  assert.deepEqual(comparison.comparisonPair(project,{left:'deleted',right:'C'}),{left:'O',right:'C'});
});

test('shared comparison viewport clamps zoom and pan without separate pane coordinates',()=>{
  assert.ok(comparison,'Synchroner Bildausschnitt fehlt');
  assert.deepEqual(comparison.boundedViewport({zoom:2,x:2,y:-3}),{zoom:2,x:.5,y:-.5});
  assert.deepEqual(comparison.boundedViewport({zoom:1,x:1,y:1}),{zoom:1,x:0,y:0});
  assert.deepEqual(comparison.boundedViewport({zoom:40,x:0,y:0}),{zoom:6,x:0,y:0});
});

test('regional raster preserves exact source aspect within workflow step and size limits',()=>{
  assert.ok(regions,'Bereichsgeometrie fehlt');
  const controls={width:{min:16,max:16384,step:16},height:{min:16,max:16384,step:16}};
  assert.deepEqual(regions.compatibleRaster(384,256,controls,{width:1024,height:1024}),{width:1248,height:832});
  const raster=regions.compatibleRaster(4032,3024,controls,{width:1024,height:1024});
  assert.equal(raster.width*3024,raster.height*4032);assert.equal(raster.width%16,0);assert.equal(raster.height%16,0);
  assert.equal(regions.compatibleRaster(16381,16379,controls,{width:1024,height:1024}),null);
});

test('mask receipt binds exact source and parent and dirty edits cannot be submitted',()=>{
  assert.ok(regions,'Maskenbindung fehlt');
  const binding={workflow_id:'krea2',source_media_id:'IMAGE',parent_version_id:'PARENT',project_id:'PROJECT'};
  const receipt={...binding,mask_media_id:'MASK'};
  assert.deepEqual(regions.regionRequest(binding,receipt,false),{mask_media_id:'MASK',source_media_id:'IMAGE',parent_version_id:'PARENT'});
  assert.equal(regions.regionRequest({...binding,source_media_id:'OTHER'},receipt,false),null);
  assert.equal(regions.regionRequest({...binding,parent_version_id:'OTHER'},receipt,false),null);
  assert.equal(regions.regionRequest({...binding,workflow_id:'kontext'},receipt,false),null);
  assert.equal(regions.regionRequest(binding,receipt,true),null);
});

function editingDOM(){
  const nodes=[];let painted=false;
  const context={fillStyle:'black',fillRect(){painted=false;},beginPath(){},moveTo(){},lineTo(){},stroke(){painted=this.fillStyle==='white';},arc(){},fill(){painted=this.fillStyle==='white';},getImageData(){return {data:painted?new Uint8ClampedArray([255,255,255,255]):new Uint8ClampedArray([0,0,0,255])};}};
  const element=tag=>{const node={tag,children:[],style:{},dataset:{},attributes:{},listeners:{},hidden:false,value:'',textContent:'',naturalWidth:384,naturalHeight:256,append(...items){this.children.push(...items);},replaceChildren(...items){this.children=[...items];},setAttribute(name,value){this.attributes[name]=String(value);},addEventListener(name,fn){this.listeners[name]=fn;},getBoundingClientRect(){return {left:0,top:0,width:384,height:256};},getContext(){return context;},toBlob(fn,type){fn({type});},scrollIntoView(){}};nodes.push(node);return node;};
  return {doc:{createElement:element},container:element('section'),nodes,find:label=>nodes.find(node=>node.textContent===label),canvas:()=>nodes.find(node=>node.tag==='canvas')};
}
const source=(id='I',parent='P')=>({workflow:{id:'krea2',controls:{width:{min:16,max:16384,step:16},height:{min:16,max:16384,step:16}}},image:{id,url:'/media/'+id},context:{project_id:'PROJECT',parent_version_id:parent}});
const pointer={button:0,pointerId:1,clientX:120,clientY:80,preventDefault(){}};

test('comparison controls and pointer pan apply one view to both images and persist chosen versions',()=>{
  const dom=editingDOM(),viewer=comparison.createComparison(dom.container,dom.doc),versions=[{id:'O',media:{url:'/O'}},{id:'A',parent_version_id:'O',media:{url:'/A'}},{id:'B',parent_version_id:'A',media:{url:'/B'}}];
  const project={id:'P',original_version_id:'O',versions};viewer.setProject(project);
  const selects=dom.nodes.filter(node=>node.tag==='select');selects[0].value='A';selects[0].listeners.change();viewer.setProject({...project});assert.equal(selects[0].value,'A');
  const zoom=dom.nodes.find(node=>node.tag==='input');zoom.value=200;zoom.listeners.input();
  const panes=dom.nodes.filter(node=>node.className==='comparison-viewport');panes[0].listeners.pointerdown(pointer);panes[0].listeners.pointermove({...pointer,clientX:158,clientY:106});
  const images=dom.nodes.filter(node=>node.tag==='img');assert.equal(images[0].style.transform,images[1].style.transform);assert.match(images[0].style.transform,/scale\(2\)/);assert.notEqual(images[0].style.transform,'translate(0%,0%) scale(2)');
  viewer.compare(versions[2]);assert.equal(selects[0].value,'A');assert.equal(selects[1].value,'B');
});

test('painted region requires explicit save then binds a single uploaded PNG receipt',async()=>{
  const dom=editingDOM();let uploads=0;const editor=regions.createRegionEditor(dom.container,{doc:dom.doc,getControls:()=>({width:768,height:512}),uploadMask:async blob=>{uploads++;assert.equal(blob.type,'image/png');return {id:'MASK'};}});
  editor.setSource(source());dom.nodes.find(node=>node.tag==='img').onload();dom.canvas().listeners.pointerdown(pointer);dom.canvas().listeners.pointerup();
  assert.equal(editor.blocked,true);assert.equal(editor.request,null);assert.equal(uploads,0);
  await dom.find('Bereich übernehmen').listeners.click();assert.equal(uploads,1);assert.equal(editor.blocked,false);assert.deepEqual(editor.request,{mask_media_id:'MASK',source_media_id:'I',parent_version_id:'P'});
  dom.find('Ganzes Bild bearbeiten').listeners.click();assert.equal(editor.request,null);assert.equal(editor.blocked,false);
});

test('late source decode and mask upload cannot attach a region to a replacement image',async()=>{
  const dom=editingDOM();let release;const editor=regions.createRegionEditor(dom.container,{doc:dom.doc,getControls:()=>({width:768,height:512}),uploadMask:()=>new Promise(resolve=>release=resolve)});
  editor.setSource(source('OLD'));const image=dom.nodes.find(node=>node.tag==='img'),oldLoad=image.onload;
  editor.setSource(source('CURRENT'));oldLoad();assert.equal(dom.find('Bereich übernehmen').disabled,true);
  dom.nodes.filter(node=>node.tag==='img').at(-1).onload();dom.canvas().listeners.pointerdown(pointer);const save=dom.find('Bereich übernehmen').listeners.click();await new Promise(resolve=>setImmediate(resolve));
  assert.equal(editor.blocked,true);editor.setSource(source('NEW','NEW-PARENT'));release({id:'STALE-MASK'});await save;assert.equal(editor.request,null);assert.equal(editor.blocked,false);
});

test('masked edit never silently changes dimensions and incompatible geometry stays blocked',async()=>{
  const dom=editingDOM();let values={width:1024,height:1024},chosen,uploads=0;const editor=regions.createRegionEditor(dom.container,{doc:dom.doc,getControls:()=>values,onDimensions:raster=>{chosen=raster;values=raster;},uploadMask:async()=>{uploads++;return {id:'M'};}});
  editor.setSource(source());dom.nodes.find(node=>node.tag==='img').onload();dom.canvas().listeners.pointerdown(pointer);
  assert.equal(dom.find('Bereich übernehmen').disabled,true);assert.equal(chosen,undefined);assert.equal(uploads,0);
  dom.find('Passende Bildgröße übernehmen').listeners.click();assert.deepEqual(chosen,{width:1248,height:832});await dom.find('Bereich übernehmen').listeners.click();assert.equal(uploads,1);
  values={width:1024,height:1024};editor.refresh();assert.equal(editor.blocked,true);assert.match(editor.hint,/Bildgröße/);
});
