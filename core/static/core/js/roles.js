(function () {
  "use strict";
  const URL_API = "/api/roles/";
  const $ = id => document.getElementById(id);
  let pagina = 1; let editando = null; let filas = [];

  const csrf = () => (document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/) || [,""])[1];
  async function api(url, options) {
    const response = await fetch(url, { credentials: "same-origin", headers: {"Content-Type": "application/json", "X-CSRFToken": decodeURIComponent(csrf()), "Accept": "application/json"}, ...options });
    const data = response.status === 204 ? null : await response.json();
    if (!response.ok) throw new Error(data.error || "No se pudo completar la operación.");
    return data;
  }
  function esc(value) { return String(value ?? "").replace(/[&<>"']/g, c => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"}[c])); }
  function avisar(titulo, mensaje, icono) { if (window.Swal) Swal.fire(titulo, mensaje, icono); else alert(mensaje); }
  const tipo = rol => rol.es_del_sistema ? "Sistema" : "Nuevo";
  const estadoTexto = rol => rol.activo ? "Activo" : "Inactivo";

  function filtros(params) {
    const search = $("buscar").value.trim(); const activo = $("filtroEstado").value;
    if (search) params.set("search", search);
    if (activo) params.set("activo", activo);
    return params;
  }
  async function cargar() {
    const params = filtros(new URLSearchParams({page: pagina, page_size: 20}));
    try { const data = await api(`${URL_API}?${params}`); filas = data.results; render(data); }
    catch (error) { $("estado").textContent = error.message; $("estado").classList.add("visible"); }
  }
  function acciones(rol) {
    let html = `<button class="btn-accion editar" data-id="${rol.id_rol}"><i class="bi bi-pencil"></i> Editar</button>`;
    if (!rol.es_del_sistema) {
      html += rol.activo
        ? `<button class="btn-accion peligro cambiar" data-id="${rol.id_rol}"><i class="bi bi-slash-circle"></i> Desactivar</button>`
        : `<button class="btn-accion cambiar" data-id="${rol.id_rol}"><i class="bi bi-check-circle"></i> Activar</button>`;
    }
    return html;
  }
  function render(data) {
    $("cuerpoTabla").innerHTML = filas.map(rol => `<tr>
      <td><strong>${esc(rol.nombre)}</strong></td>
      <td>${esc(rol.descripcion)}</td>
      <td>${rol.cantidad_usuarios}</td>
      <td><span class="etiqueta ${rol.es_del_sistema ? "info" : "no"}">${tipo(rol)}</span></td>
      <td><span class="etiqueta ${rol.activo ? "ok" : "no"}">${estadoTexto(rol)}</span></td>
      <td class="acciones">${acciones(rol)}</td></tr>`).join("");
    $("estado").textContent = filas.length ? "" : "No hay roles que coincidan con la búsqueda.";
    $("estado").classList.toggle("visible", !filas.length);
    $("total").textContent = `${data.count} rol(es)`;
    $("paginador").innerHTML = `<button ${data.previous ? "" : "disabled"} id="anterior" aria-label="Página anterior">‹</button><button aria-current="page">${pagina}</button><button ${data.next ? "" : "disabled"} id="siguiente" aria-label="Página siguiente">›</button>`;
    $("anterior").onclick = () => { pagina--; cargar(); }; $("siguiente").onclick = () => { pagina++; cargar(); };
    document.querySelectorAll(".editar").forEach(b => b.onclick = () => abrir(filas.find(r => String(r.id_rol) === b.dataset.id)));
    document.querySelectorAll(".cambiar").forEach(b => b.onclick = () => cambiarEstado(filas.find(r => String(r.id_rol) === b.dataset.id)));
  }

  function abrir(rol) {
    editando = rol || null;
    const form = $("formulario");
    $("modalTitulo").textContent = rol ? `Editar rol «${rol.nombre}»` : "Nuevo rol";
    form.elements.nombre.value = rol ? rol.nombre : "";
    form.elements.descripcion.value = rol ? rol.descripcion : "";
    form.elements.nombre.readOnly = !!(rol && rol.es_del_sistema);
    $("ayudaNombre").hidden = !(rol && rol.es_del_sistema);
    $("modal").hidden = false;
    (form.elements.nombre.readOnly ? form.elements.descripcion : form.elements.nombre).focus();
  }
  function cerrar() { $("modal").hidden = true; }
  async function guardar(event) {
    event.preventDefault();
    const form = $("formulario");
    const nombre = form.elements.nombre.value.trim();
    if (!nombre) { avisar("Falta el nombre", "El nombre es un campo obligatorio.", "warning"); return; }
    const datos = {descripcion: form.elements.descripcion.value.trim()};
    if (!editando || !editando.es_del_sistema) datos.nombre = nombre;
    try {
      await api(editando ? `${URL_API}${editando.id_rol}/` : URL_API, {method: editando ? "PATCH" : "POST", body: JSON.stringify(datos)});
      cerrar(); cargar();
      avisar("Listo", editando ? "Rol actualizado." : "Rol creado.", "success");
    } catch (error) { avisar("No se pudo guardar", error.message, "error"); }
  }
  async function cambiarEstado(rol) {
    const activar = !rol.activo;
    const detalle = activar
      ? "Se podrá volver a asignar a usuarios."
      : `${rol.cantidad_usuarios} usuario(s) lo tienen: lo conservan y pueden seguir ingresando, pero no se podrá asignar a nadie más.`;
    if (window.Swal) {
      const respuesta = await Swal.fire({title: `¿${activar ? "Activar" : "Desactivar"} el rol «${rol.nombre}»?`, text: detalle, icon: activar ? "question" : "warning", showCancelButton: true, confirmButtonText: activar ? "Activar" : "Desactivar", cancelButtonText: "Cancelar"});
      if (!respuesta.isConfirmed) return;
    } else if (!confirm(detalle)) return;
    try { await api(`${URL_API}${rol.id_rol}/`, {method: "PATCH", body: JSON.stringify({activo: activar})}); cargar(); }
    catch (error) { avisar("No se pudo cambiar el estado", error.message, "error"); }
  }

  async function exportar() {
    try {
      const registros = [];
      let siguiente = `${URL_API}?${filtros(new URLSearchParams({page_size: 100}))}`;
      while (siguiente) { const data = await api(siguiente); registros.push(...data.results); siguiente = data.next; }
      const encabezados = ["Nombre", "Descripción", "Usuarios con este rol", "Tipo", "Estado"];
      const datos = registros.map(rol => [rol.nombre, rol.descripcion, rol.cantidad_usuarios, tipo(rol), estadoTexto(rol)]);
      const hoja = XLSX.utils.aoa_to_sheet([encabezados, ...datos]);
      hoja["!cols"] = encabezados.map((encabezado, i) => ({wch: Math.min(Math.max(encabezado.length, ...datos.map(fila => String(fila[i]).length)) + 2, 50)}));
      const libro = XLSX.utils.book_new();
      XLSX.utils.book_append_sheet(libro, hoja, "Roles"); XLSX.writeFile(libro, "roles.xlsx");
    } catch (error) { avisar("No se pudo exportar", error.message, "error"); }
  }

  $("btnNuevo").onclick = () => abrir(); $("formulario").onsubmit = guardar;
  $("btnCancelar").onclick = $("modalCerrar").onclick = cerrar;
  document.addEventListener("keydown", e => { if (e.key === "Escape" && !$("modal").hidden) cerrar(); });
  $("btnExcel").onclick = exportar;
  $("buscar").oninput = () => { pagina = 1; cargar(); }; $("filtroEstado").onchange = () => { pagina = 1; cargar(); };
  $("btnLimpiar").onclick = () => { $("buscar").value = ""; $("filtroEstado").value = ""; pagina = 1; cargar(); };
  cargar();
}());
