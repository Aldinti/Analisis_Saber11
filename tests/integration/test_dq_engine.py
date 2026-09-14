"""Pruebas del motor de reglas y del quality gate (F5b)."""
from __future__ import annotations

import json
import shutil
from pathlib import Path

import duckdb
import pytest

from saber11.config import get_settings, get_source_contract
from saber11.metadata import run_log
from saber11.pipeline import ejecutar_bronze, ejecutar_dq, ejecutar_silver
from saber11.quality.engine import (
    CapaNoDisponibleError,
    ejecutar_gate,
    evaluar_regla,
    gate_aprobado,
    reglas_de_capa,
)
from saber11.quality.rules import cargar_reglas

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "mini_icfes.csv"
CLAVE = "clave-de-prueba-0123456789abcdef0123456789"
SETTINGS = get_settings()
CONTRATO = get_source_contract()
IDS_SILVER = {"DQ-INT-001", "DQ-INT-002", "DQ-COM-001", "DQ-COM-002", "DQ-UNI-001", "DQ-VAL-001", "DQ-VAL-002",
              "DQ-VAL-003", "DQ-VAL-004", "DQ-VAL-005", "DQ-CON-001", "DQ-CON-002", "DQ-EXA-001", "DQ-PRI-001",
              "DQ-VOL-001"}


@pytest.fixture()
def proyecto(tmp_path: Path) -> Path:
    landing = tmp_path / SETTINGS["paths"]["landing"]
    landing.mkdir(parents=True)
    shutil.copyfile(FIXTURE, landing / SETTINGS["source"]["file_name"])
    assert ejecutar_bronze(SETTINGS, CONTRATO, tmp_path) == 0
    assert ejecutar_silver(SETTINGS, CONTRATO, tmp_path, clave_hmac=CLAVE) == 0
    return tmp_path


def ruta_silver(raiz: Path) -> Path:
    return raiz / SETTINGS["paths"]["silver"] / "silver_resultados.parquet"


def reescribir_silver(raiz: Path, sql_select: str) -> None:
    """Reemplaza Silver por el resultado de una consulta sobre el Silver actual (inyección de defectos)."""
    ruta = ruta_silver(raiz)
    tmp = ruta.with_name("modificado.parquet")
    duckdb.sql(f"COPY ({sql_select.format(silver=f"'{ruta.as_posix()}'")}) TO '{tmp.as_posix()}' (FORMAT parquet)")
    tmp.replace(ruta)


def resultados_por_id(gate) -> dict:
    return {r.regla_id: r for r in gate.resultados}


def gate_silver(raiz: Path):
    return ejecutar_gate("silver", SETTINGS, CONTRATO, raiz, run_log.nuevo_run_id(), run_log.ahora_utc())


# ---------------------------------------------------------------- selección
def test_reglas_por_capa_cubren_todo_el_catalogo():
    reglas = cargar_reglas()
    silver = {r["id"] for r in reglas_de_capa(reglas, "silver")}
    gold = {r["id"] for r in reglas_de_capa(reglas, "gold")}
    assert silver == IDS_SILVER
    assert gold == {"DQ-REF-001", "DQ-REF-002", "DQ-PRI-001", "DQ-PRI-002", "DQ-PRI-003"}
    assert silver | gold == {r["id"] for r in reglas}


# ---------------------------------------------------------------- gate aprobado
def test_gate_silver_aprobado_persiste_resultados_informe_y_run_log(proyecto):
    assert ejecutar_dq(SETTINGS, CONTRATO, proyecto, "silver") == 0

    registros = run_log.leer(proyecto / SETTINGS["paths"]["metadata"] / "run_log.parquet")
    silver_run, dq_run = registros[-2], registros[-1]
    assert (dq_run["etapa"], dq_run["estado"]) == ("dq_silver", "exitoso")
    detalle = json.loads(dq_run["detalle"])
    assert detalle["aprobado"] and detalle["run_id_evaluado"] == silver_run["run_id"] and detalle["score_dq"] == 1.0
    assert gate_aprobado(proyecto / SETTINGS["paths"]["metadata"] / "run_log.parquet", "silver", silver_run["run_id"])

    resultados = duckdb.sql(
        f"SELECT regla_id, estado FROM '{(proyecto / 'data/metadata/dq_results.parquet').as_posix()}'").fetchall()
    assert {r[0] for r in resultados} == IDS_SILVER and {r[1] for r in resultados} == {"PASA"}

    informe = (proyecto / detalle["informe"]).read_text(encoding="utf-8")
    assert "Gate: APROBADO" in informe and "Score DQ" in informe and "Aprobación por dimensión" in informe
    for marcador in ("NombreL", "ApellidoN"):
        assert marcador not in informe


