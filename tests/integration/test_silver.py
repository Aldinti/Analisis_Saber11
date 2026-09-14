"""Pruebas de integración de la capa Silver (F3)."""
from __future__ import annotations

import hashlib
import hmac
import json
import re
import shutil
from pathlib import Path

import duckdb
import pandas as pd
import pytest

from saber11.config import get_settings, get_source_contract
from saber11.metadata import run_log
from saber11.pipeline import ejecutar_bronze, ejecutar_silver
from saber11.quality.rules import cargar_reglas, parametros_desde_settings, resolver_sql
from saber11.transform.silver import (
    COLUMNAS_PII,
    COLUMNAS_SILVER,
    VerificacionSilverError,
    construir_silver,
    nombre_silver,
)

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "mini_icfes.csv"
CLAVE = "clave-de-prueba-0123456789abcdef0123456789"
CONTRATO = get_source_contract()
COLUMNAS_FUENTE = [c["name"] for c in CONTRATO["source_contract"]["columns"]]


def pid(doc: int | str, clave: str = CLAVE) -> str:
    return hmac.new(clave.encode(), str(doc).encode(), hashlib.sha256).hexdigest()


def fuente_df() -> pd.DataFrame:
    return pd.read_csv(FIXTURE, sep=";", encoding="cp1252", dtype=str, keep_default_na=False)


def escribir_bronze(df: pd.DataFrame, carpeta: Path) -> Path:
    """Parquet con la forma de Bronze (todo VARCHAR + metadatos), sin pasar por el contrato."""
    carpeta.mkdir(parents=True, exist_ok=True)
    ruta = carpeta / "part-0.parquet"
    datos = df.astype(str).assign(_ingest_id="ingest-prueba", _source_file="fuente.csv",
                                  _source_sha256="f" * 64, _ingested_at=pd.Timestamp("2026-01-01"))
    duckdb.from_df(datos).write_parquet(str(ruta))
    return ruta


def construir(tmp_path: Path, df: pd.DataFrame, clave: str = CLAVE) -> tuple:
    bronze = escribir_bronze(df, tmp_path / "bronze")
    resultado = construir_silver([bronze], COLUMNAS_FUENTE, clave, tmp_path / "silver", tmp_path / "tmp")
    silver = duckdb.sql(f"SELECT * FROM '{resultado.rutas['silver'].as_posix()}'").df()
    rechazos = duckdb.sql(f"SELECT * FROM '{resultado.rutas['rechazos'].as_posix()}'").df()
    return resultado, silver, rechazos


# ---------------------------------------------------------------- nombres
def test_nombres_silver_son_los_del_plan():
    nombres = {nombre_silver(c) for c in COLUMNAS_FUENTE} - set(COLUMNAS_PII)
    esperados = set(COLUMNAS_SILVER) - {"jornada", "estudiante_pid", "flag_atipico",
                                        "flag_inconsistencia_global", "_ingest_id", "_source_sha256"}
    assert nombres == esperados


# ---------------------------------------------------------------- datos correctos
def test_silver_con_datos_limpios(tmp_path):
    df = fuente_df()
    resultado, silver, rechazos = construir(tmp_path, df)

    assert (resultado.filas_bronze, resultado.filas_silver, resultado.filas_rechazo) == (15, 15, 0)
    assert tuple(silver.columns) == COLUMNAS_SILVER
    assert not set(COLUMNAS_PII) & {c.lower() for c in [*silver.columns, *rechazos.columns]}
    assert list(silver["estudiante_pid"]) == [pid(int(d)) for d in df["nroDoc"]]    # orden de la fuente
    assert set(silver["grupo"]) <= {"11-1", "11-2", "11-3"}
    assert (silver["jornada"] == silver["periodo"]).all()
    assert not silver["flag_inconsistencia_global"].any()
    tipos = dict(duckdb.sql(f"SELECT column_name, column_type FROM (DESCRIBE SELECT * FROM "
                            f"'{resultado.rutas['silver'].as_posix()}')").fetchall())
    assert (tipos["anio"], tipos["estrato"], tipos["punt_ingles"]) == ("SMALLINT", "TINYINT", "TINYINT")


