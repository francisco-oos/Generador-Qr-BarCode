/**
 * Frontend de Marking Studio.
 *
 * WHY: La UI se mantiene sin framework para reducir dependencias de despliegue en estaciones
 * de taller. Las funciones están separadas por flujo (operación, lotes, diseñador, materiales,
 * calibración y sistema) para que una revisión futura pueda localizar con rapidez qué capa toca
 * cada cambio. Ninguna función de este archivo transmite movimiento, potencia ni encendido al láser.
 */
/** WHY: Estado efímero de la sesión web; evita variables globales dispersas y nunca sustituye al histórico SQLite. */
const state = { catalog:null, csvRows:[], csvHeaders:[], assignments:[], lastSvg:'', lastTemplate:null, machineCaptures:null, lightburnArtifacts:[], lasergrblArtifacts:[], materialReference:null, calibration:null, designerTemplate:null, designerSelected:-1, designerScale:1, designerPreviewTimer:null, individualPreviewTimer:null, batchExported:false, lastQuality:null, csvSheet:null, recordIndex:0, designerSelection:[], designerHistory:{past:[],future:[],lastLabel:'',lastAt:0}, mappingFocus:null };
/** WHY: Acceso DOM corto y centralizado para mantener legibles los flujos del operador. */
const $ = (id)=>document.getElementById(id);
/** WHY: Escapa texto antes de insertarlo en HTML generado y evita que datos del CSV se interpreten como marcado. */
const esc = (s)=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
/** WHY: Añade mensajes contextuales de éxito/advertencia/error sin mezclar lógica de negocio con presentación. */
function msg(el,text,type=''){ const d=document.createElement('div'); d.className='msg '+type; d.textContent=text; el.appendChild(d); }
/** WHY: Limpia un contenedor antes de volver a mostrar resultados para evitar mensajes obsoletos. */
function clear(el){ el.innerHTML=''; }
/** WHY: Centraliza fetch y normaliza errores HTTP para que todos los flujos fallen de forma visible y consistente. */
async function api(url, opts={}){ const r=await fetch(url,opts); if(!r.ok){ let t; try{t=await r.json()}catch{t=await r.text()} throw new Error(typeof t==='string'?t:JSON.stringify(t.detail??t)); } return r; }
/** WHY: Entrega artefactos generados al operador sin requerir acceso directo al sistema de archivos del navegador. */
function downloadBlob(blob,name){ const a=document.createElement('a'); a.href=URL.createObjectURL(blob); a.download=name; a.click(); setTimeout(()=>URL.revokeObjectURL(a.href),2000); }

/** WHY: Cambia de área funcional y dispara sólo las cargas necesarias para mantener la interfaz rápida. */
function setTab(name){
  const section=$('tab-'+name); const nav=document.querySelector(`[data-tab="${name}"]`);
  if(!section||!nav)return;
  document.querySelectorAll('.tab').forEach(x=>x.classList.remove('active'));
  document.querySelectorAll('.tabs button').forEach(x=>x.classList.remove('active'));
  section.classList.add('active'); nav.classList.add('active');
  window.scrollTo({top:0,behavior:'auto'});
  if(name==='home') renderHomeStatus();
  if(name==='history') loadHistory();
  if(name==='materials' && !state.materialReference) loadMaterialReference();
}
$('tabs').addEventListener('click',e=>{ if(e.target.dataset.tab) setTab(e.target.dataset.tab); });
document.addEventListener('click',e=>{const open=e.target.closest?.('[data-open-tab]');if(open)setTab(open.dataset.openTab);});

/** WHY: Deriva los campos de datos de una plantilla para que la UI no dependa de nombres hardcodeados. */
function sourceFields(template){ const expected=(template.expected_fields||[]).filter(Boolean); if(expected.length)return expected; const out=new Set(); for(const el of template.elements||[]){ if(el.source) el.source.split('|').forEach(x=>out.add(x.trim())); } return [...out].filter(Boolean); }
/** WHY: Resuelve la plantilla elegida desde el catálogo autoritativo del backend. */
function selectedTemplate(selectId){ return state.catalog.templates.find(t=>t.id===$(selectId).value); }
/** WHY: Rellena selectores desde configuración dinámica y evita duplicar renderizado de catálogos. */
function fillSelect(el, items, label=(x)=>x.name){ el.innerHTML=items.map(x=>`<option value="${esc(x.id)}">${esc(label(x))}</option>`).join(''); }
/** WHY: Los lectores provienen del catálogo; la UI no fija una marca/modelo en código y recuerda la elección del operador. */
function fillScannerSelect(el){
  if(!el)return; const remembered=localStorage.getItem('markingScannerId')||'';
  el.innerHTML='<option value="">— sin lector específico —</option>'+(state.catalog.scanners||[]).map(x=>`<option value="${esc(x.id)}">${esc(x.name)}</option>`).join('');
  if(remembered && [...el.options].some(o=>o.value===remembered)) el.value=remembered;
  el.addEventListener('change',()=>{ if(el.value)localStorage.setItem('markingScannerId',el.value); else localStorage.removeItem('markingScannerId'); });
}

/** WHY: El modo físico se hereda de la plantilla y puede sobreescribirse temporalmente sin contaminar el estándar validado. */
function defaultMarkingMode(){return {polarity:'positive',polarity_scope:'codes',negative_field:'islands',field_margin_mm:0,kerf_compensation_mm:0,validated_on:''};}
/** WHY: Normaliza plantillas antiguas/nuevas a un contrato de marcado completo sin hardcodear fabricantes. */
function templateMarkingMode(t){return {...defaultMarkingMode(),...(t?.marking_mode||{})};}
/** WHY: Refleja en UI el modo físico heredado de la plantilla sin modificarlo hasta una acción explícita. */
function fillMarkingControls(prefix,t){
  const m=templateMarkingMode(t);
  const set=(id,v)=>{const el=$(prefix+id);if(el)el.value=v??'';};
  set('Polarity',m.polarity);set('PolarityScope',m.polarity_scope);set('NegativeField',m.negative_field);set('FieldMargin',m.field_margin_mm);set('Kerf',m.kerf_compensation_mm);set('ValidatedOn',m.validated_on);
  toggleMarkingControls(prefix);
}
/** WHY: Convierte controles visibles en un MarkingMode genérico reutilizable por preview, lote y guardado. */
function readMarkingControls(prefix){
  const val=(id,def='')=>$(prefix+id)?$(prefix+id).value:def;
  return {polarity:val('Polarity','positive'),polarity_scope:val('PolarityScope','codes'),negative_field:val('NegativeField','islands'),field_margin_mm:Number(val('FieldMargin',0))||0,kerf_compensation_mm:Number(val('Kerf',0))||0,validated_on:val('ValidatedOn','').trim()};
}
/** WHY: El sufijo hace imposible confundir artefactos directos, invertidos y los invertidos que requieren segunda operación. */
function markingFilenameSuffix(mode){if(mode?.polarity!=='negative')return '';return (mode.polarity_scope==='codes'&&mode.negative_field==='template')?'_NEGATIVE_2PASS':'_NEGATIVE';}
/** WHY: Aplica divulgación progresiva: los ajustes de negativo sólo aparecen cuando el operador los necesita. */
function toggleMarkingControls(prefix){
  const neg=$(prefix+'Polarity')?.value==='negative'; const host=$(prefix+'NegativeOptions'); if(host)host.hidden=!neg;
  const scope=$(prefix+'PolarityScope'), field=$(prefix+'NegativeField');
  // WHY (v0.8.0 final): codes+template sí se permite, pero representa un artefacto
  // de DOS ETAPAS. El fondo/código y el contenido positivo quedan en capas separadas;
  // el software de la máquina debe asignar la segunda operación de forma explícita.
  if(field){const templateOpt=[...field.options].find(o=>o.value==='template'); if(templateOpt)templateOpt.disabled=false;}
}
/** WHY: Mantiene sincronizados preview y preflight al cambiar una propiedad física sin duplicar listeners por pantalla. */
function bindMarkingControls(prefix,onChange){
  ['Polarity','PolarityScope','NegativeField','FieldMargin','Kerf','ValidatedOn'].forEach(s=>{const el=$(prefix+s);if(!el)return;el.addEventListener(s==='ValidatedOn'||s==='FieldMargin'||s==='Kerf'?'input':'change',()=>{toggleMarkingControls(prefix);onChange?.();});});
}
/** WHY: Un override de prueba no debe contaminar una plantilla validada hasta que el operador decida persistirlo explícitamente. */
async function saveMarkingModeToTemplate(selectId,prefix,target){
  const t=deepClone(selectedTemplate(selectId)); if(!t)return; t.marking_mode=readMarkingControls(prefix); clear($(target));
  try{const r=await api('/api/templates/save',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({template:t})});const j=await r.json();await refreshCatalogAfterTemplateSave(t.id);msg($(target),`Modo guardado en plantilla · versión ${j.version||selectedTemplate(selectId)?.version||''}`,'ok');}
  catch(e){msg($(target),e.message,'bad');}
}

/** WHY: Resume capacidades disponibles en la portada para que el operador confirme de un vistazo que la estación cargó catálogo, máquina y lector. */
function renderHomeStatus(){
  if(!state.catalog){$('homeStatus').textContent='Catálogo aún no disponible.';return;}
  const templates=state.catalog.templates?.length||0, machines=state.catalog.machines?.length||0, scanners=state.catalog.scanners?.length||0;
  $('homeStatus').innerHTML=`<span><strong>${templates}</strong> plantillas</span><span><strong>${machines}</strong> máquinas</span><span><strong>${scanners}</strong> lectores</span>`;
}

/** WHY: Inicializa licencia, catálogo, perfiles y vistas en un orden único y reproducible al abrir la aplicación. */
async function loadAll(){
  applyExperienceMode(localStorage.getItem('markingStudioMode')||'guided'); const lic=await (await api('/api/license')).json(); $('licenseJson').textContent=JSON.stringify(lic,null,2); $('licenseBadge').textContent=lic.valid?`Licencia ${lic.payload?.edition||''} · válida`:`Licencia no válida`; $('licenseBadge').className='badge '+(lic.valid?'ok':'bad');
  if(!lic.valid) return;
  state.catalog=await (await api('/api/catalog')).json();
  ['individualTemplate','batchTemplate','configTemplate'].forEach(id=>fillSelect($(id),state.catalog.templates));
  fillSelect($('configJig'),state.catalog.jigs,x=>`${x.name} · ${x.capacity} pos.`); fillSelect($('designerQuality'),state.catalog.quality_profiles); fillScannerSelect($('individualScanner')); fillScannerSelect($('designerScanner'));
  fillSelect($('machineImportProfile'),state.catalog.machines); fillSelect($('shopPresetMachine'),state.catalog.machines); fillScannerSelect($('shopPresetScanner')); fillSelect($('calibrationJig'),state.catalog.jigs,x=>`${x.name} · ${x.capacity} pos.`);
  renderMachineCards(); renderScannerCards(); renderIndividualFields(); updateBatchJigs(); loadConfigEditors(); initVisualDesigner(); renderHomeStatus(); updateBatchStepper();
  await loadMachineCaptures(); await refreshPorts();
}
/** WHY: Muestra capacidades de máquina para dar contexto sin convertir la UI en controlador de hardware. */
function renderMachineCards(){ $('machinesList').innerHTML=state.catalog.machines.map(m=>`<div class="machine-card"><strong>${esc(m.name)}</strong><div>${esc(m.controller)} · ${m.bed_width_mm}×${m.bed_height_mm} mm · ${esc(m.connection)}</div><div class="muted">Vector: ${esc(m.vector_formats.join(', '))}</div><div class="muted">Salida directa: ${m.direct_machine_output_enabled?'sí':'no (handoff seguro)'}</div></div>`).join(''); }
/** WHY: Muestra simbologías del lector para que el operador sepa qué diseños puede validar físicamente. */
function renderScannerCards(){ $('scannersList').innerHTML=(state.catalog.scanners||[]).map(s=>`<div class="machine-card"><strong>${esc(s.name)}</strong><div>${esc(s.technology)} · ${esc(s.interfaces.join(', '))}</div><div class="muted">${esc(s.symbologies.join(', '))}</div><div class="muted">QR: ${s.supports_qr?'sí':'no'} · Data Matrix: ${s.supports_datamatrix?'sí':'no'}</div></div>`).join(''); }
/** WHY: Traduce el preflight técnico a una lectura rápida sin ocultar las comprobaciones que sustentan el resultado. */
function renderQualityResult(target, report){
  const host=$(target); if(!host)return; state.lastQuality=report;
  const overall=report.overall||'SIN_CODIGOS'; const cls=overall==='ROBUSTO'?'ok':overall==='ACEPTABLE'?'ok':overall==='FRAGIL'?'warn':'bad';
  const label={ROBUSTO:'ROBUSTO',ACEPTABLE:'ACEPTABLE',FRAGIL:'FRÁGIL',NO_LEGIBLE:'NO LEGIBLE',SIN_CODIGOS:'SIN CÓDIGOS'}[overall]||overall;
  let html=`<div class="quality-summary ${cls}"><strong>Calidad estimada: ${esc(label)}</strong><span>Preflight digital; la prueba física sigue siendo obligatoria.</span></div>`;
  for(const r of report.results||[]){
    const rcls=r.classification==='ROBUSTO'||r.classification==='ACEPTABLE'?'ok':r.classification==='FRAGIL'?'warn':'bad';
    const digital=r.digital?.available?`${r.digital.passed}/${r.digital.total} pruebas digitales`:(r.digital?.note||'sin decodificador digital');
    html+=`<article class="quality-card ${rcls}"><div class="panel-head"><strong>${esc(r.label)} · ${esc(r.kind)}</strong><span>${esc(r.classification)}</span></div><div class="quality-metrics"><span>Dato: <b>${esc(r.value)}</b></span><span>Módulo: <b>${r.module_mm??'—'} mm</b></span><span>Tamaño real: <b>${r.symbol_width_mm??'—'} × ${r.symbol_height_mm??'—'} mm</b></span><span>${esc(digital)}</span></div><ul>${(r.checks||[]).map(c=>`<li class="${esc(c.level)}">${esc(c.message)}</li>`).join('')}</ul>${r.digital?.available?`<details><summary>Ver degradaciones simuladas</summary><div class="variant-grid">${r.digital.variants.map(v=>`<span class="${v.pass?'ok':'bad'}">${esc(v.name)}: ${v.pass?'PASS':'FAIL'}</span>`).join('')}</div></details>`:''}</article>`;
  }
  html+=`<div class="messages">${(report.notes||[]).map(n=>`<div class="msg warn">${esc(n)}</div>`).join('')}</div>`; host.innerHTML=html;
}
/** WHY: Ejecuta una comprobación independiente de legibilidad antes del handoff al software de la máquina. */
async function runCodeQuality(template,data,scannerId,target,markingMode=null){
  const host=$(target); host.innerHTML='<div class="msg">Evaluando geometría, lector y degradaciones digitales…</div>';
  try{
    const r=await api('/api/quality/check',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({template,data,capture_mode:'manual',scanner_profile_id:scannerId||null,digital_stress:true,marking_mode_override:markingMode})});
    renderQualityResult(target,await r.json());
  }catch(e){host.innerHTML='';msg(host,e.message,'bad');}
}

