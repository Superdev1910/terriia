## Qué hace este PR
<!-- Ej: SCRUM-31 crea mantenedor territorio -->

**Subtarea Jira:** SCRUM-

## Checklist (definición de terminado)
- [ ] Listado con búsqueda, filtro y paginación
- [ ] Crear y editar con validaciones
- [ ] Desactivar en vez de borrar
- [ ] Solo rol Administrador (hereda de `MantenedorViewSet`)
- [ ] Auditoría automática (no escrita a mano)
- [ ] Pruebas: crear, editar, duplicado/inválido, desactivar, acceso denegado
- [ ] `python manage.py test` pasa en local
- [ ] `black .` ejecutado
- [ ] Incluye su migración (`makemigrations`) y no modifica migraciones de otros
