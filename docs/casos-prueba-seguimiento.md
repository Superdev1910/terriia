# Casos de prueba · Seguimiento de actividades (HU02 a HU08) · Brian

Resumen de las pruebas automatizadas del seguimiento, que viven en `atenciones/tests/test_seguimiento_*.py`
(72 casos; se corren con `python manage.py test atenciones`), ordenadas por historia de usuario, con las columnas
ID · Nombre · Tipo · Prueba en código · Estado para pasarlas al plan `docs/plan-de-pruebas-terriia.xlsx` (ahí se agregan además
Responsable = Brian, Fecha y Resultado esperado/obtenido).

**HU01 (SCRUM-8, registrar) y la subida de evidencia (HU04)** ya existían en `atenciones` (SCRUM-62 y SCRUM-123, de Patricio) con sus propias pruebas:
`test_actividad.py` y `test_verificacion.py`. Aquí solo se listan las pruebas de lo que agrega el seguimiento.

**Pendiente de registrar a mano** (no se puede automatizar aquí): la captura de pantalla de cada ejecución en el navegador y pasar
estas filas al Excel del plan de pruebas.

Tipo: **Caja negra** = prueba contra la API o la pantalla, por rol. Cada HU incluye casos normales, de borde y de acceso denegado.

## HU02 · Asignar a un área · historia SCRUM-9 · subtareas SCRUM-70 (desarrollo) y SCRUM-71 (pruebas y manual)

| ID | Nombre | Tipo | Prueba en código | Estado |
|---|---|---|---|---|
| PU-SEG-ASG-01 | Delegado asigna area prioridad y responsable | Caja negra | `atenciones/tests/test_seguimiento_asignacion.py` · AsignarAreaTests.test_delegado_asigna_area_prioridad_y_responsable | Aprobada |
| PU-SEG-ASG-02 | Responsable es opcional | Caja negra | `atenciones/tests/test_seguimiento_asignacion.py` · AsignarAreaTests.test_responsable_es_opcional | Aprobada |
| PU-SEG-ASG-03 | Se puede reasignar | Caja negra | `atenciones/tests/test_seguimiento_asignacion.py` · AsignarAreaTests.test_se_puede_reasignar | Aprobada |
| PU-SEG-ASG-04 | Area y prioridad son obligatorias | Caja negra | `atenciones/tests/test_seguimiento_asignacion.py` · AsignarAreaTests.test_area_y_prioridad_son_obligatorias | Aprobada |
| PU-SEG-ASG-05 | Area de otra delegacion se rechaza | Caja negra | `atenciones/tests/test_seguimiento_asignacion.py` · AsignarAreaTests.test_area_de_otra_delegacion_se_rechaza | Aprobada |
| PU-SEG-ASG-06 | Area inactiva se rechaza | Caja negra | `atenciones/tests/test_seguimiento_asignacion.py` · AsignarAreaTests.test_area_inactiva_se_rechaza | Aprobada |
| PU-SEG-ASG-07 | Responsable debe ser de la delegacion activo y del area | Caja negra | `atenciones/tests/test_seguimiento_asignacion.py` · AsignarAreaTests.test_responsable_debe_ser_de_la_delegacion_activo_y_del_area | Aprobada |
| PU-SEG-ASG-08 | Cargo transversal puede ser responsable de cualquier area | Caja negra | `atenciones/tests/test_seguimiento_asignacion.py` · AsignarAreaTests.test_cargo_transversal_puede_ser_responsable_de_cualquier_area | Aprobada |
| PU-SEG-ASG-09 | El area debe coincidir con el tipo de atencion | Caja negra | `atenciones/tests/test_seguimiento_asignacion.py` · AsignarAreaTests.test_el_area_debe_coincidir_con_el_tipo_de_atencion | Aprobada |
| PU-SEG-ASG-10 | Solicitud realizada no se reasigna | Caja negra | `atenciones/tests/test_seguimiento_asignacion.py` · AsignarAreaTests.test_solicitud_realizada_no_se_reasigna | Aprobada |
| PU-SEG-ASG-11 | Funcionario no puede asignar | Caja negra | `atenciones/tests/test_seguimiento_asignacion.py` · AsignarAreaTests.test_funcionario_no_puede_asignar | Aprobada |
| PU-SEG-ASG-12 | Delegado de otra delegacion no puede asignar | Caja negra | `atenciones/tests/test_seguimiento_asignacion.py` · AsignarAreaTests.test_delegado_de_otra_delegacion_no_puede_asignar | Aprobada |

