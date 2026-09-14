# ADR-0016: Motor de calidad de datos propio y umbrales del quality gate

## Estado
Aceptado (F5b)

## Contexto
El plan exige un catálogo formal de reglas, resultados persistidos, un informe por ejecución y un gate que impida construir Gold si falla una regla bloqueante (§8 F5, §20). El riesgo identificado en F5 es fijar umbrales arbitrarios; deben apoyarse en el perfilamiento y quedar registrados.

## Decisión
1. **Motor propio ligero** (`src/saber11/quality/engine.py`) sobre DuckDB, en lugar de Great Expectations u otra librería: las reglas ya son SQL escalar en `config/dq_rules.yaml`, y el motor solo resuelve parámetros, ejecuta, compara con el umbral y persiste. Tres reglas estructurales (DQ-INT-001, DQ-INT-002, DQ-PRI-001) se evalúan en Python.
2. **Gates por capa:** `silver` (reglas de Bronze y Silver, antes de Gold) y `gold` (reglas de Gold, antes de BI/ML). DQ-PRI-001 se evalúa en ambos.
3. **Criterio:** el gate aprueba solo si todas las reglas bloqueantes están en `PASA`. Un `ERROR` de evaluación (tabla o columna inexistente, SQL inválida, valor nulo) en una regla bloqueante **rechaza**: no se aprueba lo que no se pudo medir.
4. **Trazabilidad:** cada regla evaluada se agrega a `data/metadata/dq_results.parquet`; cada ejecución genera `reports/quality/dq_<run_id>.md` y un registro `dq_<capa>` en `run_log` con `run_id_evaluado` (la ejecución silver/gold que produjo los datos). F4 debe exigir `gate_aprobado(run_log, "silver", <run_id del Silver que consume>)`; si Silver se regenera, el gate debe volver a ejecutarse.
5. **Código de salida** de `run --stage dq`: `0` aprobado, `4` rechazado, `1` error técnico (capa no disponible).

## Umbrales y su fundamento

| Regla | Umbral | Fundamento |
|---|---|---|
| Bloqueantes de integridad, completitud, unicidad, validez, consistencia de categorías, integridad referencial y privacidad | 0 fallos | Son invariantes del modelo o de privacidad; el perfilamiento v1/v2 no mostró nulos, duplicados ni valores fuera de escala, así que cualquier fallo indica un defecto real |
| DQ-COM-002 (nulos en sexo/estrato) | ≤ 5 % (advertencia) | Variables usadas en sesgos y ML; un 5 % aún permite análisis por subgrupo sin imputar. Perfilamiento: 0 % |
| DQ-EXA-001 (Global vs fórmula de áreas) | ≤ 1 % (advertencia) | La fórmula se cumple en 100 % de filas (H4); tolerancia mínima ante redondeos de la fuente |
| DQ-CON-001 (colegio con varias naturalezas/modelos por año) | 0 (advertencia) | Puede ser un cambio real de un colegio; se informa sin bloquear |
| DQ-VOL-001 (variación de filas Silver) | ≤ 30 % (advertencia) | Las cargas anuales del original varían entre 182 y 258 filas (≈ 30 %); una variación mayor merece revisión pero puede ser legítima |
| DQ-PRI-002/003 | 0 con `k_min = 5` y `min_schools_comparative = 3` | Requisito confirmado por el usuario (plan §15.6); parámetros en `config/settings.yaml` |

## Consecuencias
- **Positivas:** sin dependencias nuevas; reglas legibles y versionadas; cada decisión del gate es reproducible y auditable; el mismo motor sirve para Gold.
- **Negativas / mitigaciones:** no incluye perfiles automáticos ni documentación HTML de Great Expectations (mitigado con el informe Markdown y los perfiles de F1/F1c); añadir una regla sin SQL exige un evaluador Python (el motor marca `ERROR` si falta, y una prueba verifica que todo el catálogo pertenece a una capa).
