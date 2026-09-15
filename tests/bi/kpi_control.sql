-- F6 · Consultas de control de KPIs del dashboard estratégico (plan §8 F6: tolerancia 0,01).
-- Se ejecutan con DuckDB sobre data/gold y se comparan con las medidas DAX del modelo
-- (docs/bi/medidas_dax.md). Cada consulta devuelve (escenario, kpi, valor).
-- Uso: python -m saber11.bi.kpi_control   (desde la raíz, con PYTHONPATH=src)

CREATE OR REPLACE VIEW fact AS
SELECT * FROM read_parquet('${gold}/fact_resultado/**/*.parquet', hive_partitioning = true);
CREATE OR REPLACE VIEW fact_area AS SELECT * FROM read_parquet('${gold}/fact_resultado_area.parquet');
CREATE OR REPLACE VIEW colegio AS SELECT * FROM read_parquet('${gold}/dim_colegio.parquet');
CREATE OR REPLACE VIEW ubicacion AS SELECT * FROM read_parquet('${gold}/dim_ubicacion.parquet');
CREATE OR REPLACE VIEW perfil AS SELECT * FROM read_parquet('${gold}/dim_perfil_estudiante.parquet');
CREATE OR REPLACE VIEW area AS SELECT * FROM read_parquet('${gold}/dim_area.parquet');
CREATE OR REPLACE VIEW tiempo AS SELECT * FROM read_parquet('${gold}/dim_tiempo.parquet');
CREATE OR REPLACE VIEW benchmark AS SELECT * FROM read_parquet('${gold}/agg_benchmark_distrito.parquet');

CREATE OR REPLACE TABLE kpi_control AS
-- Totales sin filtros
SELECT 'Todos' AS escenario, 'Evaluados' AS kpi, CAST(count(*) AS DOUBLE) AS valor FROM fact
UNION ALL SELECT 'Todos', 'Promedio Global', avg(puntaje_global) FROM fact
UNION ALL SELECT 'Todos', 'Percentil 75 Colegio', quantile_cont(puntaje_global, 0.75) FROM fact
UNION ALL SELECT 'Todos', 'Mediana Global', quantile_cont(puntaje_global, 0.5) FROM fact
-- Año 2024
UNION ALL SELECT 'Año 2024', 'Evaluados', count(*) FROM fact WHERE anio = 2024
UNION ALL SELECT 'Año 2024', 'Promedio Global', avg(puntaje_global) FROM fact WHERE anio = 2024
UNION ALL SELECT 'Año 2024', 'Promedio Global AA', avg(puntaje_global) FROM fact WHERE anio = 2023
UNION ALL SELECT 'Año 2024', 'Variacion Interanual',
    (SELECT avg(puntaje_global) FROM fact WHERE anio = 2024) / (SELECT avg(puntaje_global) FROM fact WHERE anio = 2023) - 1
UNION ALL SELECT 'Año 2024', 'Percentil 75 Distrital', quantile_cont(puntaje_global, 0.75) FROM fact WHERE anio = 2024
UNION ALL SELECT 'Año 2024', 'Pct Estudiantes >= P75 Distrital',
    avg(CASE WHEN puntaje_global >= (SELECT quantile_cont(puntaje_global, 0.75) FROM fact WHERE anio = 2024) THEN 1.0 ELSE 0 END)
    FROM fact WHERE anio = 2024
UNION ALL SELECT 'Año 2024', 'Diferencial Sector',
    (SELECT avg(f.puntaje_global) FROM fact f JOIN colegio c USING (colegio_id) WHERE f.anio = 2024 AND c.naturaleza_colegio = 'Pública')
  - (SELECT avg(f.puntaje_global) FROM fact f JOIN colegio c USING (colegio_id) WHERE f.anio = 2024 AND c.naturaleza_colegio = 'Privada')
UNION ALL SELECT 'Año 2024', 'Diferencial Zona',
    (SELECT avg(f.puntaje_global) FROM fact f JOIN ubicacion u USING (ubicacion_id) WHERE f.anio = 2024 AND u.zona = 'Urbana')
  - (SELECT avg(f.puntaje_global) FROM fact f JOIN ubicacion u USING (ubicacion_id) WHERE f.anio = 2024 AND u.zona = 'Rural')
UNION ALL SELECT 'Año 2024', 'Promedio Distrito',
    sum(promedio * n) / sum(n) FROM benchmark WHERE anio = 2024 AND area = 'Global' AND dimension = 'Total' AND NOT suprimido
UNION ALL SELECT 'Año 2024 · Matemáticas', 'Promedio Area',
    avg(fa.puntaje) FROM fact_area fa JOIN fact f USING (resultado_id) JOIN area a ON a.area_id = fa.area_id
    WHERE f.anio = 2024 AND a.area = 'Matemáticas'
UNION ALL SELECT 'Año 2024 · Matemáticas', 'Promedio Distrito Area',
    sum(promedio * n) / sum(n) FROM benchmark WHERE anio = 2024 AND area = 'Matemáticas' AND dimension = 'Total' AND NOT suprimido
-- Colegio ABC en 2024 (filtro por colegio)
UNION ALL SELECT 'ABC 2024', 'Evaluados', count(*) FROM fact f JOIN colegio c USING (colegio_id) WHERE f.anio = 2024 AND c.nombre_colegio = 'ABC'
UNION ALL SELECT 'ABC 2024', 'Promedio Global', avg(f.puntaje_global) FROM fact f JOIN colegio c USING (colegio_id) WHERE f.anio = 2024 AND c.nombre_colegio = 'ABC'
UNION ALL SELECT 'ABC 2024', 'Brecha vs Distrito',
    (SELECT avg(f.puntaje_global) FROM fact f JOIN colegio c USING (colegio_id) WHERE f.anio = 2024 AND c.nombre_colegio = 'ABC')
  - (SELECT sum(promedio * n) / sum(n) FROM benchmark WHERE anio = 2024 AND area = 'Global' AND dimension = 'Total' AND NOT suprimido)
UNION ALL SELECT 'ABC 2024', 'Pct Estudiantes >= P75 Distrital',
    avg(CASE WHEN f.puntaje_global >= (SELECT quantile_cont(puntaje_global, 0.75) FROM fact WHERE anio = 2024) THEN 1.0 ELSE 0 END)
    FROM fact f JOIN colegio c USING (colegio_id) WHERE f.anio = 2024 AND c.nombre_colegio = 'ABC'
-- Perfil: Femenino, estrato 1, 2024
UNION ALL SELECT 'Femenino estrato 1 2024', 'Promedio Global',
    avg(f.puntaje_global) FROM fact f JOIN perfil p USING (perfil_id) WHERE f.anio = 2024 AND p.sexo = 'Femenino' AND p.estrato = 1
UNION ALL SELECT 'Femenino estrato 1 2024', 'Evaluados',
    count(*) FROM fact f JOIN perfil p USING (perfil_id) WHERE f.anio = 2024 AND p.sexo = 'Femenino' AND p.estrato = 1;
