-- =====================================================================
-- TerriIA — Modelo Físico (MySQL) — v2.4 (COMPLETO)
-- Sistema de Delegaciones Municipales (TerriIA)
-- Proyecto Integrado Inacap — Municipalidad de La Serena
-- =====================================================================
-- REFERENCIA para los modelos de Django. NO importar en phpMyAdmin:
-- las tablas las crea Django con `python manage.py migrate`.
--
-- Cambios v2.4 (mantenedores de organización, SCRUM-13, revisión 22-10-2026):
--   - delegacion: + codigo (único), direccion, comuna; nombre único.
--   - area: + estado (activa/inactiva); prioridad única dentro de la delegación.
--   - cargo: + descripcion; nombre único dentro del área.
--   - NUEVA tabla codigo_recuperacion (recuperar contraseña; solo huella HMAC).
--
-- Cambios v2.3 (estudio del modelo de datos, 09-10-2026):
--   - actividad_historial fusiona fecha_compromiso_historial +
--     motivo_atraso_historial (+ historial de estados, HU03).
--   - configuracion_verificacion_item -> 2 columnas en item.
--   - resumen_ejecutivo -> VIEW v_resumen_ejecutivo (HU22).
--   - reporte_generado -> evento 'generar_reporte' en auditoria.
--   - FKs en vez de texto: actividad.id_territorio, sugerencia_ia.id_area_sugerida,
--     reconocimiento.id_periodo. area.prioridad (1 a 4).
--   - Login en backend Django (usuario.password_hash). rol = solo lectura.
--
-- Total: 27 tablas + 1 vista.
-- =====================================================================

DROP DATABASE IF EXISTS terriia;
CREATE DATABASE terriia CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE terriia;

-- ---------------------------------------------------------------------
-- ÉPICA 5 — Administración, Seguridad y Accesos (HU17-HU19)
-- ---------------------------------------------------------------------

CREATE TABLE delegacion (
    id_delegacion   INT AUTO_INCREMENT PRIMARY KEY,
    codigo          VARCHAR(10)  NOT NULL UNIQUE,             -- v2.4: código corto (ej. CEN, RUR)
    nombre          VARCHAR(100) NOT NULL,
    ambito          VARCHAR(150),                             -- Centro, Rural, La Antena, La Pampa, Avenida del Mar, Compañías
    direccion       VARCHAR(200) NOT NULL DEFAULT '',         -- v2.4
    comuna          VARCHAR(80)  NOT NULL DEFAULT 'La Serena',-- v2.4
    estado          ENUM('activa','inactiva') DEFAULT 'activa',
    UNIQUE KEY uq_delegacion_nombre (nombre)                  -- v2.4
) ENGINE=InnoDB;

CREATE TABLE area (
    id_area         INT AUTO_INCREMENT PRIMARY KEY,
    id_delegacion   INT NOT NULL,
    nombre          ENUM('Social','DISERCO','Seguridad','Organizacion Comunitaria') NOT NULL,
    prioridad       TINYINT NOT NULL DEFAULT 1,               -- 1 a 4, orden del área en esa delegación
    estado          ENUM('activa','inactiva') DEFAULT 'activa', -- v2.4: se desactiva, no se borra
    FOREIGN KEY (id_delegacion) REFERENCES delegacion(id_delegacion),
    UNIQUE KEY uq_area_delegacion (id_delegacion, nombre),            -- HU17
    UNIQUE KEY uq_area_delegacion_prioridad (id_delegacion, prioridad) -- v2.4
) ENGINE=InnoDB;

CREATE TABLE cargo (
    id_cargo        INT AUTO_INCREMENT PRIMARY KEY,
    id_area         INT NULL,                                 -- NULL = cargo transversal
    nombre          VARCHAR(100) NOT NULL,
    descripcion     VARCHAR(255) NOT NULL DEFAULT '',         -- v2.4
    vigente         BOOLEAN DEFAULT TRUE,
    FOREIGN KEY (id_area) REFERENCES area(id_area),
    UNIQUE KEY uq_cargo_area_nombre (id_area, nombre)         -- v2.4
) ENGINE=InnoDB;

