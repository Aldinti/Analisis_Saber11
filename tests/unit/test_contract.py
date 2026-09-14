"""Pruebas del contrato de fuente (F2)."""
from __future__ import annotations

from pathlib import Path

import pytest

from saber11.config import get_source_contract
from saber11.ingest.contract import validar_fuente

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "mini_icfes.csv"


@pytest.fixture(scope="module")
def contrato() -> dict:
    return get_source_contract()


def lineas_fixture() -> list[str]:
    return FIXTURE.read_bytes().decode("cp1252").split("\r\n")


def escribir(tmp_path: Path, lineas: list[str], encoding: str = "cp1252") -> Path:
    ruta = tmp_path / "fuente.csv"
    ruta.write_bytes("\r\n".join(lineas).encode(encoding))
    return ruta


def test_fixture_cumple_contrato(contrato):
    r = validar_fuente(FIXTURE, contrato)
    assert r.aprobado, r.errores
    assert (r.columnas, r.filas_datos) == (23, 15)


def test_archivo_inexistente(tmp_path, contrato):
    r = validar_fuente(tmp_path / "no_existe.csv", contrato)
    assert not r.aprobado and "archivo" in r.errores_por_tipo


def test_separador_incorrecto(tmp_path, contrato):
    r = validar_fuente(escribir(tmp_path, [linea.replace(";", ",") for linea in lineas_fixture()]), contrato)
    assert not r.aprobado and "separador" in r.errores_por_tipo


def test_utf8_rechazado_cuando_el_contrato_exige_cp1252(tmp_path, contrato):
    r = validar_fuente(escribir(tmp_path, lineas_fixture(), encoding="utf-8"), contrato)
    assert not r.aprobado and "encoding" in r.errores_por_tipo


def test_bytes_no_decodificables(tmp_path, contrato):
    ruta = escribir(tmp_path, lineas_fixture())
    ruta.write_bytes(ruta.read_bytes() + b"\x81\x8d")  # indefinidos en cp1252
    r = validar_fuente(ruta, contrato)
    assert not r.aprobado and "encoding" in r.errores_por_tipo


@pytest.mark.parametrize("cambio", ["faltante", "orden"])
def test_cabecera_distinta(tmp_path, contrato, cambio):
    lineas = lineas_fixture()
    columnas = lineas[0].split(";")
    columnas = columnas[:-1] if cambio == "faltante" else [columnas[1], columnas[0], *columnas[2:]]
    r = validar_fuente(escribir(tmp_path, [";".join(columnas), *lineas[1:]]), contrato)
    assert not r.aprobado and "cabecera" in r.errores_por_tipo


def test_errores_por_fila_sin_exponer_valores(tmp_path, contrato):
    lineas = lineas_fixture()
    campos = lineas[1].split(";")
    lineas[1] = ";".join(campos[:-1])                          # campo faltante
    campos2 = lineas[2].split(";")
    campos2[0] = "21"                                          # año sin 4 dígitos
    campos2[7] = " "                                           # nombre_colegio obligatorio vacío
    lineas[2] = ";".join(campos2)
    r = validar_fuente(escribir(tmp_path, lineas), contrato)
    assert not r.aprobado
    assert r.errores_por_tipo == {"campos": 1, "anio": 1, "obligatorio_vacio": 1}
    texto = " ".join(r.errores)
    assert "Nombre" not in texto and "Apellido" not in texto
