-- F3 Silver · paso 1: texto limpio.
-- Entrada: vista bronze_normalizado (columnas Bronze renombradas a snake_case + _fila_fuente).
-- Recorta espacios, colapsa espacios internos y convierte vacíos en NULL.
-- Minimización: nombres y apellidos no se seleccionan; nrodoc solo se usa para el seudónimo.
CREATE OR REPLACE TABLE s_texto AS
SELECT
    _fila_fuente,
    _ingest_id,
    _source_sha256,
    nullif(regexp_replace(trim(anio), '\s+', ' ', 'g'), '')                 AS anio,
    nullif(regexp_replace(trim(periodo), '\s+', ' ', 'g'), '')              AS periodo,
    nullif(regexp_replace(trim(pais), '\s+', ' ', 'g'), '')                 AS pais,
    nullif(regexp_replace(trim(departamento), '\s+', ' ', 'g'), '')         AS departamento,
    nullif(regexp_replace(trim(municipio), '\s+', ' ', 'g'), '')            AS municipio,
    nullif(regexp_replace(trim(zona), '\s+', ' ', 'g'), '')                 AS zona,
    nullif(regexp_replace(trim(estrato), '\s+', ' ', 'g'), '')              AS estrato,
    nullif(regexp_replace(trim(nombre_colegio), '\s+', ' ', 'g'), '')       AS nombre_colegio,
    nullif(regexp_replace(trim(naturaleza_colegio), '\s+', ' ', 'g'), '')   AS naturaleza_colegio,
    nullif(regexp_replace(trim(modelo_pedagogico), '\s+', ' ', 'g'), '')    AS modelo_pedagogico,
    nullif(trim(nrodoc), '')                                                AS nrodoc,
    nullif(regexp_replace(trim(sexo), '\s+', ' ', 'g'), '')                 AS sexo,
    nullif(regexp_replace(trim(grupo), '\s+', ' ', 'g'), '')                AS grupo,
    nullif(trim(puntaje_global), '')                                        AS puntaje_global,
    nullif(trim(punt_lectura_critica), '')                                  AS punt_lectura_critica,
    nullif(trim(punt_matematicas), '')                                      AS punt_matematicas,
    nullif(trim(punt_sociales), '')                                         AS punt_sociales,
    nullif(trim(punt_ciencias), '')                                         AS punt_ciencias,
    nullif(trim(punt_ingles), '')                                           AS punt_ingles
FROM bronze_normalizado;

-- Escritura canónica de categorías abiertas: para cada clave (minúsculas, sin tildes) se toma
-- la escritura más frecuente (desempate alfabético, determinista).
CREATE OR REPLACE TABLE s_canon AS
WITH valores AS (
    SELECT 'pais' AS columna, pais AS valor FROM s_texto
    UNION ALL SELECT 'departamento', departamento FROM s_texto
    UNION ALL SELECT 'municipio', municipio FROM s_texto
    UNION ALL SELECT 'nombre_colegio', nombre_colegio FROM s_texto
    UNION ALL SELECT 'modelo_pedagogico', modelo_pedagogico FROM s_texto
), conteos AS (
    SELECT columna, lower(strip_accents(valor)) AS clave, valor, count(*) AS n
    FROM valores
    WHERE valor IS NOT NULL
    GROUP BY columna, clave, valor
)
SELECT columna, clave, first(valor ORDER BY n DESC, valor) AS canonico
FROM conteos
GROUP BY columna, clave;
