/**
 * CalibPro — Wizard de Diagnóstico
 * Maneja el flujo de 6 pasos para crear un diagnóstico de calibración.
 */
'use strict';

let currentDiagId  = null;
let capturedPhotos = {};   // { slotId: { label, tipo, dataUrl, saved_id } }
let wizardStep     = 1;
let wizardPatrones = [];

const REQUIRED_SLOTS = [
  { id: 'ph-placa',    label: 'Placa de identificación', tipo: 'requerida' },
  { id: 'ph-display',  label: 'Pantalla / Display',       tipo: 'requerida' },
  { id: 'ph-conexion', label: 'Conexiones y montaje',     tipo: 'requerida' },
  { id: 'ph-general',  label: 'Vista general del equipo', tipo: 'requerida' },
];

// ── Init ────────────────────────────────────────────────────────────────────
async function initWizard() {
  // Don't reset if a diag is in progress
  if (!currentDiagId) {
    wizardStep = 1;
    updateWizardUI(1);
    buildDefaultReadings();
    initPhotoSlots();
    // Default next calibration date (+1 year)
    const nxt = new Date();
    nxt.setFullYear(nxt.getFullYear() + 1);
    const proxEl = document.getElementById('f-prox-calib');
    if (proxEl) proxEl.value = nxt.toISOString().substring(0, 10);
  }

  // Load dropdowns every time (data may have changed)
  const [equipos, patrones, usuarios] = await Promise.all([
    Equipos.list(), Patrones.list(), Auth.me(),
  ]);

  const selEq = document.getElementById('f-equipo-id');
  if (selEq && equipos) {
    const prevVal = selEq.value;
    selEq.innerHTML = '<option value="">— Seleccionar equipo —</option>' +
      equipos.map(e => `<option value="${e.id}">${e.codigo} — ${e.descripcion}</option>`).join('');
    if (prevVal) selEq.value = prevVal;
    selEq.onchange = onEquipoChange;
  }

  const selPat = document.getElementById('f-patron-id');
  if (selPat && patrones) {
    wizardPatrones = patrones;
    filtrarPatrones(document.querySelector('.meas-card.selected')?.dataset.mag || '', selPat.value);
  }

  const selU = document.getElementById('f-tecnico-id');
  if (selU && usuarios) {
    selU.innerHTML = `<option value="${usuarios.id}">${escapeHTML(usuarios.nombre)} (sesión activa)</option>`;
    selU.value = usuarios.id;
    selU.disabled = true;
  }

  // Magnitud cards click handlers
  document.querySelectorAll('.meas-card').forEach(c => {
    c.onclick = () => {
      document.querySelectorAll('.meas-card').forEach(x => x.classList.remove('selected'));
      c.classList.add('selected');
      const units = {
        Presión: 'bar', Peso: 'g', Temperatura: '°C',
        Eléctrica: 'V', pH: 'pH', Caudal: 'L/min',
        Dimensional: 'mm', Vibración: 'dB', Radiación: 'lux',
      };
      const unitEl = document.getElementById('f-unidad');
      if (unitEl) unitEl.value = units[c.dataset.mag] || '';
      filtrarPatrones(c.dataset.mag);
    };
  });
}

// ── Equipo change: show info box & auto-select magnitud ─────────────────────
async function onEquipoChange() {
  const id  = document.getElementById('f-equipo-id')?.value;
  const box = document.getElementById('equipo-info');
  if (!box) return;
  if (!id) { box.style.display = 'none'; return; }

  const d = await Equipos.get(id);
  if (!d) return;

  box.style.display = 'grid';
  box.innerHTML = `
    <div><span style="color:var(--text3)">Serie:</span>      <span style="color:var(--accent)">${d.serie||'—'}</span></div>
    <div><span style="color:var(--text3)">Fabricante:</span> <span style="color:var(--accent)">${d.fabricante||'—'}</span></div>
    <div><span style="color:var(--text3)">Rango:</span>      <span style="color:var(--accent)">${d.rango||'—'}</span></div>
    <div><span style="color:var(--text3)">Tolerancia:</span> <span style="color:var(--accent)">${d.tolerancia||'—'}</span></div>
    <div><span style="color:var(--text3)">Magnitud:</span>   <span style="color:var(--accent)">${d.magnitud||'—'}</span></div>
    <div><span style="color:var(--text3)">Cliente:</span>    <span style="color:var(--accent)">${d.cliente_nombre||'—'}</span></div>`;

  if (d.magnitud) {
    document.querySelectorAll('.meas-card').forEach(c => {
      c.classList.toggle('selected', c.dataset.mag === d.magnitud);
    });
    const units = {Presión:'bar',Peso:'g',Temperatura:'°C',Eléctrica:'V',pH:'pH',Caudal:'L/min',Dimensional:'mm',Vibración:'dB',Radiación:'lux'};
    const unidad = document.getElementById('f-unidad');
    if (unidad) unidad.value = units[d.magnitud] || '';
    filtrarPatrones(d.magnitud);
  }
}