/** WHY: Construye captura manual desde los campos/reglas de la plantilla, incluida la ayuda de prefijos. */
function renderIndividualFields(){
  const t=selectedTemplate('individualTemplate'); state.lastTemplate=t; fillMarkingControls('individual',t); const fields=sourceFields(t);
  $('individualFields').innerHTML=fields.map(f=>{const rule=(t.input_rules||[]).find(r=>r.field===f); const prefix=rule?.manual_prefix_enabled?`<span class="hint">Prefijo manual automático: <strong>${esc(rule.manual_prefix)}</strong> · CSV: ${esc(rule.imported_values)}</span>`:''; return `<label>${esc(f)}<input data-field="${esc(f)}" placeholder="${esc(f)}" />${prefix}</label>`;}).join('');
  const defaults=t.metadata?.example_data||{};
  $('individualFields').querySelectorAll('input').forEach(i=>{ if(defaults[i.dataset.field]) i.value=defaults[i.dataset.field]; i.addEventListener('input',scheduleIndividualPreview); });
  renderIndividual();
}
$('individualTemplate').addEventListener('change',renderIndividualFields);
/** WHY: Agrupa pulsaciones rápidas antes de renderizar para ofrecer preview vivo sin saturar el backend con una petición por tecla. */
function scheduleIndividualPreview(){clearTimeout(state.individualPreviewTimer);state.individualPreviewTimer=setTimeout(renderIndividual,160);}
/** WHY: Renderiza la vista previa individual con el mismo motor SVG que luego se exporta. */
async function renderIndividual(){ const t=selectedTemplate('individualTemplate'); const data={}; $('individualFields').querySelectorAll('input').forEach(i=>data[i.dataset.field]=i.value.trim()); clear($('renderWarnings')); if($('individualQualityResult'))$('individualQualityResult').innerHTML=''; try{ const r=await api('/api/render',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({template_id:t.id,data,capture_mode:'manual',output:'svg',marking_mode_override:readMarkingControls('individual')})}); const j=await r.json(); state.lastSvg=j.svg; $('preview').innerHTML=j.svg; $('markSize').textContent=`${j.width_mm} × ${j.height_mm} mm`; j.warnings.forEach(w=>msg($('renderWarnings'),w,'warn')); if(j.calibration_required) msg($('renderWarnings'),'Plantilla pendiente de calibración física antes de producción.','warn'); }catch(e){msg($('renderWarnings'),e.message,'bad');}}
$('renderBtn').addEventListener('click',renderIndividual);
$('downloadSvgBtn').addEventListener('click',()=>{ if(state.lastSvg) downloadBlob(new Blob([state.lastSvg],{type:'image/svg+xml'}),`${$('individualTemplate').value}${markingFilenameSuffix(readMarkingControls('individual'))}.svg`); });
$('downloadPngBtn').addEventListener('click',async()=>{ const t=selectedTemplate('individualTemplate'); const data={}; $('individualFields').querySelectorAll('input').forEach(i=>data[i.dataset.field]=i.value.trim()); try{ const r=await api('/api/render',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({template_id:t.id,data,capture_mode:'manual',output:'png',dpi:600,marking_mode_override:readMarkingControls('individual')})}); downloadBlob(await r.blob(),`${t.id}${markingFilenameSuffix(readMarkingControls('individual'))}-600dpi.png`);}catch(e){msg($('renderWarnings'),e.message,'bad');} });
$('individualQualityBtn').addEventListener('click',()=>{const t=selectedTemplate('individualTemplate');const data={};$('individualFields').querySelectorAll('input').forEach(i=>data[i.dataset.field]=i.value.trim());runCodeQuality(t,data,$('individualScanner').value,'individualQualityResult',readMarkingControls('individual'));});

/** WHY: Precarga serie/prefijo desde la plantilla para reducir errores de captura sin imponerlos al CSV. */
function updateSeriesDefaultsFromTemplate(){const t=selectedTemplate('batchTemplate');if(!t)return;const field=primaryIdentityField(t)||sourceFields(t)[0]||'';const rule=(t.input_rules||[]).find(r=>r.field===field);$('seriesField').value=field;$('seriesPrefix').value=rule?.manual_prefix_enabled?rule.manual_prefix:'';$('seriesSuffix').value=rule?.manual_suffix_enabled?rule.manual_suffix:'';}
/** WHY: Filtra jigs compatibles por plantilla/categoría y conserva opciones genéricas cuando no hay uno específico. */
function updateBatchJigs(){ const t=selectedTemplate('batchTemplate'); fillMarkingControls('batch',t); const exact=state.catalog.jigs.filter(j=>j.template_id===t.id); const category=state.catalog.jigs.filter(j=>j.target_category===t.category && !exact.some(e=>e.id===j.id)); const generic=state.catalog.jigs.filter(j=>j.target_category==='generic' && !exact.some(e=>e.id===j.id) && !category.some(e=>e.id===j.id)); const list=[...exact,...category,...generic]; fillSelect($('batchJig'),list.length?list:state.catalog.jigs,x=>`${x.name} · ${x.capacity} pos.`); updateSeriesDefaultsFromTemplate(); updateJigSummary(); buildMapping(); }
$('batchTemplate').addEventListener('change',updateBatchJigs); $('batchJig').addEventListener('change',updateJigSummary);
/** WHY: Expone capacidad/calibración y dibuja los slots antes de asignar datos físicos. */
function updateJigSummary(){ if(!state.catalog)return; const j=state.catalog.jigs.find(x=>x.id===$('batchJig').value); $('jigCapacity').textContent=j?`${j.capacity} posiciones · ${j.calibration_required?'calibración requerida':'aprobado'}`:''; if(j){ updateBatchProgress(); $('jigGrid').style.gridTemplateColumns=`repeat(${j.grid.cols}, minmax(0,1fr))`; $('jigGrid').innerHTML=j.slots.map(s=>`<div class="slot" data-slot="${s.slot_index}"><div>Pos. ${s.slot_index}</div><div class="slot-id muted">vacía</div></div>`).join(''); } }

/** WHY: Carga CSV o lista flexible y delega detección de encabezados al backend antes de mapear columnas. */
/** WHY: La tabla de vista previa es la única forma de que el operador confirme que
 *  el archivo se leyó como esperaba ANTES de acomodar equipo físico. Sin ella, un
 *  delimitador mal detectado o la hoja equivocada sólo se descubren tras grabar. */
function renderDataPreview(j){
  const box=$('csvPreviewTable'); if(!box)return;
  if(!j||!j.preview||!j.preview.length){box.innerHTML='';return;}
  const heads=j.headers||[];
  const head=heads.map(h=>`<th data-column="${esc(h)}">${esc(h)}</th>`).join('');
  const body=j.preview.map((row,i)=>`<tr><td class="muted">${i+1}</td>${heads.map(h=>`<td data-column="${esc(h)}">${esc(row[h]??'')}</td>`).join('')}</tr>`).join('');
  const origen=j.format==='xlsx'?`hoja «${esc(j.sheet||'')}»`:(j.delimiter?`delimitador «${esc(j.delimiter)}»`:'texto plano');
  box.innerHTML=`<div class="muted preview-caption">Mostrando ${j.preview.length} de ${j.count} registros · ${origen}</div>`+
    `<div class="preview-scroll"><table><thead><tr><th>#</th>${head}</tr></thead><tbody>${body}</tbody></table></div>`;
}

/** WHY: Se consultan las hojas por separado para que el selector exista ANTES de
 *  interpretar los datos; asumir la primera hoja es el error clásico con libros
 *  que empiezan con una portada o un instructivo. */
async function loadSheetsIfWorkbook(f){
  const wrap=$('csvSheetWrap'), sel=$('csvSheet');
  if(!wrap||!sel)return null;
  const fd=new FormData(); fd.append('file',f);
  try{
    const j=await (await api('/api/data/sheets',{method:'POST',body:fd})).json();
    if(j.format!=='xlsx'||!j.sheets.length){wrap.hidden=true;sel.innerHTML='';return null;}
    const previous=state.csvSheet;
    const keep=j.sheets.includes(previous)?previous:j.sheets[0];
    sel.innerHTML=j.sheets.map(s=>`<option value="${esc(s)}"${s===keep?' selected':''}>${esc(s)}</option>`).join('');
    wrap.hidden=false; state.csvSheet=keep; return keep;
  }catch(e){wrap.hidden=true;sel.innerHTML='';return null;}
}

/** WHY: Punto de entrada único para cualquier archivo de datos: primero resuelve
 *  las hojas si es un libro y sólo después interpreta el contenido. */
async function loadCsvFile(){
  clear($('csvInfo')); const f=$('csvFile').files[0]; if(!f)return;
  const sheet=await loadSheetsIfWorkbook(f);
  await inspectDataFile(f,sheet);
}

/** WHY: Aísla la llamada de inspección para poder repetirla al cambiar hoja,
 *  modo de encabezado o tamaño de vista previa sin volver a pedir el archivo. */
async function inspectDataFile(f,sheet){
  const fd=new FormData(); fd.append('file',f);
  const mode=$('csvHeaderMode').value||'auto';
  const limit=Math.max(1,Math.min(500,Number($('csvPreviewLimit')?.value)||25));
  let url=`/api/csv/inspect?header_mode=${encodeURIComponent(mode)}&preview_limit=${limit}`;
  if(sheet) url+=`&sheet=${encodeURIComponent(sheet)}`;
  try{
    const j=await (await api(url,{method:'POST',body:fd})).json();
    state.csvRows=j.rows; state.csvHeaders=j.headers; state.csvSheet=j.sheet||null;
    state.assignments=[]; state.batchExported=false; state.recordIndex=0; $('batchOffset').value=0;
    msg($('csvInfo'),`${j.count} registros · columnas detectadas: ${j.headers.join(', ')}`,'ok');
    if(j.format==='xlsx') msg($('csvInfo'),`Leído desde la hoja «${j.sheet}». Si el inventario está en otra hoja, cámbiela arriba.`,'ok');
    if(j.headers.length===1) msg($('csvInfo'),'Lista de una sola columna: se asignará automáticamente al/los campos de la plantilla; puede cambiar el mapeo si lo desea.','ok');
    renderDataPreview(j);
    buildMapping(); updateBatchProgress(); updateBatchStepper(); updateRecordNav(); await renderBatchRecordPreview();
  }catch(e){msg($('csvInfo'),e.message,'bad');}
}

/** WHY: Recargar con el mismo archivo evita pedirle al usuario que lo vuelva a
 *  seleccionar cada vez que corrige el modo de encabezado o la hoja. */
