"""Desempeño por subgrupo, brechas y alertas (F10; plan §8 F10 y §19)."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from saber11.ml import fairness as fr

OBJETIVO = "puntaje_global"


def predicciones(
    n_colegios: int = 6, por_colegio: int = 60, ruido_masculino: float = 0.0, sesgo: float = 0.0
) -> pd.DataFrame:
    """Predicciones de prueba con error controlado: el sexo masculino puede recibir más ruido."""
    rng = np.random.default_rng(11)
    filas = []
    for i in range(n_colegios):
        for j in range(por_colegio):
            sexo = "Masculino" if j % 2 else "Femenino"
            real = 400.0 + rng.normal(0, 40)
            error = rng.normal(sesgo, 10 + (ruido_masculino if sexo == "Masculino" else 0))
            filas.append({
                "nombre_colegio": f"C{i}",
                "sexo": sexo,
                "zona": "Urbana" if i % 2 else "Rural",
                "estrato": 1 + (j % 6),
                "anio": 2024,
                OBJETIVO: real,
                "prediccion": real + error,
            })
    return pd.DataFrame(filas)


# ---------------------------------------------------------------- etiquetas y unidades
def test_etiquetas_simples_e_interseccionales():
    df = predicciones(n_colegios=2, por_colegio=4)
    assert fr.etiquetas(df, "sexo").iloc[0] == "Femenino"
    assert fr.etiquetas(df, "sexo · zona").iloc[0] == "Femenino · Rural"


def test_etiquetas_exige_columnas_presentes():
    with pytest.raises(KeyError, match="inexistente"):
        fr.etiquetas(predicciones(n_colegios=2, por_colegio=4), "inexistente")


def test_la_dimension_colegio_remuestrea_filas_y_el_resto_colegios():
    """Con la dimensión colegio, remuestrear colegios daría intervalos de ancho cero."""
    assert fr.unidad_remuestreo("nombre_colegio") == "fila"
    assert fr.unidad_remuestreo("nombre_colegio · sexo") == "fila"
    assert fr.unidad_remuestreo("sexo") == "colegio"


# ---------------------------------------------------------------- métricas por subgrupo
def test_reporta_n_y_metricas_por_subgrupo():
    d = fr.evaluar_dimension(predicciones(), "sexo", OBJETIVO, n_muestras=100)
    assert {s.grupo for s in d.subgrupos} == {"Femenino", "Masculino"}
    assert sum(s.n for s in d.subgrupos) == 360
    for s in d.subgrupos:
        assert s.rmse > 0 and s.mae > 0 and not np.isnan(s.sd_real)
        assert s.ic_rmse[0] <= s.rmse <= s.ic_rmse[1]


def test_marca_no_concluyentes_los_grupos_pequenos():
    df = predicciones()
    df.loc[df.index[:5], "sexo"] = "No informado"
    d = fr.evaluar_dimension(df, "sexo", OBJETIVO, n_min=30, n_muestras=100)
    pequeno = next(s for s in d.subgrupos if s.grupo == "No informado")
    assert pequeno.n == 5
    assert not pequeno.concluyente
    assert all(s.concluyente for s in d.subgrupos if s.grupo != "No informado")


def test_los_no_concluyentes_no_entran_en_la_brecha():
    df = predicciones()
    df.loc[df.index[:5], "sexo"] = "No informado"
    df.loc[df.index[:5], "prediccion"] += 300  # error enorme en el grupo diminuto
    d = fr.evaluar_dimension(df, "sexo", OBJETIVO, n_min=30, n_muestras=100)
    assert d.brecha < 10, "un grupo de 5 filas no puede dominar la brecha"


def test_una_sola_categoria_no_es_evaluable():
    d = fr.evaluar_dimension(predicciones(), "anio", OBJETIVO, n_muestras=50)
    assert not d.evaluable
    assert "un solo valor" in d.motivo_no_evaluable
    assert d.brecha is None


def test_sin_dos_grupos_concluyentes_no_hay_brecha():
    df = predicciones(n_colegios=2, por_colegio=40)
    df.loc[df.index[:5], "sexo"] = "No informado"
    d = fr.evaluar_dimension(df, "sexo", OBJETIVO, n_min=200, n_muestras=50)
    assert not d.evaluable
    assert "menos de dos subgrupos" in d.motivo_no_evaluable


# ---------------------------------------------------------------- brechas y alertas
def test_detecta_la_brecha_cuando_un_grupo_tiene_mas_error():
    d = fr.evaluar_dimension(
        predicciones(ruido_masculino=25.0), "sexo", OBJETIVO,
        rmse_global=20.0, umbral=0.10, n_muestras=200,
    )
    peor = max(d.subgrupos, key=lambda s: s.rmse)
    assert peor.grupo == "Masculino"
    assert d.brecha > 2.0
    assert d.alerta
    assert d.ic_brecha[0] < d.brecha < d.ic_brecha[1]


def test_sin_diferencias_no_hay_alerta():
    d = fr.evaluar_dimension(
        predicciones(), "sexo", OBJETIVO, rmse_global=20.0, umbral=0.10, n_muestras=200
    )
    assert not d.alerta


# ---------------------------------------------------------------- sesgo global y propio
def test_el_sesgo_global_se_detecta_y_no_se_atribuye_a_los_grupos():
    """Un desvío que afecta a todo el modelo no debe leerse como sesgo de cada grupo."""
    df = predicciones(sesgo=8.0)
    valor, ic = fr.sesgo_global(df, OBJETIVO, n_muestras=200)
    assert valor == pytest.approx(8.0, abs=1.5)
    assert ic[0] > 0
    d = fr.evaluar_dimension(df, "sexo", OBJETIVO, n_muestras=200)
    assert all(s.sesgo_significativo for s in d.subgrupos), "todos comparten el desvío global"
    assert not any(s.sesgo_especifico for s in d.subgrupos), "ninguno se aparta del global"


def test_detecta_un_sesgo_propio_de_un_grupo():
    df = predicciones()
    df.loc[df["sexo"] == "Masculino", "prediccion"] += 25
    d = fr.evaluar_dimension(df, "sexo", OBJETIVO, n_muestras=200)
    masculino = next(s for s in d.subgrupos if s.grupo == "Masculino")
    assert masculino.sesgo_especifico
    assert masculino.sesgo_medio > 20


# ---------------------------------------------------------------- dispersión
def test_la_correlacion_con_la_dispersion_explica_la_brecha():
    """Si el error sigue a la dispersión del resultado, la brecha no es un problema del modelo."""
    rng = np.random.default_rng(3)
    filas = []
    for grupo, dispersion in (("A", 10.0), ("B", 40.0), ("C", 70.0)):
        for i in range(120):
            real = 400 + rng.normal(0, dispersion)
            filas.append({"nombre_colegio": f"C{i % 4}", "grupo_test": grupo,
                          OBJETIVO: real, "prediccion": real + rng.normal(0, dispersion / 2)})
    d = fr.evaluar_dimension(pd.DataFrame(filas), "grupo_test", OBJETIVO, n_muestras=100)
    assert d.correlacion_rmse_dispersion > 0.9


# ---------------------------------------------------------------- evaluación completa
def test_evaluar_omite_las_dimensiones_ausentes():
    dimensiones = fr.evaluar(predicciones(), OBJETIVO, n_muestras=50)
    nombres = [d.nombre for d in dimensiones]
    assert "sexo" in nombres and "nombre_colegio" in nombres
    assert "modelo_pedagogico" not in nombres, "no está en el conjunto de prueba"
    assert "sexo · estrato" in nombres


def test_la_tabla_de_resultados_lleva_n_y_marcas():
    resultado = fr.ResultadoSesgos(
        run_id="r", run_id_ml="m", modelo="lasso", metricas_globales={"rmse": 20.0},
        dimensiones=fr.evaluar(predicciones(), OBJETIVO, n_muestras=50),
        n_min=30, umbral_brecha=0.1, filas=360,
    )
    tabla = resultado.tabla()
    assert {"dimension", "grupo", "n", "rmse", "sd_real", "concluyente"} <= set(tabla.columns)
    assert (tabla["n"] > 0).all()