def test_gate_de_silver_nuevo_requiere_nueva_evaluacion(proyecto):
    ruta_log = proyecto / SETTINGS["paths"]["metadata"] / "run_log.parquet"
    assert ejecutar_dq(SETTINGS, CONTRATO, proyecto, "silver") == 0
    assert ejecutar_silver(SETTINGS, CONTRATO, proyecto, clave_hmac=CLAVE) == 0
    nuevo_silver = run_log.leer(ruta_log)[-1]["run_id"]
    assert not gate_aprobado(ruta_log, "silver", nuevo_silver)


# ---------------------------------------------------------------- gate rechazado
@pytest.mark.parametrize("defecto, regla", [
    ("SELECT * REPLACE (CAST(600 AS SMALLINT) AS puntaje_global) FROM {silver}", "DQ-VAL-003"),
    ("SELECT *, 'x' AS nroDoc FROM {silver}", "DQ-PRI-001"),
    ("SELECT * FROM {silver} UNION ALL SELECT * FROM {silver} LIMIT 20", "DQ-UNI-001"),
    ("SELECT * FROM {silver} LIMIT 10", "DQ-INT-002"),
    ("SELECT * REPLACE (CAST(anio + 20 AS SMALLINT) AS anio) FROM {silver}", "DQ-VAL-001"),
])
def test_defecto_bloqueante_rechaza_gate(proyecto, defecto, regla):
    reescribir_silver(proyecto, defecto)
    gate = gate_silver(proyecto)
    assert not gate.aprobado
    assert resultados_por_id(gate)[regla].estado == "FALLA"
    assert regla in gate.resumen()["bloqueantes_fallidas"]


def test_cli_devuelve_4_y_registra_fallido_si_el_gate_rechaza(proyecto):
    reescribir_silver(proyecto, "SELECT * REPLACE (CAST(600 AS SMALLINT) AS puntaje_global) FROM {silver}")
    assert ejecutar_dq(SETTINGS, CONTRATO, proyecto, "silver") == 4
    ruta_log = proyecto / SETTINGS["paths"]["metadata"] / "run_log.parquet"
    registro = run_log.leer(ruta_log)[-1]
    assert (registro["etapa"], registro["estado"]) == ("dq_silver", "fallido")
    silver_run = [r for r in run_log.leer(ruta_log) if r["etapa"] == "silver"][-1]["run_id"]
    assert not gate_aprobado(ruta_log, "silver", silver_run)
    informe = (proyecto / json.loads(registro["detalle"])["informe"]).read_text(encoding="utf-8")
    assert "Gate: RECHAZADO" in informe and "DQ-VAL-003" in informe


def test_advertencia_no_rechaza_gate(proyecto):
    reescribir_silver(proyecto, "SELECT * REPLACE (CAST(puntaje_global + 1 AS SMALLINT) AS puntaje_global) FROM {silver}")
    gate = gate_silver(proyecto)
    assert gate.aprobado
    assert resultados_por_id(gate)["DQ-EXA-001"].estado == "FALLA"
    assert gate.resumen()["advertencias"] == ["DQ-EXA-001"] and gate.score < 1


def test_error_de_evaluacion_en_regla_bloqueante_rechaza(proyecto):
    reescribir_silver(proyecto, "SELECT * EXCLUDE (zona) FROM {silver}")
    gate = gate_silver(proyecto)
    val_004 = resultados_por_id(gate)["DQ-VAL-004"]
    assert val_004.estado == "ERROR" and "zona" in val_004.mensaje and not gate.aprobado


def test_regla_sin_sql_ni_evaluador_es_error():
    regla = {"id": "DQ-VAL-999", "dimension": "validez", "tabla": "silver_resultados",
             "severidad": "bloqueante", "umbral_max_fallos": 0}
    resultado = evaluar_regla(duckdb.connect(), regla, CONTRATO, {"tablas": set()}, {})
    assert resultado.estado == "ERROR" and resultado.bloquea


