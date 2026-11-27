# Evaluación 3 · HU20 y HU22

## Alcance y fuentes

Este anexo complementa el plan de pruebas existente (`docs/plan-de-pruebas-terriia.xlsx`)
con trazabilidad y resultados de HU20/HU22. La referencia de requisitos es la guía oficial
`III_Evaluacion_Proyecto_Integrado_SGR.pdf` y los criterios de aceptación de ambas historias.
La guía oficial no está almacenada en el repositorio.

El anexo cubre el protocolo técnico, los indicadores, la matriz de trazabilidad, la comparación
de resultados esperados y observados, y el registro de defectos y reejecuciones. Los valores
marcados como pendientes no son resultados aprobados. No se midió cobertura de líneas.

La guía organiza la evaluación en cinco actividades. Este anexo aporta evidencia para los aspectos
de pruebas y trazabilidad; no sustituye las demás actividades ni afirma evidencias que no se
generaron. Se alinea con los criterios 3.1.5.9 (trazabilidad/cobertura), 3.1.5.10
(ejecución/evidencia), 3.1.5.11 (defectos, correcciones y reejecuciones) y 3.1.6.12
(comparación de resultados esperados y obtenidos). La actividad 4 representa 30 puntos y la
actividad 5, 25 puntos, según la guía.

## HU20 · Reporte histórico exportable

La implementación y el detalle de reglas, permisos, campos, pruebas y resultados de HU20 se
mantienen en [reporte-historico-hu20.md](reporte-historico-hu20.md). La fecha de resolución
utilizada es `Actividad.fecha_estado`; el estado resuelto es `Realizado`. Los registros
`Realizado` sin fecha de resolución no pueden asociarse a un período y quedan fuera del archivo;
el XLSX informa su conteo para la delegación.

La exportación es un libro `.xlsx` OpenXML generado en el servidor con bibliotecas estándar de
Python. La interfaz descarga la respuesta como archivo, sin dependencia de SheetJS ni de una CDN.
El contrato de prueba verifica el ZIP, sus partes XML, el tipo de contenido, las cabeceras, los
filtros y las filas. No se afirma que el archivo se haya abierto en Microsoft Excel o LibreOffice.

## HU22 · Dashboard ejecutivo consolidado

### Reglas implementadas

- La pantalla es `GET /metas/dashboard-ejecutivo/`; el endpoint es
  `GET /api/dashboard/ejecutivo/`. Ambos limitan el acceso a Alcaldesa y Administrador.
- El endpoint utiliza `_periodo_del_dashboard`: acepta `?periodo=<id>` y, si no se entrega,
  utiliza el período vigente. Un valor no numérico produce HTTP 400; uno inexistente, HTTP 404;
  no tener período vigente produce HTTP 400.
- Se recorren todas las delegaciones registradas, incluidas las inactivas. Solo se calculan
  funcionarios con estado `activo`. Una delegación sin funcionarios activos presenta 0.00%.
- El cálculo individual se delega a `CalculoMetasService.calcular_cumplimiento_funcionario`,
  reutilizando actividades aprobadas que ponderan y el tope computable de 150%.
- El porcentaje esperado es el del servicio existente: días transcurridos inclusivos divididos
  por días computables, limitado al total del período.
- El semáforo reutiliza los umbrales existentes: verde si cumplimiento >= esperado; ámbar si
  cumplimiento >= 80% del esperado; rojo en otro caso.
- El cumplimiento global es la media aritmética del cumplimiento computable de todos los
  funcionarios activos del municipio. Equivale a ponderar el promedio de cada delegación por su
  cantidad de funcionarios activos. No se muestran esos conteos.
- La respuesta contiene período, cumplimiento global, esperado y una fila agregada por
  delegación (id, código, nombre, promedio y semáforo). No incluye funcionarios, áreas, vecinos,
  actividades ni solicitudes individuales. La pantalla presenta los mismos agregados.
- El tope computable es de 150% y está unificado en una sola constante
  (`TOPE_CUMPLIMIENTO` en `metas/cumplimiento.py`), usada tanto por el cálculo por ítem como por
  `CalculoMetasService` y los dashboards (incluido HU22).

### Archivos técnicos

- API y cálculo: `metas/views.py`, `metas/services.py`, `metas/urls.py`.
- Pantalla y navegación: `metas/pantallas.py`, `metas/urls_pantallas.py`,
  `metas/templates/metas/dashboard_ejecutivo.html`,
  `metas/static/metas/css/dashboard_ejecutivo.css`,
  `metas/static/metas/js/dashboard_ejecutivo.js`, `territorio/pantallas.py`.