## HU03 · Cambiar estado con historial · historia SCRUM-10 · subtareas SCRUM-72 y SCRUM-73

| ID | Nombre | Tipo | Prueba en código | Estado |
|---|---|---|---|---|
| PU-SEG-EST-01 | Cambio guarda fecha usuario historial y auditoria | Caja negra | `atenciones/tests/test_seguimiento_estado.py` · CambiarEstadoTests.test_cambio_guarda_fecha_usuario_historial_y_auditoria | Aprobada |
| PU-SEG-EST-02 | Flujo completo deja un registro por cambio | Caja negra | `atenciones/tests/test_seguimiento_estado.py` · CambiarEstadoTests.test_flujo_completo_deja_un_registro_por_cambio | Aprobada |
| PU-SEG-EST-03 | Transiciones invalidas | Caja negra | `atenciones/tests/test_seguimiento_estado.py` · CambiarEstadoTests.test_transiciones_invalidas | Aprobada |
| PU-SEG-EST-04 | Realizado es final | Caja negra | `atenciones/tests/test_seguimiento_estado.py` · CambiarEstadoTests.test_realizado_es_final | Aprobada |
| PU-SEG-EST-05 | Historial se lista con usuario y fechas | Caja negra | `atenciones/tests/test_seguimiento_estado.py` · CambiarEstadoTests.test_historial_se_lista_con_usuario_y_fechas | Aprobada |
| PU-SEG-EST-06 | Responsable y delegado pueden cambiar estado otros no | Caja negra | `atenciones/tests/test_seguimiento_estado.py` · CambiarEstadoTests.test_responsable_y_delegado_pueden_cambiar_estado_otros_no | Aprobada |
| PU-SEG-EST-07 | Sin estado en la peticion | Caja negra | `atenciones/tests/test_seguimiento_estado.py` · CambiarEstadoTests.test_sin_estado_en_la_peticion | Aprobada |

## HU04 · Evidencia fotográfica (lo que agrega el seguimiento) · historia SCRUM-11 · subtareas SCRUM-74 y SCRUM-75

| ID | Nombre | Tipo | Prueba en código | Estado |
|---|---|---|---|---|
| PU-SEG-EVI-01 | Responsable sube y descarga | Caja negra | `atenciones/tests/test_seguimiento_alcance.py` · EvidenciaDelResponsableTests.test_responsable_sube_y_descarga | Aprobada |
| PU-SEG-EVI-02 | Otro funcionario no sube ni descarga | Caja negra | `atenciones/tests/test_seguimiento_alcance.py` · EvidenciaDelResponsableTests.test_otro_funcionario_no_sube_ni_descarga | Aprobada |

## HU05 · Motivo de atraso obligatorio · historia SCRUM-12 · subtareas SCRUM-76 y SCRUM-77

| ID | Nombre | Tipo | Prueba en código | Estado |
|---|---|---|---|---|
| PU-SEG-ATR-01 | Vencida exige motivo para cambiar estado | Caja negra | `atenciones/tests/test_seguimiento_estado.py` · MotivoDeAtrasoTests.test_vencida_exige_motivo_para_cambiar_estado | Aprobada |
| PU-SEG-ATR-02 | Motivo muy corto se rechaza | Caja negra | `atenciones/tests/test_seguimiento_estado.py` · MotivoDeAtrasoTests.test_motivo_muy_corto_se_rechaza | Aprobada |
| PU-SEG-ATR-03 | Con motivo cambia y guarda ambos en historial | Caja negra | `atenciones/tests/test_seguimiento_estado.py` · MotivoDeAtrasoTests.test_con_motivo_cambia_y_guarda_ambos_en_historial | Aprobada |
| PU-SEG-ATR-04 | Si ya hay motivo no se pide de nuevo | Caja negra | `atenciones/tests/test_seguimiento_estado.py` · MotivoDeAtrasoTests.test_si_ya_hay_motivo_no_se_pide_de_nuevo | Aprobada |
| PU-SEG-ATR-05 | No vencida no pide motivo | Caja negra | `atenciones/tests/test_seguimiento_estado.py` · MotivoDeAtrasoTests.test_no_vencida_no_pide_motivo | Aprobada |
| PU-SEG-ATR-06 | Endpoint motivo atraso | Caja negra | `atenciones/tests/test_seguimiento_estado.py` · MotivoDeAtrasoTests.test_endpoint_motivo_atraso | Aprobada |
| PU-SEG-ATR-07 | Motivo atraso solo si hay atraso | Caja negra | `atenciones/tests/test_seguimiento_estado.py` · MotivoDeAtrasoTests.test_motivo_atraso_solo_si_hay_atraso | Aprobada |
| PU-SEG-ATR-08 | Realizada con atraso permite registrar el motivo despues | Caja negra | `atenciones/tests/test_seguimiento_estado.py` · MotivoDeAtrasoTests.test_realizada_con_atraso_permite_registrar_el_motivo_despues | Aprobada |

