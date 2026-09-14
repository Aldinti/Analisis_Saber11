-- F4 Gold · paso 2: tablas de hechos.
-- Grano de fact_resultado: una evaluación (estudiante × año × periodo). Sin estudiante_pid:
-- resultado_id es una clave estable derivada, no se publica el seudónimo.
CREATE OR REPLACE TABLE fact_resultado AS
SELECT
    clave_estable('resultado|' || s.estudiante_pid || '|' || s.anio || '|' || coalesce(s.periodo, 'No informado')) AS resultado_id,
    t.tiempo_id,
    c.colegio_id,
    u.ubicacion_id,
    p.perfil_id,
    s.grupo,
    s.puntaje_global,
    s.punt_lectura_critica,
    s.punt_matematicas,
    s.punt_sociales,
    s.punt_ciencias,
    s.punt_ingles,
    s.anio,
    s.periodo
FROM silver_resultados s
JOIN dim_tiempo t
  ON t.anio = s.anio AND t.periodo IS NOT DISTINCT FROM s.periodo
JOIN dim_colegio c
  ON c.nombre_colegio = s.nombre_colegio
JOIN dim_ubicacion u
  ON u.pais = s.pais AND u.departamento = s.departamento AND u.municipio = s.municipio AND u.zona = s.zona
JOIN dim_perfil_estudiante p
  ON p.sexo = coalesce(s.sexo, 'No informado') AND p.estrato IS NOT DISTINCT FROM s.estrato
ORDER BY s.anio, s.periodo, c.colegio_id, resultado_id;

-- Formato largo por área (5 filas por evaluación). Puntaje en SMALLINT: sumas seguras sin desborde.
CREATE OR REPLACE TABLE fact_resultado_area AS
SELECT
    f.resultado_id,
    a.area_id,
    CAST(CASE a.area_id
             WHEN 1 THEN f.punt_lectura_critica
             WHEN 2 THEN f.punt_matematicas
             WHEN 3 THEN f.punt_sociales
             WHEN 4 THEN f.punt_ciencias
             WHEN 5 THEN f.punt_ingles
         END AS SMALLINT) AS puntaje,
    f.tiempo_id,
    f.colegio_id,
    f.perfil_id
FROM fact_resultado f
CROSS JOIN dim_area a
ORDER BY f.resultado_id, a.area_id;
