# Modelo de datos — TerriIA (v2.4)

Este es **el diseño oficial de la base de datos**. Antes de crear un modelo en Django, revisa aquí tu tabla.

Archivo: `docs/modelo-fisico-mysql-terriia-v2.4.sql`

## Regla de oro

Tu modelo en `models.py` debe tener **los mismos nombres de tabla, campos y valores** que el SQL.

| En el SQL | En Django |
|---|---|
| `CREATE TABLE area (` | `class Meta: db_table = "area"` |
| `id_area INT AUTO_INCREMENT PRIMARY KEY` | `id_area = models.AutoField(primary_key=True)` |
| `nombre VARCHAR(150) NOT NULL` | `nombre = models.CharField(max_length=150)` |
| `telefono VARCHAR(20)` (sin NOT NULL) | `telefono = models.CharField(max_length=20, blank=True, null=True)` |
| `estado ENUM('vigente','cerrado')` | `estado = models.CharField(max_length=..., choices=[("vigente", "Vigente"), ("cerrado", "Cerrado")])` |
| `activo BOOLEAN DEFAULT TRUE` | `activo = models.BooleanField(default=True)` |
| `id_delegacion INT NOT NULL` + `FOREIGN KEY ... REFERENCES delegacion` | `delegacion = models.ForeignKey(Delegacion, on_delete=models.PROTECT, db_column="id_delegacion")` |
| `UNIQUE` | `unique=True` |

- **No inventes campos ni valores.** Si necesitas uno que no está, avísale a Patricio y se agrega al SQL (nueva versión).
- **No importes el SQL en phpMyAdmin.** Las tablas las crea Django con `python manage.py migrate`; el SQL es solo la referencia.

## Tablas por integrante

| Integrante | Tablas | App |
|---|---|---|
| Brian | delegacion, area, cargo | `organizacion` |
| Pamela | vecino, territorio, junta_vecinos | `territorio` |
| Valentina | periodo, item | `metas` |
| Fernando | funcionario, meta_delegacion, meta | `personas` / `metas` |
| Patricio | rol, usuario, auditoria, codigo_recuperacion | `core` / `personas` |

## Versión 2.6 (SCRUM-62 y SCRUM-123): actividades, verificación y evidencias

Archivo: `docs/modelo-fisico-mysql-terriia-v2.6-delta.sql` (de referencia: las tablas las crean las migraciones de `atenciones`).

| Tabla | Para qué |
|---|---|
| `actividad` (ampliada) | Una sola tabla para actividades y gestiones sociales (`tipo_registro`), con código único, ponderación y `estado_verificacion`. |
| `contador_codigo_actividad` | Último correlativo por delegación y año (código `<COD>-<AAAA>-<5 dígitos>`). |
| `historial_verificacion` | Cada cambio de `estado_verificacion` (quién, de qué a qué, observación, cuándo). |
| `evidencia` (ampliada) | Archivos de una actividad; la ruta es privada y se descargan por la API. |

**Por qué `historial_verificacion` es una tabla aparte de `actividad_historial` (v2.4).** `actividad_historial` registra los
cambios del estado operativo (`estado`, `fecha_compromiso`, `motivo_atraso`) con un `campo` ENUM, y la verificación es otro
proceso: tiene otros actores (quien verifica, no quien ejecuta), otras reglas (transiciones finales, observación obligatoria) y se
consulta por separado en la bandeja y en la ficha. Mezclarlas obligaría a ampliar el ENUM `campo` y a distinguir en cada consulta
de quién es cada fila. Además `actividad_historial` aún no se usa en la aplicación. La tabla `validacion` de la v2.4 (revisión por
evidencia) **queda sin uso**: la verificación se hace sobre la actividad, no sobre cada evidencia, y la reemplaza
`historial_verificacion`; no se borra del SQL de referencia.

**`evidencia.estado_revision` está reservado.** Viene del SQL v2.4 (`pendiente`/`revisado`) y hoy no tiene flujo: siempre queda en
`pendiente`. No se borra por si el cliente define una revisión por evidencia; no la uses en reglas de negocio mientras tanto.

