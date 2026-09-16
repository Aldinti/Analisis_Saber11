"""Entrenamiento, validación y selección de modelos (F8; plan §8 F8, §16 y §18).

Esquema de validación (§16.3), idéntico para los cuatro modelos:

1. **Prueba final**: el año más reciente (`ml.test_year`) se aparta al principio y se evalúa
   **una sola vez**, después de que la regla de selección ya decidió con la CV.
2. **Comparación y ajuste**: CV anidada sobre los años anteriores, con `GroupKFold` por
   colegio fuera y dentro (`RandomizedSearchCV`), para que ningún estudiante del colegio
   evaluado haya intervenido en el ajuste de hiperparámetros.
3. **Robustez temporal**: CV expansiva (2021→2022, 2021-22→2023) con los parámetros elegidos.
4. **Incertidumbre**: IC 95 % bootstrap remuestreando colegios.

Todo el preprocesamiento vive dentro del `Pipeline`, de modo que se ajusta solo con el
pliegue de entrenamiento (§18: prohibido `fit` fuera de la CV).
"""
from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import Any

import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.dummy import DummyRegressor
from sklearn.linear_model import Lasso, Ridge
from sklearn.model_selection import GroupKFold, ParameterGrid, RandomizedSearchCV
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from xgboost import XGBRegressor

from saber11.ml import dataset as ds
from saber11.ml import evaluate as ev

PUNTUACION = "neg_root_mean_squared_error"


@dataclass(frozen=True)
class Especificacion:
    """Definición de un modelo: cómo se construye, qué se le ajusta y si necesita escalado."""

    nombre: str
    crear: Callable[[int], Any]
    grid: dict[str, list[Any]] = field(default_factory=dict)
    escalar_numericas: bool = True
    n_iter: int = 10

    def combinaciones(self) -> int:
        return len(ParameterGrid(self.grid)) if self.grid else 1


ESPECIFICACIONES: dict[str, Especificacion] = {
    "baseline_media": Especificacion(
        nombre="baseline_media",
        crear=lambda _semilla: DummyRegressor(strategy="mean"),
    ),
    "ridge": Especificacion(
        nombre="ridge",
        crear=lambda semilla: Ridge(random_state=semilla),
        grid={"modelo__alpha": [0.01, 0.1, 0.5, 1.0, 5.0, 10.0, 50.0, 100.0, 500.0, 1000.0]},
        n_iter=10,
    ),
    "lasso": Especificacion(
        nombre="lasso",
        crear=lambda semilla: Lasso(random_state=semilla, max_iter=20000),
        grid={"modelo__alpha": [0.001, 0.005, 0.01, 0.05, 0.1, 0.3, 0.5, 1.0, 3.0, 10.0]},
        n_iter=10,
    ),
    "xgboost": Especificacion(
        nombre="xgboost",
        crear=lambda semilla: XGBRegressor(
            random_state=semilla, tree_method="hist", n_jobs=1, objective="reg:squarederror"
        ),
        grid={
            "modelo__n_estimators": [200, 400, 600],
            "modelo__max_depth": [2, 3, 4, 6],
            "modelo__learning_rate": [0.02, 0.05, 0.1],
            "modelo__subsample": [0.7, 0.9, 1.0],
            "modelo__colsample_bytree": [0.7, 1.0],
            "modelo__min_child_weight": [1, 5, 20],
            "modelo__reg_lambda": [1.0, 5.0, 20.0],
        },
        escalar_numericas=False,
        n_iter=12,
    ),
}


def construir_pipeline(spec: Especificacion, variables: ds.Variables, semilla: int) -> Pipeline:
    """`Pipeline(ColumnTransformer(OneHot, StandardScaler), modelo)` (plan §8 F8, actividad 5)."""
    transformadores: list[tuple[str, Any, list[str]]] = []
    if variables.categoricas:
        transformadores.append(
            ("cat", OneHotEncoder(handle_unknown="ignore", sparse_output=False), variables.categoricas)
        )
    if variables.numericas:
        escalador = StandardScaler() if spec.escalar_numericas else "passthrough"
        transformadores.append(("num", escalador, variables.numericas))
    preparacion = ColumnTransformer(transformadores, remainder="drop", verbose_feature_names_out=False)
    return Pipeline([("preparacion", preparacion), ("modelo", spec.crear(semilla))])


def verificar_sin_fuga(X: pd.DataFrame, variables: ds.Variables) -> None:
    """Control de §18: la matriz de entrada no puede contener el objetivo ni sus derivadas."""
    prohibidas = [
        c for c in X.columns
        if c == variables.objetivo
        or c == variables.grupo
        or c.lower().startswith(ds.PREFIJOS_FUGA)
    ]
    if prohibidas:
        raise ds.ErrorConjuntoML(f"Columnas con fuga en la matriz de entrada: {sorted(prohibidas)}")
    sobrantes = set(X.columns) - set(variables.predictoras)
    if sobrantes:
        raise ds.ErrorConjuntoML(f"Columnas fuera del catálogo de predictoras: {sorted(sobrantes)}")


def _buscador(
    spec: Especificacion, variables: ds.Variables, semilla: int, n_splits: int
) -> RandomizedSearchCV | Pipeline:
    pipeline = construir_pipeline(spec, variables, semilla)
    if not spec.grid:
        return pipeline
    return RandomizedSearchCV(
        pipeline,
        spec.grid,
        n_iter=min(spec.n_iter, spec.combinaciones()),
        scoring=PUNTUACION,
        cv=GroupKFold(n_splits=n_splits),
        random_state=semilla,
        n_jobs=4,
        refit=True,
    )


