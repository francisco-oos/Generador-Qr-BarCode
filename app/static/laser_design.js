'use strict';
const $=id=>document.getElementById(id);
let mode='papercut', imageDataUri=null, lastResult=null;
const groups={papercut:['.papercut-only'],halftone:['.halftone-only','.image-only'],stencil:['.stencil-only','.image-only'],coupon:['.coupon-only'],passport:['.passport-only']};
const titles={papercut:['Papel picado','Generación reproducible'],halftone:['Foto → halftone','Perforaciones por tono'],stencil:['Foto → stencil','Puentes automáticos'],coupon:['OpenAI Experimental Lab','Bridge Ladder físico'],passport:['Material DNA Passport','Caracterización física del proceso']};
function showMode(next){mode=next;document.querySelectorAll('.mode').forEach(b=>b.classList.toggle('active',b.dataset.mode===mode));document.querySelectorAll('.papercut-only,.halftone-only,.stencil-only,.coupon-only,.passport-only,.image-only').forEach(x=>x.hidden=true);(groups[mode]||[]).forEach(sel=>document.querySelectorAll(sel).forEach(x=>x.hidden=false));document.querySelector('.dims').hidden=mode==='coupon'||mode==='passport';document.querySelector('.common-only').hidden=mode==='coupon'||mode==='passport';$('toolTitle').textContent=titles[mode][0];$('toolHint').textContent=titles[mode][1];$('formMessage').textContent='';}
document.querySelectorAll('.mode').forEach(b=>b.addEventListener('click',()=>showMode(b.dataset.mode)));
function num(id){return Number($(id).value)}
function csvNums(id){return $(id).value.split(',').map(x=>Number(x.trim())).filter(Number.isFinite)}
function readFile(f){if(!f)return;if(f.size>4*1024*1024){message('La imagen supera 4 MB.','bad');return;}const reader=new FileReader();reader.onload=()=>{imageDataUri=String(reader.result);$('imageName').textContent=`${f.name} · ${(f.size/1024).toFixed(0)} KB`;message('Imagen cargada. Ajusta parámetros y genera.','ok')};reader.readAsDataURL(f);}
$('imageInput').addEventListener('change',e=>readFile(e.target.files[0]));
['dragenter','dragover'].forEach(ev=>$('dropzone').addEventListener(ev,e=>{e.preventDefault();$('dropzone').classList.add('over')}));
['dragleave','drop'].forEach(ev=>$('dropzone').addEventListener(ev,e=>{$('dropzone').classList.remove('over');if(ev==='drop'){e.preventDefault();readFile(e.dataTransfer.files[0])}}));
function message(text,kind=''){const el=$('formMessage');el.textContent=text;el.className='message '+kind}
async function api(url,body){const r=await fetch(url,{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify(body)});if(!r.ok){let detail='';try{const j=await r.json();detail=typeof j.detail==='string'?j.detail:JSON.stringify(j.detail)}catch{detail=await r.text()}throw new Error(detail||`HTTP ${r.status}`)}return r.json()}
function common(){return {width_mm:num('widthMm'),height_mm:num('heightMm'),margin_mm:num('marginMm'),min_bridge_mm:num('minBridge'),cut_outer:true}}
function payload(){if(mode==='papercut')return {...common(),rows:num('rows'),cols:num('cols'),density:num('density'),motif:$('motif').value,symmetry:$('symmetry').value,seed:num('seed')};if((mode==='halftone'||mode==='stencil')&&!imageDataUri)throw new Error('Carga primero una imagen PNG/JPG.');if(mode==='halftone')return {...common(),image_data_uri:imageDataUri,cell_mm:num('cellMm'),min_diameter_mm:num('minDiameter'),max_diameter_mm:num('maxDiameter'),min_bridge_mm:num('halftoneBridge'),gamma:num('gamma'),invert:$('halftoneInvert').checked,shape:$('halftoneShape').value};if(mode==='stencil')return {width_mm:num('widthMm'),height_mm:num('heightMm'),image_data_uri:imageDataUri,threshold:num('threshold'),invert:$('stencilInvert').checked,frame_mm:num('frameMm'),bridge_width_mm:num('bridgeWidth'),sample_max_px:120,max_auto_bridges:num('maxBridges'),min_bridge_mm:num('minBridge'),cut_outer:true};if(mode==='coupon'){return {widths_mm:csvNums('couponWidths'),length_mm:num('couponLength'),gap_mm:num('couponGap'),label:true};}return {bridge_widths_mm:csvNums('passportBridges'),hole_diameters_mm:csvNums('passportHoles'),gap_widths_mm:csvNums('passportGaps'),row_height_mm:num('passportRowHeight'),feature_length_mm:num('passportFeatureLength')};}
const endpoints={papercut:'/api/laser-design/papercut',halftone:'/api/laser-design/halftone',stencil:'/api/laser-design/stencil',coupon:'/api/laser-design/openai-lab/bridge-coupon',passport:'/api/laser-design/openai-lab/material-passport'};
function renderResult(r){lastResult=r;const usePreview=$('showGuides').checked;$('preview').innerHTML=usePreview?(r.preview_svg||r.svg):r.svg;$('downloadSvg').disabled=false;$('downloadPreview').disabled=!r.preview_svg;const p=r.preflight||{};const status=(p.status||'PASS').toLowerCase();$('statusBadge').textContent=p.status||'PASS';$('statusBadge').className='status '+status;$('componentMetric').textContent=p.component_count===1?'Sí':`${p.component_count??'—'} piezas`;$('webMetric').textContent=p.min_web_mm==null?'—':`${p.min_web_mm.toFixed(2)} mm`;$('areaMetric').textContent=p.removed_area_ratio==null?'—':`${(p.removed_area_ratio*100).toFixed(1)} %`;$('scaleMetric').textContent=p.minimum_safe_scale_percent==null?'—':`${p.minimum_safe_scale_percent.toFixed(0)} %`;const issues=[...(p.issues||[]),...(r.warnings||[]).filter(x=>!(p.issues||[]).includes(x))];$('issues').innerHTML=(issues.length?issues:['Sin incidencias geométricas detectadas en este preflight.']).map(x=>`<li>${escapeHtml(x)}</li>`).join('');$('recipeOut').textContent=JSON.stringify(r.recipe||{},null,2);if($('passportSummary'))$('passportSummary').textContent=r.passport_id?`Pasaporte ${r.passport_id} · ${r.measurement_schema?.rows?.length||0} mediciones`:'';}
function escapeHtml(s){return String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]))}
$('generateBtn').addEventListener('click',async()=>{try{message('Generando y ejecutando preflight…');const r=await api(endpoints[mode],payload());renderResult(r);message('Diseño generado y analizado.','ok')}catch(e){message(e.message,'bad')}});
$('showGuides').addEventListener('change',()=>{if(lastResult)$('preview').innerHTML=$('showGuides').checked?(lastResult.preview_svg||lastResult.svg):lastResult.svg});
function download(text,name){const a=document.createElement('a');a.href=URL.createObjectURL(new Blob([text],{type:'image/svg+xml'}));a.download=name;document.body.appendChild(a);a.click();setTimeout(()=>{URL.revokeObjectURL(a.href);a.remove()},300)}
$('downloadSvg').addEventListener('click',()=>lastResult&&download(lastResult.svg,`laser-design-${lastResult.kind}.svg`));
$('downloadPreview').addEventListener('click',()=>lastResult&&download(lastResult.preview_svg||lastResult.svg,`laser-design-${lastResult.kind}-PREVIEW.svg`));
fetch('/api/laser-design/capabilities').then(r=>r.json()).then(c=>{$('capabilityState').textContent=`Núcleo ${c.geometry_units} · preflight ${c.engines.manufacturability.available?'activo':'no disponible'} · VTracer ${c.engines.vtracer.available?'disponible':'opcional'}`}).catch(()=>{$('capabilityState').textContent='Capacidades no disponibles'});
showMode('papercut');


