-- F4 Gold · paso 1: dimensiones.
-- Entrada: vista silver_resultados (Silver aprobado por el quality gate).
-- Claves sustitutas estables (ADR-0017): entero BIGINT derivado de MD5 de la clave natural
-- normalizada. No cambian al agregar colegios, años o cargas nuevas.
CREATE OR REPLACE MACRO clave_estable(texto) AS CAST(md5_number_upper(texto) >> 1 AS BIGINT);
CREATE OR REPLACE MACRO clave_natural(texto) AS lower(strip_accents(trim(texto)));

CREATE OR REPLACE TABLE dim_tiempo AS
SELECT DISTINCT
    CAST(anio * 10 + CASE periodo WHEN 'I' THEN 1 WHEN 'II' THEN 2 ELSE 0 END AS INTEGER) AS tiempo_id,
    anio,
    periodo,
    jornada
FROM silver_resultados
ORDER BY tiempo_id;

-- Si un colegio cambió de naturaleza o modelo (DQ-CON-001 lo advierte), se toma el valor del año más reciente.
CREATE OR REPLACE TABLE dim_colegio AS
SELECT
    clave_estable('colegio|' || clave_natural(nombre_colegio))                AS colegio_id,
    nombre_colegio,
    first(naturaleza_colegio ORDER BY anio DESC, naturaleza_colegio)          AS naturaleza_colegio,
    first(modelo_pedagogico ORDER BY anio DESC, modelo_pedagogico)            AS modelo_pedagogico
FROM silver_resultados
GROUP BY nombre_colegio
ORDER BY nombre_colegio;

CREATE OR REPLACE TABLE dim_ubicacion AS
SELECT DISTINCT
    clave_estable('ubicacion|' || clave_natural(pais) || '|' || clave_natural(departamento) || '|'
                  || clave_natural(municipio) || '|' || clave_natural(zona)) AS ubicacion_id,
    pais,
    departamento,
    municipio,
    zona
FROM silver_resultados
ORDER BY pais, departamento, municipio, zona;

-- Dimensión "junk" de perfil: evita llevar el seudónimo del estudiante a Gold.
CREATE OR REPLACE TABLE dim_perfil_estudiante AS
SELECT DISTINCT
    clave_estable('perfil|' || coalesce(sexo, 'No informado') || '|' || coalesce(CAST(estrato AS VARCHAR), 'No informado')) AS perfil_id,
    coalesce(sexo, 'No informado') AS sexo,
    estrato
FROM silver_resultados
ORDER BY sexo, estrato;

CREATE OR REPLACE TABLE dim_area AS
SELECT * FROM (VALUES
    (CAST(1 AS TINYINT), 'Lectura Crítica',      CAST(3 AS TINYINT)),
    (CAST(2 AS TINYINT), 'Matemáticas',          CAST(3 AS TINYINT)),
    (CAST(3 AS TINYINT), 'Sociales y Ciudadana', CAST(3 AS TINYINT)),
    (CAST(4 AS TINYINT), 'Ciencias Naturales',   CAST(3 AS TINYINT)),
    (CAST(5 AS TINYINT), 'Inglés',               CAST(1 AS TINYINT))
) AS t(area_id, area, peso_global);
