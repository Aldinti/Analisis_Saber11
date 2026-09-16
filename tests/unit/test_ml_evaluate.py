"""Métricas, intervalos bootstrap y regla de selección del modelo (F8; §16.3–§16.4)."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from saber11.ml import evaluate as ev


def resultado(nombre: str, rmse: float, ee: float) -> ev.ResultadoModelo:
    r = ev.ResultadoModelo(nombre=nombre)
    r.metricas_cv = {"r2": 0.2, "rmse": rmse, "mae": rmse * 0.8}
    r.error_estandar_cv = {"r2": 0.01, "rmse": ee, "mae": ee}
    return r


# ---------------------------------------------------------------- métricas
def test_metricas_prediccion_perfecta():
    m = ev.metricas([1.0, 2.0, 3.0], [1.0, 2.0, 3.0])
    assert m == pytest.approx({"r2": 1.0, "rmse": 0.0, "mae": 0.0})


def test_rmse_y_mae_conocidos():
    m = ev.metricas([0.0, 0.0], [3.0, 4.0])
    assert m["rmse"] == pytest.approx(3.5355339, rel=1e-6)
    assert m["mae"] == pytest.approx(3.5)


# ---------------------------------------------------------------- bootstrap por grupo
def test_ic_bootstrap_es_determinista_y_contiene_el_valor_puntual():
    rng = np.random.default_rng(1)
    y = rng.normal(400, 40, 400)
    y_pred = y + rng.normal(0, 10, 400)
    grupos = np.repeat([f"C{i}" for i in range(8)], 50)
    a = ev.ic_bootstrap(y, y_pred, grupos, n_muestras=200, semilla=3)
    b = ev.ic_bootstrap(y, y_pred, grupos, n_muestras=200, semilla=3)
    assert a == b
    rmse = ev.metricas(y, y_pred)["rmse"]
    assert a["rmse"][0] <= rmse <= a["rmse"][1]


def test_ic_bootstrap_remuestrea_grupos_no_filas():
    """Con un solo grupo todos los remuestreos son idénticos: el intervalo colapsa."""
    y = np.arange(20, dtype=float)
    ic = ev.ic_bootstrap(y, y + 1, ["unico"] * 20, n_muestras=50, semilla=0)
    assert ic["rmse"][0] == pytest.approx(ic["rmse"][1])


def test_ic_mejora_positivo_cuando_el_modelo_gana():
    rng = np.random.default_rng(2)
    y = rng.normal(400, 40, 300)
    grupos = np.repeat([f"C{i}" for i in range(6)], 50)
    mejora = ev.ic_mejora(y, y + rng.normal(0, 5, 300), np.full(300, y.mean()), grupos,
                          n_muestras=200, semilla=5)
    assert mejora["mejora"] > 0
    assert mejora["ic_inferior"] > 0


# ---------------------------------------------------------------- resumen de pliegues
def test_resumir_folds_media_y_error_estandar():
    media, error = ev.resumir_folds([
        {"r2": 0.1, "rmse": 40.0, "mae": 30.0},
        {"r2": 0.3, "rmse": 44.0, "mae": 34.0},
    ])
    assert media["rmse"] == pytest.approx(42.0)
    assert error["rmse"] == pytest.approx(2.0)


# ---------------------------------------------------------------- regla de selección §16.4
def test_selecciona_el_mejor_cuando_no_hay_empate():
    resultados = {
        "baseline_media": resultado("baseline_media", 48.0, 1.0),
        "ridge": resultado("ridge", 44.0, 0.2),
        "xgboost": resultado("xgboost", 41.0, 0.2),
    }
    elegido, motivo = ev.seleccionar_modelo(resultados)
    assert elegido == "xgboost"
    assert "menor RMSE" in motivo


def test_prefiere_el_modelo_mas_simple_dentro_de_un_error_estandar():
    resultados = {
        "baseline_media": resultado("baseline_media", 48.0, 1.0),
        "ridge": resultado("ridge", 41.4, 0.2),
        "xgboost": resultado("xgboost", 41.0, 0.6),
    }
    elegido, motivo = ev.seleccionar_modelo(resultados)
    assert elegido == "ridge"
    assert "empate estadístico" in motivo


def test_entre_ridge_y_lasso_desempata_el_rmse_no_el_orden():
    """Comparten nivel de parsimonia (§16.4): gana el de menor RMSE."""
    resultados = {
        "ridge": resultado("ridge", 41.5, 0.6),
        "lasso": resultado("lasso", 41.4, 0.6),
    }
    assert ev.seleccionar_modelo(resultados)[0] == "lasso"


def test_el_baseline_gana_si_ningun_modelo_lo_supera():
    resultados = {
        "baseline_media": resultado("baseline_media", 45.0, 2.0),
        "xgboost": resultado("xgboost", 44.5, 2.0),
    }
    assert ev.seleccionar_modelo(resultados)[0] == "baseline_media"


def test_seleccionar_sin_resultados():
    with pytest.raises(ValueError, match="No hay resultados"):
        ev.seleccionar_modelo({})


# ---------------------------------------------------------------- referencia por colegio
def test_media_por_grupo_usa_la_media_global_para_colegios_nuevos():
    entrena = pd.DataFrame({"nombre_colegio": ["A", "A", "B", "B"], "y": [10.0, 20.0, 30.0, 50.0]})
    evaluar = pd.DataFrame({"nombre_colegio": ["A", "B", "NUEVO"]})
    pred = ev.prediccion_media_por_grupo(entrena, evaluar, "y", "nombre_colegio")
    assert pred.tolist() == [15.0, 40.0, 27.5]