def _parametros(ajustado: Any) -> dict[str, Any]:
    return dict(getattr(ajustado, "best_params_", {}))


def matriz(df: pd.DataFrame, variables: ds.Variables) -> pd.DataFrame:
    X = df[variables.predictoras].copy()
    verificar_sin_fuga(X, variables)
    return X


def validar_cruzado(
    spec: Especificacion,
    entrena: pd.DataFrame,
    variables: ds.Variables,
    semilla: int,
    n_splits: int,
) -> ev.ResultadoModelo:
    """CV anidada por colegio: ajuste de hiperparámetros dentro, evaluación fuera."""
    X, y = matriz(entrena, variables), entrena[variables.objetivo].to_numpy(dtype=float)
    grupos = entrena[variables.grupo].to_numpy()
    resultado = ev.ResultadoModelo(nombre=spec.nombre)
    for i, (idx_tr, idx_va) in enumerate(GroupKFold(n_splits=n_splits).split(X, y, grupos), start=1):
        buscador = _buscador(spec, variables, semilla, n_splits=3)
        buscador.fit(X.iloc[idx_tr], y[idx_tr], **({"groups": grupos[idx_tr]} if spec.grid else {}))
        fold = ev.metricas(y[idx_va], buscador.predict(X.iloc[idx_va]))
        fold.update(
            fold_n=i,
            n_entrena=len(idx_tr),
            n_valida=len(idx_va),
            colegios_valida=sorted(set(grupos[idx_va])),
            parametros=_parametros(buscador),
        )
        resultado.folds.append(fold)
    resultado.metricas_cv, resultado.error_estandar_cv = ev.resumir_folds(resultado.folds)
    return resultado


def ajustar_final(
    spec: Especificacion,
    entrena: pd.DataFrame,
    variables: ds.Variables,
    semilla: int,
    n_splits: int,
) -> tuple[Pipeline, dict[str, Any]]:
    """Ajusta el modelo en todos los años de entrenamiento y devuelve el pipeline ya entrenado."""
    X, y = matriz(entrena, variables), entrena[variables.objetivo].to_numpy(dtype=float)
    buscador = _buscador(spec, variables, semilla, n_splits)
    buscador.fit(X, y, **({"groups": entrena[variables.grupo].to_numpy()} if spec.grid else {}))
    parametros = _parametros(buscador)
    pipeline = getattr(buscador, "best_estimator_", buscador)
    return pipeline, parametros


def cv_temporal_expansiva(
    spec: Especificacion,
    entrena: pd.DataFrame,
    variables: ds.Variables,
    parametros: dict[str, Any],
    semilla: int,
    columna_anio: str = "anio",
) -> list[dict[str, Any]]:
    """Entrena con los años previos y valida con el siguiente (robustez temporal, §16.3)."""
    anios = sorted(entrena[columna_anio].unique())
    filas = []
    for corte in anios[1:]:
        tr = entrena[entrena[columna_anio] < corte]
        va = entrena[entrena[columna_anio] == corte]
        pipeline = construir_pipeline(spec, variables, semilla).set_params(**parametros)
        pipeline.fit(matriz(tr, variables), tr[variables.objetivo].to_numpy(dtype=float))
        metricas = ev.metricas(
            va[variables.objetivo].to_numpy(dtype=float), pipeline.predict(matriz(va, variables))
        )
        filas.append({
            "entrena_hasta": int(corte) - 1, "valida": int(corte),
            "n_entrena": len(tr), "n_valida": len(va), **metricas,
        })
    return filas


def evaluar_colegios_retenidos(
    spec: Especificacion,
    entrena: pd.DataFrame,
    prueba: pd.DataFrame,
    variables: ds.Variables,
    parametros: dict[str, Any],
    colegios: Sequence[str],
    semilla: int,
) -> dict[str, Any]:
    """Reentrena sin los colegios indicados y los evalúa en el año de prueba (§16.3, punto 1)."""
    sin_colegios = entrena[~entrena[variables.grupo].isin(colegios)]
    objetivo_prueba = prueba[prueba[variables.grupo].isin(colegios)]
    if sin_colegios.empty or objetivo_prueba.empty:
        return {"colegios": list(colegios), "evaluado": False}
    pipeline = construir_pipeline(spec, variables, semilla).set_params(**parametros)
    pipeline.fit(matriz(sin_colegios, variables), sin_colegios[variables.objetivo].to_numpy(dtype=float))
    y = objetivo_prueba[variables.objetivo].to_numpy(dtype=float)
    y_pred = pipeline.predict(matriz(objetivo_prueba, variables))
    por_colegio = {}
    for colegio in colegios:
        sel = objetivo_prueba[variables.grupo] == colegio
        por_colegio[colegio] = {
            "n": int(sel.sum()),
            **ev.metricas(y[sel.to_numpy()], y_pred[sel.to_numpy()]),
        }
    return {
        "colegios": list(colegios),
        "evaluado": True,
        "n_entrena": len(sin_colegios),
        "n_evaluadas": len(objetivo_prueba),
        "conjunto": ev.metricas(y, y_pred),
        "por_colegio": por_colegio,
    }
