const UNKNOWN='unbekannt';
const text=value=>typeof value==='string'?value.trim():'';
function memory(value){
  return typeof value==='number' && Number.isFinite(value) && value>=0
    ?(value/1024**3).toLocaleString('de-DE',{minimumFractionDigits:1,maximumFractionDigits:1})+' GiB':UNKNOWN;
}

export function createResources(container,{doc=document,request,onChange=()=>{}}){
  const node=(tag,className,copy)=>{const item=doc.createElement(tag);if(className)item.className=className;if(copy)item.textContent=copy;return item;};
  const heading=node('div','resources-heading'),title=node('h3','','Rechendienst · Speicher'),refreshButton=node('button','quiet small','Ressourcen aktualisieren');
  refreshButton.type='button';heading.append(title,refreshButton);
  const summary=node('div','resources-summary'),measured=node('p','muted small'),readError=node('p','error-text');readError.setAttribute('role','status');
  const details=node('details','resources-details'),detailsLabel=node('summary','','Ressourcendetails'),deviceDetails=node('div','muted small'),ram=node('p','muted small'),source=node('p','muted small');
  const modelState=node('p','muted small','Geladene Bildmodelle: vom Rechendienst nicht gemeldet.');
  const scope=node('p','muted small','Die Freigabe betrifft alle Bildmodelle im eigenen Rechendienst. Ollama bleibt unverändert. Andere direkte Nutzer des Rechendienstes lassen sich dabei nicht durch MORPH sperren.');
  const freeButton=node('button','quiet small','Bildmodelle im Rechendienst freigeben');freeButton.type='button';
  const reason=node('p','muted small'),outcome=node('p','resources-outcome');outcome.setAttribute('role','status');
  const emergency=node('div','resources-emergency'),emergencyHelp=node('p','muted small','Falls die normale Freigabe nicht reicht: Die Notfallfreigabe beendet den eigenen Rechendienst und leert dessen Modell-Caches. Er startet mit deinem nächsten Bildauftrag wieder. Laufende Aufträge sperren diese Aktion.');
  const emergencyButton=node('button','quiet small','Notfall: Speicher vollständig freigeben');emergencyButton.type='button';
  emergency.append(emergencyHelp,emergencyButton);
  details.append(detailsLabel,deviceDetails,ram,source,modelState,scope,freeButton,reason);container.append(heading,summary,measured,readError,details,emergency,outcome);
  let data=null,error='',blocked='',refreshing=false,freeing=false,revision=0,message='',messageError=false;
  const available=()=>data?.available===true && Array.isArray(data.devices);
  const permitted=()=>available() && data.unload?.allowed===true;
  function render(){
    summary.replaceChildren();deviceDetails.replaceChildren();
    if(available()){
      const devices=data.devices.filter(device=>device && typeof device==='object' && !Array.isArray(device));
      if(!devices.length)summary.append(node('p','','Gerätewerte nicht gemeldet.'));
      for(const device of devices){
        const name=text(device.name) || 'Gerät';
        summary.append(node('p','',name+' · VRAM '+memory(device.vram_used)+' / '+memory(device.vram_total)));
        deviceDetails.append(node('p','',[name,text(device.type),Number.isInteger(device.index)&&device.index>=0?'Gerät '+device.index:'', 'VRAM frei: '+memory(device.vram_free)].filter(Boolean).join(' · ')));
      }
    }else summary.append(node('p','','Ressourcen derzeit nicht verfügbar.'));
    const stamp=available() && text(data.measured_at),date=stamp && /^\d{4}-\d{2}-\d{2}T/.test(stamp)?new Date(stamp):null;
    measured.textContent=date && Number.isFinite(date.getTime())?'Gemessen: '+date.toLocaleString('de-DE'):'Messzeitpunkt: nicht gemeldet.';measured.title=stamp || '';
    ram.textContent='RAM: '+memory(available()?data.ram?.used:null)+' / '+memory(available()?data.ram?.total:null)+' · frei: '+memory(available()?data.ram?.free:null);
    source.textContent='Quelle: '+(text(data?.source) || 'nicht gemeldet');
    readError.textContent=error || text(data?.error);readError.hidden=!readError.textContent;
    refreshButton.disabled=refreshing || freeing;refreshButton.setAttribute('aria-busy',refreshing);
    freeButton.disabled=freeing || Boolean(blocked) || !permitted();freeButton.setAttribute('aria-busy',freeing);
    emergencyButton.disabled=freeing || Boolean(blocked) || !permitted();emergencyButton.setAttribute('aria-busy',freeing);
    reason.textContent=freeing?'Freigabe wird angefordert …':blocked || text(data?.unload?.reason) || (permitted()?'Freigabe ist für den eigenen, derzeit freien Rechendienst erlaubt.':'Freigabe ist derzeit nicht erlaubt.');
    outcome.textContent=message;outcome.hidden=!message;outcome.className='resources-outcome'+(messageError?' error-text':'');
  }
  async function refresh(){
    if(freeing)return;
    const current=++revision;refreshing=true;render();
    try{const reply=await request('/api/resources');if(current!==revision)return;data=reply;error='';}
    catch(cause){if(current!==revision)return;data=null;error=cause.message || 'Die Ressourcenmessung konnte nicht gelesen werden.';}
    finally{if(current===revision){refreshing=false;render();}}
  }
  async function free(){
    if(freeing || blocked || !permitted())return;
    ++revision;refreshing=false;freeing=true;message='';messageError=false;render();onChange();
    try{
      const receipt=await request('/api/resources/free',{method:'POST',body:{}});
      if(receipt?.accepted!==true)throw new Error(text(receipt?.message) || 'Der Rechendienst hat die Freigabe nicht bestätigt.');
      message='Freigabe angefordert. Das bestätigt noch keinen abgeschlossenen Entladevorgang. Aktualisierte Speicherwerte sind eine neue Messung.';
    }catch(cause){message='Freigabe nicht bestätigt: '+(cause.message || 'Antwort des Rechendienstes fehlt.');messageError=true;}
    finally{freeing=false;render();onChange();}
    await refresh();
  }
  async function emergencyFree(){
    if(freeing || blocked || !permitted())return;
    ++revision;refreshing=false;freeing=true;message='Notfallfreigabe läuft …';messageError=false;render();onChange();
    try{
      const receipt=await request('/api/resources/emergency-release',{method:'POST',body:{}});
      if(receipt?.completed!==true || receipt?.stopped!==true)throw new Error('Das Ende des eigenen Rechendienstes ist nicht bestätigt. Bitte den aktuellen Zustand prüfen.');
      message='Der eigene Rechendienst wurde beendet. Seine Modell-Caches sind freigegeben. Er startet mit deinem nächsten Bildauftrag wieder.';
    }catch(cause){message='Notfallfreigabe nicht bestätigt: '+(cause.message || 'Antwort fehlt. Bitte den Zustand prüfen.');messageError=true;}
    finally{freeing=false;render();onChange();}
    await refresh();
  }
  refreshButton.addEventListener('click',refresh);freeButton.addEventListener('click',free);emergencyButton.addEventListener('click',emergencyFree);render();
  return {refresh,free,setBlocked(value){const next=text(value);if(next!==blocked){blocked=next;render();}},get freeing(){return freeing;}};
}
