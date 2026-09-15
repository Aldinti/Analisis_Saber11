# ADR-0018: Modelo semántico operativo separado y solo con agregados

## Estado
Aceptado (F7)

## Contexto
El plan (§8 F7) indicaba que el dashboard operativo dependía del modelo semántico del estratégico (F6), que contiene
filas por evaluación (`fact_resultado`, `fact_resultado_area`). El usuario confirmó el requisito de agregar o
suprimir grupos pequeños en el dashboard operativo (§15.6). Con RLS, un rector vería sus propias filas de estudiante;
en Power BI Service, un Viewer con permiso *Build* o "Analizar en Excel" puede consultar cualquier tabla del modelo, no
solo las visuales, de modo que "ocultar" `fact_resultado` no impide llegar a microdatos con cuasi-identificadores.

## Decisión
Crear `powerbi/Saber11_Operativo.pbip` con un modelo propio que solo importa:

| Tabla | Rol |
|---|---|
| `dim_colegio` | Tabla filtrada por `Rol_Rector` |
| `agg_operativo_colegio` | Agregados por colegio × año × área × dimensión con supresión aplicada en Gold |
| `agg_benchmark_distrito` | Comparativo distrital; sin relación con `dim_colegio` (RLS no lo filtra) |
| `seguridad_rectores` | Correo → colegio; oculta y sin relaciones |
| `dim_anio`, `dim_area_operativa` | Tablas calculadas para segmentar ambos agregados |

RLS dinámico (plan §15.3): `Rol_Rector` filtra `dim_colegio` con `IN CALCULATETABLE(VALUES(seguridad_rectores[colegio_id]), seguridad_rectores[email_rector] = USERPRINCIPALNAME())` y restringe `seguridad_rectores` a la fila del usuario; `Rol_Direccion` sin filtro.
Las visuales solo usan medidas con salvaguardas (una dimensión y un área, n ≥ `K Min`, sin celdas suprimidas);
las columnas numéricas crudas de los agregados están ocultas y las pruebas verifican que el informe no las use.

## Consecuencias
- **Positivas:** ninguna identidad puede obtener filas de estudiante desde este modelo; la supresión de Gold es el
  único origen de datos visibles; los KPIs se validan contra SQL calculado desde los hechos (13/13) y la matriz
  RLS-01..11 se aprobó (pre-validación DAX + "Ver como" del SUP).
- **Negativas / mitigaciones:** dos modelos que mantener (parámetro `RutaGold` en ambos); percentiles solo por celda
  (no se combinan años); no hay benchmark distrital para `grupo`. `K Min` está duplicado como medida y se sincroniza
  con `settings.yaml` mediante prueba.
