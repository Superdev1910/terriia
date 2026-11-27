/* Seguimiento de actividades (Épica 2): asignar (HU02), cambiar estado (HU03), evidencia (HU04),
   motivo de atraso (HU05), fecha de compromiso con historial (HU06), vencidas resaltadas (HU07)
   y comentarios (HU08). Habla con /api/actividades/ y /api/evidencias/ con la sesión de Django.
   Los permisos y las reglas (transiciones, motivo obligatorio, alcance por delegación) se validan
   en el servidor; aquí solo se decide qué botones mostrar y se presentan los errores. */
(function () {
  'use strict';

  const $ = (id) => document.getElementById(id);
  const ROL = JSON.parse($('rolCodigo').textContent); // admin | delegado | encargado | funcionario
  const MI_FUNCIONARIO = JSON.parse($('miFuncionario').textContent);
  const URL = '/api/actividades/';
  const URL_EVIDENCIAS = '/api/evidencias/';
  const ES_GESTOR = ROL === 'admin' || ROL === 'delegado';
  // Utilidades compartidas con "Mis registros" y "Verificación" (actividad_comun.js).
  const { esc, api, badge } = window.TerriIA;

  const estado = { pagina: 1, tam: 20, orden: '-fecha' };
  let filas = [];
  let opciones = null; // listas de la actividad abierta (/api/actividades/<id>/opciones-seguimiento/)
  let detalle = null;  // actividad abierta en el panel
  let disparador = null;

  /* ---------------- Utilidades ---------------- */
  async function traerTodo(url) {
    const registros = []; let sig = url;
    while (sig) { const d = await api(sig); registros.push(...d.results); sig = d.next; }
    return registros;
  }
  const alerta = (icon, title, text) => Swal.fire({ icon, title, text, confirmButtonText: 'Entendido', confirmButtonColor: '#ad0000' });
  const aviso = (title) => Swal.fire({ toast: true, position: 'top-end', icon: 'success', title, showConfirmButton: false, timer: 2600, timerProgressBar: true });
  const opcionesHTML = (lista, valor, vacio) => (vacio ? `<option value="">${esc(vacio)}</option>` : '')
    + lista.map((o) => `<option value="${esc(o.id)}" ${String(o.id) === String(valor ?? '') ? 'selected' : ''}>${esc(o.nombre)}</option>`).join('');
  const fechaHora = (iso) => (iso ? new Date(iso).toLocaleString('es-CL', { dateStyle: 'short', timeStyle: 'short' }) : '—');
  const soloFecha = (iso) => (iso ? new Date(`${iso}T00:00:00`).toLocaleDateString('es-CL') : '—');
  const hoyISO = () => { const d = new Date(); d.setMinutes(d.getMinutes() - d.getTimezoneOffset()); return d.toISOString().slice(0, 10); };
  const numOrNull = (v) => (v ? Number(v) : null);

  const CLASE_ESTADO = { Ingresado: 'est-ingresado', Pendiente: 'est-pendiente', 'En proceso': 'est-proceso', Realizado: 'est-realizado' };
  const ICONO_ESTADO = { Ingresado: 'bi-inbox', Pendiente: 'bi-hourglass-split', 'En proceso': 'bi-gear', Realizado: 'bi-check-circle-fill' };
  const etiquetaEstado = (e) => `<span class="etiqueta ${CLASE_ESTADO[e] || ''}"><i class="bi ${ICONO_ESTADO[e] || 'bi-circle'}"></i> ${esc(e)}</span>`;
  const etiquetaPrioridad = (p) => (p ? `<span class="etiqueta pri-${esc(p)}">${esc(p.charAt(0).toUpperCase() + p.slice(1))}</span>` : '<span class="etiqueta no">Sin prioridad</span>');
  const etiquetaVencida = (r) => (r.vencida ? `<span class="etiqueta vencida"><i class="bi bi-exclamation-triangle-fill"></i> Vencida · ${r.dias_atraso} día${r.dias_atraso === 1 ? '' : 's'}</span>` : '');

  const esParticipante = (r) => ES_GESTOR || [r.funcionario, r.responsable].includes(MI_FUNCIONARIO);
  // El servidor es quien decide; esto solo evita mostrar botones que darían error.
  const estaCerrada = (r) => r.estado === 'Realizado' || r.estado_verificacion === 'aprobada';

  /* ---------------- Listado ---------------- */
  const COLUMNAS = [
    { k: 'codigo', t: 'Código', orden: 'codigo', v: (r) => esc(r.codigo), excel: (r) => r.codigo },
    { k: 'fecha', t: 'Fecha', orden: 'fecha', v: (r) => fechaHora(r.fecha), excel: (r) => fechaHora(r.fecha) },
    {
      k: 'descripcion', t: 'Actividad', cls: 'descripcion',
      v: (r) => `<span class="recorte">${esc(r.descripcion || r.accion || r.item_nombre)}</span><small>${esc(r.item_nombre)}${r.vecino_nombre ? ` · ${esc(r.vecino_nombre)}` : ''}</small>`,
      excel: (r) => r.descripcion || r.accion || '',
    },
    { k: 'item_nombre', t: 'Ítem', hidden: true, excel: (r) => r.item_nombre },
    { k: 'vecino_nombre', t: 'Vecino', hidden: true, excel: (r) => r.vecino_nombre || '' },
    { k: 'funcionario_nombre', t: 'Registró', orden: 'funcionario__nombre', v: (r) => esc(r.funcionario_nombre), excel: (r) => r.funcionario_nombre },
    { k: 'area_nombre', t: 'Área / responsable', v: (r) => (r.area_nombre ? `${esc(r.area_nombre)}<small>${esc(r.responsable_nombre || 'Sin responsable')}</small>` : '<span class="etiqueta no">Sin asignar</span>'), excel: (r) => [r.area_nombre, r.responsable_nombre].filter(Boolean).join(' / ') },
    { k: 'prioridad', t: 'Prioridad', orden: 'prioridad', v: (r) => etiquetaPrioridad(r.prioridad), excel: (r) => r.prioridad || '' },
    { k: 'estado', t: 'Estado', orden: 'estado', v: (r) => `${etiquetaEstado(r.estado)} ${etiquetaTerrenoLista(r)}`, excel: (r) => r.estado },
    { k: 'terreno', t: 'Terreno', hidden: true, excel: (r) => (!r.requiere_terreno ? '' : r.terreno_cierre === 'conforme' ? 'Cierre OK' : r.terreno_inicial === 'conforme' ? 'Terreno OK' : 'Requiere terreno') },
    {
      k: 'fecha_compromiso', t: 'Compromiso', orden: 'fecha_compromiso',
      v: (r) => `${r.fecha_compromiso ? soloFecha(r.fecha_compromiso) : '<span class="etiqueta no">Sin fecha</span>'}<br>${etiquetaVencida(r)}`,
      excel: (r) => (r.fecha_compromiso ? soloFecha(r.fecha_compromiso) : ''),
    },
    { k: 'vencida', t: 'Vencida', hidden: true, excel: (r) => (r.vencida ? `Sí (${r.dias_atraso} días)` : 'No') },
    { k: 'motivo_atraso', t: 'Motivo de atraso', hidden: true, excel: (r) => r.motivo_atraso || '' },
  ];
  const VISIBLES = COLUMNAS.filter((c) => !c.hidden);

  function pintarCabecera() {
    $('cabeceraTabla').innerHTML = VISIBLES.map((c) => {
      if (!c.orden) return `<th scope="col">${c.t}</th>`;
      const asc = estado.orden === c.orden, desc = estado.orden === `-${c.orden}`;
      const sort = asc ? 'ascending' : desc ? 'descending' : 'none';
      const icono = asc ? 'bi-sort-up' : desc ? 'bi-sort-down' : 'bi-arrow-down-up';
      return `<th scope="col" aria-sort="${sort}"><button type="button" class="orden" data-orden="${c.orden}">${c.t} <i class="bi ${icono}"></i></button></th>`;
    }).join('') + '<th scope="col" class="acciones">Acciones</th>';
  }

  function parametros(extra = {}) {
    const p = new URLSearchParams({ page: estado.pagina, page_size: estado.tam, ordering: estado.orden, ...extra });
    const buscar = $('buscar').value.trim();
    if (buscar) p.set('search', buscar);
    if ($('filtroEstado').value) p.set('estado', $('filtroEstado').value);
    if ($('filtroPrioridad').value) p.set('prioridad', $('filtroPrioridad').value);
    if ($('filtroVencida').value) p.set('vencida', $('filtroVencida').value);
    return p;
  }
  function mostrarEstado(icono, titulo, texto, boton) {
    $('estado').innerHTML = `<i class="bi ${icono}"></i><strong>${esc(titulo)}</strong>${texto ? `<p>${esc(texto)}</p>` : ''}${boton || ''}`;
    $('estado').classList.add('visible');
  }
  let turno = 0;
  async function listar() {
    const mio = ++turno;
    try {
      const d = await api(`${URL}?${parametros()}`);
      if (mio !== turno) return;
      filas = d.results;
      $('cuerpoTabla').innerHTML = filas.map(filaHTML).join('');
      if (d.count === 0) {
        const hayFiltros = $('buscar').value || $('filtroEstado').value || $('filtroPrioridad').value || $('filtroVencida').value;
        mostrarEstado('bi-inbox', hayFiltros ? 'Sin resultados' : 'Aún no hay actividades',
          hayFiltros ? 'Ninguna actividad coincide con la búsqueda o los filtros.' : 'Registre la primera desde «Registrar actividad».');
      } else $('estado').classList.remove('visible');
      const ini = (estado.pagina - 1) * estado.tam + 1;
      $('total').textContent = d.count ? `Mostrando ${ini}–${ini + filas.length - 1} de ${d.count} actividad${d.count === 1 ? '' : 'es'}` : '0 actividades';
      pintarPaginador(Math.ceil(d.count / estado.tam));
    } catch (e) {
      if (mio !== turno) return;
      if (e.status === 404 && estado.pagina > 1) { estado.pagina = 1; return listar(); }
      $('cuerpoTabla').innerHTML = ''; $('paginador').innerHTML = ''; $('total').textContent = '';
      mostrarEstado('bi-exclamation-triangle', 'No se pudo cargar el listado', e.message,
        '<button type="button" class="btn btn-borde" id="btnReintentar"><i class="bi bi-arrow-clockwise"></i> Reintentar</button>');
    }
  }
  function filaHTML(r) {
    const celdas = VISIBLES.map((c) => `<td${c.cls ? ` class="${c.cls}"` : ''}>${c.v(r)}</td>`).join('');
    return `<tr class="${r.vencida ? 'fila-vencida' : ''}">${celdas}<td class="acciones">
      <button type="button" class="btn-accion" data-id="${r.id_actividad}" aria-label="Ver y dar seguimiento a ${esc(r.codigo)}"><i class="bi bi-eye"></i> Ver</button>
    </td></tr>`;
  }
  function pintarPaginador(paginas) {
    if (paginas <= 1) { $('paginador').innerHTML = ''; return; }
    const p = estado.pagina;
    let html = `<button type="button" data-p="${p - 1}" ${p === 1 ? 'disabled' : ''} aria-label="Página anterior"><i class="bi bi-chevron-left"></i></button>`;
    for (let n = 1; n <= paginas; n++) html += `<button type="button" data-p="${n}" ${n === p ? 'aria-current="page"' : ''} aria-label="Página ${n}">${n}</button>`;
    html += `<button type="button" data-p="${p + 1}" ${p === paginas ? 'disabled' : ''} aria-label="Página siguiente"><i class="bi bi-chevron-right"></i></button>`;
    $('paginador').innerHTML = html;
  }
  function filtrar() { estado.pagina = 1; listar(); }

  /* ---------------- Resumen (HU07: cuántas vencidas) ---------------- */
  async function pintarResumen() {
    try {
      const d = await api(`${URL}resumen/`);
      const valor = (clave, v) => (clave === 'estado' ? d.por_estado[v] : clave === 'vencida' ? d.vencidas : d.total);
      const boton = (clave, v, texto, cls = '') => `<li><button type="button" class="${cls}" data-filtro="${clave}" data-valor="${v}" aria-pressed="false"><strong>${valor(clave, v)}</strong><span>${texto}</span></button></li>`;
      $('resumen').innerHTML = boton('todas', '', 'Todas')
        + ['Ingresado', 'Pendiente', 'En proceso', 'Realizado'].map((e) => boton('estado', e, e)).join('')
        + boton('vencida', 'true', '<i class="bi bi-exclamation-triangle-fill"></i> Vencidas', 'vencidas');
      marcarResumen();
    } catch (e) { $('resumen').innerHTML = ''; }
  }
  function marcarResumen() {
    document.querySelectorAll('#resumen button').forEach((b) => {
      const { filtro, valor } = b.dataset;
      const activo = filtro === 'todas' ? !$('filtroEstado').value && !$('filtroVencida').value
        : filtro === 'estado' ? $('filtroEstado').value === valor && !$('filtroVencida').value
          : $('filtroVencida').value === 'true' && !$('filtroEstado').value;
      b.setAttribute('aria-pressed', activo ? 'true' : 'false');
    });
  }

  /* ---------------- Panel de detalle ---------------- */
  async function abrirDetalle(id, sinFoco) {
    if (!id) return;
    if (!sinFoco) disparador = document.activeElement;
    try {
      const [r, historial, comentarios, evidencias, visitas] = await Promise.all([
        api(`${URL}${id}/`),
        api(`${URL}${id}/historial-seguimiento/`),
        api(`${URL}${id}/comentarios/`),
        api(`${URL_EVIDENCIAS}?actividad=${id}`),
        api(`${URL}${id}/visitas-terreno/`),
      ]);
      detalle = r;
      opciones = null;
      pintarDetalle(r, historial, comentarios, evidencias.results || evidencias, visitas);
      $('panelFondo').hidden = false;
      if (!sinFoco) $('panelCerrar').focus();
    } catch (e) { alerta('error', 'No se pudo abrir la actividad', e.message); }
  }
  function cerrarDetalle() { $('panelFondo').hidden = true; detalle = null; if (disparador && disparador.focus) disparador.focus(); }

  function pintarDetalle(r, historial, comentarios, evidencias, visitas) {
    $('panelTitulo').textContent = `Actividad ${r.codigo}`;
    const cerrada = estaCerrada(r);
    const botones = [];
    if (esParticipante(r) && !cerrada) botones.push('<button type="button" class="btn btn-primario" data-op="estado"><i class="bi bi-arrow-repeat"></i> Cambiar estado</button>');
    if (ES_GESTOR && !cerrada) botones.push('<button type="button" class="btn btn-borde" data-op="asignar"><i class="bi bi-diagram-3"></i> Asignar área</button>');
    if (esParticipante(r) && !cerrada) botones.push('<button type="button" class="btn btn-borde" data-op="fecha"><i class="bi bi-calendar-event"></i> Fecha de compromiso</button>');
    if (esParticipante(r) && r.estado_verificacion !== 'aprobada' && (r.vencida || r.dias_atraso > 0)) botones.push('<button type="button" class="btn btn-borde" data-op="motivo"><i class="bi bi-chat-left-text"></i> Motivo de atraso</button>');

    const fila = (t, v) => `<dt>${t}</dt><dd>${v || '—'}</dd>`;
    const puedeSubir = (esParticipante(r) || ES_GESTOR) && r.estado_verificacion !== 'aprobada';
    $('panelCuerpo').innerHTML = `
      ${r.vencida ? `<p class="aviso-vencida"><i class="bi bi-exclamation-triangle-fill"></i> <strong>Actividad vencida</strong>: el compromiso era el ${soloFecha(r.fecha_compromiso)} (${r.dias_atraso} día${r.dias_atraso === 1 ? '' : 's'} de atraso). Para cambiar estado o fecha hay que indicar el motivo.</p>` : ''}
      ${r.estado_verificacion === 'aprobada' ? '<p class="aviso-vencida" style="background:var(--verde-claro);border-color:var(--verde)"><i class="bi bi-lock-fill"></i> La actividad está <strong>aprobada</strong>: no admite más cambios. Todavía se puede comentar.</p>' : ''}
      <section aria-label="Datos">
        <dl class="ficha">
          ${fila('Estado', `${etiquetaEstado(r.estado)} ${etiquetaTerrenoLista(r)}`)}
          ${fila('Verificación', badge(r.estado_verificacion))}
          ${fila('Prioridad', etiquetaPrioridad(r.prioridad))}
          ${fila('Área', esc(r.area_nombre || 'Sin asignar'))}
          ${fila('Responsable', esc(r.responsable_nombre || 'Sin responsable'))}
          ${fila('Compromiso', r.fecha_compromiso ? `${soloFecha(r.fecha_compromiso)} ${etiquetaVencida(r)}` : 'Sin fecha')}
          ${fila('Motivo de atraso', esc(r.motivo_atraso))}
          ${fila('Registró', `${esc(r.funcionario_nombre)} · ${esc(r.delegacion_codigo)}`)}
          ${fila('Fecha', fechaHora(r.fecha))}
          ${fila('Ítem', esc(r.item_nombre))}
          ${fila('Vecino', esc(r.vecino_nombre))}
          ${fila('Territorio', esc(r.territorio_nombre))}
          ${fila('Tipo de atención', esc([r.tipo_atencion_nombre, r.sub_atencion_nombre].filter(Boolean).join(' › ')))}
          ${fila('Contacto', esc([r.contacto, r.telefono].filter(Boolean).join(' · ')))}
          ${fila('Acción', esc(r.accion))}
        </dl>
        <div><h3>Descripción</h3><p class="texto" style="white-space:pre-wrap;margin:0">${esc(r.descripcion) || '—'}</p></div>
        ${botones.length ? `<div class="barra-acciones">${botones.join('')}</div>` : ''}
      </section>
      ${r.requiere_terreno ? seccionTerreno(r, visitas) : ''}
      <section aria-label="Evidencias"><h3><i class="bi bi-camera"></i> Evidencia fotográfica (${evidencias.length})</h3>
        ${evidencias.length ? `<ul class="evidencias">${evidencias.map((e) => `<li>${e.tiene_imagen ? `<a href="${esc(e.descarga)}" target="_blank" rel="noopener"><img src="${esc(e.descarga)}" alt="Evidencia ${esc(e.codigo_verificador)}" loading="lazy"></a>` : `<a href="${esc(e.descarga)}" download>${esc(e.nombre_original || 'Archivo')}</a>`}<span class="codigo">${esc(e.codigo_verificador)}</span><br>${fechaHora(e.fecha)}</li>`).join('')}</ul>` : '<p class="vacio">Aún no hay fotos de respaldo.</p>'}
        ${puedeSubir ? `<form class="form-linea" id="formEvidencia">
          <label for="archivoEvidencia">Agregar foto (JPG, PNG o WEBP, máx. 5 MB)</label>
          <input id="archivoEvidencia" type="file" accept="image/jpeg,image/png,image/webp">
          <button type="submit" class="btn btn-borde"><i class="bi bi-upload"></i> Subir foto</button></form>` : ''}
      </section>
      <section aria-label="Comentarios"><h3><i class="bi bi-chat-dots"></i> Comentarios (${comentarios.length})</h3>
        ${comentarios.length ? `<ul class="lista-simple">${comentarios.map((c) => `<li><span class="texto">${esc(c.texto)}</span><small>${esc(c.usuario_nombre)} · ${esc(c.usuario_rol)} · ${fechaHora(c.fecha)}</small></li>`).join('')}</ul>` : '<p class="vacio">Sin comentarios todavía.</p>'}
        ${esParticipante(r) ? `<form class="form-linea" id="formComentario">
          <label for="textoComentario">Nuevo comentario</label>
          <textarea id="textoComentario" maxlength="1000" placeholder="Escriba una novedad o una instrucción"></textarea>
          <span class="error" id="errorComentario" role="alert" style="color:var(--rojo);font-weight:700"></span>
          <button type="submit" class="btn btn-borde"><i class="bi bi-send"></i> Comentar</button></form>` : ''}
      </section>
      <section aria-label="Historial"><h3><i class="bi bi-clock-history"></i> Historial de cambios</h3>
        ${historial.length ? `<ul class="lista-simple">${historial.map((h) => `<li><strong>${esc(h.campo_nombre)}</strong>: ${h.valor_anterior ? `${esc(h.campo === 'fecha_compromiso' ? soloFecha(h.valor_anterior) : h.valor_anterior)} → ` : ''}<span class="texto">${esc(h.campo === 'fecha_compromiso' ? soloFecha(h.valor_nuevo) : h.valor_nuevo)}</span><small>${esc(h.usuario_nombre)} · ${fechaHora(h.fecha_cambio)}</small></li>`).join('')}</ul>` : '<p class="vacio">Sin cambios registrados.</p>'}
      </section>`;
  }

  async function recargarTrasAccion(mensaje) {
    const id = detalle.id_actividad;
    aviso(mensaje);
    pintarResumen(); listar();
    await abrirDetalle(id, true);
  }

  /* ---------------- Acciones de seguimiento (SweetAlert2) ---------------- */
  const campoSwal = (id, etiqueta, control) => `<div><label for="${id}">${etiqueta}</label>${control}</div>`;
  async function formularioSwal({ titulo, html, confirmar, leer, alAbrir }) {
    const r = await Swal.fire({
      title: titulo, html: `<div class="swal-form">${html}<div class="error-swal" id="errorSwal" role="alert"></div></div>`,
      showCancelButton: true, confirmButtonText: confirmar, cancelButtonText: 'Cancelar', reverseButtons: true, focusConfirm: false,
      confirmButtonColor: '#ad0000',
      didOpen: () => { if (alAbrir) alAbrir(); },
      preConfirm: () => {
        const v = leer();
        if (v.error) { $('errorSwal').textContent = v.error; return false; }
        return v.datos;
      },
    });
    return r.isConfirmed ? r.value : null;
  }
  async function enviarAccion(ruta, datos, mensaje) {
    try {
      await api(`${URL}${detalle.id_actividad}/${ruta}/`, { method: 'POST', body: JSON.stringify(datos) });
      await recargarTrasAccion(mensaje);
    } catch (e) { alerta('error', 'No se pudo completar', e.message); }
  }
  async function cargarOpciones() {
    opciones = await api(`${URL}${detalle.id_actividad}/opciones-seguimiento/`);
    return opciones;
  }
  const MOTIVO_HTML = (obligatorio, valor = '') => campoSwal('swMotivo', `Motivo del atraso${obligatorio ? ' *' : ''}`,
    `<textarea id="swMotivo" rows="3" maxlength="255" placeholder="Explique por qué se atrasó (mín. 10 caracteres)">${esc(valor)}</textarea>`);
  const motivoValido = (obligatorio) => {
    const m = $('swMotivo').value.trim();
    if (obligatorio && m.length < 10) return { error: 'Indique el motivo del atraso (al menos 10 caracteres).' };
    return { datos: m };
  };

  async function accionEstado() {
    const r = detalle;
    try { await cargarOpciones(); } catch (e) { return alerta('error', 'No se pudo preparar el cambio', e.message); }
    const lista = opciones.transiciones[r.estado].map((e) => ({ id: e, nombre: e }));
    if (!lista.length) return alerta('info', 'Sin cambios posibles', 'La actividad ya está realizada.');
    const necesita = r.vencida && !(r.motivo_atraso || '').trim();
    const valores = await formularioSwal({
      titulo: 'Cambiar estado',
      confirmar: 'Cambiar estado',
      html: campoSwal('swEstado', `Nuevo estado (ahora: ${esc(r.estado)})`, `<select id="swEstado">${opcionesHTML(lista, '', 'Seleccione')}</select>`)
        + (r.vencida ? (necesita ? '<p class="aviso-vencida">La actividad está vencida: el motivo es obligatorio.</p>' : `<p class="vacio">Motivo ya registrado: «${esc(r.motivo_atraso)}». Puede actualizarlo.</p>`) + MOTIVO_HTML(necesita) : ''),
      leer: () => {
        if (!$('swEstado').value) return { error: 'Elija el nuevo estado.' };
        const datos = { estado: $('swEstado').value };
        if (r.vencida) { const m = motivoValido(necesita); if (m.error) return m; if (m.datos) datos.motivo_atraso = m.datos; }
        return { datos };
      },
    });
    if (valores) enviarAccion('cambiar-estado', valores, 'Estado actualizado');
  }
  async function accionAsignar() {
    const r = detalle;
    try { await cargarOpciones(); } catch (e) { return alerta('error', 'No se pudieron cargar las áreas', e.message); }
    const valores = await formularioSwal({
      titulo: 'Asignar a un área',
      confirmar: 'Asignar',
      html: campoSwal('swArea', 'Área *', `<select id="swArea">${opcionesHTML(opciones.areas, r.area, 'Seleccione un área')}</select>`)
        + campoSwal('swPrioridad', 'Prioridad *', `<select id="swPrioridad">${opcionesHTML(opciones.prioridades, r.prioridad, 'Seleccione')}</select>`)
        + campoSwal('swResponsable', 'Responsable (opcional)', '<select id="swResponsable"></select>'),
      leer: () => {
        if (!$('swArea').value) return { error: 'Elija el área.' };
        if (!$('swPrioridad').value) return { error: 'Elija la prioridad.' };
        return { datos: { area: Number($('swArea').value), prioridad: $('swPrioridad').value, responsable: numOrNull($('swResponsable').value) } };
      },
      alAbrir: enlazarResponsables, // el responsable depende del área elegida
    });
    if (valores) enviarAccion('asignar', valores, 'Actividad asignada');
  }
  function enlazarResponsables() {
    const area = $('swArea'), resp = $('swResponsable');
    if (!area || !resp) return;
    const pintar = () => {
      const lista = opciones.responsables.filter((f) => !area.value || f.area === null || String(f.area) === area.value);
      resp.innerHTML = opcionesHTML(lista, detalle.responsable, 'Sin responsable');
    };
    area.addEventListener('change', pintar); pintar();
  }
  async function accionFecha() {
    const r = detalle;
    const necesita = r.vencida && !(r.motivo_atraso || '').trim();
    const valores = await formularioSwal({
      titulo: 'Fecha de compromiso',
      confirmar: 'Guardar fecha',
      html: campoSwal('swFecha', 'Fecha de compromiso *', `<input id="swFecha" type="date" min="${hoyISO()}" value="${esc(r.fecha_compromiso || '')}">`)
        + (r.vencida ? MOTIVO_HTML(necesita) : '') + '<p class="vacio">Cada cambio de fecha queda en el historial.</p>',
      leer: () => {
        if (!$('swFecha').value) return { error: 'Elija la fecha de compromiso.' };
        const datos = { fecha_compromiso: $('swFecha').value };
        if (r.vencida) { const m = motivoValido(necesita); if (m.error) return m; if (m.datos) datos.motivo_atraso = m.datos; }
        return { datos };
      },
    });
    if (valores) enviarAccion('fecha-compromiso', valores, 'Fecha de compromiso actualizada');
  }
  /* ---------------- Verificación en terreno (HU29) ---------------- */
  const RES_TERRENO = { conforme: ['Conforme', 'bi-check-circle-fill', 'est-realizado'], no_conforme: ['No conforme', 'bi-x-circle-fill', 'pri-alta'] };
  const etiquetaResultado = (v) => { const [t, i, c] = RES_TERRENO[v] || [v, 'bi-dash', 'no']; return `<span class="etiqueta ${c}"><i class="bi ${i}" aria-hidden="true"></i> ${esc(t)}</span>`; };
  // Insignia del listado: el texto y el icono dicen el estado, no solo el color.
  function etiquetaTerrenoLista(r) {
    if (!r.requiere_terreno) return '';
    if (r.terreno_cierre === 'conforme') return '<span class="etiqueta est-realizado"><i class="bi bi-patch-check-fill" aria-hidden="true"></i> Cierre OK</span>';
    if (r.terreno_inicial === 'conforme') return '<span class="etiqueta est-proceso"><i class="bi bi-geo-alt-fill" aria-hidden="true"></i> Terreno OK</span>';
    return '<span class="etiqueta est-pendiente"><i class="bi bi-geo-alt" aria-hidden="true"></i> Requiere terreno</span>';
  }
  const estadoTerreno = (v) => (v ? etiquetaResultado(v) : '<span class="etiqueta no">Sin visita</span>');
  function seccionTerreno(r, visitas) {
    const lista = visitas.length
      ? `<ul class="lista-simple">${visitas.map((v) => `<li><strong>${esc(v.tipo_nombre)}</strong> ${etiquetaResultado(v.resultado)}
          ${v.observacion ? `<span class="texto">${esc(v.observacion)}</span>` : ''}
          <small>${esc(v.usuario_nombre)} · ${fechaHora(v.fecha)}${v.latitud !== null && v.longitud !== null ? ` · ${esc(v.latitud)}, ${esc(v.longitud)}` : ''}${v.descarga ? ` · <a href="${esc(v.descarga)}" download><i class="bi bi-paperclip"></i> Archivo</a>` : ''}</small></li>`).join('')}</ul>`
      : '<p class="vacio">Aún no hay visitas a terreno.</p>';
    return `<section aria-label="Verificación en terreno"><h3><i class="bi bi-geo-alt"></i> Verificación en terreno (${visitas.length})</h3>
      <p class="terreno-estados"><span>Terreno: ${estadoTerreno(r.terreno_inicial)}</span> <span>Cierre: ${estadoTerreno(r.terreno_cierre)}</span></p>
      ${lista}
      ${r.puede_registrar_visita ? '<div class="barra-acciones"><button type="button" class="btn btn-primario" data-op="visita"><i class="bi bi-plus-lg"></i> Registrar visita</button></div>' : ''}
    </section>`;
  }
  async function accionVisita() {
    const r = detalle;
    const tipoInicial = r.terreno_inicial === 'conforme' ? 'cierre' : 'inicial';
    const valores = await formularioSwal({
      titulo: 'Registrar visita a terreno',
      confirmar: 'Registrar visita',
      html: campoSwal('swTipo', 'Tipo *', `<select id="swTipo">${opcionesHTML([{ id: 'inicial', nombre: 'Verificación en terreno' }, { id: 'cierre', nombre: 'Verificación de cierre' }], tipoInicial)}</select>`)
        + campoSwal('swResultado', 'Resultado *', `<select id="swResultado">${opcionesHTML([{ id: 'conforme', nombre: 'Conforme' }, { id: 'no_conforme', nombre: 'No conforme' }], 'conforme')}</select>`)
        + campoSwal('swObs', 'Observación (obligatoria si no es conforme)', '<textarea id="swObs" rows="3" maxlength="1000"></textarea>')
        + campoSwal('swArchivo', 'Foto o PDF (opcional, máx. 5 MB)', '<input id="swArchivo" type="file" accept="image/jpeg,image/png,application/pdf">')
        + '<div><button type="button" class="btn btn-borde" id="swUbicacion"><i class="bi bi-crosshair"></i> Usar mi ubicación</button> <span id="swCoords" class="vacio" aria-live="polite"></span></div>'
        + '<input id="swLat" type="hidden"><input id="swLng" type="hidden">',
      alAbrir: () => {
        $('swUbicacion').addEventListener('click', () => {
          if (!navigator.geolocation) { $('swCoords').textContent = 'Tu navegador no entrega la ubicación.'; return; }
          $('swCoords').textContent = 'Obteniendo ubicación…';
          navigator.geolocation.getCurrentPosition((pos) => {
            $('swLat').value = pos.coords.latitude.toFixed(6);
            $('swLng').value = pos.coords.longitude.toFixed(6);
            $('swCoords').textContent = `Ubicación: ${$('swLat').value}, ${$('swLng').value}`;
          }, () => { $('swCoords').textContent = 'No se pudo obtener la ubicación (es opcional; puedes continuar).'; },
          { enableHighAccuracy: true, timeout: 10000 });
        });
      },
      leer: () => {
        const resultado = $('swResultado').value, obs = $('swObs').value.trim();
        if (resultado === 'no_conforme' && !obs) return { error: 'Indica la observación: es obligatoria si la visita no es conforme.' };
        const datos = new FormData();
        datos.append('tipo', $('swTipo').value); datos.append('resultado', resultado);
        if (obs) datos.append('observacion', obs);
        if ($('swLat').value) { datos.append('latitud', $('swLat').value); datos.append('longitud', $('swLng').value); }
        const archivo = $('swArchivo').files[0];
        if (archivo) datos.append('archivo', archivo);
        return { datos };
      },
    });
    if (!valores) return;
    try {
      await api(`${URL}${detalle.id_actividad}/visitas-terreno/`, { method: 'POST', body: valores });
      await recargarTrasAccion('Visita registrada');
    } catch (e) { alerta('error', 'No se pudo registrar la visita', e.message); }
  }
  async function accionMotivo() {
    const valores = await formularioSwal({
      titulo: 'Motivo de atraso', confirmar: 'Guardar motivo',
      html: MOTIVO_HTML(true, detalle.motivo_atraso || ''),
      leer: () => { const m = motivoValido(true); return m.error ? m : { datos: { motivo_atraso: m.datos } }; },
    });
    if (valores) enviarAccion('motivo-atraso', valores, 'Motivo registrado');
  }

  /* ---------------- Eventos ---------------- */
  $('buscar').addEventListener('input', filtrar);
  ['filtroEstado', 'filtroPrioridad', 'filtroVencida'].forEach((id) => $(id).addEventListener('change', () => { filtrar(); marcarResumen(); }));
  $('tamPagina').addEventListener('change', () => { estado.tam = Number($('tamPagina').value); filtrar(); });
  $('btnLimpiar').addEventListener('click', () => {
    $('buscar').value = ''; ['filtroEstado', 'filtroPrioridad', 'filtroVencida'].forEach((id) => { $(id).value = ''; });
    marcarResumen(); filtrar();
  });
  $('resumen').addEventListener('click', (e) => {
    const b = e.target.closest('button[data-filtro]');
    if (!b) return;
    $('filtroEstado').value = b.dataset.filtro === 'estado' ? b.dataset.valor : '';
    $('filtroVencida').value = b.dataset.filtro === 'vencida' ? 'true' : '';
    marcarResumen(); filtrar();
  });
  $('paginador').addEventListener('click', (e) => {
    const b = e.target.closest('button[data-p]');
    if (!b || b.disabled) return;
    estado.pagina = Number(b.dataset.p); listar();
  });
  $('cabeceraTabla').addEventListener('click', (e) => {
    const b = e.target.closest('button[data-orden]');
    if (!b) return;
    estado.orden = estado.orden === b.dataset.orden ? `-${b.dataset.orden}` : b.dataset.orden;
    pintarCabecera(); filtrar();
  });
  $('estado').addEventListener('click', (e) => { if (e.target.closest('#btnReintentar')) listar(); });
  $('cuerpoTabla').addEventListener('click', (e) => {
    const b = e.target.closest('button[data-id]');
    if (b) abrirDetalle(Number(b.dataset.id));
  });
  $('btnExcel').addEventListener('click', exportar);
  $('panelCerrar').addEventListener('click', cerrarDetalle);
  $('panelFondo').addEventListener('mousedown', (e) => { if (e.target === $('panelFondo')) cerrarDetalle(); });
  $('panelCuerpo').addEventListener('click', (e) => {
    const b = e.target.closest('button[data-op]');
    if (!b) return;
    if (b.dataset.op === 'estado') accionEstado();
    else if (b.dataset.op === 'asignar') accionAsignar();
    else if (b.dataset.op === 'fecha') accionFecha();
    else if (b.dataset.op === 'motivo') accionMotivo();
    else if (b.dataset.op === 'visita') accionVisita();
  });
  $('panelCuerpo').addEventListener('submit', async (e) => {
    e.preventDefault();
    const id = detalle.id_actividad;
    if (e.target.id === 'formComentario') {
      const texto = $('textoComentario').value.trim();
      $('errorComentario').textContent = '';
      if (!texto) { $('errorComentario').textContent = 'Escriba el comentario.'; return; }
      try {
        await api(`${URL}${id}/comentarios/`, { method: 'POST', body: JSON.stringify({ texto }) });
        await recargarTrasAccion('Comentario agregado');
      } catch (err) { $('errorComentario').textContent = err.message; }
    } else if (e.target.id === 'formEvidencia') {
      const archivo = $('archivoEvidencia').files[0];
      if (!archivo) return alerta('warning', 'Falta la foto', 'Elija un archivo JPG, PNG o WEBP.');
      const datos = new FormData(); datos.append('actividad', id); datos.append('archivo', archivo);
      try {
        const ev = await api(URL_EVIDENCIAS, { method: 'POST', body: datos });
        await recargarTrasAccion(`Foto subida · código ${ev.codigo_verificador}`);
      } catch (err) { alerta('error', 'No se pudo subir la foto', err.message); }
    }
  });
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && !Swal.isVisible() && !$('panelFondo').hidden) cerrarDetalle();
  });

  /* ---------------- Exportar a Excel ---------------- */
  async function exportar() {
    Swal.fire({ title: 'Generando archivo…', allowOutsideClick: false, didOpen: () => Swal.showLoading() });
    try {
      const p = parametros({ page_size: 100 }); p.delete('page');
      const registros = await traerTodo(`${URL}?${p}`);
      const encabezados = COLUMNAS.map((c) => c.t);
      const datos = registros.map((r) => COLUMNAS.map((c) => (c.excel ? c.excel(r) : r[c.k] ?? '')));
      const hoja = XLSX.utils.aoa_to_sheet([encabezados, ...datos]);
      hoja['!cols'] = encabezados.map((t, i) => ({ wch: Math.min(Math.max(t.length, ...datos.map((f) => String(f[i]).length)) + 2, 50) }));
      const libro = XLSX.utils.book_new();
      XLSX.utils.book_append_sheet(libro, hoja, 'Seguimiento');
      XLSX.writeFile(libro, 'seguimiento-actividades.xlsx');
      Swal.close();
      aviso(`${registros.length} actividad${registros.length === 1 ? '' : 'es'} exportada${registros.length === 1 ? '' : 's'}`);
    } catch (e) { alerta('error', 'No se pudo exportar', e.message); }
  }

  pintarCabecera();
  pintarResumen();
  listar();
}());
