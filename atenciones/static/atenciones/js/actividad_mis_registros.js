/* Mis registros (SCRUM-62): listado filtrable de /api/actividades/?mis_registros=true y
   exportación a Excel con SheetJS. El alcance real lo aplica el servidor. */
(function () {
  'use strict';

  const $ = (id) => document.getElementById(id);
  const URL = '/api/actividades/';
  const TAM_PAGINA = 20;
  const estado = { pagina: 1 };
  const TIPOS = { actividad: 'Actividad', gestion_social: 'Gestión social' };
  const VERIF = { pendiente: 'Pendiente', aprobada: 'Aprobada', rechazada: 'Rechazada', antecedentes: 'Requiere antecedentes' };
  const { api: apiComun, badge, listaEvidencias } = window.TerriIA;
  let filas = [];

  function esc(v) {
    return String(v ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  }
  async function api(url) {
    const resp = await fetch(url, { credentials: 'same-origin', headers: { Accept: 'application/json' } });
    let datos = null;
    try { datos = await resp.json(); } catch (e) { datos = null; }
    if (!resp.ok) throw new Error((datos && datos.error) || 'No se pudo completar la operación.');
    return datos;
  }
  async function traerTodo(url) {
    const registros = []; let sig = url;
    while (sig) { const d = await api(sig); registros.push(...d.results); sig = d.next; }
    return registros;
  }
  const fechaTexto = (iso) => new Date(iso).toLocaleString('es-CL', { dateStyle: 'short', timeStyle: 'short' });
  const alerta = (icon, title, text) => Swal.fire({ icon, title, text, confirmButtonText: 'Entendido', confirmButtonColor: '#ad0000' });

  function parametros(extra = {}) {
    const p = new URLSearchParams({ mis_registros: 'true', page: estado.pagina, page_size: TAM_PAGINA, ...extra });
    const buscar = $('buscar').value.trim();
    if (buscar) p.set('search', buscar);
    const mapa = { filtroTipo: 'tipo_registro', filtroPondera: 'pondera', filtroVerificacion: 'estado_verificacion', filtroDesde: 'desde', filtroHasta: 'hasta' };
    Object.entries(mapa).forEach(([id, nombre]) => { if ($(id).value) p.set(nombre, $(id).value); });
    return p;
  }

  function fila(r) {
    const pondera = r.pondera
      ? '<span class="etiqueta ok"><i class="bi bi-check-circle-fill"></i> Sí</span>'
      : `<span class="etiqueta alerta" title="${esc(r.motivo_no_pondera)}"><i class="bi bi-exclamation-triangle"></i> No</span><br><small>${esc(r.motivo_no_pondera)}</small>`;
    return `<tr>
      <td class="mono">${esc(r.codigo)}</td>
      <td>${esc(fechaTexto(r.fecha))}</td>
      <td>${esc(TIPOS[r.tipo_registro])}</td>
      <td>${esc(r.item_nombre)}</td>
      <td>${esc(r.vecino_nombre || r.contacto)}<br><small>${esc(r.vecino_rut || '')}</small></td>
      <td>${pondera}</td>
      <td>${badge(r.estado_verificacion)}</td>
      <td class="acciones">${r.puede_editar ? `<button class="btn-accion" data-editar="${r.id_actividad}"><i class="bi bi-pencil"></i> Editar</button>` : ''}
        <button class="btn-accion" data-evidencias="${r.id_actividad}"><i class="bi bi-paperclip"></i> Evidencias (${r.n_evidencias})</button></td>
    </tr>`;
  }
  function pintarPaginador(paginas) {
    if (paginas <= 1) { $('paginador').innerHTML = ''; return; }
    const p = estado.pagina;
    let html = `<button type="button" data-p="${p - 1}" ${p === 1 ? 'disabled' : ''} aria-label="Página anterior"><i class="bi bi-chevron-left"></i></button>`;
    for (let n = 1; n <= paginas; n++) {
      html += `<button type="button" data-p="${n}" ${n === p ? 'aria-current="page"' : ''} aria-label="Página ${n}">${n}</button>`;
    }
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
      const d = await api(`${URL}?${parametros()}`);
      if (mio !== turno) return;
      filas = d.results;
      $('cuerpoTabla').innerHTML = filas.map(fila).join('');
      if (d.count === 0) mostrarEstado('bi-inbox', 'Sin registros', 'Ningún registro coincide con la búsqueda o los filtros.');
      else $('estado').classList.remove('visible');
      const ini = (estado.pagina - 1) * TAM_PAGINA + 1;
      $('total').textContent = d.count ? `Mostrando ${ini}–${ini + d.results.length - 1} de ${d.count}` : '0 resultados';
      pintarPaginador(Math.ceil(d.count / TAM_PAGINA));
    } catch (e) {
      if (mio !== turno) return;
      $('cuerpoTabla').innerHTML = ''; $('paginador').innerHTML = ''; $('total').textContent = '';
      mostrarEstado('bi-exclamation-triangle', 'No se pudo cargar el listado', e.message);
    }
  }
  function filtrar() { estado.pagina = 1; listar(); }

  async function exportar() {
    Swal.fire({ title: 'Generando archivo…', allowOutsideClick: false, didOpen: () => Swal.showLoading() });
    try {
      const p = parametros({ page_size: 100 }); p.delete('page');
      const registros = await traerTodo(`${URL}?${p}`);
      const encabezados = ['Código', 'Fecha', 'Tipo', 'Ítem', 'RUT', 'Vecino', 'Pondera', 'Motivo no pondera', 'Verificación'];
      const datos = registros.map((r) => [
        r.codigo, fechaTexto(r.fecha), TIPOS[r.tipo_registro], r.item_nombre, r.vecino_rut || '',
        r.vecino_nombre || r.contacto, r.pondera ? 'Sí' : 'No', r.motivo_no_pondera, VERIF[r.estado_verificacion],
      ]);
      const hoja = XLSX.utils.aoa_to_sheet([encabezados, ...datos]);
      hoja['!cols'] = encabezados.map((e, i) => ({ wch: Math.min(Math.max(e.length, ...datos.map((f) => String(f[i]).length)) + 2, 40) }));
      const libro = XLSX.utils.book_new();
      XLSX.utils.book_append_sheet(libro, hoja, 'Mis registros');
      XLSX.writeFile(libro, 'mis-registros.xlsx');
      Swal.close();
    } catch (e) { alerta('error', 'No se pudo exportar', e.message); }
  }

  /* ---------------- Editar (solo pendiente o con antecedentes pedidos) ---------------- */
  async function editar(id) {
    const r = filas.find((x) => x.id_actividad === id);
    const res = await Swal.fire({
      title: `Editar ${esc(r.codigo)}`, confirmButtonText: 'Guardar', showCancelButton: true, cancelButtonText: 'Cancelar', confirmButtonColor: '#ad0000',
      html: `<div class="form-swal"><label>Descripción<textarea id="eDescripcion" class="swal2-textarea">${esc(r.descripcion)}</textarea></label>
        <label>Acción realizada<input id="eAccion" class="swal2-input" value="${esc(r.accion)}"></label>
        <label>Nombre de la persona atendida<input id="eContacto" class="swal2-input" value="${esc(r.contacto)}"></label>
        <label>Teléfono<input id="eTelefono" class="swal2-input" value="${esc(r.telefono)}"></label></div>`,
      preConfirm: () => ({
        descripcion: document.getElementById('eDescripcion').value.trim(), accion: document.getElementById('eAccion').value.trim(),
        contacto: document.getElementById('eContacto').value.trim(), telefono: document.getElementById('eTelefono').value.trim(),
      }),
    });
    if (!res.isConfirmed) return;
    try {
      await apiComun(`${URL}${id}/`, { method: 'PATCH', body: JSON.stringify(res.value) });
      Swal.fire({ toast: true, position: 'top-end', icon: 'success', title: 'Registro actualizado', showConfirmButton: false, timer: 2600 });
    } catch (e) { alerta('error', 'No se pudo editar', e.message); }
    listar();
  }

  /* ---------------- Evidencias: ver, subir (JPG, PNG o PDF de hasta 5 MB) y quitar ---------------- */
  async function evidencias(id) {
    const r = filas.find((x) => x.id_actividad === id);
    const editable = r.estado_verificacion !== 'aprobada' && r.puede_editar;
    async function cargar() {
      const d = await apiComun(`/api/evidencias/?actividad=${id}&page_size=100`);
      return d.results.map((e) => ({ ...e, puedeQuitar: editable }));
    }
    try {
      const lista = await cargar();
      const subir = editable ? `<label class="subir">Agregar evidencia (JPG, PNG o PDF, máx. 5 MB)
        <input type="file" id="archivoEvidencia" accept=".jpg,.jpeg,.png,.pdf,image/jpeg,image/png,application/pdf"></label>` : '<p class="subtitulo">Esta actividad no admite cambios de evidencias.</p>';
      await Swal.fire({
        title: `Evidencias de ${esc(r.codigo)}`, showConfirmButton: false, showCloseButton: true,
        html: `<div id="listaEv">${listaEvidencias(lista)}</div>${subir}`,
        didOpen: (el) => {
          const entrada = el.querySelector('#archivoEvidencia');
          if (entrada) entrada.addEventListener('change', async () => {
            if (!entrada.files.length) return;
            const datos = new FormData(); datos.append('actividad', id); datos.append('archivo', entrada.files[0]);
            try { await apiComun('/api/evidencias/', { method: 'POST', body: datos }); Swal.close(); listar(); evidencias(id); }
            catch (e) { entrada.value = ''; alerta('error', 'No se pudo subir', e.message).then(() => evidencias(id)); }
          });
          el.addEventListener('click', async (ev) => {
            const b = ev.target.closest('[data-quitar]'); if (!b) return;
            try { await apiComun(`/api/evidencias/${b.dataset.quitar}/`, { method: 'DELETE' }); Swal.close(); listar(); evidencias(id); }
            catch (e) { alerta('error', 'No se pudo quitar', e.message); }
          });
        },
      });
    } catch (e) { alerta('error', 'No se pudieron cargar las evidencias', e.message); }
  }

  $('cuerpoTabla').addEventListener('click', (e) => {
    const ed = e.target.closest('[data-editar]'); if (ed) editar(Number(ed.dataset.editar));
    const ev = e.target.closest('[data-evidencias]'); if (ev) evidencias(Number(ev.dataset.evidencias));
  });
  let espera;
  $('buscar').addEventListener('input', () => { clearTimeout(espera); espera = setTimeout(filtrar, 300); });
  ['filtroTipo', 'filtroPondera', 'filtroVerificacion', 'filtroDesde', 'filtroHasta'].forEach((id) => $(id).addEventListener('change', filtrar));
  $('btnLimpiar').addEventListener('click', () => { $('filtros').reset(); filtrar(); });
  $('btnExcel').addEventListener('click', exportar);
  $('paginador').addEventListener('click', (e) => {
    const b = e.target.closest('button[data-p]');
    if (!b || b.disabled) return;
    estado.pagina = Number(b.dataset.p); listar();
  });
  listar();
})();
