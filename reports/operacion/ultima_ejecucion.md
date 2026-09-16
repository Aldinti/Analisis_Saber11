# Última ejecución del pipeline

- **run_id:** `20260916T052755Z-98ed59df`
- **Inicio (UTC):** 2026-09-16 05:27:55
- **Desde:** `validate-source`
- **Resultado:** ✅ completada
- **Duración total:** 82.3 s

| # | Etapa | Código | Segundos |
|--:|---|--:|--:|
| 1 | `validate-source` | 0 | 0.1 |
| 2 | `bronze` | 0 | 0.3 |
| 3 | `silver` | 0 | 0.7 |
| 4 | `dq-silver` | 0 | 0.4 |
| 5 | `gold` | 0 | 1.1 |
| 6 | `dq-gold` | 0 | 0.4 |
| 7 | `ml` | 0 | 70.2 |
| 8 | `shap` | 0 | 3.7 |
| 9 | `fairness` | 0 | 5.5 |

El histórico completo de ejecuciones está en `data/metadata/run_log.parquet`; los informes
de cada etapa, en `reports/`. Este archivo se sobrescribe en cada ejecución.
