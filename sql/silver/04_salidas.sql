-- F3 Silver · paso 4: tablas finales.
-- silver_resultados: filas válidas, tipos del plan, flags de calidad, sin PII, orden de la fuente.
-- silver_rechazos:   cuarentena con motivo y valores de texto originales NO personales.

-- Límites IQR (1,5 × rango intercuartílico) calculados sobre las filas válidas de esta carga.
CREATE OR REPLACE TABLE s_limites AS
SELECT
    quantile_cont(puntaje_global, 0.25) AS q1_g,  quantile_cont(puntaje_global, 0.75) AS q3_g,
    quantile_cont(punt_lectura_critica, 0.25) AS q1_lc, quantile_cont(punt_lectura_critica, 0.75) AS q3_lc,
    quantile_cont(punt_matematicas, 0.25) AS q1_m,  quantile_cont(punt_matematicas, 0.75) AS q3_m,
    quantile_cont(punt_sociales, 0.25) AS q1_s,     quantile_cont(punt_sociales, 0.75) AS q3_s,
    quantile_cont(punt_ciencias, 0.25) AS q1_c,     quantile_cont(punt_ciencias, 0.75) AS q3_c,
    quantile_cont(punt_ingles, 0.25) AS q1_i,       quantile_cont(punt_ingles, 0.75) AS q3_i
FROM s_evaluado
WHERE motivo_rechazo IS NULL;

CREATE OR REPLACE MACRO fuera_iqr(x, q1, q3) AS
    coalesce(x < q1 - 1.5 * (q3 - q1) OR x > q3 + 1.5 * (q3 - q1), false);

CREATE OR REPLACE TABLE silver_resultados AS
SELECT
    CAST(e.anio AS SMALLINT)                                  AS anio,
    e.periodo                                                 AS periodo,
    coalesce(e.periodo, 'Unica')                              AS jornada,
    coalesce(e.pais, 'No informado')                          AS pais,
    coalesce(e.departamento, 'No informado')                  AS departamento,
    coalesce(e.municipio, 'No informado')                     AS municipio,
    e.zona                                                    AS zona,
    CAST(e.estrato AS TINYINT)                                AS estrato,
    e.nombre_colegio                                          AS nombre_colegio,
    coalesce(e.naturaleza_colegio, 'No informado')            AS naturaleza_colegio,
    coalesce(e.modelo_pedagogico, 'No informado')             AS modelo_pedagogico,
    e.estudiante_pid                                          AS estudiante_pid,
    e.sexo                                                    AS sexo,
    coalesce(e.grupo, 'No informado')                         AS grupo,
    CAST(e.puntaje_global AS SMALLINT)                        AS puntaje_global,
    CAST(e.punt_lectura_critica AS TINYINT)                   AS punt_lectura_critica,
    CAST(e.punt_matematicas AS TINYINT)                       AS punt_matematicas,
    CAST(e.punt_sociales AS TINYINT)                          AS punt_sociales,
    CAST(e.punt_ciencias AS TINYINT)                          AS punt_ciencias,
    CAST(e.punt_ingles AS TINYINT)                            AS punt_ingles,
    (fuera_iqr(e.puntaje_global, l.q1_g, l.q3_g)
        OR fuera_iqr(e.punt_lectura_critica, l.q1_lc, l.q3_lc)
        OR fuera_iqr(e.punt_matematicas, l.q1_m, l.q3_m)
        OR fuera_iqr(e.punt_sociales, l.q1_s, l.q3_s)
        OR fuera_iqr(e.punt_ciencias, l.q1_c, l.q3_c)
        OR fuera_iqr(e.punt_ingles, l.q1_i, l.q3_i))          AS flag_atipico,
    e.puntaje_global <> round(5.0 * (3.0 * (e.punt_lectura_critica + e.punt_matematicas + e.punt_sociales
                              + e.punt_ciencias) + e.punt_ingles) / 13.0) AS flag_inconsistencia_global,
    e._ingest_id                                              AS _ingest_id,
    e._source_sha256                                          AS _source_sha256
FROM s_evaluado e
CROSS JOIN s_limites l
WHERE e.motivo_rechazo IS NULL
ORDER BY e._fila_fuente;

CREATE OR REPLACE TABLE silver_rechazos AS
SELECT
    e._ingest_id,
    e._source_sha256,
    e._fila_fuente,
    e.motivo_rechazo,
    e.estudiante_pid,
    t.anio, t.periodo, t.pais, t.departamento, t.municipio, t.zona, t.estrato, t.nombre_colegio,
    t.naturaleza_colegio, t.modelo_pedagogico, t.sexo, t.grupo, t.puntaje_global,
    t.punt_lectura_critica, t.punt_matematicas, t.punt_sociales, t.punt_ciencias, t.punt_ingles
FROM s_evaluado e
JOIN s_texto t ON t._fila_fuente = e._fila_fuente
WHERE e.motivo_rechazo IS NOT NULL
ORDER BY e._fila_fuente;
