/* Bandeja de verificación (SCRUM-123). Las reglas (quién verifica, transiciones, observación
   obligatoria) las valida el servidor; aquí solo se presentan y se piden las observaciones. */
(function () {
  'use strict';
  const { esc, api, fechaTexto, alerta, badge, listaEvidencias } = window.TerriIA;
  const $ = (id) => document.getElementById(id);
  const URL_ACT = '/api/actividades/';
  const TAM_PAGINA = 20;
  const estado = { pagina: 1 };
  let filas = [];

  function parametros() {
    const p = new URLSearchParams({ no_propias: 'true', page: estado.pagina, page_size: TAM_PAGINA });
    if ($('buscar').value.trim()) p.set('search', $('buscar').value.trim());
    const mapa = { filtroVerificacion: 'estado_verificacion', filtroTipo: 'tipo_registro', filtroDesde: 'desde', filtroHasta: 'hasta' };
    Object.entries(mapa).forEach(([id, nombre]) => { if ($(id).value) p.set(nombre, $(id).value); });
    return p;
  }
  const fila = (r) => `<tr>
    <td class="mono">${esc(r.codigo)}</td><td>${esc(fechaTexto(r.fecha))}</td>
    <td>${esc(r.funcionario_nombre)}</td><td>${esc(r.item_nombre)}</td>
    <td>${r.n_evidencias}</td><td>${badge(r.estado_verificacion)}</td>
    <td class="acciones acciones-apiladas"><button class="btn-accion" data-id="${r.id_actividad}"><i class="bi bi-eye"></i> Revisar</button></td></tr>`;

  function pintarPaginador(paginas) {
    if (paginas <= 1) { $('paginador').innerHTML = ''; return; }
    const p = estado.pagina;
    let html = `<button type="button" data-p="${p - 1}" ${p === 1 ? 'disabled' : ''} aria-label="Página anterior"><i class="bi bi-chevron-left"></i></button>`;
    for (let n = 1; n <= paginas; n++) html += `<button type="button" data-p="${n}" ${n === p ? 'aria-current="page"' : ''} aria-label="Página ${n}">${n}</button>`;
    html += `<button type="button" data-p="${p + 1}" ${p === paginas ? 'disabled' : ''} aria-label="Página siguiente"><i class="bi bi-chevron-right"></i></button>`;
    $('paginador').innerHTML = html;
  }
  function mostrarEstado(icono, titulo, texto) {
    $('estado').innerHTML = `<i class="bi ${icono}"></i><strong>${esc(titulo)}</strong>${texto ? `<p>${esc(texto)}</p>` : ''}`;
    $('estado').classList.add('visible');
  }
  let turno = 0;
  async function listar() {
    const mio = ++turno;
    try {
      const d = await api(`${URL_ACT}?${parametros()}`);
      if (mio !== turno) return;
      filas = d.results;
      $('cuerpoTabla').innerHTML = filas.map(fila).join('');
      if (d.count === 0) mostrarEstado('bi-inbox', 'Sin registros', 'No hay actividades con esos filtros.');
      else $('estado').classList.remove('visible');
      const ini = (estado.pagina - 1) * TAM_PAGINA + 1;
      $('total').textContent = d.count ? `Mostrando ${ini}–${ini + filas.length - 1} de ${d.count}` : '0 resultados';
      pintarPaginador(Math.ceil(d.count / TAM_PAGINA));
    } catch (e) {
      if (mio !== turno) return;
      $('cuerpoTabla').innerHTML = ''; $('paginador').innerHTML = ''; $('total').textContent = '';
      mostrarEstado('bi-exclamation-triangle', 'No se pudo cargar la bandeja', e.message);
    }
  }
  const filtrar = () => { estado.pagina = 1; listar(); };

  /* ---------------- Ficha ---------------- */
  async function abrirFicha(id) {
    const r = filas.find((x) => x.id_actividad === id);
    let evidencias = [], historial = [];
    try {
      [evidencias, historial] = await Promise.all([
        api(`/api/evidencias/?actividad=${id}&page_size=100`).then((d) => d.results),
        api(`${URL_ACT}${id}/historial/`),
      ]);
    } catch (e) { alerta('error', 'No se pudo cargar la ficha', esc(e.message)); return; }
    const hist = historial.length
      ? `<ol class="historial">${historial.map((h) => `<li>${esc(fechaTexto(h.fecha))} · ${esc(h.usuario_nombre)}: ${esc(h.estado_anterior)} → <strong>${esc(h.estado_nuevo)}</strong>${h.observacion ? `<br><em>${esc(h.observacion)}</em>` : ''}</li>`).join('')}</ol>`
      : '<p class="subtitulo">Sin movimientos.</p>';
    const puede = r.estado_verificacion === 'pendiente';
    const botones = puede ? `<div class="acciones-ficha">
        <button type="button" class="btn btn-primario" data-accion="aprobar"><i class="bi bi-check-lg"></i> Aprobar</button>
        <button type="button" class="btn btn-borde" data-accion="antecedentes"><i class="bi bi-question-circle"></i> Pedir antecedentes</button>
        <button type="button" class="btn btn-borde" data-accion="rechazar"><i class="bi bi-x-lg"></i> Rechazar</button></div>`
      : '<p class="aviso-cascada">Esta actividad ya no admite cambios de verificación.</p>';
    const ficha = await Swal.fire({
      titleText: r.codigo, width: 640, showConfirmButton: false, showCloseButton: true,
      html: `<dl class="ficha">
          <dt>Estado</dt><dd>${badge(r.estado_verificacion)}</dd>
          <dt>Funcionario</dt><dd>${esc(r.funcionario_nombre)}</dd>
          <dt>Fecha</dt><dd>${esc(fechaTexto(r.fecha))}</dd>
          <dt>Ítem</dt><dd>${esc(r.item_nombre)}</dd>
          <dt>Vecino</dt><dd>${esc(r.vecino_nombre || r.contacto)} ${esc(r.vecino_rut || '')}</dd>
          <dt>Pondera</dt><dd>${r.pondera ? 'Sí' : `No: ${esc(r.motivo_no_pondera)}`}</dd>
          <dt>Descripción</dt><dd>${esc(r.descripcion)}</dd></dl>
        <h3>Evidencias</h3>${listaEvidencias(evidencias)}
        <h3>Historial</h3>${hist}${botones}`,
      didOpen: (el) => {
        el.querySelectorAll('[data-accion]').forEach((b) => b.addEventListener('click', () => {
          Swal.close(); decidir(r, b.dataset.accion);
        }));
      },
    });
    return ficha;
  }
  const TEXTOS = {
    aprobar: ['Aprobar actividad', 'Una vez aprobada no se podrá modificar.', false],
    rechazar: ['Rechazar actividad', 'El rechazo es definitivo.', true],
    antecedentes: ['Pedir antecedentes', 'El autor podrá corregir y volverá a pendiente.', true],
  };
  async function decidir(r, accion) {
    const [titulo, texto, exige] = TEXTOS[accion];
    const res = await Swal.fire({
      title: titulo, text: texto, icon: accion === 'aprobar' ? 'question' : 'warning',
      input: 'textarea', inputLabel: exige ? 'Observación (obligatoria)' : 'Observación (opcional)',
      showCancelButton: true, confirmButtonText: 'Confirmar', cancelButtonText: 'Cancelar', confirmButtonColor: '#ad0000',
      inputValidator: (v) => (exige && !v.trim() ? 'Escriba la observación.' : undefined),
    });
    if (!res.isConfirmed) return;
    try {
      await api(`${URL_ACT}${r.id_actividad}/verificar/`, { method: 'POST', body: JSON.stringify({ accion, observacion: res.value || '' }) });
      Swal.fire({ toast: true, position: 'top-end', icon: 'success', title: 'Verificación registrada', showConfirmButton: false, timer: 2600 });
    } catch (e) { alerta('error', 'No se pudo verificar', esc(e.message)); }
    listar();
  }

  let espera;
  $('buscar').addEventListener('input', () => { clearTimeout(espera); espera = setTimeout(filtrar, 300); });
  ['filtroVerificacion', 'filtroTipo', 'filtroDesde', 'filtroHasta'].forEach((id) => $(id).addEventListener('change', filtrar));
  $('btnLimpiar').addEventListener('click', () => { $('filtros').reset(); filtrar(); });
  $('cuerpoTabla').addEventListener('click', (e) => {
    const b = e.target.closest('button[data-id]'); if (b) abrirFicha(Number(b.dataset.id));
  });
  $('paginador').addEventListener('click', (e) => {
    const b = e.target.closest('button[data-p]'); if (!b || b.disabled) return;
    estado.pagina = Number(b.dataset.p); listar();
  });
  listar();
})();
