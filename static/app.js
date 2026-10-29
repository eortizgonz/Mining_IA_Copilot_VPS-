
async function getJson(url,options={}){const r=await fetch(url,options);const data=await r.json();if(!r.ok)throw new Error(data.error||'No fue posible consultar los datos');return data;}
function setBar(id,val){document.getElementById(id).style.width=val+'%';}
let predictiveData=null,predictiveFilter='all',documentsLoaded=false;
const esc=value=>String(value).replace(/[&<>'"]/g,char=>({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[char]));
async function openModule(module,button){
 document.querySelectorAll('.module-btn').forEach(item=>item.classList.toggle('active',item===button));
 const predictive=document.getElementById('predictive_view');
 const dashboard=document.querySelectorAll('.mining-dashboard'),rag=document.getElementById('rag_view');
 if(module==='predictiva'){
  predictive.hidden=false;rag.hidden=true;dashboard.forEach(item=>item.hidden=true);
  await loadPredictive();return;
 }
 predictive.hidden=true;
 if(module==='documentos'){rag.hidden=false;dashboard.forEach(item=>item.hidden=true);await loadDocuments();return;}
 rag.hidden=true;dashboard.forEach(item=>item.hidden=false);
 if(module==='oee'){await loadProfile('Operacional');return;}
 if(module==='turno'){await loadProfile('Operacional');return;}
 if(module==='paradas'){
  await runSim('MII');
  document.getElementById('profile_card').innerHTML='<h3>⏱️ Paradas y pérdidas</h3><p>Seguimiento de eventos en excavadoras, camiones, trituración y bandas transportadoras.</p><p><strong>Objetivo:</strong> reducir indisponibilidad y toneladas de carbón ROM en riesgo.</p>';
  document.getElementById('question_list').innerHTML='';
  return;
 }
 document.getElementById('profile_card').innerHTML='<h3>📚 Documentos RAG</h3><p>Base de conocimiento para procedimientos operativos, manuales de equipos, estándares HSE, planes mineros y especificaciones de calidad.</p><p><strong>Próxima integración:</strong> carga, indexación y consulta contextual de documentos autorizados.</p>';
 document.getElementById('question_list').innerHTML='';
 document.getElementById('answer_box').innerHTML='<h3>Conocimiento minero</h3><p>Este módulo quedará preparado para conectar manuales, procedimientos y normativa mediante búsqueda RAG.</p>';
}
async function loadPredictive(){
 const button=document.getElementById('predictive_refresh');button.disabled=true;button.textContent='Actualizando…';
 try{predictiveData=await getJson('/api/predictive');renderPredictive();}
 finally{button.disabled=false;button.textContent='Actualizar vista';}
}
function renderPredictive(){
 const d=predictiveData,s=d.summary;
 document.getElementById('predictive_updated').textContent='Última lectura: '+new Date(d.generated_at).toLocaleString('es-CO')+' · '+(d.source==='postgresql'?'PostgreSQL':'simulación');
 document.getElementById('predictive_weights').innerHTML=d.weights.map(w=>`<span>${esc(w.label)} ${w.weight}%</span>`).join('');
 document.getElementById('healthy_count').textContent=s.healthy;document.getElementById('warning_count').textContent=s.warning;
 document.getElementById('critical_count').textContent=s.critical;document.getElementById('average_risk').textContent=s.average_risk+'%';
 const r=d.recommended;
 document.getElementById('predictive_decision').innerHTML=`<span class="eyebrow">DECISIÓN RECOMENDADA</span><div><strong>${esc(r.id)} · ${esc(r.name)} concentra el mayor riesgo (${r.risk}%).</strong><p>Factores principales: ${r.factors.map(f=>esc(f.label)+' ('+f.contribution+' puntos)').join(' y ')}. ${esc(r.action)}</p></div><b class="status critical">Crítica</b>`;
 document.getElementById('predictive_disclaimer').textContent=d.disclaimer;renderPredictiveRows();
}
function renderPredictiveRows(){
 const rows=predictiveData.machines.filter(m=>predictiveFilter==='all'||m.status===predictiveFilter);
 document.getElementById('predictive_rows').innerHTML=rows.map(m=>`<tr><td><strong>${esc(m.id)}</strong><small>${esc(m.name)} · ${esc(m.area)}</small></td><td>${m.usage_hours.toLocaleString('es-CO')} h</td><td>${m.vibration} mm/s</td><td>${m.temperature} °C</td><td>${m.current} A</td><td>${m.rpm.toLocaleString('es-CO')}</td><td>${m.pressure} bar</td><td><div class="risk-cell"><i><b style="width:${m.risk}%"></b></i><strong>${m.risk}%</strong></div></td><td><span class="status ${m.status}">${m.status}</span></td><td><button class="factor-button" data-machine="${esc(m.id)}">Ver factores</button></td></tr>`).join('');
 document.querySelectorAll('.factor-button').forEach(button=>button.addEventListener('click',()=>showPredictiveFactors(button.dataset.machine)));
}
function showPredictiveFactors(id){
 const m=predictiveData.machines.find(item=>item.id===id),dialog=document.getElementById('predictive_dialog');
 document.getElementById('predictive_dialog_title').textContent=`${m.id} · ${m.name}`;
 document.getElementById('predictive_dialog_body').innerHTML=`<p>${esc(m.area)} · riesgo calculado <strong>${m.risk}%</strong></p>${m.factors.map(f=>`<div class="factor-line"><span>${esc(f.label)}</span><i><b style="width:${f.score}%"></b></i><strong>${f.contribution} pts</strong></div>`).join('')}<p class="dialog-note">Validar las señales, límites y acciones con ingeniería, HSE y el manual del fabricante antes de intervenir.</p>`;
 dialog.showModal();
}
async function updateKpis(){
 const k=await getJson('/api/kpis');
 document.getElementById('kpi_cumplimiento').innerText=k.cumplimiento+'%';
 document.getElementById('kpi_disponibilidad').innerText=k.disponibilidad+'%';
 document.getElementById('kpi_perdida').innerText='USD '+k.perdida+'M';
 document.getElementById('kpi_stock').innerText=k.stock;
 document.getElementById('kpi_calidad').innerText=k.calidad+'%';
 document.getElementById('kpi_score').innerText=k.score;
 document.getElementById('kpi_ordenes').innerText=k.ordenes;
 document.getElementById('kpi_alertas').innerText=k.alertas;
 document.getElementById('kpi_cenizas').innerText=k.cenizas+'%';
 document.getElementById('kpi_stripping').innerText=k.stripping;
 document.getElementById('txt_excavadora').innerText=k.excavadora+'%'; setBar('bar_excavadora',k.excavadora);
 document.getElementById('txt_trituracion').innerText=k.trituracion+'%'; setBar('bar_trituracion',k.trituracion);
 document.getElementById('txt_flota').innerText=k.flota+'%'; setBar('bar_flota',k.flota);
 document.getElementById('txt_calidad').innerText=k.calidad+'%'; setBar('bar_calidad',k.calidad);
 document.getElementById('rom').innerText=k.rom.toLocaleString('es-CO');
 document.getElementById('stock').innerText=k.stock;
 document.getElementById('lotes_riesgo').innerText=k.lotes_riesgo;
 document.getElementById('donut_value').innerText=k.score;
 document.getElementById('costo_ton').innerText='USD '+k.costo_ton;
 document.getElementById('downtime').innerText=k.downtime+' h';
 document.getElementById('activos').innerText=k.activos_criticos;
 document.getElementById('humedad').innerText=k.humedad+'%';
}
async function loadProfile(perfil){
 const data=await getJson('/api/profile/'+perfil); const c=data.info.color;
 const profile=document.getElementById('profile_card'); profile.style.borderLeftColor=c;
 profile.innerHTML=`<h3>${data.info.icono} ${data.info.titulo}</h3><p>${data.info.resumen}</p><p><strong>Acción principal:</strong> ${data.info.accion}</p><div class="profile-badges"><span class="badge">${perfil}</span><span class="badge">ROM</span><span class="badge">Dispatch</span><span class="badge">Calidad</span><span class="badge">HSE</span></div>`;
 const list=document.getElementById('question_list'); list.innerHTML='';
 data.preguntas.forEach(q=>{const div=document.createElement('div');div.className='question';div.innerHTML=`<strong>${q.pregunta}</strong><small>${q.kpi} · ${q.fuente}</small>`;div.onclick=()=>showAnswer(q,c);list.appendChild(div);});
 if(data.preguntas.length){showAnswer(data.preguntas[0],c);}
}
function showAnswer(q,color){
 const box=document.getElementById('answer_box'); box.style.borderLeft='8px solid '+color;
 box.innerHTML=`<h3>${q.perfil}</h3><p><strong>${q.pregunta}</strong></p><div class="metric">${q.kpi}</div><p>${q.respuesta}</p><p><strong>Acción sugerida:</strong> ${q.accion}</p><p><strong>Fuente SAP:</strong> ${q.fuente}</p>`;
}
async function runSim(sim){
 const data=await getJson('/api/simulator/'+sim);
 document.getElementById('sim_result').innerText=data.respuesta+'\n\nEndpoint: '+data.endpoint+'\n\n'+JSON.stringify(data.datos,null,2);
}
async function loadActions(){
 const items=await getJson('/api/actions'); const box=document.getElementById('actions'); box.innerHTML='';
 items.forEach(a=>{let color=a.color==='red'?'#ef4444':a.color==='orange'?'#f59e0b':a.color==='blue'?'#3b82f6':a.color==='green'?'#22c55e':a.color==='yellow'?'#eab308':a.color==='purple'?'#8b5cf6':a.color==='pink'?'#ec4899':'#06b6d4';const div=document.createElement('div');div.className='action';div.style.borderLeftColor=color;div.innerHTML=`<strong>${a.prioridad} · ${a.area}</strong><span>${a.accion} — ${a.responsable}</span>`;box.appendChild(div);});
}
async function loadDocuments(){
 const box=document.getElementById('document_list');
 try{const rows=await getJson('/api/documents');documentsLoaded=true;box.innerHTML=rows.length?`<table class="rag-table"><thead><tr><th>Documento</th><th>Fragmentos</th><th>Indexación</th><th></th></tr></thead><tbody>${rows.map(row=>`<tr><td>${esc(row.document_name)}</td><td>${row.chunks}</td><td>${new Date(row.indexed_at).toLocaleString('es-CO')}</td><td><button class="rag-delete" data-name="${esc(row.document_name)}">Eliminar</button></td></tr>`).join('')}</tbody></table>`:'<p>No hay documentos indexados. Ejecuta la carga inicial de manuales.</p>';box.querySelectorAll('.rag-delete').forEach(button=>button.addEventListener('click',()=>removeDocument(button.dataset.name)));}
 catch(error){box.textContent=error.message;}
}
async function removeDocument(name){if(!confirm('¿Eliminar '+name+' de la base vectorial?'))return;await getJson('/api/documents/'+encodeURIComponent(name),{method:'DELETE'});documentsLoaded=false;await loadDocuments();}
function addRagMessage(text,type,sources=[]){const box=document.getElementById('rag_messages'),message=document.createElement('div');message.className='rag-message '+type;message.textContent=text;if(sources.length){const source=document.createElement('small');source.textContent='Fuentes: '+sources.join(' · ');message.appendChild(source);}box.appendChild(message);box.scrollTop=box.scrollHeight;}
document.getElementById('document_upload_form').addEventListener('submit',async event=>{event.preventDefault();const files=document.getElementById('document_files').files,data=new FormData(),button=document.getElementById('document_upload_button'),status=document.getElementById('document_status');for(const file of files)data.append('files',file);button.disabled=true;status.textContent='Extrayendo, vectorizando e indexando…';try{const result=await getJson('/api/documents',{method:'POST',body:data});status.textContent=result.total+' documento(s) indexado(s).';document.getElementById('document_files').value='';await loadDocuments();}catch(error){status.textContent=error.message;}finally{button.disabled=false;}});
document.getElementById('document_refresh').addEventListener('click',loadDocuments);
document.getElementById('rag_chat_form').addEventListener('submit',async event=>{event.preventDefault();const input=document.getElementById('rag_question'),button=document.getElementById('rag_send'),question=input.value.trim();if(question.length<5)return;addRagMessage(question,'user');input.value='';button.disabled=true;try{const result=await getJson('/api/copilot/chat',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({question})});addRagMessage(result.answer,'assistant',result.sources||[]);}catch(error){addRagMessage(error.message,'error');}finally{button.disabled=false;}});
document.getElementById('predictive_refresh').addEventListener('click',()=>loadPredictive().catch(console.error));
document.getElementById('predictive_filters').querySelectorAll('[data-filter]').forEach(button=>button.addEventListener('click',()=>{predictiveFilter=button.dataset.filter;document.querySelectorAll('#predictive_filters button').forEach(item=>item.classList.toggle('active',item===button));renderPredictiveRows();}));
document.getElementById('predictive_dialog_close').addEventListener('click',()=>document.getElementById('predictive_dialog').close());
document.getElementById('logout_button').addEventListener('click',async()=>{const button=document.getElementById('logout_button');button.disabled=true;try{await getJson('/api/auth/logout',{method:'POST'});location.href='/login';}catch(error){button.disabled=false;console.error(error);}});
updateKpis().catch(console.error);loadProfile('Operacional').catch(console.error);loadActions().catch(console.error);runSim('ERP').catch(console.error);setInterval(()=>updateKpis().catch(console.error),10000);