// Mostrar solo patrones activos de la misma magnitud que el equipo elegido.
function filtrarPatrones(magnitud, preferred = '') {
  const combo = document.getElementById('f-patron-id');
  if (!combo) return;
  const previous = preferred || combo.value;
  const compatibles = wizardPatrones.filter(p => !magnitud || p.magnitud === magnitud);
  combo.innerHTML = '<option value="">— Seleccionar patrón compatible —</option>' +
    compatibles.map(p => `<option value="${Number(p.id)}">${escapeHTML(p.codigo)} — ${escapeHTML(p.descripcion)}</option>`).join('');
  if (compatibles.some(p => String(p.id) === String(previous))) combo.value = previous;
  if (!compatibles.length) combo.innerHTML = '<option value="">— No hay patrones compatibles —</option>';
}

// ── Wizard step navigation ──────────────────────────────────────────────────
function wizNext(step) {
  if (step > wizardStep && !validateStep(wizardStep)) return;
  wizardStep = step;
  updateWizardUI(step);
  document.querySelectorAll('.step-pane').forEach(p => p.classList.remove('active'));
  document.getElementById(`sp-${step}`)?.classList.add('active');
}

function updateWizardUI(step) {
  const badge = document.getElementById('wiz-badge');
  if (badge) badge.textContent = `Paso ${step} de 6`;
  for (let i = 1; i <= 6; i++) {
    const ws = document.getElementById(`ws-${i}`);
    if (!ws) continue;
    ws.classList.remove('active', 'done');
    if (i < step) ws.classList.add('done');
    if (i === step) ws.classList.add('active');
  }
}

function validateStep(step) {
  if (step === 1) {
    if (!v('f-equipo-id')) {
      toast('Selecciona un equipo para continuar', 'warn');
      return false;
    }
    if (!v('f-patron-id')) {
      toast('Selecciona un patrón de referencia compatible', 'warn');
      return false;
    }
  }
  return true;
}

// ── Create diagnostico (called from step 3 → 4 button) ─────────────────────
async function createDiagnostico() {
  if (currentDiagId) { wizNext(4); return; }  // already created

  const mag = document.querySelector('.meas-card.selected')?.dataset.mag || 'Presión';
  const body = {
    equipo_id:      v('f-equipo-id'),
    patron_id:      v('f-patron-id') || null,
    magnitud:       mag,
    unidad:         v('f-unidad'),
    procedimiento:  v('f-procedimiento'),
    observaciones:  v('f-obs-prev'),
    temp_inicio:    parseFloat(v('f-temp-ini'))   || null,
    temp_fin:       parseFloat(v('f-temp-fin'))   || null,
    humedad_inicio: parseFloat(v('f-hum-ini'))    || null,
    humedad_fin:    parseFloat(v('f-hum-fin'))    || null,
    presion_atm:    parseFloat(v('f-presion-atm'))|| null,
    prox_calibracion: v('f-prox-calib') || null,
  };

  if (!body.equipo_id || !body.patron_id) { toast('Selecciona el equipo y un patrón compatible', 'warn'); return; }

  toast('Creando diagnóstico…', 'loading');
  const res = await Diagnosticos.create(body);
  toastClear();

  if (res?.ok) {
    currentDiagId = res.id;
    toast(`Diagnóstico ${res.n_certificado} creado`);
    wizNext(4);
  } else {
    toast(res?.error || 'Error al crear diagnóstico', 'error');
  }
}