function reinspectCurrentFile(){
  const f=$('csvFile').files[0]; if(!f)return;
  clear($('csvInfo'));
  inspectDataFile(f,$('csvSheetWrap')&&!$('csvSheetWrap').hidden?$('csvSheet').value:null);
}
$('csvFile').addEventListener('change',loadCsvFile);
$('csvHeaderMode').addEventListener('change',reinspectCurrentFile);
if($('csvSheet')) $('csvSheet').addEventListener('change',reinspectCurrentFile);
if($('csvPreviewLimit')) $('csvPreviewLimit').addEventListener('change',reinspectCurrentFile);
/** WHY: Crea lotes secuenciales sólo bajo una regla explícita aportada por el usuario. */
async function generateSeries(){ clear($('csvInfo')); const body={field:$('seriesField').value.trim(),prefix:$('seriesPrefix').value,start:Number($('seriesStart').value)||0,count:Number($('seriesCount').value)||1,width:Number($('seriesWidth').value)||0,suffix:$('seriesSuffix').value}; try{ const r=await api('/api/series/generate',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify(body)}); const j=await r.json(); state.csvRows=j.rows; state.csvHeaders=[j.field]; state.assignments=[]; state.batchExported=false; $('batchOffset').value=0; buildMapping(); updateBatchProgress(); updateBatchStepper(); msg($('csvInfo'),`${j.count} registros generados · ${j.first} → ${j.last}`,'ok'); msg($('csvInfo'),j.warning,'warn'); }catch(e){msg($('csvInfo'),e.message,'bad');} }
$('generateSeriesBtn').addEventListener('click',generateSeries);

/** WHY: Refleja el avance del flujo por lote (datos→mapeo→posiciones→salida) para orientar a usuarios que no conocen el proceso. */
function updateBatchStepper(){
  let step=1;
  if(state.csvRows.length)step=2;
  if(state.assignments.length)step=3;
  if(state.batchExported)step=4;
  document.querySelectorAll('[data-batch-step]').forEach(el=>{const n=Number(el.dataset.batchStep);el.classList.toggle('active',n===step);el.classList.toggle('done',n<step);});
}
/** WHY: Hace visible qué parte del dataset corresponde al lote físico actual. */
function updateBatchProgress(){ if(!state.catalog||!state.csvRows.length){$('batchProgress').textContent='Sin lote cargado.';return;} const jig=state.catalog.jigs.find(x=>x.id===$('batchJig').value); if(!jig)return; const total=state.csvRows.length; const cap=jig.capacity; const offset=Math.max(0,Number($('batchOffset').value)||0); const totalBatches=Math.ceil(total/cap); const current=Math.min(totalBatches,Math.floor(offset/cap)+1); const end=Math.min(total,offset+cap); $('batchProgress').innerHTML=`Lote <strong>${current}</strong> de <strong>${totalBatches}</strong> · registros ${offset+1}–${end} de ${total} · capacidad ${cap}`; }
/** WHY: Normaliza texto únicamente para heurísticas de mapeo; no altera los valores productivos importados. */
function norm(s){return String(s).toLowerCase().replace(/[^a-z0-9]/g,'');}
/** WHY: Sugiere la columna más probable para un campo sin impedir que el usuario corrija el mapeo. */
function bestHeader(field){
  if(!state.csvHeaders.length)return'';
  if(state.csvHeaders.length===1)return state.csvHeaders[0];
  const exact=state.csvHeaders.find(h=>norm(h)===norm(field)); if(exact)return exact;
  const t=selectedTemplate('batchTemplate'); const aliases=t?.metadata?.csv_aliases?.[field]||[];
  for(const alias of aliases){const h=state.csvHeaders.find(x=>norm(x)===norm(alias)); if(h)return h;}
  // Generic token overlap only; equipment-specific aliases live in template data, not code.
  const ft=norm(field); let best='',score=0;
  for(const h of state.csvHeaders){const ht=norm(h); let s=0; if(ht.includes(ft)||ft.includes(ht))s=Math.min(ht.length,ft.length); if(s>score){score=s;best=h;}}
  return score>=3?best:'';
}
/** WHY: Construye el mapeo plantilla↔CSV de forma dinámica, incluida la lista de una sola columna. */
function buildMapping(){
  if(!state.catalog)return; const t=selectedTemplate('batchTemplate'); const fields=sourceFields(t);
  // Cada fila del panel enumera los elementos de la plantilla que consumen ese campo.
  // Ver "serial → barcode_serial, text_serial" es lo que convierte el mapeo en algo
  // comprensible para alguien que nunca abrió el JSON de la plantilla.
  $('fieldMapping').innerHTML=fields.map(f=>{
    const chosen=bestHeader(f);
    const opts=['',...state.csvHeaders].map(h=>`<option value="${esc(h)}" ${h===chosen?'selected':''}>${h?esc(h):'— sin mapear —'}</option>`).join('');
    const consumers=elementsUsingField(t,f);
    const chips=consumers.length?consumers.map(c=>`<span class="chip">${esc(c)}</span>`).join(''):'<span class="chip muted">sin elemento</span>';
    return `<div class="map-row" data-maprow="${esc(f)}"><label>${esc(f)}<select data-mapfield="${esc(f)}">${opts}</select></label><div class="map-consumers">${chips}</div></div>`;
  }).join('');
  $('fieldMapping').querySelectorAll('select').forEach(x=>{
    x.addEventListener('change',()=>{focusMappingField(x.dataset.mapfield);renderBatchRecordPreview();});
    x.addEventListener('focus',()=>focusMappingField(x.dataset.mapfield));
  });
  $('fieldMapping').querySelectorAll('.map-row').forEach(r=>r.addEventListener('click',()=>focusMappingField(r.dataset.maprow)));
  renderBatchRecordPreview();
}

/** WHY: Lista los elementos de la plantilla alimentados por un campo. Un campo puede
 *  alimentar varios objetos a la vez (el barcode y el texto legible del mismo serial),
 *  y ocultarlo es justo lo que hace que un mapeo equivocado pase inadvertido. */
function elementsUsingField(template,field){
  return (template?.elements||[])
    .filter(el=>String(el.source||'').split('|').map(x=>x.trim()).includes(field))
    .map((el,i)=>el.name||el.label||`${el.kind}_${i+1}`);
}

/** WHY: Un único punto de verdad para el resaltado cruzado: panel de mapeo, columna de
 *  la tabla de datos y elementos del lienzo se iluminan desde el mismo estado. */
function focusMappingField(field){
  state.mappingFocus=(state.mappingFocus===field)?null:field;
  const column=state.mappingFocus?(document.querySelector(`[data-mapfield="${CSS.escape(state.mappingFocus)}"]`)?.value||''):'';
  $('fieldMapping').querySelectorAll('.map-row').forEach(r=>r.classList.toggle('focused',r.dataset.maprow===state.mappingFocus));
  const table=$('csvPreviewTable');
  if(table){
    table.querySelectorAll('th,td').forEach(c=>c.classList.toggle('column-hit',!!column&&c.dataset.column===column));
  }
  if(state.designerTemplate) renderDesignerCanvas();
}
/** WHY: Aplica el mapeo elegido y produce filas con los nombres que espera la plantilla. */
function mappedRows(){ const maps={}; $('fieldMapping').querySelectorAll('select').forEach(s=>{if(s.value)maps[s.dataset.mapfield]=s.value;}); return state.csvRows.map(r=>{const x={...r}; for(const [target,src] of Object.entries(maps)) x[target]=r[src]??''; return x;}); }
/** WHY: Previsualiza un registro mapeado para detectar errores antes de preparar posiciones o exportar. */
/** WHY: Poder saltar al primero, al último o a uno aleatorio es lo que permite
 *  detectar desbordes por longitud de dato sin revisar mil registros a mano. */
function updateRecordNav(){
  const total=state.csvRows.length;
  if($('recTotal')) $('recTotal').textContent=`/ ${total}`;
  if($('recIndex')){ $('recIndex').max=Math.max(1,total); $('recIndex').value=total?state.recordIndex+1:1; }
}
/** WHY: Acota el índice al rango real del dataset para que un valor escrito a mano
 *  nunca deje la vista previa apuntando a un registro inexistente. */
function gotoRecord(index){
  const total=state.csvRows.length; if(!total)return;
  state.recordIndex=Math.max(0,Math.min(total-1,index));
  updateRecordNav(); renderBatchRecordPreview();
}
if($('recFirstBtn')) $('recFirstBtn').addEventListener('click',()=>gotoRecord(0));
if($('recPrevBtn')) $('recPrevBtn').addEventListener('click',()=>gotoRecord(state.recordIndex-1));
if($('recNextBtn')) $('recNextBtn').addEventListener('click',()=>gotoRecord(state.recordIndex+1));
if($('recLastBtn')) $('recLastBtn').addEventListener('click',()=>gotoRecord(state.csvRows.length-1));
if($('recRandomBtn')) $('recRandomBtn').addEventListener('click',()=>gotoRecord(Math.floor(Math.random()*state.csvRows.length)));
if($('recIndex')) $('recIndex').addEventListener('change',()=>gotoRecord((Number($('recIndex').value)||1)-1));

/** WHY: Renderiza el registro seleccionado con el motor real de producción, no con
 *  una aproximación del navegador, para que lo revisado sea lo que se grabará. */
async function renderBatchRecordPreview(){
  if(!$('batchRecordPreview'))return; clear($('batchPreviewMsg'));
  if(!state.csvRows.length){$('batchRecordPreview').innerHTML='<span class="muted">Cargue datos para previsualizar.</span>';updateRecordNav();return;}
  const rows=mappedRows(); const row=rows[Math.min(state.recordIndex,rows.length-1)]||{}; const t=selectedTemplate('batchTemplate');
  try{const r=await api('/api/render',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({template_id:t.id,data:row,capture_mode:'import',output:'svg',marking_mode_override:readMarkingControls('batch')})});const j=await r.json();$('batchRecordPreview').innerHTML=j.svg;(j.warnings||[]).forEach(w=>msg($('batchPreviewMsg'),w,'warn'));}
  catch(e){$('batchRecordPreview').innerHTML='<span class="muted">No se pudo generar vista previa.</span>';msg($('batchPreviewMsg'),e.message,'bad');}
}
/** WHY: Obtiene la identidad definida por la plantilla para conciliación y nombres de archivo. */
function primaryIdentityField(template){return template?.metadata?.primary_identity_field||sourceFields(template||{})[0]||'';}
/** WHY: Extrae la identidad candidata de una fila ya mapeada sin asumir fabricante o equipo. */
function candidateId(r,template=selectedTemplate('batchTemplate')){const f=primaryIdentityField(template); return (f&&r[f])||Object.values(r).find(v=>String(v||'').trim())||'';}
/** WHY: Toma la ventana actual del dataset y la coloca en slots, preservando la confirmación física. */
function prepareBatch(){ clear($('batchMessages')); if(!state.csvRows.length){msg($('batchMessages'),'Cargue un CSV primero.','bad');return;} const jig=state.catalog.jigs.find(x=>x.id===$('batchJig').value); const rows=mappedRows(); const offset=Math.max(0,Number($('batchOffset').value)||0); const subset=rows.slice(offset,offset+jig.capacity); state.assignments=subset.map((r,i)=>({slot_index:jig.slots[i].slot_index,row_index:offset+i,physical_id:''})); state.batchExported=false; renderAssignments(rows,jig); updateBatchProgress(); updateBatchStepper(); }
$('prepareBatchBtn').addEventListener('click',prepareBatch); $('batchOffset').addEventListener('change',updateBatchProgress); $('nextBatchBtn').addEventListener('click',()=>{ if(!state.csvRows.length)return; const jig=state.catalog.jigs.find(x=>x.id===$('batchJig').value); const next=(Math.max(0,Number($('batchOffset').value)||0)+jig.capacity); if(next>=state.csvRows.length){ clear($('batchMessages')); msg($('batchMessages'),'Ya está en el último lote.','warn'); return;} $('batchOffset').value=next; prepareBatch(); });
/** WHY: Presenta posición, esperado y observado para que el operador pueda conciliar visualmente cada pieza. */
function renderAssignments(rows,jig){ $('jigGrid').querySelectorAll('.slot').forEach(s=>{s.classList.remove('assigned');s.querySelector('.slot-id').textContent='vacía';}); for(const a of state.assignments){ const cell=$('jigGrid').querySelector(`[data-slot="${a.slot_index}"]`); if(cell){cell.classList.add('assigned');cell.querySelector('.slot-id').textContent=candidateId(rows[a.row_index]);} }
  $('assignmentTable').innerHTML=`<div class="table-wrap"><table><thead><tr><th>Posición</th><th>Fila CSV</th><th>Esperado</th><th>ID escrito / leído físicamente</th><th>Estado</th></tr></thead><tbody>${state.assignments.map((a,i)=>{const expected=candidateId(rows[a.row_index]);return `<tr><td>${a.slot_index}</td><td>${a.row_index+1}</td><td><strong>${esc(expected)}</strong></td><td><input data-phys="${i}" value="${esc(a.physical_id)}" autocomplete="off"></td><td data-match="${i}" class="muted">pendiente</td></tr>`;}).join('')}</tbody></table></div>`;
  $('assignmentTable').querySelectorAll('[data-phys]').forEach(inp=>inp.addEventListener('input',()=>{const i=Number(inp.dataset.phys);state.assignments[i].physical_id=inp.value;const expected=candidateId(rows[state.assignments[i].row_index]);const ok=inp.value.trim().toUpperCase()===String(expected).trim().toUpperCase();const td=$('assignmentTable').querySelector(`[data-match="${i}"]`);td.textContent=inp.value?(ok?'coincide':'NO coincide'):'pendiente';td.className=inp.value?(ok?'status-ok':'status-bad'):'muted';})); }
$('simulationFillBtn').addEventListener('click',()=>{const rows=mappedRows();state.assignments.forEach(a=>a.physical_id=candidateId(rows[a.row_index]));const jig=state.catalog.jigs.find(x=>x.id===$('batchJig').value);renderAssignments(rows,jig);msg($('batchMessages'),'Confirmaciones prellenadas solo para simulación/demo.','warn');});
/** WHY: Genera el ZIP de trabajo colocado sobre el jig. Separado del modo de salida
 *  para que la conciliación física siga siendo obligatoria sólo en esta ruta. */