def test_mismo_input_misma_clave_mismo_resultado_y_clave_distinta_cambia_pid(tmp_path):
    _, silver_a, _ = construir(tmp_path / "a", fuente_df())
    _, silver_b, _ = construir(tmp_path / "b", fuente_df())
    _, silver_c, _ = construir(tmp_path / "c", fuente_df(), clave=CLAVE + "x")
    pd.testing.assert_frame_equal(silver_a, silver_b)
    assert not set(silver_a["estudiante_pid"]) & set(silver_c["estudiante_pid"])


def test_reglas_del_catalogo_pasan_sobre_silver(tmp_path):
    resultado, _, _ = construir(tmp_path, fuente_df())
    con = duckdb.connect()
    con.execute(f"CREATE VIEW silver_resultados AS SELECT * FROM '{resultado.rutas['silver'].as_posix()}'")
    parametros = parametros_desde_settings(run_id="prueba")
    for regla in cargar_reglas():
        if regla["tabla"] == "silver_resultados" and "sql" in regla and regla["id"] != "DQ-VOL-001":
            valor = con.execute(resolver_sql(regla["sql"], parametros)).fetchone()[0]
            assert float(valor) <= regla["umbral_max_fallos"], f"{regla['id']} falla sobre Silver ({valor})"


# ---------------------------------------------------------------- defectos
def test_limpieza_rechazos_y_flags(tmp_path):
    df = fuente_df()
    base = df.iloc[0].copy()

    def fila(**cambios) -> dict:
        nueva = base.copy()
        for k, v in cambios.items():
            nueva[k] = v
        return nueva.to_dict()

    extra = [
        fila(nroDoc="9001", naturaleza_colegio="publica ", zona="URBANA", municipio="  santa   marta ",
             grupo="11 ° 2", sexo="F", periodo="2"),                                        # 15 canónica
        fila(nroDoc="9001", periodo="II"),                                                  # 16 duplicado de 15
        fila(nroDoc="9002", **{"Matemáticas": "101"}),                                       # 17 fuera de escala
        fila(nroDoc="9003", estrato="x"),                                                   # 18 tipo inválido
        fila(nroDoc="9004", **{"año": "2999"}),                                              # 19 año futuro
        fila(nroDoc="9005", sexo="", estrato=""),                                           # 20 nulos tolerados
        fila(nroDoc="9006", periodo=""),                                                    # 21 jornada 'Unica'
        fila(nroDoc="9007", zona="Selva"),                                                  # 22 categoría inválida
        fila(nroDoc="abc"),                                                                 # 23 documento inválido
        fila(nroDoc="9008", Global="100"),                                                  # 24 global incoherente
        fila(nroDoc="9009", **dict.fromkeys(("Lectura Crítica", "Matemáticas", "Sociales y Ciudadana", "Ciencias Naturales", "Inglés"), "0"), Global="0"),  # 25 atípico
    ]
    df2 = pd.concat([df, pd.DataFrame(extra)], ignore_index=True)
    resultado, silver, rechazos = construir(tmp_path, df2)

    assert resultado.filas_silver + resultado.filas_rechazo == len(df2)
    motivos = dict(zip(rechazos["_fila_fuente"], rechazos["motivo_rechazo"], strict=True))
    assert motivos == {
        17: "duplicado:estudiante_anio_periodo",
        18: "fuera_de_escala:punt_matematicas",
        19: "tipo_invalido:estrato",
        20: "fuera_de_dominio:anio",
        23: "categoria_invalida:zona",
        24: "tipo_invalido:nrodoc",
    }
    assert not set(COLUMNAS_PII) & {c.lower() for c in rechazos.columns}

    por_pid = silver.set_index("estudiante_pid")
    canonica = por_pid.loc[pid(9001)]
    assert (canonica["naturaleza_colegio"], canonica["zona"], canonica["municipio"], canonica["grupo"],
            canonica["sexo"], canonica["periodo"]) == ("Pública", "Urbana", "Santa Marta", "11-2", "Femenino", "II")
    nulos = por_pid.loc[pid(9005)]
    assert pd.isna(nulos["sexo"]) and pd.isna(nulos["estrato"])
    sin_periodo = por_pid.loc[pid(9006)]
    assert pd.isna(sin_periodo["periodo"]) and sin_periodo["jornada"] == "Unica"
    assert bool(por_pid.loc[pid(9008), "flag_inconsistencia_global"])
    assert bool(por_pid.loc[pid(9009), "flag_atipico"])
    assert resultado.motivos["duplicado:estudiante_anio_periodo"] == 1


