# Seguimiento de actividades · Épicas 1 y 2 (HU01 a HU08) · Brian

El seguimiento se montó **sobre la app `atenciones`** (modelo `Actividad` de SCRUM-62 y verificación/evidencias de SCRUM-123,
de Patricio). No hay app nueva: no se duplicaron tablas ni rutas.

| HU | Jira | Qué hace | Dónde |
|---|---|---|---|
| HU01 Registrar | SCRUM-8 (68/69) | **Ya existía** (SCRUM-62): `POST /api/actividades/` y pantalla «Registrar actividad» | `atenciones/views.py`, `actividad_registrar.html` |
| HU02 Asignar a área | SCRUM-9 (70/71) | `POST /api/actividades/<id>/asignar/` área + prioridad + responsable | `seguimiento.AsignarSerializer` |
| HU03 Cambiar estado | SCRUM-10 (72/73) | `POST .../cambiar-estado/` con historial | `seguimiento.TRANSICIONES` |
| HU04 Evidencia fotográfica | SCRUM-11 (74/75) | **Ya existía** (SCRUM-123): `/api/evidencias/`. Se agregó que el **responsable asignado** vea y suba fotos | `verificacion.es_responsable` |
| HU05 Motivo de atraso | SCRUM-12 (76/77) | obligatorio si está vencida; `POST .../motivo-atraso/` | `seguimiento.MotivoOpcionalMixin` |
| HU06 Fecha de compromiso | SCRUM-34 (78/79) | `POST .../fecha-compromiso/` con historial | `seguimiento.FechaCompromisoSerializer` |
| HU07 Vencidas resaltadas | SCRUM-35 (80/81) | `vencida` y `dias_atraso` en la API, `?vencida=true`, fila resaltada | `Actividad.esta_vencida` |
| HU08 Comentarios | SCRUM-36 (82/83) | `GET/POST .../comentarios/` (solo se agregan) | `seguimiento.ComentarioSerializer` |

## Qué cambió en el proyecto
- **Modelos y migración** `atenciones/migrations/0006_seguimiento_comentarios.py`: crea `actividad_historial` y `comentario`, que ya
  estaban en el SQL v2.4 (mismos nombres de tabla y de campo). **No se agregó ninguna columna a `actividad`**: `estado`, `fecha_estado`,
  `fecha_compromiso`, `motivo_atraso`, `responsable`, `area` y `prioridad` ya existían desde SCRUM-62.
  Si otra rama crea también una migración `0006` en `atenciones`, hay que renumerar una de las dos.
- `atenciones/seguimiento.py` (nuevo): reglas, permisos y serializers del seguimiento.
- `atenciones/views.py`: acciones nuevas en `ActividadViewSet`; filtros `vencida`, `prioridad`, `responsable`; ordenar por compromiso,
  estado y prioridad; paginación con `page_size` (como los mantenedores); el Funcionario ve **lo que escribió y lo que le asignaron**.
- `atenciones/serializers.py`: `ActividadSerializer` expone (solo lectura) `responsable`, `fecha_compromiso`, `motivo_atraso`,
  `vencida`, `dias_atraso`, `n_comentarios`.
- `atenciones/verificacion.py`: el responsable asignado puede ver y adjuntar evidencias de la actividad.
- Pantalla **Seguimiento** (`/atenciones/seguimiento/`, menú «Actividades»): `actividad_seguimiento.html/.js`, `seguimiento.css`.
- `territorio/pantallas.py` (menú y páginas por rol) y `core/tests/test_permisos_roles.py` (el Funcionario ahora tiene una página más).

## Quién puede hacer qué (siempre se valida en el servidor)
| Acción | Administrador | Delegado (su delegación) | Autor o responsable (Funcionario / Encargado) | Jefe y Alcaldesa |
|---|---|---|---|---|
| Ver | todas | las de su delegación | Funcionario: las que escribió o le asignaron | consultan |
| Asignar área / prioridad / responsable | sí | sí | no | no |
| Cambiar estado, fecha, motivo | sí | sí | sí | no |
| Comentar | sí | sí | sí | no |
| Subir evidencia | sí | sí | sí | no |

Fuera de la delegación, la lectura responde 404 y las operaciones 403, igual que el resto de `atenciones`.

## Reglas (decisiones que conviene confirmar con el equipo)
- **Estados (HU03):** `Ingresado → Pendiente | En proceso | Realizado`; `Pendiente ↔ En proceso`; ambos → `Realizado`. Nunca se vuelve a
  `Ingresado` y **`Realizado` es final** para el seguimiento (no se reasigna ni cambia de fecha; sí se puede comentar y completar el motivo).
  El estado operativo es independiente de `estado_verificacion` (de Patricio).
- **Actividad aprobada** en la verificación: no se modifica (409), igual que en el ingreso. Comentar sí.
- **Asignación (HU02):** el área debe estar activa y ser de la delegación del autor (y coincidir con su tipo de atención si lo tiene);
  el responsable, activo, de la misma delegación y de un cargo de esa área o transversal.
- **Vencida (HU07):** `fecha_compromiso` anterior a hoy (hora de Chile) y estado distinto de `Realizado`.
- **Motivo de atraso (HU05):** si está vencida, cambiar el estado o la fecha exige un motivo (10 a 255 caracteres), salvo que ya tenga uno.
- **Fecha de compromiso (HU06):** no anterior a hoy ni igual a la vigente. Cada cambio guarda valor anterior, nuevo, usuario y fecha en
  `actividad_historial`. No se llama `historial_verificacion`: esa tabla es de la verificación.
- **Comentarios (HU08):** 1 a 1000 caracteres; no se editan ni se borran.
- Todo cambio queda además en `auditoria`.

## Rutas
| Qué | URL |
|---|---|
| Pantalla | `/atenciones/seguimiento/` |
| Acciones | `/api/actividades/<id>/{asignar,cambiar-estado,fecha-compromiso,motivo-atraso,historial-seguimiento,comentarios,opciones-seguimiento}/` |
| Listado y cifras | `/api/actividades/` (`?vencida=true`, `prioridad`, `responsable`, `estado`, `ordering=fecha_compromiso`) y `/api/actividades/resumen/` |

## Pruebas
`python manage.py test atenciones`: 72 pruebas del seguimiento en `atenciones/tests/test_seguimiento_*.py`, además de las de
Patricio. Detalle caso por caso en `docs/casos-prueba-seguimiento.md`.

## Límites conocidos
- Probado con SQLite y en un navegador (Chrome). No se probó contra MariaDB ni en el servidor AWS.
- El JavaScript no tiene pruebas automáticas en navegador; se verificó a mano.
- `ingreso_a_tubo` e `id_hito` de la actividad (marcados `TODO(Brian)` en el modelo) no forman parte de HU01 a HU08 y no se tocaron.
