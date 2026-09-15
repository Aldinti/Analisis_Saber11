"""Pruebas de integración de la capa Gold (F4)."""
from __future__ import annotations

import json
import re
import shutil
from pathlib import Path

import duckdb
import pandas as pd
import pytest

from saber11.config import get_settings, get_source_contract
from saber11.metadata import run_log
from saber11.pipeline import ejecutar_bronze, ejecutar_dq, ejecutar_gold, ejecutar_silver
from saber11.transform.gold import TABLAS_ARCHIVO, TABLAS_GOLD

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "mini_icfes.csv"
CLAVE = "clave-de-prueba-0123456789abcdef0123456789"
SETTINGS = get_settings()
CONTRATO = get_source_contract()


def preparar(raiz: Path, fuente: Path = FIXTURE, gate: bool = True) -> None:
    landing = raiz / SETTINGS["paths"]["landing"]
    landing.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(fuente, landing / SETTINGS["source"]["file_name"])
    assert ejecutar_bronze(SETTINGS, CONTRATO, raiz) == 0
    assert ejecutar_silver(SETTINGS, CONTRATO, raiz, clave_hmac=CLAVE) == 0
    if gate:
        assert ejecutar_dq(SETTINGS, CONTRATO, raiz, "silver") == 0


def seguridad(raiz: Path, filas: str = "rector.xyz@example.org,XYZ\n") -> Path:
    ruta = raiz / "seguridad_prueba.csv"
    ruta.write_text("email_rector,nombre_colegio\n" + filas, encoding="utf-8")
    return ruta


def gold(raiz: Path) -> Path:
    return raiz / SETTINGS["paths"]["gold"]


def leer(raiz: Path, tabla: str) -> pd.DataFrame:
    if tabla == "fact_resultado":
        patron = (gold(raiz) / "fact_resultado" / "**" / "*.parquet").as_posix()
        return duckdb.sql(f"SELECT * FROM read_parquet('{patron}', hive_partitioning = true)").df()
    return duckdb.sql(f"SELECT * FROM '{(gold(raiz) / f'{tabla}.parquet').as_posix()}'").df()


@pytest.fixture()
def proyecto(tmp_path: Path) -> Path:
    preparar(tmp_path)
    assert ejecutar_gold(SETTINGS, CONTRATO, tmp_path, seguridad(tmp_path)) == 0
    return tmp_path


# ---------------------------------------------------------------- gate previo
def test_gold_exige_gate_silver_aprobado(tmp_path):
    preparar(tmp_path, gate=False)
    assert ejecutar_gold(SETTINGS, CONTRATO, tmp_path, seguridad(tmp_path)) == 5
    assert not gold(tmp_path).exists()
    registro = run_log.leer(tmp_path / SETTINGS["paths"]["metadata"] / "run_log.parquet")[-1]
    assert (registro["etapa"], registro["estado"]) == ("gold", "fallido")
    assert json.loads(registro["detalle"])["error"] == "gate_silver_no_aprobado"


def test_silver_regenerado_invalida_el_gate_para_gold(tmp_path):
    preparar(tmp_path)
    assert ejecutar_silver(SETTINGS, CONTRATO, tmp_path, clave_hmac=CLAVE) == 0
    assert ejecutar_gold(SETTINGS, CONTRATO, tmp_path, seguridad(tmp_path)) == 5


# ---------------------------------------------------------------- criterios de aceptación
def test_estructura_y_criterios_de_aceptacion(proyecto):
    silver = duckdb.sql(f"SELECT * FROM '{(proyecto / 'data/silver/silver_resultados.parquet').as_posix()}'").df()
    fact = leer(proyecto, "fact_resultado")

    assert {p.name for p in gold(proyecto).iterdir()} == {f"{t}.parquet" for t in TABLAS_ARCHIVO} | {"fact_resultado"}
    assert len(fact) == len(silver) == 15
    assert len(leer(proyecto, "fact_resultado_area")) == 75 and len(leer(proyecto, "ml_dataset")) == 15
    assert fact["puntaje_global"].mean() == pytest.approx(silver["puntaje_global"].mean())
    assert list(gold(proyecto).glob("fact_resultado/anio=*/periodo=*/*.parquet"))

    en_archivo = duckdb.sql(f"SELECT * FROM read_parquet('{(gold(proyecto) / 'fact_resultado/**/*.parquet').as_posix()}', "
                            "hive_partitioning = false) LIMIT 0").columns
    assert {"anio", "periodo"} <= set(en_archivo)                                       # ADR-0005

    for tabla in TABLAS_GOLD:
        assert "estudiante_pid" not in leer(proyecto, tabla).columns
    assert set(leer(proyecto, "ml_dataset").columns) == {
        "resultado_id", "anio", "periodo", "nombre_colegio", "naturaleza_colegio", "modelo_pedagogico",
        "zona", "sexo", "estrato", "puntaje_global"}


def test_integridad_referencial(proyecto):
    fact, area = leer(proyecto, "fact_resultado"), leer(proyecto, "fact_resultado_area")
    for dim, clave in (("dim_tiempo", "tiempo_id"), ("dim_colegio", "colegio_id"),
                       ("dim_ubicacion", "ubicacion_id"), ("dim_perfil_estudiante", "perfil_id")):
        assert set(fact[clave]) <= set(leer(proyecto, dim)[clave])
    assert set(area["resultado_id"]) == set(fact["resultado_id"])
    assert set(leer(proyecto, "seguridad_rectores")["colegio_id"]) <= set(leer(proyecto, "dim_colegio")["colegio_id"])


