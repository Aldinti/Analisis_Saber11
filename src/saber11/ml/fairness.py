"""Desempeño del modelo por subgrupo (F10; plan §8 F10 y §19).

Se mide si el modelo **acierta por igual** en todos los subgrupos, no si unos rinden más
que otros: una brecha de error indica que el modelo funciona peor para ese grupo.

Dos decisiones de método:

- **Unidad de remuestreo.** Los intervalos se calculan remuestreando colegios, porque los
  estudiantes de un mismo centro comparten su efecto. La excepción es la dimensión
  «colegio»: ahí cada grupo *es* un colegio, así que un bootstrap de colegios daría un
  intervalo de ancho cero y se remuestrean filas.
- **Grupos pequeños.** Por debajo de `n_min` un RMSE no distingue señal de ruido: el grupo
  se reporta con su n pero se marca «no concluyente» y queda fuera del cálculo de brechas.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd

from saber11.ml import evaluate as ev

DIMENSIONES: tuple[str, ...] = (
    "sexo", "estrato", "zona", "naturaleza_colegio", "modelo_pedagogico",
    "nombre_colegio", "anio", "periodo",
)
INTERSECCIONALES: tuple[tuple[str, ...], ...] = (
    ("naturaleza_colegio", "zona"),
    ("sexo", "estrato"),
)
COLUMNA_CLUSTER = "nombre_colegio"
N_MIN_CONCLUYENTE = 30
UMBRAL_BRECHA_RMSE = 0.10  # fracción del RMSE global a partir de la cual se emite alerta
N_MUESTRAS = 1000
SEPARADOR = " · "


@dataclass
class Subgrupo:
    """Desempeño del modelo en un subgrupo del conjunto de prueba."""

    dimension: str
    grupo: str
    n: int
    rmse: float
    mae: float
    sesgo_medio: float          # media de (predicción − real): positivo = el modelo sobreestima
    r2: float
    sd_real: float              # dispersión del resultado real: el RMSE no baja de ahí
    ic_rmse: tuple[float, float]
    ic_sesgo: tuple[float, float]
    ic_sesgo_relativo: tuple[float, float]  # sesgo del grupo menos el sesgo global
    concluyente: bool

    @property
    def sesgo_significativo(self) -> bool:
        """El intervalo del sesgo medio no incluye 0: la desviación es sistemática."""
        return self.concluyente and (self.ic_sesgo[0] > 0 or self.ic_sesgo[1] < 0)

    @property
    def sesgo_especifico(self) -> bool:
        """El sesgo del grupo se aparta del sesgo global: es propio del grupo, no del modelo entero."""
        return self.concluyente and (
            self.ic_sesgo_relativo[0] > 0 or self.ic_sesgo_relativo[1] < 0
        )

    def a_dict(self) -> dict[str, Any]:
        return {
            "dimension": self.dimension, "grupo": self.grupo, "n": self.n,
            "rmse": self.rmse, "mae": self.mae, "sesgo_medio": self.sesgo_medio, "r2": self.r2,
            "sd_real": self.sd_real,
            "rmse_ic_inferior": self.ic_rmse[0], "rmse_ic_superior": self.ic_rmse[1],
            "sesgo_ic_inferior": self.ic_sesgo[0], "sesgo_ic_superior": self.ic_sesgo[1],
            "sesgo_relativo_ic_inferior": self.ic_sesgo_relativo[0],
            "sesgo_relativo_ic_superior": self.ic_sesgo_relativo[1],
            "concluyente": self.concluyente, "sesgo_significativo": self.sesgo_significativo,
            "sesgo_especifico": self.sesgo_especifico,
        }


@dataclass
class Dimension:
    """Resultado de una dimensión: sus subgrupos, la brecha entre ellos y si genera alerta."""

    nombre: str
    subgrupos: list[Subgrupo]
    unidad_remuestreo: str
    brecha: float | None = None
    ic_brecha: tuple[float, float] | None = None
    alerta: bool = False
    motivo_no_evaluable: str | None = None

    @property
    def evaluable(self) -> bool:
        return self.motivo_no_evaluable is None

    @property
    def concluyentes(self) -> list[Subgrupo]:
        return [s for s in self.subgrupos if s.concluyente]

    @property
    def correlacion_rmse_dispersion(self) -> float:
        """Cuánto sigue el RMSE a la dispersión del resultado dentro de cada grupo.

        Si es alta, la brecha refleja sobre todo que unos grupos tienen resultados más
        dispersos que otros —el RMSE no puede bajar de ahí— y no que el modelo sea peor
        para ellos.
        """
        concluyentes = [s for s in self.concluyentes if not np.isnan(s.sd_real)]
        if len(concluyentes) < 3:
            return float("nan")
        rmse = np.array([s.rmse for s in concluyentes])
        dispersion = np.array([s.sd_real for s in concluyentes])
        if rmse.std() == 0 or dispersion.std() == 0:
            return float("nan")
        return float(np.corrcoef(rmse, dispersion)[0, 1])

    def a_dict(self) -> dict[str, Any]:
        return {
            "nombre": self.nombre, "evaluable": self.evaluable,
            "motivo_no_evaluable": self.motivo_no_evaluable,
            "unidad_remuestreo": self.unidad_remuestreo,
            "brecha_rmse": self.brecha,
            "ic_brecha": list(self.ic_brecha) if self.ic_brecha else None,
            "alerta": self.alerta,
            "correlacion_rmse_dispersion": self.correlacion_rmse_dispersion,
            "subgrupos": [s.a_dict() for s in self.subgrupos],
        }


@dataclass
class ResultadoSesgos:
    """Salida de F10: desempeño por subgrupo, brechas y alertas."""

    run_id: str
    run_id_ml: str
    modelo: str
    metricas_globales: dict[str, float]
    dimensiones: list[Dimension]
    n_min: int
    umbral_brecha: float
    filas: int
    sesgo_global: float = 0.0
    ic_sesgo_global: tuple[float, float] = (float("nan"), float("nan"))
    rutas: dict[str, Any] = field(default_factory=dict)

    @property
    def alertas(self) -> list[Dimension]:
        return [d for d in self.dimensiones if d.alerta]

    @property
    def sesgo_global_significativo(self) -> bool:
        return self.ic_sesgo_global[0] > 0 or self.ic_sesgo_global[1] < 0

    @property
    def subgrupos_con_sesgo(self) -> list[Subgrupo]:
        return [s for d in self.dimensiones for s in d.subgrupos if s.sesgo_significativo]

    @property
    def subgrupos_con_sesgo_propio(self) -> list[Subgrupo]:
        """Grupos cuyo sesgo se aparta del sesgo global del modelo."""
        return [s for d in self.dimensiones for s in d.subgrupos if s.sesgo_especifico]

    def tabla(self) -> pd.DataFrame:
        return pd.DataFrame([s.a_dict() for d in self.dimensiones for s in d.subgrupos])

    def detalle(self) -> dict[str, Any]:
        return {
            "run_id_ml": self.run_id_ml,
            "modelo": self.modelo,
            "globales": self.metricas_globales,
            "n_min": self.n_min,
            "umbral_brecha": self.umbral_brecha,
            "dimensiones_evaluadas": [d.nombre for d in self.dimensiones if d.evaluable],
            "alertas": [d.nombre for d in self.alertas],
            "sesgo_global": self.sesgo_global,
            "ic_sesgo_global": list(self.ic_sesgo_global),
            "subgrupos_con_sesgo_propio": [
                f"{s.dimension}={s.grupo}" for s in self.subgrupos_con_sesgo_propio
            ],
            "filas": self.filas,
            "artefactos": {k: v.as_posix() for k, v in self.rutas.items()},
        }


# ---------------------------------------------------------------- utilidades
def etiquetas(df: pd.DataFrame, dimension: str) -> pd.Series:
    """Serie de etiquetas de la dimensión; las interseccionales unen sus columnas."""
    columnas = dimension.split(SEPARADOR)
    faltantes = [c for c in columnas if c not in df.columns]
    if faltantes:
        raise KeyError(f"La dimensión '{dimension}' requiere columnas ausentes: {faltantes}")
    return df[columnas].astype(str).agg(SEPARADOR.join, axis=1)


def unidad_remuestreo(dimension: str) -> str:
    """Colegios, salvo cuando la dimensión ya separa por colegio (daría intervalos vacíos)."""
    return "fila" if COLUMNA_CLUSTER in dimension.split(SEPARADOR) else "colegio"


def _distribuciones(
    codigos: np.ndarray, residuos: np.ndarray, resamples: list[np.ndarray], k: int
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """RMSE y sesgo por grupo en cada remuestreo, más el sesgo global de ese remuestreo.

    NaN si el grupo no salió sorteado. El sesgo global permite separar la parte del sesgo
    que comparte todo el modelo de la que es propia del grupo.
    """
    rmse = np.full((len(resamples), k), np.nan)
    sesgo = np.full((len(resamples), k), np.nan)
    sesgo_global = np.empty(len(resamples))
    for i, idx in enumerate(resamples):
        c = codigos[idx]
        r = residuos[idx]
        n = np.bincount(c, minlength=k)
        presente = n > 0
        cuadrados = np.bincount(c, weights=r**2, minlength=k)
        sumas = np.bincount(c, weights=r, minlength=k)
        rmse[i, presente] = np.sqrt(cuadrados[presente] / n[presente])
        sesgo[i, presente] = sumas[presente] / n[presente]
        sesgo_global[i] = r.mean()
    return rmse, sesgo, sesgo_global


def _ic(distribucion: np.ndarray, nivel: float = 0.95) -> tuple[float, float]:
    validos = distribucion[~np.isnan(distribucion)]
    if validos.size == 0:
        return (float("nan"), float("nan"))
    alfa = (1 - nivel) / 2
    return float(np.quantile(validos, alfa)), float(np.quantile(validos, 1 - alfa))


def _brecha(valores: np.ndarray) -> float | None:
    """Diferencia entre el peor y el mejor grupo; necesita al menos dos grupos presentes."""
    validos = valores[~np.isnan(valores)]
    return float(validos.max() - validos.min()) if validos.size >= 2 else None


# ---------------------------------------------------------------- evaluación
def evaluar_dimension(
    df: pd.DataFrame,
    dimension: str,
    objetivo: str,
    n_min: int = N_MIN_CONCLUYENTE,
    umbral: float = UMBRAL_BRECHA_RMSE,
    rmse_global: float | None = None,
    n_muestras: int = N_MUESTRAS,
    semilla: int = 0,
) -> Dimension:
    etiqueta = etiquetas(df, dimension)
    unidad = unidad_remuestreo(dimension)
    if etiqueta.nunique() < 2:
        return Dimension(
            nombre=dimension, subgrupos=[], unidad_remuestreo=unidad,
            motivo_no_evaluable=(
                f"un solo valor en el conjunto de prueba ({etiqueta.iloc[0] if len(etiqueta) else '—'})"
            ),
        )

    codigos_serie, categorias = pd.factorize(etiqueta, sort=True)
    codigos = np.asarray(codigos_serie)
    residuos = (df["prediccion"].to_numpy(dtype=float) - df[objetivo].to_numpy(dtype=float))
    clusters = df[COLUMNA_CLUSTER].to_numpy() if unidad == "colegio" else np.arange(len(df))
    resamples = ev.remuestreos_por_grupo(clusters, n_muestras, semilla)
    dist_rmse, dist_sesgo, dist_global = _distribuciones(codigos, residuos, resamples, len(categorias))

    subgrupos = []
    for i, categoria in enumerate(categorias):
        sel = codigos == i
        y = df[objetivo].to_numpy(dtype=float)[sel]
        y_pred = df["prediccion"].to_numpy(dtype=float)[sel]
        m = ev.metricas(y, y_pred) if len(set(y.tolist())) > 1 else {"r2": float("nan"),
                                                                     "rmse": float(np.sqrt((residuos[sel] ** 2).mean())),
                                                                     "mae": float(np.abs(residuos[sel]).mean())}
        subgrupos.append(Subgrupo(
            dimension=dimension, grupo=str(categoria), n=int(sel.sum()),
            rmse=m["rmse"], mae=m["mae"], sesgo_medio=float(residuos[sel].mean()), r2=m["r2"],
            sd_real=float(y.std(ddof=1)) if sel.sum() > 1 else float("nan"),
            ic_rmse=_ic(dist_rmse[:, i]), ic_sesgo=_ic(dist_sesgo[:, i]),
            ic_sesgo_relativo=_ic(dist_sesgo[:, i] - dist_global),
            concluyente=bool(sel.sum() >= n_min),
        ))

    indices = [i for i, s in enumerate(subgrupos) if s.concluyente]
    resultado = Dimension(nombre=dimension, subgrupos=subgrupos, unidad_remuestreo=unidad)
    if len(indices) < 2:
        resultado.motivo_no_evaluable = (
            f"menos de dos subgrupos con n ≥ {n_min}; las brechas no serían interpretables"
        )
        return resultado
    valores = np.array([subgrupos[i].rmse for i in indices])
    resultado.brecha = float(valores.max() - valores.min())
    brechas = [b for b in (_brecha(fila[indices]) for fila in dist_rmse) if b is not None]
    resultado.ic_brecha = _ic(np.array(brechas)) if brechas else None
    if rmse_global:
        resultado.alerta = resultado.brecha > umbral * rmse_global
    return resultado


def sesgo_global(
    df: pd.DataFrame, objetivo: str, n_muestras: int = N_MUESTRAS, semilla: int = 0
) -> tuple[float, tuple[float, float]]:
    """Sesgo medio del modelo en todo el conjunto, con IC remuestreando colegios.

    Es la referencia obligada: si el modelo se desvía en bloque, ese mismo desvío aparece
    en todos los subgrupos y no debe leerse como un problema de ninguno en particular.
    """
    residuos = df["prediccion"].to_numpy(dtype=float) - df[objetivo].to_numpy(dtype=float)
    clusters = df[COLUMNA_CLUSTER].to_numpy() if COLUMNA_CLUSTER in df.columns else np.arange(len(df))
    muestras = [
        float(residuos[idx].mean())
        for idx in ev.remuestreos_por_grupo(clusters, n_muestras, semilla)
    ]
    return float(residuos.mean()), _ic(np.array(muestras))


def evaluar(
    df: pd.DataFrame,
    objetivo: str,
    dimensiones: tuple[str, ...] = DIMENSIONES,
    interseccionales: tuple[tuple[str, ...], ...] = INTERSECCIONALES,
    n_min: int = N_MIN_CONCLUYENTE,
    umbral: float = UMBRAL_BRECHA_RMSE,
    n_muestras: int = N_MUESTRAS,
    semilla: int = 0,
) -> list[Dimension]:
    """Evalúa todas las dimensiones disponibles en el conjunto de predicciones."""
    globales = ev.metricas(df[objetivo].to_numpy(dtype=float), df["prediccion"].to_numpy(dtype=float))
    nombres = [d for d in dimensiones if d in df.columns]
    nombres += [
        SEPARADOR.join(combo) for combo in interseccionales
        if all(c in df.columns for c in combo)
    ]
    return [
        evaluar_dimension(df, nombre, objetivo, n_min, umbral, globales["rmse"], n_muestras, semilla)
        for nombre in nombres
    ]
