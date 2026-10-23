(function () {
  'use strict';

  const $ = (id) => document.getElementById(id);
  const texto = (id, value) => { $(id).textContent = value || '—'; };
  const fecha = (value) => value ? value.split('-').reverse().join('-') : '—';

  async function cargarPerfil() {
    try {
      const respuesta = await fetch('/api/mi-perfil/', {
        credentials: 'same-origin',
        headers: { Accept: 'application/json' },
      });
      if (!respuesta.ok) throw new Error(respuesta.status === 403
        ? 'Tu cuenta no tiene una ficha activa asociada.'
        : 'No se pudieron cargar tus datos. Intenta nuevamente.');
      const datos = await respuesta.json();
      texto('perfilNombre', datos.funcionario.nombre);
      texto('perfilIdentificador', datos.funcionario.identificador_inst);
      texto('perfilCargo', datos.funcionario.cargo);
      texto('perfilDelegacion', datos.funcionario.delegacion);

      const cuerpo = $('cuerpoMetas');
      cuerpo.replaceChildren();
      if (!datos.metas.length) {
        $('estadoPerfil').textContent = 'Todavía no tienes metas asignadas.';
        return;
      }
      $('estadoPerfil').textContent = '';
      datos.metas.forEach((meta) => {
        const fila = document.createElement('tr');
        [meta.item, meta.delegacion, `${fecha(meta.periodo_inicio)} a ${fecha(meta.periodo_termino)}`, `${meta.valor_objetivo}${meta.unidad ? ` ${meta.unidad}` : ''}`]
          .forEach((valor) => {
            const celda = document.createElement('td');
            celda.textContent = valor;
            fila.append(celda);
          });
        cuerpo.append(fila);
      });
    } catch (error) {
      $('estadoPerfil').textContent = error.message;
      texto('perfilNombre', 'No disponible');
    }
  }

  cargarPerfil();
})();
