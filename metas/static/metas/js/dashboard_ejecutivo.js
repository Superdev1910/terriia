(() => {
  const dashboard = document.getElementById('dashboardEjecutivo');
  const mensaje = document.getElementById('mensajeEjecutivo');
  const filas = document.getElementById('filasDelegaciones');
  const porcentajeGlobal = document.getElementById('cumplimientoGlobal');
  const porcentajeEsperado = document.getElementById('porcentajeEsperado');
  const periodo = document.getElementById('periodoEjecutivo');

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
      const respuesta = await fetch(dashboard.dataset.endpoint, {
        headers: { Accept: 'application/json' },
      });
      const resultado = await respuesta.json();
      if (!respuesta.ok) {
        throw new Error(resultado.detail || resultado.error || 'No se pudo cargar el dashboard.');
      }

      porcentajeGlobal.textContent = porcentaje(resultado.cumplimiento_global_pct);
      porcentajeEsperado.textContent = `Esperado al día: ${porcentaje(resultado.porcentaje_esperado)}`;
      periodo.textContent = `Período ${fecha(resultado.periodo.fecha_inicio)} a ${fecha(resultado.periodo.fecha_termino)}`;
      resultado.delegaciones.forEach(mostrarDelegacion);
      mensaje.textContent = resultado.delegaciones.length
        ? ''
        : 'No hay delegaciones para mostrar.';
    } catch (error) {
      mensaje.textContent = error.message || 'No se pudo cargar el dashboard ejecutivo.';
      porcentajeGlobal.textContent = '—';
      porcentajeEsperado.textContent = '';
    }
  }

  cargarDashboard();
})();