- Pruebas: `metas/tests/test_dashboard_ejecutivo.py`.
- HU20: detalle técnico en `docs/reporte-historico-hu20.md`.
- Índice y estado del proyecto: `README.md`.

### Protocolo de pruebas

Ejecutar en el entorno de desarrollo con el intérprete Python del proyecto:

```powershell
.\venv\Scripts\python.exe manage.py test atenciones.tests.test_reporte_historico
.\venv\Scripts\python.exe manage.py test metas.tests.test_dashboard_ejecutivo metas.tests.test_dashboard_permisos metas.tests.test_calculo_metas
.\venv\Scripts\python.exe manage.py check
node --check atenciones\static\atenciones\js\reporte_historico.js
node --check metas\static\metas\js\dashboard_ejecutivo.js
.\venv\Scripts\python.exe -m black --check metas\services.py metas\views.py metas\urls.py metas\pantallas.py metas\urls_pantallas.py metas\tests\test_dashboard_ejecutivo.py atenciones\reportes.py atenciones\tests\test_reporte_historico.py territorio\pantallas.py
git diff --check
```

Los casos automatizados cubren respuestas positivas y negativas, permisos, filtros, delegaciones
sin personal activo, exclusión de personal inactivo, estructura del archivo XLSX, umbrales del
semáforo y ausencia de campos personales en HU22. La suite general `manage.py test` es una
validación adicional y no sustituye los casos enfocados.

## Matriz de trazabilidad

| Requisito | Interfaz/API y regla | Prueba automatizada |
|---|---|---|
| HU20: filtrar por delegación | `GET /api/reportes/solicitudes-resueltas/`; delegación del funcionario | `test_jefe_recibe_solo_resueltas_de_la_delegacion_y_periodo` |
| HU20: filtrar por período | Rango inclusivo de `fecha_estado` | `test_jefe_recibe_solo_resueltas_de_la_delegacion_y_periodo`; `test_rechaza_filtros_invalidos` |
| HU20: incluir solo resueltas | `estado=Realizado`, actividades y gestiones sociales | `test_jefe_recibe_solo_resueltas_de_la_delegacion_y_periodo` |
| HU20: exportar formato estándar | Pantalla de reporte y libro `.xlsx` OpenXML descargable | `test_xlsx_es_un_archivo_openxml_valido`; `test_pantalla_presenta_filtros_y_descarga_excel` |
| HU20: permisos | Administrador y Jefe de delegaciones en API y pantalla | `test_solo_administrador_y_jefe_pueden_consultar_opciones_y_reporte`; `test_solo_administrador_y_jefe_ven_la_pantalla` |
| HU20: excluir registros fuera de filtros | Filtrado en consulta antes de serializar/generar el archivo | `test_jefe_recibe_solo_resueltas_de_la_delegacion_y_periodo` |
| HU22: cumplimiento global | Promedio de cumplimiento computable de funcionarios activos | `test_consolida_global_y_por_delegacion_sin_datos_individuales` |
| HU22: cumplimiento y semáforo por delegación | Todas las delegaciones; fórmula y umbrales de `CalculoMetasService` | `test_consolida_global_y_por_delegacion_sin_datos_individuales`; `test_semaforo_conserva_limites_del_servicio_existente` |
| HU22: proteger información individual | Respuesta de agregados con campos limitados; interfaz sin filas individuales | `test_consolida_global_y_por_delegacion_sin_datos_individuales`; `test_pantalla_solo_es_visible_para_alcaldesa_y_administrador` |
| HU22: permisos y período | Alcaldesa/Administrador; validación del período compartida | `test_alcaldesa_y_administrador_pueden_consultar_api`; `test_roles_no_autorizados_reciben_403`; `test_periodo_invalido_o_inexistente_se_rechaza`; `test_pantalla_solo_es_visible_para_alcaldesa_y_administrador` |

## Indicadores

| Indicador | Cálculo | Resultado observado |
|---|---|---|
| Casos enfocados aprobados HU20 | Casos OK / casos ejecutados en `atenciones.tests.test_reporte_historico` | 9/9 en la última ejecución |
| Casos enfocados aprobados HU22 | Casos HU22 OK / 7 pruebas de `metas.tests.test_dashboard_ejecutivo` | 7/7 aprobadas dentro de una ejecución dirigida de 22 pruebas; incluyó además regresiones del dashboard y el servicio de cálculo |
| Cobertura de código | Medición con herramienta de cobertura | No medida; no presentar como porcentaje |
| Django system check | Hallazgos reportados por `manage.py check` | Sin problemas en la última ejecución |
| Validez del libro de HU20 | ZIP íntegro y XML de partes OpenXML parseable | Verificado por prueba automatizada; no abierto en una aplicación de hojas de cálculo |

