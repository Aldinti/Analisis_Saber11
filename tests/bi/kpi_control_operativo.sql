-- F7 · Consultas de control del dashboard operativo (tolerancia 0,01).
-- Se calculan desde las filas de hechos (fact_resultado / fact_resultado_area), NO desde agg_operativo_colegio,
-- para contrastar de forma independiente el camino de agregados + medidas DAX con supresión.
-- Uso: python -m saber11.bi.kpi_control --tablero operativo

CREATE OR REPLACE VIEW fact AS
SELECT * FROM read_parquet('${gold}/fact_resultado/**/*.parquet', hive_partitioning = true);
CREATE OR REPLACE VIEW fact_area AS SELECT * FROM read_parquet('${gold}/fact_resultado_area.parquet');
CREATE OR REPLACE VIEW colegio AS SELECT * FROM read_parquet('${gold}/dim_colegio.parquet');
CREATE OR REPLACE VIEW perfil AS SELECT * FROM read_parquet('${gold}/dim_perfil_estudiante.parquet');
CREATE OR REPLACE VIEW area AS SELECT * FROM read_parquet('${gold}/dim_area.parquet');

-- Puntajes largos: Global + 5 áreas, con colegio, año, sexo, estrato y grupo.
CREATE OR REPLACE VIEW puntajes AS
SELECT c.nombre_colegio, f.anio, 'Global' AS area, CAST(f.puntaje_global AS DOUBLE) AS puntaje,
       p.sexo, CAST(p.estrato AS VARCHAR) AS estrato, f.grupo
FROM fact f JOIN colegio c USING (colegio_id) JOIN perfil p USING (perfil_id)
UNION ALL
SELECT c.nombre_colegio, f.anio, a.area, CAST(fa.puntaje AS DOUBLE), p.sexo, CAST(p.estrato AS VARCHAR), f.grupo
FROM fact_area fa JOIN fact f USING (resultado_id) JOIN area a ON a.area_id = fa.area_id
JOIN colegio c ON c.colegio_id = f.colegio_id JOIN perfil p ON p.perfil_id = f.perfil_id;

CREATE OR REPLACE TABLE kpi_control AS
SELECT 'ABC 2024 · Global' AS escenario, 'Evaluados Colegio' AS kpi, CAST(count(*) AS DOUBLE) AS valor
    FROM puntajes WHERE nombre_colegio = 'ABC' AND anio = 2024 AND area = 'Global'
UNION ALL SELECT 'ABC 2024 · Global', 'Promedio Colegio', avg(puntaje)
    FROM puntajes WHERE nombre_colegio = 'ABC' AND anio = 2024 AND area = 'Global'
UNION ALL SELECT 'ABC 2024 · Global', 'Mediana Colegio', quantile_cont(puntaje, 0.5)
    FROM puntajes WHERE nombre_colegio = 'ABC' AND anio = 2024 AND area = 'Global'
UNION ALL SELECT 'ABC 2024 · Global', 'Percentil 90 Colegio', quantile_cont(puntaje, 0.9)
    FROM puntajes WHERE nombre_colegio = 'ABC' AND anio = 2024 AND area = 'Global'
UNION ALL SELECT 'ABC 2024 · Global', 'Promedio Distrito', avg(puntaje)
    FROM puntajes WHERE anio = 2024 AND area = 'Global'
UNION ALL SELECT 'ABC 2024 · Global', 'Brecha vs Distrito',
    (SELECT avg(puntaje) FROM puntajes WHERE nombre_colegio = 'ABC' AND anio = 2024 AND area = 'Global')
  - (SELECT avg(puntaje) FROM puntajes WHERE anio = 2024 AND area = 'Global')
UNION ALL SELECT 'ABC 2021-2024 · Global', 'Promedio Colegio', avg(puntaje)
    FROM puntajes WHERE nombre_colegio = 'ABC' AND area = 'Global'
UNION ALL SELECT 'ABC 2021-2024 · Global', 'Evaluados Colegio', count(*)
    FROM puntajes WHERE nombre_colegio = 'ABC' AND area = 'Global'
UNION ALL SELECT 'ABC 2024 · Matemáticas · estrato 1', 'Promedio Operativo', avg(puntaje)
    FROM puntajes WHERE nombre_colegio = 'ABC' AND anio = 2024 AND area = 'Matemáticas' AND estrato = '1'
UNION ALL SELECT 'ABC 2024 · Matemáticas · estrato 1', 'Evaluados Visible', count(*)
    FROM puntajes WHERE nombre_colegio = 'ABC' AND anio = 2024 AND area = 'Matemáticas' AND estrato = '1'
UNION ALL SELECT 'ABC 2024 · Matemáticas · estrato 1', 'Promedio Distrito Categoria', avg(puntaje)
    FROM puntajes WHERE anio = 2024 AND area = 'Matemáticas' AND estrato = '1'
UNION ALL SELECT 'ABC 2024 · Global · sexo Femenino', 'Promedio Operativo', avg(puntaje)
    FROM puntajes WHERE nombre_colegio = 'ABC' AND anio = 2024 AND area = 'Global' AND sexo = 'Femenino'
UNION ALL SELECT 'ABC 2024 · Global · grupo 11-2', 'Promedio Operativo', avg(puntaje)
    FROM puntajes WHERE nombre_colegio = 'ABC' AND anio = 2024 AND area = 'Global' AND grupo = '11-2';
