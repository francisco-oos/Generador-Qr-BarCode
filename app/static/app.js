const state = { catalog:null, csvRows:[], csvHeaders:[], assignments:[], lastSvg:'', lastTemplate:null, machineCaptures:null, lightburnArtifacts:[], lasergrblArtifacts:[], materialReference:null, calibration:null };
const $ = (id)=>document.getElementById(id);
const esc = (s)=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
function msg(el,text,type=''){ const d=document.createElement('div'); d.className='msg '+type; d.textContent=text; el.appendChild(d); }
function clear(el){ el.innerHTML=''; }
async function api(url, opts={}){ const r=await fetch(url,opts); if(!r.ok){ let t; try{t=await r.json()}catch{t=await r.text()} throw new Error(typeof t==='string'?t:JSON.stringify(t.detail??t)); } return r; }
function downloadBlob(blob,name){ const a=document.createElement('a'); a.href=URL.createObjectURL(blob); a.download=name; a.click(); setTimeout(()=>URL.revokeObjectURL(a.href),2000); }

function setTab(name){ document.querySelectorAll('.tab').forEach(x=>x.classList.remove('active')); document.querySelectorAll('.tabs button').forEach(x=>x.classList.remove('active')); $('tab-'+name).classList.add('active'); document.querySelector(`[data-tab="${name}"]`).classList.add('active'); if(name==='history') loadHistory(); if(name==='materials' && !state.materialReference) loadMaterialReference(); }
$('tabs').addEventListener('click',e=>{ if(e.target.dataset.tab) setTab(e.target.dataset.tab); });

function sourceFields(template){ const expected=(template.expected_fields||[]).filter(Boolean); if(expected.length)return expected; const out=new Set(); for(const el of template.elements||[]){ if(el.source) el.source.split('|').forEach(x=>out.add(x.trim())); } return [...out].filter(Boolean); }
function selectedTemplate(selectId){ return state.catalog.templates.find(t=>t.id===$(selectId).value); }
function fillSelect(el, items, label=(x)=>x.name){ el.innerHTML=items.map(x=>`<option value="${esc(x.id)}">${esc(label(x))}</option>`).join(''); }

async function loadAll(){
  applyExperienceMode(localStorage.getItem('markingStudioMode')||'guided'); const lic=await (await api('/api/license')).json(); $('licenseJson').textContent=JSON.stringify(lic,null,2); $('licenseBadge').textContent=lic.valid?`Licencia ${lic.payload?.edition||''} · válida`:`Licencia no válida`; $('licenseBadge').className='badge '+(lic.valid?'ok':'bad');
  if(!lic.valid) return;
  state.catalog=await (await api('/api/catalog')).json();
  ['individualTemplate','batchTemplate','configTemplate'].forEach(id=>fillSelect($(id),state.catalog.templates));
  fillSelect($('configJig'),state.catalog.jigs,x=>`${x.name} · ${x.capacity} pos.`);
  fillSelect($('machineImportProfile'),state.catalog.machines); fillSelect($('shopPresetMachine'),state.catalog.machines); fillSelect($('calibrationJig'),state.catalog.jigs,x=>`${x.name} · ${x.capacity} pos.`);
  renderMachineCards(); renderScannerCards(); renderIndividualFields(); updateBatchJigs(); loadConfigEditors();
  await loadMachineCaptures(); await refreshPorts();
}
function renderMachineCards(){ $('machinesList').innerHTML=state.catalog.machines.map(m=>`<div class="machine-card"><strong>${esc(m.name)}</strong><div>${esc(m.controller)} · ${m.bed_width_mm}×${m.bed_height_mm} mm · ${esc(m.connection)}</div><div class="muted">Vector: ${esc(m.vector_formats.join(', '))}</div><div class="muted">Salida directa: ${m.direct_machine_output_enabled?'sí':'no (handoff seguro)'}</div></div>`).join(''); }
function renderScannerCards(){ $('scannersList').innerHTML=(state.catalog.scanners||[]).map(s=>`<div class="machine-card"><strong>${esc(s.name)}</strong><div>${esc(s.technology)} · ${esc(s.interfaces.join(', '))}</div><div class="muted">${esc(s.symbologies.join(', '))}</div><div class="muted">QR: ${s.supports_qr?'sí':'no'} · Data Matrix: ${s.supports_datamatrix?'sí':'no'}</div></div>`).join(''); }