async function exportJigJob(){
  if(!state.assignments.length){msg($('batchMessages'),'Prepare posiciones primero.','bad');return false;}
  const rows=mappedRows();
  const body={template_id:$('batchTemplate').value,jig_id:$('batchJig').value,material_preset_id:$('batchMaterialPreset').value?Number($('batchMaterialPreset').value):null,rows,assignments:state.assignments,require_physical_confirmation:$('requireConfirmation').checked,output_dpi:300,marking_mode_override:readMarkingControls('batch'),export_mode:$('svgExportMode')?.value||'production'};
  const r=await api('/api/batch/export',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify(body)});
  const job=r.headers.get('X-Job-Id');
  downloadBlob(await r.blob(),`marking-job-${job?.slice(0,8)||'batch'}.zip`);
  msg($('batchMessages'),`Trabajo exportado y registrado: ${job}`,'ok');
  const jig=state.catalog.jigs.find(x=>x.id===$('batchJig').value);
  const offset=Math.max(0,Number($('batchOffset').value)||0);
  if(offset+jig.capacity<state.csvRows.length) msg($('batchMessages'),'Lote listo. Use «Siguiente lote» para continuar sin recalcular posiciones.','ok');
  return true;
}

/** WHY: Un SVG por registro no requiere jig ni conciliación; sirve para recomponer
 *  después en LightBurn o para procesos que no usan una base física. */
async function exportIndividualSvgs(){
  if(!state.csvRows.length){msg($('batchMessages'),'Cargue datos o genere una serie primero.','bad');return false;}
  const rows=mappedRows(); const t=selectedTemplate('batchTemplate');
  const pattern=($('filenamePattern')?.value||'').trim();
  const body={template_id:t.id,rows,export_mode:$('svgExportMode')?.value||'production',marking_mode_override:readMarkingControls('batch'),filename_pattern:$('filenamePattern')?.value.trim()||null};
  if(pattern) body.filename_pattern=pattern; else body.filename_field=primaryIdentityField(t)||null;
  const r=await api('/api/bulk/svg-export',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify(body)});
  const count=r.headers.get('X-Record-Count')||rows.length;
  downloadBlob(await r.blob(),`${t.id}-${count}-svg.zip`);
  msg($('batchMessages'),`Generados ${count} SVG individuales desde la misma plantilla. Importe después en el software de la máquina.`,'ok');
  return true;
}

/** WHY: El modo de salida se decide una sola vez y en un solo control, para que el
 *  operador no tenga que saber qué botón corresponde a qué tipo de entrega. */
function selectedOutputMode(){
  const picked=document.querySelector('input[name="outputMode"]:checked');
  return picked?picked.value:'jig';
}

$('exportBatchBtn').addEventListener('click',async()=>{
  clear($('batchMessages'));
  const mode=selectedOutputMode();
  try{
    let ok=false;
    if(mode==='jig'||mode==='both') ok=await exportJigJob();
    if((mode==='individual'||mode==='both') && (mode==='individual'||ok)) ok=await exportIndividualSvgs()||ok;
    if(ok){state.batchExported=true; updateBatchStepper();}
  }catch(e){msg($('batchMessages'),e.message,'bad');}
});

$('verifyBtn').addEventListener('click',async()=>{clear($('verifyResult'));try{const r=await api('/api/scan/verify',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({expected:$('verifyExpected').value,scanned:$('verifyScanned').value,normalize:$('verifyNormalize').checked})});const j=await r.json();msg($('verifyResult'),j.matched?'COINCIDE — marcado verificado':'NO COINCIDE — no liberar el equipo',j.matched?'ok':'bad');if(j.history_update)msg($('verifyResult'),JSON.stringify(j.history_update),j.history_update.updated?'ok':'warn');}catch(e){msg($('verifyResult'),e.message,'bad');}});
$('verifyScanned').addEventListener('keydown',e=>{if(e.key==='Enter')$('verifyBtn').click();});

/** WHY: El historial guarda el estado ANTES de cada operación lógica, no después de
 *  cada píxel. Un arrastre completo es una sola entrada, así Ctrl+Z devuelve el objeto
 *  a donde estaba antes de tomarlo y no obliga a pulsar deshacer doscientas veces. */
const HISTORY_LIMIT = 60;
const HISTORY_COALESCE_MS = 700;

/** WHY: Captura el borrador completo antes de mutarlo. Se coalescen ediciones
 *  consecutivas de la misma propiedad para que escribir "12.5" en X no genere
 *  cuatro pasos de deshacer, uno por tecla. */
function pushHistory(label){
  const t=state.designerTemplate; if(!t)return;
  const now=Date.now();
  const h=state.designerHistory;
  if(label && h.lastLabel===label && (now-h.lastAt)<HISTORY_COALESCE_MS){ h.lastAt=now; return; }
  h.past.push({template:deepClone(t), selection:[...state.designerSelection], selected:state.designerSelected});
  if(h.past.length>HISTORY_LIMIT) h.past.shift();
  h.future.length=0;
  h.lastLabel=label||''; h.lastAt=now;
  updateHistoryButtons();
}

/** WHY: Un snapshot del estado actual; se usa para poder rehacer lo que se deshace. */
function historySnapshot(){
  return {template:deepClone(state.designerTemplate), selection:[...state.designerSelection], selected:state.designerSelected};
}

/** WHY: Restaura un snapshot completo en lugar de aplicar deltas; es más simple de
 *  auditar y no puede desincronizar el JSON, el lienzo y la vista real. */
function applySnapshot(snap){
  state.designerTemplate=snap.template;
  state.designerSelection=[...snap.selection];
  state.designerSelected=snap.selected;
  loadDesignerHeaderFields();
  renderDesignerFields();
  renderDesignerCanvas();
  renderDesignerProperties();
  scheduleDesignerPreview();
  updateHistoryButtons();
}

/** WHY: Deshacer y rehacer comparten estructura para que nunca puedan divergir. */
function undoDesigner(){
  const h=state.designerHistory; if(!h.past.length)return;
  h.future.push(historySnapshot());
  h.lastLabel=''; applySnapshot(h.past.pop());
}
/** WHY: Rehacer es la operación inversa exacta de deshacer; comparte estructura para
 *  que una pila no pueda quedar desincronizada respecto de la otra. */
function redoDesigner(){
  const h=state.designerHistory; if(!h.future.length)return;
  h.past.push(historySnapshot());
  h.lastLabel=''; applySnapshot(h.future.pop());
}

/** WHY: Los botones deshabilitados comunican el estado real del historial; un botón
 *  siempre activo que no hace nada es peor que uno gris. */
function updateHistoryButtons(){
  if($('undoBtn')) $('undoBtn').disabled=!state.designerHistory.past.length;
  if($('redoBtn')) $('redoBtn').disabled=!state.designerHistory.future.length;
}

/** WHY: Relee la cabecera del borrador al restaurar historial; sin esto, deshacer un
 *  cambio de ancho dejaría el formulario mostrando el valor viejo. */
function loadDesignerHeaderFields(){
  const t=state.designerTemplate; if(!t)return;
  if($('designerName')) $('designerName').value=t.name||'';
  if($('designerId')) $('designerId').value=t.id||'';
  if($('designerCategory')) $('designerCategory').value=t.category||'';
  if($('designerWidth')) $('designerWidth').value=t.width_mm;
  if($('designerHeight')) $('designerHeight').value=t.height_mm;
  if($('designerQuality')) $('designerQuality').value=t.quality_profile||'';
}

// ------------------------------------------------------------------ SNAP

/** WHY: El imantado ayuda a componer pero estorba en ajuste fino, así que se puede
 *  desactivar y su tolerancia se expresa en píxeles de pantalla convertidos a mm:
 *  a más zoom, menos milímetros de imantado, que es lo que espera el usuario. */
function snapSettings(){
  const enabled=$('snapEnabled')?$('snapEnabled').checked:false;
  const grid=Math.max(.1,Number($('snapGrid')?.value)||0.5);
  const tolerance=6/Math.max(.0001,state.designerScale||1); // 6 px de pantalla
  return {enabled,grid,tolerance};
}

/** WHY: Devuelve las líneas a las que un objeto puede imantarse: rejilla, centro del
 *  lienzo y bordes/centros de los demás elementos. Excluye el propio objeto para que
 *  no se imante consigo mismo. */
function snapCandidates(axis, excludeIndices){
  const t=state.designerTemplate; const out=[];
  const span=axis==='x'?t.width_mm:t.height_mm;
  out.push({value:0,type:'canvas'},{value:span/2,type:'canvas-center'},{value:span,type:'canvas'});
  t.elements.forEach((el,i)=>{
    if(excludeIndices.includes(i))return;
    const b=designerBounds(el);
    if(axis==='x') out.push({value:b.x,type:'element'},{value:b.x+b.w/2,type:'element-center'},{value:b.x+b.w,type:'element'});
    else out.push({value:b.y,type:'element'},{value:b.y+b.h/2,type:'element-center'},{value:b.y+b.h,type:'element'});
  });
  return out;
}

/** WHY: Imanta el borde inicial, el centro y el borde final del objeto, no sólo su
 *  esquina: alinear por centro es lo que más se necesita al componer una etiqueta. */
function applySnap(axis, position, size, excludeIndices){
  const {enabled,grid,tolerance}=snapSettings();
  if(!enabled) return {value:position, guide:null};
  const candidates=snapCandidates(axis,excludeIndices);
  let best=null;
  for(const anchorOffset of [0,size/2,size]){
    for(const c of candidates){
      const target=c.value-anchorOffset;
      const d=Math.abs(target-position);
      if(d<=tolerance && (!best || d<best.d)) best={d,value:target,guide:c.value};
    }
  }
  if(best) return {value:best.value, guide:{axis,at:best.guide}};
  const snapped=Math.round(position/grid)*grid;
  return {value:Math.abs(snapped-position)<=tolerance?snapped:position, guide:null};
}

/** WHY: Caja física del elemento en mm. El texto se ancla en su línea base, así que su
 *  caja visual arranca una altura de fuente más arriba; sin esta corrección la
 *  alineación superior dejaría el texto fuera del lienzo. */
function designerBounds(el){
  const size=designerElementSize(el);
  const y=el.kind==='text'?Math.max(0,el.y_mm-(el.font_size_mm||4)):el.y_mm;
  return {x:el.x_mm,y,w:size.w,h:size.h};
}

/** WHY: Traslada un elemento fijando el borde superior de su caja visual, respetando
 *  la diferencia de anclaje del texto. Centraliza la conversión caja→modelo. */
function setDesignerBounds(el,x,y){
  if(x!=null) el.x_mm=Math.max(0,Number(x.toFixed(4)));
  if(y!=null){
    const value=el.kind==='text'?y+(el.font_size_mm||4):y;
    el.y_mm=Math.max(0,Number(value.toFixed(4)));
  }
}

/** WHY: Dibuja la guía de imantado sólo mientras dura el arrastre; una guía persistente
 *  se confundiría con geometría real de la plantilla. */
function renderSnapGuides(guides){
  const c=$('designerCanvas'); if(!c)return;
  c.querySelectorAll('.snap-guide').forEach(g=>g.remove());
  const sc=state.designerScale;
  for(const g of guides){
    if(!g)continue;
    const d=document.createElement('div');
    d.className='snap-guide '+(g.axis==='x'?'vertical':'horizontal');
    if(g.axis==='x') d.style.left=`${g.at*sc}px`; else d.style.top=`${g.at*sc}px`;
    c.appendChild(d);
  }
}

// ------------------------------------------------------- SELECCION MULTIPLE

/** WHY: La selección múltiple es lo que da sentido a alinear y distribuir. Se mantiene
 *  como lista ordenada; ``designerSelected`` sigue siendo el elemento del inspector
 *  para no duplicar el concepto de "elemento activo". */
function setDesignerSelection(indices, primary){
  state.designerSelection=[...new Set(indices.filter(i=>i>=0))];
  state.designerSelected=primary!=null?primary:(state.designerSelection.at(-1)??-1);
  updateSelectionInfo();
}

/** WHY: Ctrl/Shift+clic alterna pertenencia a la selección; sin modificador, sustituye.
 *  Es el comportamiento que el usuario ya conoce de cualquier editor. */
function toggleDesignerSelection(index, additive){
  if(!additive) return setDesignerSelection([index],index);
  const sel=new Set(state.designerSelection);
  if(sel.has(index)){ sel.delete(index); }
  else sel.add(index);
  const list=[...sel];
  setDesignerSelection(list, sel.has(index)?index:(list.at(-1)??-1));
}

/** WHY: Informa cuántos objetos hay seleccionados porque alinear con uno solo no hace
 *  nada visible y el usuario necesita saber por qué. */
function updateSelectionInfo(){
  const info=$('designerSelectionInfo'); if(!info)return;
  const n=state.designerSelection.length;
  info.textContent = n===0 ? 'Sin selección. Ctrl+clic o Shift+clic para seleccionar varios.'
    : n===1 ? '1 elemento seleccionado. Seleccione 2 o más para alinear o distribuir.'
    : `${n} elementos seleccionados.`;
  document.querySelectorAll('#alignGroup button[data-align]').forEach(b=>{
    const needsThree=b.dataset.align.startsWith('dist-');
    b.disabled = needsThree ? n<3 : n<2;
  });
}

