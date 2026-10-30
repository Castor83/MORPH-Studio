const KEY = 'morph.pending-request.v1';

export async function request(path, {method='GET',body,fetchFn=globalThis.fetch}={}) {
  const headers = {};
  if (method !== 'GET') headers['X-MORPH-Request'] = '1';
  let payload;
  if (body instanceof FormData) payload = body;
  else if (body !== undefined) { headers['Content-Type'] = 'application/json'; payload = JSON.stringify(body); }
  let response;
  try { response = await fetchFn(path,{method,headers,body:payload,credentials:'same-origin',cache:'no-store'}); }
  catch { throw new Error('Die Verbindung zur MORPH-Oberfläche ist unterbrochen. Ein gestarteter Auftrag wird nicht automatisch wiederholt.'); }
  let envelope;
  try { envelope = await response.json(); }
  catch { throw new Error('Der lokale Dienst hat keine lesbare Antwort geliefert.'); }
  if (!response.ok || !envelope.ok) {
    const error = new Error(envelope.error?.message || `Der Dienst meldet Fehler ${response.status}.`);
    error.details = envelope.error?.details;
    throw error;
  }
  return envelope.data;
}

export function pendingRequest(storage=localStorage) {
  const saved = storage.getItem(KEY);
  if (!saved) return null;
  try { return JSON.parse(saved); }
  catch { throw new Error('Der gespeicherte Startbeleg ist nicht lesbar. Bitte das lokale Auftragsprotokoll prüfen.'); }
}

export function finishRequest(storage, requestId) {
  if (pendingRequest(storage)?.request_id === requestId) storage.removeItem(KEY);
}

export function createStartGuard(post,storage=localStorage,uuid=()=>crypto.randomUUID()) {
  let flight;
  return body => {
    if (flight) return flight;
    if (pendingRequest(storage)) return Promise.reject(new Error('Der letzte Start ist noch nicht abschließend geklärt. Bitte den Auftrag im Verlauf prüfen.'));
    const receipt = {...body,request_id:uuid()};
    // Persist before any network call. Reload never resubmits this body.
    storage.setItem(KEY,JSON.stringify(receipt));
    flight = Promise.resolve().then(()=>post(receipt));
    flight.finally(()=>{flight=undefined;}).catch(()=>{});
    return flight;
  };
}
