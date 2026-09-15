# Catálogo de medidas DAX — Dashboard operativo

> Generado desde `powerbi/Saber11_Operativo.SemanticModel` con `python -m saber11.bi.catalogo_medidas`. No editar a mano: modificar la medida en el modelo y regenerar.

Validación numérica contra SQL: [`reports/bi/validacion_kpis_operativo.md`](../../reports/bi/validacion_kpis_operativo.md); casos RLS: [`tests/rls/casos_rls.md`](../../tests/rls/casos_rls.md).

| Carpeta | Medida | Formato | Descripción |
|---|---|---|---|
| 0. Parámetros | `Area Mostrada` | `` | Área aplicada a las medidas: la seleccionada si es única; si no, Global. |
| 0. Parámetros | `Etiqueta Datos Ficticios` | `` | Rótulo obligatorio en todas las páginas. |
| 0. Parámetros | `K Min` | `0` | Umbral mínimo de estudiantes por celda mostrada. Debe coincidir con privacy.k_min de config/settings.yaml (prueba de sincronía). |
| 1. Colegio | `Evaluados Colegio` | `#,0` | Estudiantes evaluados del colegio (dimensión Total) en los años seleccionados. |
| 1. Colegio | `Promedio Colegio` | `#,0.0` | Promedio total del colegio (dimensión Total) en el área mostrada y los años seleccionados. |
| 2. Subgrupos | `Etiqueta Supresion` | `` | Aviso cuando el grupo en contexto está suprimido. |
| 2. Subgrupos | `Evaluados Visible` | `#,0` | Estudiantes del grupo; BLANK en grupos suprimidos (no se publican conteos de celdas suprimidas). |
| 2. Subgrupos | `Instruccion Subgrupos` | `` | Indica que las visuales de subgrupos requieren elegir una sola dimensión. |
| 2. Subgrupos | `Promedio Operativo` | `#,0.0` | Promedio del grupo en contexto (usar con una dimensión: sexo, estrato o grupo). BLANK si el grupo tiene menos de K Min estudiantes o hay celdas suprimidas. |
| 3. Distribución | `Mediana Colegio` | `#,0.0` |  |
| 3. Distribución | `Percentil 10 Colegio` | `#,0.0` | P10 del colegio; requiere un solo año (celda Total única). |
| 3. Distribución | `Percentil 25 Colegio` | `#,0.0` |  |
| 3. Distribución | `Percentil 75 Colegio` | `#,0.0` |  |
| 3. Distribución | `Percentil 90 Colegio` | `#,0.0` |  |
| 4. Distrito | `Brecha vs Distrito` | `+#,0.0;-#,0.0;0.0` |  |
| 4. Distrito | `Promedio Distrito` | `#,0.0` | Promedio distrital (Total, celdas no suprimidas, ponderado por n) para los años seleccionados y el área mostrada. Desde agg_benchmark_distrito: RLS no lo filtra y no usa ALL(). |
| 4. Distrito | `Promedio Distrito Categoria` | `#,0.0` | Promedio distrital de la misma dimensión y categoría del contexto (p. ej. estrato 1). BLANK para 'grupo', que no tiene equivalente distrital. |
| 5. Seguridad | `Aviso Sin Colegio` | `` | Mensaje para usuarios sin colegio asignado (RLS-03). |
| 5. Seguridad | `Colegios Visibles` | `` |  |
| 5. Seguridad | `Usuario Actual` | `` | UPN con el que se evalúa el informe (para verificar RLS). |
| 9. Internas | `Celdas Suprimidas` | `0` |  |
| 9. Internas | `Evaluados Grupo` | `#,0` | Suma de n de las celdas en contexto (uso interno; no mostrar en visuales). |
| 9. Internas | `Promedio Celda` | `#,0.0` | Promedio ponderado por n con salvaguardas de supresión (una dimensión, un área, n >= K Min, sin celdas suprimidas). |

## 0. Parámetros

### Area Mostrada

Área aplicada a las medidas: la seleccionada si es única; si no, Global.

```dax
Area Mostrada =
IF ( HASONEVALUE ( dim_area_operativa[area] ), VALUES ( dim_area_operativa[area] ), "Global" )
```

### Etiqueta Datos Ficticios

Rótulo obligatorio en todas las páginas.

```dax
Etiqueta Datos Ficticios =
"Datos ficticios · No representan resultados reales del ICFES"
```

### K Min

Umbral mínimo de estudiantes por celda mostrada. Debe coincidir con privacy.k_min de config/settings.yaml (prueba de sincronía).

