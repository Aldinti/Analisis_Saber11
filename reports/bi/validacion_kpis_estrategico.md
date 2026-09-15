# Validación de KPIs del dashboard estratégico (F6)

Criterio (plan §8 F6): cada KPI DAX coincide con su consulta SQL de control con tolerancia 0.01.

**Resultado: APROBADO** — 21/21 KPIs dentro de tolerancia.

- SQL de control: `tests/bi/kpi_control.sql` sobre `data/gold` (DuckDB).
- DAX: medidas de `_Medidas` evaluadas en el modelo abierto en Power BI Desktop (motor Analysis Services) con los mismos filtros; resultado bruto en `reports/bi/kpi_dax_resultados.csv`.
- Datos ficticios.

| Escenario | KPI | SQL (esperado) | DAX (modelo) | Diferencia | Cumple |
|---|---|---|---|---|---|
| Todos | Evaluados | 14666.000000 | 14666.000000 | 0.00e+00 | ✅ |
| Todos | Promedio Global | 399.825106 | 399.825106 | 0.00e+00 | ✅ |
| Todos | Percentil 75 Colegio | 433.000000 | 433.000000 | 0.00e+00 | ✅ |
| Todos | Mediana Global | 401.000000 | 401.000000 | 0.00e+00 | ✅ |
| Año 2024 | Evaluados | 3509.000000 | 3509.000000 | 0.00e+00 | ✅ |
| Año 2024 | Promedio Global | 405.358507 | 405.358507 | 0.00e+00 | ✅ |
| Año 2024 | Promedio Global AA | 400.656447 | 400.656447 | 0.00e+00 | ✅ |
| Año 2024 | Variacion Interanual | 0.011736 | 0.011736 | 4.68e-17 | ✅ |
| Año 2024 | Percentil 75 Distrital | 440.000000 | 440.000000 | 0.00e+00 | ✅ |
| Año 2024 | Pct Estudiantes >= P75 Distrital | 0.251924 | 0.251924 | 0.00e+00 | ✅ |
| Año 2024 | Diferencial Sector | -21.767270 | -21.767270 | 0.00e+00 | ✅ |
| Año 2024 | Diferencial Zona | 19.972350 | 19.972350 | 0.00e+00 | ✅ |
| Año 2024 | Promedio Distrito | 405.358507 | 405.358507 | 0.00e+00 | ✅ |
| Año 2024 · Matemáticas | Promedio Area | 80.760046 | 80.760046 | 0.00e+00 | ✅ |
| Año 2024 · Matemáticas | Promedio Distrito Area | 80.760046 | 80.760046 | 0.00e+00 | ✅ |
| ABC 2024 | Evaluados | 128.000000 | 128.000000 | 0.00e+00 | ✅ |
| ABC 2024 | Promedio Global | 407.179688 | 407.179688 | 0.00e+00 | ✅ |
| ABC 2024 | Brecha vs Distrito | 1.821181 | 1.821181 | 0.00e+00 | ✅ |
| ABC 2024 | Pct Estudiantes >= P75 Distrital | 0.218750 | 0.218750 | 0.00e+00 | ✅ |
| Femenino estrato 1 2024 | Promedio Global | 382.666667 | 382.666667 | 0.00e+00 | ✅ |
| Femenino estrato 1 2024 | Evaluados | 390.000000 | 390.000000 | 0.00e+00 | ✅ |
