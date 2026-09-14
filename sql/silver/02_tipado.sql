-- F3 Silver · paso 2: tipado (TRY_CAST) y categorías canónicas.
-- Los dominios cerrados usan un mapa explícito; un valor no reconocido queda NULL y el paso 3
-- lo distingue de un vacío gracias a las columnas *_txt.
-- Los puntajes se tipan como SMALLINT para poder detectar valores fuera de escala (p. ej. 150).
CREATE OR REPLACE TABLE s_tipado AS
SELECT
    t._fila_fuente,
    t._ingest_id,
    t._source_sha256,
    TRY_CAST(t.anio AS SMALLINT)                                           AS anio,
    CASE lower(t.periodo) WHEN 'i' THEN 'I' WHEN '1' THEN 'I'
                          WHEN 'ii' THEN 'II' WHEN '2' THEN 'II' END       AS periodo,
    cp.canonico                                                            AS pais,
    cd.canonico                                                            AS departamento,
    cm.canonico                                                            AS municipio,
    CASE lower(strip_accents(t.zona)) WHEN 'urbana' THEN 'Urbana'
                                      WHEN 'rural' THEN 'Rural' END        AS zona,
    TRY_CAST(t.estrato AS TINYINT)                                         AS estrato,
    cc.canonico                                                            AS nombre_colegio,
    CASE lower(strip_accents(t.naturaleza_colegio))
        WHEN 'publica' THEN 'Pública' WHEN 'oficial' THEN 'Pública'
        WHEN 'privada' THEN 'Privada' WHEN 'no oficial' THEN 'Privada' END AS naturaleza_colegio,
    cmp.canonico                                                           AS modelo_pedagogico,
    TRY_CAST(t.nrodoc AS BIGINT)                                           AS nrodoc,
    CASE lower(strip_accents(t.sexo))
        WHEN 'masculino' THEN 'Masculino' WHEN 'm' THEN 'Masculino'
        WHEN 'femenino' THEN 'Femenino' WHEN 'f' THEN 'Femenino' END      AS sexo,
    nullif(regexp_replace(regexp_replace(t.grupo, '[^0-9A-Za-z]+', '-', 'g'), '^-+|-+$', '', 'g'), '') AS grupo,
    TRY_CAST(t.puntaje_global AS SMALLINT)                                 AS puntaje_global,
    TRY_CAST(t.punt_lectura_critica AS SMALLINT)                           AS punt_lectura_critica,
    TRY_CAST(t.punt_matematicas AS SMALLINT)                               AS punt_matematicas,
    TRY_CAST(t.punt_sociales AS SMALLINT)                                  AS punt_sociales,
    TRY_CAST(t.punt_ciencias AS SMALLINT)                                  AS punt_ciencias,
    TRY_CAST(t.punt_ingles AS SMALLINT)                                    AS punt_ingles,
    -- texto previo al tipado, solo para clasificar motivos de rechazo
    t.anio AS anio_txt, t.periodo AS periodo_txt, t.zona AS zona_txt, t.estrato AS estrato_txt,
    t.naturaleza_colegio AS naturaleza_txt, t.nrodoc IS NOT NULL AS nrodoc_informado, t.sexo AS sexo_txt,
    t.puntaje_global AS puntaje_global_txt, t.punt_lectura_critica AS punt_lectura_critica_txt,
    t.punt_matematicas AS punt_matematicas_txt, t.punt_sociales AS punt_sociales_txt,
    t.punt_ciencias AS punt_ciencias_txt, t.punt_ingles AS punt_ingles_txt
FROM s_texto t
LEFT JOIN s_canon cp  ON cp.columna = 'pais'              AND cp.clave  = lower(strip_accents(t.pais))
LEFT JOIN s_canon cd  ON cd.columna = 'departamento'      AND cd.clave  = lower(strip_accents(t.departamento))
LEFT JOIN s_canon cm  ON cm.columna = 'municipio'         AND cm.clave  = lower(strip_accents(t.municipio))
LEFT JOIN s_canon cc  ON cc.columna = 'nombre_colegio'    AND cc.clave  = lower(strip_accents(t.nombre_colegio))
LEFT JOIN s_canon cmp ON cmp.columna = 'modelo_pedagogico' AND cmp.clave = lower(strip_accents(t.modelo_pedagogico));