function renderIndividualFields(){ const t=selectedTemplate('individualTemplate'); state.lastTemplate=t; const fields=sourceFields(t); $('individualFields').innerHTML=fields.map(f=>{const rule=(t.input_rules||[]).find(r=>r.field===f); const prefix=rule?.manual_prefix_enabled?`<span class="hint">Prefijo manual automático: <strong>${esc(rule.manual_prefix)}</strong> · CSV: ${esc(rule.imported_values)}</span>`:''; return `<label>${esc(f)}<input data-field="${esc(f)}" placeholder="${esc(f)}" />${prefix}</label>`;}).join(''); const defaults=t.metadata?.example_data||{}; $('individualFields').querySelectorAll('input').forEach(i=>{ if(defaults[i.dataset.field]) i.value=defaults[i.dataset.field]; }); renderIndividual(); }
$('individualTemplate').addEventListener('change',renderIndividualFields);
async function renderIndividual(){ const t=selectedTemplate('individualTemplate'); const data={}; $('individualFields').querySelectorAll('input').forEach(i=>data[i.dataset.field]=i.value.trim()); clear($('renderWarnings')); try{ const r=await api('/api/render',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({template_id:t.id,data,capture_mode:'manual',output:'svg'})}); const j=await r.json(); state.lastSvg=j.svg; $('preview').innerHTML=j.svg; $('markSize').textContent=`${j.width_mm} × ${j.height_mm} mm`; j.warnings.forEach(w=>msg($('renderWarnings'),w,'warn')); if(j.calibration_required) msg($('renderWarnings'),'Plantilla pendiente de calibración física antes de producción.','warn'); }catch(e){msg($('renderWarnings'),e.message,'bad');}}
$('renderBtn').addEventListener('click',renderIndividual);
$('downloadSvgBtn').addEventListener('click',()=>{ if(state.lastSvg) downloadBlob(new Blob([state.lastSvg],{type:'image/svg+xml'}),`${$('individualTemplate').value}.svg`); });
$('downloadPngBtn').addEventListener('click',async()=>{ const t=selectedTemplate('individualTemplate'); const data={}; $('individualFields').querySelectorAll('input').forEach(i=>data[i.dataset.field]=i.value.trim()); try{ const r=await api('/api/render',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({template_id:t.id,data,capture_mode:'manual',output:'png',dpi:600})}); downloadBlob(await r.blob(),`${t.id}-600dpi.png`);}catch(e){msg($('renderWarnings'),e.message,'bad');} });

function updateBatchJigs(){ const t=selectedTemplate('batchTemplate'); const exact=state.catalog.jigs.filter(j=>j.template_id===t.id); const category=state.catalog.jigs.filter(j=>j.target_category===t.category && !exact.some(e=>e.id===j.id)); const generic=state.catalog.jigs.filter(j=>j.id==='single_asset' && !exact.some(e=>e.id===j.id)); const list=[...exact,...category,...generic]; fillSelect($('batchJig'),list.length?list:state.catalog.jigs,x=>`${x.name} · ${x.capacity} pos.`); updateJigSummary(); buildMapping(); }
$('batchTemplate').addEventListener('change',updateBatchJigs); $('batchJig').addEventListener('change',updateJigSummary);
function updateJigSummary(){ if(!state.catalog)return; const j=state.catalog.jigs.find(x=>x.id===$('batchJig').value); $('jigCapacity').textContent=j?`${j.capacity} posiciones · ${j.calibration_required?'calibración requerida':'aprobado'}`:''; if(j){ updateBatchProgress(); $('jigGrid').style.gridTemplateColumns=`repeat(${j.grid.cols}, minmax(0,1fr))`; $('jigGrid').innerHTML=j.slots.map(s=>`<div class="slot" data-slot="${s.slot_index}"><div>Pos. ${s.slot_index}</div><div class="slot-id muted">vacía</div></div>`).join(''); } }

$('csvFile').addEventListener('change',async()=>{ clear($('csvInfo')); const f=$('csvFile').files[0]; if(!f)return; const fd=new FormData(); fd.append('file',f); try{ const r=await api('/api/csv/inspect',{method:'POST',body:fd}); const j=await r.json(); state.csvRows=j.rows; state.csvHeaders=j.headers; $('batchOffset').value=0; msg($('csvInfo'),`${j.count} registros · columnas: ${j.headers.join(', ')}`,'ok'); buildMapping(); updateBatchProgress(); }catch(e){msg($('csvInfo'),e.message,'bad');} });
async function generateSeries(){ clear($('csvInfo')); const body={field:$('seriesField').value.trim(),prefix:$('seriesPrefix').value,start:Number($('seriesStart').value)||0,count:Number($('seriesCount').value)||1,width:Number($('seriesWidth').value)||0,suffix:$('seriesSuffix').value}; try{ const r=await api('/api/series/generate',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify(body)}); const j=await r.json(); state.csvRows=j.rows; state.csvHeaders=[j.field]; $('batchOffset').value=0; buildMapping(); updateBatchProgress(); msg($('csvInfo'),`${j.count} registros generados · ${j.first} → ${j.last}`,'ok'); msg($('csvInfo'),j.warning,'warn'); }catch(e){msg($('csvInfo'),e.message,'bad');} }
$('generateSeriesBtn').addEventListener('click',generateSeries);

