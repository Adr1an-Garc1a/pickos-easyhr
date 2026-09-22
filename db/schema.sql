-- =============================================================================
-- Pick'Os · Easy HR — Esquema de base de datos (Cloud SQL for PostgreSQL)
-- =============================================================================
-- Nota de diseño: el requerimiento original de campos fue:
--   id, nombre, apellido paterno, apellido materno, fecha de ingreso, rol,
--   gerente, área.
-- Se agregó `fecha_nacimiento` porque es indispensable para que el
-- "Birthday Agent" pueda calcular quién cumple años; sin este dato el
-- subagente de cumpleaños no puede funcionar. Es el único campo añadido
-- fuera de lo solicitado explícitamente.

CREATE TABLE IF NOT EXISTS areas (
    id          SERIAL PRIMARY KEY,
    nombre      VARCHAR(60) NOT NULL UNIQUE
);

INSERT INTO areas (nombre) VALUES
    ('Recursos Humanos'), ('Legal'), ('Contabilidad'), ('Marketing'),
    ('Ingenieria'), ('PMO'), ('Calidad'), ('Ventas')
ON CONFLICT (nombre) DO NOTHING;

CREATE TABLE IF NOT EXISTS employees (
    id                  SERIAL PRIMARY KEY,
    nombre              VARCHAR(80)  NOT NULL,
    apellido_paterno    VARCHAR(80)  NOT NULL,
    apellido_materno    VARCHAR(80)  NOT NULL,
    fecha_nacimiento    DATE         NOT NULL,
    fecha_ingreso       DATE         NOT NULL,
    rol                 VARCHAR(120) NOT NULL,
    area_id             INTEGER      NOT NULL REFERENCES areas(id),
    gerente_id          INTEGER      REFERENCES employees(id) ON DELETE SET NULL,
    email               VARCHAR(150) UNIQUE,
    activo              BOOLEAN      NOT NULL DEFAULT TRUE,
    creado_en           TIMESTAMPTZ  NOT NULL DEFAULT now(),
    actualizado_en      TIMESTAMPTZ  NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_employees_area ON employees(area_id);
CREATE INDEX IF NOT EXISTS idx_employees_gerente ON employees(gerente_id);
-- Índice para que el Birthday Agent busque rápido por día/mes de nacimiento
CREATE INDEX IF NOT EXISTS idx_employees_birthday_md
    ON employees (EXTRACT(MONTH FROM fecha_nacimiento), EXTRACT(DAY FROM fecha_nacimiento));

-- Vista de conveniencia usada por employee-api para no repetir el JOIN de área/gerente
CREATE OR REPLACE VIEW v_employees AS
SELECT
    e.id,
    e.nombre,
    e.apellido_paterno,
    e.apellido_materno,
    e.fecha_nacimiento,
    e.fecha_ingreso,
    e.rol,
    a.nombre AS area,
    e.area_id,
    e.gerente_id,
    (g.nombre || ' ' || g.apellido_paterno) AS gerente_nombre,
    e.email,
    e.activo
FROM employees e
JOIN areas a ON a.id = e.area_id
LEFT JOIN employees g ON g.id = e.gerente_id;