// ── Readings ────────────────────────────────────────────────────────────────
function buildDefaultReadings() {
  const tbody = document.getElementById('lecturas-body');
  if (!tbody) return;
  tbody.innerHTML = '';
  [0, 25, 50, 75, 100].forEach(pct => addLecturaRow(pct));
}

function addLecturaRow(pct = '') {
  const tbody = document.getElementById('lecturas-body');
  if (!tbody) return;
  const idx = tbody.rows.length + 1;
  const tr  = document.createElement('tr');
  tr.innerHTML = `
    <td style="color:var(--text3);font-family:'DM Mono',monospace;font-size:11px">${idx}</td>
    <td><input type="number" step="0.001" class="nom" placeholder="0.000" oninput="calcDesviation(this)"></td>
    <td style="font-family:'DM Mono',monospace;font-size:11px;color:var(--text2)">${pct !== '' ? pct + '%' : ''}</td>
    <td><input type="number" step="0.001" class="ebp" placeholder="0.000" oninput="calcDesviation(this)"></td>
    <td><input type="number" step="0.001" class="pat" placeholder="0.000" oninput="calcDesviation(this)"></td>
    <td class="dev" style="font-family:'DM Mono',monospace;font-size:12px">—</td>
    <td class="err" style="font-family:'DM Mono',monospace;font-size:12px">—</td>
    <td><input type="number" step="0.001" class="inc" placeholder="0.052"></td>
    <td><button class="btn-danger-sm" onclick="this.closest('tr').remove();renumberReadings()">✕</button></td>`;
  tbody.appendChild(tr);
}

function renumberReadings() {
  const rows = document.querySelectorAll('#lecturas-body tr');
  rows.forEach((tr, i) => {
    const numCell = tr.querySelector('td:first-child');
    if (numCell) numCell.textContent = i + 1;
  });
}

function calcDesviation(input) {
  const tr  = input.closest('tr');
  if (!tr) return;
  const ebp = parseFloat(tr.querySelector('.ebp')?.value);
  const pat = parseFloat(tr.querySelector('.pat')?.value);
  if (!isNaN(ebp) && !isNaN(pat)) {
    const dev = ebp - pat;
    const devCell = tr.querySelector('.dev');
    devCell.textContent = dev.toFixed(4);
    devCell.className   = 'dev ' + (Math.abs(dev) > 0.04 ? 'dev-warn' : 'dev-ok');
  }
}

async function saveLecturas() {
  if (!currentDiagId) { toast('Crea el diagnóstico primero (paso 3)', 'warn'); return false; }
  const rows = Array.from(document.querySelectorAll('#lecturas-body tr')).map((tr, i) => ({
    ciclo:           1,
    punto:           i + 1,
    valor_nominal:   parseFloat(tr.querySelector('.nom')?.value)  || 0,
    porcentaje_rango: 0,
    lectura_ebp:     parseFloat(tr.querySelector('.ebp')?.value)  || 0,
    lectura_patron:  parseFloat(tr.querySelector('.pat')?.value)  || 0,
    desviacion:      parseFloat(tr.querySelector('.dev')?.textContent) || 0,
    error_pct:       0,
    incertidumbre:   parseFloat(tr.querySelector('.inc')?.value)  || 0,
  }));
  const res = await Diagnosticos.saveLecturas(currentDiagId, rows);
  if (res?.ok) {
    toast(`${res.count} lecturas guardadas`);
    return true;
  } else {
    toast(res?.error || 'Error al guardar lecturas', 'error');
    return false;
  }
}

async function saveLecturasAndNext() {
  const ok = await saveLecturas();
  if (ok) wizNext(5);
}

// ── Photos ──────────────────────────────────────────────────────────────────
function initPhotoSlots() {
  capturedPhotos = {};
  const req = document.getElementById('photos-required');
  const ext = document.getElementById('photos-extra');
  if (!req || !ext) return;
  req.innerHTML = '';
  ext.innerHTML = '';
  REQUIRED_SLOTS.forEach(slot => req.appendChild(buildPhotoSlot(slot)));
  updatePhotoCounter();
}