// ------------------------------------------------------------- ALINEACION

/** WHY: Todas las acciones trabajan sobre milímetros físicos y no sobre píxeles del
 *  lienzo; el zoom no debe cambiar el resultado de alinear. */
function alignDesignerSelection(action){
  const t=state.designerTemplate; if(!t)return;
  const idx=state.designerSelection;
  const needsThree=action.startsWith('dist-');
  if(idx.length<(needsThree?3:2))return;
  pushHistory('align:'+action+':'+Date.now());
  const items=idx.map(i=>({i,el:t.elements[i],b:designerBounds(t.elements[i])}));
  const minX=Math.min(...items.map(o=>o.b.x));
  const maxX=Math.max(...items.map(o=>o.b.x+o.b.w));
  const minY=Math.min(...items.map(o=>o.b.y));
  const maxY=Math.max(...items.map(o=>o.b.y+o.b.h));
  if(action==='left') items.forEach(o=>setDesignerBounds(o.el,minX,null));
  if(action==='right') items.forEach(o=>setDesignerBounds(o.el,maxX-o.b.w,null));
  if(action==='center-h'){const c=(minX+maxX)/2;items.forEach(o=>setDesignerBounds(o.el,c-o.b.w/2,null));}
  if(action==='top') items.forEach(o=>setDesignerBounds(o.el,null,minY));
  if(action==='bottom') items.forEach(o=>setDesignerBounds(o.el,null,maxY-o.b.h));
  if(action==='center-v'){const c=(minY+maxY)/2;items.forEach(o=>setDesignerBounds(o.el,null,c-o.b.h/2));}
  if(action==='dist-h'){
    const sorted=[...items].sort((a,b)=>a.b.x-b.b.x);
    const total=sorted.reduce((s,o)=>s+o.b.w,0);
    const gap=((maxX-minX)-total)/(sorted.length-1);
    let cursor=minX;
    sorted.forEach(o=>{setDesignerBounds(o.el,cursor,null);cursor+=o.b.w+gap;});
  }
  if(action==='dist-v'){
    const sorted=[...items].sort((a,b)=>a.b.y-b.b.y);
    const total=sorted.reduce((s,o)=>s+o.b.h,0);
    const gap=((maxY-minY)-total)/(sorted.length-1);
    let cursor=minY;
    sorted.forEach(o=>{setDesignerBounds(o.el,null,cursor);cursor+=o.b.h+gap;});
  }
  renderDesignerCanvas();renderDesignerProperties();scheduleDesignerPreview();
}

