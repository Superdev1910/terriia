/* Mantenedores de los catálogos de atención: tipos de atención y sub atenciones.
   Habla con /api/tipos-atencion/ y /api/sub-atenciones/ con la sesión de Django; los permisos
   y las reglas (duplicados, tipo inactivo) se validan en el servidor, aquí solo se presentan.
   En sub atenciones, el filtro por tipo y el select del formulario dependen del área elegida. */
(function () {
  'use strict';

  const $ = (id) => document.getElementById(id);
  const ENTIDAD = JSON.parse($('entidad').textContent);
  const AREAS = JSON.parse($('areas').textContent); // [{v, t}] desde organizacion.Area.NOMBRES
  const ES_SUB = ENTIDAD === 'sub-atenciones';

  const etiquetaEstado = (activo) => activo
    ? '<span class="etiqueta ok"><i class="bi bi-check-circle-fill"></i> Activo</span>'
    : '<span class="etiqueta no"><i class="bi bi-dash-circle"></i> Inactivo</span>';
  const textoEstado = (r) => (r.activo ? 'Activo' : 'Inactivo');

  /* ---------------- Configuración por mantenedor ---------------- */
  const CONFIG = {
    'tipos-atencion': {
      titulo: 'Tipos de atención', singular: 'tipo de atención', fin: 'o', nuevo: 'Nuevo tipo de atención',
      subtitulo: 'Tipos de atención de cada área. No se borran: se desactivan y conservan su historial.',
      url: '/api/tipos-atencion/', pk: 'id_tipo_atencion',
      columnas: [
        { k: 'area_nombre', t: 'Área' },
        { k: 'nombre', t: 'Tipo de atención' },
        { k: 'activo', t: 'Estado', html: (r) => etiquetaEstado(r.activo), excel: textoEstado },
      ],
    },
    'sub-atenciones': {
      titulo: 'Sub atenciones', singular: 'sub atención', fin: 'a', nuevo: 'Nueva sub atención',
      subtitulo: 'Cada sub atención pertenece a un tipo de atención activo. Elija primero el área.',
      url: '/api/sub-atenciones/', pk: 'id_sub_atencion',
      columnas: [
        { k: 'area_nombre', t: 'Área' },
        { k: 'tipo_atencion_nombre', t: 'Tipo de atención' },
        { k: 'nombre', t: 'Sub atención' },
        { k: 'activo', t: 'Estado', html: (r) => etiquetaEstado(r.activo), excel: textoEstado },
      ],
    },
  };
  const C = CONFIG[ENTIDAD];
  const TAM_PAGINA = 20;
  const estado = { pagina: 1 };
  let filas = [];
  let editando = null; // registro en edición; null = nuevo

  /* ---------------- Utilidades ---------------- */
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
    if (resp.status !== 204) { try { datos = await resp.json(); } catch (e) { datos = null; } }
    if (!resp.ok) {
      const err = new Error((datos && datos.error) || 'No se pudo completar la operación.');
      err.campo = datos && datos.campo; err.status = resp.status;
      throw err;
    }
    return datos;
  }
  async function traerTodo(url) {
    const registros = []; let sig = url;
    while (sig) { const d = await api(sig); registros.push(...d.results); sig = d.next; }
    return registros;
  }
  const opcionesHTML = (lista, valor) => lista
    .map((o) => `<option value="${esc(o.v)}" ${String(o.v) === String(valor) ? 'selected' : ''}>${esc(o.t)}</option>`).join('');
  const alerta = (icon, title, text) => Swal.fire({ icon, title, text, confirmButtonText: 'Entendido' });
  const aviso = (title) => Swal.fire({ toast: true, position: 'top-end', icon: 'success', title, showConfirmButton: false, timer: 2600, timerProgressBar: true });
  const cap = (s) => s.charAt(0).toUpperCase() + s.slice(1);

  // Tipos de atención de un área, para los select dependientes. soloActivos: para el formulario.
  async function tiposDelArea(area, soloActivos) {
    if (!area) return [];
    const p = new URLSearchParams({ area, page_size: 100 });
    if (soloActivos) p.set('activo', 'true');
    const tipos = await traerTodo(`/api/tipos-atencion/?${p}`);
    return tipos.map((t) => ({ v: t.id_tipo_atencion, t: t.activo ? t.nombre : `${t.nombre} (inactivo)` }));
  }

  /* ---------------- Filtros ---------------- */
  function parametros(extra = {}) {
    const p = new URLSearchParams({ page: estado.pagina, page_size: TAM_PAGINA, ...extra });
    const buscar = $('buscar').value.trim();
    if (buscar) p.set('search', buscar);
    if ($('filtroArea').value) p.set('area', $('filtroArea').value);
    if (ES_SUB && $('filtroTipo').value) p.set('tipo_atencion', $('filtroTipo').value);
    if ($('filtroEstado').value) p.set('activo', $('filtroEstado').value);
    return p;
  }
  async function pintarFiltroTipo() {
    const area = $('filtroArea').value;
    const selector = $('filtroTipo');
    selector.disabled = !area;
    selector.innerHTML = `<option value="">${area ? 'Todos los tipos' : 'Elija un área para filtrar por tipo'}</option>`;
    if (!area) return;
    try { selector.innerHTML += opcionesHTML(await tiposDelArea(area, false), ''); }
    catch (e) { alerta('error', 'No se pudieron cargar los tipos de atención', e.message); }
  }
  function filtrar() { estado.pagina = 1; listar(); }

  /* ---------------- Listado ---------------- */
  function mostrarEstado(icono, titulo, texto) {
    $('estado').innerHTML = `<i class="bi ${icono}"></i><strong>${esc(titulo)}</strong>${texto ? `<p>${esc(texto)}</p>` : ''}`;
    $('estado').classList.add('visible');
  }
  let turno = 0; // descarta respuestas viejas si el usuario escribe rápido en la búsqueda
  async function listar() {
    const mio = ++turno;
    try {
      const d = await api(`${C.url}?${parametros()}`);
      if (mio !== turno) return;
      filas = d.results;
      $('cuerpoTabla').innerHTML = filas.map(filaHTML).join('');
      if (d.count === 0) mostrarEstado('bi-inbox', 'Sin registros', 'Ningún registro coincide con la búsqueda o los filtros.');
      else $('estado').classList.remove('visible');
      const ini = (estado.pagina - 1) * TAM_PAGINA + 1;
      $('total').textContent = d.count
        ? `Mostrando ${ini}–${ini + filas.length - 1} de ${d.count} resultado${d.count === 1 ? '' : 's'}`
        : '0 resultados';
      pintarPaginador(Math.ceil(d.count / TAM_PAGINA));
    } catch (e) {
      if (mio !== turno) return;
      if (e.status === 404 && estado.pagina > 1) { estado.pagina = 1; return listar(); }
      $('cuerpoTabla').innerHTML = ''; $('paginador').innerHTML = ''; $('total').textContent = '';
      mostrarEstado('bi-exclamation-triangle', 'No se pudo cargar el listado', e.message);
    }
  }
  function filaHTML(r) {
    const celdas = C.columnas.map((c) => `<td>${c.html ? c.html(r) : esc(r[c.k])}</td>`).join('');
    const id = r[C.pk];
    return `<tr>${celdas}<td class="acciones">
      <button class="btn-accion" data-accion="editar" data-id="${id}" aria-label="Editar"><i class="bi bi-pencil"></i> Editar</button>
      ${r.activo ? `<button class="btn-accion peligro" data-accion="desactivar" data-id="${id}" aria-label="Desactivar"><i class="bi bi-slash-circle"></i> Desactivar</button>` : ''}
    </td></tr>`;
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

  /* ---------------- Formulario ---------------- */
  function campo(k, etiqueta, control, ayuda) {
    return `<div class="campo ancho" data-campo="${k}">
      <label for="f_${k}">${etiqueta} <span class="oblig" aria-hidden="true">*</span><span class="sr">(obligatorio)</span></label>
      ${control}
      ${ayuda ? `<small class="ayuda">${ayuda}</small>` : ''}
      <span class="error" id="e_${k}" role="alert"></span>
    </div>`;
  }
  function camposHTML(reg) {
    const area = reg ? reg.area : '';
    const selectArea = `<select id="f_area" name="area"><option value="">Seleccione un área</option>${opcionesHTML(AREAS, area)}</select>`;
    const nombre = `<input id="f_nombre" name="nombre" type="text" maxlength="100" value="${esc(reg ? reg.nombre : '')}">`;
    if (!ES_SUB) return campo('area', 'Área', selectArea) + campo('nombre', 'Nombre', nombre);
    return campo('area', 'Área', selectArea, 'Solo se usa para elegir el tipo de atención.')
      + campo('tipo_atencion', 'Tipo de atención', '<select id="f_tipo_atencion" name="tipo_atencion"></select>', 'Solo aparecen los tipos activos del área elegida.')
      + campo('nombre', 'Nombre', nombre);
  }
  // Llena el select de tipo del formulario con los tipos activos del área elegida.
  async function pintarTipoFormulario(seleccionado) {
    const area = $('f_area').value;
    const selector = $('f_tipo_atencion');
    selector.disabled = !area;
    selector.innerHTML = `<option value="">${area ? 'Seleccione un tipo de atención' : 'Primero elija un área'}</option>`;
    if (!area) return;
    try {
      const tipos = await tiposDelArea(area, true);
      // Al editar, el tipo actual se muestra aunque esté inactivo, para no cambiarlo sin querer.
      if (editando && editando.area === area && !tipos.some((t) => t.v === editando.tipo_atencion)) {
        tipos.unshift({ v: editando.tipo_atencion, t: `${editando.tipo_atencion_nombre} (inactivo)` });
      }
      if (!tipos.length) selector.innerHTML = '<option value="">El área no tiene tipos de atención activos</option>';
      selector.innerHTML += opcionesHTML(tipos, seleccionado);
    } catch (e) { alerta('error', 'No se pudieron cargar los tipos de atención', e.message); }
  }
  async function abrirModal(reg) {
    editando = reg || null;
    $('modalTitulo').textContent = reg ? `Editar ${C.singular}` : C.nuevo;
    $('camposForm').innerHTML = camposHTML(reg);
    if (ES_SUB) {
      $('f_area').addEventListener('change', () => pintarTipoFormulario(''));
      await pintarTipoFormulario(reg ? reg.tipo_atencion : '');
    }
    $('modal').hidden = false;
    $('f_area').focus();
  }
  function cerrarModal() { $('modal').hidden = true; editando = null; }
  function marcar(k, mensaje) {
    const caja = document.querySelector(`[data-campo="${k}"]`);
    if (!caja) return false;
    caja.classList.add('invalido'); $(`e_${k}`).textContent = mensaje; return true;
  }
  function limpiarErrores() {
    document.querySelectorAll('.campo.invalido').forEach((c) => c.classList.remove('invalido'));
    document.querySelectorAll('.campo .error').forEach((e) => { e.textContent = ''; });
  }
  function recolectar() {
    const datos = { nombre: $('f_nombre').value.trim() };
    if (ES_SUB) datos.tipo_atencion = $('f_tipo_atencion').value ? Number($('f_tipo_atencion').value) : '';
    else datos.area = $('f_area').value;
    const obligatorios = ES_SUB ? ['area', 'tipo_atencion', 'nombre'] : ['area', 'nombre'];
    const faltan = obligatorios.filter((k) => !$(`f_${k}`).value.trim());
    return { datos, faltan };
  }
  async function guardar(ev) {
    ev.preventDefault();
    if ($('btnGuardar').disabled) return; // evita doble envío
    limpiarErrores();
    const { datos, faltan } = recolectar();
    if (faltan.length) {
      faltan.forEach((k) => marcar(k, 'Este campo es obligatorio.'));
      return alerta('warning', 'Revise el formulario', 'Hay campos obligatorios sin completar.');
    }
    const crear = !editando;
    $('btnGuardar').disabled = true;
    try {
      await api(crear ? C.url : `${C.url}${editando[C.pk]}/`, { method: crear ? 'POST' : 'PATCH', body: JSON.stringify(datos) });
      cerrarModal();
      aviso(`${cap(C.singular)} ${crear ? 'cread' : 'actualizad'}${C.fin} correctamente`);
      if (ES_SUB) await pintarFiltroTipoConservando();
      listar();
    } catch (e) {
      const enCampo = e.campo && marcar(e.campo, e.message);
      alerta('error', enCampo ? 'Revise el formulario' : 'No se pudo guardar', e.message);
    } finally { $('btnGuardar').disabled = false; }
  }
  async function pintarFiltroTipoConservando() {
    const actual = $('filtroTipo').value;
    await pintarFiltroTipo();
    $('filtroTipo').value = actual;
  }
  async function desactivar(id) {
    const r = await Swal.fire({
      icon: 'warning', title: `¿Desactivar ${C.singular}?`,
      text: 'El registro no se borra: queda inactivo y conserva su historial.',
      showCancelButton: true, confirmButtonText: 'Sí, desactivar', cancelButtonText: 'Cancelar', reverseButtons: true,
    });
    if (!r.isConfirmed) return;
    try {
      await api(`${C.url}${id}/`, { method: 'DELETE' });
      aviso(`${cap(C.singular)} desactivad${C.fin}`);
      listar();
    } catch (e) { alerta('error', 'No se pudo desactivar', e.message); }
  }

  /* ---------------- Exportar a Excel ---------------- */
  async function exportar() {
    Swal.fire({ title: 'Generando archivo…', allowOutsideClick: false, didOpen: () => Swal.showLoading() });
    try {
      const p = parametros({ page_size: 100 }); p.delete('page');
      const registros = await traerTodo(`${C.url}?${p}`);
      const encabezados = C.columnas.map((c) => c.t);
      const datos = registros.map((r) => C.columnas.map((c) => (c.excel ? c.excel(r) : r[c.k] ?? '')));
      const hoja = XLSX.utils.aoa_to_sheet([encabezados, ...datos]);
      hoja['!cols'] = encabezados.map((e, i) => ({
        wch: Math.min(Math.max(e.length, ...datos.map((f) => String(f[i]).length)) + 2, 40),
      }));
      const libro = XLSX.utils.book_new();
      XLSX.utils.book_append_sheet(libro, hoja, C.titulo.slice(0, 31));
      XLSX.writeFile(libro, `${ENTIDAD}.xlsx`);
      Swal.close();
      aviso(`${registros.length} registro${registros.length === 1 ? '' : 's'} exportado${registros.length === 1 ? '' : 's'}`);
    } catch (e) { alerta('error', 'No se pudo exportar', e.message); }
  }

  /* ---------------- Eventos ---------------- */
  $('tituloPagina').textContent = C.titulo;
  $('subtituloPagina').textContent = C.subtitulo;
  $('txtNuevo').textContent = C.nuevo;
  $('capTabla').textContent = `Listado de ${C.titulo.toLowerCase()}`;
  $('cabeceraTabla').innerHTML = C.columnas.map((c) => `<th scope="col">${c.t}</th>`).join('') + '<th scope="col" class="acciones">Acciones</th>';
  $('filtroArea').innerHTML += opcionesHTML(AREAS, '');

  $('buscar').addEventListener('input', filtrar);
  $('filtroEstado').addEventListener('change', filtrar);
  $('filtroArea').addEventListener('change', async () => { if (ES_SUB) await pintarFiltroTipo(); filtrar(); });
  if (ES_SUB) $('filtroTipo').addEventListener('change', filtrar);
  $('btnLimpiar').addEventListener('click', async () => {
    $('buscar').value = ''; $('filtroArea').value = ''; $('filtroEstado').value = '';
    if (ES_SUB) await pintarFiltroTipo();
    filtrar();
  });
  $('paginador').addEventListener('click', (e) => {
    const b = e.target.closest('button[data-p]');
    if (!b || b.disabled) return;
    estado.pagina = Number(b.dataset.p); listar();
  });
  $('cuerpoTabla').addEventListener('click', (e) => {
    const b = e.target.closest('button[data-accion]');
    if (!b) return;
    if (b.dataset.accion === 'editar') abrirModal(filas.find((r) => String(r[C.pk]) === b.dataset.id));
    else desactivar(b.dataset.id);
  });
  $('btnNuevo').addEventListener('click', () => abrirModal(null));
  $('btnExcel').addEventListener('click', exportar);
  $('formulario').addEventListener('submit', guardar);
  $('btnCancelar').addEventListener('click', cerrarModal);
  $('modalCerrar').addEventListener('click', cerrarModal);
  document.addEventListener('keydown', (e) => { if (e.key === 'Escape' && !$('modal').hidden && !Swal.isVisible()) cerrarModal(); });

  if (ES_SUB) pintarFiltroTipo();
  listar();
}());
