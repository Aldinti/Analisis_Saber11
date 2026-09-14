-- F4 Gold · paso 3: agregados con agregación y supresión de grupos pequeños (plan §15.6).
-- Parámetros: ${k_min} y ${min_schools_comparative} desde config/settings.yaml.
-- Celda suprimida: conserva n y suprimido = true; todas las métricas quedan NULL.
-- Supresión complementaria: si en una dimensión queda exactamente una celda suprimida, se
-- suprime también la siguiente más pequeña (así no se deduce restando del total).

-- Puntajes en formato largo con atributos para agrupar (Global + 5 áreas).
CREATE OR REPLACE TABLE g_puntajes AS
SELECT f.resultado_id, f.colegio_id, f.anio, 'Global' AS area, CAST(f.puntaje_global AS INTEGER) AS puntaje,
       c.naturaleza_colegio, u.zona, c.modelo_pedagogico, p.sexo,
       coalesce(CAST(p.estrato AS VARCHAR), 'No informado') AS estrato, f.grupo
FROM fact_resultado f
JOIN dim_colegio c USING (colegio_id)
JOIN dim_ubicacion u USING (ubicacion_id)
JOIN dim_perfil_estudiante p USING (perfil_id)
UNION ALL
SELECT f.resultado_id, f.colegio_id, f.anio, a.area, CAST(fa.puntaje AS INTEGER) AS puntaje,
       c.naturaleza_colegio, u.zona, c.modelo_pedagogico, p.sexo,
       coalesce(CAST(p.estrato AS VARCHAR), 'No informado') AS estrato, f.grupo
FROM fact_resultado_area fa
JOIN fact_resultado f USING (resultado_id)
JOIN dim_area a ON a.area_id = fa.area_id
JOIN dim_colegio c ON c.colegio_id = f.colegio_id
JOIN dim_ubicacion u ON u.ubicacion_id = f.ubicacion_id
JOIN dim_perfil_estudiante p ON p.perfil_id = f.perfil_id;

-- ---------------------------------------------------------------- operativo por colegio
CREATE OR REPLACE TABLE g_operativo_base AS
SELECT
    colegio_id, anio, area,
    CASE WHEN GROUPING(sexo) = 0 THEN 'sexo'
         WHEN GROUPING(estrato) = 0 THEN 'estrato'
         WHEN GROUPING(grupo) = 0 THEN 'grupo'
         ELSE 'Total' END                                   AS dimension,
    CASE WHEN GROUPING(sexo) = 0 THEN sexo
         WHEN GROUPING(estrato) = 0 THEN estrato
         WHEN GROUPING(grupo) = 0 THEN grupo
         ELSE 'Total' END                                   AS categoria,
    count(*)                                                AS n,
    avg(puntaje)                                            AS promedio,
    quantile_cont(puntaje, 0.10)                            AS p10,
    quantile_cont(puntaje, 0.25)                            AS p25,
    quantile_cont(puntaje, 0.50)                            AS p50,
    quantile_cont(puntaje, 0.75)                            AS p75,
    quantile_cont(puntaje, 0.90)                            AS p90
FROM g_puntajes
GROUP BY GROUPING SETS (
    (colegio_id, anio, area),
    (colegio_id, anio, area, sexo),
    (colegio_id, anio, area, estrato),
    (colegio_id, anio, area, grupo)
);