/** WHY: Clona plantillas/elementos editables sin compartir referencias que provocarían cambios accidentales. */
function deepClone(x){return JSON.parse(JSON.stringify(x));}
/** WHY: Normaliza IDs creados por el diseñador para que sean válidos como archivo, API y referencia histórica. */
function safeDesignerId(value){return String(value||'').trim().replace(/[^A-Za-z0-9_-]+/g,'_').replace(/^_+|_+$/g,'').slice(0,96)||'custom_template';}
/** WHY: Crea el borrador mínimo de una plantilla nueva sin imponer un tipo de equipo. */
function blankDesignerTemplate(){
  const quality=state.catalog?.quality_profiles?.[0]?.id||'rugged_field_v1';
  return {id:`custom_${Date.now()}`,name:'Nueva plantilla',version:'1.0',category:'custom',description:'Plantilla creada desde el estudio visual',width_mm:50,height_mm:25,quality_profile:quality,calibration_required:true,expected_fields:['value'],input_rules:[],marking_mode:defaultMarkingMode(),elements:[],metadata:{primary_identity_field:'value',example_data:{value:'EJEMPLO'},created_with:'visual_designer_v0.8.0'}};
}
/** WHY: Obtiene los campos actuales del borrador para alimentar propiedades, reglas y preview. */
function designerFields(){return [...new Set((state.designerTemplate?.expected_fields||[]).filter(Boolean))];}
/** WHY: Sincroniza metadatos visibles del formulario con el objeto de plantilla antes de renderizar/guardar. */
function syncDesignerHeaderToDraft(){
  const t=state.designerTemplate;if(!t)return;
  t.name=$('designerName').value.trim()||'Plantilla sin nombre'; t.id=safeDesignerId($('designerId').value); $('designerId').value=t.id;
  t.category=$('designerCategory').value.trim()||'custom'; t.width_mm=Math.max(1,Number($('designerWidth').value)||1); t.height_mm=Math.max(1,Number($('designerHeight').value)||1); t.quality_profile=$('designerQuality').value||t.quality_profile;
  t.metadata=t.metadata||{}; t.metadata.primary_identity_field=$('designerPrimaryField').value||designerFields()[0]||''; t.marking_mode=readMarkingControls('designer');
}
/** WHY: Abre una plantilla en el estudio visual como copia editable y prepara todos los paneles. */
function loadDesignerFromTemplate(template){
  state.designerTemplate=deepClone(template); state.designerSelected=-1;
  const t=state.designerTemplate; t.metadata=t.metadata||{}; t.expected_fields=t.expected_fields||[]; t.input_rules=t.input_rules||[]; t.elements=t.elements||[]; t.marking_mode=t.marking_mode||defaultMarkingMode(); fillMarkingControls('designer',t);
  $('designerName').value=t.name||''; $('designerId').value=t.id||''; $('designerCategory').value=t.category||'custom'; $('designerWidth').value=t.width_mm; $('designerHeight').value=t.height_mm; $('designerQuality').value=t.quality_profile;
  renderDesignerFields(); renderDesignerCanvas(); renderDesignerProperties(); updateDesignerJson(); scheduleDesignerPreview();
}
/** WHY: Sincroniza editores visual/JSON/jig al cambiar la selección de configuración. */
function loadConfigEditors(){
  const t=selectedTemplate('configTemplate'); if(t) loadDesignerFromTemplate(t);
  const j=state.catalog.jigs.find(x=>x.id===$('configJig').value); if(j)$('jigJson').value=JSON.stringify(Object.fromEntries(Object.entries(j).filter(([k])=>!['capacity','slots'].includes(k))),null,2);
}
/** WHY: Mantiene una representación JSON de auditoría del borrador sin que sea el flujo principal para principiantes. */
function updateDesignerJson(){if(state.designerTemplate&&$('templateJson'))$('templateJson').value=JSON.stringify(state.designerTemplate,null,2);}
/** WHY: Dibuja variables de plantilla y ejemplos para que el usuario vea qué datos espera el diseño. */
function renderDesignerFields(){
  const t=state.designerTemplate;if(!t)return; const fields=designerFields();
  $('designerFieldsList').innerHTML=fields.map(f=>`<span class="field-chip">${esc(f)} <button data-remove-field="${esc(f)}" title="Quitar">×</button></span>`).join('')||'<span class="muted">Sin campos.</span>';
  $('designerFieldsList').querySelectorAll('[data-remove-field]').forEach(b=>b.addEventListener('click',()=>{const f=b.dataset.removeField;t.expected_fields=t.expected_fields.filter(x=>x!==f);t.input_rules=(t.input_rules||[]).filter(x=>x.field!==f);renderDesignerFields();renderDesignerProperties();updateDesignerJson();scheduleDesignerPreview();}));
  const opts=fields.map(f=>`<option value="${esc(f)}">${esc(f)}</option>`).join('');
  $('ruleField').innerHTML=opts; $('designerPrimaryField').innerHTML=opts; $('designerPrimaryField').value=t.metadata?.primary_identity_field||fields[0]||'';
  const oldData={};$('designerDataFields').querySelectorAll('input[data-designer-field]').forEach(i=>oldData[i.dataset.designerField]=i.value);
  $('designerDataFields').innerHTML=fields.map(f=>`<label>${esc(f)}<input data-designer-field="${esc(f)}" value="${esc(oldData[f]??t.metadata?.example_data?.[f]??(f==='value'?'EJEMPLO':''))}" /></label>`).join('');
  $('designerDataFields').querySelectorAll('input').forEach(i=>i.addEventListener('input',scheduleDesignerPreview));
  loadInputRuleForm();
}
/** WHY: Carga prefijo/sufijo y política de importación del campo seleccionado. */
function loadInputRuleForm(){
  const t=state.designerTemplate;if(!t)return; const field=$('ruleField').value; const r=(t.input_rules||[]).find(x=>x.field===field)||{};
  $('rulePrefixEnabled').checked=!!r.manual_prefix_enabled; $('rulePrefix').value=r.manual_prefix||''; $('ruleSuffixEnabled').checked=!!r.manual_suffix_enabled; $('ruleSuffix').value=r.manual_suffix||''; $('ruleImportedMode').value=r.imported_values||'as_is'; $('ruleUppercase').checked=!!r.uppercase;
}
/** WHY: Calcula el tamaño aproximado del objeto en canvas para arrastre y límites, no como sustituto del SVG real. */
function designerElementSize(el){
  if(el.kind==='text')return {w:el.width_mm||20,h:Math.max(el.font_size_mm||4,3)};
  if(['qr','datamatrix'].includes(el.kind)){const m=el.module_mm||.5;return {w:el.width_mm||Math.max(12,29*m),h:el.height_mm||Math.max(12,29*m)};}
  if(['code128','code39'].includes(el.kind))return {w:el.width_mm||35,h:el.height_mm||10};
  if(el.kind==='image')return {w:el.width_mm||20,h:el.height_mm||20};
  return {w:el.width_mm||12,h:el.height_mm||4};
}
/** WHY: Representa cada objeto de forma reconocible en el canvas incluso antes del render SVG real. */
function designerObjectLabel(el,index){
  const field=el.source||''; const lit=el.literal;
  if(el.kind==='text')return lit!=null?esc(lit):esc(field||'texto');
  if(el.kind==='qr')return `<span class="fake-qr">▦</span><small>${esc(field||'QR')}${el.engraving_mode==='negative_background'?' · NEG':''}</small>`;
  if(el.kind==='datamatrix')return `<span class="fake-qr">▩</span><small>${esc(field||'DM')}${el.engraving_mode==='negative_background'?' · NEG':''}</small>`;
  if(['code128','code39'].includes(el.kind))return `<span class="fake-bars"></span><small>${esc(field||el.kind)}${el.engraving_mode==='negative_background'?' · NEG':''}</small>`;
  if(el.kind==='image')return `<span class="fake-image">▧</span><small>${esc(el.image_source_name||'imagen')}</small>`;
  if(el.kind==='rect')return '<small>rectángulo</small>'; if(el.kind==='line')return '<small>línea</small>'; return `<small>${index+1}</small>`;
}
/** WHY: Redibuja el lienzo interactivo a escala manteniendo posiciones en milímetros. */
function renderDesignerCanvas(){
  const t=state.designerTemplate;if(!t)return; syncDesignerHeaderToDraft(); const maxW=650,maxH=420; state.designerScale=Math.max(.25,Math.min(12,maxW/t.width_mm,maxH/t.height_mm)); const sc=state.designerScale;
  const c=$('designerCanvas');c.style.width=`${t.width_mm*sc}px`;c.style.height=`${t.height_mm*sc}px`;c.innerHTML=''; $('designerSizeLabel').textContent=`${t.width_mm} × ${t.height_mm} mm · ${sc.toFixed(2)} px/mm`;
  t.elements.forEach((el,index)=>{const size=designerElementSize(el);const d=document.createElement('div');
    const inSel=state.designerSelection.includes(index);
    d.className='design-object kind-'+el.kind+(index===state.designerSelected?' selected':'')+(inSel?' multi':'')+(state.mappingFocus&&el.source===state.mappingFocus?' mapping-hit':'');
    d.dataset.index=index;const top=(el.kind==='text'?Math.max(0,el.y_mm-(el.font_size_mm||4)):el.y_mm);
    d.style.left=`${el.x_mm*sc}px`;d.style.top=`${top*sc}px`;d.style.width=`${Math.max(6,size.w*sc)}px`;d.style.height=`${Math.max(6,size.h*sc)}px`;
    // WHY: La rotación se previsualiza en el lienzo con el mismo centro que usa el
    // backend, para que lo que el usuario gira aquí coincida con el SVG real.
    if(el.rotation_deg) d.style.transform=`rotate(${el.rotation_deg}deg)`;
    d.innerHTML=designerObjectLabel(el,index);d.title=`${el.label||el.kind} · X ${el.x_mm.toFixed(1)} · Y ${el.y_mm.toFixed(1)} mm${el.rotation_deg?` · ${el.rotation_deg}°`:''}`;
    d.addEventListener('pointerdown',beginDesignerDrag);
    d.addEventListener('click',ev=>{ev.stopPropagation();toggleDesignerSelection(index,ev.ctrlKey||ev.metaKey||ev.shiftKey);renderDesignerCanvas();renderDesignerProperties();});
    c.appendChild(d);});
  c.onclick=()=>{setDesignerSelection([],-1);renderDesignerCanvas();renderDesignerProperties();}; renderDesignerLayerList(); updateDesignerJson(); updateSelectionInfo(); updateHistoryButtons();
}
/** WHY: Convierte movimiento del puntero a milímetros y limita el objeto a la superficie de la plantilla. */
function beginDesignerDrag(ev){
  ev.preventDefault();ev.stopPropagation(); const node=ev.currentTarget;const index=Number(node.dataset.index);
  if(!state.designerSelection.includes(index)) toggleDesignerSelection(index,ev.ctrlKey||ev.metaKey||ev.shiftKey);
  else state.designerSelected=index;
  renderDesignerProperties();
  const t=state.designerTemplate,el=t.elements[index],sc=state.designerScale;
  // WHY: Una sola entrada de historial por arrastre. Se registra al tomar el objeto,
  // antes de mover nada, para que deshacer devuelva la posición original exacta.
  pushHistory('drag:'+index+':'+Date.now());
  const moving=(state.designerSelection.length>1?state.designerSelection:[index]);
  const origins=moving.map(i=>({i,el:t.elements[i],b:designerBounds(t.elements[i])}));
  const sx=ev.clientX,sy=ev.clientY;node.setPointerCapture?.(ev.pointerId);node.classList.add('dragging');
  const move=e=>{
    const dx=(e.clientX-sx)/sc,dy=(e.clientY-sy)/sc;
    const lead=origins.find(o=>o.i===index);
    // El imantado se calcula sobre el objeto tomado y el mismo delta se aplica al
    // resto de la selección, para no deformar la composición ya construida.
    const sx1=applySnap('x',lead.b.x+dx,lead.b.w,moving);
    const sy1=applySnap('y',lead.b.y+dy,lead.b.h,moving);
    const adx=sx1.value-lead.b.x, ady=sy1.value-lead.b.y;
    for(const o of origins){
      const nx=Math.max(0,Math.min(t.width_mm-Math.min(o.b.w,t.width_mm),o.b.x+adx));
      const ny=Math.max(0,Math.min(t.height_mm,o.b.y+ady));
      setDesignerBounds(o.el,nx,ny);
    }
    renderDesignerCanvas();renderSnapGuides([sx1.guide,sy1.guide]);renderDesignerProperties();scheduleDesignerPreview();
  };
  const up=()=>{document.removeEventListener('pointermove',move);document.removeEventListener('pointerup',up);renderSnapGuides([]);updateDesignerJson();};
  document.addEventListener('pointermove',move);document.addEventListener('pointerup',up,{once:true});
}
/** WHY: Ofrece una lista de capas alternativa al canvas; facilita seleccionar objetos pequeños, solapados o difíciles de clicar. */
function renderDesignerLayerList(){
  const host=$('designerLayerList'); if(!host)return; const items=state.designerTemplate?.elements||[];
  host.innerHTML=items.length?items.map((el,i)=>`<button class="layer-item ${i===state.designerSelected?'active':''} ${state.designerSelection.includes(i)?'in-selection':''} ${state.mappingFocus&&el.source===state.mappingFocus?'mapping-hit':''}" data-layer-index="${i}"><span>${i+1}</span><strong>${esc(el.label||el.kind)}</strong><small>${esc(el.kind)}${el.rotation_deg?` · ${el.rotation_deg}°`:''}</small></button>`).join(''):'<span class="muted">Aún no hay elementos.</span>';
  host.querySelectorAll('[data-layer-index]').forEach(b=>b.addEventListener('click',ev=>{toggleDesignerSelection(Number(b.dataset.layerIndex),ev.ctrlKey||ev.metaKey||ev.shiftKey);renderDesignerCanvas();renderDesignerProperties();}));
}
/** WHY: Carga el elemento seleccionado en el inspector para edición precisa además del arrastre visual. */
function renderDesignerProperties(){
  renderDesignerLayerList();
  const t=state.designerTemplate;const el=t?.elements?.[state.designerSelected];$('designerPropertyForm').hidden=!el;$('designerNoSelection').hidden=!!el;$('designerSelectionLabel').textContent=el?(el.label||`elemento ${state.designerSelected+1}`):'sin selección';if(!el)return;
  const fields=designerFields();$('propSource').innerHTML='<option value="">— sin campo / texto fijo —</option>'+fields.map(f=>`<option value="${esc(f)}">${esc(f)}</option>`).join('');
  $('propLabel').value=el.label||'';$('propKind').value=el.kind;$('propSource').value=el.source||'';$('propLiteral').value=el.literal??'';$('propX').value=el.x_mm;$('propY').value=el.y_mm;$('propWidth').value=el.width_mm??'';$('propHeight').value=el.height_mm??'';$('propFont').value=el.font_size_mm??4;$('propModule').value=el.module_mm??'';$('propAlign').value=el.align||'center';$('propEc').value=el.error_correction||'M';$('propRotation').value=el.rotation_deg??0;$('propQuiet').value=el.quiet_modules??'';$('propEngravingMode').value=el.engraving_mode||'positive';
  if($('imagePropertyGroup')){
    $('imagePropertyGroup').hidden=el.kind!=='image';
    $('propImageProcessing').value=el.image_processing||'auto';
    $('propImageThreshold').value=el.image_threshold??128;
    $('propImageDpi').value=el.image_dpi??254;
    $('propImageAspect').checked=el.image_preserve_aspect!==false;
    $('propImageSource').textContent=el.kind==='image'?(el.image_source_name||'imagen embebida'):'';
  }
  applyDesignerPropertyAvailability(el);
}
/** WHY: Deshabilita propiedades que no aplican al tipo de elemento y evita configuraciones incoherentes. */
function applyDesignerPropertyAvailability(el){
  const dataKinds=['text','code128','code39','qr','datamatrix'];
  const barcodeKinds=['code128','code39'];
  const matrixKinds=['qr','datamatrix'];
  $('propSource').disabled=!dataKinds.includes(el.kind);
  $('propLiteral').disabled=!dataKinds.includes(el.kind);
  $('propWidth').disabled=matrixKinds.includes(el.kind);
  $('propHeight').disabled=matrixKinds.includes(el.kind);
  $('propFont').disabled=el.kind!=='text';
  $('propModule').disabled=!(barcodeKinds.includes(el.kind)||matrixKinds.includes(el.kind));
  $('propAlign').disabled=!(el.kind==='text'||barcodeKinds.includes(el.kind));
  $('propEc').disabled=el.kind!=='qr';
  const codeKinds=[...barcodeKinds,...matrixKinds];
  $('propQuiet').disabled=!codeKinds.includes(el.kind);
  $('propQuiet').title=codeKinds.includes(el.kind)?'Módulos de silencio alrededor del código. Vacío hereda el perfil de calidad.':'Sólo aplica a códigos de barras y matriciales.';
  if($('quietHint')) $('quietHint').hidden=!codeKinds.includes(el.kind);
  $('propEngravingMode').disabled=!codeKinds.includes(el.kind);
  if($('engravingModeHint')) $('engravingModeHint').hidden=!codeKinds.includes(el.kind);
  $('propWidth').title=matrixKinds.includes(el.kind)?'El tamaño de QR/Data Matrix depende del contenido y del módulo (mm).':'';
  $('propHeight').title=$('propWidth').title;
  $('propModule').title=(barcodeKinds.includes(el.kind)||matrixKinds.includes(el.kind))?'Tamaño físico del módulo; use valores aprobados por el perfil de calidad o por pruebas reales.':'';
}
/** WHY: Crea un elemento genérico con valores iniciales seguros y opcionalmente lo coloca donde se soltó. */
function addDesignerElement(kind,role='variable',dropX=null,dropY=null){
  const t=state.designerTemplate;if(!t)return; if(!designerFields().length&&['text','code128','code39','qr','datamatrix'].includes(kind)){t.expected_fields=['value'];t.metadata.primary_identity_field='value';renderDesignerFields();}
  const f=designerFields()[0]||'value';let el={kind,x_mm:2,y_mm:2,source:f,literal:null,width_mm:null,height_mm:null,font_size_mm:4,align:'center',module_mm:null,error_correction:'M',stroke_mm:.25,label:kind,engraving_mode:'positive'};
  if(kind==='text'){el.y_mm=8;el.width_mm=Math.min(30,Math.max(5,t.width_mm-4));el.label=role==='literal'?'Texto fijo':'Texto / serie';if(role==='literal'){el.source=null;el.literal='TEXTO';}}
  if(kind==='code128'||kind==='code39'){el.width_mm=Math.min(45,Math.max(10,t.width_mm-4));el.height_mm=Math.min(10,Math.max(4,t.height_mm-8));el.label=kind==='code128'?'Code 128':'Code 39';}
  if(kind==='qr'||kind==='datamatrix'){el.module_mm=.5;el.label=kind==='qr'?'QR':'Data Matrix';}
  if(kind==='rect'){el.source=null;el.literal=null;el.width_mm=Math.min(20,t.width_mm-4);el.height_mm=Math.min(10,t.height_mm-4);el.label='Rectángulo';}
  if(kind==='line'){el.source=null;el.literal=null;el.width_mm=Math.min(20,t.width_mm-4);el.height_mm=.1;el.label='Línea';}
  if(dropX!=null&&dropY!=null){
    const size=designerElementSize(el); el.x_mm=Math.max(0,Math.min(t.width_mm-Math.min(size.w,t.width_mm),dropX));
    el.y_mm=el.kind==='text'?Math.max(el.font_size_mm||4,Math.min(t.height_mm,dropY+(el.font_size_mm||4))):Math.max(0,Math.min(t.height_mm-Math.min(size.h,t.height_mm),dropY));
  }
  pushHistory('add:'+Date.now());
  t.elements.push(el);setDesignerSelection([t.elements.length-1],t.elements.length-1);renderDesignerCanvas();renderDesignerProperties();scheduleDesignerPreview();
}
/** WHY: Convierte un archivo local en un elemento imagen embebido sin depender de rutas del PC del operador. */
function addOrReplaceDesignerImage(file,replaceIndex=null){
  if(!file)return; const max=3*1024*1024;
  if(file.size>max){msg($('designerWarnings'),'La imagen supera 3 MB; reduzca el archivo antes de integrarlo.','bad');return;}
  const ext=(file.name.split('.').pop()||'').toLowerCase();
  const mime=ext==='svg'?'image/svg+xml':(['jpg','jpeg'].includes(ext)?'image/jpeg':'image/png');
  if(!['png','jpg','jpeg','svg'].includes(ext)){msg($('designerWarnings'),'Formato no soportado. Use PNG, JPG/JPEG o SVG.','bad');return;}
  const reader=new FileReader();
  reader.onload=()=>{
    const raw=String(reader.result||''); const payload=raw.includes(',')?raw.split(',',2)[1]:'';
    if(!payload){msg($('designerWarnings'),'No se pudo leer la imagen.','bad');return;}
    const uri=`data:${mime};base64,${payload}`; const t=state.designerTemplate;if(!t)return;
    pushHistory('image:'+Date.now());
    if(replaceIndex!=null&&t.elements[replaceIndex]?.kind==='image'){
      const el=t.elements[replaceIndex];el.image_data_uri=uri;el.image_source_name=file.name;el.image_processing=ext==='svg'?'vector':'threshold';
      setDesignerSelection([replaceIndex],replaceIndex);
    }else{
      const w=Math.min(20,Math.max(5,t.width_mm-4)),h=Math.min(20,Math.max(5,t.height_mm-4));
      const el={kind:'image',x_mm:2,y_mm:2,source:null,literal:null,width_mm:w,height_mm:h,font_size_mm:4,align:'center',module_mm:null,error_correction:'M',stroke_mm:.25,label:'Imagen / logo',engraving_mode:'positive',rotation_deg:0,quiet_modules:null,image_data_uri:uri,image_processing:ext==='svg'?'vector':'threshold',image_threshold:128,image_dpi:254,image_preserve_aspect:true,image_source_name:file.name};
      t.elements.push(el);setDesignerSelection([t.elements.length-1],t.elements.length-1);
    }
    renderDesignerCanvas();renderDesignerProperties();scheduleDesignerPreview();
  };
  reader.readAsDataURL(file);
}
/** WHY: Devuelve la selección actual como único punto de acceso para acciones de propiedades. */
function selectedDesignerElement(){return state.designerTemplate?.elements?.[state.designerSelected]||null;}
/** WHY: Aplica cambios del inspector al borrador y refresca canvas/preview en tiempo real. */
function updateSelectedElementFromProperties(){
  const el=selectedDesignerElement();if(!el)return;
  pushHistory('prop:'+state.designerSelected);
  el.label=$('propLabel').value.trim()||el.kind;el.x_mm=Math.max(0,Number($('propX').value)||0);el.y_mm=Math.max(0,Number($('propY').value)||0);el.width_mm=$('propWidth').value?Math.max(.1,Number($('propWidth').value)):null;el.height_mm=$('propHeight').value?Math.max(.1,Number($('propHeight').value)):null;el.font_size_mm=Math.max(.1,Number($('propFont').value)||4);el.module_mm=$('propModule').value?Math.max(.01,Number($('propModule').value)):null;el.align=$('propAlign').value;el.error_correction=$('propEc').value;
  el.rotation_deg=((Number($('propRotation').value)||0)%360+360)%360;
  // WHY: Vacío significa "heredar el perfil", que es distinto de 0. Un 0 explícito es
  // una decisión del usuario y debe conservarse para que el preflight lo advierta.
  el.quiet_modules=$('propQuiet').value===''?null:Math.max(0,Math.min(64,Number($('propQuiet').value)||0));
  el.engraving_mode=['code128','code39','qr','datamatrix'].includes(el.kind)?($('propEngravingMode').value||'positive'):'positive';
  if(el.kind==='image'){
    el.source=null;el.literal=null;el.image_processing=$('propImageProcessing').value||'auto';
    el.image_threshold=Math.max(0,Math.min(255,Number($('propImageThreshold').value)||128));
    el.image_dpi=Math.max(50,Math.min(1200,Number($('propImageDpi').value)||254));
    el.image_preserve_aspect=$('propImageAspect').checked;
  }else{const source=$('propSource').value,lit=$('propLiteral').value;if(lit.trim()){el.literal=lit;el.source=null;}else{el.literal=null;el.source=source||null;}}
  renderDesignerCanvas();scheduleDesignerPreview();
}
/** WHY: Recoge datos de ejemplo usados sólo para visualizar el resultado real de la plantilla. */
function designerData(){const data={};$('designerDataFields').querySelectorAll('[data-designer-field]').forEach(i=>data[i.dataset.designerField]=i.value);return data;}
/** WHY: Agrupa cambios rápidos antes de llamar al backend y evita renders excesivos durante arrastre/escritura. */
function scheduleDesignerPreview(){clearTimeout(state.designerPreviewTimer);if($('designerQualityResult'))$('designerQualityResult').innerHTML='';state.designerPreviewTimer=setTimeout(renderDesignerPreview,140);}
/** WHY: Solicita al backend el SVG real del borrador para que la vista final no difiera del motor productivo. */
async function renderDesignerPreview(){
  const t=state.designerTemplate;if(!t)return;syncDesignerHeaderToDraft();clear($('designerWarnings'));
  try{const r=await api('/api/templates/preview',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({template:t,data:designerData(),capture_mode:'manual',output:'svg'})});const j=await r.json();$('designerPreview').innerHTML=j.svg;(j.warnings||[]).forEach(w=>msg($('designerWarnings'),w,'warn'));updateDesignerJson();}
  catch(e){$('designerPreview').innerHTML='<span class="muted">Corrija la plantilla para ver el SVG real.</span>';msg($('designerWarnings'),e.message,'bad');}
}
/** WHY: Recarga configuración después de guardar para hacer la nueva plantilla disponible en todos los flujos. */
async function refreshCatalogAfterTemplateSave(templateId){
  state.catalog=await (await api('/api/catalog')).json(); ['individualTemplate','batchTemplate','configTemplate'].forEach(id=>fillSelect($(id),state.catalog.templates)); fillSelect($('designerQuality'),state.catalog.quality_profiles); $('configTemplate').value=templateId; $('individualTemplate').value=templateId; $('batchTemplate').value=templateId; updateBatchJigs(); renderIndividualFields();
}
/** WHY: Valida requisitos mínimos y persiste el borrador creado en el estudio visual. */
async function saveVisualTemplate(){
  clear($('designerSaveMsg'));syncDesignerHeaderToDraft();const t=state.designerTemplate;if(!t.elements.length){msg($('designerSaveMsg'),'Agregue al menos un elemento antes de guardar.','warn');return;}
  try{await api('/api/templates/save',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({template:t})});await refreshCatalogAfterTemplateSave(t.id);loadDesignerFromTemplate(state.catalog.templates.find(x=>x.id===t.id));msg($('designerSaveMsg'),'Plantilla guardada y disponible en Generador y Lotes/CSV.','ok');}
  catch(e){msg($('designerSaveMsg'),e.message,'bad');}
}
/** WHY: Conecta drag&drop, teclado y acciones del diseñador una sola vez al iniciar la UI. */
function initVisualDesigner(){
  document.querySelectorAll('[data-add-kind]').forEach(b=>{
    b.draggable=true;
    b.addEventListener('click',()=>addDesignerElement(b.dataset.addKind,b.dataset.role||'variable'));
    b.addEventListener('dragstart',e=>{e.dataTransfer.effectAllowed='copy';e.dataTransfer.setData('application/x-marking-element',JSON.stringify({kind:b.dataset.addKind,role:b.dataset.role||'variable'}));});
  });
  $('designerCanvas').addEventListener('dragover',e=>{if(e.dataTransfer.types.includes('application/x-marking-element')){e.preventDefault();e.dataTransfer.dropEffect='copy';}});
  $('designerCanvas').addEventListener('drop',e=>{e.preventDefault();let payload;try{payload=JSON.parse(e.dataTransfer.getData('application/x-marking-element'));}catch{return;}if(!payload?.kind)return;const rect=$('designerCanvas').getBoundingClientRect();const x=(e.clientX-rect.left)/state.designerScale;const y=(e.clientY-rect.top)/state.designerScale;addDesignerElement(payload.kind,payload.role||'variable',x,y);});
  $('addImageElementBtn')?.addEventListener('click',()=>{state.pendingImageReplaceIndex=null;$('designerImageInput').value='';$('designerImageInput').click();});
  $('replaceImageBtn')?.addEventListener('click',()=>{const el=selectedDesignerElement();if(!el||el.kind!=='image')return;state.pendingImageReplaceIndex=state.designerSelected;$('designerImageInput').value='';$('designerImageInput').click();});
  $('designerImageInput')?.addEventListener('change',()=>{const file=$('designerImageInput').files?.[0];addOrReplaceDesignerImage(file,state.pendingImageReplaceIndex);state.pendingImageReplaceIndex=null;});
  $('newTemplateBtn').addEventListener('click',()=>loadDesignerFromTemplate(blankDesignerTemplate()));
  $('duplicateTemplateBtn').addEventListener('click',()=>{const t=deepClone(state.designerTemplate||blankDesignerTemplate());t.id=`${safeDesignerId(t.id)}_copy_${Date.now().toString().slice(-5)}`;t.name=`${t.name} — copia`;loadDesignerFromTemplate(t);});
  $('saveVisualTemplateBtn').addEventListener('click',saveVisualTemplate);
  $('designerQualityBtn').addEventListener('click',()=>{syncDesignerHeaderToDraft();runCodeQuality(state.designerTemplate,designerData(),$('designerScanner').value,'designerQualityResult',readMarkingControls('designer'));});
  ['designerName','designerId','designerCategory','designerWidth','designerHeight','designerQuality'].forEach(id=>$(id).addEventListener('input',()=>{syncDesignerHeaderToDraft();renderDesignerCanvas();scheduleDesignerPreview();}));
  $('designerPrimaryField').addEventListener('change',()=>{syncDesignerHeaderToDraft();updateDesignerJson();});
  $('designerAddFieldBtn').addEventListener('click',()=>{const f=safeDesignerId($('designerNewField').value).replace(/-/g,'_');if(!f)return;if(!state.designerTemplate.expected_fields.includes(f))state.designerTemplate.expected_fields.push(f);state.designerTemplate.metadata.example_data=state.designerTemplate.metadata.example_data||{};state.designerTemplate.metadata.example_data[f]='';$('designerNewField').value='';renderDesignerFields();renderDesignerProperties();updateDesignerJson();scheduleDesignerPreview();});
  $('designerNewField').addEventListener('keydown',e=>{if(e.key==='Enter'){e.preventDefault();$('designerAddFieldBtn').click();}});
  ['propLabel','propX','propY','propWidth','propHeight','propFont','propModule','propRotation','propQuiet','propImageThreshold','propImageDpi'].forEach(id=>$(id).addEventListener('input',updateSelectedElementFromProperties));
  document.querySelectorAll('[data-rotate]').forEach(b=>b.addEventListener('click',()=>{
    const el=selectedDesignerElement(); if(!el)return;
    pushHistory('rotate:'+state.designerSelected+':'+Date.now());
    el.rotation_deg=Number(b.dataset.rotate)||0;
    $('propRotation').value=el.rotation_deg;
    renderDesignerCanvas();renderDesignerProperties();scheduleDesignerPreview();
  }));
  if($('undoBtn')) $('undoBtn').addEventListener('click',undoDesigner);
  if($('redoBtn')) $('redoBtn').addEventListener('click',redoDesigner);
  document.querySelectorAll('#alignGroup button[data-align]').forEach(b=>b.addEventListener('click',()=>alignDesignerSelection(b.dataset.align)));
  // WHY: Los atajos sólo actúan con la pestaña de diseño activa; capturarlos de forma
  // global haría que Ctrl+Z deshiciera cambios del diseñador mientras el usuario
  // escribe en otra pantalla.
  document.addEventListener('keydown',e=>{
    if(!$('tab-config')||!$('tab-config').classList.contains('active'))return;
    const z=(e.ctrlKey||e.metaKey)&&e.key.toLowerCase()==='z';
    const y=(e.ctrlKey||e.metaKey)&&e.key.toLowerCase()==='y';
    if(z&&!e.shiftKey){e.preventDefault();undoDesigner();}
    else if((z&&e.shiftKey)||y){e.preventDefault();redoDesigner();}
  });
  ['propAlign','propEc','propEngravingMode','propImageProcessing','propImageAspect'].forEach(id=>$(id).addEventListener('change',updateSelectedElementFromProperties));
  $('propSource').addEventListener('change',()=>{$('propLiteral').value='';updateSelectedElementFromProperties();}); $('propLiteral').addEventListener('input',updateSelectedElementFromProperties);
  $('deleteElementBtn').addEventListener('click',()=>{if(!state.designerSelection.length)return;pushHistory('delete:'+Date.now());const keep=new Set(state.designerSelection);state.designerTemplate.elements=state.designerTemplate.elements.filter((_,i)=>!keep.has(i));setDesignerSelection([],-1);renderDesignerCanvas();renderDesignerProperties();scheduleDesignerPreview();});
  $('duplicateElementBtn').addEventListener('click',()=>{const el=selectedDesignerElement();if(!el)return;pushHistory('duplicate:'+Date.now());const c=deepClone(el);c.x_mm=Math.min(state.designerTemplate.width_mm,c.x_mm+2);c.y_mm=Math.min(state.designerTemplate.height_mm,c.y_mm+2);state.designerTemplate.elements.push(c);setDesignerSelection([state.designerTemplate.elements.length-1],state.designerTemplate.elements.length-1);renderDesignerCanvas();renderDesignerProperties();scheduleDesignerPreview();});
  document.addEventListener('keydown',e=>{if(!state.designerTemplate||state.designerSelected<0||!$('tab-config').classList.contains('active'))return;const el=selectedDesignerElement();if(!el)return;const step=e.shiftKey?1:.2;if(['ArrowLeft','ArrowRight','ArrowUp','ArrowDown'].includes(e.key)){e.preventDefault();pushHistory('nudge:'+state.designerSelected);if(e.key==='ArrowLeft')el.x_mm=Math.max(0,el.x_mm-step);if(e.key==='ArrowRight')el.x_mm+=step;if(e.key==='ArrowUp')el.y_mm=Math.max(0,el.y_mm-step);if(e.key==='ArrowDown')el.y_mm+=step;renderDesignerCanvas();renderDesignerProperties();scheduleDesignerPreview();}});
}
$('configTemplate').addEventListener('change',loadConfigEditors); $('configJig').addEventListener('change',loadConfigEditors); $('ruleField').addEventListener('change',loadInputRuleForm);
$('saveInputRuleBtn').addEventListener('click',()=>{clear($('inputRuleMsg'));const t=state.designerTemplate,field=$('ruleField').value;if(!t||!field){msg($('inputRuleMsg'),'Agregue/seleccione un campo primero.','warn');return;}const rules=(t.input_rules||[]).filter(r=>r.field!==field);rules.push({field,manual_prefix_enabled:$('rulePrefixEnabled').checked,manual_prefix:$('rulePrefix').value,manual_suffix_enabled:$('ruleSuffixEnabled').checked,manual_suffix:$('ruleSuffix').value,imported_values:$('ruleImportedMode').value,uppercase:$('ruleUppercase').checked,trim:true,description:'Regla configurada desde el estudio visual.'});t.input_rules=rules;updateDesignerJson();scheduleDesignerPreview();msg($('inputRuleMsg'),'Regla aplicada al borrador. Guarde la plantilla para conservarla.','ok');});
$('saveTemplateBtn').addEventListener('click',async()=>{clear($('templateSaveMsg'));try{const obj=JSON.parse($('templateJson').value);await api('/api/templates/save',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({template:obj})});await refreshCatalogAfterTemplateSave(obj.id);loadDesignerFromTemplate(state.catalog.templates.find(x=>x.id===obj.id));msg($('templateSaveMsg'),'Plantilla JSON guardada y catálogo actualizado.','ok');}catch(e){msg($('templateSaveMsg'),e.message,'bad');}});
$('saveJigBtn').addEventListener('click',async()=>{clear($('jigSaveMsg'));try{const obj=JSON.parse($('jigJson').value);await api('/api/jigs/save',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({jig:obj})});msg($('jigSaveMsg'),'Jig guardado. Recargue la aplicación para refrescar el catálogo.','ok');}catch(e){msg($('jigSaveMsg'),e.message,'bad');}});

