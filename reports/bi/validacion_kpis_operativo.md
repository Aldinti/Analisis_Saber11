# Validación de KPIs del dashboard operativo (F7)

Criterio: cada medida DAX del modelo operativo coincide con su consulta SQL de control (tolerancia 0.01).

**Resultado: APROBADO** — 13/13 KPIs dentro de tolerancia.

- SQL de control: `tests/bi/kpi_control_operativo.sql`, calculado desde `fact_resultado` y `fact_resultado_area` (no desde `agg_operativo_colegio`): contrasta de forma independiente el camino agregados + medidas con supresión.
- DAX: medidas de `_Medidas` en el modelo operativo abierto en Power BI Desktop, sin rol (autor); resultado bruto en `reports/bi/kpi_dax_resultados_operativo.csv`.
- Datos ficticios. Con los datos actuales ninguna celda está suprimida (n mínimo 10); la supresión se prueba en `tests/integration/test_gold.py` y en los casos RLS-09/10.

| Escenario | KPI | SQL (esperado) | DAX (modelo) | Diferencia | Cumple |
|---|---|---|---|---|---|
| ABC 2024 · Global | Evaluados Colegio | 128.000000 | 128.000000 | 0.00e+00 | ✅ |
| ABC 2024 · Global | Promedio Colegio | 407.179688 | 407.179688 | 0.00e+00 | ✅ |
| ABC 2024 · Global | Mediana Colegio | 404.500000 | 404.500000 | 0.00e+00 | ✅ |
| ABC 2024 · Global | Percentil 90 Colegio | 469.500000 | 469.500000 | 0.00e+00 | ✅ |
| ABC 2024 · Global | Promedio Distrito | 405.358507 | 405.358507 | 0.00e+00 | ✅ |
| ABC 2024 · Global | Brecha vs Distrito | 1.821181 | 1.821181 | 0.00e+00 | ✅ |
| ABC 2021-2024 · Global | Promedio Colegio | 398.001106 | 398.001106 | 0.00e+00 | ✅ |
| ABC 2021-2024 · Global | Evaluados Colegio | 904.000000 | 904.000000 | 0.00e+00 | ✅ |
| ABC 2024 · Matemáticas · estrato 1 | Promedio Operativo | 80.285714 | 80.285714 | 0.00e+00 | ✅ |
| ABC 2024 · Matemáticas · estrato 1 | Evaluados Visible | 28.000000 | 28.000000 | 0.00e+00 | ✅ |
| ABC 2024 · Matemáticas · estrato 1 | Promedio Distrito Categoria | 76.273077 | 76.273077 | 0.00e+00 | ✅ |
| ABC 2024 · Global · sexo Femenino | Promedio Operativo | 406.093750 | 406.093750 | 0.00e+00 | ✅ |
| ABC 2024 · Global · grupo 11-2 | Promedio Operativo | 407.490196 | 407.490196 | 0.00e+00 | ✅ |