function buildPhotoSlot(slot) {
  const wrap  = document.createElement('div');
  wrap.id     = `slot-${slot.id}`;

  const label         = document.createElement('label');
  label.htmlFor       = slot.id;
  label.style.cursor  = 'pointer';
  label.style.display = 'block';

  const div       = document.createElement('div');
  div.className   = 'photo-slot';
  div.innerHTML   = `<div class="ps-icon">📷</div><div style="font-size:10px;text-align:center;margin-top:4px">${slot.label}</div>`;
  label.appendChild(div);

  const input    = document.createElement('input');
  input.type     = 'file';
  input.id       = slot.id;
  input.accept   = 'image/*';
  input.style.display = 'none';
  input.addEventListener('change', () => handlePhoto(input, slot));
  label.appendChild(input);
  wrap.appendChild(label);
  return wrap;
}

function handlePhoto(input, slot) {
  if (!input.files?.[0]) return;
  const reader = new FileReader();
  reader.onload = e => {
    const dataUrl = e.target.result;
    capturedPhotos[slot.id] = { label: slot.label, tipo: slot.tipo, dataUrl };

    const slotEl = document.querySelector(`#slot-${slot.id} div`);
    if (slotEl) {
      slotEl.className = 'photo-taken';
      slotEl.innerHTML = `
        <img src="${dataUrl}" alt="${slot.label}" style="width:100%;height:100%;object-fit:cover;">
        <button class="photo-del" onclick="removePhoto('${slot.id}');event.preventDefault()">✕</button>
        <div class="photo-label">${slot.label}</div>`;
    }
    updatePhotoCounter();
    toast(`📷 "${slot.label}" capturada`);
    uploadPhotoToServer(slot.id, slot.label, slot.tipo, dataUrl);
  };
  reader.readAsDataURL(input.files[0]);
}

function handleExtraPhotos(input) {
  const ext = document.getElementById('photos-extra');
  if (!ext) return;
  Array.from(input.files).forEach((file, i) => {
    const id   = `ph-extra-${Date.now()}-${i}`;
    const slot = { id, label: `Foto adicional ${Object.keys(capturedPhotos).length + 1}`, tipo: 'adicional' };
    const reader = new FileReader();
    reader.onload = e => {
      const dataUrl = e.target.result;
      capturedPhotos[id] = { label: slot.label, tipo: slot.tipo, dataUrl };

      const wrap       = document.createElement('div');
      wrap.id          = `slot-${id}`;
      wrap.className   = 'photo-taken';
      wrap.style.cssText = 'aspect-ratio:1;position:relative;overflow:hidden;border-radius:8px;';
      wrap.innerHTML   = `
        <img src="${dataUrl}" alt="${slot.label}" style="width:100%;height:100%;object-fit:cover;">
        <button class="photo-del" onclick="removePhoto('${id}');this.closest('[id]').remove()">✕</button>
        <div class="photo-label">${slot.label}</div>`;
      ext.appendChild(wrap);

      updatePhotoCounter();
      uploadPhotoToServer(id, slot.label, slot.tipo, dataUrl);
    };
    reader.readAsDataURL(file);
  });
  // reset so same files can be selected again
  input.value = '';
}

async function uploadPhotoToServer(slotId, label, tipo, dataUrl) {
  if (!currentDiagId) return;
  const res = await Diagnosticos.savePhotos(currentDiagId, [{ dataUrl, label, tipo }]);
  if (res?.saved?.[0]) {
    if (capturedPhotos[slotId]) capturedPhotos[slotId].saved_id = res.saved[0].id;
  }
}

function removePhoto(slotId) {
  const saved = capturedPhotos[slotId]?.saved_id;
  if (saved) Diagnosticos.deletePhoto(saved);
  delete capturedPhotos[slotId];
  updatePhotoCounter();
}

function updatePhotoCounter() {
  const count = Object.keys(capturedPhotos).length;
  const bar   = document.getElementById('photo-counter');
  if (!bar) return;
  if (count > 0) {
    bar.style.display = 'block';
    bar.textContent   = `🖼️ ${count} foto(s) capturada(s) — se incluirán en el certificado.`;
  } else {
    bar.style.display = 'none';
  }
}

