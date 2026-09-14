# ADR-0014: Estandarización del entorno de ejecución en Python 3.12

## Estado
Aceptado

## Contexto
El entorno host inicial poseía Python 3.14. Paquetes fundamentales de machine learning y compilación JIT como `numba`, `shap` y `xgboost` presentan inestabilidad o ausencia de binarios precompilados (*wheels*) en Windows para Python 3.14.

## Decisión
Fijar el entorno de desarrollo y ejecución estrictamente en **Python 3.12** utilizando `uv` para la provisión del runtime CPython y la gestión determinista de dependencias con `requirements.txt`.

## Consecuencias
- **Positivas:**
  - Compatibilidad al 100 % comprobada con librerías nativas compiladas en Windows.
  - Instalación limpia y reproducible en segundos sin requerir compiladores C++ locales.
  - Soporte de largo plazo en todas las herramientas del stack (DuckDB, Pandas, Scikit-Learn, XGBoost, SHAP).
- **Negativas / Mitigaciones:**
  - Requiere asegurar que la ejecución se realice siempre bajo el intérprete de `.venv` (Python 3.12).
