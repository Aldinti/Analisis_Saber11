# Casos de prueba RLS — Dashboard operativo (F7)

> Datos y cuentas **ficticios** (dominio reservado `example.org`). Plan §15.3–§15.6.

## Cómo se valida

1. **Pre-validación automática (agente, en el modelo abierto en Power BI Desktop):** se evalúa en DAX la **misma
   expresión de filtro** del rol `Rol_Rector`, sustituyendo `USERPRINCIPALNAME()` por el UPN de cada caso.
   El MCP no puede impersonar el rol (se conecta con la API de metadatos, que un rol de solo lectura no ve).
   Evidencia: `reports/bi/rls_simulacion_dax.csv`, `reports/bi/supresion_dax_fixture.csv`.
2. **Validación con el rol real (SUP):** Power BI Desktop → *Modelado* → *Ver como* → marcar `Rol_Rector` y
   *Otro usuario* con el UPN del caso. Registrar resultado y captura en la columna "Ver como (SUP)".
3. **Despliegue (pendiente, ADR-0015):** repetir RLS-01..05 en Power BI Service con cuentas de prueba como *Viewer*.

## Roles del modelo `Saber11_Operativo`

| Rol | Tabla | Filtro DAX |
|---|---|---|
| `Rol_Rector` | `dim_colegio` | `dim_colegio[colegio_id] IN CALCULATETABLE ( VALUES ( seguridad_rectores[colegio_id] ), seguridad_rectores[email_rector] = USERPRINCIPALNAME () )` |
| `Rol_Rector` | `seguridad_rectores` | `seguridad_rectores[email_rector] = USERPRINCIPALNAME ()` |
| `Rol_Direccion` | — | Sin filtro |

`seguridad_rectores` no tiene relaciones; `agg_benchmark_distrito` no se relaciona con `dim_colegio`, por eso el
promedio distrital no cambia bajo RLS (sin `ALL()`).

## Matriz

**Resultado F7 (15-sep-2026): APROBADO.** El SUP ejecutó "Ver como" en Power BI Desktop 2.157 y todos los casos
reproducibles pasaron. RLS-09 y RLS-10 se validaron con el Gold de fixture (no hay grupos pequeños en los datos actuales).

Valores esperados de año 2024, área Global (SQL sobre Gold: ABC n=128, promedio 407,18; RST n=190, 402,31;
ABC+RST n=318, 404,27; distrito 405,36).

| Caso | Identidad (rol `Rol_Rector` salvo indicación) | Esperado | Pre-validación DAX | Ver como (SUP) |
|---|---|---|---|---|
| RLS-01 | `rector.abc@example.org` | Solo ABC; Evaluados 128; Promedio 407,18 | ✅ ABC · 128 · 407,18 | ✅ Aprobado |
| RLS-02 | `rector.rst@example.org` | Solo RST; Evaluados 190; Promedio 402,31 | ✅ RST · 190 · 402,31 | ✅ Aprobado |
| RLS-03 | `no.registrado@example.org` | Sin datos del colegio; aviso "Usuario sin colegio asignado" | ✅ 0 colegios · aviso visible | ✅ Aprobado |
| RLS-04 | `rector.multi@example.org` (ABC y RST) | Unión ABC + RST; Evaluados 318; Promedio 404,27 | ✅ "ABC, RST" · 318 · 404,27 | ✅ Aprobado |
| RLS-05 | `RECTOR.ABC@EXAMPLE.ORG` | Igual que RLS-01 | ✅ igual a RLS-01 (comparación sin distinguir mayúsculas) | ✅ Aprobado |
| RLS-06 | `rector.abc@example.org`, tarjeta Promedio Distrito | 405,36, igual para todos los casos | ✅ 405,36 en RLS-01..05; 408 filas de benchmark visibles | ✅ Aprobado |
| RLS-07 | `rector.abc@example.org`, tabla `seguridad_rectores` | Solo su fila | ✅ 1 fila (RLS-04: 2 filas) | ✅ Aprobado (tabla oculta: verificado en DAX) |
| RLS-08 | Sin rol (autor) | Los 16 colegios (comportamiento de autor, no es un control) | ✅ 16 colegios; KPIs = SQL (`reports/bi/validacion_kpis_operativo.md`) | ✅ Aprobado |
| RLS-09 | Grupo con n < `k_min` | Métrica y conteo en blanco; etiqueta "dato suprimido" | ✅ con Gold de fixture: estrato 2 (n=4) en blanco + etiqueta | No reproducible con datos actuales (n mínimo 10) |
| RLS-10 | Única categoría suprimida en una dimensión | También se suprime la siguiente más pequeña; el total no permite deducirla | ✅ con Gold de fixture: estrato 1 (n=5) también en blanco; "todos los estratos" en blanco | No reproducible con datos actuales |
| RLS-11 | "Exportar datos" / "Ver datos" | Solo datos resumidos; sin filas de estudiante | ✅ el modelo operativo no contiene filas de estudiante (solo agregados); informe con `exportDataMode: AllowSummarized` | ✅ Aprobado |

Salvaguardas adicionales verificadas en DAX: combinar dos dimensiones a la vez devuelve BLANK; con una celda
Total del colegio no suprimida, `Promedio Colegio` y `Evaluados Colegio` se muestran.
