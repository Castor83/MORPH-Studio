import test from 'node:test';
import assert from 'node:assert/strict';
let proposals;
try { proposals=await import('../frontend/proposals.js'); }
catch(error) { if(error.code!=='ERR_MODULE_NOT_FOUND')throw error; }

const tools=[
  {id:'kontext',name:'Bild bearbeiten',roles:[{id:'image',label:'Ausgangsbild'}],issues:[],controls:{
    image_model:{kind:'model',label:'Bildmodell',default:'original',options:[]},
    prompt:{kind:'text',label:'Bildbeschreibung',default:'Ein rotes Haus'},
    width:{kind:'integer',label:'Breite',default:768},
    seed:{kind:'integer',label:'Zufallswert',default:42},
  }},
  {id:'reactor',name:'Gesicht austauschen',roles:[{id:'target',label:'Zielfoto'},{id:'source',label:'Quellgesicht'}],issues:[{message:'Eine Modelldatei fehlt.'}],controls:{
    image_model:{kind:'model',label:'Bildmodell',default:'face-default',options:[]},
    source_faces:{kind:'faces',label:'Quellgesichter',default:'0'},
    target_faces:{kind:'faces',label:'Zielgesichter',default:'0'},
  }},
];
const available=()=>assert.ok(proposals,'Werkzeugvorschläge fehlen');

test('taking a step keeps manually selected model, pictures and omitted controls for the same tool',()=>{
  available();
  const images={image:{id:'PHOTO',name:'mein-foto.png'}};
  const result=proposals.prepareProposalStep({workflow_id:'kontext',prompt:'Ein blaues Haus',controls:{width:1024,image_model:'unwanted',unknown:'ignore'}},tools,tools[0],{image_model:'manual',prompt:'Alte Beschreibung',width:640,seed:91},images);
  assert.deepEqual(result.controls,{image_model:'manual',prompt:'Ein blaues Haus',width:1024,seed:91});
  assert.equal(result.images,images);
  assert.equal(result.changedTool,false);
});

test('changing tools starts with target defaults and requires explicitly assigned pictures',()=>{
  available();
  const result=proposals.prepareProposalStep({workflow_id:'reactor',prompt:'',controls:{source_faces:'1',image_model:'unwanted'}},tools,tools[0],{image_model:'manual',width:640},{image:{id:'PHOTO'}});
  assert.deepEqual(result.controls,{image_model:'face-default',source_faces:'1',target_faces:'0'});
  assert.deepEqual(result.images,{});
  assert.equal(result.changedTool,true);
  assert.equal(result.workflow.name,'Gesicht austauschen');
});

test('unknown tools cannot change the form',()=>{
  available();
  assert.throws(()=>proposals.prepareProposalStep({workflow_id:'missing',prompt:'',controls:{}},tools,tools[0],{},{}),/Werkzeug/);
});

function element(tag){return {tag,children:[],listeners:{},textContent:'',append(...nodes){this.children.push(...nodes);},replaceChildren(...nodes){this.children=[...nodes];},addEventListener(event,handler){this.listeners[event]=handler;}};}
const descendants=node=>[node,...node.children.flatMap(descendants)];

test('proposal cards show human labels, missing picture roles and availability without raw controls',()=>{
  available();
  const container=element('section');
  proposals.renderProposals(container,{assistant_text:'Zuerst das Gesicht austauschen.',steps:[{workflow_id:'reactor',reason:'Damit das gewünschte Gesicht erhalten bleibt.',prompt:'',controls:{source_faces:'1',image_model:'hidden-model',unknown:'hidden-unknown'}}]},tools,tools[0],{},()=>{},{createElement:element});
  const nodes=descendants(container),texts=nodes.map(node=>node.textContent).join('\n');
  assert.match(texts,/Gesicht austauschen/);
  assert.match(texts,/Quellgesichter/);
  assert.match(texts,/Zielfoto/);
  assert.match(texts,/Quellgesicht/);
  assert.match(texts,/Eine Modelldatei fehlt/);
  assert.doesNotMatch(texts,/source_faces|workflow_id|hidden-model|hidden-unknown|reactor/);
  assert.equal(nodes.filter(node=>node.tag==='button').length,1);
});

test('each rendered step requires its own explicit selection',()=>{
  available();
  const chosen=[],container=element('section');
  const plan={assistant_text:'Zwei einzeln bestätigte Schritte.',steps:[{workflow_id:'kontext',reason:'Zuerst bearbeiten.',prompt:'Ein blaues Haus',controls:{width:1024}},{workflow_id:'reactor',reason:'Danach das Gesicht auswählen.',prompt:'',controls:{}}]};
  proposals.renderProposals(container,plan,tools,tools[0],{},index=>chosen.push(index),{createElement:element});
  assert.deepEqual(chosen,[]);
  const buttons=descendants(container).filter(node=>node.tag==='button');
  assert.equal(buttons.length,2);
  buttons[1].listeners.click();
  assert.deepEqual(chosen,[1]);
});

test('rendered prompts remain text and applied steps cannot be selected again',()=>{
  available();
  const chosen=[],container=element('section');
  proposals.renderProposals(container,{assistant_text:'Bitte prüfen.',steps:[{workflow_id:'kontext',reason:'Eine Änderung.',prompt:'<img src=x onerror=alert(1)>',controls:{width:1024}}]},tools,tools[0],{},index=>chosen.push(index),{createElement:element},new Set([0]));
  const nodes=descendants(container),button=nodes.find(node=>node.tag==='button');
  assert.equal(nodes.some(node=>node.tag==='img'),false);
  assert.ok(nodes.some(node=>node.textContent.includes('<img src=x onerror=alert(1)>')));
  assert.equal(button.disabled,true);
  button.listeners.click();
  assert.deepEqual(chosen,[]);
});

