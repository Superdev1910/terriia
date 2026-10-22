/* Motor común de los mantenedores de organización (delegación, área, cargo).
   Habla con la API REST (/api/...) con la sesión de Django; los permisos y las reglas
   de negocio se validan en el servidor, esta pantalla solo los presenta. */
(function () {
  'use strict';

  const ENTIDAD = JSON.parse(document.getElementById('entidad').textContent);

  const ESTADOS_ACT = [{ v: 'activa', t: 'Activa' }, { v: 'inactiva', t: 'Inactiva' }];
  const TIPOS_AREA = [
    { v: 'Social', t: 'Social' }, { v: 'DISERCO', t: 'DISERCO' },
    { v: 'Seguridad', t: 'Seguridad' }, { v: 'Organizacion Comunitaria', t: 'Organización Comunitaria' },
  ];

  const etiquetaEstado = (activo, si, no) => activo
    ? `<span class="etiqueta ok"><i class="bi bi-check-circle-fill"></i> ${si}</span>`
    : `<span class="etiqueta no"><i class="bi bi-dash-circle"></i> ${no}</span>`;

  /* ---------------- Configuración por mantenedor ---------------- */
  const CONFIG = {
    delegaciones: {
      titulo: 'Delegaciones', singular: 'delegación', nuevo: 'Nueva delegación',
      subtitulo: 'Al crear una delegación se generan automáticamente sus 4 áreas.',
      url: '/api/delegaciones/', pk: 'id_delegacion', archivo: 'delegaciones', detalle: true,
      dependientes: (r) => ({ areas: r.areas_activas || 0, cargos: r.cargos_vigentes || 0 }),
      campoEstado: 'estado', esActivo: (r) => r.estado === 'activa',
      columnas: [
        { k: 'codigo', orden: 'codigo', t: 'Código', html: (r) => `<span class="codigo">${esc(r.codigo)}</span>` },
        { k: 'nombre', orden: 'nombre', t: 'Nombre' },
        { k: 'direccion', orden: 'direccion', t: 'Dirección', vacio: '—' },
        { k: 'comuna', orden: 'comuna', t: 'Comuna' },
        { k: 'total_areas', orden: 'n_areas', t: 'Áreas', html: (r) => `<span class="etiqueta info"><i class="bi bi-diagram-3"></i> ${r.total_areas}</span>` },
        { k: 'estado', orden: 'estado', t: 'Estado', html: (r) => etiquetaEstado(r.estado === 'activa', 'Activa', 'Inactiva'), excel: (r) => r.estado === 'activa' ? 'Activa' : 'Inactiva' },
      ],
      campos: [
        { k: 'codigo', t: 'Código', req: true, max: 10, ayuda: 'Ej.: D01. Se guarda en mayúsculas.' },
        { k: 'estado', t: 'Estado', tipo: 'select', opciones: () => ESTADOS_ACT, defecto: 'activa' },
        { k: 'nombre', t: 'Nombre', req: true, max: 100, ancho: true },
        { k: 'ambito', t: 'Ámbito', max: 150, ancho: true, ayuda: 'Sector que cubre la delegación (ej.: Centro, Rural, La Antena).' },
        { k: 'direccion', t: 'Dirección', max: 200, ancho: true },
        { k: 'comuna', t: 'Comuna', req: true, max: 80, defecto: 'La Serena' },
      ],
      filtros: [{ k: 'estado', t: 'Todos los estados', opciones: () => ESTADOS_ACT }],
    },

    areas: {
      titulo: 'Áreas', singular: 'área', nuevo: 'Nueva área',
      subtitulo: 'Las 4 áreas nacen con cada delegación. Use «Nueva área» solo si falta alguna: cada área una vez y una prioridad por delegación. Si cambia la prioridad a una ya usada, las dos áreas la intercambian.',
      url: '/api/areas/', pk: 'id_area', archivo: 'areas',
      dependientes: (r) => ({ areas: 0, cargos: r.cargos_vigentes || 0 }),
      campoEstado: 'estado', esActivo: (r) => r.estado === 'activa',
      columnas: [
        { k: 'delegacion_codigo', orden: 'delegacion__codigo', t: 'Delegación', html: (r) => `<span class="codigo">${esc(r.delegacion_codigo)}</span> ${esc(r.delegacion_nombre)}`, excel: (r) => `${r.delegacion_codigo} · ${r.delegacion_nombre}` },
        { k: 'nombre_texto', orden: 'nombre', t: 'Área' },
        { k: 'prioridad', orden: 'prioridad', t: 'Prioridad', html: (r) => `<span class="etiqueta info">${r.prioridad}</span>` },
        { k: 'estado', orden: 'estado', t: 'Estado', html: (r) => etiquetaEstado(r.estado === 'activa', 'Activa', 'Inactiva'), excel: (r) => r.estado === 'activa' ? 'Activa' : 'Inactiva' },
      ],
      campos: [
        { k: 'delegacion', t: 'Delegación', tipo: 'select', req: true, ancho: true, opciones: () => OPC.delegaciones, vacio: 'Seleccione una delegación' },
        { k: 'nombre', t: 'Área', tipo: 'select', req: true, opciones: () => TIPOS_AREA, vacio: 'Seleccione' },
        { k: 'prioridad', t: 'Prioridad (1 a 4)', tipo: 'number', req: true, min: 1, max: 4 },
        { k: 'estado', t: 'Estado', tipo: 'select', opciones: () => ESTADOS_ACT, defecto: 'activa' },
      ],
      filtros: [
        { k: 'delegacion', t: 'Todas las delegaciones', opciones: () => OPC.delegaciones },
        { k: 'nombre', t: 'Todas las áreas', opciones: () => TIPOS_AREA },
        { k: 'estado', t: 'Todos los estados', opciones: () => ESTADOS_ACT },
      ],
      cargarOpciones: () => cargarDelegaciones(),
    },

    cargos: {
      titulo: 'Cargos', singular: 'cargo', nuevo: 'Nuevo cargo',
      subtitulo: 'Un cargo sin área es transversal. Márquelo como vigente o no vigente.',
      url: '/api/cargos/', pk: 'id_cargo', archivo: 'cargos',
      campoEstado: 'vigente', esActivo: (r) => r.vigente === true,
      columnas: [
        { k: 'nombre', orden: 'nombre', t: 'Cargo' },
        { k: 'area_texto', orden: 'area__delegacion__codigo', t: 'Área', html: (r) => r.transversal ? '<span class="etiqueta info"><i class="bi bi-arrows-fullscreen"></i> Transversal</span>' : esc(r.area_texto), excel: (r) => r.area_texto },
        { k: 'descripcion', orden: 'descripcion', t: 'Descripción', vacio: '—' },
        { k: 'vigente', orden: 'vigente', t: 'Estado', html: (r) => etiquetaEstado(r.vigente, 'Vigente', 'No vigente'), excel: (r) => r.vigente ? 'Vigente' : 'No vigente' },
      ],
      campos: [
        { k: 'nombre', t: 'Nombre del cargo', req: true, max: 100, ancho: true },
        { k: 'area', t: 'Área', tipo: 'select', ancho: true, opciones: () => OPC.areas, vacio: 'Transversal (sin área)', nulo: true, ayuda: 'Déjelo en «Transversal» si el cargo no pertenece a un área.' },
        { k: 'descripcion', t: 'Descripción', tipo: 'textarea', max: 255, ancho: true },
        { k: 'vigente', t: 'Vigencia', tipo: 'select', bool: true, opciones: () => [{ v: 'true', t: 'Vigente' }, { v: 'false', t: 'No vigente' }], defecto: 'true' },
      ],
      filtros: [
        { k: 'vigente', t: 'Todas las vigencias', opciones: () => [{ v: 'true', t: 'Vigente' }, { v: 'false', t: 'No vigente' }] },
        { k: 'area', t: 'Todas las áreas', opciones: () => OPC.areas },
      ],
      cargarOpciones: () => cargarAreas(),
    },
  };

  const C = CONFIG[ENTIDAD];
  const OPC = { delegaciones: [], areas: [] };
  const estado = { pagina: 1, tam: 20, orden: '', buscar: '', filtros: {}, total: 0, cargando: false, nuevo: null };
  const registros = {}; // registros de la página visible, por id (para el aviso al desactivar)
  let disparador = null; // elemento que abrió el formulario o el panel, para devolverle el foco
  let editando = null; // {modo, registro}
  let sucio = false;

  /* ---------------- Utilidades ---------------- */
  const $ = (id) => document.getElementById(id);
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
    const filas = []; let sig = url;
    while (sig) { const d = await api(sig); filas.push(...d.results); sig = d.next; }
    return filas;
  }
  function parametros(pagina, tam) {
    const p = new URLSearchParams();
    if (pagina) p.set('page', pagina);
    if (tam) p.set('page_size', tam); else if (estado.tam !== 20) p.set('page_size', estado.tam);
    if (estado.orden) p.set('ordering', `${estado.orden},${C.pk}`); // el pk desempata: las páginas no repiten ni omiten filas
    if (estado.buscar) p.set('search', estado.buscar);
    Object.entries(estado.filtros).forEach(([k, v]) => v !== '' && p.set(k, v));
    return p;
  }
  const alerta = (icon, title, text) => Swal.fire({ icon, title, text, confirmButtonText: 'Entendido' });
  const aviso = (title) => Swal.fire({ toast: true, position: 'top-end', icon: 'success', title, showConfirmButton: false, timer: 2600, timerProgressBar: true });

  async function cargarDelegaciones() {
    const d = await traerTodo('/api/delegaciones/?estado=activa');
    OPC.delegaciones = d.map((x) => ({ v: String(x.id_delegacion), t: `${x.codigo} · ${x.nombre}` }));
  }
  async function cargarAreas() {
    const a = await traerTodo('/api/areas/?estado=activa');
    OPC.areas = a.map((x) => ({ v: String(x.id_area), t: `${x.nombre_texto} — ${x.delegacion_codigo} · ${x.delegacion_nombre}` }));
  }

  /* ---------------- Listado ---------------- */
  function pintarCabecera() {
    $('tituloPagina').textContent = C.titulo;
    $('subtituloPagina').textContent = C.subtitulo;
    $('txtNuevo').textContent = C.nuevo;
    $('capTabla').textContent = `Listado de ${C.titulo.toLowerCase()}`;
    $('cabeceraTabla').innerHTML = C.columnas.map((c) => c.orden
      ? `<th scope="col" data-orden="${c.orden}" aria-sort="none"><button type="button" class="orden" data-orden="${c.orden}">${c.t} <i class="bi bi-arrow-down-up" aria-hidden="true"></i></button></th>`
      : `<th scope="col">${c.t}</th>`).join('') + '<th scope="col" class="acciones">Acciones</th>';
    pintarOrden();
  }
  function pintarOrden() {
    document.querySelectorAll('th[data-orden]').forEach((th) => {
      const clave = th.dataset.orden;
      const asc = estado.orden === clave, desc = estado.orden === `-${clave}`;
      th.setAttribute('aria-sort', asc ? 'ascending' : desc ? 'descending' : 'none');
      th.querySelector('i').className = `bi ${asc ? 'bi-arrow-up' : desc ? 'bi-arrow-down' : 'bi-arrow-down-up'}`;
    });
  }
  function pintarFiltros() {
    $('filtrosExtra').innerHTML = C.filtros.map((f) => `
      <select data-filtro="${f.k}" aria-label="${f.t}">
        <option value="">${f.t}</option>
        ${f.opciones().map((o) => `<option value="${esc(o.v)}">${esc(o.t)}</option>`).join('')}
      </select>`).join('');
    document.querySelectorAll('[data-filtro]').forEach((s) => {
      s.value = estado.filtros[s.dataset.filtro] || '';
      s.addEventListener('change', () => { estado.filtros[s.dataset.filtro] = s.value; estado.pagina = 1; listar(); });
    });
  }
  function mostrarEstado(tipo, titulo, texto, reintentar) {
    const e = $('estado');
    const iconos = { carga: '<span class="giro" aria-hidden="true"></span>', vacio: '<i class="bi bi-inbox"></i>', sinres: '<i class="bi bi-search"></i>', error: '<i class="bi bi-exclamation-triangle"></i>' };
    e.innerHTML = `${iconos[tipo]}<strong>${titulo}</strong>${texto || ''}` + (reintentar ? '<button class="btn btn-borde" id="btnReintentar"><i class="bi bi-arrow-clockwise"></i> Reintentar</button>' : '');
    e.classList.add('visible');
    if (reintentar) $('btnReintentar').addEventListener('click', listar);
    const vacioNuevo = $('btnVacioNuevo');
    if (vacioNuevo) vacioNuevo.addEventListener('click', () => $('btnNuevo').click());
  }
  const ocultarEstado = () => $('estado').classList.remove('visible');

  let tokenListado = 0;
  async function listar() {
    const mio = ++tokenListado;
    estado.cargando = true;
    $('cuerpoTabla').innerHTML = '';
    $('paginador').innerHTML = ''; $('total').textContent = '';
    mostrarEstado('carga', 'Cargando…');
    sincronizarURL();
    try {
      const d = await api(`${C.url}?${parametros(estado.pagina)}`);
      if (mio !== tokenListado) return; // llegó una respuesta más nueva
      estado.total = d.count;
      if (d.count === 0) {
        const filtrado = estado.buscar || Object.values(estado.filtros).some(Boolean);
        filtrado
          ? mostrarEstado('sinres', 'Sin coincidencias', `<p>Ningún registro coincide con la búsqueda o los filtros aplicados.</p>`)
          : mostrarEstado('vacio', `Aún no hay ${C.titulo.toLowerCase()}`, `<p>Todavía no se ha creado ningún registro.</p><button type="button" class="btn btn-primario" id="btnVacioNuevo"><i class="bi bi-plus-lg"></i> ${C.nuevo}</button>`);
        $('total').textContent = '0 resultados';
        return;
      }
      ocultarEstado();
      $('cuerpoTabla').innerHTML = d.results.map(filaHTML).join('');
      d.results.forEach((r) => { registros[r[C.pk]] = r; });
      resaltar($('cuerpoTabla'), estado.buscar);
      const ini = (estado.pagina - 1) * estado.tam + 1;
      $('total').textContent = `Mostrando ${ini}–${ini + d.results.length - 1} de ${d.count} resultado${d.count === 1 ? '' : 's'}`;
      pintarPaginador(Math.ceil(d.count / estado.tam));
    } catch (e) {
      if (mio !== tokenListado) return;
      if (e.status === 404 && estado.pagina > 1) { estado.pagina = 1; return listar(); }
      const msg = e.status === 403 ? 'Su perfil no tiene permiso para ver este mantenedor.' : e.message;
      mostrarEstado('error', 'No se pudo cargar el listado', `<p>${esc(msg)}</p>`, e.status !== 403);
    } finally { if (mio === tokenListado) estado.cargando = false; }
  }
  function filaHTML(r) {
    const celdas = C.columnas.map((c) => {
      const v = c.html ? c.html(r) : (r[c.k] === '' || r[c.k] == null ? (c.vacio || '') : esc(r[c.k]));
      return `<td>${v}</td>`;
    }).join('');
    const id = r[C.pk];
    const activo = C.esActivo(r);
    return `<tr>${celdas}<td class="acciones">
      ${C.detalle ? `<button class="btn-accion" data-accion="detalle" data-id="${id}" aria-label="Ver áreas y cargos"><i class="bi bi-diagram-3"></i> Áreas</button>` : ''}
      <button class="btn-accion" data-accion="ver" data-id="${id}" aria-label="Consultar"><i class="bi bi-eye"></i> Ver</button>
      <button class="btn-accion" data-accion="editar" data-id="${id}" aria-label="Editar"><i class="bi bi-pencil"></i> Editar</button>
      ${activo ? `<button class="btn-accion peligro" data-accion="desactivar" data-id="${id}" aria-label="Desactivar"><i class="bi bi-slash-circle"></i> Desactivar</button>` : ''}
    </td></tr>`;
  }
  function pintarPaginador(paginas) {
    if (paginas <= 1) { $('paginador').innerHTML = ''; return; }
    const p = estado.pagina; const nums = new Set([1, paginas, p - 1, p, p + 1]);
    let html = `<button data-p="${p - 1}" ${p === 1 ? 'disabled' : ''} aria-label="Página anterior"><i class="bi bi-chevron-left"></i></button>`;
    let prev = 0;
    [...nums].filter((n) => n >= 1 && n <= paginas).sort((a, b) => a - b).forEach((n) => {
      if (n - prev > 1) html += '<button disabled>…</button>';
      html += `<button data-p="${n}" ${n === p ? 'aria-current="page"' : ''} aria-label="Página ${n}">${n}</button>`;
      prev = n;
    });
    html += `<button data-p="${p + 1}" ${p === paginas ? 'disabled' : ''} aria-label="Página siguiente"><i class="bi bi-chevron-right"></i></button>`;
    $('paginador').innerHTML = html;
  }
  // Los filtros y la página viven en la URL: al recargar o compartir el enlace se conservan.
  function sincronizarURL() {
    const p = parametros(estado.pagina > 1 ? estado.pagina : 0).toString();
    history.replaceState(null, '', p ? `?${p}` : location.pathname);
  }
  function leerURL() {
    const p = new URLSearchParams(location.search);
    estado.buscar = p.get('search') || '';
    estado.orden = p.get('ordering') ? p.get('ordering').split(',')[0] : '';
    estado.tam = [10, 20, 50].includes(Number(p.get('page_size'))) ? Number(p.get('page_size')) : 20;
    estado.nuevo = p.get('nuevo');
    $('tamPagina').value = String(estado.tam);
    estado.pagina = parseInt(p.get('page') || '1', 10) || 1;
    C.filtros.forEach((f) => { estado.filtros[f.k] = p.get(f.k) || ''; });
    $('buscar').value = estado.buscar;
  }

  /* ---------------- Formulario ---------------- */
  function campoHTML(f, valor, soloLectura) {
    const id = `f_${f.k}`;
    const dis = soloLectura ? 'disabled' : '';
    let control;
    if (f.tipo === 'select') {
      const opts = (f.vacio !== undefined ? [{ v: '', t: f.vacio }] : []).concat(f.opciones());
      control = `<select id="${id}" name="${f.k}" ${dis}>${opts.map((o) => `<option value="${esc(o.v)}" ${String(o.v) === String(valor) ? 'selected' : ''}>${esc(o.t)}</option>`).join('')}</select>`;
    } else if (f.tipo === 'textarea') {
      control = `<textarea id="${id}" name="${f.k}" rows="3" maxlength="${f.max || ''}" ${dis}>${esc(valor)}</textarea>`;
    } else {
      control = `<input id="${id}" name="${f.k}" type="${f.tipo || 'text'}" value="${esc(valor)}" ${f.max && !f.tipo ? `maxlength="${f.max}"` : ''} ${f.tipo === 'number' ? `min="${f.min}" max="${f.max}"` : ''} ${dis}>`;
    }
    return `<div class="campo ${f.ancho ? 'ancho' : ''}" data-campo="${f.k}">
      <label for="${id}">${f.t}${f.req ? ' <span class="oblig" aria-hidden="true">*</span><span class="sr">(obligatorio)</span>' : ''}</label>
      ${control}
      ${f.ayuda ? `<small class="ayuda">${f.ayuda}</small>` : ''}
      <span class="error" id="e_${f.k}" role="alert"></span>
    </div>`;
  }
  function valorInicial(f, reg, previo) {
    if (!reg && previo && previo[f.k] !== undefined) return previo[f.k];
    if (!reg) return f.defecto ?? '';
    const v = reg[f.k];
    if (v === null || v === undefined) return '';
    return typeof v === 'boolean' ? String(v) : v;
  }
  function abrirModal(modo, reg, previo) {
    disparador = document.activeElement; // al cerrar, el foco vuelve a este botón
    editando = { modo, reg }; sucio = false;
    const ro = modo === 'ver';
    $('modalTitulo').textContent = { crear: C.nuevo, editar: `Editar ${C.singular}`, ver: `Consultar ${C.singular}` }[modo];
    $('camposForm').innerHTML = C.campos.map((f) => campoHTML(f, valorInicial(f, reg, previo), ro)).join('');
    $('btnGuardar').style.display = ro ? 'none' : '';
    $('btnCancelar').textContent = ro ? 'Cerrar' : 'Cancelar';
    $('modal').hidden = false;
    const primero = $('camposForm').querySelector('input:not([disabled]), select:not([disabled]), textarea:not([disabled])');
    (primero || $('modalCerrar')).focus();
  }
  async function cerrarModal(forzar) {
    if (!forzar && sucio && editando && editando.modo !== 'ver') {
      const r = await Swal.fire({ icon: 'warning', title: '¿Descartar los cambios?', text: 'Tiene cambios sin guardar.', showCancelButton: true, confirmButtonText: 'Descartar', cancelButtonText: 'Seguir editando', reverseButtons: true });
      if (!r.isConfirmed) return;
    }
    $('modal').hidden = true; editando = null; sucio = false;
    devolverFoco();
  }
  function marcar(campo, mensaje) {
    const caja = document.querySelector(`[data-campo="${campo}"]`);
    if (!caja) return false;
    caja.classList.add('invalido'); $(`e_${campo}`).textContent = mensaje; return true;
  }
  function limpiarErrores() {
    document.querySelectorAll('.campo.invalido').forEach((c) => c.classList.remove('invalido'));
    document.querySelectorAll('.campo .error').forEach((e) => { e.textContent = ''; });
  }
  function recolectar() {
    const datos = {}; const fallos = [];
    C.campos.forEach((f) => {
      const el = $(`f_${f.k}`); let v = el.value.trim();
      if (f.req && v === '') { fallos.push([f.k, 'Este campo es obligatorio.']); return; }
      if (f.tipo === 'number' && v !== '') {
        const n = Number(v);
        if (!Number.isInteger(n) || n < f.min || n > f.max) { fallos.push([f.k, `Ingrese un número entero entre ${f.min} y ${f.max}.`]); return; }
        v = n;
      }
      if (f.bool) v = v === 'true';
      else if (f.nulo && v === '') v = null;
      else if (f.tipo === 'select' && v !== '' && /^\d+$/.test(v) && (f.k === 'delegacion' || f.k === 'area')) v = Number(v);
      datos[f.k] = v;
    });
    return { datos, fallos };
  }
  async function guardar(ev) {
    ev.preventDefault();
    if (!editando || editando.modo === 'ver' || $('btnGuardar').disabled) return; // evita doble envío
    limpiarErrores();
    const { datos, fallos } = recolectar();
    if (fallos.length) {
      fallos.forEach(([k, m]) => marcar(k, m));
      document.querySelector('.campo.invalido input, .campo.invalido select')?.focus();
      return alerta('warning', 'Revise el formulario', 'Hay campos obligatorios o con formato inválido.');
    }
    const crear = editando.modo === 'crear';
    if (!crear && C.dependientes && C.esActivo(editando.reg) && datos[C.campoEstado] === 'inactiva') {
      const r = await confirmarDesactivacion(editando.reg);
      if (!r.isConfirmed) return;
    }
    $('btnGuardar').disabled = true;
    try {
      const url = crear ? C.url : `${C.url}${editando.reg[C.pk]}/`;
      await api(url, { method: crear ? 'POST' : 'PATCH', body: JSON.stringify(datos) });
      sucio = false; await cerrarModal(true);
      aviso(crear ? `${cap(C.singular)} creada correctamente` : `${cap(C.singular)} actualizada correctamente`);
      if (C.cargarOpciones) await C.cargarOpciones();
      if (ENTIDAD === 'delegaciones') cargarDelegaciones();
      pintarFiltros(); listar();
    } catch (e) {
      const enCampo = e.campo && marcar(e.campo, e.message);
      alerta('error', enCampo ? 'Revise el formulario' : 'No se pudo guardar', e.message);
    } finally { $('btnGuardar').disabled = false; }
  }
  const cap = (s) => s.charAt(0).toUpperCase() + s.slice(1);

  function textoDependientes(reg) {
    if (!C.dependientes) return '';
    const d = C.dependientes(reg);
    const partes = [];
    if (d.areas) partes.push(`${d.areas} área${d.areas === 1 ? '' : 's'} activa${d.areas === 1 ? '' : 's'}`);
    if (d.cargos) partes.push(`${d.cargos} cargo${d.cargos === 1 ? '' : 's'} vigente${d.cargos === 1 ? '' : 's'}`);
    return partes.length
      ? `<div class="aviso-cascada"><strong>Se desactivarán también:</strong> ${partes.join(' y ')}. Reactivarlos después es manual, uno a uno.</div>`
      : '';
  }
  function confirmarDesactivacion(reg) {
    return Swal.fire({
      icon: 'warning', title: `¿Desactivar ${C.singular}?`,
      html: `<p>El registro no se borra: queda inactivo y conserva su historial.</p>${textoDependientes(reg || {})}`,
      showCancelButton: true, confirmButtonText: 'Sí, desactivar', cancelButtonText: 'Cancelar', reverseButtons: true,
    });
  }
  async function desactivar(id) {
    const r = await confirmarDesactivacion(registros[id]);
    if (!r.isConfirmed) return;
    try {
      await api(`${C.url}${id}/`, { method: 'DELETE' });
      aviso(`${cap(C.singular)} desactivada`);
      listar();
    } catch (e) { alerta('error', 'No se pudo desactivar', e.message); }
  }

  /* ---------------- Accesibilidad: foco ---------------- */
  const FOCALIZABLES = 'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';
  function atraparFoco(e, caja) {
    const lista = [...caja.querySelectorAll(FOCALIZABLES)].filter((el) => el.offsetParent !== null);
    if (!lista.length) return;
    const primero = lista[0], ultimo = lista[lista.length - 1];
    if (e.shiftKey && document.activeElement === primero) { e.preventDefault(); ultimo.focus(); }
    else if (!e.shiftKey && document.activeElement === ultimo) { e.preventDefault(); primero.focus(); }
    else if (!caja.contains(document.activeElement)) { e.preventDefault(); primero.focus(); }
  }
  function devolverFoco() {
    if (disparador && document.contains(disparador)) disparador.focus(); else $('btnNuevo').focus();
    disparador = null;
  }

  /* ---------------- Resaltar lo buscado ---------------- */
  function resaltar(raiz, texto) {
    if (!texto) return;
    const re = new RegExp(texto.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), 'gi');
    const recorrido = document.createTreeWalker(raiz, NodeFilter.SHOW_TEXT);
    const nodos = [];
    while (recorrido.nextNode()) nodos.push(recorrido.currentNode);
    nodos.forEach((nodo) => {
      if (!re.test(nodo.nodeValue)) return;
      re.lastIndex = 0;
      const frag = document.createDocumentFragment();
      let ultimo = 0, m;
      while ((m = re.exec(nodo.nodeValue)) !== null) {
        if (m[0] === '') { re.lastIndex++; continue; }
        frag.append(nodo.nodeValue.slice(ultimo, m.index));
        const marca = document.createElement('mark'); marca.className = 'coincidencia'; marca.textContent = m[0];
        frag.append(marca); ultimo = m.index + m[0].length;
      }
      frag.append(nodo.nodeValue.slice(ultimo));
      nodo.replaceWith(frag);
    });
  }

  /* ---------------- Detalle de la delegación (panel lateral) ---------------- */
  async function abrirDetalle(id, origen) {
    try {
      const d = await api(`${C.url}${id}/detalle/`);
      disparador = origen || document.activeElement;
      $('panelTitulo').textContent = `${d.codigo} · ${d.nombre}`;
      const dele = d.estado === 'activa';
      $('panelCuerpo').innerHTML = `
        <section><h3>Datos</h3><dl class="ficha">
          <dt>Código</dt><dd>${esc(d.codigo)}</dd>
          <dt>Dirección</dt><dd>${esc(d.direccion) || '—'}</dd>
          <dt>Comuna</dt><dd>${esc(d.comuna)}</dd>
          <dt>Estado</dt><dd>${etiquetaEstado(dele, 'Activa', 'Inactiva')}</dd>
        </dl></section>
        <section><h3>Áreas y cargos (${d.areas.length} área${d.areas.length === 1 ? '' : 's'})</h3>
          ${d.areas.map((a) => `
            <article class="area-detalle">
              <header><h3>${esc(a.nombre_texto)} · prioridad ${a.prioridad}</h3>${etiquetaEstado(a.estado === 'activa', 'Activa', 'Inactiva')}</header>
              ${a.cargos.length
                ? `<ul>${a.cargos.map((c) => `<li>${esc(c.nombre)} ${c.vigente ? '' : '<em>(no vigente)</em>'}</li>`).join('')}</ul>`
                : '<p class="sin-cargos">Sin cargos registrados.</p>'}
              <div class="enlaces">
                <a href="/organizacion/cargos/?area=${a.id_area}">Ver sus cargos</a>
                ${a.estado === 'activa' ? `<a href="/organizacion/cargos/?nuevo=${a.id_area}">Nuevo cargo en esta área</a>` : ''}
              </div>
            </article>`).join('')}
          <div class="enlaces"><a href="/organizacion/areas/?delegacion=${d.id_delegacion}">Ver todas sus áreas en el listado</a></div>
        </section>`;
      $('panelFondo').hidden = false;
      $('panelCerrar').focus();
    } catch (err) { alerta('error', 'No se pudo abrir el detalle', err.message); }
  }
  function cerrarDetalle() { $('panelFondo').hidden = true; devolverFoco(); }

  /* ---------------- Exportar a Excel ---------------- */
  async function exportar() {
    if (typeof XLSX === 'undefined') return alerta('error', 'No se pudo exportar', 'No se cargó la librería de Excel. Revise su conexión e intente de nuevo.');
    if (estado.total === 0) return alerta('info', 'Nada que exportar', 'El filtro actual no tiene resultados.');
    const btn = $('btnExcel'); btn.disabled = true;
    Swal.fire({ title: 'Generando archivo…', allowOutsideClick: false, didOpen: () => Swal.showLoading() });
    try {
      const filas = await traerTodo(`${C.url}?${parametros(0, 100)}`); // todas las páginas del filtro, de a 100
      const hoja = filas.map((r) => Object.fromEntries(C.columnas.map((c) => [c.t, c.excel ? c.excel(r) : (r[c.k] ?? '')])));
      const libro = XLSX.utils.book_new();
      XLSX.utils.book_append_sheet(libro, XLSX.utils.json_to_sheet(hoja), C.titulo);
      XLSX.writeFile(libro, `${C.archivo}_${new Date().toISOString().slice(0, 10)}.xlsx`);
      Swal.close(); aviso(`${filas.length} registro${filas.length === 1 ? '' : 's'} exportado${filas.length === 1 ? '' : 's'}`);
    } catch (e) { alerta('error', 'No se pudo exportar', e.message); } finally { btn.disabled = false; }
  }

  /* ---------------- Eventos ---------------- */
  let temporizador;
  $('buscar').addEventListener('input', (e) => {
    clearTimeout(temporizador);
    temporizador = setTimeout(() => { estado.buscar = e.target.value.trim(); estado.pagina = 1; listar(); }, 300);
  });
  $('btnLimpiar').addEventListener('click', () => {
    estado.buscar = ''; estado.filtros = {}; estado.pagina = 1; $('buscar').value = '';
    document.querySelectorAll('[data-filtro]').forEach((s) => { s.value = ''; });
    listar();
  });
  $('paginador').addEventListener('click', (e) => {
    const b = e.target.closest('button[data-p]'); if (!b || b.disabled) return;
    estado.pagina = Number(b.dataset.p); listar(); window.scrollTo({ top: 0, behavior: 'smooth' });
  });
  $('cabeceraTabla').addEventListener('click', (e) => {
    const b = e.target.closest('button[data-orden]'); if (!b) return;
    const clave = b.dataset.orden;
    estado.orden = estado.orden === clave ? `-${clave}` : estado.orden === `-${clave}` ? '' : clave;
    estado.pagina = 1; pintarOrden(); listar();
  });
  $('tamPagina').addEventListener('change', (e) => { estado.tam = Number(e.target.value); estado.pagina = 1; listar(); });
  $('cuerpoTabla').addEventListener('click', async (e) => {
    const b = e.target.closest('button[data-accion]'); if (!b) return;
    const id = b.dataset.id;
    if (b.dataset.accion === 'desactivar') return desactivar(id);
    if (b.dataset.accion === 'detalle') return abrirDetalle(id, b);
    try {
      const reg = await api(`${C.url}${id}/`);
      if (C.cargarOpciones) await C.cargarOpciones();
      abrirModal(b.dataset.accion === 'ver' ? 'ver' : 'editar', reg);
    } catch (err) { alerta('error', 'No se pudo abrir el registro', err.message); }
  });
  $('btnNuevo').addEventListener('click', async () => {
    try { if (C.cargarOpciones) await C.cargarOpciones(); abrirModal('crear', null); }
    catch (err) { alerta('error', 'No se pudieron cargar las opciones', err.message); }
  });
  $('btnExcel').addEventListener('click', exportar);
  $('formulario').addEventListener('submit', guardar);
  $('formulario').addEventListener('input', () => { sucio = true; });
  $('btnCancelar').addEventListener('click', () => cerrarModal(false));
  $('modalCerrar').addEventListener('click', () => cerrarModal(false));
  $('modal').addEventListener('mousedown', (e) => { if (e.target === $('modal')) cerrarModal(false); });
  document.addEventListener('keydown', (e) => {
    if (Swal.isVisible()) return;
    if (e.key === 'Escape') {
      if (!$('panelFondo').hidden) return cerrarDetalle();
      if (!$('modal').hidden) return cerrarModal(false);
    }
    if (e.key === 'Tab') {
      const caja = !$('modal').hidden ? $('modal') : !$('panelFondo').hidden ? $('panelDetalle') : null;
      if (caja) atraparFoco(e, caja);
    }
    // Atajo: «/» lleva al buscador (si no se está escribiendo ya en otro campo)
    if (e.key === '/' && !e.target.closest('input, textarea, select') && $('modal').hidden && $('panelFondo').hidden) {
      e.preventDefault(); $('buscar').focus();
    }
  });
  $('panelCerrar').addEventListener('click', cerrarDetalle);
  $('panelFondo').addEventListener('mousedown', (e) => { if (e.target === $('panelFondo')) cerrarDetalle(); });

  /* ---------------- Inicio ---------------- */
  (async function iniciar() {
    pintarCabecera();
    leerURL();
    try { if (C.cargarOpciones) await C.cargarOpciones(); } catch (e) { /* el listado mostrará el error */ }
    pintarFiltros();
    listar();
    if (ENTIDAD === 'cargos' && estado.nuevo && /^\d+$/.test(estado.nuevo)) {
      abrirModal('crear', null, { area: estado.nuevo });
    }
  })();
})();