```dax
K Min =
5
```

## 1. Colegio

### Evaluados Colegio

Estudiantes evaluados del colegio (dimensión Total) en los años seleccionados.

```dax
Evaluados Colegio =
CALCULATE ( [Evaluados Visible], agg_operativo_colegio[dimension] = "Total", REMOVEFILTERS ( agg_operativo_colegio[categoria] ) )
```

### Promedio Colegio

Promedio total del colegio (dimensión Total) en el área mostrada y los años seleccionados.

```dax
Promedio Colegio =
CALCULATE ( [Promedio Operativo], agg_operativo_colegio[dimension] = "Total", REMOVEFILTERS ( agg_operativo_colegio[categoria] ) )
```

## 2. Subgrupos

### Etiqueta Supresion

Aviso cuando el grupo en contexto está suprimido.

```dax
Etiqueta Supresion =
VAR AreaSel = [Area Mostrada]
VAR N = CALCULATE ( [Evaluados Grupo], dim_area_operativa[area] = AreaSel )
VAR Suprimidas = CALCULATE ( [Celdas Suprimidas], dim_area_operativa[area] = AreaSel )
RETURN
    IF ( N > 0 && ( N < [K Min] || Suprimidas > 0 ), "Grupo menor a " & [K Min] & " estudiantes: dato suprimido", "" )
```

### Evaluados Visible

Estudiantes del grupo; BLANK en grupos suprimidos (no se publican conteos de celdas suprimidas).

```dax
Evaluados Visible =
VAR AreaSel = [Area Mostrada]
RETURN
    CALCULATE (
        IF ( [Evaluados Grupo] < [K Min] || [Celdas Suprimidas] > 0, BLANK (), [Evaluados Grupo] ),
        dim_area_operativa[area] = AreaSel
    )
```

### Instruccion Subgrupos

Indica que las visuales de subgrupos requieren elegir una sola dimensión.

```dax
Instruccion Subgrupos =
IF ( NOT HASONEVALUE ( agg_operativo_colegio[dimension] ), "Seleccione una dimensión (sexo, estrato o grupo) para ver los subgrupos", "" )
```

### Promedio Operativo

Promedio del grupo en contexto (usar con una dimensión: sexo, estrato o grupo). BLANK si el grupo tiene menos de K Min estudiantes o hay celdas suprimidas.

```dax
Promedio Operativo =
VAR AreaSel = [Area Mostrada]
RETURN
    CALCULATE ( [Promedio Celda], dim_area_operativa[area] = AreaSel )
```

## 3. Distribución

### Mediana Colegio

```dax
Mediana Colegio =
VAR AreaSel = [Area Mostrada]
RETURN
    CALCULATE (
        IF ( COUNTROWS ( agg_operativo_colegio ) = 1, MAX ( agg_operativo_colegio[p50] ) ),
        dim_area_operativa[area] = AreaSel,
        agg_operativo_colegio[dimension] = "Total",
        REMOVEFILTERS ( agg_operativo_colegio[categoria] )
    )
```

### Percentil 10 Colegio

P10 del colegio; requiere un solo año (celda Total única).

```dax
Percentil 10 Colegio =
VAR AreaSel = [Area Mostrada]
RETURN
    CALCULATE (
        IF ( COUNTROWS ( agg_operativo_colegio ) = 1, MAX ( agg_operativo_colegio[p10] ) ),
        dim_area_operativa[area] = AreaSel,
        agg_operativo_colegio[dimension] = "Total",
        REMOVEFILTERS ( agg_operativo_colegio[categoria] )
    )
```

### Percentil 25 Colegio

```dax
Percentil 25 Colegio =
VAR AreaSel = [Area Mostrada]
RETURN
    CALCULATE (
        IF ( COUNTROWS ( agg_operativo_colegio ) = 1, MAX ( agg_operativo_colegio[p25] ) ),
        dim_area_operativa[area] = AreaSel,
        agg_operativo_colegio[dimension] = "Total",
        REMOVEFILTERS ( agg_operativo_colegio[categoria] )
    )
```

### Percentil 75 Colegio

```dax
Percentil 75 Colegio =
VAR AreaSel = [Area Mostrada]
RETURN
    CALCULATE (
        IF ( COUNTROWS ( agg_operativo_colegio ) = 1, MAX ( agg_operativo_colegio[p75] ) ),
        dim_area_operativa[area] = AreaSel,
        agg_operativo_colegio[dimension] = "Total",
        REMOVEFILTERS ( agg_operativo_colegio[categoria] )
    )
```

