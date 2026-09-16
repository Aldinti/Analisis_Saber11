"""Cálculo de explicaciones SHAP y prueba de recuperación de efectos (F9; plan §17)."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from saber11.ml import dataset as ds
from saber11.ml import explain as ex
from saber11.ml import train as tr

PARAMETROS = {
    "efecto_estrato": 2.5,
    "efecto_privada": 4.0,
    "efecto_ingles_privada": 5.0,
    "efecto_rural": -4.0,
    "efecto_anio": 0.8,
    "efecto_periodo_I": 0.0,
    "efecto_modelo": {"Tradicional": 0.0, "Constructivista": 1.0},
    "efecto_sexo_area": {"Matemáticas": [-1.5, 1.5], "Lectura Crítica": [1.5, -1.5]},
}


@pytest.fixture()
def variables(marco_ml, settings_ml):
    return ds.seleccionar_variables(marco_ml(), settings_ml)


@pytest.fixture()
def pipeline_ajustado(marco_ml, variables):
    df = marco_ml()
    pipeline = tr.construir_pipeline(tr.ESPECIFICACIONES["ridge"], variables, semilla=1)
    pipeline.fit(tr.matriz(df, variables), df["puntaje_global"])
    return pipeline


# ---------------------------------------------------------------- estructura de columnas
def test_estructura_columnas_mapea_dummies_a_su_variable(pipeline_ajustado, variables):
    nombres, indices = ex.estructura_columnas(pipeline_ajustado.named_steps["preparacion"], variables)
    assert len(nombres) == sum(len(i) for i in indices.values())
    assert set(indices) == set(variables.predictoras)
    for columna in variables.categoricas:
        assert all(nombres[i].startswith(f"{columna}=") for i in indices[columna])
    for columna in variables.numericas:
        assert [nombres[i] for i in indices[columna]] == [columna]


def test_agregar_por_variable_suma_las_dummies():
    valores = np.array([[1.0, 2.0, 10.0], [0.5, -0.5, 4.0]])
    agregado = ex.agregar_por_variable(valores, {"cat": [0, 1], "num": [2]})
    assert agregado["cat"].tolist() == [3.0, 0.0]
    assert agregado["num"].tolist() == [10.0, 4.0]


# ---------------------------------------------------------------- efectos esperados §17
def test_conversion_de_efectos_de_area_a_puntaje_global():
    """Un efecto común a las cinco áreas vale ×5; uno solo de Inglés, ×5/13."""
    esperados = ex.efectos_esperados(PARAMETROS)
    assert esperados[("estrato", "por nivel")] == pytest.approx(12.5)
    assert esperados[("zona", "Rural − Urbana")] == pytest.approx(-20.0)
    assert esperados[("naturaleza_colegio", "Privada − Pública")] == pytest.approx(4 * 5 + 5 * 5 / 13)
    assert esperados[("modelo_pedagogico", "Constructivista − Tradicional")] == pytest.approx(5.0)
    assert esperados[("anio", "por año")] == pytest.approx(4.0)


def test_el_efecto_del_sexo_sobre_el_global_es_nulo_por_construccion():
    """Matemáticas y Lectura Crítica se compensan con el mismo peso en la fórmula del Global."""
    assert ex.efectos_esperados(PARAMETROS)[("sexo", "Masculino − Femenino")] == pytest.approx(0.0)


# ---------------------------------------------------------------- contrastes y recuperación
def explicacion_sintetica(prueba: pd.DataFrame, variables: ds.Variables, efectos: dict) -> ex.Explicacion:
    """Explicación fabricada con contribuciones conocidas, para probar la lectura."""
    valores = pd.DataFrame({v: np.zeros(len(prueba)) for v in variables.predictoras})
    for variable, mapa in efectos.items():
        if callable(mapa):
            valores[variable] = prueba[variable].map(mapa) if variable in prueba else 0.0
        else:
            valores[variable] = prueba[variable].map(mapa).astype(float)
    return ex.Explicacion(
        nombre="sintetico", familia="lineal", base=400.0, valores=valores,
        valores_columnas=valores.to_numpy(), columnas=list(valores.columns),
        prediccion=400.0 + valores.sum(axis=1).to_numpy(), error_aditividad=0.0,
    )


def test_contrastes_medidos_recuperan_las_diferencias_entre_categorias(marco_ml, variables):
    prueba = marco_ml(anios=(2024,))
    explicacion = explicacion_sintetica(prueba, variables, {
        "naturaleza_colegio": {"Privada": 10.0, "Pública": -10.0},
        "estrato": dict.fromkeys(range(1, 7), 0.0) | {e: 3.0 * e for e in range(1, 7)},
    })
    medidos = ex.contrastes_medidos(explicacion, prueba, variables)
    assert medidos[("naturaleza_colegio", "Privada − Pública")] == pytest.approx(20.0)
    assert medidos[("estrato", "por nivel")] == pytest.approx(3.0)


def test_recuperacion_aprueba_cuando_los_signos_coinciden(marco_ml, variables):
    prueba = marco_ml(anios=(2024,))
    explicacion = explicacion_sintetica(prueba, variables, {
        "naturaleza_colegio": {"Privada": 9.0, "Pública": -9.0},
        "zona": {"Rural": -8.0, "Urbana": 8.0},
        "estrato": {e: 10.0 * e for e in range(1, 7)},
    })
    tabla = ex.prueba_recuperacion(explicacion, prueba, variables, PARAMETROS)
    exigidas = tabla[tabla["exigida"]]
    assert set(exigidas["variable"]) == set(ex.EXIGIDAS)
    assert exigidas["signo_coincide"].all()


def test_recuperacion_detecta_un_signo_invertido(marco_ml, variables):
    prueba = marco_ml(anios=(2024,))
    explicacion = explicacion_sintetica(prueba, variables, {
        "zona": {"Rural": 8.0, "Urbana": -8.0},  # el generador esperaba el signo contrario
        "naturaleza_colegio": {"Privada": 9.0, "Pública": -9.0},
        "estrato": {e: 10.0 * e for e in range(1, 7)},
    })
    tabla = ex.prueba_recuperacion(explicacion, prueba, variables, PARAMETROS)
    fila = tabla[tabla["variable"] == "zona"].iloc[0]
    assert fila["signo_coincide"] is False
    assert "signo distinto" in fila["nota"]


def test_variable_constante_en_la_prueba_no_es_evaluable(marco_ml, variables):
    """`anio` es único en el holdout: no hay pendiente que medir, y así se reporta."""
    prueba = marco_ml(anios=(2024,))
    explicacion = explicacion_sintetica(prueba, variables, {})
    tabla = ex.prueba_recuperacion(explicacion, prueba, variables, PARAMETROS)
    fila = tabla[tabla["variable"] == "anio"].iloc[0]
    assert pd.isna(fila["medido"])
    assert "no evaluable" in fila["nota"]


def test_efecto_nulo_se_aprueba_dentro_de_la_tolerancia(marco_ml, variables):
    prueba = marco_ml(anios=(2024,))
    explicacion = explicacion_sintetica(prueba, variables, {
        "sexo": {"Masculino": 0.2, "Femenino": -0.2},
        "naturaleza_colegio": {"Privada": 9.0, "Pública": -9.0},
        "zona": {"Rural": -8.0, "Urbana": 8.0},
        "estrato": {e: 10.0 * e for e in range(1, 7)},
    })
    tabla = ex.prueba_recuperacion(explicacion, prueba, variables, PARAMETROS)
    assert tabla[tabla["variable"] == "sexo"].iloc[0]["signo_coincide"] is True


# ---------------------------------------------------------------- casos locales
def test_casos_representativos_cubren_los_tres_percentiles(marco_ml, variables):
    prueba = marco_ml(anios=(2024,))
    explicacion = explicacion_sintetica(prueba, variables, {"estrato": {e: 10.0 * e for e in range(1, 7)}})
    casos = ex.casos_representativos(explicacion, prueba, variables)
    assert list(casos) == ["p10", "p50", "p90"]
    assert casos["p10"]["prediccion"] < casos["p50"]["prediccion"] < casos["p90"]["prediccion"]
    for caso in casos.values():
        assert set(caso["valores"]) == set(variables.predictoras)
        assert caso["base"] == pytest.approx(400.0)


# ---------------------------------------------------------------- aditividad con un modelo real
def test_aditividad_del_explicador_lineal(marco_ml, settings_ml, variables, tmp_path, monkeypatch):
    df = marco_ml()
    entrena, prueba = ds.separar_temporal(df, 2024)
    pipeline = tr.construir_pipeline(tr.ESPECIFICACIONES["ridge"], variables, semilla=1)
    pipeline.fit(tr.matriz(entrena, variables), entrena["puntaje_global"])
    contexto = ex.ContextoF9(
        run_id_ml="prueba", directorio=tmp_path, metricas={}, pipeline_final=pipeline,
        variables=variables, entrena=entrena, prueba=prueba,
    )
    explicacion = ex.explicar("ridge", pipeline, contexto, semilla=1)
    assert explicacion.aditividad_ok()
    assert list(explicacion.valores.columns) == variables.predictoras
