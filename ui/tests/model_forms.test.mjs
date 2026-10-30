import test from 'node:test';
import assert from 'node:assert/strict';
import * as forms from '../frontend/forms.js';

function element(tag){return {tag,children:[],value:'',hidden:false,dataset:{},classList:{add(){}},append(...x){this.children.push(...x)},replaceChildren(...x){this.children=x},addEventListener(event,fn){this[event]=fn},setAttribute(){}};}
const descendants=node=>[node,...node.children.flatMap(descendants)];
const workflow={controls:{image_model:{kind:'model',label:'Bildmodell',default:'checkpoints/one.safetensors',options:[{id:'checkpoints/one.safetensors',label:'SDXL · one',family:'sdxl',path:'E:/models/one',recommended_size:1024},{id:'checkpoints/two.safetensors',label:'SD 1.5 · two',family:'sd15',path:'E:/models/two',recommended_size:512}]},width:{kind:'integer',label:'Breite',default:768,min:16,max:16384,step:8}}};

test('model choice renders a select and changing it keeps manual dimensions',()=>{
  globalThis.document={createElement:element};
  try{
    const container=element('div');let changes=0;
    forms.renderControls(container,workflow,()=>changes++);
    const model=descendants(container).find(x=>x.name==='image_model');
    assert.ok(model,'Bildmodell muss auswählbar sein');
    assert.equal(model.children.length,2);
    model.value='checkpoints/two.safetensors';model.input({target:model});
    assert.equal(changes,1);
    const width=descendants(container).find(x=>x.name==='width');
    assert.equal(width.value,768);
    const hint=descendants(container).find(x=>x.tag==='small');
    assert.match(hint.textContent,/512/);
  }finally{delete globalThis.document;}
});

test('simple controls show only the main prompt while expert controls keep their defaults',()=>{
  globalThis.document={createElement:element};
  try{
    const tool={controls:{...workflow.controls,prompt:{kind:'text',label:'Dein Auftrag',default:'Färbe die Tasse blau.'},negative:{kind:'text',label:'Unerwünscht',default:'Unschärfe',advanced:true},seed:{kind:'integer',label:'Seed',default:17,min:0,max:9999,advanced:true}}};
    const visibleNames=(node,hidden=false)=>[...(node.name && !hidden && !node.hidden?[node.name]:[]),...node.children.flatMap(child=>visibleNames(child,hidden || node.hidden))];
    const simple=element('div');forms.renderControls(simple,tool,()=>{});
    assert.deepEqual(visibleNames(simple),['prompt']);
    assert.equal(descendants(simple).find(x=>x.name==='width').value,768);
    assert.equal(descendants(simple).find(x=>x.name==='seed').value,17);
    const expert=element('div');forms.renderControls(expert,tool,()=>{},true);
    assert.deepEqual(visibleNames(expert).sort(),['image_model','negative','prompt','seed','width']);
  }finally{delete globalThis.document;}
});

test('readiness request includes model IDs but leaves prompt and numbers out',()=>{
  assert.equal(typeof forms.modelSelections,'function','Modellauswahl für Prüfung fehlt');
  const form={elements:{namedItem:name=>({value:name==='image_model'?'checkpoints/two.safetensors':'768'})}};
  assert.deepEqual(forms.modelSelections(form,workflow),{image_model:'checkpoints/two.safetensors'});
});

test('applying a language proposal preserves the manually selected image model',()=>{
  const entries={image_model:{value:'checkpoints/two.safetensors'},width:{value:768}};
  forms.fillControls({elements:{namedItem:name=>entries[name]}},{image_model:'checkpoints/one.safetensors',width:512},workflow);
  assert.equal(entries.image_model.value,'checkpoints/two.safetensors');
  assert.equal(entries.width.value,512);
});
