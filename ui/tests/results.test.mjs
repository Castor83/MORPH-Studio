import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';

function rendered(job,actions={}){
  const element=tag=>({tag,children:[],textContent:'',open:false,listeners:{},attributes:{},setAttribute(name,value){this.attributes[name]=String(value);},append(...children){this.children.push(...children);},replaceChildren(...children){this.children=[...children];},addEventListener(name,callback){this.listeners[name]=callback;},set innerHTML(value){throw new Error('HTML must not be interpreted');}});
  const document={createElement:element};
  const context=vm.createContext({document});
  const source=fs.readFileSync(new URL('../frontend/results.js',import.meta.url),'utf8').replace(/^export /gm,'');
  vm.runInContext(source+'\nglobalThis.render=renderJob;',context);
  const container=element('div');context.render(container,job,actions);return container;
}
const descendants=node=>[node,...node.children.flatMap(descendants)];

test('failed job preserves its message and exposes diagnostic details as plain text',()=>{
  const message='MORPH konnte seinen Rechendienst nicht bereitstellen.';
  const detail='Port 8188: <img src=x onerror="danger()"> gehört zu PID 15608.';
  const container=rendered({state:'error',error:message,error_code:'comfy_start',details:detail,outputs:[]});
  assert.ok(container.children.some(node=>node.tag==='p' && node.textContent===message));
  const disclosure=container.children.find(node=>node.tag==='details');
  assert.ok(disclosure,'Die eigentliche Startursache muss aufklappbar sein.');
  assert.equal(disclosure.open,false);
  assert.equal(disclosure.children.find(node=>node.tag==='summary').textContent,'Fehlerdetails');
  const text=disclosure.children.find(node=>node.tag==='pre').textContent;
  assert.match(text,/comfy_start/);assert.ok(text.includes(detail));
  assert.equal(descendants(disclosure).some(node=>node.tag==='img'),false);
});

test('optional language residency warnings remain visible as plain text with the actual job status',()=>{
  const warning='Ollama ist nicht erreichbar; der GPU-Speicher des Sprachmodells ist unbekannt. <img src=x onerror="danger()">';
  for(const state of ['preparing','running','completed']){
    const container=rendered({id:'JOB',state,warnings:[warning],outputs:[]}),nodes=descendants(container);
    assert.ok(nodes.some(node=>node.tag==='p' && node.textContent.includes(warning)),state);
    assert.equal(nodes.some(node=>node.tag==='img' || node.tag==='button'),false);
    assert.equal(nodes.some(node=>node.className==='error-text'),false);
    assert.equal(container.children[0].textContent,{preparing:'Wird vorbereitet',running:'Berechnung läuft',completed:'Fertig'}[state]);
  }
});

test('absent or malformed job warnings do not invent messages or interpret arbitrary objects',()=>{
  for(const warnings of [undefined,null,'unknown',{message:'unknown'},[null,{},false,'  ']]){
    const container=rendered({id:'JOB',state:'completed',warnings,outputs:[]});
    assert.equal(descendants(container).some(node=>node.tag==='p'),false);
  }
});

test('a generated image offers an explicit new project action without preparing another job',async()=>{
  const file={id:'GENERATED',name:'new.png',url:'/media/GENERATED',kind:'image'};let selected;
  const container=rendered({id:'JOB',state:'completed',workflow_id:'sdxl',outputs:[file]},{onProject:image=>{selected=image;}});
  assert.equal(selected,undefined);
  const button=descendants(container).find(node=>node.tag==='button' && /Bildprojekt/.test(node.textContent));
  assert.ok(button,'Neue Text-zu-Bild-Ergebnisse brauchen einen bewussten Einstieg in den Bildverlauf.');await button.listeners.click();assert.equal(selected,file);
});

test('a version storage failure keeps the completed image visible and offers only a receipt refresh',async()=>{
  let refreshed;const container=rendered({id:'JOB',state:'completed',outputs:[{id:'IMAGE',name:'done.png',kind:'image',url:'/media/IMAGE'}],versioning_error:'Der Datenträger ist vorübergehend nicht schreibbar.'},{onRefresh:id=>{refreshed=id;}});
  const nodes=descendants(container);assert.ok(nodes.some(node=>node.tag==='img' && node.src==='/media/IMAGE'));
  assert.ok(nodes.some(node=>node.textContent.includes('vorübergehend nicht schreibbar')));
  const button=nodes.find(node=>node.tag==='button' && /Versionsspeicherung/.test(node.textContent));assert.ok(button);assert.equal(refreshed,undefined);await button.listeners.click();assert.equal(refreshed,'JOB');
});

test('structured error details remain readable and absent details add no empty disclosure',()=>{
  const container=rendered({state:'error',error:'Anfrage abgelehnt.',details:{reason:'Knoten fehlt',node:'42'},outputs:[]});
  const disclosure=container.children.find(node=>node.tag==='details');
  assert.ok(disclosure,'Strukturierte Fehlerbelege dürfen nicht verschwinden.');
  assert.match(disclosure.children.find(node=>node.tag==='pre').textContent,/"reason": "Knoten fehlt"/);
  const plain=rendered({state:'error',error:'Kurzer Fehler',outputs:[]});
  assert.equal(plain.children.some(node=>node.tag==='details'),false);
});

const progressJob=(progress={},state='running')=>({id:'JOB',state,outputs:[],progress:{event:'progress',node_id:'42',node_type:'KSampler',value:3,max:12,percent:25,cached_nodes:[],observed_at:'2026-10-20T15:00:00Z',connection:'connected',revision:1,...progress}});
const visibleText=container=>descendants(container).map(node=>node.textContent).join('\n');

