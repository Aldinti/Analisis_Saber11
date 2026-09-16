"""Métricas, intervalos de confianza y regla de selección del modelo (F8; plan §16.3–§16.4).

Los intervalos se calculan remuestreando **colegios** y no filas: los estudiantes de un
mismo colegio comparten el efecto del centro, así que un bootstrap por fila subestimaría
la incertidumbre. La misma razón por la que la validación agrupa por colegio (§16.3).
"""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, r2_score, root_mean_squared_error

METRICAS = ("r2", "rmse", "mae")
# Niveles de parsimonia: ante un empate estadístico se prefiere el nivel más bajo (§16.4).
# Ridge y Lasso comparten nivel (el plan los trata como una sola familia): entre ellos
# desempata el RMSE, no el orden de esta tabla.
NIVEL_PARSIMONIA = {"baseline_media": 0, "ridge": 1, "lasso": 1, "xgboost": 2}
NIVEL_DESCONOCIDO = max(NIVEL_PARSIMONIA.values()) + 1


@dataclass
class ResultadoModelo:
    """Desempeño de un modelo en validación cruzada y, si se evaluó, en la prueba final."""

    nombre: str
    metricas_cv: dict[str, float] = field(default_factory=dict)
    error_estandar_cv: dict[str, float] = field(default_factory=dict)
    folds: list[dict[str, Any]] = field(default_factory=list)
    mejores_parametros: dict[str, Any] = field(default_factory=dict)
    metricas_test: dict[str, float] = field(default_factory=dict)
    ic_test: dict[str, tuple[float, float]] = field(default_factory=dict)

    def a_dict(self) -> dict[str, Any]:
        return {
            "nombre": self.nombre,
            "cv": self.metricas_cv,
            "error_estandar_cv": self.error_estandar_cv,
            "folds": self.folds,
            "mejores_parametros": self.mejores_parametros,
            "test": self.metricas_test,
            "ic_test": {k: list(v) for k, v in self.ic_test.items()},
        }


def metricas(y: Sequence[float], y_pred: Sequence[float]) -> dict[str, float]:
    """R², RMSE y MAE. RMSE con `root_mean_squared_error` (§ Inconsistencias I11)."""
    y = np.asarray(y, dtype=float)
    y_pred = np.asarray(y_pred, dtype=float)
    return {
        "r2": float(r2_score(y, y_pred)),
        "rmse": float(root_mean_squared_error(y, y_pred)),
        "mae": float(mean_absolute_error(y, y_pred)),
    }


def _indices_por_grupo(grupos: Sequence[Any]) -> dict[Any, np.ndarray]:
    serie = pd.Series(list(grupos))
    return {g: idx.to_numpy() for g, idx in serie.groupby(serie, observed=True).groups.items()}


def remuestreos_por_grupo(
    grupos: Sequence[Any], n_muestras: int, semilla: int
) -> list[np.ndarray]:
    """Índices de `n_muestras` remuestreos con reemplazo sobre los grupos (no sobre las filas)."""
    por_grupo = _indices_por_grupo(grupos)
    claves = sorted(por_grupo, key=str)
    rng = np.random.default_rng(semilla)
    muestras = []
    for _ in range(n_muestras):
        elegidos = rng.integers(0, len(claves), len(claves))
        muestras.append(np.concatenate([por_grupo[claves[i]] for i in elegidos]))
    return muestras


def ic_bootstrap(
    y: Sequence[float],
    y_pred: Sequence[float],
    grupos: Sequence[Any],
    n_muestras: int = 2000,
    semilla: int = 0,
    nivel: float = 0.95,
) -> dict[str, tuple[float, float]]:
    """IC percentil de R²/RMSE/MAE remuestreando colegios con reemplazo."""
    y = np.asarray(y, dtype=float)
    y_pred = np.asarray(y_pred, dtype=float)
    acumulado: dict[str, list[float]] = {m: [] for m in METRICAS}
    for idx in remuestreos_por_grupo(grupos, n_muestras, semilla):
        for nombre, valor in metricas(y[idx], y_pred[idx]).items():
            acumulado[nombre].append(valor)
    alfa = (1 - nivel) / 2
    return {
        m: (float(np.quantile(v, alfa)), float(np.quantile(v, 1 - alfa)))
        for m, v in acumulado.items()
    }