// ── Step 6: load photo thumbs ───────────────────────────────────────────────
function loadStep6() {
  const grid   = document.getElementById('step6-photos');
  const photos = Object.values(capturedPhotos);
  if (!grid) return;
  grid.innerHTML = photos.length
    ? photos.map(p => `
        <div class="photo-thumb">
          <img src="${p.dataUrl}" alt="${p.label}">
          <div class="photo-thumb-label">${p.label}</div>
        </div>`).join('')
    : '<p style="color:var(--text3);font-size:12px;">Sin fotos capturadas</p>';
}

// ── Finalize diagnostico ─────────────────────────────────────────────────────
async function finalizarDiagnostico() {
  if (!currentDiagId) { toast('Crea el diagnóstico primero', 'warn'); return; }
  const body = {
    resultado:       v('f-resultado'),
    dictamen:        v('f-dictamen'),
    observaciones:   v('f-obs-final'),
    estado_visual:   v('f-obs-visual'),
    prox_calibracion: v('f-prox-calib'),
  };
  toast('Guardando diagnóstico…', 'loading');
  const res = await Diagnosticos.update(currentDiagId, body);
  toastClear();
  if (res?.ok) {
    toast('✅ Diagnóstico guardado exitosamente');
    document.getElementById('btn-revision').disabled = false;
    document.getElementById('btn-ver-pdf').disabled = true;
    document.getElementById('btn-email')?.setAttribute('disabled','');
    toast('Envíe el diagnóstico a revisión antes de descargar o enviar su PDF.');
    const certEl = document.getElementById('diag-cert-num');
    if (certEl) {
      certEl.style.display = 'block';
      const d = await Diagnosticos.get(currentDiagId);
      if (d) certEl.textContent = `N° Certificado: ${d.n_certificado}`;
    }
  } else {
    toast(res?.error || 'Error al guardar', 'error');
  }
}

// ── PDF & Email ──────────────────────────────────────────────────────────────
function verPDF() {
  if (currentDiagId) verPDFById(currentDiagId);
  else toast('No hay diagnóstico activo', 'warn');
}
function verPDFById(id) {
  window.open(Diagnosticos.getPDF(id), '_blank');
}

let _emailDiagId = null;
function openEmailModal() {
  if (currentDiagId) openEmailModalById(currentDiagId);
  else toast('No hay diagnóstico activo', 'warn');
}
async function openEmailModalById(id) {
  _emailDiagId = id;
  const d = await Diagnosticos.get(id);
  if (d) {
    document.getElementById('email-to').value      = d.cliente_email || '';
    document.getElementById('email-subject').value = `Certificado de Calibración ${d.n_certificado} — ${d.equipo_desc || ''}`;
    document.getElementById('email-body').value    =
      `Estimado/a,\n\nAdjuntamos el Certificado de Calibración N° ${d.n_certificado} correspondiente al instrumento ${d.equipo_desc}.\n\nResultado: ${(d.resultado || '').toUpperCase()}\nPróxima calibración: ${(d.prox_calibracion || '').substring(0, 10)}\n\nAtentamente,\nÁrea de Metrología — Tatronics / CalibPro`;
  }
  if (!d || d.estado_aprobacion !== 'aprobado') { toast('Primero debe aprobarse el certificado.', 'warn'); return; }
  if (!['admin','jefe'].includes(document.body.dataset.userRole)) { toast('El envío requiere autorización de jefe o administrador.', 'warn'); return; }
  openModal('email-modal');
}

async function sendEmail() {
  const btn = document.getElementById('btn-send-email');
  if (!_emailDiagId) { toast('Sin diagnóstico seleccionado', 'warn'); return; }
  if (btn) { btn.disabled = true; btn.textContent = '⏳ Enviando…'; }
  const body = {
    to:      v('email-to'),
    cc:      v('email-cc'),
    subject: v('email-subject'),
    body:    document.getElementById('email-body')?.value || '',
  };
  if (!body.to) { toast('Ingresa un destinatario', 'warn'); if (btn) { btn.disabled = false; btn.textContent = '📤 Enviar ahora'; } return; }
  const res = await Diagnosticos.sendEmail(_emailDiagId, body);
  if (btn) { btn.disabled = false; btn.textContent = '📤 Enviar ahora'; }
  if (res?.ok) {
    toast(res.message || 'Correo enviado');
    closeModal('email-modal');
  } else {
    toast(res?.error || 'Error al enviar', 'error');
  }
}

