/* Cifras reales en las tarjetas de inicio (API /api/organizacion/resumen/). */
(function () {
  'use strict';
  const plural = (n, uno, varios) => `${n} ${n === 1 ? uno : varios}`;
  const poner = (id, texto) => { document.getElementById(id).textContent = texto; };

  fetch('/api/organizacion/resumen/', { credentials: 'same-origin', headers: { Accept: 'application/json' } })
    .then((r) => { if (!r.ok) throw new Error(); return r.json(); })
    .then((d) => {
      poner('cifrasDelegaciones', `${plural(d.delegaciones.total, 'delegación', 'delegaciones')} · ${plural(d.delegaciones.activas, 'activa', 'activas')} · ${plural(d.delegaciones.inactivas, 'inactiva', 'inactivas')}`);
      poner('cifrasAreas', `${plural(d.areas.total, 'área', 'áreas')} · ${plural(d.areas.activas, 'activa', 'activas')} · ${plural(d.areas.inactivas, 'inactiva', 'inactivas')}`);
      poner('cifrasCargos', `${plural(d.cargos.total, 'cargo', 'cargos')} · ${plural(d.cargos.vigentes, 'vigente', 'vigentes')} · ${plural(d.cargos.transversales, 'transversal', 'transversales')}`);
    })
    .catch(() => {
      ['cifrasDelegaciones', 'cifrasAreas', 'cifrasCargos'].forEach((id) => poner(id, 'No se pudieron cargar las cifras.'));
    });
})();
