# Suite de pruebas

Consolidación de F12: qué exige el plan (§22), qué lo cubre y qué sigue siendo manual.

```powershell
.\tasks.ps1 test                              # toda la suite con cobertura
$env:PYTHONPATH = "src"                       # para invocar pytest directamente
.\.venv\Scripts\pytest.exe tests/data         # solo una carpeta
.\.venv\Scripts\pytest.exe -k reproducible    # solo lo que interesa
```

**Estado (16-sep-2026):** 266 pruebas verdes · cobertura **94 %** de `src/saber11/` ·
duración ≈ 7 min. El umbral del plan (80 %) está **enforced**: `pytest` falla por debajo de
él (`--cov-fail-under=80` en `pyproject.toml`), así que la cobertura no puede degradarse sin
que la suite se ponga roja.

---

## 1. Trazabilidad con el plan §22

| Tipo (§22) | Criterio | Dónde está | Estado |
|---|---|---|---|
| **Unitarias** | 100 % verdes | `tests/unit/` — 129 pruebas en 14 archivos | ✅ |
| **Datos** | Reglas bloqueantes PASS sobre lo publicado | `tests/data/` — 52 pruebas: `test_silver_contract.py`, `test_no_pii.py`, `test_ranges.py`, `test_gold_referential.py` | ✅ |
| **Integración** | Pipeline completo, artefactos esperados | `tests/integration/` — 85 pruebas en 8 archivos; la cadena entera en `test_pipeline_completo.py` | ✅ |
| **ML** | Sin fuga, ajuste solo con entrenamiento, aditividad SHAP | `tests/unit/test_ml_no_leakage.py`, `tests/unit/test_ml_explain.py`, `tests/integration/test_ml_shap.py` | ✅ |
| **Funcionales BI** | Diferencia KPI ≤ 0,01 frente a SQL | `tests/bi/kpi_control.sql`, `kpi_control_operativo.sql`; comparación automática en `tests/unit/test_bi_*.py`; evidencia en `reports/bi/validacion_kpis_*.md` | ✅ 21/21 y 13/13 |
| **RLS** | 100 % de casos | `tests/rls/casos_rls.md` (RLS-01..11) + evidencia DAX en `reports/bi/` | ✅ con revisión humana |
| **Reproducibilidad** | Mismos hashes y mismas métricas | `tests/integration/test_reproducible.py` (contenido de Silver y Gold), `test_pipeline_completo.py` (métricas de ML) | ✅ |

---

## 2. Qué comprueba cada carpeta

### `tests/unit/` — lógica aislada
Normalización de nombres, seudonimización HMAC, catálogo y SQL de las 19 reglas DQ, contrato
de la fuente, perfilamiento, generador de datos ficticios, construcción de los informes PBIR
y catálogos DAX, y toda la capa de ML (selección de variables, métricas, regla de selección,
explicabilidad y sesgos). No tocan disco salvo `tmp_path`.

### `tests/data/` — los artefactos publicados
Se ejecutan contra `data/` tal como está en la máquina y **se omiten** si no hay datos
(clon recién hecho o integración continua sin el CSV). Cubren lo que el catálogo DQ no puede
ver por sí solo:

- **Contrato de Silver:** columnas exactas y tipos del plan, nombres snake_case ASCII, sin
  nulos en obligatorias, formato del seudónimo, unicidad por estudiante-año-periodo y cuadre
  `Silver + rechazos = Bronze`.
- **Privacidad:** ninguna columna de identificación directa en Silver ni Gold; el seudónimo
  no sale de Silver; solo `seguridad_rectores` contiene correos; y **los informes de
  `reports/` y `docs/` no reproducen nombres ni números de documento** (se contrastan contra
  la copia original de Bronze).
- **Rangos y dominios:** escalas 0–100 y 0–500, estrato 1–6, año plausible, categorías dentro
  de su dominio cerrado y la fórmula del puntaje global con el umbral del plan.
- **Modelo estrella:** sin hechos huérfanos, claves únicas, 5 filas por evaluación en el
  desglose por área, particiones Hive que devuelven `anio`/`periodo` dentro del archivo
  (ADR-0005), promedios Gold = Silver, y **supresión de grupos pequeños efectiva**
  (`n < k_min` siempre suprimido y sin métricas).

### `tests/integration/` — capas y cadena
Cada capa sobre un lakehouse temporal construido desde un fixture, incluidos los casos de
fallo (gate no aprobado, verificación fallida que conserva la versión anterior, CSV de
seguridad ilegible). La cadena completa se prueba de extremo a extremo en
`test_pipeline_completo.py`: proyecto vacío → un comando → código 0 → artefactos → repetición
idéntica.

### `tests/bi/` y `tests/rls/` — lo que necesita Power BI
Las consultas SQL de control y la matriz RLS. La parte automatizable (que las medidas DAX
existan, que el informe no use columnas prohibidas, que los KPIs publicados coincidan con el
SQL dentro de 0,01) está en `tests/unit/test_bi_*.py`; la parte que exige la interfaz de
Power BI la ejecuta el supervisor.

---

## 3. Lo que no cubre la suite

Queda fuera por definición, no por olvido:

| Qué | Por qué | Cómo se verifica |
|---|---|---|
| Renderizado de los informes en Power BI | Requiere Power BI Desktop | Revisión visual del SUP (F6, F7) |
| RLS con el rol real | *Ver como* y el Service no son automatizables desde aquí | `tests/rls/casos_rls.md`, aprobado por el SUP |
| Publicación en Power BI Service | Requiere licencia y tenant | Pendiente registrado en ADR-0015 |
| Validez externa de los resultados de ML | Los datos son ficticios | Advertencia en todos los informes (S7) |

---

## 4. Convenciones al añadir pruebas

- **Nombre descriptivo en español**, en presente y afirmando el comportamiento esperado:
  `test_las_celdas_suprimidas_no_traen_metricas`, no `test_supresion_2`.
- **Una afirmación por idea.** Si la prueba necesita un comentario para entenderse, el
  comentario explica *por qué* importa, no qué hace la línea.
- **Fixtures compartidas en `tests/conftest.py`:** `marco_ml` (conjunto de modelado),
  `csv_fuente` (CSV en formato de fuente) y `settings_ml`. Las de alcance módulo evitan
  repetir experimentos caros: F8, F9 y F10 se ejecutan **una vez por archivo**, no por prueba.
- **Nada de red ni de rutas absolutas**: todo bajo `tmp_path`/`tmp_path_factory`, salvo
  `tests/data/`, que por diseño mira el proyecto real y se omite si no hay datos.
