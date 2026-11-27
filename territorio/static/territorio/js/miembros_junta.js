(function () {
  "use strict";
  // Diálogo "Miembros" de una junta de vecinos (solo se carga en la pantalla de juntas).
  const URL = "/api/miembros-junta/";
  const csrf = () => (document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/) || [, ""])[1];
  const esc = v => String(v ?? "").replace(/[&<>"']/g, c => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"}[c]));
  const CARGOS = [["socio", "Socio"], ["presidente", "Presidente"], ["vicepresidente", "Vicepresidente"], ["secretario", "Secretario"], ["tesorero", "Tesorero"], ["director", "Director"]];
  const hoy = () => { const d = new Date(); return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`; };
  async function api(url, options) {
    const r = await fetch(url, {credentials: "same-origin", headers: {"Content-Type": "application/json", "X-CSRFToken": decodeURIComponent(csrf()), "Accept": "application/json"}, ...options});
    const data = r.status === 204 ? null : await r.json().catch(() => ({}));
    if (!r.ok) throw new Error((data && data.error) || "No se pudo completar la operación.");
    return data;
  }
  async function todos(url) {
    const filas = []; let sig = url;
    while (sig) { const d = await api(sig); filas.push(...(d.results || [])); sig = d.next; }
    return filas;
  }
  function abrir(junta, alCerrar) {
    let verInactivos = false; let vecino = null; let miembros = [];
    const cuerpo = () => document.getElementById("miembrosCuerpo");
    const aviso = texto => { const e = document.getElementById("miembrosAviso"); if (e) e.textContent = texto || ""; };
    async function cargar() {
      try { miembros = await todos(`${URL}?junta=${encodeURIComponent(junta.id_junta_vecinos)}&page_size=100`); pintar(); }
      catch (e) { aviso(e.message); }
    }
    function pintar() {
      const visibles = miembros.filter(m => verInactivos || m.estado === "activo");
      const filas = visibles.map(m => `<tr><td>${esc(m.vecino_rut)}</td><td>${esc(m.vecino_nombre)}</td><td>${esc(m.cargo_display)}</td><td>${esc(m.fecha_ingreso)}${m.fecha_salida ? " → " + esc(m.fecha_salida) : ""}</td><td>${m.estado === "activo" ? `<button type="button" class="btn btn-texto" data-quitar="${esc(m.id_miembro_junta)}">Quitar</button>` : "Inactivo"}</td></tr>`).join("");
      cuerpo().innerHTML = filas
        ? `<div class="tabla-scroll"><table class="tabla"><thead><tr><th>RUT</th><th>Nombre</th><th>Cargo</th><th>Ingreso</th><th></th></tr></thead><tbody>${filas}</tbody></table></div>`
        : "<p>La junta no tiene miembros registrados.</p>";
      cuerpo().querySelectorAll("[data-quitar]").forEach(b => b.onclick = () => quitar(b.dataset.quitar));
    }
    async function quitar(id) {
      try { await api(`${URL}${encodeURIComponent(id)}/`, {method: "DELETE"}); aviso("Miembro quitado."); await cargar(); }
      catch (e) { aviso(e.message); }
    }
    async function buscar() {
      const rut = document.getElementById("mjRut").value.trim(); vecino = null;
      document.getElementById("mjVecino").textContent = "";
      try {
        vecino = await api(`/api/vecinos/buscar/?rut=${encodeURIComponent(rut)}`);
        document.getElementById("mjVecino").textContent = `${vecino.nombres} ${vecino.apellidos} (${vecino.rut})`; aviso("");
      } catch (e) { aviso(e.message); }
    }
    async function agregar() {
      if (!vecino) { aviso("Busque primero al vecino por RUT."); return; }
      try {
        await api(URL, {method: "POST", body: JSON.stringify({junta: junta.id_junta_vecinos, vecino: vecino.id_vecino, cargo: document.getElementById("mjCargo").value, fecha_ingreso: document.getElementById("mjFecha").value || hoy()})});
        vecino = null; document.getElementById("mjRut").value = ""; document.getElementById("mjVecino").textContent = ""; aviso("Miembro agregado."); await cargar();
      } catch (e) { aviso(e.message); }
    }
    Swal.fire({
      title: `Miembros · ${esc(junta.nombre)}`, width: 760, showConfirmButton: true, confirmButtonText: "Cerrar",
      html: `<div style="text-align:left"><label><input type="checkbox" id="mjInactivos"> Mostrar inactivos e historial</label><div id="miembrosCuerpo">Cargando...</div>
        <h3 style="margin:1rem 0 .5rem">Agregar miembro</h3>
        <div style="display:flex;gap:.5rem;flex-wrap:wrap;align-items:end">
          <label class="campo"><span>RUT del vecino</span><input id="mjRut" type="text" autocomplete="off" placeholder="12345678-5"></label>
          <button type="button" class="btn btn-borde" id="mjBuscar">Buscar</button>
          <label class="campo"><span>Cargo</span><select id="mjCargo">${CARGOS.map(c => `<option value="${c[0]}">${c[1]}</option>`).join("")}</select></label>
          <label class="campo"><span>Fecha de ingreso</span><input id="mjFecha" type="date" value="${hoy()}"></label>
          <button type="button" class="btn btn-primario" id="mjAgregar">Agregar</button>
        </div><p id="mjVecino"></p><p id="miembrosAviso" role="alert" class="alerta"></p></div>`,
      didOpen: () => {
        document.getElementById("mjInactivos").onchange = e => { verInactivos = e.target.checked; pintar(); };
        document.getElementById("mjBuscar").onclick = buscar; document.getElementById("mjAgregar").onclick = agregar;
        cargar();
      },
      willClose: () => { if (alCerrar) alCerrar(); },
    });
  }
  window.MiembrosJunta = {abrir};
}());
