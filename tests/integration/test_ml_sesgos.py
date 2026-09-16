"""Ejecución completa de F10: informe de sesgos, tabla de subgrupos y figura."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd
import pytest

from saber11.config import get_settings
from saber11.ml import experimento, experimento_sesgos
from saber11.ml import fairness as fr
from saber11.ml import train as tr
from saber11.pipeline import ejecutar_fairness

RUN_ML = "20260101T000000Z-aaaabbbb"
RUN_SESGOS = "20260101T020000Z-99998888"
ESPECIFICACIONES_RAPIDAS = {
    n: tr.ESPECIFICACIONES[n] for n in ("baseline_media", "lasso")
}


@dataclass
class Corrida:
    raiz: Path
    settings: dict
    resultado: fr.ResultadoSesgos


@pytest.fixture(scope="module")
def corrida(tmp_path_factory, marco_ml, settings_ml_factory) -> Corrida:
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(tr, "ESPECIFICACIONES", ESPECIFICACIONES_RAPIDAS)
        raiz = tmp_path_factory.mktemp("f10")
        settings = settings_ml_factory()
        gold = raiz / settings["paths"]["gold"]
        gold.mkdir(parents=True)
        marco_ml(n_colegios=6, por_grupo=20).to_parquet(gold / "ml_dataset.parquet", index=False)
        experimento.ejecutar(settings, raiz, RUN_ML)
        yield Corrida(raiz, settings, experimento_sesgos.ejecutar(settings, raiz, RUN_SESGOS, RUN_ML))


# ---------------------------------------------------------------- artefactos
def test_publica_tabla_informe_y_figura(corrida):
    for clave in ("subgrupos", "informe", "brechas"):
        ruta = corrida.raiz / corrida.resultado.rutas[clave]
        assert ruta.exists() and ruta.stat().st_size > 0, clave


def test_la_tabla_reporta_cada_subgrupo_con_su_n(corrida):
    tabla = pd.read_csv(corrida.raiz / corrida.resultado.rutas["subgrupos"])
    assert {"dimension", "grupo", "n", "rmse", "mae", "sesgo_medio", "sd_real",
            "rmse_ic_inferior", "rmse_ic_superior", "concluyente"} <= set(tabla.columns)
    assert (tabla["n"] > 0).all()
    # Cada dimensión evaluable cubre todas las filas del conjunto de prueba.
    por_dimension = tabla.groupby("dimension")["n"].sum()
    evaluables = [d.nombre for d in corrida.resultado.dimensiones if d.evaluable]
    assert (por_dimension[evaluables] == corrida.resultado.filas).all()


def test_el_informe_explica_como_se_lee_una_brecha(corrida):
    informe = (corrida.raiz / corrida.resultado.rutas["informe"]).read_text(encoding="utf-8")
    assert "funciona peor" in informe
    assert "datos son ficticios" in informe
    assert "## 3. Sesgo sistemático" in informe
    assert "Sesgo global del modelo" in informe


# ---------------------------------------------------------------- contenido del análisis
def test_evalua_las_dimensiones_del_plan(corrida):
    nombres = [d.nombre for d in corrida.resultado.dimensiones]
    for esperada in ("sexo", "estrato", "zona", "naturaleza_colegio", "modelo_pedagogico",
                     "nombre_colegio", "naturaleza_colegio · zona", "sexo · estrato"):
        assert esperada in nombres, esperada


def test_el_anio_no_es_evaluable_con_un_solo_ano_de_prueba(corrida):
    anio = next(d for d in corrida.resultado.dimensiones if d.nombre == "anio")
    assert not anio.evaluable
    assert "un solo valor" in anio.motivo_no_evaluable


def test_las_brechas_llevan_intervalo(corrida):
    for d in corrida.resultado.dimensiones:
        if d.evaluable and d.brecha is not None:
            assert d.ic_brecha is not None
            assert d.ic_brecha[0] <= d.ic_brecha[1]


def test_la_alerta_usa_el_umbral_configurado(corrida):
    limite = corrida.resultado.umbral_brecha * corrida.resultado.metricas_globales["rmse"]
    for d in corrida.resultado.dimensiones:
        if d.evaluable and d.brecha is not None:
            assert d.alerta == (d.brecha > limite)


# ---------------------------------------------------------------- etapa previa
def test_fairness_exige_una_ejecucion_de_ml(tmp_path):
    assert ejecutar_fairness(get_settings(), tmp_path) == 5


def test_sin_predicciones_falla_con_mensaje_util(tmp_path, settings_ml):
    (tmp_path / settings_ml["paths"]["models"] / RUN_ML).mkdir(parents=True)
    with pytest.raises(experimento_sesgos.ErrorSesgos, match="run --stage ml"):
        experimento_sesgos.ejecutar(settings_ml, tmp_path, RUN_SESGOS, RUN_ML)
