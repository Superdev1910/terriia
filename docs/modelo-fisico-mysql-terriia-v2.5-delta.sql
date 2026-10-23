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
-- Sistema de Delegaciones Municipales (TerriIA)
-- Proyecto Integrado Inacap — Municipalidad de La Serena
-- =====================================================================
-- REFERENCIA para los modelos de Django. NO importar en phpMyAdmin:
-- las tablas las crea Django con `python manage.py migrate`.
-- Solo contiene lo que cambia respecto de modelo-fisico-mysql-terriia-v2.4.sql;
-- cada tarea escribe su propia sección.
-- =====================================================================

USE terriia;

-- ---------------------------------------------------------------------
-- SCRUM-61 tipo_atencion y sub_atencion
-- Catálogos de atención por área (reunión 28-08, guía SGR §8.1).
--   - NUEVA tabla tipo_atencion: tipos de atención de cada área.
--   - NUEVA tabla sub_atencion: detalle de un tipo de atención.
--   - actividad: + id_tipo_atencion, id_sub_atencion (NULL; los usa el ingreso, T5).
-- ---------------------------------------------------------------------

CREATE TABLE tipo_atencion (
    id_tipo_atencion INT AUTO_INCREMENT PRIMARY KEY,
    area             ENUM('Social','DISERCO','Seguridad','Organizacion Comunitaria') NOT NULL, -- mismas 4 áreas de area.nombre
    nombre           VARCHAR(100) NOT NULL,
    activo           BOOLEAN DEFAULT TRUE,                    -- se desactiva, no se borra
    UNIQUE KEY uq_tipo_atencion_area_nombre (area, nombre)    -- utf8mb4_unicode_ci: sin distinguir mayúsculas
) ENGINE=InnoDB;

CREATE TABLE sub_atencion (
    id_sub_atencion  INT AUTO_INCREMENT PRIMARY KEY,
    id_tipo_atencion INT NOT NULL,                            -- solo bajo un tipo activo (regla en la aplicación)
    nombre           VARCHAR(100) NOT NULL,
    activo           BOOLEAN DEFAULT TRUE,
    FOREIGN KEY (id_tipo_atencion) REFERENCES tipo_atencion(id_tipo_atencion),
    UNIQUE KEY uq_sub_atencion_tipo_nombre (id_tipo_atencion, nombre)
) ENGINE=InnoDB;

ALTER TABLE actividad
    ADD COLUMN id_tipo_atencion INT NULL AFTER id_area,       -- SCRUM-61, lo llena T5
    ADD COLUMN id_sub_atencion  INT NULL AFTER id_tipo_atencion,
    ADD FOREIGN KEY (id_tipo_atencion) REFERENCES tipo_atencion(id_tipo_atencion),
    ADD FOREIGN KEY (id_sub_atencion) REFERENCES sub_atencion(id_sub_atencion);

-- Semilla ficticia (migración atenciones/0002_semilla_social):
--   Social: Informe social, Gestión de subsidio, Derivación, Otras gestiones.
--   Otras gestiones > Orientación social.
