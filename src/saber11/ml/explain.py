"""Explicabilidad del modelo con SHAP (F9; plan §8 F9 y §17).

Se explica el **modelo final de F8** y, como contraste, el modelo de la otra familia
(lineal frente a árboles), reajustado con los hiperparámetros que F8 registró. El modelo
lineal usa `LinearExplainer` con el entrenamiento como fondo; el de árboles,
`TreeExplainer` en modo `tree_path_dependent`. Cada uno tiene su propio valor esperado,
así que se comparan **rankings de importancia**, no valores absolutos entre modelos.

Las contribuciones de las variables ficticias (one-hot) se **agregan por variable
original** antes de rankear: de otro modo una variable con muchas categorías parece más
importante solo por estar partida en más columnas.

> SHAP explica el comportamiento del modelo; no demuestra causalidad.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
import shap

from saber11.ml import dataset as ds
from saber11.ml import train as tr

TOLERANCIA_ADITIVIDAD = 1e-3
# Categoría de referencia de cada variable en el generador de datos ficticios (F1b).
REFERENCIAS = {
    "naturaleza_colegio": "Pública",
    "zona": "Urbana",
    "modelo_pedagogico": "Tradicional",
    "sexo": "Femenino",
    "periodo": "II",
}
FAMILIAS = {"baseline_media": "lineal", "ridge": "lineal", "lasso": "lineal", "xgboost": "arbol"}
# Variables cuya recuperación exige el plan §17 (criterio de aceptación: signos coinciden).
EXIGIDAS = ("estrato", "naturaleza_colegio", "zona")


class ErrorExplicacion(RuntimeError):
    """No se puede explicar el modelo con los artefactos disponibles."""


@dataclass
class Explicacion:
    """Valores SHAP de un modelo, ya agregados por variable original."""

    nombre: str
    familia: str
    base: float
    valores: pd.DataFrame          # (n filas de prueba × variables originales)
    valores_columnas: np.ndarray   # (n × columnas transformadas), para el enjambre
    columnas: list[str]
    prediccion: np.ndarray
    error_aditividad: float

    @property
    def importancia(self) -> dict[str, float]:
        return self.valores.abs().mean().sort_values(ascending=False).to_dict()

    def aditividad_ok(self, tolerancia: float = TOLERANCIA_ADITIVIDAD) -> bool:
        return self.error_aditividad <= tolerancia


@dataclass
class ResultadoSHAP:
    """Salida de F9: explicaciones, prueba de recuperación y artefactos publicados."""

    run_id: str
    run_id_ml: str
    modelo_final: str
    explicaciones: dict[str, Explicacion]
    recuperacion: pd.DataFrame
    casos: dict[str, dict[str, Any]]
    coeficientes: pd.DataFrame
    filas: dict[str, int]
    rutas: dict[str, Path] = field(default_factory=dict)

    @property
    def recuperacion_aprobada(self) -> bool:
        exigidas = self.recuperacion[self.recuperacion["exigida"]]
        return bool(len(exigidas)) and bool(exigidas["signo_coincide"].all())

    @property
    def aditividad_ok(self) -> bool:
        return all(e.aditividad_ok() for e in self.explicaciones.values())

    def detalle(self) -> dict[str, Any]:
        return {
            "run_id_ml": self.run_id_ml,
            "modelo_final": self.modelo_final,
            "aditividad_ok": self.aditividad_ok,
            "error_aditividad": {n: e.error_aditividad for n, e in self.explicaciones.items()},
            "recuperacion_aprobada": self.recuperacion_aprobada,
            "importancia": {n: e.importancia for n, e in self.explicaciones.items()},
            "filas": self.filas,
            "artefactos": {k: v.as_posix() for k, v in self.rutas.items()},
        }


# ---------------------------------------------------------------- contexto desde F8
@dataclass
class ContextoF9:
    run_id_ml: str
    directorio: Path
    metricas: dict[str, Any]
    pipeline_final: Any
    variables: ds.Variables
    entrena: pd.DataFrame
    prueba: pd.DataFrame


def cargar_contexto(settings: dict[str, Any], raiz: Path, run_id_ml: str) -> ContextoF9:
    """Recupera el modelo y los conjuntos exactos de la ejecución de F8 indicada."""
    directorio = raiz / settings["paths"]["models"] / run_id_ml
    modelo = directorio / "model.joblib"
    metricas = directorio / "metrics.json"
    if not modelo.exists() or not metricas.exists():
        raise ErrorExplicacion(
            f"Faltan artefactos de la ejecución {run_id_ml} en {directorio.relative_to(raiz).as_posix()}. "
            "Ejecute: run --stage ml"
        )
    df = ds.cargar(settings, raiz)
    variables = ds.seleccionar_variables(df, settings)
    entrena, prueba = ds.separar_temporal(df, int(settings["ml"]["test_year"]))
    return ContextoF9(
        run_id_ml=run_id_ml,
        directorio=directorio,
        metricas=json.loads(metricas.read_text(encoding="utf-8")),
        pipeline_final=joblib.load(modelo),
        variables=variables,
        entrena=entrena,
        prueba=prueba,
    )


def modelo_de_contraste(contexto: ContextoF9, settings: dict[str, Any]) -> tuple[str, Any] | None:
    """Reajusta un modelo de la otra familia con los hiperparámetros que eligió F8."""
    final = contexto.metricas["seleccionado"]
    familia_final = FAMILIAS.get(final, "lineal")
    candidatos = [
        n for n, m in contexto.metricas["modelos"].items()
        if FAMILIAS.get(n) != familia_final and n in tr.ESPECIFICACIONES and m.get("test")
    ]
    if not candidatos:
        return None
    nombre = min(candidatos, key=lambda n: contexto.metricas["modelos"][n]["cv"]["rmse"])
    spec = tr.ESPECIFICACIONES[nombre]
    pipeline = tr.construir_pipeline(spec, contexto.variables, int(settings["ml"]["random_state"]))
    pipeline.set_params(**contexto.metricas["modelos"][nombre]["mejores_parametros"])
    X = tr.matriz(contexto.entrena, contexto.variables)
    pipeline.fit(X, contexto.entrena[contexto.variables.objetivo].to_numpy(dtype=float))
    return nombre, pipeline


# ---------------------------------------------------------------- estructura de columnas
def estructura_columnas(preparacion: Any, variables: ds.Variables) -> tuple[list[str], dict[str, list[int]]]:
    """Nombres de las columnas transformadas y a qué variable original pertenece cada una."""
    nombres: list[str] = []
    indices: dict[str, list[int]] = {}
    transformadores = {n: t for n, t, _ in preparacion.transformers}
    if "cat" in transformadores:
        codificador = preparacion.named_transformers_["cat"]
        for columna, categorias in zip(variables.categoricas, codificador.categories_, strict=True):
            indices[columna] = [len(nombres) + i for i in range(len(categorias))]
            nombres += [f"{columna}={c}" for c in categorias]
    for columna in variables.numericas:
        indices[columna] = [len(nombres)]
        nombres.append(columna)
    return nombres, indices


def agregar_por_variable(
    valores: np.ndarray, indices: dict[str, list[int]]
) -> pd.DataFrame:
    """Suma las contribuciones de las dummies de cada variable original (§17)."""
    return pd.DataFrame({v: valores[:, idx].sum(axis=1) for v, idx in indices.items()})


# ---------------------------------------------------------------- explicaciones
def _transformar(pipeline: Any, X: pd.DataFrame) -> np.ndarray:
    return np.asarray(pipeline.named_steps["preparacion"].transform(X), dtype=float)


def matriz_transformada(
    pipeline: Any, df: pd.DataFrame, variables: ds.Variables, columnas: list[str]
) -> pd.DataFrame:
    """Matriz tras el `ColumnTransformer`, con los nombres de las columnas transformadas."""
    return pd.DataFrame(_transformar(pipeline, tr.matriz(df, variables)), columns=columnas)


def explicar(
    nombre: str,
    pipeline: Any,
    contexto: ContextoF9,
    semilla: int,
) -> Explicacion:
    """SHAP del modelo: `LinearExplainer` si es lineal, `TreeExplainer` si es de árboles."""
    variables = contexto.variables
    X_entrena = tr.matriz(contexto.entrena, variables)
    X_prueba = tr.matriz(contexto.prueba, variables)
    fondo = _transformar(pipeline, X_entrena)
    matriz_prueba = _transformar(pipeline, X_prueba)
    modelo = pipeline.named_steps["modelo"]
    familia = FAMILIAS.get(nombre, "lineal")

    if familia == "arbol":
        # `interventional` no está disponible: XGBoost 3.4 lo rechaza en este modelo
        # ("Categorical split is not yet supported"). El recorrido del árbol es exacto
        # para la aditividad, pero su valor esperado no es comparable con el del lineal.
        explicador = shap.TreeExplainer(modelo, feature_perturbation="tree_path_dependent")
    else:
        explicador = shap.LinearExplainer(modelo, shap.maskers.Independent(fondo, max_samples=len(fondo)))
    explicacion = explicador(matriz_prueba)
    valores = np.asarray(explicacion.values, dtype=float)
    base = float(np.ravel(explicacion.base_values)[0])

    prediccion = pipeline.predict(X_prueba)
    error = float(np.abs(base + valores.sum(axis=1) - prediccion).max())
    nombres, indices = estructura_columnas(pipeline.named_steps["preparacion"], variables)
    return Explicacion(
        nombre=nombre,
        familia=familia,
        base=base,
        valores=agregar_por_variable(valores, indices),
        valores_columnas=valores,
        columnas=nombres,
        prediccion=np.asarray(prediccion, dtype=float),
        error_aditividad=error,
    )


def coeficientes_lineales(pipeline: Any, variables: ds.Variables) -> pd.DataFrame:
    """Coeficientes del modelo lineal, para contrastarlos con el ranking SHAP (§17)."""
    modelo = pipeline.named_steps["modelo"]
    if not hasattr(modelo, "coef_"):
        return pd.DataFrame(columns=["columna", "coeficiente"])
    nombres, _ = estructura_columnas(pipeline.named_steps["preparacion"], variables)
    return (
        pd.DataFrame({"columna": nombres, "coeficiente": np.ravel(modelo.coef_)})
        .sort_values("coeficiente", key=lambda s: s.abs(), ascending=False)
        .reset_index(drop=True)
    )


# ---------------------------------------------------------------- prueba de recuperación §17
def efectos_esperados(parametros: dict[str, Any]) -> dict[tuple[str, str], float]:
    """Efectos del generador (F1b) convertidos a puntos del puntaje global.

    `Global = round(5·(3·(LC+MAT+SOC+CN)+ING)/13)`: un efecto común a las cinco áreas se
    multiplica por 5 y uno que solo afecta Inglés, por 5/13.
    """
    comun, solo_ingles = 5.0, 5.0 / 13.0
    esperados: dict[tuple[str, str], float] = {
        ("estrato", "por nivel"): parametros["efecto_estrato"] * comun,
        ("naturaleza_colegio", "Privada − Pública"):
            parametros["efecto_privada"] * comun + parametros["efecto_ingles_privada"] * solo_ingles,
        ("zona", "Rural − Urbana"): parametros["efecto_rural"] * comun,
        ("periodo", "I − II"): parametros.get("efecto_periodo_I", 0.0) * comun,
        ("anio", "por año"): parametros["efecto_anio"] * comun,
    }
    modelos = parametros["efecto_modelo"]
    base = modelos.get("Tradicional", 0.0)
    for nombre, efecto in modelos.items():
        if nombre != "Tradicional":
            esperados[("modelo_pedagogico", f"{nombre} − Tradicional")] = (efecto - base) * comun
    # El sexo altera Matemáticas y Lectura Crítica en sentidos opuestos y con el mismo peso:
    # su efecto neto sobre el puntaje global es nulo por construcción.
    sexo = parametros.get("efecto_sexo_area", {})
    neto = sum(comun * 3 * (fem - masc) / 13 for fem, masc in sexo.values())
    esperados[("sexo", "Masculino − Femenino")] = -neto
    return esperados


def contrastes_medidos(
    explicacion: Explicacion, prueba: pd.DataFrame, variables: ds.Variables
) -> dict[tuple[str, str], float]:
    """Contrastes observados en el SHAP: diferencia de contribución media entre categorías."""
    medidos: dict[tuple[str, str], float] = {}
    for columna in variables.categoricas:
        shap_col = explicacion.valores[columna].to_numpy()
        valores = prueba[columna].to_numpy()
        medias = {c: float(shap_col[valores == c].mean()) for c in sorted(set(valores))}
        referencia = REFERENCIAS.get(columna, sorted(medias)[0])
        if referencia not in medias:
            continue
        for categoria, media in medias.items():
            if categoria != referencia:
                medidos[(columna, f"{categoria} − {referencia}")] = media - medias[referencia]
    for columna in variables.numericas:
        valores = prueba[columna].to_numpy(dtype=float)
        if len(set(valores)) < 2:  # constante en la prueba (p. ej. el año del holdout)
            continue
        pendiente = float(np.polyfit(valores, explicacion.valores[columna].to_numpy(), 1)[0])
        medidos[(columna, "por nivel" if columna == "estrato" else f"por {columna}")] = pendiente
    return medidos


def prueba_recuperacion(
    explicacion: Explicacion,
    prueba: pd.DataFrame,
    variables: ds.Variables,
    parametros: dict[str, Any],
    tolerancia_nula: float = 2.0,
) -> pd.DataFrame:
    """Compara los contrastes SHAP con los efectos que el generador introdujo (§17).

    Un efecto esperado de 0 (sexo, periodo) no tiene signo que comparar: se da por
    recuperado si el contraste medido se mantiene dentro de `tolerancia_nula` puntos.
    """
    esperados = efectos_esperados(parametros)
    medidos = contrastes_medidos(explicacion, prueba, variables)
    filas = []
    for clave, esperado in esperados.items():
        variable, contraste = clave
        medido = medidos.get(clave)
        if medido is None:
            filas.append({
                "variable": variable, "contraste": contraste, "esperado": esperado,
                "medido": None, "diferencia": None, "error_relativo": None,
                "signo_coincide": None, "exigida": False,
                "nota": "no evaluable en el conjunto de prueba (valor único)",
            })
            continue
        if abs(esperado) < 1e-9:
            coincide = abs(medido) <= tolerancia_nula
            nota = f"efecto nulo por construcción; |medido| ≤ {tolerancia_nula:g} puntos"
        else:
            coincide = np.sign(medido) == np.sign(esperado)
            nota = "signo y orden de magnitud comparables" if coincide else "signo distinto al esperado"
        filas.append({
            "variable": variable, "contraste": contraste, "esperado": esperado, "medido": medido,
            "diferencia": medido - esperado,
            "error_relativo": (medido - esperado) / esperado if abs(esperado) > 1e-9 else None,
            "signo_coincide": bool(coincide), "exigida": variable in EXIGIDAS, "nota": nota,
        })
    return pd.DataFrame(filas)


# ---------------------------------------------------------------- casos locales
def casos_representativos(
    explicacion: Explicacion, prueba: pd.DataFrame, variables: ds.Variables
) -> dict[str, dict[str, Any]]:
    """Tres estudiantes en los percentiles 10, 50 y 90 de la predicción, sin identificadores."""
    orden = np.argsort(explicacion.prediccion)
    casos = {}
    for etiqueta, percentil in (("p10", 0.10), ("p50", 0.50), ("p90", 0.90)):
        fila = int(orden[min(int(percentil * len(orden)), len(orden) - 1)])
        casos[etiqueta] = {
            "percentil": percentil,
            "contribuciones": explicacion.valores.iloc[fila].to_dict(),
            "valores": {c: prueba.iloc[fila][c] for c in variables.predictoras},
            "base": explicacion.base,
            "prediccion": float(explicacion.prediccion[fila]),
            "real": float(prueba.iloc[fila][variables.objetivo]),
        }
    return casos
