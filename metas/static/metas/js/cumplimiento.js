/* Pantallas «Cumplimiento por delegación» y «Mi cumplimiento». Solo presentan lo que devuelven
   /api/dashboard/delegacion/<id>/ y /api/dashboard/funcionario/<id>/; los permisos por rol y
   por delegación los valida el servidor. */
(function () {
  'use strict';

  const CFG = JSON.parse(document.getElementById('configCumplimiento').textContent);
  const PROPIO = CFG.modo === 'propio';
  const $ = (id) => document.getElementById(id);

  function esc(v) {
    return String(v ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  }
  const pct = (v) => `${Number(v).toLocaleString('es-CL', { minimumFractionDigits: 2, maximumFractionDigits: 2 })} %`;
  const num = (v) => Number(v).toLocaleString('es-CL', { maximumFractionDigits: 2 });
  const COLORES = { verde: 'Verde', ambar: 'Ámbar', rojo: 'Rojo' };
  const semaforo = (color) => {
    const c = COLORES[color] ? color : 'rojo';
    return `<span class="cump-semaforo ${c}">${esc(COLORES[color] || color)}</span>`;
  };
  const opciones = (lista) => lista.map((o) => `<option value="${esc(o.id)}">${esc(o.texto)}</option>`).join('');

  async function api(url) {
    const resp = await fetch(url, { credentials: 'same-origin', headers: { Accept: 'application/json' } });
    let datos = null;
    try { datos = await resp.json(); } catch (e) { datos = null; }
    if (!resp.ok) {
      const d = datos || {};
      const detalle = d.detail || d.error || (d.periodo && [].concat(d.periodo).join(' '));
      const err = new Error(detalle || 'No se pudo cargar el cumplimiento.');
      err.status = resp.status;
      throw err;
    }
    return datos;
  }

  function estado(texto, error) {
    const e = $('estadoCumplimiento');
    e.innerHTML = texto ? `<i class="bi ${error ? 'bi-exclamation-triangle' : 'bi-info-circle'}" aria-hidden="true"></i><strong>${esc(texto)}</strong>` : '';
    e.classList.toggle('visible', Boolean(texto));
  }

  let ficha = 0; // descarta respuestas viejas si el usuario consulta otra cosa
  async function verDetalle(funcionarioId, nombre) {
    const mio = ++ficha;
    estado('Cargando detalle…');
    try {
      const d = await api(`/api/dashboard/funcionario/${funcionarioId}/?periodo=${encodeURIComponent($('selPeriodo').value)}`);
      if (mio !== ficha) return;
      estado('');
      $('tituloDetalle').textContent = nombre ? `Detalle de ${nombre}` : 'Detalle';
      $('semaforoDetalle').innerHTML = semaforo(d.color_semaforo);
      $('detComputable').textContent = pct(d.cumplimiento_computable);
      $('detBruto').textContent = pct(d.cumplimiento_bruto);
      $('detEsperado').textContent = pct(d.porcentaje_esperado);
      $('cuerpoItems').innerHTML = d.items.length
        ? d.items.map((i) => `<tr><td>${esc(i.nombre_item)}</td><td>${num(i.meta_objetivo)}</td><td>${num(i.avance_aprobado)}</td><td>${pct(i.ponderador)}</td><td>${pct(i.cumplimiento_pct)}</td><td>${pct(i.aporte_ponderado)}</td></tr>`).join('')
        : '<tr><td colspan="6">No tiene metas asignadas en este período.</td></tr>';
      $('panelDetalle').hidden = false;
      if (!PROPIO) $('panelDetalle').scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    } catch (e) {
      if (mio !== ficha) return;
      $('panelDetalle').hidden = true;
      estado(e.message, true);
    }
  }

  async function consultar() {
    ficha++;
    $('panelDetalle').hidden = true;
    if (!$('selPeriodo').value) { estado('No hay períodos registrados.', true); return; }
    if (PROPIO) {
      if (!CFG.funcionario_id) { estado('Tu cuenta no tiene una ficha de funcionario asociada.', true); return; }
      return verDetalle(CFG.funcionario_id, CFG.nombre);
    }
    $('panelDelegacion').hidden = true;
    const delegacion = $('selDelegacion').value;
    if (!delegacion) { estado('No tiene una delegación asignada para consultar.', true); return; }
    estado('Cargando…');
    try {
      const d = await api(`/api/dashboard/delegacion/${encodeURIComponent(delegacion)}/?periodo=${encodeURIComponent($('selPeriodo').value)}`);
      estado('');
      $('promedioDelegacion').textContent = `Promedio de la delegación: ${pct(d.promedio_cumplimiento_delegacion)} · ${d.total_funcionarios} funcionario${d.total_funcionarios === 1 ? '' : 's'}`;
      $('cuerpoFuncionarios').innerHTML = d.funcionarios.length
        ? d.funcionarios.map((f) => `<tr><td>${esc(f.nombre)}</td><td>${pct(f.cumplimiento_computable)}</td><td>${semaforo(f.color_semaforo)}</td><td class="acciones"><button type="button" class="btn-accion" data-id="${esc(f.funcionario_id)}" data-nombre="${esc(f.nombre)}"><i class="bi bi-eye"></i> Ver detalle</button></td></tr>`).join('')
        : '<tr><td colspan="4">La delegación no tiene funcionarios activos.</td></tr>';
      $('panelDelegacion').hidden = false;
    } catch (e) { estado(e.message, true); }
  }

  /* ---------------- Inicio ---------------- */
  $('selPeriodo').innerHTML = opciones(CFG.periodos);
  const vigente = CFG.periodos.find((p) => p.vigente) || CFG.periodos[0];
  if (vigente) $('selPeriodo').value = String(vigente.id);
  if (!PROPIO) {
    $('selDelegacion').innerHTML = opciones(CFG.delegaciones);
    // Delegado y Encargado tienen una sola delegación: queda fija.
    if (CFG.delegaciones.length === 1) $('selDelegacion').disabled = true;
    $('cuerpoFuncionarios').addEventListener('click', (e) => {
      const b = e.target.closest('button[data-id]');
      if (b) verDetalle(b.dataset.id, b.dataset.nombre);
    });
  }
  $('btnConsultar').addEventListener('click', consultar);
  $('selPeriodo').addEventListener('change', consultar);
  if (!PROPIO) $('selDelegacion').addEventListener('change', consultar);
  consultar();
})();