def test_vol_001_compara_contra_la_carga_silver_anterior(proyecto):
    # Segunda carga con 5 filas menos: la variación frente a la carga previa (15 filas) es 5/15.
    fuente = proyecto / SETTINGS["paths"]["landing"] / SETTINGS["source"]["file_name"]
    lineas = fuente.read_bytes().split(b"\r\n")
    fuente.write_bytes(b"\r\n".join(lineas[:-6] + [b""]))
    assert ejecutar_bronze(SETTINGS, CONTRATO, proyecto) == 0
    assert ejecutar_silver(SETTINGS, CONTRATO, proyecto, clave_hmac=CLAVE) == 0
    vol = resultados_por_id(gate_silver(proyecto))["DQ-VOL-001"]
    assert vol.valor == pytest.approx(5 / 15) and vol.estado == "FALLA" and vol.severidad == "advertencia"


# ---------------------------------------------------------------- capas no disponibles
def test_sin_silver_no_se_puede_evaluar(tmp_path):
    with pytest.raises(CapaNoDisponibleError):
        gate_silver(tmp_path)
    assert ejecutar_dq(SETTINGS, CONTRATO, tmp_path, "silver") == 1


def test_gate_gold_sin_tablas_gold(proyecto):
    with pytest.raises(CapaNoDisponibleError):
        ejecutar_gate("gold", SETTINGS, CONTRATO, proyecto, run_log.nuevo_run_id(), run_log.ahora_utc())


def escribir_gold_minimo(raiz: Path, huerfano: bool = False) -> None:
    """Tablas Gold mínimas con los esquemas del plan (§14, §15.6); F4 producirá las reales."""
    gold = raiz / SETTINGS["paths"]["gold"]
    (gold / "fact_resultado" / "anio=2023" / "periodo=II").mkdir(parents=True)
    con = duckdb.connect()
    colegio_fact = 99 if huerfano else 1
    tablas = {
        "dim_tiempo": "SELECT 20232 AS tiempo_id, 2023 AS anio, 'II' AS periodo",
        "dim_colegio": "SELECT 1 AS colegio_id, 'ABC' AS nombre_colegio",
        "dim_ubicacion": "SELECT 1 AS ubicacion_id",
        "dim_perfil_estudiante": "SELECT 1 AS perfil_id",
        "dim_area": "SELECT 1 AS area_id, 'Matemáticas' AS area",
        "fact_resultado_area": "SELECT 10 AS resultado_id, 1 AS area_id, 70 AS puntaje",
        "seguridad_rectores": "SELECT 'rector.abc@example.org' AS email_rector, 1 AS colegio_id",
        "agg_operativo_colegio": """SELECT * FROM (VALUES
            (1, 2023, 'Global', 'Total', 'Total', 40, 380.0, 330.0, 350.0, 380.0, 410.0, 430.0, false),
            (1, 2023, 'Global', 'sexo', 'Femenino', 20, 381.0, 331.0, 351.0, 381.0, 411.0, 431.0, false),
            (1, 2023, 'Global', 'sexo', 'Masculino', 20, 379.0, 329.0, 349.0, 379.0, 409.0, 429.0, false)
            ) t(colegio_id, anio, area, dimension, categoria, n, promedio, p10, p25, p50, p75, p90, suprimido)""",
        "agg_benchmark_distrito": """SELECT 2023 AS anio, 'Global' AS area, 'Total' AS dimension, 'Total' AS categoria,
            40 AS n, 16 AS n_colegios, 385.0 AS promedio, 350.0 AS p25, 385.0 AS p50, 420.0 AS p75, false AS suprimido""",
    }
    for nombre, sql in tablas.items():
        con.execute(f"COPY ({sql}) TO '{(gold / f'{nombre}.parquet').as_posix()}' (FORMAT parquet)")
    con.execute(f"COPY (SELECT 10 AS resultado_id, 20232 AS tiempo_id, {colegio_fact} AS colegio_id, 1 AS ubicacion_id, "
                f"1 AS perfil_id) TO '{(gold / 'fact_resultado/anio=2023/periodo=II/part-0.parquet').as_posix()}' (FORMAT parquet)")
    con.close()


@pytest.mark.parametrize("huerfano, aprobado", [(False, True), (True, False)])
def test_gate_gold_con_tablas_gold(proyecto, huerfano, aprobado):
    escribir_gold_minimo(proyecto, huerfano)
    gate = ejecutar_gate("gold", SETTINGS, CONTRATO, proyecto, run_log.nuevo_run_id(), run_log.ahora_utc())
    estados = {r.regla_id: r.estado for r in gate.resultados}
    assert set(estados) == {"DQ-REF-001", "DQ-REF-002", "DQ-PRI-001", "DQ-PRI-002", "DQ-PRI-003"}
    assert gate.aprobado is aprobado
    assert estados["DQ-REF-001"] == ("FALLA" if huerfano else "PASA")
