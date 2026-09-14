-- F3 Silver · paso 3: motivos de rechazo y duplicados.
-- Requiere s_tipado con la columna estudiante_pid ya calculada (HMAC en Python).
-- Una fila se rechaza (cuarentena) si tiene al menos un motivo; los motivos se concatenan con ';'.
-- sexo y estrato vacíos NO se rechazan (quedan NULL; los mide DQ-COM-002).
CREATE OR REPLACE TABLE s_evaluado AS
WITH motivos AS (
    SELECT
        *,
        list_filter([
            CASE WHEN anio IS NULL THEN (CASE WHEN anio_txt IS NULL THEN 'nulo:anio' ELSE 'tipo_invalido:anio' END)
                 WHEN anio NOT BETWEEN 2000 AND year(current_date) THEN 'fuera_de_dominio:anio' END,
            CASE WHEN nombre_colegio IS NULL THEN 'nulo:nombre_colegio' END,
            CASE WHEN nrodoc IS NULL THEN (CASE WHEN nrodoc_informado THEN 'tipo_invalido:nrodoc' ELSE 'nulo:nrodoc' END) END,
            CASE WHEN periodo IS NULL AND periodo_txt IS NOT NULL THEN 'categoria_invalida:periodo' END,
            CASE WHEN zona IS NULL THEN (CASE WHEN zona_txt IS NULL THEN 'nulo:zona' ELSE 'categoria_invalida:zona' END) END,
            CASE WHEN naturaleza_colegio IS NULL AND naturaleza_txt IS NOT NULL THEN 'categoria_invalida:naturaleza_colegio' END,
            CASE WHEN sexo IS NULL AND sexo_txt IS NOT NULL THEN 'categoria_invalida:sexo' END,
            CASE WHEN estrato IS NULL AND estrato_txt IS NOT NULL THEN 'tipo_invalido:estrato'
                 WHEN estrato NOT BETWEEN 1 AND 6 THEN 'fuera_de_dominio:estrato' END,
            CASE WHEN puntaje_global IS NULL
                     THEN (CASE WHEN puntaje_global_txt IS NULL THEN 'nulo:puntaje_global' ELSE 'tipo_invalido:puntaje_global' END)
                 WHEN puntaje_global NOT BETWEEN 0 AND 500 THEN 'fuera_de_escala:puntaje_global' END,
            CASE WHEN punt_lectura_critica IS NULL
                     THEN (CASE WHEN punt_lectura_critica_txt IS NULL THEN 'nulo:punt_lectura_critica' ELSE 'tipo_invalido:punt_lectura_critica' END)
                 WHEN punt_lectura_critica NOT BETWEEN 0 AND 100 THEN 'fuera_de_escala:punt_lectura_critica' END,
            CASE WHEN punt_matematicas IS NULL
                     THEN (CASE WHEN punt_matematicas_txt IS NULL THEN 'nulo:punt_matematicas' ELSE 'tipo_invalido:punt_matematicas' END)
                 WHEN punt_matematicas NOT BETWEEN 0 AND 100 THEN 'fuera_de_escala:punt_matematicas' END,
            CASE WHEN punt_sociales IS NULL
                     THEN (CASE WHEN punt_sociales_txt IS NULL THEN 'nulo:punt_sociales' ELSE 'tipo_invalido:punt_sociales' END)
                 WHEN punt_sociales NOT BETWEEN 0 AND 100 THEN 'fuera_de_escala:punt_sociales' END,
            CASE WHEN punt_ciencias IS NULL
                     THEN (CASE WHEN punt_ciencias_txt IS NULL THEN 'nulo:punt_ciencias' ELSE 'tipo_invalido:punt_ciencias' END)
                 WHEN punt_ciencias NOT BETWEEN 0 AND 100 THEN 'fuera_de_escala:punt_ciencias' END,
            CASE WHEN punt_ingles IS NULL
                     THEN (CASE WHEN punt_ingles_txt IS NULL THEN 'nulo:punt_ingles' ELSE 'tipo_invalido:punt_ingles' END)
                 WHEN punt_ingles NOT BETWEEN 0 AND 100 THEN 'fuera_de_escala:punt_ingles' END
        ], lambda m: m IS NOT NULL) AS lista_motivos
    FROM s_tipado
), duplicados AS (
    -- Entre filas sin otros motivos, la primera aparición en la fuente se conserva.
    SELECT
        *,
        CASE WHEN len(lista_motivos) = 0
             THEN row_number() OVER (PARTITION BY estudiante_pid, anio, periodo, len(lista_motivos) = 0
                                     ORDER BY _fila_fuente) END AS orden_evaluacion
    FROM motivos
)
SELECT
    * EXCLUDE (lista_motivos, orden_evaluacion),
    list_aggregate(
        CASE WHEN orden_evaluacion > 1 THEN list_append(lista_motivos, 'duplicado:estudiante_anio_periodo')
             ELSE lista_motivos END,
        'string_agg', ';') AS motivo_rechazo
FROM duplicados;