## Comparación esperado/observado

| Historia/caso | Resultado esperado | Resultado observado |
|---|---|---|
| HU20: filtros y acceso | Solo filas resueltas de la delegación/período; filtros inválidos rechazados; roles no permitidos reciben 403 | Pruebas HU20: 9 ejecutadas, OK |
| HU20: exportación | Respuesta descargable `.xlsx` con partes XML válidas y solo datos filtrados | Prueba valida tipo, cabeceras, ZIP/XML y contenido; no se ejecutó descarga visual desde navegador |
| HU22: agregado | Porcentaje global y filas de todas las delegaciones, promediando funcionarios activos | Prueba automatizada aprobada: promedio global ponderado por funcionarios, delegaciones sin funcionarios activos y delegación inactiva incluidos |
| HU22: semáforos | Umbrales verdes/ámbar/rojo idénticos al servicio existente | Pruebas automatizadas aprobadas para verde, ámbar y rojo y resultados por delegación |
| HU22: privacidad y permisos | Sin individuos, áreas ni solicitudes; solo Alcaldesa/Administrador autorizados | Pruebas automatizadas aprobadas para roles permitidos y denegados, pantalla y forma de respuesta sin datos personales |

## Defectos, correcciones y reejecuciones

| Hallazgo | Corrección | Reejecución/resultado |
|---|---|---|
| El test inicial de HU20 intentó leer `.data` de una respuesta HTTP de archivo, que expone `content` | La aserción de error ahora inspecciona el contenido de respuesta | `atenciones.tests.test_reporte_historico`: 9 pruebas, OK |
| La implementación inicial de Excel dependía de SheetJS desde CDN, que no está disponible en el entorno de evaluación | La generación pasó al servidor con OpenXML y el navegador descarga el Blob de la respuesta | Validación estructural automatizada del `.xlsx`; descarga en navegador no ejecutada |
| Un test de pantalla HU22 buscó la URL API en el HTML aunque el endpoint se configura en el JavaScript local | Se ajustó la aserción para comprobar la inclusión del script local; la ruta API se comprueba por pruebas de endpoint | Suite dirigida: 22 pruebas, OK |
| La pantalla HU22 apuntaba a `/api/metas/dashboard/ejecutivo/`, pero Django registra `/api/dashboard/ejecutivo/` | La plantilla ahora inyecta la URL con `{% url 'dashboard-ejecutivo' %}` y el JavaScript la consume | 7 pruebas HU22, OK; suite completa posterior: 545 pruebas, OK |

### Ejecuciones registradas

- `.\venv\Scripts\python.exe manage.py test atenciones.tests.test_reporte_historico`:
  **9 pruebas, OK**.
- `.\venv\Scripts\python.exe manage.py test metas.tests.test_dashboard_ejecutivo metas.tests.test_dashboard_permisos metas.tests.test_calculo_metas`:
  **22 pruebas, OK** en 194.883 segundos.
- Tras corregir la URL consumida por la pantalla, `.\venv\Scripts\python.exe manage.py test metas.tests.test_dashboard_ejecutivo`:
  **7 pruebas, OK** en 0.504 segundos.
- `manage.py shell` resolvió `dashboard-ejecutivo` como `/api/dashboard/ejecutivo/` y
  `metas_dashboard_ejecutivo` como `/metas/dashboard-ejecutivo/`; la plantilla usa la ruta
  resuelta, no una URL duplicada en JavaScript.
- `.\venv\Scripts\python.exe manage.py check`: **sin problemas**.
- `node --check atenciones\static\atenciones\js\reporte_historico.js` y
  `node --check metas\static\metas\js\dashboard_ejecutivo.js`: **OK, sin salida**.
- `.\venv\Scripts\python.exe -m black --check` sobre los nueve archivos Python listados en el
  protocolo: **OK, los nueve sin cambios requeridos**.
- `git diff --check`: **OK, sin errores de espacios**.

Después de corregir la vinculación de la ruta API, la suite general
`& .\venv\Scripts\python.exe manage.py test` terminó con **545 pruebas, OK** en 1189.837 segundos.
El runner también informó que no hubo problemas del system check.

No se registran evidencias manuales ni resultados de navegador que no hayan sido ejecutados. Para
la defensa, conservar la salida real de los comandos de protocolo y, si se requiere evidencia
visual o apertura en Excel/LibreOffice, agregarla solo después de ejecutarla.