CREATE TABLE rol (
    id_rol          INT AUTO_INCREMENT PRIMARY KEY,
    nombre          VARCHAR(50) NOT NULL UNIQUE   -- solo lectura: Administrador, Jefe de delegaciones, Delegado territorial, Encargado de área, Funcionario, Alcaldesa
) ENGINE=InnoDB;

CREATE TABLE funcionario (
    id_funcionario      INT AUTO_INCREMENT PRIMARY KEY,
    identificador_inst  VARCHAR(30) NOT NULL UNIQUE,
    nombre              VARCHAR(150) NOT NULL,
    id_cargo            INT NOT NULL,
    id_delegacion       INT NOT NULL,
    estado              ENUM('activo','inactivo') DEFAULT 'activo',
    FOREIGN KEY (id_cargo) REFERENCES cargo(id_cargo),
    FOREIGN KEY (id_delegacion) REFERENCES delegacion(id_delegacion)
) ENGINE=InnoDB;

CREATE TABLE usuario (
    id_usuario      INT AUTO_INCREMENT PRIMARY KEY,
    id_funcionario  INT NULL,                     -- NULL para usuarios sin ficha (ej. alcaldesa)
    id_rol          INT NOT NULL,
    id_delegacion   INT NULL,                     -- HU19: NULL = acceso global (alcaldesa/admin)
    rut             VARCHAR(12) NOT NULL UNIQUE,
    email           VARCHAR(150) NOT NULL UNIQUE,
    password_hash   VARCHAR(255) NOT NULL,        -- login gestionado por el backend Django
    estado          ENUM('activo','inactivo') DEFAULT 'activo',
    FOREIGN KEY (id_funcionario) REFERENCES funcionario(id_funcionario),
    FOREIGN KEY (id_rol) REFERENCES rol(id_rol),
    FOREIGN KEY (id_delegacion) REFERENCES delegacion(id_delegacion)
) ENGINE=InnoDB;