function updateBatchProgress(){ if(!state.catalog||!state.csvRows.length){$('batchProgress').textContent='Sin lote cargado.';return;} const jig=state.catalog.jigs.find(x=>x.id===$('batchJig').value); if(!jig)return; const total=state.csvRows.length; const cap=jig.capacity; const offset=Math.max(0,Number($('batchOffset').value)||0); const totalBatches=Math.ceil(total/cap); const current=Math.min(totalBatches,Math.floor(offset/cap)+1); const end=Math.min(total,offset+cap); $('batchProgress').innerHTML=`Lote <strong>${current}</strong> de <strong>${totalBatches}</strong> · registros ${offset+1}–${end} de ${total} · capacidad ${cap}`; }
function norm(s){return String(s).toLowerCase().replace(/[^a-z0-9]/g,'');}
function bestHeader(field){ if(!state.csvHeaders.length)return''; const exact=state.csvHeaders.find(h=>norm(h)===norm(field)); if(exact)return exact; const synonyms={manufacturer_id:['nodo','node','serial','serie','id','numero','numnodo','q'],asset_id:['assetid','activo','idactivo','id'],economic_number:['economico','numeroeconomico','noeconomico','id'],serial:['serial','serie','sn'],operational_id:['operationalid','idoperativo','nodo','serial']}; for(const s of synonyms[field]||[]){ const h=state.csvHeaders.find(x=>norm(x)===s); if(h)return h; } return ''; }
function buildMapping(){ if(!state.catalog)return; const t=selectedTemplate('batchTemplate'); const fields=sourceFields(t); $('fieldMapping').innerHTML=fields.map(f=>{const opts=['',...state.csvHeaders].map(h=>`<option value="${esc(h)}" ${h===bestHeader(f)?'selected':''}>${h?esc(h):'— sin mapear —'}</option>`).join('');return `<label>${esc(f)}<select data-mapfield="${esc(f)}">${opts}</select></label>`;}).join(''); }
function mappedRows(){ const maps={}; $('fieldMapping').querySelectorAll('select').forEach(s=>{if(s.value)maps[s.dataset.mapfield]=s.value;}); return state.csvRows.map(r=>{const x={...r}; for(const [target,src] of Object.entries(maps)) x[target]=r[src]??''; return x;}); }
function candidateId(r){return r.manufacturer_id||r.operational_id||r.asset_id||r.serial||r.economic_number||'';}
function prepareBatch(){ clear($('batchMessages')); if(!state.csvRows.length){msg($('batchMessages'),'Cargue un CSV primero.','bad');return;} const jig=state.catalog.jigs.find(x=>x.id===$('batchJig').value); const rows=mappedRows(); const offset=Math.max(0,Number($('batchOffset').value)||0); const subset=rows.slice(offset,offset+jig.capacity); state.assignments=subset.map((r,i)=>({slot_index:jig.slots[i].slot_index,row_index:offset+i,physical_id:''})); renderAssignments(rows,jig); updateBatchProgress(); }
$('prepareBatchBtn').addEventListener('click',prepareBatch); $('batchOffset').addEventListener('change',updateBatchProgress); $('nextBatchBtn').addEventListener('click',()=>{ if(!state.csvRows.length)return; const jig=state.catalog.jigs.find(x=>x.id===$('batchJig').value); const next=(Math.max(0,Number($('batchOffset').value)||0)+jig.capacity); if(next>=state.csvRows.length){ clear($('batchMessages')); msg($('batchMessages'),'Ya está en el último lote.','warn'); return;} $('batchOffset').value=next; prepareBatch(); });
function renderAssignments(rows,jig){ $('jigGrid').querySelectorAll('.slot').forEach(s=>{s.classList.remove('assigned');s.querySelector('.slot-id').textContent='vacía';}); for(const a of state.assignments){ const cell=$('jigGrid').querySelector(`[data-slot="${a.slot_index}"]`); if(cell){cell.classList.add('assigned');cell.querySelector('.slot-id').textContent=candidateId(rows[a.row_index]);} }
  $('assignmentTable').innerHTML=`<div class="table-wrap"><table><thead><tr><th>Posición</th><th>Fila CSV</th><th>Esperado</th><th>ID escrito / leído físicamente</th><th>Estado</th></tr></thead><tbody>${state.assignments.map((a,i)=>{const expected=candidateId(rows[a.row_index]);return `<tr><td>${a.slot_index}</td><td>${a.row_index+1}</td><td><strong>${esc(expected)}</strong></td><td><input data-phys="${i}" value="${esc(a.physical_id)}" autocomplete="off"></td><td data-match="${i}" class="muted">pendiente</td></tr>`;}).join('')}</tbody></table></div>`;
  $('assignmentTable').querySelectorAll('[data-phys]').forEach(inp=>inp.addEventListener('input',()=>{const i=Number(inp.dataset.phys);state.assignments[i].physical_id=inp.value;const expected=candidateId(rows[state.assignments[i].row_index]);const ok=inp.value.trim().toUpperCase()===String(expected).trim().toUpperCase();const td=$('assignmentTable').querySelector(`[data-match="${i}"]`);td.textContent=inp.value?(ok?'coincide':'NO coincide'):'pendiente';td.className=inp.value?(ok?'status-ok':'status-bad'):'muted';})); }
