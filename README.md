# Análisis Saber 11 — Lakehouse + BI + ML

Plataforma analítica integral y reproducible de resultados de las pruebas Saber 11, diseñada bajo arquitectura Medallion local (DuckDB + Parquet), modelado dimensional en Power BI con RLS dinámico y modelos predictivos e interpretables con Scikit-Learn, XGBoost y SHAP.

---

## 1. Stack Tecnológico

- **Entorno:** Python 3.12 (gestionado de forma determinista con `uv` y `pip-tools`).
- **Motor OLAP:** DuckDB 1.5.x (procesamiento vectorial in-process sin servidor).
- **Almacenamiento:** Apache Parquet (Snappy, particionamiento Hive `anio/periodo`).
- **DataFrames & ML:** Pandas 3.0.x, Scikit-Learn 1.9.x, XGBoost 3.4.x.
- **Explicabilidad (XAI):** SHAP 0.52.x (`TreeExplainer` y `LinearExplainer`).
- **Business Intelligence:** Power BI Desktop + Power BI Service / Fabric (Trial 60 días) para comprobación real de RLS dinámico.
- **Calidad y Testing:** Pytest, Pytest-cov, Ruff.

---

## 2. Estructura del Repositorio

```text
Analisis_Saber11/
├── config/                  # Contratos de fuente, reglas DQ y settings
│   ├── settings.yaml
│   ├── source_contract.yaml
│   ├── dq_rules.yaml
│   └── seguridad_rectores.example.csv   # cuentas de prueba del tenant de ensayo (ADR-0019); el de rectores reales (seguridad_rectores.csv) no se versiona
├── data/                    # Zona de datos (Ignorada por Git)
│   ├── landing/             # CSV de entrada sin procesar
│   ├── bronze/              # Copia inmutable + Parquet VARCHAR
│   ├── silver/              # Datos tipados, limpios y seudonimizados
│   ├── gold/                # Modelo estrella y agregados analíticos
│   └── metadata/            # Logs de ejecución y calidad (run_log)
├── docs/                    # Plan maestro, ADRs y gobernanza
│   ├── PLAN_MAESTRO.md
│   ├── operacion.md             # manual de operación del pipeline
│   ├── pruebas.md               # qué cubre la suite y qué queda manual
│   ├── seguridad.md             # checklist de privacidad y seguridad (F13)
│   ├── lineage.md               # de dónde viene cada número
│   ├── manual_tecnico.md        # para quien mantenga el proyecto
│   ├── manual_usuario.md        # para quien lea los tableros
│   ├── ml/variables_modelo.md   # catálogo de predictoras y exclusiones (generado por --stage ml)
│   ├── data_classification.md
│   └── adr/                 # Decisiones arquitectónicas registradas
├── models/                  # Artefactos y métricas por run_id (no versionado: se regenera con --stage ml)
├── powerbi/                 # Saber11_Estrategico.pbip y Saber11_Operativo.pbip (RLS): TMDL + PBIR, sin datos
├── reports/                 # Informes generados (calidad, perfilamiento, shap, sesgos)
├── scripts/                 # Scripts auxiliares (ej. generación ortogonal F1b)
├── sql/                     # Transformaciones SQL por capa
├── src/saber11/             # Código modular del pipeline
├── tests/                   # unit, data (artefactos publicados), integration, bi y rls
├── tasks.ps1                # Tareas: setup, run, test, lint, clean-tmp
├── pyproject.toml           # Configuración de herramientas
├── requirements.in          # Dependencias directas
├── requirements.txt         # Lockfile determinista
└── .env.example             # Plantilla de variables de entorno
```

---

## 3. Instalación y Configuración Inicial

### Prerrequisitos
- Tener instalado `uv` o Python 3.12.

### Pasos de inicialización
1. **Crear y activar el entorno virtual:**
   ```powershell
   uv venv --python 3.12 .venv
   .\.venv\Scripts\Activate.ps1
   ```
2. **Instalar dependencias fijadas:**
   ```powershell
   uv pip install -r requirements.txt
   ```
3. **Configurar variables de entorno:**
   ```powershell
   Copy-Item .env.example .env
   ```
   *Generar clave HMAC:*
   ```powershell
   .\.venv\Scripts\python.exe -c "import secrets; print('SABER11_HMAC_KEY=' + secrets.token_hex(32))"
   ```
   Copiar el valor resultante en la variable `SABER11_HMAC_KEY` dentro de `.env`.

4. **Ejecutar suite de pruebas de verificación:**
   ```powershell
   .\.venv\Scripts\pytest.exe
   ```
   266 pruebas (unitarias, de datos publicados, de integración, de BI y de reproducibilidad). La suite falla si la cobertura baja del 80 %. Qué cubre cada carpeta y qué queda fuera: [`docs/pruebas.md`](docs/pruebas.md).

