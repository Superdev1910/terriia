-- =====================================================================
-- TerriIA — Modelo Físico (MySQL) — v2.5 (DELTA sobre v2.4)
-- Solo trae los cambios respecto de modelo-fisico-mysql-terriia-v2.4.sql.
-- =====================================================================
-- REFERENCIA para los modelos de Django. NO importar en phpMyAdmin:
-- las tablas las crea Django con `python manage.py migrate`.

-- SCRUM-14 rol: descripcion y activo
-- Migración core/0005_rol_descripcion_activo. Mantenedor /api/roles/ (solo Administrador).
-- Los 6 roles del sistema no se renombran ni se desactivan (los permisos los usan por
-- nombre); solo se edita su descripción. Los roles nuevos sí se pueden desactivar.
ALTER TABLE rol
    ADD COLUMN descripcion VARCHAR(255) NOT NULL DEFAULT '',
    ADD COLUMN activo      BOOLEAN      NOT NULL DEFAULT TRUE;
