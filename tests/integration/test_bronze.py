"""Pruebas de integración de la capa Bronze (F2) sobre un proyecto temporal."""
from __future__ import annotations

import json
import shutil
from pathlib import Path

import duckdb
import pandas as pd
import pytest

from saber11.config import get_settings, get_source_contract
from saber11.ingest.bronze import sha256_archivo
from saber11.metadata import run_log
from saber11.pipeline import ejecutar_bronze

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "mini_icfes.csv"


@pytest.fixture()
def proyecto(tmp_path: Path) -> dict:
    settings, contrato = get_settings(), get_source_contract()
    landing = tmp_path / settings["paths"]["landing"]
    landing.mkdir(parents=True)
    fuente = landing / settings["source"]["file_name"]
    shutil.copyfile(FIXTURE, fuente)
    return {"raiz": tmp_path, "settings": settings, "contrato": contrato, "fuente": fuente,
            "dataset": tmp_path / settings["paths"]["bronze"] / settings["lakehouse"]["bronze_table"],
            "run_log": tmp_path / settings["paths"]["metadata"] / "run_log.parquet"}


def correr(p: dict) -> int:
    return ejecutar_bronze(p["settings"], p["contrato"], p["raiz"], p["fuente"])


def leer_bronze(dataset: Path) -> pd.DataFrame:
    return duckdb.sql(
        f"SELECT * FROM read_parquet('{dataset.as_posix()}/*/*.parquet', hive_partitioning=true)"
    ).df()


def test_ingesta_preserva_la_fuente(proyecto):
    assert correr(proyecto) == 0
    sha = sha256_archivo(proyecto["fuente"])

    raw = proyecto["raiz"] / "data" / "bronze" / "raw" / f"{sha}.csv"
    assert raw.exists() and sha256_archivo(raw) == sha

    df = leer_bronze(proyecto["dataset"])
    original = pd.read_csv(FIXTURE, sep=";", encoding="cp1252", dtype=str, keep_default_na=False)
    assert len(df) == len(original)
    assert list(df.columns[:23]) == list(original.columns)
    assert {"_ingest_id", "_source_file", "_source_sha256", "_ingested_at", "ingest_id"} <= set(df.columns)
    assert df[list(original.columns)].reset_index(drop=True).equals(original)   # valores idénticos como texto
    assert (df["_source_sha256"] == sha).all() and (df["_ingest_id"] == df["ingest_id"]).all()

    tipos = duckdb.sql(f"DESCRIBE SELECT * FROM read_parquet('{proyecto['dataset'].as_posix()}/*/*.parquet')").df()
    assert set(tipos.loc[tipos["column_name"].isin(original.columns), "column_type"]) == {"VARCHAR"}
    assert not list(proyecto["dataset"].glob(".staging_*"))


def test_reingesta_del_mismo_archivo_no_duplica(proyecto):
    assert correr(proyecto) == 0
    assert correr(proyecto) == 0
    assert len(leer_bronze(proyecto["dataset"])) == 15
    assert len(list(proyecto["dataset"].glob("ingest_id=*"))) == 1
    estados = [r["estado"] for r in run_log.leer(proyecto["run_log"])]
    assert estados == ["exitoso", "omitido"]


def test_archivo_modificado_genera_nueva_ingesta(proyecto):
    assert correr(proyecto) == 0
    datos = proyecto["fuente"].read_bytes()
    proyecto["fuente"].write_bytes(datos + datos.split(b"\r\n")[1] + b"\r\n")
    assert correr(proyecto) == 0
    assert len(list(proyecto["dataset"].glob("ingest_id=*"))) == 2
    assert len(leer_bronze(proyecto["dataset"])) == 15 + 16
    assert len(list((proyecto["raiz"] / "data" / "bronze" / "raw").glob("*.csv"))) == 2


def test_contrato_incumplido_no_escribe_bronze_y_registra_fallo(proyecto):
    lineas = proyecto["fuente"].read_bytes().decode("cp1252").replace(";", ",")
    proyecto["fuente"].write_bytes(lineas.encode("cp1252"))
    assert correr(proyecto) == 2
    assert not proyecto["dataset"].exists() or not list(proyecto["dataset"].glob("ingest_id=*"))
    registro = run_log.leer(proyecto["run_log"])[-1]
    assert (registro["etapa"], registro["estado"]) == ("bronze", "fallido")
    assert json.loads(registro["detalle"])["error"] == "contrato"
    assert list((proyecto["raiz"] / "reports" / "quality").glob("source_check_*.json"))


def test_run_log_cumple_columnas_de_dq_vol_001(proyecto):
    assert correr(proyecto) == 0
    registro = run_log.leer(proyecto["run_log"])[0]
    assert {"run_id", "etapa", "estado", "filas", "finalizado_utc"} <= set(registro)
    assert registro["filas"] == 15 and registro["source_sha256"] == sha256_archivo(proyecto["fuente"])


def test_logs_y_run_log_sin_pii(proyecto, capsys):
    assert correr(proyecto) == 0
    salida = capsys.readouterr().out
    contenido_log = duckdb.sql(f"SELECT * FROM read_parquet('{proyecto['run_log'].as_posix()}')").df().to_string()
    for marcador in ("NombreL", "ApellidoN"):
        assert marcador not in salida and marcador not in contenido_log