5. **Ejecutar el pipeline.** La cadena completa, de un comando:
   ```powershell
   .\tasks.ps1 run              # validate-source -> bronze -> silver -> dq -> gold -> dq -> ml -> shap -> fairness
   .\tasks.ps1 run -From gold   # retomar desde una etapa
   .\tasks.ps1 run -Stage ml    # una sola etapa
   ```
   Se detiene en la primera etapa que falle y devuelve su código; el resumen queda en `reports/operacion/ultima_ejecucion.md` y en `data/metadata/run_log.parquet`. Otras tareas: `setup`, `test`, `lint`, `clean-tmp`. Detalle de operación en [`docs/operacion.md`](docs/operacion.md).

   Etapa por etapa, sin `tasks.ps1`:
   ```powershell
   $env:PYTHONPATH = "src"
   .\.venv\Scripts\python.exe -m saber11.pipeline validate-source      # contrato del CSV de data/landing
   .\.venv\Scripts\python.exe -m saber11.pipeline run --stage bronze   # idempotente: reingestar el mismo archivo se omite
   .\.venv\Scripts\python.exe -m saber11.pipeline run --stage silver   # requiere SABER11_HMAC_KEY en .env
   .\.venv\Scripts\python.exe -m saber11.pipeline run --stage dq --layer silver   # quality gate antes de Gold
   .\.venv\Scripts\python.exe -m saber11.pipeline run --stage gold   # exige el gate de Silver aprobado
   .\.venv\Scripts\python.exe -m saber11.pipeline run --stage dq --layer gold     # quality gate antes de BI/ML
   .\.venv\Scripts\python.exe -m saber11.pipeline run --stage ml     # exige el gate de Gold aprobado
   .\.venv\Scripts\python.exe -m saber11.pipeline run --stage shap   # explicabilidad del modelo de la etapa ml
   .\.venv\Scripts\python.exe -m saber11.pipeline run --stage fairness   # desempeño por subgrupo
   ```
   Códigos de salida: `0` éxito, omitido o gate aprobado, `1` fallo técnico, `2` contrato incumplido, `3` etapa aún no implementada, `4` quality gate rechazado, `5` etapa bloqueada porque la capa anterior no tiene el gate aprobado (Gold exige el de Silver; ML, el de Gold).
   Para el dashboard estratégico abra `powerbi/Saber11_Estrategico.pbip` (si movió el proyecto, actualice el parámetro `RutaGold` en Transformar datos) y pulse *Actualizar*. El dashboard operativo con RLS por colegio es `powerbi/Saber11_Operativo.pbip` (pruebas en *Modelado → Ver como* con `Rol_Rector`; casos en `tests/rls/casos_rls.md`). KPIs de control: `python -m saber11.bi.kpi_control [--tablero operativo]`; catálogo DAX: `python -m saber11.bi.catalogo_medidas [--tablero operativo]`.
   La etapa `ml` (F8) entrena baseline, Ridge, Lasso y XGBoost con validación cruzada anidada por colegio y una única evaluación del año más reciente: deja el modelo elegido en `models/<run_id>/` (no versionado, se regenera) y la evidencia en `reports/ml/comparacion_modelos.md`, `reports/ml/resultados_cv.csv` y `docs/ml/variables_modelo.md`.
   La etapa `shap` (F9) explica el modelo elegido y lo contrasta con un modelo de la otra familia: publica figuras, valores SHAP y `reports/shap/interpretacion.md`, con la prueba de recuperación de los efectos con que se generaron los datos ficticios.
   La etapa `fairness` (F10) mide el desempeño por subgrupo con IC bootstrap, separa el sesgo global del propio de cada grupo y deja `reports/fairness/{desempeno_subgrupos.csv, brechas_rmse.png, informe_sesgos.md}`.
   Cada ejecución queda en `data/metadata/run_log.parquet`; los resultados de calidad en `data/metadata/dq_results.parquet` y los informes (contrato y `dq_<run_id>.md`) en `reports/quality/`.

---

## 4. Política de Privacidad y Seguridad

- **PII Eliminada:** Los identificadores directos (`nroDoc`, `nombre1..apellido2`) son eliminados en la capa Silver.
- **Seudonimización Robusta:** Se utiliza `HMAC-SHA-256` con clave secreta; no se confía en hashing simple sin secreto.
- **Protección contra Cuasi-identificadores:** Se aplica supresión primaria y complementaria para cualquier celda o subgrupo con menos de 5 estudiantes ($k_{\min} \ge 5$).
- **Revisión completa:** el checklist con evidencia por medida y los pendientes está en [`docs/seguridad.md`](docs/seguridad.md).

> ⚠️ **Los datos del repositorio son ficticios** (ver `scripts/generar_datos_ficticios.py`). Sirven para validar la plataforma; ningún resultado describe la realidad educativa.

---

## 5. Documentación

| Si necesita… | Lea |
|---|---|
| Ejecutar y mantener el pipeline día a día | [`docs/operacion.md`](docs/operacion.md) |
| Entender o extender el código | [`docs/manual_tecnico.md`](docs/manual_tecnico.md) |
| Usar los tableros de Power BI | [`docs/manual_usuario.md`](docs/manual_usuario.md) |
| Saber qué significa cada columna | [`docs/data_dictionary.md`](docs/data_dictionary.md) |
| Saber de dónde viene un número | [`docs/lineage.md`](docs/lineage.md) |
| Conocer los resultados y sus límites | [`reports/informe_final.md`](reports/informe_final.md) |
| Saber qué cubren las pruebas | [`docs/pruebas.md`](docs/pruebas.md) |
| Ver el plan y las decisiones | [`docs/PLAN_MAESTRO.md`](docs/PLAN_MAESTRO.md) · [`docs/adr/`](docs/adr/) |