CREATE TABLE codigo_recuperacion (
    id_codigo   INT AUTO_INCREMENT PRIMARY KEY,   -- v2.4: recuperación de contraseña
    id_usuario  INT NOT NULL,
    huella      VARCHAR(64) NOT NULL,             -- solo se guarda la huella HMAC, nunca el código
    creado      DATETIME NOT NULL,
    vence       DATETIME NOT NULL,
    intentos    SMALLINT UNSIGNED NOT NULL DEFAULT 0,
    usado       BOOLEAN NOT NULL DEFAULT FALSE,
    FOREIGN KEY (id_usuario) REFERENCES usuario(id_usuario) ON DELETE CASCADE
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------
-- ÉPICA 8 (maestras) — Vecinos, Territorios, Juntas de vecinos
-- ---------------------------------------------------------------------

CREATE TABLE vecino (
    id_vecino       INT AUTO_INCREMENT PRIMARY KEY,   -- HU27
    rut             VARCHAR(12) NOT NULL UNIQUE,
    nombres         VARCHAR(100) NOT NULL,
    apellidos       VARCHAR(100) NOT NULL,
    telefono        VARCHAR(20),
    direccion       VARCHAR(255)
) ENGINE=InnoDB;

CREATE TABLE territorio (
    id_territorio   INT AUTO_INCREMENT PRIMARY KEY,   -- HU28
    id_delegacion   INT NOT NULL,
    nombre          VARCHAR(150) NOT NULL,
    es_formal       BOOLEAN DEFAULT TRUE,             -- excluye tomas/asentamientos informales
    activo          BOOLEAN DEFAULT TRUE,
    FOREIGN KEY (id_delegacion) REFERENCES delegacion(id_delegacion)
) ENGINE=InnoDB;

CREATE TABLE junta_vecinos (
    id_junta_vecinos   INT AUTO_INCREMENT PRIMARY KEY,   -- catálogo, sin vínculo con vecino
    id_territorio      INT NOT NULL,
    nombre             VARCHAR(150) NOT NULL,
    numero_registro    VARCHAR(30) UNIQUE,
    direccion          VARCHAR(255),
    presidente         VARCHAR(150),
    telefono           VARCHAR(20),
    email              VARCHAR(150),
    activa             BOOLEAN DEFAULT TRUE,
    FOREIGN KEY (id_territorio) REFERENCES territorio(id_territorio)
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------
-- ÉPICA 3 — Metas y Semáforo (HU09-HU13)
-- ---------------------------------------------------------------------

CREATE TABLE periodo (
    id_periodo          INT AUTO_INCREMENT PRIMARY KEY,
    fecha_inicio        DATE NOT NULL,
    fecha_termino       DATE NOT NULL,
    dias_computables    INT,
    estado              ENUM('vigente','cerrado') DEFAULT 'vigente',
    version_parametros  VARCHAR(20)
) ENGINE=InnoDB;

CREATE TABLE item (
    id_item                      INT AUTO_INCREMENT PRIMARY KEY,
    id_cargo                     INT NOT NULL,
    nombre                       VARCHAR(150) NOT NULL,
    tipo_meta                    ENUM('conteo','porcentaje') NOT NULL,
    ponderador                   DECIMAL(5,2) NOT NULL,   -- % dentro del cargo, suma 100% por cargo
    activo                       BOOLEAN DEFAULT TRUE,
    requiere_verificacion_previa BOOLEAN DEFAULT FALSE,   -- HU29
    radio_tolerancia_metros      INT NULL,                -- obligatorio solo si requiere_verificacion_previa = TRUE
    FOREIGN KEY (id_cargo) REFERENCES cargo(id_cargo)
) ENGINE=InnoDB;

CREATE TABLE meta_delegacion (
    id_meta_delegacion      INT AUTO_INCREMENT PRIMARY KEY,   -- HU09/HU10
    id_item                 INT NOT NULL,
    id_delegacion           INT NOT NULL,
    id_periodo              INT NOT NULL,
    valor_objetivo_total    DECIMAL(10,2) NOT NULL,
    FOREIGN KEY (id_item) REFERENCES item(id_item),
    FOREIGN KEY (id_delegacion) REFERENCES delegacion(id_delegacion),
    FOREIGN KEY (id_periodo) REFERENCES periodo(id_periodo),
    UNIQUE KEY uq_meta_delegacion (id_item, id_delegacion, id_periodo)
) ENGINE=InnoDB;

CREATE TABLE meta (
    id_meta             INT AUTO_INCREMENT PRIMARY KEY,
    id_meta_delegacion  INT NOT NULL,               -- ítem y periodo se obtienen de meta_delegacion
    id_funcionario      INT NOT NULL,
    valor_objetivo      DECIMAL(10,2) NOT NULL,      -- porción individual; ajustes en recalibracion_meta
    unidad              VARCHAR(20),
    FOREIGN KEY (id_meta_delegacion) REFERENCES meta_delegacion(id_meta_delegacion),
    FOREIGN KEY (id_funcionario) REFERENCES funcionario(id_funcionario),
    UNIQUE KEY uq_meta_funcionario (id_meta_delegacion, id_funcionario)
) ENGINE=InnoDB;

CREATE TABLE recalibracion_meta (
    id_recalibracion        INT AUTO_INCREMENT PRIMARY KEY,   -- HU12
    id_meta                 INT NOT NULL,
    valor_objetivo_anterior DECIMAL(10,2) NULL,
    valor_objetivo_nuevo    DECIMAL(10,2) NOT NULL,
    motivo                  VARCHAR(255) NOT NULL,
    usuario_id              INT NOT NULL,
    fecha                   DATETIME NOT NULL,
    FOREIGN KEY (id_meta) REFERENCES meta(id_meta),
    FOREIGN KEY (usuario_id) REFERENCES usuario(id_usuario)
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------
-- ÉPICAS 1 y 2 — Solicitudes, Tareas y Seguimiento (HU01-HU08, HU25)
-- ---------------------------------------------------------------------

CREATE TABLE actividad (
    id_actividad        INT AUTO_INCREMENT PRIMARY KEY,
    id_funcionario      INT NOT NULL,               -- autor
    id_item             INT NOT NULL,
    id_vecino           INT NULL,                   -- HU27 (NULL si es actividad medida sin vecino, HU25)
    id_territorio       INT NULL,
    fecha               DATETIME NOT NULL,
    descripcion         TEXT,
    accion              VARCHAR(255),
    contacto            VARCHAR(150),
    telefono            VARCHAR(20),
    ingreso_a_tubo      BOOLEAN DEFAULT FALSE,
    id_area             INT NULL,                   -- HU02
    prioridad           ENUM('alta','media','baja') NULL,
    responsable_id      INT NULL,
    estado              ENUM('Ingresado','Pendiente','En proceso','Realizado') DEFAULT 'Ingresado',
    fecha_estado        DATETIME NULL,              -- valor vigente; historial en actividad_historial
    usuario_cambio_id   INT NULL,                   -- valor vigente; historial en actividad_historial
    fecha_compromiso    DATE NULL,                  -- HU06, valor vigente
    motivo_atraso       VARCHAR(255) NULL,          -- HU05, valor vigente
    FOREIGN KEY (id_funcionario) REFERENCES funcionario(id_funcionario),
    FOREIGN KEY (id_item) REFERENCES item(id_item),
    FOREIGN KEY (id_vecino) REFERENCES vecino(id_vecino),
    FOREIGN KEY (id_territorio) REFERENCES territorio(id_territorio),
    FOREIGN KEY (id_area) REFERENCES area(id_area),
    FOREIGN KEY (responsable_id) REFERENCES funcionario(id_funcionario),
    FOREIGN KEY (usuario_cambio_id) REFERENCES usuario(id_usuario)
) ENGINE=InnoDB;

CREATE TABLE actividad_historial (
    id_historial     INT AUTO_INCREMENT PRIMARY KEY,   -- HU03, HU05, HU06
    id_actividad     INT NOT NULL,
    campo            ENUM('estado','fecha_compromiso','motivo_atraso') NOT NULL,
    valor_anterior   VARCHAR(255) NULL,
    valor_nuevo      VARCHAR(255) NOT NULL,
    usuario_id       INT NOT NULL,
    fecha_cambio     DATETIME NOT NULL,
    FOREIGN KEY (id_actividad) REFERENCES actividad(id_actividad),
    FOREIGN KEY (usuario_id) REFERENCES usuario(id_usuario)
) ENGINE=InnoDB;

CREATE TABLE comentario (
    id_comentario        INT AUTO_INCREMENT PRIMARY KEY,   -- HU08
    id_actividad         INT NOT NULL,
    id_usuario           INT NOT NULL,
    texto                TEXT NOT NULL,
    fecha                DATETIME NOT NULL,
    FOREIGN KEY (id_actividad) REFERENCES actividad(id_actividad),
    FOREIGN KEY (id_usuario) REFERENCES usuario(id_usuario)
) ENGINE=InnoDB;

CREATE TABLE evidencia (
    id_evidencia        INT AUTO_INCREMENT PRIMARY KEY,   -- HU04
    id_actividad        INT NOT NULL,
    codigo_verificador  VARCHAR(10) NOT NULL,              -- 3 letras + 3 dígitos (ej. ORC711)
    archivo_url         VARCHAR(255),
    autor_usuario_id    INT NOT NULL,
    fecha               DATETIME NOT NULL,
    tiene_imagen        BOOLEAN DEFAULT FALSE,
    estado_revision     ENUM('pendiente','revisado') DEFAULT 'pendiente',
    FOREIGN KEY (id_actividad) REFERENCES actividad(id_actividad),
    FOREIGN KEY (autor_usuario_id) REFERENCES usuario(id_usuario)
) ENGINE=InnoDB;

CREATE TABLE validacion (
    id_validacion          INT AUTO_INCREMENT PRIMARY KEY,
    id_evidencia           INT NOT NULL,
    verificador_usuario_id INT NOT NULL,
    verificador_valido     BOOLEAN NOT NULL,
    resultado              BOOLEAN NOT NULL,          -- suma a "Avance actual"
    fecha                  DATETIME NOT NULL,
    observacion            VARCHAR(255),
    FOREIGN KEY (id_evidencia) REFERENCES evidencia(id_evidencia),
    FOREIGN KEY (verificador_usuario_id) REFERENCES usuario(id_usuario)
) ENGINE=InnoDB;

CREATE TABLE indicador (
    id_indicador            INT AUTO_INCREMENT PRIMARY KEY,
    id_meta                 INT NOT NULL,
    avance_actual           DECIMAL(10,2) NOT NULL DEFAULT 0,
    porcentaje_cumplimiento DECIMAL(6,2),
    ajuste                  DECIMAL(6,2) DEFAULT 0,      -- bono/malus aplicado (HU26)
    semaforo                ENUM('verde','amarillo','rojo'),
    fecha_calculo           DATETIME NOT NULL,
    FOREIGN KEY (id_meta) REFERENCES meta(id_meta)
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------
-- ÉPICA 7 — Inteligencia Artificial (HU23)
-- ---------------------------------------------------------------------

CREATE TABLE sugerencia_ia (
    id_sugerencia        INT AUTO_INCREMENT PRIMARY KEY,
    id_actividad         INT NOT NULL,
    id_area_sugerida     INT NOT NULL,
    prioridad_sugerida   ENUM('alta','media','baja') NOT NULL,
    fue_aceptada         BOOLEAN NULL,                -- NULL = sin revisar; TRUE = aceptada; FALSE = corregida
    tiempo_respuesta_ms  INT,
    fecha                DATETIME NOT NULL,
    FOREIGN KEY (id_actividad) REFERENCES actividad(id_actividad),
    FOREIGN KEY (id_area_sugerida) REFERENCES area(id_area)
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------
-- ÉPICA 6 — Reconocimiento (HU21) / ÉPICA 3 — bono/malus (HU26)
-- ---------------------------------------------------------------------

CREATE TABLE reconocimiento (
    id_reconocimiento    INT AUTO_INCREMENT PRIMARY KEY,   -- HU21: automático al 100%
    id_funcionario       INT NOT NULL,
    id_periodo           INT NOT NULL,
    porcentaje_alcanzado DECIMAL(6,2) NOT NULL,
    copia_alcaldesa      BOOLEAN DEFAULT FALSE,
    fecha_emision        DATETIME NOT NULL,
    FOREIGN KEY (id_funcionario) REFERENCES funcionario(id_funcionario),
    FOREIGN KEY (id_periodo) REFERENCES periodo(id_periodo)
) ENGINE=InnoDB;

CREATE TABLE felicitacion_reclamo (
    id_felicitacion_reclamo INT AUTO_INCREMENT PRIMARY KEY,   -- HU26
    id_funcionario      INT NOT NULL,
    tipo                ENUM('felicitacion','reclamo') NOT NULL,
    fecha               DATE NOT NULL,
    motivo              VARCHAR(255),
    usuario_autoriza_id INT NOT NULL,
    impacto_pct         DECIMAL(5,2) NOT NULL,       -- +10% felicitación / -20% reclamo
    FOREIGN KEY (id_funcionario) REFERENCES funcionario(id_funcionario),
    FOREIGN KEY (usuario_autoriza_id) REFERENCES usuario(id_usuario)
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------
-- ÉPICA 4 — Colaboración y Visibilidad (HU14-HU16)
-- ---------------------------------------------------------------------

CREATE TABLE notificacion (
    id_notificacion     INT AUTO_INCREMENT PRIMARY KEY,
    id_usuario_destino  INT NOT NULL,
    tipo                VARCHAR(100) NOT NULL,
    referencia_tabla    VARCHAR(50),
    referencia_id       INT,
    mensaje             VARCHAR(255),
    fecha               DATETIME NOT NULL,
    leida               BOOLEAN DEFAULT FALSE,
    FOREIGN KEY (id_usuario_destino) REFERENCES usuario(id_usuario)
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------
-- ÉPICA 8 — Verificación en terreno (HU29)
-- ---------------------------------------------------------------------

CREATE TABLE verificacion_terreno (
    id_verificacion     INT AUTO_INCREMENT PRIMARY KEY,
    id_actividad        INT NOT NULL,
    id_revisor          INT NOT NULL,
    id_territorio       INT NOT NULL,
    codigo_verificador  VARCHAR(10) NOT NULL,
    foto_evidencia      VARCHAR(255) NOT NULL,
    latitud_gps         DECIMAL(10,7) NOT NULL,
    longitud_gps        DECIMAL(10,7) NOT NULL,
    en_radio_valido     BOOLEAN NOT NULL,              -- se compara con item.radio_tolerancia_metros
    aprobada            BOOLEAN NOT NULL,
    fecha_hora          DATETIME NOT NULL,
    FOREIGN KEY (id_actividad) REFERENCES actividad(id_actividad),
    FOREIGN KEY (id_revisor) REFERENCES funcionario(id_funcionario),
    FOREIGN KEY (id_territorio) REFERENCES territorio(id_territorio)
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------
-- Transversal — Auditoría (HU18/HU19) — también registra 'generar_reporte'
-- ---------------------------------------------------------------------

CREATE TABLE auditoria (
    id_auditoria    INT AUTO_INCREMENT PRIMARY KEY,
    id_usuario      INT NOT NULL,
    evento          VARCHAR(100) NOT NULL,     -- ej. 'crear', 'editar', 'desactivar', 'generar_reporte'
    fecha           DATETIME NOT NULL,
    entidad         VARCHAR(100) NOT NULL,
    entidad_id      INT NOT NULL,
    valor_anterior  JSON,
    valor_nuevo     JSON,                      -- para 'generar_reporte': tipo, delegación, rango de fechas, formato
    FOREIGN KEY (id_usuario) REFERENCES usuario(id_usuario)
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------
-- VISTA — Resumen ejecutivo de la alcaldesa (HU22)
-- Agregada por delegación y periodo, sin datos personales de vecinos.
-- ---------------------------------------------------------------------

CREATE VIEW v_resumen_ejecutivo AS
SELECT
    d.id_delegacion,
    d.nombre                                            AS delegacion,
    p.id_periodo,
    (SELECT COUNT(*) FROM actividad a
       JOIN funcionario fa ON fa.id_funcionario = a.id_funcionario
      WHERE fa.id_delegacion = d.id_delegacion
        AND a.fecha BETWEEN p.fecha_inicio AND p.fecha_termino)                       AS total_solicitudes_ingresadas,
    (SELECT COUNT(*) FROM actividad a
       JOIN funcionario fa ON fa.id_funcionario = a.id_funcionario
      WHERE fa.id_delegacion = d.id_delegacion
        AND a.estado = 'Realizado'
        AND a.fecha BETWEEN p.fecha_inicio AND p.fecha_termino)                       AS total_solicitudes_resueltas,
    (SELECT ROUND(AVG(i.porcentaje_cumplimiento), 2) FROM indicador i
       JOIN meta m             ON m.id_meta = i.id_meta
       JOIN meta_delegacion md ON md.id_meta_delegacion = m.id_meta_delegacion
      WHERE md.id_delegacion = d.id_delegacion
        AND md.id_periodo = p.id_periodo)                                             AS porcentaje_cumplimiento
FROM delegacion d
CROSS JOIN periodo p;
-- El color del semáforo se calcula en la aplicación a partir de porcentaje_cumplimiento.
