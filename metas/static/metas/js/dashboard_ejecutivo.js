(() => {
  const dashboard = document.getElementById('dashboardEjecutivo');
  const mensaje = document.getElementById('mensajeEjecutivo');
  const filas = document.getElementById('filasDelegaciones');
  const porcentajeGlobal = document.getElementById('cumplimientoGlobal');
  const porcentajeEsperado = document.getElementById('porcentajeEsperado');
  const periodo = document.getElementById('periodoEjecutivo');
  const filtro = document.getElementById('filtroDelegacion');
  const totales = document.getElementById('totalesGlobales');
  const detalle = document.getElementById('detalleDelegaciones');
  let opcionesCargadas = false;

  function esc(valor) {
    return String(valor ?? '').replace(/[&<>"']/g, (c) => ({
      '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
    }[c]));
  }

  function bloqueVolumen(volumen, indicadores) {
    const estados = volumen.por_estado
      .map((e) => `<li>${esc(e.etiqueta)}: <strong>${esc(e.cantidad)}</strong></li>`).join('');
    const areas = volumen.por_area
      .filter((a) => a.clave || a.cantidad)
      .map((a) => `<li>${esc(a.etiqueta)}: <strong>${esc(a.cantidad)}</strong></li>`).join('');
    const ultimo = indicadores.fecha_ultimo_ingreso
      ? fecha(indicadores.fecha_ultimo_ingreso) : 'Sin ingresos';
    const dias = indicadores.dias_desde_ultimo_ingreso === null
      ? '—' : indicadores.dias_desde_ultimo_ingreso;
    const promedio = Number(indicadores.promedio_ingresos_diarios)
      .toLocaleString('es-CL', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    return `<div class="ejecutivo-tarjeta"><h3>Por estado (total ${esc(volumen.total)})</h3><ul>${estados}</ul></div>`
      + `<div class="ejecutivo-tarjeta"><h3>Por área</h3><ul>${areas}</ul></div>`
      + '<div class="ejecutivo-tarjeta"><h3>Actividad</h3><ul>'
      + `<li>Último ingreso: <strong>${esc(ultimo)}</strong></li>`
      + `<li>Días desde el último ingreso: <strong>${esc(dias)}</strong></li>`
      + `<li>Total de ingresos: <strong>${esc(indicadores.total_ingresos)}</strong></li>`
      + `<li>Promedio diario: <strong>${esc(promedio)}</strong></li></ul></div>`;
  }

  function mostrarDetalle(resultado) {
    totales.innerHTML = bloqueVolumen(resultado.volumen_global, resultado.indicadores_actividad_global);
    detalle.innerHTML = resultado.delegaciones.map((d) => `<article class="ejecutivo-delegacion">`
      + `<h3>${esc(d.codigo)} · ${esc(d.nombre)}</h3>`
      + `<div class="ejecutivo-tarjetas">${bloqueVolumen(d.volumen, d.indicadores_actividad)}</div>`
      + '</article>').join('');
  }

  function llenarFiltro(delegaciones) {
    delegaciones.forEach((d) => {
      const opcion = document.createElement('option');
      opcion.value = d.delegacion_id;
      opcion.textContent = `${d.codigo} · ${d.nombre}`;
      filtro.append(opcion);
    });
    opcionesCargadas = true;
  }

  function urlConsulta() {
    const parametros = new URLSearchParams();
    const periodoUrl = new URLSearchParams(window.location.search).get('periodo');
    if (periodoUrl) parametros.set('periodo', periodoUrl);
    if (filtro.value) parametros.set('delegacion', filtro.value);
    const texto = parametros.toString();
    return texto ? `${dashboard.dataset.endpoint}?${texto}` : dashboard.dataset.endpoint;
  }

  function porcentaje(valor) {
    return `${Number(valor).toLocaleString('es-CL', {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    })}%`;
  }

  function fecha(valor) {
    return new Date(`${valor}T00:00:00`).toLocaleDateString('es-CL');
  }

  function mostrarDelegacion(delegacion) {
    const fila = document.createElement('tr');
    const nombre = document.createElement('th');
    const cumplimiento = document.createElement('td');
    const estado = document.createElement('td');
    const indicador = document.createElement('span');

    nombre.scope = 'row';
    nombre.textContent = `${delegacion.codigo} · ${delegacion.nombre}`;
    cumplimiento.textContent = porcentaje(delegacion.cumplimiento_pct);
    indicador.className = `ejecutivo-estado ${delegacion.color_semaforo}`;
    indicador.textContent = delegacion.color_semaforo[0].toUpperCase()
      + delegacion.color_semaforo.slice(1);
    estado.append(indicador);
    fila.append(nombre, cumplimiento, estado);
    filas.append(fila);
  }

  async function cargarDashboard() {
    try {
      const respuesta = await fetch(urlConsulta(), {
        headers: { Accept: 'application/json' },
      });
      const resultado = await respuesta.json();
      if (!respuesta.ok) {
        throw new Error(resultado.detail || resultado.error || 'No se pudo cargar el dashboard.');
      }

      porcentajeGlobal.textContent = porcentaje(resultado.cumplimiento_global_pct);
      porcentajeEsperado.textContent = `Esperado al día: ${porcentaje(resultado.porcentaje_esperado)}`;
      periodo.textContent = `Período ${fecha(resultado.periodo.fecha_inicio)} a ${fecha(resultado.periodo.fecha_termino)}`;
      filas.replaceChildren();
      if (!opcionesCargadas) llenarFiltro(resultado.delegaciones);
      resultado.delegaciones.forEach(mostrarDelegacion);
      mostrarDetalle(resultado);
      mensaje.textContent = resultado.delegaciones.length
        ? ''
        : 'No hay delegaciones para mostrar.';
    } catch (error) {
      mensaje.textContent = error.message || 'No se pudo cargar el dashboard ejecutivo.';
      porcentajeGlobal.textContent = '—';
      porcentajeEsperado.textContent = '';
    }
  }

  filtro.addEventListener('change', cargarDashboard);
  cargarDashboard();
})();