def ic_mejora(
    y: Sequence[float],
    y_pred_modelo: Sequence[float],
    y_pred_referencia: Sequence[float],
    grupos: Sequence[Any],
    metrica: str = "rmse",
    n_muestras: int = 2000,
    semilla: int = 0,
    nivel: float = 0.95,
) -> dict[str, float]:
    """IC de la mejora (referencia − modelo) en la métrica indicada; positivo = el modelo gana.

    Es un contraste pareado: ambos modelos se evalúan sobre las mismas filas remuestreadas.
    """
    y = np.asarray(y, dtype=float)
    a = np.asarray(y_pred_modelo, dtype=float)
    b = np.asarray(y_pred_referencia, dtype=float)
    diferencias = [
        metricas(y[idx], b[idx])[metrica] - metricas(y[idx], a[idx])[metrica]
        for idx in remuestreos_por_grupo(grupos, n_muestras, semilla)
    ]
    alfa = (1 - nivel) / 2
    return {
        "metrica": metrica,
        "mejora": float(metricas(y, b)[metrica] - metricas(y, a)[metrica]),
        "ic_inferior": float(np.quantile(diferencias, alfa)),
        "ic_superior": float(np.quantile(diferencias, 1 - alfa)),
    }


def resumir_folds(folds: list[dict[str, Any]]) -> tuple[dict[str, float], dict[str, float]]:
    """Media y error estándar de la media por métrica a partir de los folds."""
    media, error = {}, {}
    for m in METRICAS:
        valores = np.array([f[m] for f in folds], dtype=float)
        media[m] = float(valores.mean())
        error[m] = float(valores.std(ddof=1) / np.sqrt(len(valores))) if len(valores) > 1 else 0.0
    return media, error


def seleccionar_modelo(
    resultados: dict[str, ResultadoModelo], metrica: str = "rmse"
) -> tuple[str, str]:
    """Regla §16.4: menor RMSE en CV; dentro de 1 error estándar, el modelo más simple."""
    if not resultados:
        raise ValueError("No hay resultados de validación cruzada para seleccionar")
    def coma(valor: float) -> str:
        return f"{valor:.3f}".replace(".", ",")

    mejor = min(resultados.values(), key=lambda r: r.metricas_cv[metrica])
    umbral = mejor.metricas_cv[metrica] + mejor.error_estandar_cv[metrica]
    empatados = [r.nombre for r in resultados.values() if r.metricas_cv[metrica] <= umbral]
    nivel = min(NIVEL_PARSIMONIA.get(n, NIVEL_DESCONOCIDO) for n in empatados)
    candidatos = [n for n in empatados if NIVEL_PARSIMONIA.get(n, NIVEL_DESCONOCIDO) == nivel]
    elegido = min(candidatos, key=lambda n: resultados[n].metricas_cv[metrica])
    if elegido == mejor.nombre:
        motivo = (
            f"menor {metrica.upper()} en validación cruzada ({coma(mejor.metricas_cv[metrica])}); "
            "ningún modelo de menor complejidad queda dentro de 1 error estándar"
        )
    else:
        motivo = (
            f"empate estadístico con {mejor.nombre} "
            f"({coma(resultados[elegido].metricas_cv[metrica])} frente a {coma(mejor.metricas_cv[metrica])}, "
            f"1 EE = {coma(mejor.error_estandar_cv[metrica])}) y menor complejidad"
        )
    return elegido, motivo


def prediccion_media_por_grupo(
    entrena: pd.DataFrame, evaluar: pd.DataFrame, objetivo: str, grupo: str
) -> np.ndarray:
    """Referencia «media histórica del colegio»: usa el colegio, que los modelos no ven.

    No es un modelo comparable (no generaliza a colegios nuevos: cae a la media global);
    sirve para situar cuánto del resultado explica simplemente el centro educativo.
    """
    medias = entrena.groupby(grupo, observed=True)[objetivo].mean()
    global_ = float(entrena[objetivo].mean())
    return evaluar[grupo].map(medias).fillna(global_).to_numpy(dtype=float)
