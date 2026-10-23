/* Motor común de los mantenedores de metas (períodos, ítems, metas por delegación y metas
   individuales). Sigue el de organización: habla con la API REST (/api/...) con la sesión de
   Django; los permisos y las reglas de negocio se validan en el servidor, esta pantalla solo
   los presenta. */
(function () {
  'use strict';

  const ENTIDAD = JSON.parse(document.getElementById('entidad').textContent);
  const TAM = 20; // filas por página (PAGE_SIZE de la API)

  const ESTADOS_PERIODO = [{ v: 'vigente', t: 'Vigente' }, { v: 'cerrado', t: 'Cerrado' }];
  const TIPOS_META = [{ v: 'conteo', t: 'Conteo' }, { v: 'porcentaje', t: 'Porcentaje' }];
  const SI_NO = [{ v: 'true', t: 'Sí' }, { v: 'false', t: 'No' }];
  const ACTIVO = [{ v: 'true', t: 'Activo' }, { v: 'false', t: 'Inactivo' }];

  const etiquetaEstado = (activo, si, no) => activo
    ? `<span class="etiqueta ok"><i class="bi bi-check-circle-fill"></i> ${si}</span>`
    : `<span class="etiqueta no"><i class="bi bi-dash-circle"></i> ${no}</span>`;
  const textoAlerta = (texto) => `<span class="texto-alerta"><i class="bi bi-exclamation-triangle-fill" aria-hidden="true"></i> ${esc(texto)}</span>`;

  /* ---------------- Formatos ---------------- */
  const num = (v) => (v === null || v === undefined || v === '' ? '' : Number(v).toLocaleString('es-CL', { minimumFractionDigits: 2, maximumFractionDigits: 2 }));
  const valor = (v, tipo) => (num(v) === '' ? '' : `${num(v)}${tipo === 'porcentaje' ? ' %' : ''}`);
  const fecha = (v) => (v ? v.split('-').reverse().join('-') : ''); // 2026-01-31 → 31-01-2026
  const fechaHora = (v) => (v ? new Date(v).toLocaleString('es-CL') : '');
  const tipoTexto = (v) => (TIPOS_META.find((t) => t.v === v) || { t: v }).t;
  const redondear = (n) => Math.round(n * 100) / 100;

  /* ---------------- Datos de apoyo (para los select y para mostrar nombres) ---------------- */
  const FUENTES = {
    cargos: { url: '/api/cargos/?page_size=100', pk: 'id_cargo' },
    delegaciones: { url: '/api/delegaciones/?page_size=100', pk: 'id_delegacion' },
    periodos: { url: '/api/periodos/', pk: 'id_periodo' },
    items: { url: '/api/items/', pk: 'id_item' },
    metasDelegacion: { url: '/api/metas-delegacion/', pk: 'id_meta_delegacion' },
    funcionarios: { url: '/api/funcionarios/', pk: 'id_funcionario' },
  };
  const REF = {}; // REF.cargos = { lista: [...], id: { 3: {...} } }
  async function cargar(...nombres) {
    await Promise.all(nombres.map(async (n) => {
      const lista = await traerTodo(FUENTES[n].url);
      REF[n] = { lista, id: Object.fromEntries(lista.map((x) => [x[FUENTES[n].pk], x])) };
    }));
  }
  const ref = (n, id) => (REF[n] && REF[n].id[id]) || null;
  const lista = (n) => (REF[n] ? REF[n].lista : []);

  const txtCargo = (id) => { const c = ref('cargos', id); return c ? `${c.nombre} — ${c.area_texto}` : `Cargo ${id}`; };
  const htmlCargo = (id) => { const c = ref('cargos', id); return c ? `${esc(c.nombre)}<br><small>${esc(c.area_texto)}</small>` : esc(txtCargo(id)); };
  const txtDelegacion = (id) => { const d = ref('delegaciones', id); return d ? `${d.codigo} · ${d.nombre}` : `Delegación ${id}`; };
  const txtPeriodo = (id) => {
    const p = ref('periodos', id);
    return p ? `${fecha(p.fecha_inicio)} a ${fecha(p.fecha_termino)}${p.estado === 'vigente' ? ' (vigente)' : ''}` : `Período ${id}`;
  };
  const htmlPeriodo = (id) => {
    const p = ref('periodos', id);
    return p
      ? `<span class="sin-corte">${fecha(p.fecha_inicio)}</span> a <span class="sin-corte">${fecha(p.fecha_termino)}</span>${p.estado === 'vigente' ? '<br><small>vigente</small>' : ''}`
      : esc(txtPeriodo(id));
  };
  const txtMetaDelegacion = (id) => {
    const m = ref('metasDelegacion', id);
    return m ? `${m.item_nombre} · ${txtDelegacion(m.delegacion)} · ${txtPeriodo(m.periodo)}` : `Meta de delegación ${id}`;
  };
  const txtFuncionario = (id) => { const f = ref('funcionarios', id); return f ? `${f.identificador_inst} · ${f.nombre}` : `Funcionario ${id}`; };
  const tipoDeMeta = (r) => (ref('metasDelegacion', r.meta_delegacion) || {}).tipo_meta;

  // Opciones de los select. «actual» mantiene visible el valor guardado aunque ya esté inactivo.
  const opcCargos = (actual, todos) => lista('cargos').filter((c) => todos || c.vigente || c.id_cargo === actual)
    .map((c) => ({ v: String(c.id_cargo), t: txtCargo(c.id_cargo) }));
  const opcDelegaciones = (actual, todas) => lista('delegaciones').filter((d) => todas || d.estado === 'activa' || d.id_delegacion === actual)
    .map((d) => ({ v: String(d.id_delegacion), t: txtDelegacion(d.id_delegacion) }));
  const opcPeriodos = () => lista('periodos').map((p) => ({ v: String(p.id_periodo), t: txtPeriodo(p.id_periodo) }));
  const opcItems = (actual) => lista('items').filter((i) => i.activo || i.id_item === actual)
    .map((i) => ({ v: String(i.id_item), t: `${i.nombre} · ${txtCargo(i.cargo)} (${tipoTexto(i.tipo_meta)})` }));
  const opcMetasDelegacion = (conSaldo) => lista('metasDelegacion').map((m) => ({
    v: String(m.id_meta_delegacion),
    t: txtMetaDelegacion(m.id_meta_delegacion) + (conSaldo ? ` · saldo ${valor(m.saldo_por_asignar, m.tipo_meta)}` : ''),
  }));
  const periodoVigente = () => { const p = lista('periodos').find((x) => x.estado === 'vigente'); return p ? String(p.id_periodo) : ''; };

  /* ---------------- Ponderadores por cargo (ítems) ---------------- */
  let sumas = {}; // id_cargo → suma de los ponderadores de sus ítems activos
  async function cargarSumas() {
    const activos = await traerTodo('/api/items/?activo=true');
    sumas = {};
    activos.forEach((i) => { sumas[i.cargo] = redondear((sumas[i.cargo] || 0) + Number(i.ponderador)); });
  }
  function advertenciaCargo(idCargo) {
    const suma = sumas[idCargo] || 0;
    return suma === 100 ? null : `Los ponderadores del cargo ${txtCargo(idCargo)} suman ${num(suma)} %, no 100 %.`;
  }

  /* ---------------- Configuración por mantenedor ---------------- */
  const CONFIG = {
    periodos: {
      titulo: 'Períodos', singular: 'período', nuevo: 'Nuevo período', masculino: true,
      subtitulo: 'Solo puede haber un período vigente a la vez. Un período no se borra: se cierra y conserva su historial.',
      buscar: 'Buscar por versión de parámetros…',
      url: '/api/periodos/', pk: 'id_periodo', archivo: 'periodos',
      esActivo: (r) => r.estado === 'vigente',
      desactivar: { boton: 'Cerrar', titulo: '¿Cerrar el período?', texto: 'El período queda cerrado y conserva su historial.', hecho: 'Período cerrado' },
      columnas: [
        { k: 'fecha_inicio', orden: 'fecha_inicio', t: 'Inicio', html: (r) => fecha(r.fecha_inicio), excel: (r) => fecha(r.fecha_inicio) },
        { k: 'fecha_termino', orden: 'fecha_termino', t: 'Término', html: (r) => fecha(r.fecha_termino), excel: (r) => fecha(r.fecha_termino) },
        { k: 'dias_computables', orden: 'dias_computables', t: 'Días computables', vacio: '—' },
        { k: 'version_parametros', orden: 'version_parametros', t: 'Versión de parámetros', vacio: '—' },
        { k: 'estado', orden: 'estado', t: 'Estado', html: (r) => etiquetaEstado(r.estado === 'vigente', 'Vigente', 'Cerrado'), excel: (r) => (r.estado === 'vigente' ? 'Vigente' : 'Cerrado') },
      ],
      campos: [
        { k: 'fecha_inicio', t: 'Fecha de inicio', tipo: 'date', req: true },
        { k: 'fecha_termino', t: 'Fecha de término', tipo: 'date', req: true },
        { k: 'dias_computables', t: 'Días computables', tipo: 'number', entero: true, min: 1, nulo: true, msj: 'Ingrese un número entero mayor a cero.' },
        { k: 'version_parametros', t: 'Versión de parámetros', max: 20, nulo: true, ayuda: 'Opcional. Ej.: v1.0' },
        { k: 'estado', t: 'Estado', tipo: 'select', opciones: () => ESTADOS_PERIODO, defecto: 'vigente', ancho: true, ayuda: 'Solo un período puede estar vigente: cierre el anterior antes de abrir uno nuevo.' },
      ],
      filtros: [{ k: 'estado', t: 'Todos los estados', opciones: () => ESTADOS_PERIODO }],
      validar: (d) => (d.fecha_inicio && d.fecha_termino && d.fecha_termino <= d.fecha_inicio
        ? [['fecha_termino', 'La fecha de término debe ser posterior a la fecha de inicio.']] : []),
    },

    items: {
      titulo: 'Ítems', singular: 'ítem', nuevo: 'Nuevo ítem', masculino: true,
      subtitulo: 'Cada ítem pertenece a un cargo. Los ponderadores de los ítems activos de un cargo deben sumar 100 %.',
      buscar: 'Buscar por nombre o tipo…',
      url: '/api/items/', pk: 'id_item', archivo: 'items',
      esActivo: (r) => r.activo === true,
      desactivar: { boton: 'Desactivar', titulo: '¿Desactivar el ítem?', texto: 'El ítem no se borra: queda inactivo y deja de contar en los ponderadores de su cargo.', hecho: 'Ítem desactivado' },
      columnas: [
        { k: 'cargo', orden: 'cargo', t: 'Cargo', html: (r) => htmlCargo(r.cargo), excel: (r) => txtCargo(r.cargo) },
        { k: 'nombre', orden: 'nombre', t: 'Ítem' },
        { k: 'tipo_meta', orden: 'tipo_meta', t: 'Tipo', html: (r) => `<span class="etiqueta info">${tipoTexto(r.tipo_meta)}</span>`, excel: (r) => tipoTexto(r.tipo_meta) },
        { k: 'ponderador', orden: 'ponderador', t: 'Ponderador', html: (r) => `${num(r.ponderador)} %`, excel: (r) => Number(r.ponderador) },
        {
          k: 'requiere_verificacion_previa', orden: 'requiere_verificacion_previa', t: 'Verificación previa',
          html: (r) => (r.requiere_verificacion_previa ? `Sí<br><small>radio ${r.radio_tolerancia_metros ?? '—'} m</small>` : 'No'),
          excel: (r) => (r.requiere_verificacion_previa ? 'Sí' : 'No'),
        },
        { k: 'radio_tolerancia_metros', t: 'Radio de tolerancia (m)', soloExcel: true, excel: (r) => r.radio_tolerancia_metros ?? '' },
        {
          k: 'suma_cargo', t: 'Suma del cargo',
          html: (r) => (advertenciaCargo(r.cargo) ? textoAlerta(`${num(sumas[r.cargo] || 0)} %`) : `<span class="etiqueta ok"><i class="bi bi-check-circle-fill"></i> 100 %</span>`),
          excel: (r) => sumas[r.cargo] || 0,
        },
        { k: 'activo', orden: 'activo', t: 'Estado', html: (r) => etiquetaEstado(r.activo, 'Activo', 'Inactivo'), excel: (r) => (r.activo ? 'Activo' : 'Inactivo') },
      ],
      campos: [
        { k: 'cargo', t: 'Cargo', tipo: 'select', req: true, ancho: true, id: true, opciones: (reg) => opcCargos(reg && reg.cargo), vacio: 'Seleccione un cargo' },
        { k: 'nombre', t: 'Nombre del ítem', req: true, max: 150, ancho: true },
        { k: 'tipo_meta', t: 'Tipo de meta', tipo: 'select', req: true, opciones: () => TIPOS_META, defecto: 'conteo', ayuda: 'Conteo: una cantidad. Porcentaje: hasta 100 %.' },
        { k: 'ponderador', t: 'Ponderador (%)', tipo: 'number', req: true, min: 0.01, max: 100, msj: 'Ingrese un número mayor a 0 y hasta 100 (máximo 2 decimales).' },
        { k: 'requiere_verificacion_previa', t: '¿Requiere verificación previa?', tipo: 'select', bool: true, opciones: () => SI_NO, defecto: 'false' },
        { k: 'radio_tolerancia_metros', t: 'Radio de tolerancia (metros)', tipo: 'number', entero: true, min: 1, nulo: true, reqSi: 'requiere_verificacion_previa', msj: 'Ingrese un número entero de metros mayor a cero.', ayuda: 'Obligatorio solo si requiere verificación previa.' },
        { k: 'activo', t: 'Estado', tipo: 'select', bool: true, opciones: () => ACTIVO, defecto: 'true' },
      ],
      filtros: [
        { k: 'cargo', t: 'Todos los cargos', opciones: () => opcCargos(null, true) },
        { k: 'tipo_meta', t: 'Todos los tipos', opciones: () => TIPOS_META },
        { k: 'activo', t: 'Todos los estados', opciones: () => ACTIVO },
      ],
      cargarOpciones: () => Promise.all([cargar('cargos'), cargarSumas()]),
      requisitos: () => (opcCargos().length ? null : 'Primero debe registrarse un cargo vigente en Organización › Cargos.'),
      avisos: () => Object.keys(sumas).map(advertenciaCargo).filter(Boolean),
      trasGuardar: (r) => advertenciaCargo(r.cargo),
      alCambiar: { cargo: ayudaPonderador },
      validar: (d) => (d.requiere_verificacion_previa && !d.radio_tolerancia_metros
        ? [['radio_tolerancia_metros', 'Si requiere verificación previa, el radio de tolerancia es obligatorio.']] : []),
    },

    'metas-delegacion': {
      titulo: 'Metas por delegación', singular: 'meta por delegación', nuevo: 'Nueva meta por delegación', masculino: false,
      subtitulo: 'Meta total de cada ítem por delegación y período. Después se reparte entre los funcionarios en «Metas individuales».',
      buscar: 'Buscar por ítem o delegación…',
      url: '/api/metas-delegacion/', pk: 'id_meta_delegacion', archivo: 'metas_delegacion',
      columnas: [
        { k: 'item', orden: 'item', t: 'Ítem', html: (r) => `${esc(r.item_nombre)}<br><small>${esc(r.cargo_nombre)} · ${tipoTexto(r.tipo_meta)}</small>`, excel: (r) => r.item_nombre },
        { k: 'delegacion', orden: 'delegacion', t: 'Delegación', html: (r) => esc(txtDelegacion(r.delegacion)), excel: (r) => txtDelegacion(r.delegacion) },
        { k: 'periodo', orden: 'periodo', t: 'Período', html: (r) => htmlPeriodo(r.periodo), excel: (r) => txtPeriodo(r.periodo) },
        { k: 'valor_objetivo_total', orden: 'valor_objetivo_total', t: 'Valor objetivo total', html: (r) => valor(r.valor_objetivo_total, r.tipo_meta), excel: (r) => Number(r.valor_objetivo_total) },
        { k: 'suma_metas', orden: 'suma_anotada', t: 'Suma asignada', html: (r) => valor(r.suma_metas, r.tipo_meta), excel: (r) => Number(r.suma_metas) },
        { k: 'saldo_por_asignar', t: 'Saldo por asignar', html: (r) => valor(r.saldo_por_asignar, r.tipo_meta), excel: (r) => Number(r.saldo_por_asignar) },
        { k: 'advertencia', t: 'Advertencia', html: (r) => (r.advertencia ? textoAlerta(r.advertencia) : '—'), excel: (r) => r.advertencia || '' },
      ],
      campos: [
        { k: 'item', t: 'Ítem', tipo: 'select', req: true, ancho: true, id: true, fijo: true, opciones: (reg) => opcItems(reg && reg.item), vacio: 'Seleccione un ítem' },
        { k: 'delegacion', t: 'Delegación', tipo: 'select', req: true, ancho: true, id: true, fijo: true, opciones: (reg) => opcDelegaciones(reg && reg.delegacion), vacio: 'Seleccione una delegación' },
        { k: 'periodo', t: 'Período', tipo: 'select', req: true, id: true, fijo: true, opciones: () => opcPeriodos(), vacio: 'Seleccione un período', defecto: periodoVigente },
        { k: 'valor_objetivo_total', t: 'Valor objetivo total', tipo: 'number', req: true, min: 0.01, msj: 'Ingrese un número mayor a cero (máximo 2 decimales).', ayuda: 'En un ítem de porcentaje, hasta 100.' },
      ],
      filtros: [
        { k: 'periodo', t: 'Todos los períodos', opciones: () => opcPeriodos() },
        { k: 'delegacion', t: 'Todas las delegaciones', opciones: () => opcDelegaciones(null, true) },
        { k: 'item__cargo', t: 'Todos los cargos', opciones: () => opcCargos(null, true) },
      ],
      cargarOpciones: () => cargar('items', 'delegaciones', 'periodos', 'cargos'),
      requisitos: () => (!opcItems().length ? 'Primero debe registrarse un ítem activo en «Ítems».'
        : !opcDelegaciones().length ? 'Primero debe registrarse una delegación activa.'
          : !opcPeriodos().length ? 'Primero debe registrarse un período en «Períodos».' : null),
      trasGuardar: (r) => r.advertencia,
      extraAcciones: (r) => `<a class="btn-accion" href="/metas/metas-individuales/?meta_delegacion=${r.id_meta_delegacion}" aria-label="Ver sus metas individuales"><i class="bi bi-people"></i> Individuales</a>`,
    },

    metas: {
      titulo: 'Metas individuales', singular: 'meta individual', nuevo: 'Nueva meta individual', masculino: false,
      subtitulo: 'Reparte la meta de la delegación entre sus funcionarios. El valor solo cambia con «Recalibrar», que guarda el motivo en el historial.',
      buscar: 'Buscar por nombre o identificador del funcionario…',
      url: '/api/metas/', pk: 'id_meta', archivo: 'metas_individuales',
      columnas: [
        { k: 'meta_delegacion', orden: 'meta_delegacion', t: 'Meta de delegación', html: (r) => esc(txtMetaDelegacion(r.meta_delegacion)), excel: (r) => txtMetaDelegacion(r.meta_delegacion) },
        { k: 'funcionario', orden: 'funcionario', t: 'Funcionario', html: (r) => esc(txtFuncionario(r.funcionario)), excel: (r) => txtFuncionario(r.funcionario) },
        { k: 'valor_objetivo', orden: 'valor_objetivo', t: 'Valor objetivo', html: (r) => valor(r.valor_objetivo, tipoDeMeta(r)), excel: (r) => Number(r.valor_objetivo) },
        { k: 'unidad', orden: 'unidad', t: 'Unidad', vacio: '—' },
      ],
      campos: [
        { k: 'meta_delegacion', t: 'Meta de delegación', tipo: 'select', req: true, ancho: true, id: true, fijo: true, opciones: () => opcMetasDelegacion(true), vacio: 'Seleccione una meta de delegación' },
        { k: 'funcionario', t: 'Funcionario', tipo: 'select', req: true, ancho: true, id: true, fijo: true, opciones: (reg) => (reg ? [{ v: String(reg.funcionario), t: txtFuncionario(reg.funcionario) }] : []), vacio: 'Primero elija la meta de delegación', ayuda: 'Solo funcionarios activos de la delegación de la meta y sin meta en ella.' },
        { k: 'valor_objetivo', t: 'Valor objetivo', tipo: 'number', req: true, min: 0.01, fijo: true, msj: 'Ingrese un número mayor a cero (máximo 2 decimales).', ayudaFijo: 'Para cambiarlo use «Recalibrar».' },
        { k: 'unidad', t: 'Unidad', max: 20, nulo: true, ayuda: 'Opcional. Ej.: visitas, casos.' },
      ],
      filtros: [
        { k: 'meta_delegacion__periodo', t: 'Todos los períodos', opciones: () => opcPeriodos() },
        { k: 'meta_delegacion__delegacion', t: 'Todas las delegaciones', opciones: () => opcDelegaciones(null, true) },
        { k: 'meta_delegacion', t: 'Todas las metas de delegación', opciones: () => opcMetasDelegacion(false) },
      ],
      cargarOpciones: () => cargar('metasDelegacion', 'delegaciones', 'periodos', 'funcionarios'),
      requisitos: () => (lista('metasDelegacion').length ? null : 'Primero debe registrarse una meta en «Metas por delegación».'),
      previo: () => ({ meta_delegacion: estado.filtros.meta_delegacion }), // «Nueva» parte con la meta filtrada
      alCambiar: { meta_delegacion: elegirMetaDelegacion },
      extraAcciones: (r) => `
        <button class="btn-accion" data-accion="recalibrar" data-id="${r.id_meta}" aria-label="Recalibrar"><i class="bi bi-sliders"></i> Recalibrar</button>
        <button class="btn-accion" data-accion="historial" data-id="${r.id_meta}" aria-label="Historial de recalibraciones"><i class="bi bi-clock-history"></i> Historial</button>`,
      acciones: { recalibrar, historial },
    },
  };

  const C = CONFIG[ENTIDAD];
  const columnasTabla = C.columnas.filter((c) => !c.soloExcel); // las «soloExcel» van solo al archivo
  const estado ={ pagina: 1, orden: '', buscar: '', filtros: {}, total: 0 };
  const registros = {}; // registros de la página visible, por id
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
  function parametros(pagina) {
    const p = new URLSearchParams();
    if (pagina) p.set('page', pagina);
    if (estado.orden) p.set('ordering', `${estado.orden},${C.pk}`); // el pk desempata: las páginas no repiten ni omiten filas
    if (estado.buscar) p.set('search', estado.buscar);
    Object.entries(estado.filtros).forEach(([k, v]) => v && p.set(k, v));
    return p;
  }
  const alerta = (icon, title, text) => Swal.fire({ icon, title, text, confirmButtonText: 'Entendido' });
  const aviso = (title) => Swal.fire({ toast: true, position: 'top-end', icon: 'success', title, showConfirmButton: false, timer: 2600, timerProgressBar: true });
  const cap = (s) => s.charAt(0).toUpperCase() + s.slice(1);
  const participio = (base) => `${base}${C.masculino ? 'o' : 'a'}`; // creado / creada

  /* ---------------- Listado ---------------- */
  function pintarCabecera() {
    $('tituloPagina').textContent = C.titulo;
    $('subtituloPagina').textContent = C.subtitulo;
    $('txtNuevo').textContent = C.nuevo;
    $('buscar').placeholder = C.buscar;
    $('capTabla').textContent = `Listado de ${C.titulo.toLowerCase()}`;
    $('cabeceraTabla').innerHTML = columnasTabla.map((c) => (c.orden
      ? `<th scope="col" data-orden="${c.orden}" aria-sort="none"><button type="button" class="orden" data-orden="${c.orden}">${c.t} <i class="bi bi-arrow-down-up" aria-hidden="true"></i></button></th>`
      : `<th scope="col">${c.t}</th>`)).join('') + '<th scope="col" class="acciones">Acciones</th>';
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
  function pintarAvisos() {
    const avisos = C.avisos ? C.avisos() : [];
    $('avisos').innerHTML = avisos.map((t) => `<div class="aviso-cascada"><i class="bi bi-exclamation-triangle-fill" aria-hidden="true"></i> ${esc(t)}</div>`).join('');
    $('avisos').hidden = !avisos.length;
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
    pintarAvisos();
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
      d.results.forEach((r) => { registros[r[C.pk]] = r; });
      resaltar($('cuerpoTabla'), estado.buscar);
      const ini = (estado.pagina - 1) * TAM + 1;
      $('total').textContent = `Mostrando ${ini}–${ini + d.results.length - 1} de ${d.count} resultado${d.count === 1 ? '' : 's'}`;
      pintarPaginador(Math.ceil(d.count / TAM));
    } catch (e) {
      if (mio !== tokenListado) return;
      if (e.status === 404 && estado.pagina > 1) { estado.pagina = 1; return listar(); }
      const msg = e.status === 403 ? 'Su perfil no tiene permiso para ver este mantenedor.' : e.message;
      mostrarEstado('error', 'No se pudo cargar el listado', `<p>${esc(msg)}</p>`, e.status !== 403);
    }
  }
  function filaHTML(r) {
    const celdas = columnasTabla.map((c) => {
      const v = c.html ? c.html(r) : (r[c.k] === '' || r[c.k] == null ? (c.vacio || '') : esc(r[c.k]));
      return `<td>${v}</td>`;
    }).join('');
    const id = r[C.pk];
    return `<tr>${celdas}<td class="acciones">
      <button class="btn-accion" data-accion="ver" data-id="${id}" aria-label="Consultar"><i class="bi bi-eye"></i> Ver</button>
      <button class="btn-accion" data-accion="editar" data-id="${id}" aria-label="Editar"><i class="bi bi-pencil"></i> Editar</button>
      ${C.extraAcciones ? C.extraAcciones(r) : ''}
      ${C.desactivar && C.esActivo(r) ? `<button class="btn-accion peligro" data-accion="desactivar" data-id="${id}" aria-label="${C.desactivar.boton}"><i class="bi bi-slash-circle"></i> ${C.desactivar.boton}</button>` : ''}
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
    estado.pagina = parseInt(p.get('page') || '1', 10) || 1;
    C.filtros.forEach((f) => { estado.filtros[f.k] = p.get(f.k) || ''; });
    $('buscar').value = estado.buscar;
  }

  /* ---------------- Formulario ---------------- */
  const bloqueado = (f) => editando.modo === 'ver' || (editando.modo === 'editar' && f.fijo);
  function campoHTML(f, valorCampo) {
    const id = `f_${f.k}`;
    const dis = bloqueado(f) ? 'disabled' : '';
    let control;
    if (f.tipo === 'select') {
      const opts = (f.vacio !== undefined ? [{ v: '', t: f.vacio }] : []).concat(f.opciones(editando.reg));
      control = `<select id="${id}" name="${f.k}" ${dis}>${opts.map((o) => `<option value="${esc(o.v)}" ${String(o.v) === String(valorCampo) ? 'selected' : ''}>${esc(o.t)}</option>`).join('')}</select>`;
    } else if (f.tipo === 'number') {
      control = `<input id="${id}" name="${f.k}" type="number" inputmode="decimal" value="${esc(valorCampo)}" step="${f.entero ? 1 : 0.01}" ${f.min !== undefined ? `min="${f.min}"` : ''} ${f.max !== undefined ? `max="${f.max}"` : ''} ${dis}>`;
    } else {
      control = `<input id="${id}" name="${f.k}" type="${f.tipo || 'text'}" value="${esc(valorCampo)}" ${f.max ? `maxlength="${f.max}"` : ''} ${dis}>`;
    }
    const ayuda = editando.modo === 'editar' && f.fijo ? (f.ayudaFijo || 'No se puede cambiar una vez creado el registro.') : f.ayuda;
    const oblig = f.req || f.reqSi
      ? ` <span class="oblig" id="o_${f.k}" aria-hidden="true">*</span><span class="sr">(obligatorio${f.reqSi ? ' en este caso' : ''})</span>` : '';
    return `<div class="campo ${f.ancho ? 'ancho' : ''}" data-campo="${f.k}">
      <label for="${id}">${f.t}${oblig}</label>
      ${control}
      <small class="ayuda" id="a_${f.k}">${ayuda || ''}</small>
      <span class="error" id="e_${f.k}" role="alert"></span>
    </div>`;
  }
  function valorInicial(f, reg, previo) {
    if (!reg && previo && previo[f.k]) return previo[f.k];
    if (!reg) return (typeof f.defecto === 'function' ? f.defecto() : f.defecto) ?? '';
    const v = reg[f.k];
    if (v === null || v === undefined) return '';
    return typeof v === 'boolean' ? String(v) : v;
  }
  const esRequerido = (f) => f.req || (f.reqSi && $(`f_${f.reqSi}`).value === 'true');
  function actualizarDinamicos(origen) {
    C.campos.filter((f) => f.reqSi).forEach((f) => { $(`o_${f.k}`).hidden = !esRequerido(f); });
    Object.entries(C.alCambiar || {}).forEach(([k, fn]) => { if (!origen || origen === k) fn(); });
  }
  function abrirModal(modo, reg, previo) {
    disparador = document.activeElement; // al cerrar, el foco vuelve a este botón
    editando = { modo, reg }; sucio = false;
    const ro = modo === 'ver';
    $('modalTitulo').textContent = { crear: C.nuevo, editar: `Editar ${C.singular}`, ver: `Consultar ${C.singular}` }[modo];
    $('camposForm').innerHTML = C.campos.map((f) => campoHTML(f, valorInicial(f, reg, previo))).join('');
    $('btnGuardar').style.display = ro ? 'none' : '';
    $('btnCancelar').textContent = ro ? 'Cerrar' : 'Cancelar';
    $('modal').hidden = false;
    actualizarDinamicos();
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
      if (bloqueado(f)) return; // lo fijo no se envía al editar
      let v = $(`f_${f.k}`).value.trim();
      if (v === '' && esRequerido(f)) { fallos.push([f.k, 'Este campo es obligatorio.']); return; }
      if (f.tipo === 'number' && v !== '') {
        const n = Number(v);
        const formato = f.entero ? /^\d+$/ : /^\d+(\.\d{1,2})?$/;
        if (!formato.test(v) || (f.min !== undefined && n < f.min) || (f.max !== undefined && n > f.max)) { fallos.push([f.k, f.msj]); return; }
        if (f.entero) v = n; // los decimales viajan como texto: la API los guarda exactos
      }
      if (f.bool) v = v === 'true';
      else if (f.nulo && v === '') v = null;
      else if (f.id && v !== '') v = Number(v);
      datos[f.k] = v;
    });
    if (C.validar && !fallos.length) fallos.push(...C.validar(datos));
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
    $('btnGuardar').disabled = true;
    try {
      const url = crear ? C.url : `${C.url}${editando.reg[C.pk]}/`;
      const resp = await api(url, { method: crear ? 'POST' : 'PATCH', body: JSON.stringify(datos) });
      sucio = false; await cerrarModal(true);
      if (C.cargarOpciones) await C.cargarOpciones();
      const hecho = `${cap(C.singular)} ${participio(crear ? 'cread' : 'actualizad')} correctamente`;
      const advertencia = C.trasGuardar && C.trasGuardar(resp);
      if (advertencia) Swal.fire({ icon: 'warning', title: hecho, text: `Atención: ${advertencia}`, confirmButtonText: 'Entendido' });
      else aviso(hecho);
      pintarFiltros(); listar();
    } catch (e) {
      const enCampo = e.campo && marcar(e.campo, e.message);
      alerta('error', enCampo ? 'Revise el formulario' : 'No se pudo guardar', e.message);
    } finally { $('btnGuardar').disabled = false; }
  }
  async function desactivar(id) {
    const r = await Swal.fire({
      icon: 'warning', title: C.desactivar.titulo, text: C.desactivar.texto,
      showCancelButton: true, confirmButtonText: `Sí, ${C.desactivar.boton.toLowerCase()}`, cancelButtonText: 'Cancelar', reverseButtons: true,
    });
    if (!r.isConfirmed) return;
    try {
      await api(`${C.url}${id}/`, { method: 'DELETE' });
      if (C.cargarOpciones) await C.cargarOpciones();
      aviso(C.desactivar.hecho);
      listar();
    } catch (e) { alerta('error', 'No se pudo completar', e.message); }
  }

  /* ---------------- Ítems: cuánto queda del 100 % del cargo ---------------- */
  function ayudaPonderador() {
    const cargo = Number($('f_cargo').value);
    const caja = $('a_ponderador');
    if (!cargo) { caja.textContent = 'Mayor a 0 y hasta 100.'; return; }
    let suma = sumas[cargo] || 0;
    const reg = editando.reg;
    if (reg && reg.activo && reg.cargo === cargo) suma = redondear(suma - Number(reg.ponderador)); // sin contar este mismo ítem
    caja.textContent = `Los otros ítems activos del cargo suman ${num(suma)} %: quedan ${num(redondear(100 - suma))} % disponibles.`;
  }

  /* ---------------- Metas individuales: funcionarios de la delegación y saldo ---------------- */
  let tokenFuncionarios = 0;
  async function elegirMetaDelegacion() {
    const md = ref('metasDelegacion', $('f_meta_delegacion').value);
    $('a_valor_objetivo').textContent = editando.modo === 'editar'
      ? 'Para cambiarlo use «Recalibrar».'
      : md ? `Saldo por asignar en la meta de la delegación: ${valor(md.saldo_por_asignar, md.tipo_meta)}.` : '';
    if (editando.modo !== 'crear') return; // al editar o consultar el funcionario no cambia
    const select = $('f_funcionario');
    const llenar = (vacio, opciones = []) => {
      select.innerHTML = `<option value="">${esc(vacio)}</option>` + opciones.map((f) => `<option value="${f.id_funcionario}">${esc(`${f.identificador_inst} · ${f.nombre}`)}</option>`).join('');
    };
    if (!md) { llenar('Primero elija la meta de delegación'); return; }
    const mio = ++tokenFuncionarios;
    llenar('Cargando funcionarios…');
    try {
      const [funcionarios, asignadas] = await Promise.all([
        traerTodo(`/api/funcionarios/?delegacion=${md.delegacion}&estado=activo`),
        traerTodo(`/api/metas/?meta_delegacion=${md.id_meta_delegacion}`),
      ]);
      if (mio !== tokenFuncionarios || !editando) return;
      const ocupados = new Set(asignadas.map((m) => m.funcionario));
      const libres = funcionarios.filter((f) => !ocupados.has(f.id_funcionario));
      llenar(libres.length ? 'Seleccione un funcionario' : 'No hay funcionarios activos sin meta en esta delegación', libres);
    } catch (e) {
      if (mio === tokenFuncionarios) llenar('No se pudieron cargar los funcionarios');
    }
  }

  async function recalibrar(id) {
    let meta;
    try { meta = await api(`/api/metas/${id}/`); } catch (e) { return alerta('error', 'No se pudo abrir la meta', e.message); }
    const tipo = tipoDeMeta(meta);
    const r = await Swal.fire({
      title: 'Recalibrar meta',
      html: `<div class="swal-campos">
          <p>${esc(txtFuncionario(meta.funcionario))}<br><small>${esc(txtMetaDelegacion(meta.meta_delegacion))}</small></p>
          <p>Valor actual: <strong>${valor(meta.valor_objetivo, tipo)}</strong></p>
          <label for="recValor"><span>Nuevo valor objetivo <span class="oblig">*</span></span>
            <input id="recValor" type="number" inputmode="decimal" min="0.01" step="0.01" ${tipo === 'porcentaje' ? 'max="100"' : ''}></label>
          <label for="recMotivo"><span>Motivo del ajuste <span class="oblig">*</span></span>
            <textarea id="recMotivo" rows="3" maxlength="255"></textarea></label>
          <small>El total de la meta de la delegación cambia en la misma diferencia. El ajuste queda en el historial.</small>
        </div>`,
      focusConfirm: false, showCancelButton: true, reverseButtons: true,
      confirmButtonText: 'Recalibrar', cancelButtonText: 'Cancelar',
      showLoaderOnConfirm: true, allowOutsideClick: () => !Swal.isLoading(),
      didOpen: () => $('recValor').focus(),
      preConfirm: async () => {
        const nuevo = $('recValor').value.trim();
        const motivo = $('recMotivo').value.trim();
        if (!/^\d+(\.\d{1,2})?$/.test(nuevo) || Number(nuevo) <= 0) { Swal.showValidationMessage('Ingrese un nuevo valor mayor a cero (máximo 2 decimales).'); return false; }
        if (Number(nuevo) === Number(meta.valor_objetivo)) { Swal.showValidationMessage('El nuevo valor es igual al valor actual.'); return false; }
        if (!motivo) { Swal.showValidationMessage('El motivo del ajuste es obligatorio.'); return false; }
        try {
          return await api(`/api/metas/${id}/recalibrar/`, { method: 'POST', body: JSON.stringify({ valor_objetivo_nuevo: nuevo, motivo }) });
        } catch (e) { Swal.showValidationMessage(e.message); return false; }
      },
    });
    if (!r.isConfirmed) return;
    aviso('Meta recalibrada correctamente');
    await C.cargarOpciones(); // cambió el total de la meta de la delegación
    pintarFiltros(); listar();
  }

  async function historial(id) {
    try {
      const [meta, filas] = await Promise.all([api(`/api/metas/${id}/`), traerTodo(`/api/recalibraciones-meta/?meta=${id}`)]);
      const tipo = tipoDeMeta(meta);
      const tabla = filas.length
        ? `<table class="tabla-historial"><caption class="sr">Recalibraciones de la meta</caption>
            <thead><tr><th scope="col">Fecha</th><th scope="col">Anterior</th><th scope="col">Nuevo</th><th scope="col">Motivo</th><th scope="col">Usuario</th></tr></thead>
            <tbody>${filas.map((h) => `<tr><td>${esc(fechaHora(h.fecha))}</td><td>${valor(h.valor_objetivo_anterior, tipo) || '—'}</td><td>${valor(h.valor_objetivo_nuevo, tipo)}</td><td>${esc(h.motivo)}</td><td>${esc(h.usuario_email)}</td></tr>`).join('')}</tbody></table>`
        : '<p>Esta meta aún no tiene recalibraciones.</p>';
      Swal.fire({
        title: 'Historial de recalibraciones', width: 860, confirmButtonText: 'Cerrar',
        html: `<p>${esc(txtFuncionario(meta.funcionario))} · valor actual <strong>${valor(meta.valor_objetivo, tipo)}</strong></p>${tabla}`,
      });
    } catch (e) { alerta('error', 'No se pudo cargar el historial', e.message); }
  }

  /* ---------------- Accesibilidad: foco ---------------- */
  const FOCALIZABLES = 'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';
  function atraparFoco(e, caja) {
    const focos = [...caja.querySelectorAll(FOCALIZABLES)].filter((el) => el.offsetParent !== null);
    if (!focos.length) return;
    const primero = focos[0], ultimo = focos[focos.length - 1];
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

  /* ---------------- Exportar a Excel ---------------- */
  async function exportar() {
    if (typeof XLSX === 'undefined') return alerta('error', 'No se pudo exportar', 'No se cargó la librería de Excel. Revise su conexión e intente de nuevo.');
    if (estado.total === 0) return alerta('info', 'Nada que exportar', 'El filtro actual no tiene resultados.');
    const btn = $('btnExcel'); btn.disabled = true;
    Swal.fire({ title: 'Generando archivo…', allowOutsideClick: false, didOpen: () => Swal.showLoading() });
    try {
      const filas = await traerTodo(`${C.url}?${parametros(0)}`); // todas las páginas del filtro actual
      const hoja = filas.map((r) => Object.fromEntries(C.columnas.map((c) => [c.t, c.excel ? c.excel(r) : (r[c.k] ?? '')])));
      const libro = XLSX.utils.book_new();
      XLSX.utils.book_append_sheet(libro, XLSX.utils.json_to_sheet(hoja), C.titulo.slice(0, 31));
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
  $('cuerpoTabla').addEventListener('click', async (e) => {
    const b = e.target.closest('button[data-accion]'); if (!b) return;
    const { accion, id } = b.dataset;
    if (accion === 'desactivar') return desactivar(id);
    if (C.acciones && C.acciones[accion]) return C.acciones[accion](id);
    try {
      const reg = await api(`${C.url}${id}/`);
      if (C.cargarOpciones) await C.cargarOpciones();
      abrirModal(accion === 'ver' ? 'ver' : 'editar', reg);
    } catch (err) { alerta('error', 'No se pudo abrir el registro', err.message); }
  });
  $('btnNuevo').addEventListener('click', async () => {
    try {
      if (C.cargarOpciones) await C.cargarOpciones();
      const falta = C.requisitos && C.requisitos();
      if (falta) return alerta('info', 'Faltan datos previos', falta);
      abrirModal('crear', null, C.previo && C.previo());
    } catch (err) { alerta('error', 'No se pudieron cargar las opciones', err.message); }
  });
  $('btnExcel').addEventListener('click', exportar);
  $('formulario').addEventListener('submit', guardar);
  $('formulario').addEventListener('input', () => { sucio = true; });
  $('formulario').addEventListener('change', (e) => { if (editando && e.target.name) actualizarDinamicos(e.target.name); });
  $('btnCancelar').addEventListener('click', () => cerrarModal(false));
  $('modalCerrar').addEventListener('click', () => cerrarModal(false));
  $('modal').addEventListener('mousedown', (e) => { if (e.target === $('modal')) cerrarModal(false); });
  document.addEventListener('keydown', (e) => {
    if (Swal.isVisible()) return;
    if (e.key === 'Escape' && !$('modal').hidden) return cerrarModal(false);
    if (e.key === 'Tab' && !$('modal').hidden) atraparFoco(e, $('modal'));
    // Atajo: «/» lleva al buscador (si no se está escribiendo ya en otro campo)
    if (e.key === '/' && !e.target.closest('input, textarea, select') && $('modal').hidden) {
      e.preventDefault(); $('buscar').focus();
    }
  });

  /* ---------------- Inicio ---------------- */
  (async function iniciar() {
    pintarCabecera();
    leerURL();
    try { if (C.cargarOpciones) await C.cargarOpciones(); } catch (e) { /* el listado mostrará el error */ }
    pintarFiltros();
    listar();
  })();
})();
