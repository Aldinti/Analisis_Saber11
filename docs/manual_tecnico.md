# Manual técnico

Para quien tenga que mantener o extender el proyecto. Qué hay, por qué está así y dónde tocar
para cada cambio habitual.

- **Poner en marcha y operar:** [operacion.md](operacion.md)
- **Qué significa cada columna:** [data_dictionary.md](data_dictionary.md) · [lineage.md](lineage.md)
- **Por qué se decidió cada cosa:** [PLAN_MAESTRO.md](PLAN_MAESTRO.md) y [adr/](adr/)
- **Qué cubren las pruebas:** [pruebas.md](pruebas.md) · **Privacidad:** [seguridad.md](seguridad.md)

---

## 1. Ideas que gobiernan el diseño

Cuatro reglas explican la mayoría de las decisiones del código. Si una modificación las
contradice, es señal de que hay que discutirla antes de escribirla.

1. **Nada se publica sin verificarse.** Silver y Gold se escriben en una ubicación temporal,
   se comprueban (conteos, claves, promedios, reglas DQ) y solo entonces se intercambian por
   la versión vigente. Si algo falla, la versión anterior sigue en pie.
2. **Los gates son puntos de control, no informes.** Gold no se construye si el Silver vigente
   no aprobó su gate; ML no entrena si el Gold vigente no aprobó el suyo. El código de salida
   lo refleja (5).
3. **Los datos personales se quedan en Bronze.** Todo lo que sale de ahí está minimizado y
   seudonimizado; lo que llega a BI está además agregado y suprimido.
4. **Cada resultado se puede rehacer.** Semilla fija, versiones fijadas, `run_log` con
   `git_sha` y hash del origen, y claves sustitutas estables entre ejecuciones.

---

## 2. Mapa del código

```text
src/saber11/
├── config.py            # settings.yaml, contrato, reglas DQ, clave HMAC
├── pipeline.py          # CLI: etapas sueltas y cadena completa (F11)
├── logging_utils.py     # logger a consola, sin archivos ni filas de datos
├── ingest/
│   ├── contract.py      # valida el CSV contra config/source_contract.yaml
│   └── bronze.py        # copia inmutable + Parquet VARCHAR + metadatos
├── transform/
│   ├── naming.py        # snake_case ASCII
│   ├── silver.py        # orquesta sql/silver/*.sql y verifica antes de publicar
│   └── gold.py          # orquesta sql/gold/*.sql, claves estables, supresión
├── quality/
│   ├── rules.py         # carga y resuelve el catálogo YAML
│   └── engine.py        # ejecuta el gate por capa y escribe el informe
├── security/pseudonymize.py   # HMAC-SHA-256
├── profiling/profile.py       # perfilamiento reproducible (F1/F1c)
├── bi/                  # constructor PBIR, catálogo DAX y KPIs de control
└── ml/
    ├── dataset.py       # catálogo de variables y separación temporal
    ├── train.py         # pipelines, CV anidada, CV temporal
    ├── evaluate.py      # métricas, bootstrap por colegio, regla de selección
    ├── explain.py       # SHAP y prueba de recuperación de efectos
    ├── fairness.py      # desempeño por subgrupo y brechas
    ├── graficos.py      # figuras (backend Agg)
    └── experimento*.py  # orquestación de F8, F9 y F10 + informes
```

La lógica de datos vive en SQL (`sql/silver/`, `sql/gold/`); Python orquesta, verifica y
publica. Quien quiera entender una transformación debe leer el SQL, no el Python.

---

## 3. Cómo hacer los cambios habituales

### Añadir una regla de calidad
1. Agregar la regla a `config/dq_rules.yaml` con `id`, `dimension`, `tabla`, `sql`,
   `umbral_max_fallos` y `severidad`. Los marcadores `${k_min}`, `${min_schools_comparative}`
   y `${run_id}` se resuelven solos.
2. Si es de Bronze o Silver, entra en el gate `silver`; si menciona tablas Gold, en el gate
   `gold` (`quality/engine.py::reglas_de_capa`).
3. `tests/unit/test_dq_rules.py` ejecuta cada regla contra un caso correcto y uno incorrecto:
   añadir ambos. Una regla que nunca falla en pruebas no protege de nada.

### Añadir una columna a Silver o Gold
1. Modificar el SQL de la capa y, en Silver, `COLUMNAS_SILVER`/`TIPOS_SILVER`.
2. Documentarla en `data_dictionary.md`: hay pruebas que comparan el diccionario con el
   esquema real y fallan si falta.
3. Si llega a Gold, revisar `tests/data/test_gold_referential.py` y el modelo de Power BI.

