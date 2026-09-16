# Manual de operación

Cómo se ejecuta y se mantiene el pipeline Saber 11 en el día a día. Para la arquitectura y
las decisiones de diseño, ver `PLAN_MAESTRO.md` y `adr/`.

---

## 1. La cadena

```text
validate-source → bronze → silver → dq-silver → gold → dq-gold → ml → shap → fairness
```

Cada etapa lee la configuración de `config/settings.yaml`, escribe una fila en
`data/metadata/run_log.parquet` (inicio, fin, conteos, `git_sha`, parámetros) y termina con
un código de salida. **La cadena se detiene en la primera etapa que falla**: las siguientes
no se ejecutan y el código de la que falló es el del proceso.

Los dos *quality gates* son los puntos de control: Gold no se construye si el Silver vigente
no aprobó el suyo, y ML no entrena si el Gold vigente no aprobó el suyo.

---

## 2. Requisitos

- Windows con Python 3.12 (o `uv`), y Power BI Desktop si se van a abrir los tableros.
- `data/landing/ResultadosICFES.csv` en el formato del contrato (`config/source_contract.yaml`:
  23 columnas, separador `;`, codificación cp1252).
- `SABER11_HMAC_KEY` en `.env`, con al menos 32 caracteres. **Respáldela fuera del
  repositorio**: sin ella no se pueden volver a enlazar seudónimos de cargas anteriores.

---

## 3. Primera ejecución

```powershell
.\tasks.ps1 setup              # crea .venv, instala requirements.txt y genera .env con clave HMAC
Copy-Item <origen>\ResultadosICFES.csv data\landing\
.\tasks.ps1 run                # cadena completa
.\tasks.ps1 test               # verificación
```

`setup` no pisa un `.env` existente. Si prefiere hacerlo a mano, el equivalente está en el
`README.md`.

---

## 4. Comandos

| Qué necesita | Comando |
|---|---|
| Ejecutar todo | `.\tasks.ps1 run` |
| Retomar desde una etapa | `.\tasks.ps1 run -From gold` |
| Ejecutar una sola etapa | `.\tasks.ps1 run -Stage ml` |
| Quality gate de una capa | `.\tasks.ps1 run -Stage dq -Layer gold` |
| Solo validar el CSV de entrada | `python -m saber11.pipeline validate-source` |
| Pruebas con cobertura | `.\tasks.ps1 test` |
| Estilo de código | `.\tasks.ps1 lint` |
| Limpiar temporales de DuckDB | `.\tasks.ps1 clean-tmp` |
| Otra configuración | `python -m saber11.pipeline --config ruta\settings.yaml run` |

`tasks.ps1` fija `PYTHONPATH=src` y usa el intérprete de `.venv`; los comandos de
`python -m saber11.pipeline` requieren hacerlo a mano (`$env:PYTHONPATH = "src"`).

---

## 5. Qué hace cada etapa

| Etapa | Entrada | Salida | Notas |
|---|---|---|---|
| `validate-source` | CSV de landing | `reports/quality/source_check_<run_id>.json` | No modifica datos; solo verifica el contrato |
| `bronze` | CSV de landing | `data/bronze/raw/<sha256>.csv` (solo lectura) y Parquet VARCHAR | **Idempotente**: si el `sha256` ya se ingirió, se omite |
| `silver` | Bronze vigente | `silver_resultados.parquet`, `silver_rechazos.parquet` | Elimina PII, tipa, seudonimiza con HMAC |
| `dq-silver` | Silver | `dq_results.parquet`, `reports/quality/dq_<run_id>.md` | Bloquea Gold si falla una regla bloqueante |
| `gold` | Silver aprobado | Estrella, agregados con supresión, `ml_dataset.parquet`, `seguridad_rectores.parquet` | Publica por intercambio de carpeta: si algo falla, queda la versión anterior |
| `dq-gold` | Gold | Informe de calidad | Bloquea ML si falla |
| `ml` | `ml_dataset.parquet` | `models/<run_id>/`, `reports/ml/` | El año más reciente se evalúa una sola vez |
| `shap` | Modelo de la última ejecución de `ml` | `reports/shap/` | Explica el modelo elegido y uno de contraste |
| `fairness` | Predicciones de la última ejecución de `ml` | `reports/fairness/` | Desempeño por subgrupo con IC |

---

## 6. Códigos de salida

