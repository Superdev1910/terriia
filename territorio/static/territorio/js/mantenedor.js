(function () {
  "use strict";
  const entidad = JSON.parse(document.getElementById("entidad").textContent);
  const cfg = {
    vecinos: { title: "Vecinos", url: "/api/vecinos/", pk: "id_vecino", estadoCampo: "estado", estados: [["activo", "Activos"], ["inactivo", "Inactivos"]], fields: [
      ["rut", "RUT", "text", true], ["nombres", "Nombres", "text", true], ["apellidos", "Apellidos", "text", true],
      ["telefono", "Teléfono", "text", false], ["direccion", "Dirección", "text", false]],
      cols: [["rut","RUT"],["nombres","Nombres"],["apellidos","Apellidos"],["estado","Estado"]] },
    territorios: { title: "Territorios", url: "/api/territorios/", pk: "id_territorio", estadoCampo: "activo", estados: [["true", "Activos"], ["false", "Inactivos"]], fields: [
      ["delegacion","Delegación","select",true], ["nombre","Nombre","text",true], ["es_formal","¿Es formal?","checkbox",false],
      ], cols: [["delegacion_nombre","Delegación"],["nombre","Nombre"],["es_formal","Formal"],["activo","Estado"]] },
    "juntas-vecinos": { title: "Juntas de vecinos", url: "/api/juntas-vecinos/", pk: "id_junta_vecinos", estadoCampo: "activa", estados: [["true", "Activas"], ["false", "Inactivas"]], fields: [
      ["territorio","Territorio","select",true], ["numero_registro","N° registro","text",false], ["nombre","Nombre","text",true],
      ["direccion","Dirección","text",false], ["presidente","Presidente","text",false], ["telefono","Teléfono","text",false], ["email","Correo","email",false]], cols: [["numero_registro","Registro"],["nombre","Nombre"],["territorio_nombre","Territorio"],["presidente","Presidente"],["telefono","Teléfono"],["email","Correo"],["activa","Estado"]] }
  }[entidad];
  const $ = id => document.getElementById(id); let pagina = 1; let editando = null; let filas = [];
  const estaActivo = valor => valor === true || valor === "activo" || valor === "activa";
  const csrf = () => (document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/) || [,""])[1];
  async function api(url, options) {
    const response = await fetch(url, { credentials: "same-origin", headers: {"Content-Type":"application/json","X-CSRFToken":decodeURIComponent(csrf()),"Accept":"application/json"}, ...options });
    const data = response.status === 204 ? null : await response.json();
    if (!response.ok) throw new Error(data.error || "No se pudo completar la operación.");
    return data;
  }
  function esc(value) { return String(value ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c])); }
  async function cargar() {
    const params = new URLSearchParams({page: pagina, page_size: 20});
    const search = $("buscar").value.trim(); const estado = $("filtroEstado").value;
    if (search) params.set("search", search); if (estado) params.set(cfg.estadoCampo, estado === "true" ? "true" : estado === "false" ? "false" : estado);
    try { const data = await api(`${cfg.url}?${params}`); filas = data.results; render(data); }
    catch (error) { $("estado").textContent = error.message; }
  }
  function render(data) {
    $("tituloPagina").textContent = cfg.title; $("subtituloPagina").textContent = "Administre registros y conserve su historial.";
    $("cabeceraTabla").innerHTML = cfg.cols.map(c => `<th>${c[1]}</th>`).join("") + "<th>Acciones</th>";
    $("cuerpoTabla").innerHTML = filas.map(row => `<tr>${cfg.cols.map(c => `<td>${esc(c[0] === "es_formal" || c[0] === "activo" || c[0] === "activa" ? (row[c[0]] ? "Sí" : "No") : row[c[0]])}</td>`).join("")}<td><button class="btn btn-texto editar" data-id="${row[cfg.pk]}">Editar</button>${estaActivo(row[cfg.estadoCampo]) ? `<button class="btn btn-texto desactivar" data-id="${row[cfg.pk]}">Desactivar</button>` : ""}</td></tr>`).join("");
    $("total").textContent = `${data.count} registro(s)`; $("paginador").innerHTML = `<button class="btn btn-texto" ${data.previous ? "" : "disabled"} id="anterior">Anterior</button><span>Página ${pagina}</span><button class="btn btn-texto" ${data.next ? "" : "disabled"} id="siguiente">Siguiente</button>`;
    $("anterior").onclick = () => { pagina--; cargar(); }; $("siguiente").onclick = () => { pagina++; cargar(); };
    document.querySelectorAll(".editar").forEach(b => b.onclick = () => abrir(filas.find(r => String(r[cfg.pk]) === b.dataset.id)));
    document.querySelectorAll(".desactivar").forEach(b => b.onclick = () => desactivar(b.dataset.id));
  }
  async function cargarTodasLasPaginas(url) {
    const registros = [];
    let siguiente = url;
    while (siguiente) {
      const data = await api(siguiente);
      registros.push(...(data.results || []));
      siguiente = data.next;
    }
    return registros;
  }
  async function delegacionesActivas() {
    return cargarTodasLasPaginas("/api/delegaciones/?estado=activa&page_size=100");
  }
  async function territoriosActivos() {
    return cargarTodasLasPaginas("/api/territorios/?activo=true&page_size=100");
  }
  function campoFormulario(field, row, opciones) {
    const obligatorio = field[3] ? " *" : "";
    if (field[2] === "select") {
      const opcionesHtml = opciones.map(item => {
        const id = field[0] === "delegacion" ? item.id_delegacion : item.id_territorio;
        const texto = field[0] === "delegacion"
          ? `${item.codigo} · ${item.nombre}`
          : `${item.nombre} · ${item.delegacion_nombre}`;
        const seleccionado = row && Number(row[field[0]]) === Number(id) ? " selected" : "";
        return `<option value="${id}"${seleccionado}>${esc(texto)}</option>`;
      }).join("");
      const etiqueta = field[0] === "delegacion" ? "Seleccione una delegación" : "Seleccione un territorio";
      return `<label class="campo"><span>${field[1]}${obligatorio}</span><select name="${field[0]}" required><option value="">${etiqueta}</option>${opcionesHtml}</select></label>`;
    }
    return `<label class="campo"><span>${field[1]}${obligatorio}</span><input name="${field[0]}" type="${field[2]}" ${field[3] ? "required" : ""} ${field[2] === "checkbox" ? "" : "value=\"" + esc(row ? row[field[0]] : "") + "\""}>${field[2] === "checkbox" ? "<small>Marque para clasificarlo como formal</small>" : ""}</label>`;
  }
  async function abrir(row) {
    editando = row || null; $("modalTitulo").textContent = row ? "Editar" : "Nuevo";
    let opciones = [];
    if (entidad === "territorios" || entidad === "juntas-vecinos") {
      try {
        opciones = entidad === "territorios" ? await delegacionesActivas() : await territoriosActivos();
      }
      catch (error) { $("camposForm").innerHTML = `<p class="alerta">${esc(error.message)}</p>`; $("formulario").querySelector("button[type=submit]").disabled = true; $("modal").hidden = false; return; }
      if (!opciones.length) {
        const mensaje = entidad === "territorios"
          ? "Primero debe registrarse una delegación activa."
          : "Primero debe registrarse un territorio activo";
        $("camposForm").innerHTML = `<p class="alerta" role="alert">${mensaje}</p>`;
        $("formulario").querySelector("button[type=submit]").disabled = true; $("modal").hidden = false; return;
      }
    }
    $("formulario").querySelector("button[type=submit]").disabled = false;
    $("camposForm").innerHTML = cfg.fields.map(f => campoFormulario(f, row, opciones)).join("");
    cfg.fields.forEach(f => { if (f[2] === "checkbox") $(`formulario`).elements[f[0]].checked = row ? !!row[f[0]] : true; });
    const selector = $("formulario").elements.territorio;
    if (selector) {
      const guardar = $("formulario").querySelector("button[type=submit]");
      guardar.disabled = !selector.value;
      selector.addEventListener("change", () => { guardar.disabled = !selector.value; });
    }
    $("modal").hidden = false;
  }
  async function guardar(event) { event.preventDefault(); const data = {}; cfg.fields.forEach(f => { const input = $("formulario").elements[f[0]]; data[f[0]] = f[2] === "checkbox" ? input.checked : input.value || (f[2] === "number" ? null : ""); }); try { await api(editando ? `${cfg.url}${editando[cfg.pk]}/` : cfg.url, {method: editando ? "PATCH" : "POST", body: JSON.stringify(data)}); $("modal").hidden = true; cargar(); } catch (error) { if (window.Swal) Swal.fire("No se pudo guardar", error.message, "error"); else alert(error.message); } }
  async function desactivar(id) { if (window.Swal && !(await Swal.fire({title:"¿Desactivar registro?",icon:"warning",showCancelButton:true,confirmButtonText:"Desactivar"})).isConfirmed) return; try { await api(`${cfg.url}${id}/`, {method:"DELETE"}); cargar(); } catch (error) { alert(error.message); } }
  async function exportar() {
    const params = new URLSearchParams({page_size: 100});
    const search = $("buscar").value.trim(); const estado = $("filtroEstado").value;
    if (search) params.set("search", search); if (estado) params.set(cfg.estadoCampo, estado);
    try {
      const filasExportar = await cargarTodasLasPaginas(`${cfg.url}?${params}`);
      const encabezados = cfg.cols.map(columna => columna[1]);
      const filasFormateadas = filasExportar.map(fila => cfg.cols.map(columna => {
        const valor = fila[columna[0]];
        if (columna[0] === "es_formal" || columna[0] === "activo" || columna[0] === "activa") return valor ? "Sí" : "No";
        if (columna[0] === "estado") {
          return {"activo": "Activo", "inactivo": "Inactivo", "activa": "Activa", "inactiva": "Inactiva", true: "Activo", false: "Inactivo"}[valor] || valor;
        }
        return valor ?? "";
      }));
      const hoja = XLSX.utils.aoa_to_sheet([encabezados, ...filasFormateadas]);
      hoja["!cols"] = encabezados.map((encabezado, indice) => {
        const mayor = Math.max(
          String(encabezado).length,
          ...filasFormateadas.map(fila => String(fila[indice] ?? "").length)
        );
        return {wch: Math.min(Math.max(mayor + 2, 12), 40)};
      });
      const libro = XLSX.utils.book_new();
      XLSX.utils.book_append_sheet(libro, hoja, cfg.title.slice(0, 31)); XLSX.writeFile(libro, `${entidad}.xlsx`);
    } catch (error) { if (window.Swal) Swal.fire("No se pudo exportar", error.message, "error"); else alert(error.message); }
  }
  $("btnNuevo").onclick = () => abrir(); $("formulario").onsubmit = guardar; $("btnCancelar").onclick = $("modalCerrar").onclick = () => $("modal").hidden = true;
  $("btnExcel").onclick = exportar;
  $("buscar").oninput = () => { pagina = 1; cargar(); }; $("filtroEstado").onchange = () => { pagina = 1; cargar(); };
  $("btnLimpiar").onclick = () => { $("buscar").value = ""; $("filtroEstado").value = ""; pagina = 1; cargar(); };
  $("filtroEstado").innerHTML = '<option value="">Todos los estados</option>' + cfg.estados.map(estado => `<option value="${estado[0]}">${estado[1]}</option>`).join("");
  cargar();
}());