CREATE OR REPLACE TABLE agg_operativo_colegio AS
WITH marcado AS (
    SELECT *,
           n < ${k_min} AS primaria,
           count(*) FILTER (WHERE n < ${k_min}) OVER w                                           AS n_primarias,
           row_number() OVER (PARTITION BY colegio_id, anio, area, dimension ORDER BY n, categoria) AS orden_n
    FROM g_operativo_base
    WINDOW w AS (PARTITION BY colegio_id, anio, area, dimension)
), decidido AS (
    SELECT *, primaria OR (dimension <> 'Total' AND n_primarias = 1 AND orden_n = 2) AS suprimido
    FROM marcado
)
SELECT
    colegio_id,
    CAST(anio AS SMALLINT)                       AS anio,
    area,
    dimension,
    categoria,
    CAST(n AS INTEGER)                           AS n,
    CASE WHEN suprimido THEN NULL ELSE promedio END AS promedio,
    CASE WHEN suprimido THEN NULL ELSE p10 END   AS p10,
    CASE WHEN suprimido THEN NULL ELSE p25 END   AS p25,
    CASE WHEN suprimido THEN NULL ELSE p50 END   AS p50,
    CASE WHEN suprimido THEN NULL ELSE p75 END   AS p75,
    CASE WHEN suprimido THEN NULL ELSE p90 END   AS p90,
    suprimido
FROM decidido
ORDER BY colegio_id, anio, area, dimension, categoria;

-- ---------------------------------------------------------------- benchmark distrital (sin relación con dim_colegio: no filtrado por RLS)
CREATE OR REPLACE TABLE g_benchmark_base AS
SELECT
    anio, area,
    CASE WHEN GROUPING(naturaleza_colegio) = 0 THEN 'naturaleza_colegio'
         WHEN GROUPING(zona) = 0 THEN 'zona'
         WHEN GROUPING(modelo_pedagogico) = 0 THEN 'modelo_pedagogico'
         WHEN GROUPING(sexo) = 0 THEN 'sexo'
         WHEN GROUPING(estrato) = 0 THEN 'estrato'
         ELSE 'Total' END                                   AS dimension,
    CASE WHEN GROUPING(naturaleza_colegio) = 0 THEN naturaleza_colegio
         WHEN GROUPING(zona) = 0 THEN zona
         WHEN GROUPING(modelo_pedagogico) = 0 THEN modelo_pedagogico
         WHEN GROUPING(sexo) = 0 THEN sexo
         WHEN GROUPING(estrato) = 0 THEN estrato
         ELSE 'Total' END                                   AS categoria,
    count(*)                                                AS n,
    count(DISTINCT colegio_id)                              AS n_colegios,
    avg(puntaje)                                            AS promedio,
    quantile_cont(puntaje, 0.25)                            AS p25,
    quantile_cont(puntaje, 0.50)                            AS p50,
    quantile_cont(puntaje, 0.75)                            AS p75
FROM g_puntajes
GROUP BY GROUPING SETS (
    (anio, area),
    (anio, area, naturaleza_colegio),
    (anio, area, zona),
    (anio, area, modelo_pedagogico),
    (anio, area, sexo),
    (anio, area, estrato)
);

CREATE OR REPLACE TABLE agg_benchmark_distrito AS
WITH marcado AS (
    SELECT *,
           (n < ${k_min} OR n_colegios < ${min_schools_comparative}) AS primaria,
           count(*) FILTER (WHERE n < ${k_min} OR n_colegios < ${min_schools_comparative}) OVER w AS n_primarias,
           row_number() OVER (PARTITION BY anio, area, dimension ORDER BY n, categoria) AS orden_n
    FROM g_benchmark_base
    WINDOW w AS (PARTITION BY anio, area, dimension)
), decidido AS (
    SELECT *, primaria OR (dimension <> 'Total' AND n_primarias = 1 AND orden_n = 2) AS suprimido
    FROM marcado
)
SELECT
    CAST(anio AS SMALLINT)                          AS anio,
    area,
    dimension,
    categoria,
    CAST(n AS INTEGER)                              AS n,
    CAST(n_colegios AS INTEGER)                     AS n_colegios,
    CASE WHEN suprimido THEN NULL ELSE promedio END AS promedio,
    CASE WHEN suprimido THEN NULL ELSE p25 END      AS p25,
    CASE WHEN suprimido THEN NULL ELSE p50 END      AS p50,
    CASE WHEN suprimido THEN NULL ELSE p75 END      AS p75,
    suprimido
FROM decidido
ORDER BY anio, area, dimension, categoria;
