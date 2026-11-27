-- ---------------------------------------------------------------------
-- TerriIA · Modelo físico v2.6 (DELTA sobre v2.4 + v2.5)       SCRUM-62
-- Ingreso de actividad y gestión social. Coherente con la migración
-- atenciones/0003_actividad (las tablas las crea Django; este SQL es solo la referencia).
-- Autoriza la nueva versión: Patricio.
--
-- ESTE ARCHIVO ES DE REFERENCIA. Cómo usarlo:
--   * Base creada con `python manage.py migrate` (local o servidor nuevo): NO lo ejecutes. Las
--     migraciones atenciones/0003, 0004 y 0005 ya crearon todo esto; el archivo solo documenta el
--     diseño para revisión.
--   * Base manual en v2.5 (creada a mano con los SQL v2.4 y v2.5): ejecútalo ENTERO y en orden, con
--     un respaldo previo y en una ventana sin uso. Cada bloque lleva su verificación.
--
-- Diferencias de tipos con lo que genera Django (no son errores):
--   - ENUM aquí; Django crea VARCHAR con `choices` (la validación está en la aplicación).
--   - contador_codigo_actividad.id: aquí INT; Django usa BIGINT (DEFAULT_AUTO_FIELD = BigAutoField).
--     Las demás llaves (id_actividad, id_historial, id_evidencia) son INT en ambos.
--   - BOOLEAN = TINYINT(1) en ambos. Los índices UNIQUE/INDEX nombrados pueden diferir en el nombre
--     autogenerado por Django (el nombre no afecta el funcionamiento).
--   - Las fechas DATETIME se guardan en UTC (USE_TZ=True); el año del código usa hora de Chile.
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
-- El año usa la hora de Chile: `fecha` está en UTC y el 31-dic/1-ene Chile está en horario de
-- verano (UTC-3), por eso se restan 3 horas. (La aplicación usa el año de fecha_registro al crear;
-- para filas antiguas se aproxima con `fecha`.)
-- Se usa una tabla temporal: un UPDATE sobre `actividad` con subconsulta sobre `actividad` puede
-- fallar con el error 1093 ("You can't specify target table ... for update in FROM clause").
CREATE TEMPORARY TABLE tmp_codigo_actividad AS
SELECT x.id_actividad,
       f.id_delegacion,
       YEAR(x.fecha - INTERVAL 3 HOUR) AS anio,
       CONCAT(d.codigo, '-', YEAR(x.fecha - INTERVAL 3 HOUR), '-',
              LPAD(ROW_NUMBER() OVER (PARTITION BY f.id_delegacion, YEAR(x.fecha - INTERVAL 3 HOUR)
                                      ORDER BY x.id_actividad), 5, '0')) AS cod
FROM actividad x
JOIN funcionario f ON f.id_funcionario = x.id_funcionario
JOIN delegacion d ON d.id_delegacion = f.id_delegacion;

UPDATE actividad a
JOIN tmp_codigo_actividad t ON t.id_actividad = a.id_actividad
SET a.codigo = t.cod;

INSERT INTO contador_codigo_actividad (id_delegacion, anio, ultimo)
SELECT id_delegacion, anio, COUNT(*) FROM tmp_codigo_actividad GROUP BY id_delegacion, anio;

DROP TEMPORARY TABLE tmp_codigo_actividad;

-- Verificación: debe devolver 0 filas.
-- SELECT COUNT(*) FROM actividad WHERE codigo IS NULL;

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

-- ---------------------------------------------------------------------
-- SCRUM-123 · Verificación y evidencias (migración atenciones/0004_verificacion_evidencias)
--   - NUEVA tabla historial_verificacion: cada cambio de actividad.estado_verificacion.
--   - evidencia (v2.4): archivo_url pasa a archivo (ruta relativa PRIVADA, nunca una URL pública;
--     se descarga por /api/evidencias/<id>/archivo/) y se agregan nombre_original,
--     tipo_contenido (detectado por firma: JPG, PNG o PDF), tamano (máx. 5 MB, en la aplicación)
--     y la unicidad del codigo_verificador (3 letras + 3 dígitos, generado por el servidor).
--   - Reglas en la aplicación: transiciones pendiente -> aprobada|rechazada|antecedentes,
--     antecedentes -> pendiente al editar el autor; aprobada y rechazada son finales; una
--     actividad aprobada no se modifica ni cambia sus evidencias.
-- ---------------------------------------------------------------------

CREATE TABLE historial_verificacion (
    id_historial     INT AUTO_INCREMENT PRIMARY KEY,
    id_actividad     INT NOT NULL,
    id_usuario       INT NOT NULL,                              -- quien hizo el cambio
    estado_anterior  ENUM('pendiente','aprobada','rechazada','antecedentes') NOT NULL,
    estado_nuevo     ENUM('pendiente','aprobada','rechazada','antecedentes') NOT NULL,
    observacion      TEXT NOT NULL,                             -- obligatoria al rechazar o pedir antecedentes
    fecha            DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (id_actividad) REFERENCES actividad(id_actividad),
    FOREIGN KEY (id_usuario) REFERENCES usuario(id_usuario),
    INDEX ix_hist_verif_actividad (id_actividad, fecha)
) ENGINE=InnoDB;

-- Conversión previa: `archivo` será NOT NULL y guardará una ruta relativa a MEDIA_ROOT, nunca una
-- URL. Las filas con archivo_url NULL o con una URL externa (http...) no tienen archivo en el
-- servidor: se dejan con ruta vacía. REVISA antes (y guarda las URLs si importan):
--   SELECT id_evidencia, archivo_url FROM evidencia WHERE archivo_url IS NULL OR archivo_url LIKE 'http%';
UPDATE evidencia SET archivo_url = '' WHERE archivo_url IS NULL OR archivo_url LIKE 'http%';
-- Los codigo_verificador repetidos impedirían el UNIQUE de abajo. Debe devolver 0 filas:
--   SELECT codigo_verificador, COUNT(*) FROM evidencia GROUP BY codigo_verificador HAVING COUNT(*) > 1;

ALTER TABLE evidencia
    CHANGE COLUMN archivo_url archivo VARCHAR(255) NOT NULL,   -- ruta relativa a MEDIA_ROOT (nombre uuid)
    MODIFY COLUMN codigo_verificador VARCHAR(10) NOT NULL,
    MODIFY COLUMN fecha DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    ADD COLUMN nombre_original VARCHAR(150) NOT NULL DEFAULT '' AFTER archivo,
    ADD COLUMN tipo_contenido  VARCHAR(30)  NOT NULL DEFAULT '' AFTER nombre_original,
    ADD COLUMN tamano          INT UNSIGNED NOT NULL DEFAULT 0 AFTER tipo_contenido,
    ADD UNIQUE KEY evidencia_codigo_verificador_uniq (codigo_verificador);