def test_sin_clave_hmac_no_publica(tmp_path):
    bronze = escribir_bronze(fuente_df(), tmp_path / "bronze")
    with pytest.raises(ValueError):
        construir_silver([bronze], COLUMNAS_FUENTE, "", tmp_path / "silver", tmp_path / "tmp")
    assert not (tmp_path / "silver" / "silver_resultados.parquet").exists()


def test_verificacion_fallida_no_reemplaza_silver_previo(tmp_path, monkeypatch):
    resultado, silver_previo, _ = construir(tmp_path, fuente_df())
    from saber11.transform import silver as modulo
    monkeypatch.setattr(modulo, "COLUMNAS_SILVER", (*modulo.COLUMNAS_SILVER, "columna_inexistente"))
    bronze = escribir_bronze(fuente_df().iloc[:5], tmp_path / "bronze2")
    with pytest.raises(VerificacionSilverError):
        construir_silver([bronze], COLUMNAS_FUENTE, CLAVE, tmp_path / "silver", tmp_path / "tmp")
    actual = duckdb.sql(f"SELECT * FROM '{resultado.rutas['silver'].as_posix()}'").df()
    pd.testing.assert_frame_equal(actual, silver_previo)


# ---------------------------------------------------------------- de punta a punta con la CLI
def test_pipeline_bronze_silver_y_run_log(tmp_path):
    settings = get_settings()
    landing = tmp_path / settings["paths"]["landing"]
    landing.mkdir(parents=True)
    fuente = landing / settings["source"]["file_name"]
    shutil.copyfile(FIXTURE, fuente)

    assert ejecutar_bronze(settings, CONTRATO, tmp_path, fuente) == 0
    assert ejecutar_silver(settings, CONTRATO, tmp_path, clave_hmac=CLAVE) == 0
    registros = run_log.leer(tmp_path / settings["paths"]["metadata"] / "run_log.parquet")
    assert [(r["etapa"], r["estado"]) for r in registros] == [("bronze", "exitoso"), ("silver", "exitoso")]
    detalle = json.loads(registros[-1]["detalle"])
    assert registros[-1]["filas"] == 15 and detalle["ingest_id"] == json.loads(registros[0]["detalle"])["ingest_id"]
    assert (tmp_path / settings["paths"]["silver"] / "silver_resultados.parquet").exists()


def test_pipeline_silver_sin_bronze_registra_fallo(tmp_path):
    settings = get_settings()
    assert ejecutar_silver(settings, CONTRATO, tmp_path, clave_hmac=CLAVE) == 1
    registro = run_log.leer(tmp_path / settings["paths"]["metadata"] / "run_log.parquet")[-1]
    assert (registro["etapa"], registro["estado"]) == ("silver", "fallido")


def test_diccionario_de_datos_documenta_exactamente_las_columnas_silver():
    texto = (Path(__file__).resolve().parents[2] / "docs" / "data_dictionary.md").read_text(encoding="utf-8")
    seccion = texto.split("## Silver — `data/silver/silver_resultados.parquet`", 1)[1].split("\n## ", 1)[0]
    documentadas = tuple(re.findall(r"^\| `([a-z_0-9]+)` \|", seccion, flags=re.M))
    assert documentadas == COLUMNAS_SILVER
