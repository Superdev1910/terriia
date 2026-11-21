/* Registrar actividad (SCRUM-62). Habla con /api/actividades/ con la sesión de Django.
   Las reglas (tope diario, semana cerrada, consistencia, ponderación) las valida el servidor;
   aquí solo se presentan los selects dependientes, el autocompletado por RUT y los avisos. */
(function () {
  'use strict';

  const $ = (id) => document.getElementById(id);
  let OPCIONES = { items: [], areas: [], territorios: [], tipos_atencion: [], sub_atenciones: [] };
  let vecinoId = null;
  const AYUDA_RUT = 'Al salir del campo se completan los datos del vecino.';

  function esc(v) {
    return String(v ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  }
  function csrf() {
    const m = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
    return m ? decodeURIComponent(m[1]) : '';
  }
  async function api(url, opciones = {}) {
    const resp = await fetch(url, {
      credentials: 'same-origin',
      headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf(), Accept: 'application/json' },
      ...opciones,
    });
    let datos = null;
    try { datos = await resp.json(); } catch (e) { datos = null; }
    if (!resp.ok) {
      const err = new Error((datos && datos.error) || 'No se pudo completar la operación.');
      err.campo = datos && datos.campo; err.status = resp.status;
      throw err;
    }
    return datos;
  }
  const alerta = (icon, title, html) => Swal.fire({ icon, title, html, confirmButtonText: 'Entendido', confirmButtonColor: '#ad0000' });
  const llenar = (sel, lista, vacio, v, t) => {
    $(sel).innerHTML = `<option value="">${esc(vacio)}</option>` +
      lista.map((o) => `<option value="${esc(o[v])}">${esc(o[t])}</option>`).join('');
  };

  function fechaLocalActual() {
    const d = new Date(); d.setMinutes(d.getMinutes() - d.getTimezoneOffset());
    return d.toISOString().slice(0, 16);
  }
  function limpiarErrores() {
    document.querySelectorAll('.campo.invalido').forEach((c) => c.classList.remove('invalido'));
    document.querySelectorAll('[data-error]').forEach((e) => { e.textContent = ''; });
  }
  function marcarError(campo, mensaje) {
    const e = document.querySelector(`[data-error="${campo}"]`);
    if (!e) return false;
    e.textContent = mensaje; e.closest('.campo').classList.add('invalido');
    return true;
  }

  /* ---------------- Selects dependientes ---------------- */
  function pintarTipos() {
    const area = OPCIONES.areas.find((a) => String(a.id_area) === $('area').value);
    const tipos = area ? OPCIONES.tipos_atencion.filter((t) => t.area === area.nombre) : [];
    llenar('tipo_atencion', tipos, area ? 'Seleccione…' : 'Elija primero el área', 'id_tipo_atencion', 'nombre');
    $('tipo_atencion').disabled = !area;
    pintarSubs();
  }
  function pintarSubs() {
    const tipo = $('tipo_atencion').value;
    const subs = tipo ? OPCIONES.sub_atenciones.filter((s) => String(s.tipo_atencion) === tipo) : [];
    llenar('sub_atencion', subs, tipo ? 'Sin sub atención' : 'Elija primero el tipo', 'id_sub_atencion', 'nombre');
    $('sub_atencion').disabled = !tipo;
  }

  /* ---------------- Autocompletado por RUT ---------------- */
  async function buscarRut() {
    const rut = $('rut').value.trim();
    vecinoId = null;
    if (!rut) { $('ayudaRut').textContent = AYUDA_RUT; return; }
    try {
      const v = await api(`/api/vecinos/buscar/?rut=${encodeURIComponent(rut)}`);
      vecinoId = v.id_vecino;
      $('rut').value = v.rut;
      $('contacto').value = `${v.nombres} ${v.apellidos}`.trim();
      $('telefono').value = v.telefono || '';
      $('ayudaRut').textContent = 'Vecino encontrado: datos completados.';
    } catch (e) {
      $('ayudaRut').textContent = e.message + ' Puede escribir el nombre y teléfono a mano.';
    }
  }

  /* ---------------- Guardar ---------------- */
  function datosFormulario() {
    const num = (id) => ($(id).value ? Number($(id).value) : null);
    const f = $('fecha').value;
    return {
      tipo_registro: document.querySelector('input[name="tipo_registro"]:checked').value,
      fecha: f ? new Date(f).toISOString() : null,
      item: num('item'),
      vecino: vecinoId,
      territorio: num('territorio'),
      area: num('area'),
      tipo_atencion: num('tipo_atencion'),
      sub_atencion: num('sub_atencion'),
      contacto: $('contacto').value.trim(),
      telefono: $('telefono').value.trim(),
      descripcion: $('descripcion').value.trim(),
      accion: $('accion').value.trim(),
      es_coordinacion_preparatoria: $('es_coordinacion_preparatoria').checked,
      ingreso_a_tubo: $('ingreso_a_tubo').checked,
    };
  }
  async function guardar(e) {
    e.preventDefault();
    limpiarErrores();
    const datos = datosFormulario();
    if (!datos.item) { marcarError('item', 'Seleccione un ítem.'); return; }
    if (!datos.fecha) { marcarError('fecha', 'Indique la fecha.'); return; }
    $('btnGuardar').disabled = true;
    try {
      const r = await api('/api/actividades/', { method: 'POST', body: JSON.stringify(datos) });
      const aviso = r.pondera ? '' :
        `<p class="aviso-cascada"><i class="bi bi-exclamation-triangle"></i> <strong>No pondera:</strong> ${esc(r.motivo_no_pondera)}</p>`;
      await alerta(r.pondera ? 'success' : 'warning', 'Registro guardado',
        `<p>Código: <strong class="mono">${esc(r.codigo)}</strong></p>${aviso}`);
      $('formActividad').reset(); vecinoId = null; $('ayudaRut').textContent = AYUDA_RUT; $('fecha').value = fechaLocalActual(); pintarTipos();
    } catch (err) {
      if (!(err.campo && marcarError(err.campo, err.message))) {
        alerta('error', 'No se pudo guardar', esc(err.message));
      } else if (err.campo === 'fecha') {
        alerta('error', 'No se pudo guardar', esc(err.message));
      }
    } finally { $('btnGuardar').disabled = false; }
  }

  async function iniciar() {
    $('fecha').value = fechaLocalActual();
    try {
      OPCIONES = await api('/api/actividades/opciones/');
    } catch (e) {
      alerta('error', 'No se pudo cargar el formulario', esc(e.message));
      $('btnGuardar').disabled = true;
      return;
    }
    llenar('item', OPCIONES.items, 'Seleccione…', 'id_item', 'nombre');
    llenar('territorio', OPCIONES.territorios, 'Sin territorio', 'id_territorio', 'nombre');
    llenar('area', OPCIONES.areas, 'Sin área', 'id_area', 'texto');
    $('area').addEventListener('change', pintarTipos);
    $('tipo_atencion').addEventListener('change', pintarSubs);
    $('rut').addEventListener('blur', buscarRut);
    $('btnBuscarRut').addEventListener('click', buscarRut);
    $('rut').addEventListener('input', () => { vecinoId = null; });
    $('formActividad').addEventListener('submit', guardar);
    $('formActividad').addEventListener('reset', () => {
      limpiarErrores(); vecinoId = null; $('ayudaRut').textContent = AYUDA_RUT;
      setTimeout(() => { $('fecha').value = fechaLocalActual(); pintarTipos(); }, 0);
    });
  }
  // Sin ficha activa el servidor ya deshabilitó el formulario: no se piden catálogos (darían 403).
  if (!$('formActividad').dataset.sinFicha) iniciar();
})();
