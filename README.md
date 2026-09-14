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
│   └── seguridad_rectores.example.csv
├── data/                    # Zona de datos (Ignorada por Git)
│   ├── landing/             # CSV de entrada sin procesar
│   ├── bronze/              # Copia inmutable + Parquet VARCHAR
│   ├── silver/              # Datos tipados, limpios y seudonimizados
│   ├── gold/                # Modelo estrella y agregados analíticos
│   └── metadata/            # Logs de ejecución y calidad (run_log)
├── docs/                    # Plan maestro, ADRs y gobernanza
│   ├── PLAN_MAESTRO.md
│   ├── data_classification.md
│   └── adr/                 # Decisiones arquitectónicas registradas
├── models/                  # Artefactos serializados y métricas por run_id
├── notebooks/               # Cuadernos de perfilamiento y análisis exploratorio
├── powerbi/                 # Proyectos y reportes Power BI (.pbip / .pbix)
├── reports/                 # Informes generados (calidad, perfilamiento, shap, sesgos)
├── scripts/                 # Scripts auxiliares (ej. generación ortogonal F1b)
├── sql/                     # Transformaciones SQL por capa
├── src/saber11/             # Código modular del pipeline
├── tests/                   # Pruebas unitarias, de contrato, integración y RLS
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

5. **Ejecutar el pipeline** (etapas implementadas: `bronze`):
   ```powershell
   $env:PYTHONPATH = "src"
   .\.venv\Scripts\python.exe -m saber11.pipeline validate-source      # contrato del CSV de data/landing
   .\.venv\Scripts\python.exe -m saber11.pipeline run --stage bronze   # idempotente: reingestar el mismo archivo se omite
   ```
   Códigos de salida: `0` éxito u omitido, `1` fallo técnico, `2` contrato incumplido, `3` etapa aún no implementada.
   Cada ejecución queda en `data/metadata/run_log.parquet` y el reporte del contrato en `reports/quality/`.

---

## 4. Política de Privacidad y Seguridad

- **PII Eliminada:** Los identificadores directos (`nroDoc`, `nombre1..apellido2`) son eliminados en la capa Silver.
- **Seudonimización Robusta:** Se utiliza `HMAC-SHA-256` con clave secreta; no se confía en hashing simple sin secreto.
- **Protección contra Cuasi-identificadores:** Se aplica supresión primaria y complementaria para cualquier celda o subgrupo con menos de 5 estudiantes ($k_{\min} \ge 5$).
