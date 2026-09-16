"""Gráficos de explicabilidad (F9). Todos los ejes y rótulos van en puntos del puntaje global."""
from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # sin interfaz gráfica: el pipeline corre sin escritorio

import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import shap  # noqa: E402

COLOR_POSITIVO = "#2166ac"
COLOR_NEGATIVO = "#b2182b"
PIE = "SHAP en puntos del puntaje global · datos ficticios"


def _guardar(fig: plt.Figure, ruta: Path) -> Path:
    ruta.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(ruta, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return ruta


def barras_importancia(importancia: dict[str, float], ruta: Path, titulo: str) -> Path:
    """Media de |SHAP| por variable original (las dummies ya agregadas)."""
    orden = sorted(importancia.items(), key=lambda kv: kv[1])
    etiquetas = [k for k, _ in orden]
    valores = [v for _, v in orden]
    fig, ax = plt.subplots(figsize=(7, 0.5 * len(orden) + 1.6))
    ax.barh(etiquetas, valores, color=COLOR_POSITIVO)
    for y, v in enumerate(valores):
        ax.text(v, y, f" {v:.2f}".replace(".", ","), va="center", fontsize=9)
    ax.set_xlabel("Media de |SHAP| (puntos del puntaje global)")
    ax.set_title(titulo)
    ax.set_xlim(0, max(valores) * 1.18 if valores else 1)
    ax.spines[["top", "right"]].set_visible(False)
    fig.text(0.01, 0.005, PIE, fontsize=7, color="#666666")
    return _guardar(fig, ruta)


def beeswarm(valores: np.ndarray, X: pd.DataFrame, ruta: Path, titulo: str) -> Path:
    """Enjambre sobre las columnas transformadas (one-hot incluidas)."""
    explicacion = shap.Explanation(values=valores, data=X.to_numpy(), feature_names=list(X.columns))
    shap.plots.beeswarm(explicacion, max_display=14, show=False)
    fig = plt.gcf()
    fig.set_size_inches(8, 6)
    plt.title(titulo, fontsize=11, pad=18)
    plt.xlabel("SHAP (puntos del puntaje global)")
    fig.text(0.01, 0.005, PIE, fontsize=7, color="#666666")
    return _guardar(fig, ruta)


def dependencia(valores: np.ndarray, columna: pd.Series, ruta: Path, titulo: str) -> Path:
    """Efecto de una variable: dispersión si es numérica, caja por categoría si no lo es."""
    fig, ax = plt.subplots(figsize=(7, 4.2))
    if pd.api.types.is_numeric_dtype(columna):
        ax.scatter(columna + np.random.default_rng(0).normal(0, 0.05, len(columna)), valores,
                   s=8, alpha=0.35, color=COLOR_POSITIVO, edgecolors="none")
        medias = pd.Series(valores).groupby(columna.to_numpy()).mean()
        ax.plot(medias.index, medias.to_numpy(), color=COLOR_NEGATIVO, marker="o", linewidth=1.5,
                label="media por valor")
        ax.legend(frameon=False, fontsize=9)
        ax.set_xticks(sorted(columna.unique()))
    else:
        categorias = sorted(columna.unique())
        ax.boxplot([valores[columna.to_numpy() == c] for c in categorias], tick_labels=categorias,
                   vert=True, showfliers=False)
        ax.tick_params(axis="x", labelrotation=15 if max(len(str(c)) for c in categorias) > 12 else 0)
    ax.axhline(0, color="#999999", linewidth=0.8, linestyle="--")
    ax.set_xlabel(columna.name)
    ax.set_ylabel("SHAP (puntos)")
    ax.set_title(titulo)
    ax.spines[["top", "right"]].set_visible(False)
    fig.text(0.01, 0.005, PIE, fontsize=7, color="#666666")
    return _guardar(fig, ruta)


def cascada(
    contribuciones: dict[str, float],
    valores_fila: dict[str, object],
    base: float,
    prediccion: float,
    real: float,
    ruta: Path,
    titulo: str,
) -> Path:
    """Explicación local: del valor esperado del modelo a la predicción de un caso."""
    orden = sorted(contribuciones.items(), key=lambda kv: abs(kv[1]))
    etiquetas = [f"{k} = {valores_fila[k]}" for k, _ in orden]
    valores = [v for _, v in orden]
    acumulado, inicios = base, []
    for v in valores:
        inicios.append(acumulado)
        acumulado += v
    fig, ax = plt.subplots(figsize=(7.5, 0.5 * len(orden) + 2))
    ax.barh(etiquetas, valores, left=inicios,
            color=[COLOR_POSITIVO if v >= 0 else COLOR_NEGATIVO for v in valores])
    for y, (inicio, v) in enumerate(zip(inicios, valores, strict=True)):
        ax.text(inicio + v + (0.6 if v >= 0 else -0.6), y, f"{v:+.1f}".replace(".", ","),
                va="center", ha="left" if v >= 0 else "right", fontsize=9)
    extremos = [base, prediccion, *inicios, *(i + v for i, v in zip(inicios, valores, strict=True))]
    margen = max(4.0, (max(extremos) - min(extremos)) * 0.18)
    ax.set_xlim(min(extremos) - margen, max(extremos) + margen)
    ax.axvline(base, color="#999999", linewidth=1, linestyle="--")
    ax.text(base, len(orden) - 0.4, f" esperado {base:.1f}".replace(".", ","),
            fontsize=8, color="#666666", ha="left")
    ax.axvline(prediccion, color="#333333", linewidth=1)
    lado = "right" if prediccion >= base else "left"
    ax.text(prediccion + (-0.6 if lado == "right" else 0.6), -0.85,
            f"predicción {prediccion:.1f}".replace(".", ","), fontsize=8, ha=lado)
    ax.set_xlabel(f"Puntaje global · valor real del estudiante: {real:.0f}")
    ax.set_title(titulo)
    ax.spines[["top", "right"]].set_visible(False)
    fig.text(0.01, 0.005, PIE, fontsize=7, color="#666666")
    return _guardar(fig, ruta)


def comparacion_modelos(
    importancias: dict[str, dict[str, float]], ruta: Path, titulo: str
) -> Path:
    """Importancia por variable de los dos modelos explicados, lado a lado."""
    variables = sorted(next(iter(importancias.values())), key=lambda v: -max(
        i.get(v, 0.0) for i in importancias.values()))
    y = np.arange(len(variables))
    alto = 0.8 / len(importancias)
    fig, ax = plt.subplots(figsize=(7.5, 0.55 * len(variables) + 1.8))
    for i, (nombre, imp) in enumerate(importancias.items()):
        ax.barh(y + i * alto, [imp.get(v, 0.0) for v in variables], height=alto, label=nombre)
    ax.set_yticks(y + alto * (len(importancias) - 1) / 2, variables)
    ax.invert_yaxis()
    ax.set_xlabel("Media de |SHAP| (puntos del puntaje global)")
    ax.set_title(titulo)
    ax.legend(frameon=False, fontsize=9)
    ax.spines[["top", "right"]].set_visible(False)
    fig.text(0.01, 0.005, PIE, fontsize=7, color="#666666")
    return _guardar(fig, ruta)
