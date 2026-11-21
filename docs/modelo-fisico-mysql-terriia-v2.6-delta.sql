-- ---------------------------------------------------------------------
-- TerriIA · Modelo físico v2.6 (DELTA sobre v2.4 + v2.5)       SCRUM-62
-- Ingreso de actividad y gestión social. Coherente con la migración
-- atenciones/0003_actividad (las tablas las crea Django; este SQL es solo la referencia).
-- Autoriza la nueva versión: Patricio.
--
-- Cambios:
--   - NUEVA tabla contador_codigo_actividad: último correlativo por delegación y año.
--   - actividad: + codigo (único, <COD_DELEGACION>-<AAAA>-<5 dígitos>), tipo_registro,
--     fecha_registro, es_coordinacion_preparatoria, origen, id_delegado_solicitante, id_hito,
--     estado_verificacion, pondera, motivo_no_pondera + índices.
--   - actividad.estado (estado operativo del v2.4) NO cambia: la verificación va aparte.
--   - actividad.id_hito: entero NULL sin FK hasta que exista la tabla hito (TODO Brian).
--   - Los valores de pondera / motivo_no_pondera los calcula el servidor (atenciones/reglas.py).
-- ---------------------------------------------------------------------

CREATE TABLE contador_codigo_actividad (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    id_delegacion   INT NOT NULL,
    anio            SMALLINT UNSIGNED NOT NULL,
    ultimo          INT UNSIGNED NOT NULL DEFAULT 0,       -- se incrementa con SELECT ... FOR UPDATE
    FOREIGN KEY (id_delegacion) REFERENCES delegacion(id_delegacion),
    UNIQUE KEY uq_contador_actividad_delegacion_anio (id_delegacion, anio)
) ENGINE=InnoDB;

ALTER TABLE actividad
    ADD COLUMN codigo                       VARCHAR(24) NULL AFTER id_actividad,   -- se completa y se vuelve NOT NULL abajo
    ADD COLUMN tipo_registro                ENUM('actividad','gestion_social') NOT NULL DEFAULT 'actividad' AFTER codigo,
    ADD COLUMN fecha_registro               DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP AFTER fecha,   -- Django: auto_now_add
    ADD COLUMN es_coordinacion_preparatoria BOOLEAN NOT NULL DEFAULT FALSE AFTER ingreso_a_tubo,
    ADD COLUMN origen                       ENUM('funcionario','delegado') NOT NULL DEFAULT 'funcionario',
    ADD COLUMN id_delegado_solicitante      INT NULL,                                -- usuario con rol Delegado territorial
    ADD COLUMN id_hito                      INT NULL,                                -- TODO(Brian): FK a hito cuando exista
    ADD COLUMN estado_verificacion          ENUM('pendiente','aprobada','rechazada','antecedentes') NOT NULL DEFAULT 'pendiente',
    ADD COLUMN pondera                      BOOLEAN NOT NULL DEFAULT TRUE,
    ADD COLUMN motivo_no_pondera            VARCHAR(255) NOT NULL DEFAULT '',
    ADD FOREIGN KEY (id_delegado_solicitante) REFERENCES usuario(id_usuario);

-- Filas anteriores a v2.6 (si las hubiera): código <COD>-<AAAA>-<correlativo> y contador al día.
UPDATE actividad a
JOIN (
    SELECT x.id_actividad,
           CONCAT(d.codigo, '-', YEAR(x.fecha), '-',
                  LPAD(ROW_NUMBER() OVER (PARTITION BY d.id_delegacion, YEAR(x.fecha)
                                          ORDER BY x.id_actividad), 5, '0')) AS cod
    FROM actividad x
    JOIN funcionario f ON f.id_funcionario = x.id_funcionario
    JOIN delegacion d ON d.id_delegacion = f.id_delegacion
) n ON n.id_actividad = a.id_actividad
SET a.codigo = n.cod;

INSERT INTO contador_codigo_actividad (id_delegacion, anio, ultimo)
SELECT f.id_delegacion, YEAR(a.fecha), COUNT(*)
FROM actividad a
JOIN funcionario f ON f.id_funcionario = a.id_funcionario
GROUP BY f.id_delegacion, YEAR(a.fecha);

ALTER TABLE actividad
    MODIFY COLUMN codigo VARCHAR(24) NOT NULL,
    ADD UNIQUE KEY actividad_codigo_uniq (codigo),
    ADD INDEX ix_actividad_func_fecha (id_funcionario, fecha),
    ADD INDEX ix_actividad_verificacion (estado_verificacion);

-- Reglas de negocio (en la aplicación, no en la base de datos):
--   - Máximo 7 registros por funcionario y día; no se acepta fecha futura.
--   - Semana lunes-domingo: se cierra al terminar el domingo + SEMANA_CIERRE_DIAS_GRACIA días
--     (por defecto 1; a confirmar con el cliente).
--   - pondera = FALSE con motivo si: el atendido es el delegado, falta nombre o teléfono, o es
--     coordinación preparatoria.
--   - Ítem del cargo del funcionario; área, territorio y vecino de la delegación del funcionario;
--     sub atención del tipo elegido; catálogos activos.
