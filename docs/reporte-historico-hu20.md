# HU20 · Reporte histórico exportable de solicitudes resueltas

## Alcance implementado

El reporte usa `Actividad`, que contiene tanto actividades como gestiones sociales (`tipo_registro`).
Incluye registros cuyo estado operativo es `Realizado`; no filtra por `estado_verificacion`, que
es independiente del avance operativo.

La fecha usada para delimitar el período es `Actividad.fecha_estado`, que registra el cambio de
estado y permite filtrar por fecha local de forma inclusiva. No se usa la fecha de ocurrencia
(`fecha`) como sustituto de la fecha de resolución.

Los registros `Realizado` sin `fecha_estado` no se asignan a un período. La API los cuenta y la
pantalla informa cuántos quedaron fuera del archivo por no tener una fecha de resolución fiable.
Esta limitación de datos debe revisarse si la cuenta es mayor que cero en el entorno de evaluación.

El archivo contiene código, tipo de registro, código y nombre de delegación, ítem y fecha de
resolución. No incluye nombres de funcionarios, vecinos, teléfonos ni descripciones.

## Acceso y rutas

Solo los roles Administrador y Jefe de delegaciones pueden consultar el reporte y sus opciones.
La pantalla y ambas rutas API verifican el rol en el servidor.

| Uso | Método y ruta |
|---|---|
| Pantalla de filtros y exportación | `GET /atenciones/reportes/solicitudes-resueltas/` |
| Delegaciones disponibles (incluidas las inactivas para consulta histórica) | `GET /api/reportes/solicitudes-resueltas/delegaciones/` |
| Datos filtrados del reporte | `GET /api/reportes/solicitudes-resueltas/?delegacion=<id>&desde=<YYYY-MM-DD>&hasta=<YYYY-MM-DD>` |

El endpoint valida que ambas fechas tengan formato ISO, que la delegación exista y que `desde` no
sea posterior a `hasta`. Responde una lista vacía con `total: 0` si no hay resultados. El período
filtra por `fecha_estado`; delegación, estado y fecha se aplican en el servidor.

El endpoint genera y devuelve un libro `.xlsx` OpenXML en el servidor usando `zipfile` y
`xml.etree.ElementTree` de la biblioteca estándar de Python. La pantalla descarga la respuesta
como archivo mediante `Blob` y enlaces temporales del navegador. La solución no depende de
SheetJS, de una CDN ni de una dependencia Python nueva.

## Trazabilidad de HU20

| Criterio | Implementación | Verificación |
|---|---|---|
| Filtrar por delegación | `funcionario__delegacion` en el queryset del reporte | Prueba que otra delegación queda excluida |
| Filtrar por período | Rango inclusivo sobre `fecha_estado` | Prueba que fechas fuera del período quedan excluidas |
| Incluir solicitudes resueltas | `estado=Actividad.REALIZADO`; se incluyen ambos tipos de registro | Prueba de reporte filtrado y etiqueta de tipo |
| Exportar a Excel | El endpoint genera un archivo `.xlsx` con los datos filtrados; la pantalla descarga la respuesta | Prueba inspecciona el ZIP, las partes XML, las cabeceras y los datos filtrados |
| Respetar permisos | API y pantalla limitadas a Administrador y Jefe de delegaciones | Pruebas positivas y denegación para otros roles |
| No incluir solicitudes fuera de filtros | La API compone los filtros antes de serializar | Prueba verifica el código exacto incluido |

## Casos de prueba y resultado esperado/obtenido

| Caso | Resultado esperado | Resultado observado |
|---|---|---|
| Jefe consulta por delegación y fechas | Solo solicitudes `Realizado` con `fecha_estado` dentro del período y delegación solicitada; sin datos personales individuales | Aprobado en prueba automatizada |
| Período sin coincidencias | Archivo `.xlsx` válido, sin filas de solicitudes y cabecera `X-Total-Registros: 0` | Aprobado en prueba automatizada |
| Fechas inválidas, invertidas o delegación inexistente | HTTP 400 con el campo inválido | Aprobado en prueba automatizada |
| Permisos | Administrador/Jefe reciben HTTP 200; Delegado/Alcaldesa/Funcionario reciben HTTP 403 | Aprobado en prueba automatizada |
| Opciones de delegación | Incluye delegaciones activas e inactivas para búsqueda histórica | Aprobado en prueba automatizada |
| Pantalla y menú | Solo roles autorizados pueden abrir la pantalla; el Jefe ve el enlace | Aprobado en prueba automatizada |
| Respuesta de exportación | El cliente recibe un archivo Excel OpenXML descargable con nombre y tipo correctos | Aprobado en pruebas: respuesta binaria, ZIP íntegro, partes XML parseables, nombre y contenido filtrado |

### Ejecuciones registradas

- `.\venv\Scripts\python.exe manage.py test atenciones.tests.test_reporte_historico`:
  **9 pruebas, OK**.
- `.\venv\Scripts\python.exe manage.py check`: **sin problemas**.
- `& .\venv\Scripts\python.exe manage.py test`: **545 pruebas, OK** en 1189.837 segundos, tras la corrección final de ruta HU22.
- `node --check atenciones\static\atenciones\js\reporte_historico.js`: **OK, sin salida**.
- `.\venv\Scripts\python.exe -m black --check atenciones\reportes.py atenciones\tests\test_reporte_historico.py`:
  **OK, ambos archivos sin cambios requeridos**.
- `git diff --check`: **OK, sin errores de espacios**.

La prueba automatizada recibe y valida un archivo `.xlsx` real en la respuesta HTTP y el JavaScript
lo ofrece al navegador como descarga. No se ejecutó una comprobación visual en navegador ni se
abrió el libro en Excel o LibreOffice; esas comprobaciones no se afirman como realizadas.

La cobertura de líneas no se midió. Las 9 pruebas enfocadas de HU20 no deben presentarse como
cobertura porcentual del código.

## Archivos de implementación

- `atenciones/reportes.py`
- `atenciones/urls.py`
- `atenciones/urls_pantallas.py`
- `atenciones/pantallas.py`
- `atenciones/templates/atenciones/reporte_historico.html`
- `atenciones/static/atenciones/css/reporte_historico.css`
- `atenciones/static/atenciones/js/reporte_historico.js`
- `atenciones/tests/test_reporte_historico.py`
- `territorio/pantallas.py` (enlace de navegación para el rol autorizado)
