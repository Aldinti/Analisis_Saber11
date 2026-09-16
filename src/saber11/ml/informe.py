"""Informes en Markdown de F8: comparación de modelos y catálogo de variables."""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # pragma: no cover - solo para anotaciones
    from saber11.ml.experimento import ResultadoML

NOMBRES = {
    "baseline_media": "Baseline (media)",
    "ridge": "Ridge",
    "lasso": "Lasso",
    "xgboost": "XGBoost",
}


def num(valor: float | None, decimales: int = 3) -> str:
    """Número con coma decimal (convención de los informes del proyecto)."""
    if valor is None:
        return "—"
    if abs(valor) < 0.5 * 10 ** -decimales:
        valor = 0.0  # evita el «-0,00» de los coeficientes anulados
    return f"{valor:,.{decimales}f}".replace(",", " ").replace(".", ",")


def _fila_metricas(metricas: dict[str, float]) -> str:
    return f"{num(metricas['r2'])} | {num(metricas['rmse'], 2)} | {num(metricas['mae'], 2)}"


def catalogo_variables(resultado: ResultadoML) -> str:
    """Catálogo auditable de variables incluidas y excluidas (plan §28)."""
    v = resultado.variables
    lineas = [
        "# Catálogo de variables del modelo (F8)",
        "",
        f"> Generado por `saber11.ml` en la ejecución `{resultado.run_id}`. No editar a mano.",
        "",
        f"Objetivo: `{v.objetivo}` · Variable de agrupamiento en la validación: `{v.grupo}`.",
        "",
        "## Incluidas",
        "",
        "| Variable | Tipo en el modelo | Tratamiento |",
        "|---|---|---|",
    ]
    for c in v.categoricas:
        lineas.append(f"| `{c}` | Categórica | One-Hot (`handle_unknown=\"ignore\"`) |")
    for c in v.numericas:
        lineas.append(f"| `{c}` | Numérica | `StandardScaler` en los modelos lineales; sin escalar en XGBoost |")
    lineas += ["", "## Excluidas", "", "| Variable | Motivo |", "|---|---|"]
    for columna, motivo in sorted(v.excluidas.items()):
        lineas.append(f"| `{columna}` | {motivo} |")
    if v.dependencias:
        lineas += [
            "",
            "## Alias del diseño (dependencias funcionales)",
            "",
            "Estas variables quedan determinadas por otras, así que el modelo reparte el crédito",
            "entre ellas: sus coeficientes y sus valores SHAP no son interpretables por separado.",
            "",
            "| Variable | Determinada por |",
            "|---|---|",
        ]
        for columna, determinantes in v.dependencias:
            lineas.append(f"| `{columna}` | {', '.join(f'`{d}`' for d in determinantes)} |")
    return "\n".join(lineas) + "\n"


def _seccion_cv(resultado: ResultadoML) -> list[str]:
    lineas = [
        "## 3. Comparación por validación cruzada anidada",
        "",
        f"`GroupKFold` por `{resultado.variables.grupo}` fuera y dentro; media de los pliegues ± error",
        "estándar de la media. El conjunto de prueba no interviene aquí.",
        "",
        "| Modelo | R² | RMSE | MAE | EE (RMSE) | Hiperparámetros elegidos |",
        "|---|--:|--:|--:|--:|---|",
    ]
    for nombre, r in resultado.resultados.items():
        parametros = ", ".join(
            f"`{k.replace('modelo__', '')}`={v}" for k, v in sorted(r.mejores_parametros.items())
        ) or "—"
        lineas.append(
            f"| {NOMBRES.get(nombre, nombre)} | {_fila_metricas(r.metricas_cv)} | "
            f"{num(r.error_estandar_cv['rmse'], 2)} | {parametros} |"
        )
    lineas += [
        "",
        "El R² del baseline es negativo porque cada pliegue deja fuera colegios completos: la media",
        "de los colegios de entrenamiento no es la media de los colegios evaluados. Es justamente la",
        "dificultad que mide este esquema y la razón de comparar contra él.",
    ]
    return lineas