$('simulationFillBtn').addEventListener('click',()=>{const rows=mappedRows();state.assignments.forEach(a=>a.physical_id=candidateId(rows[a.row_index]));const jig=state.catalog.jigs.find(x=>x.id===$('batchJig').value);renderAssignments(rows,jig);msg($('batchMessages'),'Confirmaciones prellenadas solo para simulación/demo.','warn');});
$('exportBatchBtn').addEventListener('click',async()=>{clear($('batchMessages')); if(!state.assignments.length){msg($('batchMessages'),'Prepare posiciones primero.','bad');return;} const rows=mappedRows(); const body={template_id:$('batchTemplate').value,jig_id:$('batchJig').value,material_preset_id:$('batchMaterialPreset').value?Number($('batchMaterialPreset').value):null,rows,assignments:state.assignments,require_physical_confirmation:$('requireConfirmation').checked,output_dpi:300}; try{ const r=await api('/api/batch/export',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify(body)}); const job=r.headers.get('X-Job-Id'); downloadBlob(await r.blob(),`marking-job-${job?.slice(0,8)||'batch'}.zip`); msg($('batchMessages'),`Trabajo exportado y registrado: ${job}`,'ok'); const jig=state.catalog.jigs.find(x=>x.id===$('batchJig').value); const offset=Math.max(0,Number($('batchOffset').value)||0); if(offset+jig.capacity<state.csvRows.length) msg($('batchMessages'),'Lote listo. Use «Siguiente lote» para continuar sin recalcular posiciones.','ok'); }catch(e){msg($('batchMessages'),e.message,'bad');} });

$('verifyBtn').addEventListener('click',async()=>{clear($('verifyResult'));try{const r=await api('/api/scan/verify',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({expected:$('verifyExpected').value,scanned:$('verifyScanned').value,normalize:$('verifyNormalize').checked})});const j=await r.json();msg($('verifyResult'),j.matched?'COINCIDE — marcado verificado':'NO COINCIDE — no liberar el equipo',j.matched?'ok':'bad');if(j.history_update)msg($('verifyResult'),JSON.stringify(j.history_update),j.history_update.updated?'ok':'warn');}catch(e){msg($('verifyResult'),e.message,'bad');}});
$('verifyScanned').addEventListener('keydown',e=>{if(e.key==='Enter')$('verifyBtn').click();});

function loadConfigEditors(){ const t=selectedTemplate('configTemplate'); $('templateJson').value=JSON.stringify(t,null,2); const fields=sourceFields(t); $('ruleField').innerHTML=fields.map(f=>`<option value="${esc(f)}">${esc(f)}</option>`).join(''); loadInputRuleForm(); const j=state.catalog.jigs.find(x=>x.id===$('configJig').value); $('jigJson').value=JSON.stringify(Object.fromEntries(Object.entries(j).filter(([k])=>!['capacity','slots'].includes(k))),null,2); }
function loadInputRuleForm(){ const t=selectedTemplate('configTemplate'); const field=$('ruleField').value; const r=(t.input_rules||[]).find(x=>x.field===field)||{}; $('rulePrefixEnabled').checked=!!r.manual_prefix_enabled; $('rulePrefix').value=r.manual_prefix||''; $('ruleSuffixEnabled').checked=!!r.manual_suffix_enabled; $('ruleSuffix').value=r.manual_suffix||''; $('ruleImportedMode').value=r.imported_values||'as_is'; $('ruleUppercase').checked=!!r.uppercase; }
$('configTemplate').addEventListener('change',loadConfigEditors); $('configJig').addEventListener('change',loadConfigEditors); $('ruleField').addEventListener('change',loadInputRuleForm);
$('saveInputRuleBtn').addEventListener('click',async()=>{clear($('inputRuleMsg')); try{const body={template_id:$('configTemplate').value,field:$('ruleField').value,manual_prefix_enabled:$('rulePrefixEnabled').checked,manual_prefix:$('rulePrefix').value,manual_suffix_enabled:$('ruleSuffixEnabled').checked,manual_suffix:$('ruleSuffix').value,imported_values:$('ruleImportedMode').value,uppercase:$('ruleUppercase').checked}; const r=await api('/api/templates/input-rule',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify(body)}); const j=await r.json(); const idx=state.catalog.templates.findIndex(t=>t.id===j.template.id); if(idx>=0) state.catalog.templates[idx]=j.template; $('templateJson').value=JSON.stringify(j.template,null,2); msg($('inputRuleMsg'),'Regla guardada. La captura manual aplicará el prefijo/sufijo; CSV seguirá la política seleccionada.','ok'); renderIndividualFields();}catch(e){msg($('inputRuleMsg'),e.message,'bad');}});
$('saveTemplateBtn').addEventListener('click',async()=>{clear($('templateSaveMsg'));try{const obj=JSON.parse($('templateJson').value);await api('/api/templates/save',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({template:obj})});msg($('templateSaveMsg'),'Plantilla guardada. Recargue la aplicación para refrescar el catálogo.','ok');}catch(e){msg($('templateSaveMsg'),e.message,'bad');}});
$('saveJigBtn').addEventListener('click',async()=>{clear($('jigSaveMsg'));try{const obj=JSON.parse($('jigJson').value);await api('/api/jigs/save',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({jig:obj})});msg($('jigSaveMsg'),'Jig guardado. Recargue la aplicación para refrescar el catálogo.','ok');}catch(e){msg($('jigSaveMsg'),e.message,'bad');}});

