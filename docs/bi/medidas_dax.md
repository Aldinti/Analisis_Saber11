# Catálogo de medidas DAX — Dashboard estratégico

> Generado desde `powerbi/Saber11_Estrategico.SemanticModel` con `python -m saber11.bi.catalogo_medidas`. No editar a mano: modificar la medida en el modelo y regenerar.

Validación numérica contra SQL: [`reports/bi/validacion_kpis_estrategico.md`](../../reports/bi/validacion_kpis_estrategico.md) (consultas de control en `tests/bi/kpi_control.sql`).

| Carpeta | Medida | Formato | Descripción |
|---|---|---|---|
| 0. Etiquetas | `Etiqueta Datos Ficticios` | `` | Rótulo obligatorio en todas las páginas (plan F6). |
| 1. Resumen | `Evaluados` | `#,0` | Número de evaluaciones en el contexto de filtros. |
| 1. Resumen | `Pct Estudiantes >= P75 Distrital` | `0.0%` | Proporción de estudiantes de la selección con puntaje global mayor o igual al P75 distrital. |
| 1. Resumen | `Percentil 75 Distrital` | `#,0.0` | P75 del distrito para los años seleccionados, ignorando filtros de colegio, ubicación y perfil. |
| 1. Resumen | `Promedio Global` | `#,0.0` | Promedio del puntaje global (0-500). |
| 2. Áreas | `Promedio Area` | `#,0.0` | Promedio del puntaje por área (0-100). |
| 3. Tendencias | `Promedio Global AA` | `#,0.0` | Promedio global del año anterior al más reciente seleccionado. |
| 3. Tendencias | `Promedio Global Anio Actual` | `#,0.0` | Promedio global del año más reciente dentro de la selección. |
| 3. Tendencias | `Variacion Interanual` | `+0.0%;-0.0%;0.0%` | Variación relativa del promedio global frente al año anterior. |
| 4. Benchmarking | `Aviso Benchmark Sector` | `` | Texto de advertencia cuando el diferencial de sector no es calculable. |
| 4. Benchmarking | `Aviso Benchmark Zona` | `` | Texto de advertencia cuando el diferencial de zona no es calculable. |
| 4. Benchmarking | `Brecha Area vs Distrito` | `+#,0.0;-#,0.0;0.0` |  |
| 4. Benchmarking | `Brecha vs Distrito` | `+#,0.0;-#,0.0;0.0` |  |
| 4. Benchmarking | `Diferencial Sector` | `+#,0.0;-#,0.0;0.0` | Pública menos Privada. BLANK si falta alguno de los dos sectores en la selección. |
| 4. Benchmarking | `Diferencial Zona` | `+#,0.0;-#,0.0;0.0` | Urbana menos Rural. BLANK si falta alguna de las dos zonas en la selección. |
| 4. Benchmarking | `Promedio Distrito` | `#,0.0` | Promedio global distrital ponderado por n desde agg_benchmark_distrito (celdas no suprimidas) para los años seleccionados. No usa ALL(): válido también bajo RLS. |
| 4. Benchmarking | `Promedio Distrito Area` | `#,0.0` | Promedio distrital por área (áreas seleccionadas en dim_area), ponderado por n. |
| 4. Benchmarking | `Promedio Privada` | `#,0.0` |  |
| 4. Benchmarking | `Promedio Publica` | `#,0.0` |  |
| 4. Benchmarking | `Promedio Rural` | `#,0.0` |  |
| 4. Benchmarking | `Promedio Urbana` | `#,0.0` |  |
| 5. Distribución | `Desviacion Estandar Global` | `#,0.0` |  |
| 5. Distribución | `Mediana Global` | `#,0.0` |  |
| 5. Distribución | `Percentil 25 Global` | `#,0.0` |  |
| 5. Distribución | `Percentil 75 Colegio` | `#,0.0` | Percentil 75 del puntaje global en el contexto actual (p. ej. por colegio). |

## 0. Etiquetas

### Etiqueta Datos Ficticios

Rótulo obligatorio en todas las páginas (plan F6).

```dax
Etiqueta Datos Ficticios =
"Datos ficticios · No representan resultados reales del ICFES"
```

## 1. Resumen

### Evaluados

Número de evaluaciones en el contexto de filtros.

```dax
Evaluados =
COUNTROWS ( fact_resultado )
```

### Pct Estudiantes >= P75 Distrital

Proporción de estudiantes de la selección con puntaje global mayor o igual al P75 distrital.

```dax
Pct Estudiantes >= P75 Distrital =
VAR Umbral = [Percentil 75 Distrital]
RETURN
    DIVIDE ( CALCULATE ( COUNTROWS ( fact_resultado ), fact_resultado[puntaje_global] >= Umbral ), [Evaluados] )
```

### Percentil 75 Distrital

P75 del distrito para los años seleccionados, ignorando filtros de colegio, ubicación y perfil.

```dax
Percentil 75 Distrital =
CALCULATE (
    PERCENTILE.INC ( fact_resultado[puntaje_global], 0.75 ),
    REMOVEFILTERS ( dim_colegio ),
    REMOVEFILTERS ( dim_ubicacion ),
    REMOVEFILTERS ( dim_perfil_estudiante )
)
```

### Promedio Global

Promedio del puntaje global (0-500).

```dax
Promedio Global =
AVERAGE ( fact_resultado[puntaje_global] )
```

## 2. Áreas

### Promedio Area

Promedio del puntaje por área (0-100).

