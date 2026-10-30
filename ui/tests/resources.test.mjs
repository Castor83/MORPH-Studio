import test from 'node:test';
import assert from 'node:assert/strict';
let resources;try{resources=await import('../frontend/resources.js');}catch(error){if(error.code!=='ERR_MODULE_NOT_FOUND')throw error;}

const snapshot=(patch={})=>({available:true,measured_at:'2026-10-20T14:05:06Z',source:'ComfyUI /system_stats',devices:[{name:'RTX 4080',type:'cuda',index:0,vram_total:16*1024**3,vram_free:12*1024**3,vram_used:4*1024**3}],ram:{total:48*1024**3,free:32*1024**3,used:16*1024**3},model_state:'unknown',unload:{allowed:true,reason:''},...patch});
function panel(request){
  assert.ok(resources?.createResources,'Die Ressourcenanzeige fehlt.');
  const nodes=[];const doc={createElement(tag){const node={tag,textContent:'',children:[],listeners:{},disabled:false,hidden:false,attributes:{},append(...children){this.children.push(...children);},replaceChildren(...children){this.children=[...children];},setAttribute(key,value){this.attributes[key]=String(value);},addEventListener(key,fn){this.listeners[key]=fn;}};nodes.push(node);return node;}};
  const container=doc.createElement('section'),controller=resources.createResources(container,{doc,request});
  const descendants=node=>[node,...node.children.flatMap(descendants)];
  return {controller,nodes,container,text:()=>descendants(container).map(node=>node.textContent).join('\n'),button:label=>nodes.find(node=>node.tag==='button' && node.textContent===label)};
}
const freeLabel='Bildmodelle im Rechendienst freigeben';
const emergencyLabel='Notfall: Speicher vollständig freigeben';

test('emergency release is explicit, stops the own service once, and excludes automatic restart',async()=>{
  const calls=[];let finish;const view=panel(async(path,options={})=>{
    calls.push({path,options});
    if(path.endsWith('/emergency-release'))return new Promise(resolve=>finish=resolve);
    return snapshot();
  });
  await view.controller.refresh();
  assert.ok(view.button(emergencyLabel),'Notfall-Schaltfläche fehlt');
  assert.match(view.text(),/nächsten.*Bildauftrag/s);
  assert.match(view.text(),/beendet.*eigenen Rechendienst/s);
  const pending=view.button(emergencyLabel).listeners.click();
  assert.equal(view.controller.freeing,true);
  assert.equal(view.button(freeLabel).disabled,true);
  await view.button(emergencyLabel).listeners.click();
  assert.equal(calls.filter(c=>c.options.method==='POST').length,1);
  finish({completed:true,stopped:true,old_pid:123});await pending;
  const posts=calls.filter(c=>c.options.method==='POST');
  assert.equal(posts[0].path,'/api/resources/emergency-release');
  assert.deepEqual(posts[0].options.body,{});
  assert.match(view.text(),/Rechendienst.*beendet/);
  assert.equal(view.controller.freeing,false);
});

test('emergency release denies busy or unowned instances even with retained handlers',async()=>{
  const calls=[],view=panel(async(path,options={})=>{calls.push({path,options});return snapshot({unload:{allowed:false,reason:'Keine eigene freie Instanz'}});});
  await view.controller.refresh();
  assert.ok(view.button(emergencyLabel),'Notfall-Schaltfläche fehlt');
  assert.equal(view.button(emergencyLabel).disabled,true);
  await view.button(emergencyLabel).listeners.click();
  assert.equal(calls.filter(c=>c.options.method==='POST').length,0);
  const local=panel(async(path,options={})=>{calls.push({path,options});return snapshot();});
  await local.controller.refresh();local.controller.setBlocked('Auftrag läuft');
  assert.equal(local.button(emergencyLabel).disabled,true);
  await local.button(emergencyLabel).listeners.click();
  assert.equal(calls.filter(c=>c.options.method==='POST').length,0);
});

test('accepted or ambiguous emergency replies never claim confirmed process exit or retry',async()=>{
  for(const reply of [{accepted:true,completed:false},{completed:true,stopped:false},null]){
    let posts=0;const view=panel(async(path,options={})=>{if(options.method==='POST'){posts++;return reply;}return snapshot();});
    await view.controller.refresh();
    assert.ok(view.button(emergencyLabel),'Notfall-Schaltfläche fehlt');
    await view.button(emergencyLabel).listeners.click();
    assert.equal(posts,1);assert.match(view.text(),/nicht bestätigt/);
    assert.doesNotMatch(view.text(),/wurde beendet/);
    assert.equal(view.controller.freeing,false);
  }
});

test('resource panel shows measured GPU VRAM and time while model residency stays unknown',async()=>{
  const view=panel(async()=>snapshot({last_used_model:'last-used.safetensors',loaded_models:['invented-loaded-model']}));await view.controller.refresh();
  assert.match(view.text(),/RTX 4080.*4,0.*16,0.*GiB/);assert.match(view.text(),/Gemessen:/);assert.match(view.text(),/20\.10\.2026/);
  assert.match(view.text(),/RAM.*16,0.*48,0.*GiB/);assert.match(view.text(),/ComfyUI \/system_stats/);
  assert.match(view.text(),/Geladene Bildmodelle: vom Rechendienst nicht gemeldet/);assert.doesNotMatch(view.text(),/last-used|invented-loaded/);
  assert.equal(view.button(freeLabel).disabled,false);
});