async function loadHistory(){ if(!state.catalog)return; try{const j=await (await api('/api/history?limit=200')).json(); $('historyTable').innerHTML=`<table><thead><tr><th>Fecha</th><th>Activo</th><th>Plantilla</th><th>Pos.</th><th>Estado</th><th>Verificado</th></tr></thead><tbody>${j.items.map(x=>`<tr><td>${esc(x.created_at)}</td><td><strong>${esc(x.asset_key)}</strong></td><td>${esc(x.template_id)}</td><td>${x.slot_index??''}</td><td>${esc(x.status)}</td><td>${esc(x.verified_at||'')}</td></tr>`).join('')}</tbody></table>`;}catch(e){$('historyTable').textContent=e.message;}}
$('refreshHistoryBtn').addEventListener('click',loadHistory);



function prettySuggested(suggested){
  if(!suggested || !Object.keys(suggested).length) return 'Sin parámetros de producción publicados';
  const parts=[];
  if(Array.isArray(suggested.speed_mm_min)) parts.push(`velocidad ${suggested.speed_mm_min[0]}–${suggested.speed_mm_min[1]} mm/min`);
  if(Array.isArray(suggested.power_percent)) parts.push(`potencia ${suggested.power_percent[0]}–${suggested.power_percent[1]}%`);
  if(Array.isArray(suggested.passes)) parts.push(`pasadas ${suggested.passes[0]}–${suggested.passes[1]}`);
  if(suggested.conservative_start_speed_mm_min!=null) parts.push(`inicio conservador ${suggested.conservative_start_speed_mm_min} mm/min @ ${suggested.conservative_start_power_percent}%`);
  if(suggested.recommended_test) parts.push('incluye rango sugerido para Material Test');
  if(suggested.examples_speed_power_passes) parts.push('incluye ejemplos de corte (no preset de grabado)');
  if(suggested.cut_reference_speed_mm_min) parts.push('incluye referencia de corte');
  return parts.join(' · ') || JSON.stringify(suggested);
}
function materialStatusClass(item){
  const bad=['unsafe','unknown','high_caution'];
  if(bad.includes(item.compatibility) || String(item.status||'').includes('blocked') || String(item.status||'').includes('do_not')) return 'bad';
  if(String(item.status||'').includes('validated')) return 'ok';
  return 'warn';
}
function renderMaterialItems(items){
  if(!items.length) return '<span class="muted">Sin coincidencias.</span>';
  return items.map(m=>`<div class="material-card ${materialStatusClass(m)}"><div class="panel-head"><strong>${esc(m.name)}</strong><span class="pill">${esc(m.category)} · ${esc(m.operation)}</span></div><div>${esc(prettySuggested(m.suggested))}</div><div class="muted">Estado: ${esc(m.status)} · compatibilidad: ${esc(m.compatibility)}</div>${(m.notes||[]).map(n=>`<div class="hint">• ${esc(n)}</div>`).join('')}</div>`).join('');
}
async function loadMaterialReference(){
  clear($('materialPolicy')); $('materialsResults').innerHTML='';
  const q=$('materialSearch').value.trim(); const cat=$('materialCategory').value;
  const params=new URLSearchParams(); if(q)params.set('q',q); if(cat)params.set('category',cat);
  try{
    const j=await (await api('/api/materials/reference?'+params.toString())).json(); state.materialReference=j;
    msg($('materialPolicy'),'Prioridad: ajuste validado por el área > recomendación específica > rango investigado > Material Test conservador.','ok');
    msg($('materialPolicy'),j.policy?.unknown_material_rule||'No grabar materiales desconocidos sin confirmar composición.','warn');
    $('materialsResults').innerHTML=renderMaterialItems(j.materials||[]);
  }catch(e){msg($('materialPolicy'),e.message,'bad');}
}
$('searchMaterialsBtn').addEventListener('click',loadMaterialReference);
$('materialSearch').addEventListener('keydown',e=>{if(e.key==='Enter')loadMaterialReference();});

