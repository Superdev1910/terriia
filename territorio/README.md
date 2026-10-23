# Mantenedores territoriales

La app expone los siguientes endpoints, protegidos para el rol
`Administrador`:

- `/api/vecinos/`
- `/api/territorios/`
- `/api/juntas-vecinos/`

Los tres endpoints usan búsqueda mediante `search`, filtros mediante
`django-filter`, paginación `page`/`page_size` y desactivación lógica con
`DELETE`. Las pantallas administrativas están disponibles en
`/territorio/vecinos/`, `/territorio/territorios/` y
`/territorio/juntas-vecinos/`.

## Confirmación pendiente del SQL físico

El repositorio no contiene el modelo físico SQL v2.3. La migración
`0001_initial` implementa una propuesta mínima para que el módulo sea
funcional con SQLite y MariaDB. Antes de integrar en el servidor se deben
confirmar con el equipo:

- nombres y longitudes de teléfono, dirección y correo de `vecino`;
- si `junta_vecinos` requiere presidente, fecha de constitución u otros
  datos de contacto;
- si `territorio.es_formal` corresponde a un booleano o a un catálogo de
  tipos de asentamiento;
- los nombres físicos exactos de las tres tablas y sus claves.

No se deben editar migraciones de otras aplicaciones al reemplazar esta
propuesta por el SQL oficial.