test('missing or malformed memory values remain unknown instead of becoming zero',async()=>{
  const view=panel(async()=>snapshot({measured_at:null,source:null,devices:[{name:'GPU',type:'cuda',index:0,vram_total:'17179869184',vram_used:-5,vram_free:Infinity}],ram:{total:null,free:'0',used:NaN}}));await view.controller.refresh();
  assert.match(view.text(),/GPU.*VRAM.*unbekannt.*unbekannt/);assert.match(view.text(),/Messzeitpunkt: nicht gemeldet/);assert.match(view.text(),/RAM.*unbekannt.*unbekannt/);assert.doesNotMatch(view.text(),/0,0 GiB/);
});

test('unavailable and structurally malformed resource replies show the gap and deny freeing',async()=>{
  for(const data of [null,[],{},snapshot({devices:null}),snapshot({available:false,error:'Rechendienst ist offline',devices:[]})]){
    const view=panel(async()=>data);await view.controller.refresh();assert.match(view.text(),/Ressourcen.*nicht verfügbar/);assert.equal(view.button(freeLabel).disabled,true);assert.doesNotMatch(view.text(),/0,0 GiB/);
  }
});

test('resource read failures show an explicit unavailable state and never request a release',async()=>{
  const calls=[],view=panel(async(path,options={})=>{calls.push({path,options});throw new Error('Verbindung fehlt');});await view.controller.refresh();
  assert.match(view.text(),/Ressourcen.*nicht verfügbar/);assert.match(view.text(),/Verbindung fehlt/);assert.equal(calls.length,1);assert.equal(calls[0].path,'/api/resources');assert.notEqual(calls[0].options.method,'POST');assert.equal(view.controller.freeing,false);
});

test('a later resource read wins when an earlier read arrives late',async()=>{
  let release;let reads=0;const view=panel(async()=>++reads===1?new Promise(resolve=>release=resolve):snapshot({devices:[{name:'CURRENT',vram_total:16*1024**3,vram_used:6*1024**3}]}));
  const older=view.controller.refresh();await view.controller.refresh();release(snapshot({devices:[{name:'STALE',vram_total:16*1024**3,vram_used:1*1024**3}]}));await older;
  assert.match(view.text(),/CURRENT/);assert.doesNotMatch(view.text(),/STALE/);
});

test('only an explicit release action sends a POST and an accepted request does not claim completion',async()=>{
  const calls=[];let finishFree;const view=panel(async(path,options={})=>{calls.push({path,options});return path.endsWith('/free')?new Promise(resolve=>finishFree=resolve):snapshot();});
  await view.controller.refresh();assert.equal(calls.some(call=>call.options.method==='POST'),false);
  const freeing=view.button(freeLabel).listeners.click();assert.equal(view.controller.freeing,true);assert.equal(view.button(freeLabel).disabled,true);
  finishFree({accepted:true,completed:false,message:'Freigabe angefordert'});await freeing;
  const posts=calls.filter(call=>call.options.method==='POST');assert.equal(posts.length,1);assert.equal(posts[0].path,'/api/resources/free');assert.deepEqual(posts[0].options.body,{});
  assert.match(view.text(),/Freigabe angefordert/);assert.match(view.text(),/noch kein.*abgeschlossen/i);assert.doesNotMatch(view.text(),/Modelle freigegeben|erfolgreich entladen/);assert.equal(view.controller.freeing,false);
  assert.match(view.text(),/alle Bildmodelle.*eigenen Rechendienst/s);assert.match(view.text(),/Ollama bleibt unverändert/);
});

test('backend and local busy reasons disable release even for a retained click handler',async()=>{
  const calls=[],view=panel(async(path,options={})=>{calls.push({path,options});return snapshot({unload:{allowed:false,reason:'Fremde Instanz'}});});
  await view.controller.refresh();await view.button(freeLabel).listeners.click();assert.match(view.text(),/Fremde Instanz/);assert.equal(calls.some(call=>call.options.method==='POST'),false);
  const local=panel(async(path,options={})=>{calls.push({path,options});return snapshot();});await local.controller.refresh();local.controller.setBlocked('Ein Bild wird übernommen.');await local.button(freeLabel).listeners.click();assert.match(local.text(),/Ein Bild wird übernommen/);assert.equal(local.button(freeLabel).disabled,true);assert.equal(calls.some(call=>call.options.method==='POST'),false);
});

test('a backend release denial remains visible and is never reported as successful',async()=>{
  const view=panel(async path=>{if(path.endsWith('/free'))throw new Error('Warteschlange nicht leer');return snapshot();});await view.controller.refresh();await view.button(freeLabel).listeners.click();
  assert.match(view.text(),/Warteschlange nicht leer/);assert.doesNotMatch(view.text(),/Freigabe angefordert/);assert.equal(view.controller.freeing,false);
});

test('an old resource refresh cannot overwrite the status measured after a release',async()=>{
  let releaseRead,reads=0;const view=panel(async path=>path.endsWith('/free')?{accepted:true,completed:false}:++reads===1?snapshot():reads===2?new Promise(resolve=>releaseRead=resolve):snapshot({devices:[{name:'AFTER',vram_used:2*1024**3,vram_total:16*1024**3}]}));
  await view.controller.refresh();const older=view.controller.refresh();await view.controller.free();releaseRead(snapshot({devices:[{name:'OLD',vram_used:10*1024**3,vram_total:16*1024**3}]}));await older;
  assert.match(view.text(),/AFTER/);assert.doesNotMatch(view.text(),/OLD/);
});