### Añadir o cambiar una medida DAX
1. Editarla en el modelo (`powerbi/*.SemanticModel/definition/tables/_Medidas.tmdl`) o con el
   MCP de modelado.
2. Reflejarla en `docs/bi/medidas_dax*.md` y en `src/saber11/bi/catalogo_medidas.py`: una
   prueba comprueba que catálogo y modelo coinciden.
3. Si tiene contrapartida en SQL, añadirla a `tests/bi/kpi_control*.sql` y volver a validar
   con `python -m saber11.bi.kpi_control [--tablero operativo]` (tolerancia 0,01).

### Regenerar un informe de Power BI
`python scripts/generar_reporte_estrategico.py` y `..._operativo.py` reconstruyen las páginas
PBIR. **Se niegan a pisar formato manual** salvo con `--forzar`: el formato que el usuario
aplicó en Desktop no está en el generador. Cuidado con `"active": true` — solo es válido en
`Category` de gráficos y `Values` de segmentadores (lección de F6).

### Añadir un modelo o cambiar hiperparámetros
1. Agregar una `Especificacion` a `ml/train.py::ESPECIFICACIONES` (constructor, grid,
   si necesita escalado) y su nivel en `evaluate.py::NIVEL_PARSIMONIA`.
2. El resto —CV anidada, comparación, selección, prueba, SHAP y sesgos— lo recoge solo.
3. Verificar que no entra ninguna variable nueva por la puerta de atrás:
   `tests/unit/test_ml_no_leakage.py`.

### Cambiar un umbral
`config/settings.yaml` concentra `k_min`, `min_schools_comparative`, `test_year`, `cv_splits`,
`random_state`, `n_min_subgrupo` y `umbral_brecha_rmse`. No hay umbrales escritos en el
código; si aparece uno, es un error.

---

## 4. Decisiones que conviene conocer antes de tocar nada

| Decisión | Dónde | Por qué importa al modificar |
|---|---|---|
| Claves sustitutas MD5 estables (ADR-0017) | `sql/gold/01_dimensiones.sql` | Con `row_number()` las claves se desplazarían al llegar un colegio nuevo y romperían el RLS ya publicado |
| Columnas de partición dentro del archivo (ADR-0005) | `transform/gold.py` | Power BI no deriva `anio`/`periodo` de la ruta |
| Modelo operativo solo con agregados (ADR-0018) | `powerbi/Saber11_Operativo.*` | Un *Viewer* con permiso Build consulta cualquier tabla del modelo: ocultar los hechos no basta |
| Cuentas RLS del tenant de ensayo (ADR-0019) | `config/seguridad_rectores.example.csv` | El Service no acepta UPN que no existan en el directorio |
| HMAC en vez de SHA-256 (ADR-0012) | `security/pseudonymize.py` | Un hash sin secreto se revierte por enumeración |
| `periodo` = naturaleza × zona | datos de F1b | Es un alias del diseño: sus efectos no son interpretables por separado (F9) |

---

## 5. Trampas conocidas

Todas costaron una sesión de depuración; están documentadas para que no se repitan.

- **CSV editado a mano en Windows.** Finales de línea mezclados rompen la detección de
  dialecto de DuckDB. Por eso la tabla de seguridad se lee con el módulo `csv` de Python.
- **`TINYINT` se desborda al sumar.** Los puntajes por área son `TINYINT`: convertir a
  `INTEGER` antes de cualquier suma (fue un fallo real en DQ-EXA-001).
- **Excel bloquea el CSV de landing** y el pipeline no puede reemplazarlo.
- **`ALL()` no ignora el RLS.** El comparativo distrital usa una tabla agregada sin relación
  con `dim_colegio`, no `ALL()`.
- **XGBoost 3.4 rechaza el modo *interventional*** de `TreeExplainer`; se usa
  `tree_path_dependent`, con la consecuencia de que los valores esperados no son comparables
  entre modelos (sí los rankings).
- **El año del holdout está fuera del rango de entrenamiento:** los modelos de árboles no
  extrapolan la tendencia y el conjunto entero queda con un sesgo global (visible en F10).

---

## 6. Qué hace falta para pasar a datos reales

1. Cerrar los pendientes de [seguridad.md](seguridad.md) §3 (ACL de Bronze, custodia de la
   clave, retención, revisión jurídica).
2. Sustituir `config/seguridad_rectores.example.csv` por el archivo real, que no se versiona.
3. Volver a correr el perfilamiento: los umbrales de calidad se fijaron con los datos
   ficticios y algunos (rangos, volumen) pueden necesitar ajuste.
4. Reentrenar y **no reutilizar** ninguna conclusión de F8–F10: los efectos actuales los puso
   el generador de F1b.
