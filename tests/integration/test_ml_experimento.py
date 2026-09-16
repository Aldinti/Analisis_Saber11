"""Experimento completo de F8: artefactos, reproducibilidad y gate previo."""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from saber11.config import get_settings
from saber11.ml import experimento
from saber11.ml import train as tr
from saber11.pipeline import ejecutar_ml

# Subconjunto de modelos: el esquema de validación es el mismo y la prueba se mantiene rápida.
ESPECIFICACIONES_RAPIDAS = {
    n: tr.ESPECIFICACIONES[n] for n in ("baseline_media", "ridge", "lasso")
}


@pytest.fixture()
def proyecto(tmp_path: Path, marco_ml, settings_ml, monkeypatch) -> Path:
    monkeypatch.setattr(tr, "ESPECIFICACIONES", ESPECIFICACIONES_RAPIDAS)
    gold = tmp_path / settings_ml["paths"]["gold"]
    gold.mkdir(parents=True)
    marco_ml(n_colegios=6, por_grupo=15).to_parquet(gold / "ml_dataset.parquet", index=False)
    return tmp_path


def ejecutar(raiz: Path, settings: dict, run_id: str = "20260101T000000Z-aaaabbbb"):
    return experimento.ejecutar(settings, raiz, run_id)


# ---------------------------------------------------------------- artefactos
def test_publica_todos_los_artefactos(proyecto, settings_ml):
    r = ejecutar(proyecto, settings_ml)
    for clave in ("modelo", "params", "metricas", "predicciones", "cv", "informe", "variables"):
        assert (proyecto / r.rutas[clave]).exists(), clave
    metricas = json.loads((proyecto / r.rutas["metricas"]).read_text(encoding="utf-8"))
    assert metricas["seleccionado"] == r.seleccionado
    assert set(metricas["modelos"]) == set(ESPECIFICACIONES_RAPIDAS)
    assert "ficticios" in metricas["advertencia"]


def test_el_informe_documenta_seleccion_y_advertencia(proyecto, settings_ml):
    r = ejecutar(proyecto, settings_ml)
    informe = (proyecto / r.rutas["informe"]).read_text(encoding="utf-8")
    assert "Los datos son ficticios" in informe
    assert "## 5. Modelo seleccionado" in informe
    assert "2024 (evaluación única)" in informe
    catalogo = (proyecto / r.rutas["variables"]).read_text(encoding="utf-8")
    assert "## Excluidas" in catalogo and "`nombre_colegio`" in catalogo


def test_las_predicciones_no_llevan_identificadores(proyecto, settings_ml):
    r = ejecutar(proyecto, settings_ml)
    pred = pd.read_parquet(proyecto / r.rutas["predicciones"])
    assert "resultado_id" not in pred.columns
    assert {"prediccion", "residuo", "puntaje_global"} <= set(pred.columns)
    assert len(pred) == r.filas["prueba"]
    assert pred["residuo"].equals(pred["prediccion"] - pred["puntaje_global"])


# ---------------------------------------------------------------- esquema de validación
def test_el_modelo_supera_al_baseline(proyecto, settings_ml):
    r = ejecutar(proyecto, settings_ml)
    assert r.seleccionado != "baseline_media"
    assert r.supera_baseline
    seleccionado = r.resultados[r.seleccionado].metricas_test
    assert seleccionado["rmse"] < r.resultados["baseline_media"].metricas_test["rmse"]


def test_evalua_colegios_nunca_vistos(proyecto, settings_ml):
    r = ejecutar(proyecto, settings_ml)
    assert r.retenidos["evaluado"]
    assert set(r.retenidos["por_colegio"]) == set(r.retenidos["colegios"])
    assert r.retenidos["n_entrena"] < r.filas["entrena"]


def test_la_prueba_conserva_solo_el_anio_de_prueba(proyecto, settings_ml):
    r = ejecutar(proyecto, settings_ml)
    assert r.filas["entrena"] + r.filas["prueba"] == r.filas["total"]
    assert r.filas["colegios"] == 6


# ---------------------------------------------------------------- reproducibilidad (§22)
def test_dos_ejecuciones_dan_las_mismas_metricas(proyecto, settings_ml):
    primera = ejecutar(proyecto, settings_ml, "20260101T000000Z-aaaabbbb")
    segunda = ejecutar(proyecto, settings_ml, "20260101T000001Z-ccccdddd")
    assert primera.seleccionado == segunda.seleccionado
    for nombre, r in primera.resultados.items():
        assert r.metricas_cv == segunda.resultados[nombre].metricas_cv
        assert r.metricas_test == segunda.resultados[nombre].metricas_test


# ---------------------------------------------------------------- gate previo
def test_ml_exige_gate_de_gold_aprobado(tmp_path):
    """Sin un Gold con quality gate aprobado la etapa se detiene con código 5."""
    assert ejecutar_ml(get_settings(), tmp_path) == 5