def _seccion_temporal(resultado: ResultadoML) -> list[str]:
    lineas = [
        "",
        "## 4. Robustez temporal (validación expansiva)",
        "",
        "Entrenar con los años previos y validar con el siguiente, sin reajustar hiperparámetros.",
        "",
        "| Modelo | Entrena hasta | Valida | n validación | R² | RMSE | MAE |",
        "|---|--:|--:|--:|--:|--:|--:|",
    ]
    for nombre, filas in resultado.temporal.items():
        for f in filas:
            lineas.append(
                f"| {NOMBRES.get(nombre, nombre)} | {f['entrena_hasta']} | {f['valida']} | "
                f"{f['n_valida']} | {_fila_metricas(f)} |"
            )
    return lineas


def _seccion_test(resultado: ResultadoML, anio_test: int) -> list[str]:
    lineas = [
        "",
        f"## 6. Año de prueba {anio_test} (evaluación única)",
        "",
        "Todos los modelos se evalúan en una sola pasada, después de que la regla de selección ya",
        "decidió con la validación cruzada. IC 95 % bootstrap remuestreando colegios.",
        "",
        "| Modelo | R² | RMSE | MAE | IC 95 % RMSE |",
        "|---|--:|--:|--:|---|",
    ]
    for nombre, r in resultado.resultados.items():
        ic = r.ic_test["rmse"]
        marca = " **(seleccionado)**" if nombre == resultado.seleccionado else ""
        lineas.append(
            f"| {NOMBRES.get(nombre, nombre)}{marca} | {_fila_metricas(r.metricas_test)} | "
            f"[{num(ic[0], 2)}; {num(ic[1], 2)}] |"
        )
    m = resultado.mejora_vs_baseline
    veredicto = (
        "El intervalo no incluye 0: la mejora sobre el baseline es estadísticamente distinguible"
        if resultado.supera_baseline
        else "**El intervalo incluye 0: la mejora sobre el baseline no es concluyente**"
    )
    lineas += [
        "",
        f"**Mejora del modelo seleccionado sobre el baseline** (RMSE del baseline − RMSE del modelo): "
        f"{num(m['mejora'], 2)} puntos, IC 95 % [{num(m['ic_inferior'], 2)}; {num(m['ic_superior'], 2)}]. "
        f"{veredicto}.",
    ]
    return lineas


def _seccion_retenidos(resultado: ResultadoML, anio_test: int) -> list[str]:
    r = resultado.retenidos
    if not r.get("evaluado"):
        return ["", "## 7. Colegios nunca vistos", "", "No evaluable con los datos actuales."]
    lineas = [
        "",
        "## 7. Colegios nunca vistos en el entrenamiento",
        "",
        f"El modelo seleccionado se reentrena sin {', '.join(f'`{c}`' for c in r['colegios'])} "
        f"({r['n_entrena']} filas) y se evalúa en sus estudiantes de {anio_test} "
        f"({r['n_evaluadas']} filas). Es el escenario de uso real: un centro que el modelo no conoce.",
        "",
        "| Colegio | n | R² | RMSE | MAE |",
        "|---|--:|--:|--:|--:|",
    ]
    for colegio, m in r["por_colegio"].items():
        lineas.append(f"| `{colegio}` | {m['n']} | {_fila_metricas(m)} |")
    lineas.append(f"| **Conjunto** | {r['n_evaluadas']} | {_fila_metricas(r['conjunto'])} |")
    return lineas