def test_gate_gold_aprobado_sobre_gold_publicado(proyecto):
    assert ejecutar_dq(SETTINGS, CONTRATO, proyecto, "gold") == 0


def test_supresion_primaria_y_complementaria(proyecto):
    # Fixture: estratos 1 (n=5), 2 (n=4), 3 (n=6) en el único colegio-año → 2 primaria, 1 complementaria.
    op = leer(proyecto, "agg_operativo_colegio")
    estrato = op[(op["area"] == "Global") & (op["dimension"] == "estrato")].set_index("categoria")
    assert estrato.loc["2", "suprimido"] and estrato.loc["2", "n"] == 4
    assert estrato.loc["1", "suprimido"] and estrato.loc["1", "n"] == 5
    assert not estrato.loc["3", "suprimido"] and estrato.loc["3", "promedio"] > 0
    suprimidas = op[op["suprimido"]]
    assert suprimidas[["promedio", "p10", "p25", "p50", "p75", "p90"]].isna().all().all()
    total = op[(op["area"] == "Global") & (op["dimension"] == "Total")].iloc[0]
    assert total["n"] == 15 and not total["suprimido"]

    # Benchmark: un solo colegio en el fixture → n_colegios < 3 → todo suprimido.
    bench = leer(proyecto, "agg_benchmark_distrito")
    assert bench["suprimido"].all() and bench["promedio"].isna().all()


def test_claves_estables_entre_ejecuciones_y_con_colegios_nuevos(tmp_path, proyecto):
    colegios_antes = leer(proyecto, "dim_colegio").set_index("nombre_colegio")["colegio_id"]
    resultados_antes = set(leer(proyecto, "fact_resultado")["resultado_id"])

    # Segunda carga: mismos 15 registros + un colegio nuevo "AAA" (que ordena antes que XYZ).
    lineas = FIXTURE.read_bytes().decode("cp1252").split("\r\n")
    nuevas = [";".join(["AAA" if i == 7 else ("99" + v if i == 10 else v) for i, v in enumerate(linea.split(";"))])
              for linea in lineas[1:4]]
    fuente = tmp_path / "ampliada.csv"
    fuente.write_bytes("\r\n".join([*lineas[:-1], *nuevas, ""]).encode("cp1252"))
    otro = tmp_path / "otro"
    preparar(otro, fuente)
    assert ejecutar_gold(SETTINGS, CONTRATO, otro, seguridad(otro)) == 0

    colegios_despues = leer(otro, "dim_colegio").set_index("nombre_colegio")["colegio_id"]
    assert colegios_despues["XYZ"] == colegios_antes["XYZ"] and "AAA" in colegios_despues
    assert resultados_antes <= set(leer(otro, "fact_resultado")["resultado_id"])


def test_seguridad_con_colegio_inexistente_no_publica_y_conserva_gold(proyecto):
    antes = leer(proyecto, "dim_colegio")
    mala = seguridad(proyecto, "rector.xyz@example.org,XYZ\nrector.fantasma@example.org,NO_EXISTE\n")
    assert ejecutar_gold(SETTINGS, CONTRATO, proyecto, mala) == 1
    registro = run_log.leer(proyecto / SETTINGS["paths"]["metadata"] / "run_log.parquet")[-1]
    assert registro["estado"] == "fallido" and "DQ-REF-002" in json.loads(registro["detalle"])["mensaje"]
    pd.testing.assert_frame_equal(leer(proyecto, "dim_colegio"), antes)
    assert not [p for p in gold(proyecto).parent.iterdir() if p.name.startswith(".gold_")]


def test_seguridad_con_finales_de_linea_mezclados_y_bom(proyecto):
    # Regresión F7: un CSV editado a mano (CRLF + LF, BOM de Excel) hacía fallar la detección de dialecto de DuckDB.
    ruta = proyecto / "seguridad_mixta.csv"
    contenido = "\ufeffemail_rector,nombre_colegio\r\nrector.xyz@example.org,XYZ\nrector.otro@example.org, XYZ \n\n"
    ruta.write_bytes(contenido.encode("utf-8"))
    assert ejecutar_gold(SETTINGS, CONTRATO, proyecto, ruta) == 0
    seguridad_final = leer(proyecto, "seguridad_rectores")
    assert sorted(seguridad_final["email_rector"]) == ["rector.otro@example.org", "rector.xyz@example.org"]
    assert seguridad_final["colegio_id"].notna().all()


def test_seguridad_sin_columnas_requeridas_no_publica(proyecto):
    ruta = proyecto / "seguridad_mala.csv"
    ruta.write_text("correo,colegio\nrector.xyz@example.org,XYZ\n", encoding="utf-8")
    assert ejecutar_gold(SETTINGS, CONTRATO, proyecto, ruta) == 1


def test_correo_invalido_en_seguridad_no_publica(proyecto):
    assert ejecutar_gold(SETTINGS, CONTRATO, proyecto, seguridad(proyecto, "no-es-correo,XYZ\n")) == 1


def test_diccionario_documenta_columnas_gold(proyecto):
    texto = (Path(__file__).resolve().parents[2] / "docs" / "data_dictionary.md").read_text(encoding="utf-8")
    for tabla in TABLAS_GOLD:
        encabezado = f"### `{tabla}`"
        assert encabezado in texto, f"falta {tabla} en el diccionario"
        seccion = texto.split(encabezado, 1)[1].split("\n### ", 1)[0].split("\n## ", 1)[0]
        documentadas = re.findall(r"^\| `([a-z_0-9]+)` \|", seccion, flags=re.M)
        assert documentadas == list(leer(proyecto, tabla).columns), tabla
