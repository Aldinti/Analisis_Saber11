"""Selección de variables y separación temporal del conjunto de modelado (F8; §16.2, §18)."""
from __future__ import annotations

import numpy as np
import pytest

from saber11.ml import dataset as ds


# ---------------------------------------------------------------- selección de variables
def test_excluye_objetivo_grupo_e_identificadores(marco_ml, settings_ml):
    v = ds.seleccionar_variables(marco_ml(), settings_ml)
    assert v.excluidas["puntaje_global"] == ds.MOTIVOS["objetivo"]
    assert v.excluidas["nombre_colegio"] == ds.MOTIVOS["agrupamiento"]
    assert v.excluidas["resultado_id"] == ds.MOTIVOS["identificador"]
    assert set(v.predictoras).isdisjoint({"puntaje_global", "nombre_colegio", "resultado_id"})


@pytest.mark.parametrize("columna", ["punt_matematicas", "nivel_desempeno", "flag_atipico", "pct_area"])
def test_excluye_columnas_con_fuga(marco_ml, settings_ml, columna):
    df = marco_ml()
    df[columna] = 1.0
    assert ds.seleccionar_variables(df, settings_ml).excluidas[columna] == ds.MOTIVOS["fuga"]


def test_excluye_pseudonimo_y_cuasi_identificador(marco_ml, settings_ml):
    df = marco_ml()
    df["estudiante_pid"] = [f"{i:064x}" for i in range(len(df))]
    df["grupo"] = "11-1"
    v = ds.seleccionar_variables(df, settings_ml)
    assert v.excluidas["estudiante_pid"] == ds.MOTIVOS["identificador"]
    assert v.excluidas["grupo"] == ds.MOTIVOS["cuasi_identificador"]


def test_excluye_columnas_constantes(marco_ml, settings_ml):
    df = marco_ml()
    df["municipio"] = "Santa Marta"
    assert ds.seleccionar_variables(df, settings_ml).excluidas["municipio"] == ds.MOTIVOS["varianza_cero"]


def test_excluye_categorica_confundida_con_el_colegio(marco_ml, settings_ml):
    """H3: si cada categoría pertenece a un solo colegio, su efecto no es separable."""
    df = marco_ml()
    df["lema_colegio"] = df["nombre_colegio"] + " lema"
    v = ds.seleccionar_variables(df, settings_ml)
    assert v.excluidas["lema_colegio"] == ds.MOTIVOS["confundida"]
    assert "naturaleza_colegio" in v.categoricas  # la comparten dos colegios: se conserva


def test_clasifica_numericas_y_categoricas(marco_ml, settings_ml):
    v = ds.seleccionar_variables(marco_ml(), settings_ml)
    assert set(v.numericas) == {"anio", "estrato"}
    assert set(v.categoricas) == {"periodo", "naturaleza_colegio", "modelo_pedagogico", "zona", "sexo"}


def test_falta_columna_objetivo(marco_ml, settings_ml):
    with pytest.raises(ds.ErrorConjuntoML, match="puntaje_global"):
        ds.seleccionar_variables(marco_ml().drop(columns=["puntaje_global"]), settings_ml)


# ---------------------------------------------------------------- dependencias funcionales
def test_detecta_alias_entre_categoricas(marco_ml):
    df = marco_ml()
    df["periodo"] = np.where(df["naturaleza_colegio"] == "Privada", "I", "II")
    dependencias = dict(ds.dependencias_funcionales(df, ["periodo", "naturaleza_colegio", "sexo"]))
    assert dependencias["periodo"] == ("naturaleza_colegio",)
    assert "sexo" not in dependencias


def test_alias_de_segundo_orden(marco_ml):
    """El caso del diseño real: `periodo` = naturaleza × zona, no de ninguna de las dos sola."""
    df = marco_ml()
    df["periodo"] = np.where(
        (df["naturaleza_colegio"] == "Privada") == (df["zona"] == "Urbana"), "I", "II"
    )
    dependencias = dict(ds.dependencias_funcionales(df, ["periodo", "naturaleza_colegio", "zona"]))
    assert set(dependencias["periodo"]) == {"naturaleza_colegio", "zona"}


# ---------------------------------------------------------------- separación temporal
def test_separacion_temporal_deja_anios_disjuntos(marco_ml):
    df = marco_ml()
    entrena, prueba = ds.separar_temporal(df, 2024)
    assert entrena["anio"].max() < prueba["anio"].min()
    assert set(prueba["anio"]) == {2024}
    assert len(entrena) + len(prueba) == len(df)


def test_separacion_temporal_sin_datos_de_prueba(marco_ml):
    with pytest.raises(ds.ErrorConjuntoML, match="conjunto vacío"):
        ds.separar_temporal(marco_ml(anios=(2021, 2022)), 2024)


# ---------------------------------------------------------------- colegios retenidos
def test_colegios_retenidos_desde_configuracion(marco_ml, settings_ml):
    settings_ml["ml"]["colegios_retenidos"] = ["C1", "C2"]
    assert ds.colegios_retenidos(marco_ml(), settings_ml) == ["C1", "C2"]


def test_colegios_retenidos_fallback_uno_por_naturaleza(marco_ml, settings_ml):
    settings_ml["ml"]["colegios_retenidos"] = ["NO_EXISTE"]
    assert ds.colegios_retenidos(marco_ml(), settings_ml) == ["C0", "C1"]


def test_cargar_sin_gold(tmp_path, settings_ml):
    with pytest.raises(ds.ErrorConjuntoML, match="run --stage gold"):
        ds.cargar(settings_ml, tmp_path)