def comparacion(resultado: ResultadoML, settings: dict[str, Any], anio_test: int) -> str:
    """Informe `reports/ml/comparacion_modelos.md` (entregable E18)."""
    v = resultado.variables
    from saber11.ml.experimento import ADVERTENCIA

    lineas = [
        "# Comparación de modelos — F8",
        "",
        f"> ⚠️ {ADVERTENCIA}",
        "",
        f"Ejecución `{resultado.run_id}` · semilla `{settings['ml']['random_state']}` · "
        f"objetivo `{v.objetivo}`.",
        "",
        "## 1. Conjunto y esquema de validación",
        "",
        f"- **Origen:** `data/gold/ml_dataset.parquet` — {resultado.filas['total']} filas, "
        f"{resultado.filas['colegios']} colegios.",
        f"- **Entrenamiento:** años anteriores a {anio_test} ({resultado.filas['entrena']} filas). "
        f"**Prueba:** {anio_test} ({resultado.filas['prueba']} filas), usada una sola vez.",
        f"- **Comparación y ajuste:** CV anidada con `GroupKFold` por `{v.grupo}` "
        f"({settings['ml']['cv_splits']} pliegues fuera, 3 dentro con `RandomizedSearchCV`).",
        "- **Por qué no un `train_test_split` aleatorio:** mezclaría años y estudiantes del mismo",
        "  colegio entre entrenamiento y prueba, lo que infla el desempeño y no refleja el uso real",
        "  (predecir cohortes futuras y colegios nuevos) — plan §16.3.",
        "- **Control de fuga (§18):** el preprocesamiento vive dentro del `Pipeline`, los puntajes por",
        "  área quedan fuera del conjunto y la separación temporal se verifica en código.",
        "",
        "## 2. Variables",
        "",
        f"- **Predictoras ({len(v.predictoras)}):** "
        + ", ".join(f"`{c}`" for c in v.predictoras) + ".",
        f"- **Excluidas ({len(v.excluidas)}):** "
        + ", ".join(f"`{c}` ({m})" for c, m in sorted(v.excluidas.items())) + ".",
        "- Catálogo completo: `docs/ml/variables_modelo.md`.",
    ]
    if v.dependencias:
        alias = "; ".join(
            f"`{c}` = f({', '.join(d)})" for c, d in v.dependencias
        )
        lineas += [
            f"- **Alias del diseño:** {alias}. Son variables redundantes: el modelo reparte su crédito",
            "  entre ellas, así que no deben interpretarse por separado (relevante para F9).",
        ]
    lineas += ["", *_seccion_cv(resultado), *_seccion_temporal(resultado)]
    lineas += [
        "",
        "## 5. Modelo seleccionado",
        "",
        f"**{NOMBRES.get(resultado.seleccionado, resultado.seleccionado)}** — {resultado.motivo_seleccion}.",
        "",
        "Regla aplicada (§16.4): menor RMSE en CV; si otro modelo queda dentro de 1 error estándar,",
        "se prefiere el más simple; además debe superar al baseline en la prueba con un IC que no",
        "incluya 0.",
    ]
    lineas += _seccion_test(resultado, anio_test)
    lineas += _seccion_retenidos(resultado, anio_test)
    lineas += [
        "",
        "## 8. Referencia: media histórica del colegio",
        "",
        "Predecir con la media del colegio en los años de entrenamiento —información que los modelos",
        "no reciben, porque `nombre_colegio` se reserva como variable de agrupamiento— da "
        f"R² {num(resultado.referencia_colegio['r2'])}, RMSE {num(resultado.referencia_colegio['rmse'], 2)}, "
        f"MAE {num(resultado.referencia_colegio['mae'], 2)} en {anio_test}. No es un modelo comparable:",
        "no generaliza a colegios nuevos (cae a la media global) y por eso no entra en la selección.",
        "",
        "## 9. Limitaciones",
        "",
        "- Los efectos que los modelos recuperan fueron introducidos por el generador de datos",
        "  ficticios (`reports/datos_ficticios/parametros_generacion.json`). Sirven para comprobar que",
        "  el pipeline los recupera, no como evidencia educativa.",
        "- El techo de R² está fijado por diseño: la mayor parte de la varianza del puntaje es",
        "  habilidad individual y ruido por área, que ninguna variable del conjunto observa.",
        "- `anio` entra como numérica: los modelos de árboles no extrapolan la tendencia más allá del",
        "  último año visto, a diferencia de los lineales.",
        "- El efecto propio de cada colegio no es un predictor (se usa como grupo), así que el modelo",
        "  no puede distinguir dos centros con los mismos atributos.",
    ]
    return "\n".join(lineas) + "\n"