```dax
Promedio Area =
AVERAGE ( fact_resultado_area[puntaje] )
```

## 3. Tendencias

### Promedio Global AA

Promedio global del año anterior al más reciente seleccionado.

```dax
Promedio Global AA =
VAR AnioActual = MAX ( dim_tiempo[anio] )
RETURN
    CALCULATE ( [Promedio Global], REMOVEFILTERS ( dim_tiempo ), dim_tiempo[anio] = AnioActual - 1 )
```

### Promedio Global Anio Actual

Promedio global del año más reciente dentro de la selección.

```dax
Promedio Global Anio Actual =
VAR AnioActual = MAX ( dim_tiempo[anio] )
RETURN
    CALCULATE ( [Promedio Global], dim_tiempo[anio] = AnioActual )
```

### Variacion Interanual

Variación relativa del promedio global frente al año anterior.

```dax
Variacion Interanual =
DIVIDE ( [Promedio Global Anio Actual] - [Promedio Global AA], [Promedio Global AA] )
```

## 4. Benchmarking

### Aviso Benchmark Sector

Texto de advertencia cuando el diferencial de sector no es calculable.

```dax
Aviso Benchmark Sector =
IF ( ISBLANK ( [Diferencial Sector] ), "Sin datos de colegios públicos y privados para la selección", "" )
```

### Aviso Benchmark Zona

Texto de advertencia cuando el diferencial de zona no es calculable.

```dax
Aviso Benchmark Zona =
IF ( ISBLANK ( [Diferencial Zona] ), "Sin datos de zona urbana y rural para la selección", "" )
```

### Brecha Area vs Distrito

```dax
Brecha Area vs Distrito =
[Promedio Area] - [Promedio Distrito Area]
```

### Brecha vs Distrito

```dax
Brecha vs Distrito =
[Promedio Global] - [Promedio Distrito]
```

### Diferencial Sector

Pública menos Privada. BLANK si falta alguno de los dos sectores en la selección.

```dax
Diferencial Sector =
VAR Pub = [Promedio Publica]
VAR Priv = [Promedio Privada]
RETURN
    IF ( ISBLANK ( Pub ) || ISBLANK ( Priv ), BLANK (), Pub - Priv )
```

### Diferencial Zona

Urbana menos Rural. BLANK si falta alguna de las dos zonas en la selección.

```dax
Diferencial Zona =
VAR Urb = [Promedio Urbana]
VAR Rur = [Promedio Rural]
RETURN
    IF ( ISBLANK ( Urb ) || ISBLANK ( Rur ), BLANK (), Urb - Rur )
```

### Promedio Distrito

Promedio global distrital ponderado por n desde agg_benchmark_distrito (celdas no suprimidas) para los años seleccionados. No usa ALL(): válido también bajo RLS.

```dax
Promedio Distrito =
VAR Filas =
    FILTER (
        agg_benchmark_distrito,
        agg_benchmark_distrito[area] = "Global"
            && agg_benchmark_distrito[dimension] = "Total"
            && agg_benchmark_distrito[anio] IN VALUES ( dim_tiempo[anio] )
            && NOT agg_benchmark_distrito[suprimido]
    )
RETURN
    DIVIDE (
        SUMX ( Filas, agg_benchmark_distrito[promedio] * agg_benchmark_distrito[n] ),
        SUMX ( Filas, agg_benchmark_distrito[n] )
    )
```

### Promedio Distrito Area

Promedio distrital por área (áreas seleccionadas en dim_area), ponderado por n.

```dax
Promedio Distrito Area =
VAR Filas =
    FILTER (
        agg_benchmark_distrito,
        agg_benchmark_distrito[area] IN VALUES ( dim_area[area] )
            && agg_benchmark_distrito[dimension] = "Total"
            && agg_benchmark_distrito[anio] IN VALUES ( dim_tiempo[anio] )
            && NOT agg_benchmark_distrito[suprimido]
    )
RETURN
    DIVIDE (
        SUMX ( Filas, agg_benchmark_distrito[promedio] * agg_benchmark_distrito[n] ),
        SUMX ( Filas, agg_benchmark_distrito[n] )
    )
```

### Promedio Privada

```dax
Promedio Privada =
CALCULATE ( [Promedio Global], dim_colegio[naturaleza_colegio] = "Privada" )
```

### Promedio Publica

```dax
Promedio Publica =
CALCULATE ( [Promedio Global], dim_colegio[naturaleza_colegio] = "Pública" )
```

### Promedio Rural

```dax
Promedio Rural =
CALCULATE ( [Promedio Global], dim_ubicacion[zona] = "Rural" )
```

### Promedio Urbana

```dax
Promedio Urbana =
CALCULATE ( [Promedio Global], dim_ubicacion[zona] = "Urbana" )
```

## 5. Distribución

### Desviacion Estandar Global

```dax
Desviacion Estandar Global =
STDEV.S ( fact_resultado[puntaje_global] )
```

### Mediana Global

```dax
Mediana Global =
MEDIAN ( fact_resultado[puntaje_global] )
```

### Percentil 25 Global

```dax
Percentil 25 Global =
PERCENTILE.INC ( fact_resultado[puntaje_global], 0.25 )
```

### Percentil 75 Colegio

Percentil 75 del puntaje global en el contexto actual (p. ej. por colegio).

```dax
Percentil 75 Colegio =
PERCENTILE.INC ( fact_resultado[puntaje_global], 0.75 )
```