## HU06 · Fecha de compromiso con historial · historia SCRUM-34 · subtareas SCRUM-78 y SCRUM-79

| ID | Nombre | Tipo | Prueba en código | Estado |
|---|---|---|---|---|
| PU-SEG-FEC-01 | Fijar la fecha registra historial y auditoria | Caja negra | `atenciones/tests/test_seguimiento_fecha_compromiso.py` · FechaCompromisoTests.test_fijar_la_fecha_registra_historial_y_auditoria | Aprobada |
| PU-SEG-FEC-02 | Cada cambio conserva el valor anterior | Caja negra | `atenciones/tests/test_seguimiento_fecha_compromiso.py` · FechaCompromisoTests.test_cada_cambio_conserva_el_valor_anterior | Aprobada |
| PU-SEG-FEC-03 | No acepta fecha pasada ni la misma fecha ni formato invalido | Caja negra | `atenciones/tests/test_seguimiento_fecha_compromiso.py` · FechaCompromisoTests.test_no_acepta_fecha_pasada_ni_la_misma_fecha_ni_formato_invalido | Aprobada |
| PU-SEG-FEC-04 | Hoy es valido | Caja negra | `atenciones/tests/test_seguimiento_fecha_compromiso.py` · FechaCompromisoTests.test_hoy_es_valido | Aprobada |
| PU-SEG-FEC-05 | Postergar una vencida exige motivo | Caja negra | `atenciones/tests/test_seguimiento_fecha_compromiso.py` · FechaCompromisoTests.test_postergar_una_vencida_exige_motivo | Aprobada |
| PU-SEG-FEC-06 | Solicitud realizada no cambia de fecha | Caja negra | `atenciones/tests/test_seguimiento_fecha_compromiso.py` · FechaCompromisoTests.test_solicitud_realizada_no_cambia_de_fecha | Aprobada |
| PU-SEG-FEC-07 | Permisos por rol y delegacion | Caja negra | `atenciones/tests/test_seguimiento_fecha_compromiso.py` · FechaCompromisoTests.test_permisos_por_rol_y_delegacion | Aprobada |

## HU07 · Resaltado de vencidas · historia SCRUM-35 · subtareas SCRUM-80 y SCRUM-81

| ID | Nombre | Tipo | Prueba en código | Estado |
|---|---|---|---|---|
| PU-SEG-VEN-01 | Propiedad vencida y dias de atraso | Caja negra | `atenciones/tests/test_seguimiento_fecha_compromiso.py` · VencidasTests.test_propiedad_vencida_y_dias_de_atraso | Aprobada |
| PU-SEG-VEN-02 | Realizada con atraso cuenta los dias hasta el cierre | Caja negra | `atenciones/tests/test_seguimiento_fecha_compromiso.py` · VencidasTests.test_realizada_con_atraso_cuenta_los_dias_hasta_el_cierre | Aprobada |
| PU-SEG-VEN-03 | La api marca la solicitud vencida | Caja negra | `atenciones/tests/test_seguimiento_fecha_compromiso.py` · VencidasTests.test_la_api_marca_la_solicitud_vencida | Aprobada |
| PU-SEG-VEN-04 | Filtro vencida true y false | Caja negra | `atenciones/tests/test_seguimiento_fecha_compromiso.py` · VencidasTests.test_filtro_vencida_true_y_false | Aprobada |
| PU-SEG-VEN-05 | Orden por fecha de compromiso | Caja negra | `atenciones/tests/test_seguimiento_fecha_compromiso.py` · VencidasTests.test_orden_por_fecha_de_compromiso | Aprobada |
| PU-SEG-VEN-06 | Resumen cuenta estados y vencidas | Caja negra | `atenciones/tests/test_seguimiento_fecha_compromiso.py` · VencidasTests.test_resumen_cuenta_estados_y_vencidas | Aprobada |
| PU-SEG-VEN-07 | Resumen respeta el alcance | Caja negra | `atenciones/tests/test_seguimiento_fecha_compromiso.py` · VencidasTests.test_resumen_respeta_el_alcance | Aprobada |