/** WHY: Consulta eventos recientes para auditoría sin acceder directamente al archivo SQLite. */
async function loadHistory(){ if(!state.catalog)return; try{const j=await (await api('/api/history?limit=200')).json(); $('historyTable').innerHTML=`<table><thead><tr><th>Fecha</th><th>Activo</th><th>Plantilla</th><th>Modo</th><th>Pos.</th><th>Estado</th><th>Verificado</th></tr></thead><tbody>${j.items.map(x=>{const mm=x.job_metadata?.marking_mode;const mode=mm?.polarity==='negative'?`Invertido · ${mm.polarity_scope||'codes'} / ${mm.negative_field||'islands'}`:'Directo';return `<tr><td>${esc(x.created_at)}</td><td><strong>${esc(x.asset_key)}</strong></td><td>${esc(x.template_id)}</td><td>${esc(mode)}</td><td>${x.slot_index??''}</td><td>${esc(x.status)}</td><td>${esc(x.verified_at||'')}</td></tr>`;}).join('')}</tbody></table>`;}catch(e){$('historyTable').textContent=e.message;}}
$('refreshHistoryBtn').addEventListener('click',loadHistory);



/** WHY: Resume referencias de material en lenguaje operativo sin presentarlas como preset validado. */
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
/** WHY: Traduce nivel de riesgo/validación a una clase visual consistente. */
function materialStatusClass(item){
  const bad=['unsafe','unknown','high_caution'];
  if(bad.includes(item.compatibility) || String(item.status||'').includes('blocked') || String(item.status||'').includes('do_not')) return 'bad';
  if(String(item.status||'').includes('validated')) return 'ok';
  return 'warn';
}
/** WHY: Presenta referencias y advertencias de material preservando el contexto de seguridad. */
function renderMaterialItems(items){
  if(!items.length) return '<span class="muted">Sin coincidencias.</span>';
  return items.map(m=>`<div class="material-card ${materialStatusClass(m)}"><div class="panel-head"><strong>${esc(m.name)}</strong><span class="pill">${esc(m.category)} · ${esc(m.operation)}</span></div><div>${esc(prettySuggested(m.suggested))}</div><div class="muted">Estado: ${esc(m.status)} · compatibilidad: ${esc(m.compatibility)}</div>${(m.notes||[]).map(n=>`<div class="hint">• ${esc(n)}</div>`).join('')}</div>`).join('');
}
/** WHY: Consulta biblioteca de materiales bajo la jerarquía ajuste local > fabricante > investigación > prueba. */
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