| Código | Significado | Qué hacer |
|--:|---|---|
| 0 | Éxito (o etapa omitida por idempotencia) | — |
| 1 | Fallo técnico | Revisar el traceback en el log y el detalle en `run_log` |
| 2 | El CSV no cumple el contrato | Comparar con `config/source_contract.yaml`; no se toca nada aguas abajo |
| 3 | Etapa no implementada | No debería ocurrir: todas las etapas del plan están implementadas |
| 4 | Quality gate rechazado | Abrir `reports/quality/dq_<run_id>.md`, corregir el origen y repetir desde `silver` |
| 5 | Etapa bloqueada porque la anterior no está disponible o aprobada | Ejecutar la etapa previa (`dq --layer silver` antes de Gold, `dq --layer gold` antes de ML, `ml` antes de `shap`/`fairness`) |

---

## 7. Llegan datos nuevos

1. Copiar el CSV a `data/landing/` (mismo nombre y formato).
2. `.\tasks.ps1 run`.
3. Si `dq-silver` rechaza: **el Gold vigente no se toca**. Corregir el origen y repetir.
4. Actualizar los tableros: abrir `powerbi/Saber11_Estrategico.pbip` y
   `powerbi/Saber11_Operativo.pbip` y pulsar *Actualizar* (Power BI Desktop no programa
   actualizaciones; con el modelo publicado en el Service, la actualización se programa allí).
5. Re-ejecutar los controles de BI: `python -m saber11.bi.kpi_control [--tablero operativo]`.
6. Comparar el modelo nuevo con el vigente antes de promoverlo (`reports/ml/comparacion_modelos.md`
   y la regla del plan §16.4).

---

## 8. Dónde queda cada cosa

| Ruta | Contenido | ¿Se versiona? |
|---|---|---|
| `data/` | Bronze, Silver, Gold y metadatos | No |
| `models/<run_id>/` | Modelo, parámetros, métricas y predicciones | No: se regenera con `run -Stage ml` |
| `reports/quality/` | Contrato y calidad por ejecución | Sí |
| `reports/ml`, `reports/shap`, `reports/fairness` | Evidencia de las fases F8–F10 | Sí |
| `reports/operacion/ultima_ejecucion.md` | Manifiesto de la última corrida completa | Sí (se sobrescribe) |
| `data/metadata/run_log.parquet` | Histórico de todas las ejecuciones | No |
| `powerbi/*.pbip` | Modelos e informes (TMDL + PBIR, sin datos) | Sí |

---

## 9. Reproducibilidad

- La semilla (`app.seed`, `ml.random_state`) y las versiones fijadas en `requirements.txt`
  hacen que dos ejecuciones con los mismos datos den las mismas métricas. Está comprobado en
  `tests/integration/test_pipeline_completo.py`.
- Cada fila del `run_log` guarda `git_sha` y `git_con_cambios`: si es `true`, el código de esa
  ejecución tenía cambios sin confirmar y el `git_sha` no la describe por completo.
- Bronze conserva el CSV original por `sha256`, así que cualquier capa puede reconstruirse
  desde el origen exacto que se usó.

---

## 10. Problemas frecuentes

| Síntoma | Causa habitual | Solución |
|---|---|---|
| `PermissionError` al escribir el CSV de landing | El archivo está abierto en Excel | Cerrarlo y repetir |
| El contrato falla por tildes raras | El CSV se guardó en UTF-8 en vez de cp1252 | Reexportar con el formato del contrato |
| `SABER11_HMAC_KEY no está definida` | Falta `.env` o la variable | `.\tasks.ps1 setup`, o definirla en el entorno |
| Gold falla al leer la tabla de seguridad | CSV editado a mano con finales de línea mezclados | Guardarlo con un editor que respete un solo tipo de salto de línea (el cargador admite BOM de Excel) |
| ML termina con código 5 | El Gold vigente no tiene gate aprobado | `.\tasks.ps1 run -Stage dq -Layer gold` |
| `models/` crece con cada corrida | Un directorio por `run_id` | Está fuera de git; borrar los antiguos cuando estorben |
| Power BI no ve datos nuevos | El modelo importa datos | Pulsar *Actualizar* en Desktop |

---

## 11. Lo que no hace el pipeline

- **No publica en Power BI Service ni programa actualizaciones**: se hace desde Desktop o el
  portal (ADR-0015).
- **No prueba el RLS con cuentas reales**: la matriz `tests/rls/casos_rls.md` se valida en
  Desktop con *Ver como* y, en el Service, asignando las cuentas del tenant de ensayo como
  *Viewer* (ADR-0019).
- **No decide si un modelo nuevo reemplaza al vigente**: la comparación se publica, la
  promoción es una decisión explícita.