async function searchPhoneReference(){
  const brand=$('phoneBrand').value.trim(); const model=$('phoneModel').value.trim(); $('phoneResults').innerHTML='';
  if(!brand && !model){$('phoneResults').innerHTML='<div class="msg warn">Indique al menos la marca o el modelo.</div>';return;}
  const params=new URLSearchParams({brand,model});
  try{
    const j=await (await api('/api/materials/phone?'+params.toString())).json();
    const items=j.matches||[];
    $('phoneResults').innerHTML=items.length?items.map(p=>`<div class="material-card warn"><div class="panel-head"><strong>${esc(p.brand)} ${esc(p.model)}</strong><span class="pill">${esc(p.direct_laser_policy)}</span></div><div class="muted">${esc(p.battery||'')}</div>${(p.surface_evidence||[]).map(x=>`<div>• ${esc(x)}</div>`).join('')}${(p.notes||[]).map(x=>`<div class="hint">• ${esc(x)}</div>`).join('')}</div>`).join(''):'<div class="msg warn">No hay una ficha exacta en el catálogo. Trátelo como teléfono ensamblado de superficie no confirmada y capture primero el ajuste que ya usa el área o identifique el material exacto.</div>';
  }catch(e){$('phoneResults').innerHTML=`<div class="msg bad">${esc(e.message)}</div>`;}
}
$('searchPhoneBtn').addEventListener('click',searchPhoneReference);
$('phoneModel').addEventListener('keydown',e=>{if(e.key==='Enter')searchPhoneReference();});

async function discoverLightBurn(){
  clear($('lightburnDiscoveryMsg')); $('lightburnArtifact').innerHTML='<option value="">— buscando —</option>';
  try{
    const j=await (await api('/api/machine/lightburn/discover')).json(); state.lightburnArtifacts=j.artifacts||[];
    $('lightburnArtifact').innerHTML=state.lightburnArtifacts.length?'<option value="">— seleccione —</option>'+state.lightburnArtifacts.map((a,i)=>`<option value="${i}">${esc(a.name)} · ${Math.ceil((a.size||0)/1024)} KiB</option>`).join(''):'<option value="">— no se encontraron archivos —</option>';
    msg($('lightburnDiscoveryMsg'),`Rutas revisadas: ${(j.roots||[]).join(' · ') || 'ninguna'} · artefactos: ${state.lightburnArtifacts.length}.`,'ok');
  }catch(e){msg($('lightburnDiscoveryMsg'),e.message,'bad');}
}
$('discoverLightBurnBtn').addEventListener('click',discoverLightBurn);
$('importDetectedLightBurnBtn').addEventListener('click',async()=>{
  clear($('lightburnDiscoveryMsg')); const idx=$('lightburnArtifact').value;
  if(idx===''){msg($('lightburnDiscoveryMsg'),'Seleccione un artefacto detectado.','warn');return;}
  const item=state.lightburnArtifacts[Number(idx)]; if(!item){msg($('lightburnDiscoveryMsg'),'Selección inválida.','bad');return;}
  try{
    const r=await api('/api/machine/lightburn/import-local',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({path:item.path,machine_profile_id:$('machineImportProfile').value||null})});
    const j=await r.json(); $('machineImportResult').textContent=JSON.stringify(j,null,2); msg($('lightburnDiscoveryMsg'),`Importado en solo lectura: ${j.source_type}. Presets detectados: ${j.material_preset_count}.`,'ok'); await loadMachineCaptures();
  }catch(e){msg($('lightburnDiscoveryMsg'),e.message,'bad');}
});


async function loadMachineCaptures(){
  if(!state.catalog)return;
  try{
    state.machineCaptures=await (await api('/api/machine/captures?limit=100')).json();
    const presets=state.machineCaptures.material_presets||[];
    $('batchMaterialPreset').innerHTML='<option value="">— ninguno / definir en LightBurn —</option>'+presets.map(p=>`<option value="${p.id}">${esc(p.material||'Material')} · ${esc(p.description||p.operation||'preset')} · ${esc(p.source_name)}</option>`).join('');
    const caps=state.machineCaptures.captures||[];
    $('capturesTable').innerHTML=caps.length?`<table><thead><tr><th>Fecha</th><th>Fuente</th><th>Archivo/puerto</th><th>Máquina</th><th>SHA-256</th></tr></thead><tbody>${caps.map(c=>`<tr><td>${esc(c.created_at)}</td><td>${esc(c.source_type)}</td><td>${esc(c.source_name)}</td><td>${esc(c.machine_profile_id||'')}</td><td><code>${esc((c.sha256||'').slice(0,16))}…</code></td></tr>`).join('')}</tbody></table>`:'<span class="muted">Sin capturas todavía.</span>';
  }catch(e){console.error(e);}
}
$('refreshCapturesBtn').addEventListener('click',loadMachineCaptures);

