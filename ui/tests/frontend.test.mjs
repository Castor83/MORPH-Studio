import test from 'node:test';
import assert from 'node:assert/strict';
let forms, api;
try { forms = await import('../frontend/forms.js'); api = await import('../frontend/api.js'); }
catch (error) { if (error.code !== 'ERR_MODULE_NOT_FOUND') throw error; }

function storage() {
  const values = new Map();
  return {getItem:k=>values.get(k) ?? null,setItem:(k,v)=>values.set(k,v),removeItem:k=>values.delete(k)};
}

test('face workflow requires both correctly assigned pictures', () => {
  assert.ok(forms, 'Formularlogik fehlt');
  const workflow = {roles:[{id:'target'},{id:'source'}]};
  assert.equal(forms.requiredImagesPresent(workflow,{target:{id:'one'}}),false);
  assert.equal(forms.requiredImagesPresent(workflow,{target:{id:'one'},source:{id:'two'}}),true);
  assert.equal(forms.requiredImagesPresent({roles:[]},{image:{id:'one'}}),false);
});

test('simultaneous start clicks send once and retain request after lost response', async () => {
  assert.ok(api, 'API-Logik fehlt');
  const saved = storage();
  let calls = 0;
  const start = api.createStartGuard(async body => {calls++; await new Promise(r=>setTimeout(r,15)); throw new Error('Verbindung verloren');},saved,()=> '00000000-0000-4000-8000-000000000001');
  await Promise.allSettled([start({workflow_id:'sdxl',controls:{width:768},images:{}}),start({workflow_id:'sdxl',controls:{width:768},images:{}})]);
  assert.equal(calls,1);
  assert.equal(api.pendingRequest(saved).request_id,'00000000-0000-4000-8000-000000000001');
  await assert.rejects(start({workflow_id:'sdxl',controls:{},images:{}}));
  assert.equal(calls,1);
  api.finishRequest(saved,'different-id');
  assert.ok(api.pendingRequest(saved));
  api.finishRequest(saved,'00000000-0000-4000-8000-000000000001');
  assert.equal(api.pendingRequest(saved),null);
});

test('API errors remain human readable without automatic retry', async () => {
  assert.ok(api, 'API-Logik fehlt');
  let calls = 0;
  await assert.rejects(api.request('/api/models',{fetchFn:async (path,options) => {
    calls++;
    assert.equal(options.method,'GET');
    return {ok:false,status:503,json:async ()=>({ok:false,error:{message:'Lokaler Server nicht erreichbar.'}})};
  }}),/Lokaler Server nicht erreichbar/);
  assert.equal(calls,1);
});
