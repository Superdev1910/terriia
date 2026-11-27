/* Utilidades compartidas por "Mis registros" y "Verificación" (SCRUM-123). */
window.TerriIA = (function () {
  'use strict';

  const esc = (v) => String(v ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const csrf = () => {
    const m = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
    return m ? decodeURIComponent(m[1]) : '';
  };
  // Si el cuerpo es FormData no se fija Content-Type (el navegador agrega el boundary).
  async function api(url, opciones = {}) {
    const cabeceras = { 'X-CSRFToken': csrf(), Accept: 'application/json' };
    if (!(opciones.body instanceof FormData)) cabeceras['Content-Type'] = 'application/json';
    const resp = await fetch(url, { credentials: 'same-origin', headers: cabeceras, ...opciones });
    let datos = null;
    if (resp.status !== 204) { try { datos = await resp.json(); } catch (e) { datos = null; } }
    if (!resp.ok) {
      const err = new Error((datos && datos.error) || 'No se pudo completar la operación.');
      err.campo = datos && datos.campo; err.status = resp.status;
      throw err;
    }
    return datos;
  }
  const fechaTexto = (iso) => new Date(iso).toLocaleString('es-CL', { dateStyle: 'short', timeStyle: 'short' });
  const alerta = (icon, title, html) => Swal.fire({ icon, title, html, confirmButtonText: 'Entendido', confirmButtonColor: '#ad0000' });

  const VERIF = {
    pendiente: ['Pendiente', 'bi-hourglass-split', 'info'],
    aprobada: ['Aprobada', 'bi-check-circle-fill', 'ok'],
    rechazada: ['Rechazada', 'bi-x-circle-fill', 'no'],
    antecedentes: ['Requiere antecedentes', 'bi-exclamation-circle', 'alerta'],
  };
  // El color nunca es el único indicador: cada estado lleva texto e icono.
  function badge(estado) {
    const [texto, icono, clase] = VERIF[estado] || [estado, 'bi-dash', 'no'];
    return `<span class="etiqueta ${clase}"><i class="bi ${icono}" aria-hidden="true"></i> ${esc(texto)}</span>`;
  }
  const listaEvidencias = (evs) => (evs.length
    ? `<ul class="lista-evidencias">${evs.map((e) => `<li><i class="bi ${e.tiene_imagen ? 'bi-file-earmark-image' : 'bi-file-earmark-pdf'}" aria-hidden="true"></i>
        <a href="${esc(e.descarga)}" download>${esc(e.nombre_original || e.codigo_verificador)}</a>
        <small class="mono">${esc(e.codigo_verificador)}</small>
        ${e.puedeQuitar ? `<button type="button" class="btn-accion peligro" data-quitar="${e.id_evidencia}" aria-label="Quitar evidencia"><i class="bi bi-trash"></i></button>` : ''}</li>`).join('')}</ul>`
    : '<p class="subtitulo">Sin evidencias.</p>');

  return { esc, api, fechaTexto, alerta, badge, listaEvidencias, VERIF };
})();
