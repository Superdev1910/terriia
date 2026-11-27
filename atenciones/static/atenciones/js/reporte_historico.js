(function () {
  'use strict';

  const URL_DELEGACIONES = '/api/reportes/solicitudes-resueltas/delegaciones/';
  const URL_REPORTE = '/api/reportes/solicitudes-resueltas/';
  const delegacion = document.getElementById('filtroDelegacion');
  const desde = document.getElementById('filtroDesde');
  const hasta = document.getElementById('filtroHasta');
  const boton = document.getElementById('btnExportar');
  const mensaje = document.getElementById('mensajeReporte');

  function mostrarMensaje(texto, tipo) {
    mensaje.textContent = texto;
    mensaje.classList.toggle('error', tipo === 'error');
  }

  function detalleError(datos) {
    if (datos && typeof datos.detail === 'string') return datos.detail;
    if (datos && typeof datos.error === 'string') return datos.error;
    if (datos && typeof datos === 'object') {
      return Object.values(datos).flat().map(String).join(' ');
    }
    return 'No se pudo completar la solicitud.';
  }

  async function consultar(url) {
    const respuesta = await fetch(url, {
      headers: { Accept: 'application/json' },
      credentials: 'same-origin',
    });
    if (!respuesta.ok) {
      const datos = await respuesta.json();
      throw new Error(detalleError(datos));
    }
    return respuesta;
  }

  async function cargarDelegaciones() {
    try {
      const respuesta = await consultar(URL_DELEGACIONES);
      const datos = await respuesta.json();
      delegacion.replaceChildren(new Option('Seleccione una delegación', ''));
      datos.results.forEach((fila) => {
        delegacion.add(new Option(`${fila.codigo} · ${fila.nombre}`, fila.id));
      });
      boton.disabled = !datos.results.length;
      mostrarMensaje(
        datos.results.length
          ? 'Seleccione la delegación y el período para descargar el reporte.'
          : 'No hay delegaciones disponibles.',
      );
    } catch (error) {
      delegacion.replaceChildren(new Option('No se pudieron cargar', ''));
      boton.disabled = true;
      mostrarMensaje(error.message, 'error');
    }
  }

  function nombreArchivo(contentDisposition) {
    const coincidencia = contentDisposition && contentDisposition.match(/filename="([^"]+)"/i);
    return coincidencia ? coincidencia[1] : 'solicitudes-resueltas.xlsx';
  }

  async function exportar(evento) {
    evento.preventDefault();
    if (!delegacion.value || !desde.value || !hasta.value) {
      mostrarMensaje('Seleccione una delegación y ambas fechas.', 'error');
      return;
    }
    if (desde.value > hasta.value) {
      mostrarMensaje('La fecha final debe ser igual o posterior a la fecha inicial.', 'error');
      return;
    }

    boton.disabled = true;
    mostrarMensaje('Generando el reporte…');
    try {
      const parametros = new URLSearchParams({
        delegacion: delegacion.value,
        desde: desde.value,
        hasta: hasta.value,
      });
      const respuesta = await consultar(`${URL_REPORTE}?${parametros}`);
      const total = Number(respuesta.headers.get('X-Total-Registros') || 0);
      const sinFecha = Number(respuesta.headers.get('X-Sin-Fecha-Resolucion') || 0);
      if (!total) {
        const aviso = sinFecha
          ? ` Hay ${sinFecha} solicitud(es) Realizado sin fecha de resolución.`
          : '';
        mostrarMensaje(`No hay solicitudes resueltas en el período seleccionado.${aviso}`);
        return;
      }

      const archivo = await respuesta.blob();
      const url = URL.createObjectURL(archivo);
      const enlace = document.createElement('a');
      enlace.href = url;
      enlace.download = nombreArchivo(respuesta.headers.get('Content-Disposition'));
      document.body.appendChild(enlace);
      enlace.click();
      enlace.remove();
      window.setTimeout(() => URL.revokeObjectURL(url), 1000);

      const aviso = sinFecha
        ? ` Se omitieron ${sinFecha} solicitud(es) Realizado sin fecha de resolución; no se pueden asignar a un período.`
        : '';
      mostrarMensaje(`Descarga iniciada con ${total} solicitud(es).${aviso}`);
    } catch (error) {
      mostrarMensaje(error.message, 'error');
    } finally {
      boton.disabled = false;
    }
  }

  document.getElementById('filtrosReporte').addEventListener('submit', exportar);
  cargarDelegaciones();
}());
