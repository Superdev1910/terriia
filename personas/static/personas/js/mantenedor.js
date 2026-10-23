/* Motor de los mantenedores de personas (usuarios y funcionarios).
   Habla con la API REST (/api/...) con la sesión de Django; los permisos y las reglas
   de negocio (RUT, email único, clave segura) se validan en el servidor, esta pantalla
   solo los presenta. Sigue el mismo diseño que los mantenedores de organización. */
(function () {
  'use strict';

  const leerJSON = (id) => {
    const el = document.getElementById(id);
    return el ? JSON.parse(el.textContent) : null;
  };
  const ENTIDAD = leerJSON('entidad');
  // Los roles vienen en la página (pantallas.py): todavía no hay /api/roles/.
  const ROLES = (leerJSON('roles') || []).map((r) => ({ v: String(r.id_rol), t: r.nombre }));
  const ID_USUARIO_ACTUAL = leerJSON('idUsuarioActual');

  const ESTADOS = [{ v: 'activo', t: 'Activo' }, { v: 'inactivo', t: 'Inactivo' }];
  const etiquetaEstado = (r) => r.estado === 'activo'
    ? '<span class="etiqueta ok"><i class="bi bi-check-circle-fill"></i> Activo</span>'
    : '<span class="etiqueta no"><i class="bi bi-dash-circle"></i> Inactivo</span>';
  const textoEstado = (r) => (r.estado === 'activo' ? 'Activo' : 'Inactivo');
  // HU19: un usuario sin delegación tiene acceso global.
  const textoDelegacion = (r) => (r.delegacion ? `${r.delegacion_codigo} · ${r.delegacion_nombre}` : 'Global');
  const htmlDelegacion = (r) => (r.delegacion
    ? `<span class="codigo">${esc(r.delegacion_codigo)}</span> ${esc(r.delegacion_nombre)}`
    : '<span class="etiqueta info"><i class="bi bi-globe2"></i> Global</span>');
  const nombreCompleto = (r) => `${r.first_name || ''} ${r.last_name || ''}`.trim();

  /* ---------------- Configuración por mantenedor ---------------- */
  const CONFIG = {
    usuarios: {
      titulo: 'Usuarios', singular: 'usuario', nuevo: 'Nuevo usuario',
      subtitulo: 'Cuentas de acceso al sistema. Un usuario sin delegación tiene acceso global.',
      url: '/api/usuarios/', pk: 'id_usuario', archivo: 'usuarios',
      columnas: [
        { k: 'email', orden: 'email', t: 'Email' },
        { k: 'rut', orden: 'rut', t: 'RUT' },
        { k: 'nombre', orden: 'first_name', t: 'Nombre', valor: nombreCompleto, vacio: '—' },
        { k: 'rol_nombre', orden: 'rol__nombre', t: 'Rol' },
        { k: 'delegacion', orden: 'delegacion__codigo', t: 'Delegación', html: htmlDelegacion, excel: textoDelegacion },
        { k: 'estado', orden: 'estado', t: 'Estado', html: etiquetaEstado, excel: textoEstado },
      ],
      campos: [
        { k: 'email', t: 'Email', tipo: 'email', req: true, max: 150, ancho: true },
        { k: 'rut', t: 'RUT', req: true, max: 12, ayuda: 'Con dígito verificador. Ej.: 12.345.678-5' },
        { k: 'rol', t: 'Rol', tipo: 'select', req: true, fk: true, opciones: () => ROLES, vacio: 'Seleccione un rol' },
        { k: 'first_name', t: 'Nombres', max: 150 },
        { k: 'last_name', t: 'Apellidos', max: 150 },
        {
          k: 'delegacion', t: 'Delegación', tipo: 'select', ancho: true, fk: true, nulo: true,
          opciones: () => OPC.delegaciones, vacio: 'Global (todas las delegaciones)', actual: textoDelegacion,
          ayuda: 'Déjela en «Global» para la alcaldesa o el administrador: ven todas las delegaciones.',
        },
        {
          k: 'funcionario', t: 'Funcionario', tipo: 'select', ancho: true, fk: true, nulo: true,
          opciones: () => OPC.funcionarios, vacio: 'Sin ficha de funcionario', actual: (r) => r.funcionario_nombre,
          ayuda: 'Ficha de funcionario municipal asociada a la cuenta (opcional).',
        },
        {
          k: 'password', t: 'Clave inicial', tipo: 'password', req: true, soloCrear: true, ancho: true,
          ayuda: 'Mínimo 8 caracteres. No puede ser solo números, muy común ni parecida al email o al nombre.',
        },
        { k: 'estado', t: 'Estado', tipo: 'select', opciones: () => ESTADOS, defecto: 'activo' },
      ],
      filtros: [
        { k: 'rol', t: 'Todos los roles', opciones: () => ROLES },
        { k: 'delegacion', t: 'Todas las delegaciones', opciones: () => OPC.delegaciones },
        { k: 'estado', t: 'Todos los estados', opciones: () => ESTADOS },
      ],
      // Su propia cuenta no se ofrece para desactivar: quedaría sin acceso.
      puedeDesactivar: (r) => r.id_usuario !== ID_USUARIO_ACTUAL,
      cargarOpciones: () => Promise.all([cargarDelegaciones(), cargarFuncionarios()]),
    },

    funcionarios: {
      titulo: 'Funcionarios', singular: 'funcionario', nuevo: 'Nuevo funcionario',
      subtitulo: 'Fichas de los funcionarios municipales, con su cargo y su delegación.',
      url: '/api/funcionarios/', pk: 'id_funcionario', archivo: 'funcionarios',
      columnas: [
        { k: 'identificador_inst', orden: 'identificador_inst', t: 'Identificador institucional', html: (r) => `<span class="codigo">${esc(r.identificador_inst)}</span>` },
        { k: 'nombre', orden: 'nombre', t: 'Nombre' },
        { k: 'cargo_nombre', orden: 'cargo__nombre', t: 'Cargo' },
        { k: 'delegacion', orden: 'delegacion__codigo', t: 'Delegación', html: htmlDelegacion, excel: textoDelegacion },
        { k: 'estado', orden: 'estado', t: 'Estado', html: etiquetaEstado, excel: textoEstado },
      ],
      campos: [
        { k: 'identificador_inst', t: 'Identificador institucional', req: true, max: 30, ayuda: 'Código único del funcionario. Ej.: F-0001' },
        { k: 'estado', t: 'Estado', tipo: 'select', opciones: () => ESTADOS, defecto: 'activo' },
        { k: 'nombre', t: 'Nombre completo', req: true, max: 150, ancho: true },
        { k: 'cargo', t: 'Cargo', tipo: 'select', req: true, ancho: true, fk: true, opciones: () => OPC.cargos, vacio: 'Seleccione un cargo', actual: (r) => r.cargo_nombre },
        { k: 'delegacion', t: 'Delegación', tipo: 'select', req: true, ancho: true, fk: true, opciones: () => OPC.delegaciones, vacio: 'Seleccione una delegación', actual: textoDelegacion },
      ],
      filtros: [
        { k: 'delegacion', t: 'Todas las delegaciones', opciones: () => OPC.delegaciones },
        { k: 'cargo', t: 'Todos los cargos', opciones: () => OPC.cargos },
        { k: 'estado', t: 'Todos los estados', opciones: () => ESTADOS },
      ],
      puedeDesactivar: () => true,
      cargarOpciones: () => Promise.all([cargarDelegaciones(), cargarCargos()]),
    },
  };

  const C = CONFIG[ENTIDAD];
  const OPC = { delegaciones: [], funcionarios: [], cargos: [] };
  const estado = { pagina: 1, tam: 20, orden: '', buscar: '', filtros: {}, total: 0 };
  let disparador = null; // elemento que abrió el formulario, para devolverle el foco
  let editando = null; // {modo, reg}
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
  const cap = (s) => s.charAt(0).toUpperCase() + s.slice(1);
  const alerta = (icon, title, text) => Swal.fire({ icon, title, text, confirmButtonText: 'Entendido' });
  const aviso = (title) => Swal.fire({ toast: true, position: 'top-end', icon: 'success', title, showConfirmButton: false, timer: 2600, timerProgressBar: true });

  async function cargarDelegaciones() {
    const d = await traerTodo('/api/delegaciones/?estado=activa&page_size=100');
    OPC.delegaciones = d.map((x) => ({ v: String(x.id_delegacion), t: `${x.codigo} · ${x.nombre}` }));
  }
  async function cargarFuncionarios() {
    const f = await traerTodo('/api/funcionarios/?estado=activo&page_size=100');
    OPC.funcionarios = f.map((x) => ({ v: String(x.id_funcionario), t: `${x.identificador_inst} · ${x.nombre}` }));
  }
  async function cargarCargos() {
    const c = await traerTodo('/api/cargos/?vigente=true&page_size=100');
    OPC.cargos = c.map((x) => ({ v: String(x.id_cargo), t: `${x.nombre} — ${x.area_texto}` }));
  }

  /* ---------------- Listado ---------------- */
  function pintarCabecera() {
    $('tituloPagina').textContent = C.titulo;
    $('subtituloPagina').textContent = C.subtitulo;
    $('txtNuevo').textContent = C.nuevo;
    $('capTabla').textContent = `Listado de ${C.titulo.toLowerCase()}`;
    $('cabeceraTabla').innerHTML = C.columnas.map((c) => `<th scope="col" data-orden="${c.orden}" aria-sort="none"><button type="button" class="orden" data-orden="${c.orden}">${c.t} <i class="bi bi-arrow-down-up" aria-hidden="true"></i></button></th>`).join('')
      + '<th scope="col" class="acciones">Acciones</th>';
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
          ? mostrarEstado('sinres', 'Sin coincidencias', '<p>Ningún registro coincide con la búsqueda o los filtros aplicados.</p>')
          : mostrarEstado('vacio', `Aún no hay ${C.titulo.toLowerCase()}`, `<p>Todavía no se ha creado ningún registro.</p><button type="button" class="btn btn-primario" id="btnVacioNuevo"><i class="bi bi-plus-lg"></i> ${C.nuevo}</button>`);
        $('total').textContent = '0 resultados';
        return;
      }
      ocultarEstado();
      $('cuerpoTabla').innerHTML = d.results.map(filaHTML).join('');
      const ini = (estado.pagina - 1) * estado.tam + 1;
      $('total').textContent = `Mostrando ${ini}–${ini + d.results.length - 1} de ${d.count} resultado${d.count === 1 ? '' : 's'}`;
      pintarPaginador(Math.ceil(d.count / estado.tam));
    } catch (e) {
      if (mio !== tokenListado) return;
      if (e.status === 404 && estado.pagina > 1) { estado.pagina = 1; return listar(); }
      const msg = e.status === 403 ? 'Su perfil no tiene permiso para ver este mantenedor.' : e.message;
      mostrarEstado('error', 'No se pudo cargar el listado', `<p>${esc(msg)}</p>`, e.status !== 403);
    }
  }
  const valorColumna = (c, r) => (c.valor ? c.valor(r) : r[c.k]);
  function filaHTML(r) {
    const celdas = C.columnas.map((c) => {
      const v = valorColumna(c, r);
      return `<td>${c.html ? c.html(r) : (v === '' || v == null ? (c.vacio || '') : esc(v))}</td>`;
    }).join('');
    const id = r[C.pk];
    const desactivable = r.estado === 'activo' && C.puedeDesactivar(r);
    return `<tr>${celdas}<td class="acciones">
      <button class="btn-accion" data-accion="ver" data-id="${id}" aria-label="Consultar"><i class="bi bi-eye"></i> Ver</button>
      <button class="btn-accion" data-accion="editar" data-id="${id}" aria-label="Editar"><i class="bi bi-pencil"></i> Editar</button>
      ${desactivable ? `<button class="btn-accion peligro" data-accion="desactivar" data-id="${id}" aria-label="Desactivar"><i class="bi bi-slash-circle"></i> Desactivar</button>` : ''}
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
  // Los filtros, el orden y la página viven en la URL: al recargar o compartir el enlace se conservan.
  function sincronizarURL() {
    const p = parametros(estado.pagina > 1 ? estado.pagina : 0).toString();
    history.replaceState(null, '', p ? `?${p}` : location.pathname);
  }
  function leerURL() {
    const p = new URLSearchParams(location.search);
    estado.buscar = p.get('search') || '';
    estado.orden = p.get('ordering') ? p.get('ordering').split(',')[0] : '';
    estado.tam = [10, 20, 50].includes(Number(p.get('page_size'))) ? Number(p.get('page_size')) : 20;
    estado.pagina = parseInt(p.get('page') || '1', 10) || 1;
    C.filtros.forEach((f) => { estado.filtros[f.k] = p.get(f.k) || ''; });
    $('tamPagina').value = String(estado.tam);
    $('buscar').value = estado.buscar;
  }

  /* ---------------- Formulario ---------------- */
  function campoHTML(f, valor, reg, soloLectura) {
    const id = `f_${f.k}`;
    const dis = soloLectura ? 'disabled' : '';
    let control;
    if (f.tipo === 'select') {
      const opts = (f.vacio !== undefined ? [{ v: '', t: f.vacio }] : []).concat(f.opciones());
      // Al editar, la opción guardada puede estar inactiva y no venir en la lista: se agrega igual.
      if (reg && f.actual && valor !== '' && !opts.some((o) => String(o.v) === String(valor))) {
        opts.push({ v: String(valor), t: `${f.actual(reg)} (inactivo)` });
      }
      control = `<select id="${id}" name="${f.k}" ${dis}>${opts.map((o) => `<option value="${esc(o.v)}" ${String(o.v) === String(valor) ? 'selected' : ''}>${esc(o.t)}</option>`).join('')}</select>`;
    } else {
      const extra = f.tipo === 'password' ? 'autocomplete="new-password"' : '';
      control = `<input id="${id}" name="${f.k}" type="${f.tipo || 'text'}" value="${esc(valor)}" ${f.max ? `maxlength="${f.max}"` : ''} ${extra} ${dis}>`;
    }
    return `<div class="campo ${f.ancho ? 'ancho' : ''}" data-campo="${f.k}">
      <label for="${id}">${f.t}${f.req ? ' <span class="oblig" aria-hidden="true">*</span><span class="sr">(obligatorio)</span>' : ''}</label>
      ${control}
      ${f.ayuda && !soloLectura ? `<small class="ayuda">${f.ayuda}</small>` : ''}
      <span class="error" id="e_${f.k}" role="alert"></span>
    </div>`;
  }
  function valorInicial(f, reg) {
    if (!reg) return f.defecto ?? '';
    const v = reg[f.k];
    return v === null || v === undefined ? '' : v;
  }
  // La clave inicial solo se pide al crear; después cada usuario la cambia desde su sesión.
  const camposDe = (modo) => C.campos.filter((f) => modo === 'crear' || !f.soloCrear);
  function abrirModal(modo, reg) {
    disparador = document.activeElement; // al cerrar, el foco vuelve a este botón
    editando = { modo, reg }; sucio = false;
    const ro = modo === 'ver';
    $('modalTitulo').textContent = { crear: C.nuevo, editar: `Editar ${C.singular}`, ver: `Consultar ${C.singular}` }[modo];
    $('camposForm').innerHTML = camposDe(modo).map((f) => campoHTML(f, valorInicial(f, reg), reg, ro)).join('');
    $('btnGuardar').style.display = ro ? 'none' : '';
    $('btnCancelar').textContent = ro ? 'Cerrar' : 'Cancelar';
    $('modal').hidden = false;
    const primero = $('camposForm').querySelector('input:not([disabled]), select:not([disabled])');
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
  function recolectar(modo) {
    const datos = {}; const fallos = [];
    camposDe(modo).forEach((f) => {
      const el = $(`f_${f.k}`);
      let v = f.tipo === 'password' ? el.value : el.value.trim(); // la clave no se recorta
      if (f.req && v === '') { fallos.push([f.k, 'Este campo es obligatorio.']); return; }
      if (f.tipo === 'email' && v !== '' && !el.checkValidity()) { fallos.push([f.k, 'Ingrese un email válido.']); return; }
      if (f.nulo && v === '') v = null;
      else if (f.fk && v !== '') v = Number(v);
      datos[f.k] = v;
    });
    return { datos, fallos };
  }
  async function guardar(ev) {
    ev.preventDefault();
    if (!editando || editando.modo === 'ver' || $('btnGuardar').disabled) return; // evita doble envío
    limpiarErrores();
    const crear = editando.modo === 'crear';
    const { datos, fallos } = recolectar(editando.modo);
    if (fallos.length) {
      fallos.forEach(([k, m]) => marcar(k, m));
      document.querySelector('.campo.invalido input, .campo.invalido select')?.focus();
      return alerta('warning', 'Revise el formulario', 'Hay campos obligatorios o con formato inválido.');
    }
    $('btnGuardar').disabled = true;
    try {
      const url = crear ? C.url : `${C.url}${editando.reg[C.pk]}/`;
      await api(url, { method: crear ? 'POST' : 'PATCH', body: JSON.stringify(datos) });
      sucio = false; await cerrarModal(true);
      aviso(crear ? `${cap(C.singular)} creado correctamente` : `${cap(C.singular)} actualizado correctamente`);
      listar();
    } catch (e) {
      const enCampo = e.campo && marcar(e.campo, e.message);
      alerta('error', enCampo ? 'Revise el formulario' : 'No se pudo guardar', e.message);
    } finally { $('btnGuardar').disabled = false; }
  }

  async function desactivar(id) {
    const r = await Swal.fire({
      icon: 'warning', title: `¿Desactivar ${C.singular}?`,
      html: ENTIDAD === 'usuarios'
        ? '<p>El usuario no se borra: queda inactivo, ya no puede iniciar sesión y conserva su historial.</p>'
        : '<p>El funcionario no se borra: queda inactivo y conserva su historial.</p>',
      showCancelButton: true, confirmButtonText: 'Sí, desactivar', cancelButtonText: 'Cancelar', reverseButtons: true,
    });
    if (!r.isConfirmed) return;
    try {
      await api(`${C.url}${id}/`, { method: 'DELETE' });
      aviso(`${cap(C.singular)} desactivado`);
      listar();
    } catch (e) { alerta('error', 'No se pudo desactivar', e.message); }
  }

  /* ---------------- Accesibilidad: foco ---------------- */
  const FOCALIZABLES = 'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), [tabindex]:not([tabindex="-1"])';
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

  /* ---------------- Exportar a Excel ---------------- */
  async function exportar() {
    if (typeof XLSX === 'undefined') return alerta('error', 'No se pudo exportar', 'No se cargó la librería de Excel. Revise su conexión e intente de nuevo.');
    if (estado.total === 0) return alerta('info', 'Nada que exportar', 'El filtro actual no tiene resultados.');
    const btn = $('btnExcel'); btn.disabled = true;
    Swal.fire({ title: 'Generando archivo…', allowOutsideClick: false, didOpen: () => Swal.showLoading() });
    try {
      const filas = await traerTodo(`${C.url}?${parametros(0, 100)}`); // todas las páginas del filtro, de a 100
      const hoja = filas.map((r) => Object.fromEntries(C.columnas.map((c) => [c.t, c.excel ? c.excel(r) : (valorColumna(c, r) ?? '')])));
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
    try {
      const reg = await api(`${C.url}${id}/`);
      await C.cargarOpciones();
      abrirModal(b.dataset.accion === 'ver' ? 'ver' : 'editar', reg);
    } catch (err) { alerta('error', 'No se pudo abrir el registro', err.message); }
  });
  $('btnNuevo').addEventListener('click', async () => {
    try { await C.cargarOpciones(); abrirModal('crear', null); }
    catch (err) { alerta('error', 'No se pudieron cargar las opciones', err.message); }
  });
  $('btnExcel').addEventListener('click', exportar);
  $('formulario').addEventListener('submit', guardar);
  $('formulario').addEventListener('input', () => { sucio = true; });
  $('btnCancelar').addEventListener('click', () => cerrarModal(false));
  $('modalCerrar').addEventListener('click', () => cerrarModal(false));
  $('modal').addEventListener('mousedown', (e) => { if (e.target === $('modal')) cerrarModal(false); });
  document.addEventListener('keydown', (e) => {
    if (Swal.isVisible() || $('modal').hidden) return;
    if (e.key === 'Escape') cerrarModal(false);
    if (e.key === 'Tab') atraparFoco(e, $('modal'));
  });

  /* ---------------- Inicio ---------------- */
  (async function iniciar() {
    pintarCabecera();
    leerURL();
    pintarOrden();
    try { await C.cargarOpciones(); } catch (e) { /* el listado mostrará el error */ }
    pintarFiltros();
    listar();
  })();
})();
