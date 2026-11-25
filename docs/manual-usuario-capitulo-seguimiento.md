# Manual de usuario · Capítulo: Seguimiento de actividades

*Borrador de Brian para integrar en el manual de usuario (Sprint 3). Los recuadros «Captura» se completan con
pantallazos de la versión desplegada, con datos ficticios.*

## 1. Para qué sirve
Las actividades se ingresan en **Registrar actividad**. La pantalla **Seguimiento** permite llevar cada una hasta que se realiza:
a qué área corresponde, quién lo atiende, en qué estado va, para cuándo se comprometió y qué se ha conversado.
Las actividades **no se borran**: terminan en el estado «Realizado» y conservan su historial.

**Quién la usa:** el Funcionario y el Encargado de área (las suyas o las que les asignaron), el Delegado territorial (todas las de su delegación)
y el Administrador (todas).

Entrada: menú lateral → **Actividades → Seguimiento**.

> **Captura 1:** listado de actividades con las tarjetas de resumen.

## 2. El listado
- **Tarjetas de resumen:** cuántas actividades hay en total, por estado y cuántas están **vencidas**. Al hacer clic filtran el listado.
- **Buscar y filtrar:** por texto (descripción, vecino, RUT, ítem, funcionario), estado, prioridad y vencimiento.
- **Ordenar:** clic en el encabezado de la columna (fecha de registro, estado, prioridad, compromiso).
- **Vencidas:** la fila tiene un borde rojo, fondo rosado y la etiqueta **«Vencida · N días»**. Una actividad está vencida cuando su
  fecha de compromiso ya pasó y todavía no está «Realizado».
- **Exportar a Excel:** descarga lo que muestran los filtros actuales.

> **Captura 2:** fila vencida resaltada.

## 3. Registrar una actividad (HU01)
Se hace desde **Actividades → Registrar actividad** (ver el capítulo de ingreso de actividades). Al guardarla nace en estado «Ingresado» y aparece en **Seguimiento**.

## 4. Ver y dar seguimiento
Botón **Ver** abre el detalle a la derecha, con los datos, las acciones disponibles, las fotos, los comentarios y el historial.

### 4.1 Asignar a un área (HU02) — Administrador y Delegado
**Asignar área** → elige el **área**, la **prioridad** (alta, media o baja) y, si quieres, un **responsable** (solo aparecen funcionarios
de esa delegación y de esa área o de cargo transversal). Se puede reasignar mientras la actividad esté abierta.

### 4.2 Cambiar el estado (HU03)
**Cambiar estado** → elige el nuevo estado. Recorrido: *Ingresado → Pendiente / En proceso → Realizado*; entre «Pendiente» y «En proceso» se
puede ir y volver. **«Realizado» es final**: la actividad queda cerrada. Cada cambio guarda quién y cuándo en el historial.

### 4.3 Fecha de compromiso (HU06)
**Fecha de compromiso** → elige una fecha de hoy en adelante. Cada cambio queda en el historial con la fecha anterior, la nueva, quién y cuándo.

### 4.4 Motivo de atraso (HU05)
Si la actividad está **vencida**, para cambiar el estado o la fecha tienes que escribir el **motivo del atraso** (entre 10 y 255 caracteres).
Si ya tenía un motivo registrado, no se vuelve a pedir. También puedes registrarlo o corregirlo con **Motivo de atraso**.

> **Captura 4:** cambio de estado en una actividad vencida pidiendo el motivo.

### 4.5 Evidencia fotográfica (HU04)
En **Evidencia fotográfica** elige una foto **JPG, PNG o WEBP de hasta 5 MB** y pulsa **Subir foto**. El sistema le asigna un
**código verificador** (3 letras y 3 números, por ejemplo ORC711) que aparece bajo la miniatura. Las fotos solo las ven quienes
pueden ver la actividad.

### 4.6 Comentarios (HU08)
Escribe en **Nuevo comentario** (hasta 1000 caracteres) y pulsa **Comentar**. Se muestran en orden con el nombre, el cargo y la hora de quien
comentó. **No se pueden editar ni borrar.** Se puede comentar incluso cuando la actividad ya está realizada.

> **Captura 5:** detalle de una actividad con fotos, comentarios e historial.

## 5. Problemas frecuentes
| Qué ves | Qué significa | Qué hacer |
|---|---|---|
| «La actividad ya está realizada y no admite más cambios.» | «Realizado» cierra la actividad. | Agrega un comentario; si fue un error, avisa al Administrador. |
| «La actividad está vencida: indica el motivo del atraso…» | Pasó la fecha de compromiso. | Escribe el motivo (mín. 10 caracteres). |
| «La actividad está aprobada y no se puede modificar.» | La verificación ya la aprobó. | Solo se puede comentar. |
| «Sube una foto en formato JPG, PNG o WEBP.» / «no puede pesar más de 5 MB» | El archivo no es una foto válida o es muy grande. | Convierte o reduce la imagen. |
| No aparece una actividad | Un Funcionario solo ve las que escribió o le asignaron. | Pide al Delegado que te la asigne. |
| El botón «Asignar área» no aparece | Solo lo tienen el Administrador y el Delegado. | Pide la asignación a tu delegado. |
