"""Controles anti-fuga y construcción del pipeline de modelado (F8; plan §18 y §22)."""
from __future__ import annotations

import numpy as np
import pytest
from sklearn.preprocessing import StandardScaler

from saber11.ml import dataset as ds
from saber11.ml import train as tr


@pytest.fixture()
def variables(marco_ml, settings_ml):
    return ds.seleccionar_variables(marco_ml(), settings_ml)


# ---------------------------------------------------------------- matriz de entrada
def test_la_matriz_solo_contiene_predictoras(marco_ml, variables):
    X = tr.matriz(marco_ml(), variables)
    assert list(X.columns) == variables.predictoras
    assert not {"puntaje_global", "nombre_colegio", "resultado_id"} & set(X.columns)


@pytest.mark.parametrize("columna", ["puntaje_global", "nombre_colegio", "punt_ingles"])
def test_verificar_sin_fuga_rechaza_columnas_prohibidas(marco_ml, variables, columna):
    X = tr.matriz(marco_ml(), variables)
    X[columna] = 1.0
    with pytest.raises(ds.ErrorConjuntoML):
        tr.verificar_sin_fuga(X, variables)


def test_verificar_sin_fuga_rechaza_columnas_fuera_del_catalogo(marco_ml, variables):
    X = tr.matriz(marco_ml(), variables)
    X["inventada"] = 1.0
    with pytest.raises(ds.ErrorConjuntoML, match="fuera del catálogo"):
        tr.verificar_sin_fuga(X, variables)


# ---------------------------------------------------------------- preprocesamiento en el Pipeline
def test_el_preprocesamiento_va_dentro_del_pipeline(variables):
    pipeline = tr.construir_pipeline(tr.ESPECIFICACIONES["ridge"], variables, semilla=1)
    assert list(dict(pipeline.steps)) == ["preparacion", "modelo"]
    numericas = {n: t for n, t, _ in pipeline.named_steps["preparacion"].transformers}["num"]
    assert isinstance(numericas, StandardScaler)


def test_xgboost_no_escala_las_numericas(variables):
    pipeline = tr.construir_pipeline(tr.ESPECIFICACIONES["xgboost"], variables, semilla=1)
    transformadores = {n: t for n, t, _ in pipeline.named_steps["preparacion"].transformers}
    assert transformadores["num"] == "passthrough"


def test_el_escalado_se_ajusta_solo_con_el_entrenamiento(marco_ml, variables):
    """§18: ningún estadístico del preprocesamiento puede mirar el conjunto de prueba."""
    df = marco_ml()
    entrena, _ = ds.separar_temporal(df, 2024)
    pipeline = tr.construir_pipeline(tr.ESPECIFICACIONES["ridge"], variables, semilla=1)
    pipeline.fit(tr.matriz(entrena, variables), entrena["puntaje_global"])
    escalador = {n: t for n, t, _ in pipeline.named_steps["preparacion"].transformers_}["num"]
    medias = dict(zip(variables.numericas, escalador.mean_, strict=True))
    assert medias["anio"] == pytest.approx(entrena["anio"].mean())
    assert medias["anio"] != pytest.approx(df["anio"].mean()), (
        "la media incluye el año de prueba: el escalado se ajustó con todo el conjunto"
    )


def test_categoria_nueva_en_prediccion_no_rompe_el_modelo(marco_ml, variables):
    """`handle_unknown="ignore"`: un colegio nuevo puede traer una categoría no vista."""
    entrena = marco_ml()
    pipeline = tr.construir_pipeline(tr.ESPECIFICACIONES["ridge"], variables, semilla=1)
    pipeline.fit(tr.matriz(entrena, variables), entrena["puntaje_global"])
    nuevo = entrena.head(3).copy()
    nuevo["modelo_pedagogico"] = "Modelo inexistente"
    assert np.isfinite(pipeline.predict(tr.matriz(nuevo, variables))).all()


# ---------------------------------------------------------------- agrupamiento en la CV
def test_ningun_colegio_aparece_a_la_vez_en_ajuste_y_validacion(marco_ml, variables):
    entrena, _ = ds.separar_temporal(marco_ml(n_colegios=6), 2024)
    resultado = tr.validar_cruzado(
        tr.ESPECIFICACIONES["baseline_media"], entrena, variables, semilla=1, n_splits=3
    )
    validados: set[str] = set()
    for fold in resultado.folds:
        evaluados = set(fold["colegios_valida"])
        assert evaluados, "cada pliegue debe evaluar al menos un colegio"
        assert not evaluados & validados, "un colegio no puede validarse en dos pliegues"
        validados |= evaluados
    assert validados == set(entrena["nombre_colegio"])


def test_la_cv_temporal_nunca_entrena_con_el_anio_que_valida(marco_ml, variables):
    entrena, _ = ds.separar_temporal(marco_ml(n_colegios=6), 2024)
    filas = tr.cv_temporal_expansiva(
        tr.ESPECIFICACIONES["baseline_media"], entrena, variables, {}, semilla=1
    )
    assert [f["valida"] for f in filas] == [2022, 2023]
    assert all(f["entrena_hasta"] < f["valida"] for f in filas)