async function refreshPorts(){
  if(!state.catalog)return;
  clear($('grblMsg'));
  try{const j=await (await api('/api/machine/ports')).json(); const ports=j.ports||[]; $('serialPort').innerHTML=ports.length?ports.map(p=>`<option value="${esc(p.device)}">${esc(p.device)} · ${esc(p.description||p.product||'serial')}</option>`).join(''):'<option value="">— no se detectaron puertos —</option>';}
  catch(e){msg($('grblMsg'),e.message,'bad');}
}
$('refreshPortsBtn').addEventListener('click',refreshPorts);
$('probeGrblBtn').addEventListener('click',async()=>{
  clear($('grblMsg')); $('grblResult').textContent=''; const port=$('serialPort').value; if(!port){msg($('grblMsg'),'No hay puerto seleccionado. Conecte la grabadora por USB y cierre LightBurn/LaserGRBL si tienen abierto el puerto.','warn');return;}
  try{const r=await api('/api/machine/grbl/probe',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({port,baud:Number($('serialBaud').value),machine_profile_id:$('machineImportProfile').value})}); const j=await r.json(); $('grblResult').textContent=JSON.stringify(j,null,2); msg($('grblMsg'),'Lectura segura completada: sólo se enviaron $I y $$. No se modificó la máquina.','ok'); await loadMachineCaptures();}
  catch(e){msg($('grblMsg'),e.message,'bad');}
});
$('importMachineConfigBtn').addEventListener('click',async()=>{
  clear($('machineImportMsg')); $('machineImportResult').textContent=''; const f=$('machineConfigFile').files[0]; if(!f){msg($('machineImportMsg'),'Seleccione un archivo .clb, .lbset, .lbmt, .lbprefs, prefs.ini, .lbrn2, .lbzip o texto de $$.','warn');return;}
  const fd=new FormData(); fd.append('file',f); const profile=$('machineImportProfile').value; const url='/api/machine/import'+(profile?`?machine_profile_id=${encodeURIComponent(profile)}`:'');
  try{const r=await api(url,{method:'POST',body:fd}); const j=await r.json(); $('machineImportResult').textContent=JSON.stringify(j,null,2); msg($('machineImportMsg'),`Importado: ${j.source_type}. Presets detectados: ${j.material_preset_count}.`,'ok'); await loadMachineCaptures();}
  catch(e){msg($('machineImportMsg'),e.message,'bad');}
});



function applyExperienceMode(mode){
  const expert=mode==='expert'; document.body.classList.toggle('expert-mode',expert);
  $('guidedModeBtn')?.classList.toggle('active',!expert); $('expertModeBtn')?.classList.toggle('active',expert);
  localStorage.setItem('markingStudioMode',expert?'expert':'guided');
}
$('guidedModeBtn').addEventListener('click',()=>applyExperienceMode('guided'));
$('expertModeBtn').addEventListener('click',()=>applyExperienceMode('expert'));

$('saveShopPresetBtn').addEventListener('click',async()=>{
  clear($('shopPresetMsg'));
  const body={
    name:$('shopPresetName').value.trim(), machine_profile_id:$('shopPresetMachine').value,
    material:$('shopPresetMaterial').value.trim(), surface_or_model:$('shopPresetSurface').value.trim(),
    operation:$('shopPresetOperation').value, speed_mm_min:Number($('shopPresetSpeed').value),
    power_percent:Number($('shopPresetPower').value), passes:Number($('shopPresetPasses').value)||1,
    interval_mm:$('shopPresetInterval').value?Number($('shopPresetInterval').value):null,
    focus_reference_mm:$('shopPresetFocus').value?Number($('shopPresetFocus').value):null,
    laser_mode:$('shopPresetLaserMode').value,
    validated_on_exact_machine_surface:$('shopPresetValidated').checked, notes:$('shopPresetNotes').value.trim()
  };
  if(!body.name||!body.material||!body.speed_mm_min||!body.power_percent){msg($('shopPresetMsg'),'Complete nombre, material/superficie, velocidad y potencia.','warn');return;}
  try{const r=await api('/api/materials/shop-preset',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify(body)}); const j=await r.json(); msg($('shopPresetMsg'),j.status==='validated'?'Ajuste local guardado como VALIDADO para la misma máquina/superficie.':'Ajuste guardado como BORRADOR; valide físicamente antes de producción.',j.status==='validated'?'ok':'warn'); await loadMachineCaptures();}catch(e){msg($('shopPresetMsg'),e.message,'bad');}
});