test('real node observations render accessible current-node steps without suggesting total progress',()=>{
  const container=rendered(progressJob({percent:90})),nodes=descendants(container),text=visibleText(container);
  const bar=nodes.find(node=>node.tag==='progress');assert.ok(bar,'Beobachtete Knotenschritte müssen sichtbar werden.');
  assert.equal(bar.value,3);assert.equal(bar.max,12);assert.equal(bar.attributes['aria-label'],'Knotenfortschritt');
  assert.match(text,/Knotenfortschritt: 25 %/);assert.match(text,/Schritt 3 von 12 im aktuellen Knoten/);assert.match(text,/KSampler.*42/);
  assert.doesNotMatch(text,/90 %|Gesamtfortschritt|Restzeit/);
});

test('a new executing node clears prior percentages and identifies its actual model loader as plain text',()=>{
  const malicious='<img src=x onerror="danger()">';
  const container=rendered(progressJob({event:'executing',node_id:'7',node_type:'UNETLoader '+malicious,value:3,max:12,percent:25}));
  const text=visibleText(container);
  assert.match(text,/Modellknoten/);assert.ok(text.includes('UNETLoader '+malicious));assert.match(text,/Knoten 7/);
  assert.equal(descendants(container).some(node=>node.tag==='progress' || node.tag==='img'),false);
  assert.doesNotMatch(text,/%|alle Modelle|Modelle geladen/);
});

test('an image loader is an ordinary node and disconnected model observations stay in the past',()=>{
  const image=rendered(progressJob({event:'executing',node_type:'ImageLoader'}));
  assert.match(visibleText(image),/Aktueller Knoten: ImageLoader/);assert.doesNotMatch(visibleText(image),/Modellknoten/);
  const model=rendered(progressJob({event:'executing',node_type:'UNETLoaderGGUF',connection:'unavailable'}));
  assert.match(visibleText(model),/Zuletzt gemeldeter Modellknoten/);assert.doesNotMatch(visibleText(model),/wird ausgeführt/);
});

test('nonfinite, malformed and impossible node steps never create a percentage',()=>{
  for(const pair of [[NaN,12],[Infinity,12],[3,Infinity],[-1,12],[13,12],[0,0],[3,-1],['3',12],[3,'12'],[null,12]]){
    const container=rendered(progressJob({value:pair[0],max:pair[1]}));
    assert.equal(descendants(container).some(node=>node.tag==='progress'),false,JSON.stringify(pair));
    assert.doesNotMatch(visibleText(container),/\d+\s*%/);
  }
  const zero=rendered(progressJob({value:0,max:12}));assert.match(visibleText(zero),/Knotenfortschritt: 0 %/);
});

test('queue, preparation and cached nodes never infer an automatic percentage',()=>{
  for(const state of ['preparing','submitting','queued']){
    const container=rendered(progressJob({},state));
    assert.equal(descendants(container).some(node=>node.tag==='progress'),false);
    assert.doesNotMatch(visibleText(container),/\d+\s*%/);
  }
  const cached=rendered(progressJob({event:'execution_cached',node_id:null,node_type:null,cached_nodes:['2','3']}));
  assert.match(visibleText(cached),/2 Knoten.*Zwischenspeicher/);assert.doesNotMatch(visibleText(cached),/\d+\s*%/);
});

test('a disconnected live source marks retained progress as historical while status polling continues',()=>{
  for(const connection of ['reconnecting','unavailable','closed']){
    const container=rendered(progressJob({connection})),text=visibleText(container);
    assert.match(text,/Letzte Fortschrittsmeldung/);assert.match(text,/Liveverbindung unterbrochen/);assert.match(text,/Status wird geprüft/);
    assert.match(text,/Schritt 3 von 12 im aktuellen Knoten/);assert.match(text,/Berechnung läuft/);
    assert.doesNotMatch(text,/Fertig|Abgebrochen/);
  }
});

test('execution completion and failure hints do not override an active job state',()=>{
  for(const event of ['execution_success','execution_error','execution_interrupted']){
    const container=rendered(progressJob({event}));
    assert.equal(container.children[0].textContent,'Berechnung läuft');
    assert.match(visibleText(container),/Status wird geprüft/);
    assert.equal(descendants(container).some(node=>node.tag==='progress'),false);
  }
});

test('terminal receipts remove stale live progress and retain their authoritative status',()=>{
  for(const [state,label] of [['completed','Fertig'],['error','Fehler'],['cancelled','Abgebrochen']]){
    const container=rendered(progressJob({},state));assert.equal(container.children[0].textContent,label);
    assert.equal(descendants(container).some(node=>node.tag==='progress'),false);
    assert.doesNotMatch(visibleText(container),/Knotenfortschritt|Liveverbindung|\d+\s*%/);
  }
});

test('actual preparation phases explain service startup, checking, upload and submission in German',()=>{
  for(const [phase,expected] of [['connecting',/Rechendienst wird verbunden/],['checking',/Workflow wird geprüft/],['uploading',/Eingabebilder werden übertragen/],['submitting',/Auftrag wird.*übergeben/]]){
    const container=rendered({id:'JOB',state:phase==='submitting'?'submitting':'preparing',phase,outputs:[]});
    assert.match(visibleText(container),expected);assert.doesNotMatch(visibleText(container),/Modelle geladen|\d+\s*%/);
  }
});