### Percentil 90 Colegio

```dax
Percentil 90 Colegio =
VAR AreaSel = [Area Mostrada]
RETURN
    CALCULATE (
        IF ( COUNTROWS ( agg_operativo_colegio ) = 1, MAX ( agg_operativo_colegio[p90] ) ),
        dim_area_operativa[area] = AreaSel,
        agg_operativo_colegio[dimension] = "Total",
        REMOVEFILTERS ( agg_operativo_colegio[categoria] )
    )
```

## 4. Distrito

### Brecha vs Distrito

```dax
Brecha vs Distrito =
IF ( ISBLANK ( [Promedio Colegio] ) || ISBLANK ( [Promedio Distrito] ), BLANK (), [Promedio Colegio] - [Promedio Distrito] )
```

### Promedio Distrito

Promedio distrital (Total, celdas no suprimidas, ponderado por n) para los años seleccionados y el área mostrada. Desde agg_benchmark_distrito: RLS no lo filtra y no usa ALL().

```dax
Promedio Distrito =
VAR AreaSel = [Area Mostrada]
VAR Filas =
    CALCULATETABLE (
        FILTER ( agg_benchmark_distrito, agg_benchmark_distrito[dimension] = "Total" && NOT agg_benchmark_distrito[suprimido] ),
        dim_area_operativa[area] = AreaSel
    )
RETURN
    DIVIDE ( SUMX ( Filas, agg_benchmark_distrito[promedio] * agg_benchmark_distrito[n] ), SUMX ( Filas, agg_benchmark_distrito[n] ) )
```

### Promedio Distrito Categoria

Promedio distrital de la misma dimensión y categoría del contexto (p. ej. estrato 1). BLANK para 'grupo', que no tiene equivalente distrital.

```dax
Promedio Distrito Categoria =
VAR AreaSel = [Area Mostrada]
VAR Dimensiones = VALUES ( agg_operativo_colegio[dimension] )
VAR Categorias = VALUES ( agg_operativo_colegio[categoria] )
VAR Filas =
    CALCULATETABLE (
        FILTER (
            agg_benchmark_distrito,
            agg_benchmark_distrito[dimension] IN Dimensiones
                && agg_benchmark_distrito[categoria] IN Categorias
                && NOT agg_benchmark_distrito[suprimido]
        ),
        dim_area_operativa[area] = AreaSel
    )
RETURN
    IF (
        HASONEVALUE ( agg_operativo_colegio[dimension] ),
        DIVIDE ( SUMX ( Filas, agg_benchmark_distrito[promedio] * agg_benchmark_distrito[n] ), SUMX ( Filas, agg_benchmark_distrito[n] ) )
    )
```

## 5. Seguridad

### Aviso Sin Colegio

Mensaje para usuarios sin colegio asignado (RLS-03).

```dax
Aviso Sin Colegio =
IF ( COUNTROWS ( dim_colegio ) = 0, "Usuario sin colegio asignado: " & USERPRINCIPALNAME (), "" )
```

### Colegios Visibles

```dax
Colegios Visibles =
CONCATENATEX ( VALUES ( dim_colegio[nombre_colegio] ), dim_colegio[nombre_colegio], ", ", dim_colegio[nombre_colegio], ASC )
```

### Usuario Actual

UPN con el que se evalúa el informe (para verificar RLS).

```dax
Usuario Actual =
USERPRINCIPALNAME ()
```

## 9. Internas

### Celdas Suprimidas

```dax
Celdas Suprimidas =
CALCULATE ( COUNTROWS ( agg_operativo_colegio ), agg_operativo_colegio[suprimido] = TRUE () )
```

### Evaluados Grupo

Suma de n de las celdas en contexto (uso interno; no mostrar en visuales).

```dax
Evaluados Grupo =
SUM ( agg_operativo_colegio[n] )
```

### Promedio Celda

Promedio ponderado por n con salvaguardas de supresión (una dimensión, un área, n >= K Min, sin celdas suprimidas).

```dax
Promedio Celda =
VAR N = [Evaluados Grupo]
RETURN
    IF (
        NOT HASONEVALUE ( agg_operativo_colegio[dimension] )
            || NOT HASONEVALUE ( agg_operativo_colegio[area] )
            || N < [K Min]
            || [Celdas Suprimidas] > 0,
        BLANK (),
        DIVIDE ( SUMX ( agg_operativo_colegio, agg_operativo_colegio[promedio] * agg_operativo_colegio[n] ), N )
    )
```