// ── Reset wizard ─────────────────────────────────────────────────────────────
function resetWizard() {
  currentDiagId = null;
  capturedPhotos = {};
  wizardStep = 1;
  updateWizardUI(1);
  document.querySelectorAll('.step-pane').forEach(p => p.classList.remove('active'));
  document.getElementById('sp-1')?.classList.add('active');

  const pdfBtn = document.getElementById('btn-ver-pdf');
  const emlBtn = document.getElementById('btn-email');
  const certEl = document.getElementById('diag-cert-num');
  if (pdfBtn) pdfBtn.disabled = true;
  const reviewBtn = document.getElementById('btn-revision');
  if (reviewBtn) reviewBtn.disabled = true;
  if (emlBtn) emlBtn.disabled = true;
  if (certEl) certEl.style.display = 'none';

  // Clear form fields
  const fields = ['f-equipo-id','f-patron-id','f-procedimiento','f-obs-prev','f-obs-visual','f-obs-final','f-dictamen'];
  fields.forEach(fid => {
    const el = document.getElementById(fid);
    if (el) el.value = el.tagName === 'SELECT' ? el.options[0]?.value || '' : '';
  });
  document.getElementById('equipo-info').style.display = 'none';

  buildDefaultReadings();
  initPhotoSlots();
  toast('Wizard reiniciado — listo para nuevo diagnóstico');
}

// ── Circuito de aprobación electrónica ─────────────────────────────────
async function enviarARevision() {
  if (!currentDiagId) return toast('Guarde primero el diagnóstico.', 'warn');
  const res = await Diagnosticos.submitReview(currentDiagId);
  if (!res?.ok) return toast(res?.error || 'No se pudo solicitar la revisión', 'error');
  toast('Diagnóstico enviado a revisión de administración o jefatura.');
  document.getElementById('btn-revision').disabled = true;
  document.getElementById('btn-ver-pdf').disabled = true;
  document.getElementById('btn-email')?.setAttribute('disabled','');
  document.getElementById('btn-finalizar').disabled = true;
}
let _approvalDiagId = null;
async function solicitarRevisionPorId(id) {
  const res = await Diagnosticos.submitReview(id);
  if (!res?.ok) return toast(res?.error || 'Error al solicitar revisión','error');
  toast('Enviado a revisión');
  loadCertificados();
  if (typeof loadHistorial === 'function') loadHistorial();
}
async function openApprovalModalById(id) {
  if (!['admin','jefe'].includes(document.body.dataset.userRole)) return toast('Acceso restringido','warn');
  const d = await Diagnosticos.get(id);
  if (!d || d.estado_aprobacion !== 'en_revision') return toast('Expediente no disponible para aprobar','warn');
  _approvalDiagId = id;
  document.getElementById('approval-context').textContent = `Certificado ${d.n_certificado} · Técnico: ${d.tecnico_nombre}. Revise lecturas, patrón y dictamen antes de aprobar.`;
  document.getElementById('approval-password').value = '';
  document.getElementById('approval-comment').value = '';
  document.getElementById('approval-action').value = 'aprobar';
  openModal('approval-modal');
}
async function confirmarAprobacion() {
  if (!_approvalDiagId) return;
  const btn = document.getElementById('btn-confirm-approval');
  btn.disabled = true;
  const res = await Diagnosticos.approve(_approvalDiagId, {
    accion: document.getElementById('approval-action').value,
    comentario: document.getElementById('approval-comment').value,
    password: document.getElementById('approval-password').value,
  });
  btn.disabled = false;
  if (!res?.ok) return toast(res?.error || 'No se pudo aprobar el documento','error');
  document.getElementById('approval-password').value = '';
  closeModal('approval-modal');
  toast(res.estado === 'aprobado' ? 'Certificado aprobado y disponible para emitir PDF' : 'Devuelto para correcciones');
  loadCertificados();
  if (typeof loadHistorial === 'function') loadHistorial();
}