async function loadCalibration(){
  clear($('calibrationInstructions')); $('calibrationPoints').innerHTML=''; $('calibrationMeasured').innerHTML=''; $('calibrationResult').textContent='';
  const jigId=$('calibrationJig').value; if(!jigId)return;
  try{
    const j=await (await api(`/api/calibration/jig/${encodeURIComponent(jigId)}`)).json(); state.calibration=j;
    $('calibrationPreview').innerHTML=j.svg;
    (j.instructions||[]).forEach(x=>msg($('calibrationInstructions'),x,'warn'));
    $('calibrationPoints').innerHTML=(j.reference_points||[]).map(p=>`<div class="cal-point"><strong>${esc(p.name)}</strong> · esperado X=${Number(p.x_mm).toFixed(2)} mm · Y=${Number(p.y_mm).toFixed(2)} mm</div>`).join('');
    $('calibrationMeasured').innerHTML=(j.reference_points||[]).map(p=>`<label>${esc(p.name)} X medido<input data-cal-name="${esc(p.name)}" data-axis="x" type="number" step="0.01" value="${p.x_mm}" /></label><label>${esc(p.name)} Y medido<input data-cal-name="${esc(p.name)}" data-axis="y" type="number" step="0.01" value="${p.y_mm}" /></label>`).join('');
  }catch(e){msg($('calibrationInstructions'),e.message,'bad');}
}
$('loadCalibrationBtn').addEventListener('click',loadCalibration);
$('calibrationJig').addEventListener('change',loadCalibration);
$('downloadCalibrationBtn').addEventListener('click',()=>{if(state.calibration?.svg)downloadBlob(new Blob([state.calibration.svg],{type:'image/svg+xml'}),`${$('calibrationJig').value}-CALIBRATION_ONLY.svg`);});
$('evaluateCalibrationBtn').addEventListener('click',async()=>{
  if(!state.calibration){return;}
  const by={}; $('calibrationMeasured').querySelectorAll('input').forEach(i=>{by[i.dataset.calName]??={name:i.dataset.calName}; by[i.dataset.calName][i.dataset.axis+'_mm']=Number(i.value);});
  try{const r=await api('/api/calibration/evaluate',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({jig_id:$('calibrationJig').value,measured:Object.values(by)})}); $('calibrationResult').textContent=JSON.stringify(await r.json(),null,2);}catch(e){$('calibrationResult').textContent=e.message;}
});

async function discoverLaserGrbl(){
  clear($('lasergrblDiscoveryMsg')); $('lasergrblArtifact').innerHTML='<option value="">— buscando —</option>';
  try{const j=await (await api('/api/machine/lasergrbl/discover')).json(); state.lasergrblArtifacts=j.artifacts||[]; $('lasergrblArtifact').innerHTML=state.lasergrblArtifacts.length?'<option value="">— seleccione —</option>'+state.lasergrblArtifacts.map((a,i)=>`<option value="${i}">${esc(a.name)} · ${Math.ceil((a.size||0)/1024)} KiB</option>`).join(''):'<option value="">— no se encontraron archivos —</option>'; msg($('lasergrblDiscoveryMsg'),`Rutas revisadas: ${(j.roots||[]).join(' · ')||'ninguna'} · artefactos: ${state.lasergrblArtifacts.length}.`,'ok');}catch(e){msg($('lasergrblDiscoveryMsg'),e.message,'bad');}
}
$('discoverLaserGrblBtn').addEventListener('click',discoverLaserGrbl);
$('importDetectedLaserGrblBtn').addEventListener('click',async()=>{
  clear($('lasergrblDiscoveryMsg')); const idx=$('lasergrblArtifact').value; if(idx===''){msg($('lasergrblDiscoveryMsg'),'Seleccione una base detectada.','warn');return;} const item=state.lasergrblArtifacts[Number(idx)];
  try{const r=await api('/api/machine/lasergrbl/import-local',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({path:item.path,machine_profile_id:$('machineImportProfile').value||null})}); const j=await r.json(); msg($('lasergrblDiscoveryMsg'),`Importados ${j.material_preset_count} presets LaserGRBL en solo lectura.`,'ok'); await loadMachineCaptures();}catch(e){msg($('lasergrblDiscoveryMsg'),e.message,'bad');}
});

loadAll().catch(e=>{ $('licenseBadge').textContent='Error de inicio'; $('licenseBadge').className='badge bad'; console.error(e); });