/** WHY: Busca superficies por modelo para evitar asumir que todos los teléfonos de una marca usan el mismo material. */
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

/** WHY: Busca artefactos locales de LightBurn en modo sólo lectura antes de que el usuario elija importar alguno. */
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


/** WHY: Carga presets/capturas ya auditados y los pone disponibles para asociarlos a trabajos. */
async function loadMachineCaptures(){
  if(!state.catalog)return;
  try{
    state.machineCaptures=await (await api('/api/machine/captures?limit=100')).json();
    const presets=state.machineCaptures.material_presets||[];
    $('batchMaterialPreset').innerHTML='<option value="">— ninguno / definir en LightBurn —</option>'+presets.map(p=>{const mm=p.settings?.marking_mode;const mode=mm?.polarity==='negative'?` · INVERTIDO/${esc(mm.polarity_scope||'codes')}/${esc(mm.negative_field||'islands')}`:' · directo';const scan=p.settings?.scan_validation&&p.settings.scan_validation!=='not_tested'?` · lectura ${esc(p.settings.scan_validation)}`:'';return `<option value="${p.id}">${esc(p.material||'Material')} · ${esc(p.description||p.operation||'preset')} · ${esc(p.source_name)}${mode}${scan}</option>`;}).join('');
    const caps=state.machineCaptures.captures||[];
    $('capturesTable').innerHTML=caps.length?`<table><thead><tr><th>Fecha</th><th>Fuente</th><th>Archivo/puerto</th><th>Máquina</th><th>SHA-256</th></tr></thead><tbody>${caps.map(c=>`<tr><td>${esc(c.created_at)}</td><td>${esc(c.source_type)}</td><td>${esc(c.source_name)}</td><td>${esc(c.machine_profile_id||'')}</td><td><code>${esc((c.sha256||'').slice(0,16))}…</code></td></tr>`).join('')}</tbody></table>`:'<span class="muted">Sin capturas todavía.</span>';
  }catch(e){console.error(e);}
}
$('refreshCapturesBtn').addEventListener('click',loadMachineCaptures);

/** WHY: Lista puertos seriales candidatos sin abrirlos ni controlar la máquina. */
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



/** WHY: Reduce o amplía información según perfil guiado/experto sin cambiar las capacidades del motor. */
function applyExperienceMode(mode){
  const expert=mode==='expert'; document.body.classList.toggle('expert-mode',expert); document.querySelectorAll('.expert-nav').forEach(el=>el.hidden=!expert);
  $('guidedModeBtn')?.classList.toggle('active',!expert); $('expertModeBtn')?.classList.toggle('active',expert);
  localStorage.setItem('markingStudioMode',expert?'expert':'guided');
}
$('guidedModeBtn').addEventListener('click',()=>applyExperienceMode('guided'));
$('expertModeBtn').addEventListener('click',()=>applyExperienceMode('expert'));

/** WHY: La biblioteca validada debe registrar la estrategia física completa; los detalles sólo se muestran en invertido. */
function toggleShopPresetNegativeOptions(){
  const neg=$('shopPresetPolarity').value==='negative'; const host=$('shopPresetNegativeOptions'); if(host)host.hidden=!neg;
  const scope=$('shopPresetPolarityScope'), field=$('shopPresetNegativeField'); const opt=field?[...field.options].find(o=>o.value==='template'):null;
  if(opt)opt.disabled=false;
}
$('shopPresetPolarity').addEventListener('change',toggleShopPresetNegativeOptions);
$('shopPresetPolarityScope').addEventListener('change',toggleShopPresetNegativeOptions);
toggleShopPresetNegativeOptions();

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
    validated_on_exact_machine_surface:$('shopPresetValidated').checked, notes:$('shopPresetNotes').value.trim(),
    marking_mode:{polarity:$('shopPresetPolarity').value,polarity_scope:$('shopPresetPolarityScope').value,negative_field:$('shopPresetNegativeField').value,field_margin_mm:Number($('shopPresetFieldMargin').value)||0,kerf_compensation_mm:Number($('shopPresetKerf').value)||0,validated_on:$('shopPresetValidatedOn').value.trim()},
    scanner_profile_id:$('shopPresetScanner').value||null,scan_validation:$('shopPresetScanValidation').value,scan_attempts:$('shopPresetScanAttempts').value?Number($('shopPresetScanAttempts').value):null,scan_successes:$('shopPresetScanSuccesses').value?Number($('shopPresetScanSuccesses').value):null
  };
  if(!body.name||!body.material||!body.speed_mm_min||!body.power_percent){msg($('shopPresetMsg'),'Complete nombre, material/superficie, velocidad y potencia.','warn');return;}
  try{const r=await api('/api/materials/shop-preset',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify(body)}); const j=await r.json(); msg($('shopPresetMsg'),j.status==='validated'?'Ajuste local guardado como VALIDADO para la misma máquina/superficie.':'Ajuste guardado como BORRADOR; valide físicamente antes de producción.',j.status==='validated'?'ok':'warn'); await loadMachineCaptures();}catch(e){msg($('shopPresetMsg'),e.message,'bad');}
});

/** WHY: Genera referencias del jig y prepara datos esperados para una medición física controlada. */
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

/** WHY: Busca bibliotecas LaserGRBL existentes para rescatar conocimiento del taller sin modificarlo. */
async function discoverLaserGrbl(){
  clear($('lasergrblDiscoveryMsg')); $('lasergrblArtifact').innerHTML='<option value="">— buscando —</option>';
  try{const j=await (await api('/api/machine/lasergrbl/discover')).json(); state.lasergrblArtifacts=j.artifacts||[]; $('lasergrblArtifact').innerHTML=state.lasergrblArtifacts.length?'<option value="">— seleccione —</option>'+state.lasergrblArtifacts.map((a,i)=>`<option value="${i}">${esc(a.name)} · ${Math.ceil((a.size||0)/1024)} KiB</option>`).join(''):'<option value="">— no se encontraron archivos —</option>'; msg($('lasergrblDiscoveryMsg'),`Rutas revisadas: ${(j.roots||[]).join(' · ')||'ninguna'} · artefactos: ${state.lasergrblArtifacts.length}.`,'ok');}catch(e){msg($('lasergrblDiscoveryMsg'),e.message,'bad');}
}
$('discoverLaserGrblBtn').addEventListener('click',discoverLaserGrbl);
$('importDetectedLaserGrblBtn').addEventListener('click',async()=>{
  clear($('lasergrblDiscoveryMsg')); const idx=$('lasergrblArtifact').value; if(idx===''){msg($('lasergrblDiscoveryMsg'),'Seleccione una base detectada.','warn');return;} const item=state.lasergrblArtifacts[Number(idx)];
  try{const r=await api('/api/machine/lasergrbl/import-local',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({path:item.path,machine_profile_id:$('machineImportProfile').value||null})}); const j=await r.json(); msg($('lasergrblDiscoveryMsg'),`Importados ${j.material_preset_count} presets LaserGRBL en solo lectura.`,'ok'); await loadMachineCaptures();}catch(e){msg($('lasergrblDiscoveryMsg'),e.message,'bad');}
});


/** WHY: Muestra positivo vs negativo usando exactamente el mismo motor de producción. */
async function compareIndividualMarking(){
  const t=selectedTemplate('individualTemplate'); const data={}; $('individualFields').querySelectorAll('input').forEach(i=>data[i.dataset.field]=i.value.trim());
  const host=$('individualMarkingCompare'); host.innerHTML='<div class="msg">Generando comparación…</div>';
  try{
    const r=await api('/api/marking/compare',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({template:t,data,capture_mode:'manual',negative_mode:{...readMarkingControls('individual'),polarity:'negative'}})});
    const j=await r.json(); host.innerHTML=`<article><strong>POSITIVO · referencia de lectura</strong><div class="preview">${j.positive_svg}</div></article><article><strong>NEGATIVO · instrucción de ablación</strong><div class="preview">${j.negative_svg}</div><small>${j.estimated_negative_ablation_ratio!=null?`Ablación estimada ~${Math.round(j.estimated_negative_ablation_ratio*100)}% del lienzo`:''}</small></article>`;
  }catch(e){host.innerHTML='';msg(host,e.message,'bad');}
}

bindMarkingControls('individual',scheduleIndividualPreview);
bindMarkingControls('batch',()=>{renderBatchRecordPreview?.();});
bindMarkingControls('designer',()=>{if(state.designerTemplate){state.designerTemplate.marking_mode=readMarkingControls('designer');updateDesignerJson();scheduleDesignerPreview();}});
/** WHY: El cupón usa una sola identidad en cuatro estrategias para que la prueba física compare sólo el modo de marcado. */
async function downloadMarkingCoupon(){
  const t=selectedTemplate('individualTemplate');const data={};$('individualFields').querySelectorAll('input').forEach(i=>data[i.dataset.field]=i.value.trim());
  try{const r=await api('/api/marking/coupon',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({template:t,data,capture_mode:'manual',negative_mode:{...readMarkingControls('individual'),polarity:'negative'}})});const j=await r.json();downloadBlob(new Blob([j.svg],{type:'image/svg+xml'}),`${t.id}-CHARACTERIZATION_COUPON.svg`);msg($('renderWarnings'),'Cupón experimental generado. Grábelo sólo sobre una pieza de descarte y registre cuál panel lee mejor.','warn');}
  catch(e){msg($('renderWarnings'),e.message,'bad');}
}
$('individualCompareMarkingBtn')?.addEventListener('click',compareIndividualMarking);
$('individualCouponBtn')?.addEventListener('click',downloadMarkingCoupon);
$('designerCompareMarkingBtn')?.addEventListener('click',async()=>{
  if(!state.designerTemplate)return; syncDesignerHeaderToDraft();
  const host=$('designerWarnings'), compare=$('designerMarkingCompare');
  if(compare)compare.innerHTML='<div class="msg">Generando comparación…</div>';
  try{
    const r=await api('/api/marking/compare',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({template:state.designerTemplate,data:designerData(),negative_mode:{...readMarkingControls('designer'),polarity:'negative'}})});
    const j=await r.json();
    if(compare)compare.innerHTML=`<article><strong>POSITIVO · referencia de lectura</strong><div class="preview">${j.positive_svg}</div></article><article><strong>NEGATIVO · instrucción de ablación</strong><div class="preview">${j.negative_svg}</div><small>${j.estimated_negative_ablation_ratio!=null?`Ablación estimada ~${Math.round(j.estimated_negative_ablation_ratio*100)}% del lienzo`:''}</small></article>`;
    msg(host,`Comparación generada. Ablación negativa estimada: ${j.estimated_negative_ablation_mm2??'—'} mm².`,'ok');
  }catch(e){if(compare)compare.innerHTML='';msg(host,e.message,'bad');}
});
$('individualSaveMarkingBtn')?.addEventListener('click',()=>saveMarkingModeToTemplate('individualTemplate','individual','renderWarnings'));
$('batchSaveMarkingBtn')?.addEventListener('click',()=>saveMarkingModeToTemplate('batchTemplate','batch','batchMessages'));

loadAll().catch(e=>{ $('licenseBadge').textContent='Error de inicio'; $('licenseBadge').className='badge bad'; console.error(e); });