// Direct GRBL control v0.10 --------------------------------------------------
let compiledMachineJobId=null, machineFrameVerified=false, machinePollTimer=null;
async function getJson(url){const r=await fetch(url);if(!r.ok)throw new Error(await r.text()||`HTTP ${r.status}`);return r.json()}
function machineMsg(text,kind=''){const el=$('machineMessage');el.textContent=text;el.className='message '+kind}
function setMachineState(state,progress=0,text=''){const badge=$('machineState');badge.textContent=state||'IDLE';badge.className='status '+(({COMPLETE:'pass',RUNNING:'warn',HOLD:'warn',ERROR:'fail',ABORTED:'fail'})[state]||'idle');$('machineProgress').value=Math.max(0,Math.min(1,Number(progress)||0));$('machineStatusText').textContent=text||state||'IDLE'}
function selectedPort(){const port=$('machinePort').value;if(!port)throw new Error('Selecciona el puerto serial de la grabadora.');return port}
async function refreshMachineData(){
  try{
    const [ports,captures]=await Promise.all([getJson('/api/machine/ports'),getJson('/api/machine/captures?limit=500')]);
    const portSel=$('machinePort'), previousPort=portSel.value;
    portSel.innerHTML='<option value="">Selecciona puerto</option>'+((ports.ports||[]).map(p=>`<option value="${escapeHtml(p.device)}">${escapeHtml(p.device)} · ${escapeHtml(p.description||p.name||'Serial')}</option>`).join(''));
    if([...portSel.options].some(o=>o.value===previousPort))portSel.value=previousPort;
    const valid=(captures.material_presets||[]).filter(p=>p.settings&&p.settings.validated_on_exact_machine_surface===true);
    const presetSel=$('machinePreset'), previousPreset=presetSel.value;
    presetSel.innerHTML=valid.length?'<option value="">Selecciona preset validado</option>'+valid.map(p=>`<option value="${p.id}">#${p.id} · ${escapeHtml(p.material||'material')} · ${escapeHtml(p.description||p.operation||'')}</option>`).join(''):'<option value="">No hay presets validados; créalo en Marking Studio → Materiales</option>';
    if([...presetSel.options].some(o=>o.value===previousPreset))presetSel.value=previousPreset;
    machineMsg(`Detectados ${(ports.ports||[]).length} puertos y ${valid.length} presets validados.`,'ok');
  }catch(e){machineMsg('No se pudieron actualizar puertos/presets: '+e.message,'bad')}
}
$('refreshMachineData').addEventListener('click',refreshMachineData);
$('loadProcessTemplate').addEventListener('click',async()=>{
  try{
    const templateId=$('processTemplate').value;if(!templateId)throw new Error('Selecciona una plantilla rápida.');
    const item=await api('/api/machine/control/process-template',{template_id:templateId,width_mm:num('widthMm'),height_mm:num('heightMm')});
    lastResult={kind:item.template_id,svg:item.svg,preview_svg:item.svg,recipe:item,preflight:{status:'PASS',component_count:null,min_web_mm:null,removed_area_ratio:null,minimum_safe_scale_percent:null,issues:[]},warnings:['Plantilla geométrica: velocidad/potencia se agregan únicamente al compilar con un preset validado.']};
    renderResult(lastResult);$('machineOperation').value=item.operation;compiledMachineJobId=null;machineFrameVerified=false;$('frameMachineJob').disabled=true;$('startMachineJob').disabled=true;machineMsg('Plantilla cargada. Compílala con un preset local validado.','ok');
  }catch(e){machineMsg(e.message,'bad')}
});
$('compileMachineJob').addEventListener('click',async()=>{
  try{
    if(!lastResult?.svg)throw new Error('Genera o carga primero una geometría SVG.');
    const preset=Number($('machinePreset').value);if(!preset)throw new Error('Selecciona un preset validado.');
    const result=await api('/api/machine/control/compile',{svg:lastResult.svg,machine_profile_id:$('machineProfile').value,material_preset_id:preset,operation:$('machineOperation').value,offset_x_mm:num('machineOffsetX'),offset_y_mm:num('machineOffsetY'),current_position_origin:true});
    compiledMachineJobId=result.job_id;machineFrameVerified=false;$('frameMachineJob').disabled=false;$('startMachineJob').disabled=true;$('compiledJobInfo').textContent=`${result.job_id} · ${result.path_count} paths · ${result.bounds_mm.join(' × ')} mm · ${result.speed_mm_min} mm/min · ${result.power_percent}% · ${result.passes} pasada(s)`;machineMsg('Job compilado. El siguiente paso obligatorio es Frame con láser apagado.','ok');
  }catch(e){machineMsg(e.message,'bad')}
});
$('frameMachineJob').addEventListener('click',async()=>{
  try{
    if(!compiledMachineJobId)throw new Error('Compila primero el job.');
    const result=await api('/api/machine/control/frame',{job_id:compiledMachineJobId,port:selectedPort(),baud:num('machineBaud'),confirm_workspace_clear:$('confirmClearFrame').checked,frame_feed_mm_min:1800});
    machineFrameVerified=!!result.framed;$('startMachineJob').disabled=!machineFrameVerified;machineMsg('Frame terminado con láser apagado. Verifica físicamente la posición antes de START.','ok');
  }catch(e){machineFrameVerified=false;$('startMachineJob').disabled=true;machineMsg(e.message,'bad')}
});
async function pollMachine(){
  try{
    const st=await getJson('/api/machine/control/status');setMachineState(st.state,st.progress,`${st.state} · línea ${st.line_index}/${st.line_total}${st.error?' · '+st.error:''}`);
    if(['RUNNING','HOLD','STARTING'].includes(st.state)){machinePollTimer=setTimeout(pollMachine,700)}else{machinePollTimer=null}
  }catch(e){machineMsg('No se pudo leer estado: '+e.message,'bad')}
}
$('startMachineJob').addEventListener('click',async()=>{
  try{
    if(!machineFrameVerified)throw new Error('Frame obligatorio antes de START.');
    const result=await api('/api/machine/control/start',{job_id:compiledMachineJobId,port:selectedPort(),baud:num('machineBaud'),confirm_workspace_clear:$('confirmClearFrame').checked,confirm_material_matches_preset:$('confirmMaterial').checked,confirm_protective_measures:$('confirmProtection').checked});
    setMachineState(result.state,result.progress,'Arranque solicitado.');machineMsg('Trabajo enviado al controlador experimental. Mantén supervisión física continua.','ok');if(machinePollTimer)clearTimeout(machinePollTimer);pollMachine();
  }catch(e){machineMsg(e.message,'bad')}
});
$('pauseMachineJob').addEventListener('click',async()=>{try{const r=await api('/api/machine/control/pause',{});setMachineState(r.state,r.progress);machineMsg('Feed hold enviado.','ok')}catch(e){machineMsg(e.message,'bad')}});
$('resumeMachineJob').addEventListener('click',async()=>{try{const r=await api('/api/machine/control/resume',{});setMachineState(r.state,r.progress);machineMsg('Reanudación enviada.','ok');pollMachine()}catch(e){machineMsg(e.message,'bad')}});
$('abortMachineJob').addEventListener('click',async()=>{try{const r=await api('/api/machine/control/abort',{});setMachineState(r.state,r.progress);machineMsg('ABORT enviado: hold + soft reset GRBL. Revisa la máquina antes de cualquier nuevo trabajo.','bad')}catch(e){machineMsg(e.message,'bad')}});
document.querySelectorAll('[data-jog-x],[data-jog-y]').forEach(btn=>btn.addEventListener('click',async()=>{
  try{
    const x=Number(btn.dataset.jogX||0),y=Number(btn.dataset.jogY||0);
    const result=await api('/api/machine/control/jog',{port:selectedPort(),baud:num('machineBaud'),x_mm:x,y_mm:y,feed_mm_min:num('jogFeed'),confirm_workspace_clear:$('confirmClearFrame').checked});
    machineMsg(`Jog enviado: ${result.command}`,'ok');
  }catch(e){machineMsg(e.message,'bad')}
}));
getJson('/api/machine/control/capabilities').then(c=>{if(c.direct_control)$('capabilityState').textContent+=' · GRBL directo EXPERIMENTAL'}).catch(()=>{});
refreshMachineData();
pollMachine();