## HU08 · Comentarios en cada tarea · historia SCRUM-36 · subtareas SCRUM-82 y SCRUM-83

| ID | Nombre | Tipo | Prueba en código | Estado |
|---|---|---|---|---|
| PU-SEG-COM-01 | Comentar guarda autor fecha y auditoria | Caja negra | `atenciones/tests/test_seguimiento_comentarios.py` · ComentariosTests.test_comentar_guarda_autor_fecha_y_auditoria | Aprobada |
| PU-SEG-COM-02 | Se listan en orden cronologico con varios autores | Caja negra | `atenciones/tests/test_seguimiento_comentarios.py` · ComentariosTests.test_se_listan_en_orden_cronologico_con_varios_autores | Aprobada |
| PU-SEG-COM-03 | Comentario vacio o muy largo | Caja negra | `atenciones/tests/test_seguimiento_comentarios.py` · ComentariosTests.test_comentario_vacio_o_muy_largo | Aprobada |
| PU-SEG-COM-04 | Los comentarios no se editan ni se borran | Caja negra | `atenciones/tests/test_seguimiento_comentarios.py` · ComentariosTests.test_los_comentarios_no_se_editan_ni_se_borran | Aprobada |
| PU-SEG-COM-05 | Solo comenta quien ve la solicitud | Caja negra | `atenciones/tests/test_seguimiento_comentarios.py` · ComentariosTests.test_solo_comenta_quien_ve_la_solicitud | Aprobada |
| PU-SEG-COM-06 | Responsable puede comentar | Caja negra | `atenciones/tests/test_seguimiento_comentarios.py` · ComentariosTests.test_responsable_puede_comentar | Aprobada |
| PU-SEG-COM-07 | Se puede comentar una solicitud realizada | Caja negra | `atenciones/tests/test_seguimiento_comentarios.py` · ComentariosTests.test_se_puede_comentar_una_solicitud_realizada | Aprobada |

## Alcance por rol y delegación, actividad aprobada, listas y pantalla

