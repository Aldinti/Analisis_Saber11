"""Ejecución completa de F9: figuras, valores SHAP e interpretación.

El experimento de F8 y la explicación se ejecutan **una vez por módulo**: son deterministas
y cada corrida cuesta decenas de segundos.
"""
from __future__ import annotations

import dataclasses
import json
from dataclasses import dataclass
from pathlib import Path

import pandas as pd
import pytest

from saber11.config import get_settings
from saber11.ml import experimento, experimento_shap
from saber11.ml import explain as ex
from saber11.ml import train as tr
from saber11.pipeline import ejecutar_shap

RUN_ML = "20260101T000000Z-aaaabbbb"
RUN_SHAP = "20260101T010000Z-eeeeffff"
PARAMETROS = {
    "efecto_estrato": 2.5, "efecto_privada": 4.0, "efecto_ingles_privada": 5.0,
    "efecto_rural": -4.0, "efecto_anio": 0.8, "efecto_periodo_I": 0.0,
    "efecto_modelo": {"Tradicional": 0.0, "Constructivista": 1.0},
    "efecto_sexo_area": {"Matemáticas": [-1.5, 1.5], "Lectura Crítica": [1.5, -1.5]},
}
# XGBoost minúsculo: basta para ejercitar `TreeExplainer` sin alargar la prueba.
ESPECIFICACIONES_RAPIDAS = {
    "baseline_media": tr.ESPECIFICACIONES["baseline_media"],
    "lasso": tr.ESPECIFICACIONES["lasso"],
    "xgboost": dataclasses.replace(
        tr.ESPECIFICACIONES["xgboost"],
        grid={"modelo__n_estimators": [40], "modelo__max_depth": [2]},
        n_iter=1,
    ),
}


@dataclass
class Corrida:
    raiz: Path
    settings: dict
    resultado: ex.ResultadoSHAP


def _preparar(raiz: Path, settings: dict, marco_ml) -> None:
    gold = raiz / settings["paths"]["gold"]
    gold.mkdir(parents=True, exist_ok=True)
    marco_ml(n_colegios=6, por_grupo=15).to_parquet(gold / "ml_dataset.parquet", index=False)
    parametros = raiz / experimento_shap.RUTA_PARAMETROS
    parametros.parent.mkdir(parents=True, exist_ok=True)
    parametros.write_text(json.dumps(PARAMETROS, ensure_ascii=False), encoding="utf-8")


@pytest.fixture(scope="module")
def corrida(tmp_path_factory, marco_ml, settings_ml_factory) -> Corrida:
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(tr, "ESPECIFICACIONES", ESPECIFICACIONES_RAPIDAS)
        raiz = tmp_path_factory.mktemp("f9")
        settings = settings_ml_factory()
        _preparar(raiz, settings, marco_ml)
        experimento.ejecutar(settings, raiz, RUN_ML)
        yield Corrida(raiz, settings, experimento_shap.ejecutar(settings, raiz, RUN_SHAP, RUN_ML))


# ---------------------------------------------------------------- artefactos
def test_publica_figuras_y_tablas(corrida):
    esperados = {
        "importancia", "beeswarm", "dependencia_estrato", "dependencia_sexo",
        "dependencia_modelo_pedagogico", "waterfall_p10", "waterfall_p50", "waterfall_p90",
        "comparacion", "valores", "recuperacion", "interpretacion",
    }
    assert esperados <= set(corrida.resultado.rutas)
    for clave in esperados:
        ruta = corrida.raiz / corrida.resultado.rutas[clave]
        assert ruta.exists() and ruta.stat().st_size > 0, clave


def test_explica_el_modelo_final_y_uno_de_contraste(corrida):
    r = corrida.resultado
    assert r.modelo_final in r.explicaciones
    assert "xgboost" in r.explicaciones, "debe contrastarse con la otra familia de modelo"
    assert r.explicaciones["xgboost"].familia == "arbol"


def test_se_cumple_la_aditividad_en_ambos_modelos(corrida):
    """Criterio del plan: valor esperado + Σ SHAP ≈ predicción (tolerancia 1e-3)."""
    assert corrida.resultado.aditividad_ok
    for explicacion in corrida.resultado.explicaciones.values():
        assert explicacion.error_aditividad <= ex.TOLERANCIA_ADITIVIDAD


def test_los_valores_shap_no_llevan_identificadores(corrida):
    valores = pd.read_parquet(corrida.raiz / corrida.resultado.rutas["valores"])
    assert "resultado_id" not in valores.columns
    assert set(valores["modelo"]) == set(corrida.resultado.explicaciones)
    assert {"valor_esperado", "prediccion", "shap_estrato"} <= set(valores.columns)


def test_el_informe_incluye_la_advertencia_de_causalidad(corrida):
    informe = (corrida.raiz / corrida.resultado.rutas["interpretacion"]).read_text(encoding="utf-8")
    assert experimento_shap.FRASE_CAUSALIDAD in informe
    assert "datos son ficticios" in informe
    assert "## 5. Prueba de recuperación de efectos sintéticos" in informe


# ---------------------------------------------------------------- prueba de recuperación §17
def test_recupera_los_efectos_del_generador(corrida):
    r = corrida.resultado
    assert r.recuperacion_aprobada
    medidos = r.recuperacion.dropna(subset=["medido"]).set_index("variable")["medido"]
    assert medidos["naturaleza_colegio"] > 0
    assert medidos["zona"] < 0
    assert medidos["estrato"] > 0


def test_sin_parametros_del_generador_se_omite_la_prueba(tmp_path, marco_ml, settings_ml):
    """Con datos reales no hay efectos conocidos: la fase continúa y lo deja dicho."""
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(tr, "ESPECIFICACIONES", ESPECIFICACIONES_RAPIDAS)
        settings = settings_ml
        _preparar(tmp_path, settings, marco_ml)
        (tmp_path / experimento_shap.RUTA_PARAMETROS).unlink()
        experimento.ejecutar(settings, tmp_path, RUN_ML)
        r = experimento_shap.ejecutar(settings, tmp_path, RUN_SHAP, RUN_ML)
    assert r.recuperacion.empty
    assert not r.recuperacion_aprobada
    assert "recuperacion" not in r.rutas
    informe = (tmp_path / r.rutas["interpretacion"]).read_text(encoding="utf-8")
    assert "Con datos reales esta prueba no aplica" in informe


# ---------------------------------------------------------------- etapa previa
def test_shap_exige_una_ejecucion_de_ml(tmp_path):
    assert ejecutar_shap(get_settings(), tmp_path) == 5