test('proposal differences show only changed non-model fields against the original form',()=>{
  const container=element('section');
  const original={instruction:'Nur das Haus umfärben.',workflow_id:'kontext',controls:{prompt:'Ein rotes Haus',width:640,seed:91,image_model:'manual'},workflow_defaults:{kontext:{prompt:'Ein rotes Haus',width:768,seed:42}}};
  proposals.renderProposals(container,{original,assistant_text:'Die übrigen Bildbereiche sollen bleiben.',steps:[{workflow_id:'kontext',reason:'Nur eine Farbänderung.',prompt:'Ein blaues Haus',controls:{width:1024,seed:91,image_model:'unwanted'}}]},tools,tools[0],{},()=>{},{createElement:element});
  const nodes=descendants(container),card=nodes.find(node=>node.className==='proposal-step');
  const changes=descendants(card).find(node=>node.className==='proposal-changes');
  assert.ok(changes,'Ein prüfbarer Vorher-Nachher-Vergleich fehlt.');
  assert.deepEqual(changes.children.filter(node=>node.tag==='dt').map(node=>node.textContent),['Bildbeschreibung','Breite']);
  const text=descendants(changes).map(node=>node.textContent).join('\n');
  assert.match(text,/Vorher: Ein rotes Haus/);assert.match(text,/Nachher: Ein blaues Haus/);
  assert.match(text,/Vorher: 640/);assert.match(text,/Nachher: 1024/);
  assert.doesNotMatch(text,/Zufallswert|Bildmodell|unwanted|manual/);
  assert.ok(nodes.some(node=>node.textContent==='Nur das Haus umfärben.'));
  assert.ok(nodes.some(node=>node.textContent==='Die übrigen Bildbereiche sollen bleiben.'));
});

test('each prompt stays visible separately even when unchanged and echoes are identified',()=>{
  const original={instruction:'Ein rotes Haus',workflow_id:'kontext',controls:{prompt:'Ein rotes Haus'}};
  const proposal={original,assistant_text:'Bitte prüfen.',steps:[{workflow_id:'kontext',reason:'Bild bearbeiten.',prompt:'Ein rotes Haus',controls:{}}]};
  const container=element('section');
  proposals.renderProposals(container,proposal,tools,tools[0],{},()=>{},{createElement:element});
  const card=descendants(container).find(node=>node.className==='proposal-step');
  const prompt=descendants(card).find(node=>node.className==='proposal-prompt');
  assert.ok(prompt,'Der vorgeschlagene Prompt fehlt in der Schrittkarte.');
  assert.ok(descendants(prompt).some(node=>node.textContent==='Ein rotes Haus'));
  assert.ok(descendants(prompt).some(node=>/Vorgeschlagener Bild-\/Videoprompt/.test(node.textContent)));
  assert.ok(descendants(card).some(node=>/Auftrag wortgleich/.test(node.textContent)));
  proposal.steps[0].prompt='Färbe nur das Haus blau. Erhalte die Umgebung.';
  proposals.renderProposals(container,proposal,tools,tools[0],{},()=>{},{createElement:element});
  const changedCard=descendants(container).find(node=>node.className==='proposal-step');
  assert.equal(descendants(changedCard).some(node=>/Auftrag wortgleich/.test(node.textContent)),false);
  assert.ok(descendants(changedCard).some(node=>node.textContent==='Färbe nur das Haus blau. Erhalte die Umgebung.'));
});

test('target tool differences retain their request-time defaults after that tool is adopted',()=>{
  const container=element('section');
  const proposal={original:{instruction:'Das Gesicht wählen.',workflow_id:'kontext',controls:{prompt:'Mein unveränderter Ausgangsprompt',width:640},workflow_defaults:{reactor:{source_faces:'0',target_faces:'0'}}},assistant_text:'Bitte das Zielfoto zuordnen.',steps:[{workflow_id:'reactor',reason:'Einzeln prüfen.',prompt:'',controls:{source_faces:'1',target_faces:'0'}}]};
  const render=(workflow,applied)=>proposals.renderProposals(container,proposal,tools,workflow,{},()=>{},{createElement:element},applied);
  render(tools[0],new Set());
  const before=descendants(container).find(node=>node.className==='proposal-changes');
  assert.ok(before,'Die Änderungen gegenüber den Werkzeug-Grundeinstellungen fehlen.');
  assert.deepEqual(before.children.filter(node=>node.tag==='dt').map(node=>node.textContent),['Quellgesichter']);
  assert.match(descendants(before).map(node=>node.textContent).join('\n'),/Vorher: 0[\s\S]*Nachher: 1/);
  render({...tools[1],controls:{...tools[1].controls,source_faces:{...tools[1].controls.source_faces,default:'1'}}},new Set([0]));
  const after=descendants(container).find(node=>node.className==='proposal-changes');
  assert.equal(descendants(after).map(node=>node.textContent).join('\n'),descendants(before).map(node=>node.textContent).join('\n'));
  assert.ok(descendants(container).some(node=>node.textContent==='Mein unveränderter Ausgangsprompt'));
});