| ID | Nombre | Tipo | Prueba en código | Estado |
|---|---|---|---|---|
| PU-SEG-ALC-01 | Administrador ve todo | Caja negra | `atenciones/tests/test_seguimiento_alcance.py` · AlcanceTests.test_administrador_ve_todo | Aprobada |
| PU-SEG-ALC-02 | Delegado ve solo su delegacion | Caja negra | `atenciones/tests/test_seguimiento_alcance.py` · AlcanceTests.test_delegado_ve_solo_su_delegacion | Aprobada |
| PU-SEG-ALC-03 | Funcionario ve las que escribio o le asignaron | Caja negra | `atenciones/tests/test_seguimiento_alcance.py` · AlcanceTests.test_funcionario_ve_las_que_escribio_o_le_asignaron | Aprobada |
| PU-SEG-ALC-04 | Funcionario no abre la de otro | Caja negra | `atenciones/tests/test_seguimiento_alcance.py` · AlcanceTests.test_funcionario_no_abre_la_de_otro | Aprobada |
| PU-SEG-ALC-05 | Anonimo no entra | Caja negra | `atenciones/tests/test_seguimiento_alcance.py` · AlcanceTests.test_anonimo_no_entra | Aprobada |
| PU-SEG-ALC-06 | Alcaldesa solo consulta no opera | Caja negra | `atenciones/tests/test_seguimiento_alcance.py` · AlcanceTests.test_alcaldesa_solo_consulta_no_opera | Aprobada |
| PU-SEG-ALC-07 | Delegado sin delegacion no entra | Caja negra | `atenciones/tests/test_seguimiento_alcance.py` · AlcanceTests.test_delegado_sin_delegacion_no_entra | Aprobada |
| PU-SEG-ALC-08 | Busqueda y filtros | Caja negra | `atenciones/tests/test_seguimiento_alcance.py` · AlcanceTests.test_busqueda_y_filtros | Aprobada |
| PU-SEG-ALC-09 | Paginacion con tamano elegido | Caja negra | `atenciones/tests/test_seguimiento_alcance.py` · AlcanceTests.test_paginacion_con_tamano_elegido | Aprobada |
| PU-SEG-ALC-10 | Resumen respeta el alcance | Caja negra | `atenciones/tests/test_seguimiento_alcance.py` · AlcanceTests.test_resumen_respeta_el_alcance | Aprobada |
| PU-SEG-ALC-11 | Delegado recibe areas y responsables de su delegacion | Caja negra | `atenciones/tests/test_seguimiento_alcance.py` · OpcionesSeguimientoTests.test_delegado_recibe_areas_y_responsables_de_su_delegacion | Aprobada |
| PU-SEG-ALC-12 | Funcionario no recibe listas de asignacion | Caja negra | `atenciones/tests/test_seguimiento_alcance.py` · OpcionesSeguimientoTests.test_funcionario_no_recibe_listas_de_asignacion | Aprobada |
| PU-SEG-ALC-13 | Otra delegacion no las ve | Caja negra | `atenciones/tests/test_seguimiento_alcance.py` · OpcionesSeguimientoTests.test_otra_delegacion_no_las_ve | Aprobada |
| PU-SEG-ALC-14 | No se cambia estado ni fecha ni motivo | Caja negra | `atenciones/tests/test_seguimiento_estado.py` · ActividadAprobadaTests.test_no_se_cambia_estado_ni_fecha_ni_motivo | Aprobada |
| PU-SEG-ALC-15 | El delegado tampoco asigna una aprobada | Caja negra | `atenciones/tests/test_seguimiento_estado.py` · ActividadAprobadaTests.test_el_delegado_tampoco_asigna_una_aprobada | Aprobada |
| PU-SEG-ALC-16 | Si se puede comentar | Caja negra | `atenciones/tests/test_seguimiento_estado.py` · ActividadAprobadaTests.test_si_se_puede_comentar | Aprobada |
| PU-SEG-ALC-17 | Anonimo es enviado al login | Caja negra | `atenciones/tests/test_seguimiento_pantallas.py` · PantallaSeguimientoTests.test_anonimo_es_enviado_al_login | Aprobada |
| PU-SEG-ALC-18 | Alcaldesa y jefe reciben 403 | Caja negra | `atenciones/tests/test_seguimiento_pantallas.py` · PantallaSeguimientoTests.test_alcaldesa_y_jefe_reciben_403 | Aprobada |
| PU-SEG-ALC-19 | Cada rol con acceso ve la pantalla y su codigo | Caja negra | `atenciones/tests/test_seguimiento_pantallas.py` · PantallaSeguimientoTests.test_cada_rol_con_acceso_ve_la_pantalla_y_su_codigo | Aprobada |
| PU-SEG-ALC-20 | Controles de la pantalla | Caja negra | `atenciones/tests/test_seguimiento_pantallas.py` · PantallaSeguimientoTests.test_controles_de_la_pantalla | Aprobada |
| PU-SEG-ALC-21 | Menu muestra solicitudes solo a quien corresponde | Caja negra | `atenciones/tests/test_seguimiento_pantallas.py` · PantallaSeguimientoTests.test_menu_muestra_solicitudes_solo_a_quien_corresponde | Aprobada |
| PU-SEG-ALC-22 | Funcionario ve el enlace desde su pagina de inicio | Caja negra | `atenciones/tests/test_seguimiento_pantallas.py` · PantallaSeguimientoTests.test_funcionario_ve_el_enlace_desde_su_pagina_de_inicio | Aprobada |
