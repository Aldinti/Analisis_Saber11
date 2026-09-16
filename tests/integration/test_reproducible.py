"""Reproducibilidad de las capas publicadas (plan §22, fila «Reproducibilidad»).

Dos ejecuciones sobre el mismo origen deben dejar **el mismo contenido** en Silver y Gold.
Se compara un hash del contenido y no del archivo: el Parquet puede diferir byte a byte por
metadatos de escritura sin que los datos cambien, y lo que importa es el dato.
"""
from __future__ import annotations

from pathlib import Path

import duckdb
import pytest

from saber11.config import get_settings, get_source_contract
from saber11.pipeline import ejecutar_bronze, ejecutar_dq, ejecutar_gold, ejecutar_silver
from saber11.transform.gold import TABLA_PARTICIONADA, TABLAS_ARCHIVO

CLAVE = "clave-de-prueba-0123456789abcdef0123456789"
SETTINGS = get_settings()
CONTRATO = get_source_contract()


def hash_contenido(ruta: Path, patron_hive: bool = False) -> str:
    """Hash del contenido completo, independiente del orden físico de las filas."""
    origen = (
        f"read_parquet('{ruta.as_posix()}', hive_partitioning = true)" if patron_hive
        else f"read_parquet('{ruta.as_posix()}')"
    )
    con = duckdb.connect()
    try:
        return con.execute(
            f"SELECT md5(string_agg(fila, '\n' ORDER BY fila)) FROM "
            f"(SELECT t::VARCHAR AS fila FROM {origen} t)"
        ).fetchone()[0]
    finally:
        con.close()


def hashes(raiz: Path) -> dict[str, str]:
    gold = raiz / SETTINGS["paths"]["gold"]
    valores = {
        "silver": hash_contenido(raiz / SETTINGS["paths"]["silver"] / "silver_resultados.parquet"),
        TABLA_PARTICIONADA: hash_contenido(
            gold / TABLA_PARTICIONADA / "**" / "*.parquet", patron_hive=True
        ),
    }
    for tabla in TABLAS_ARCHIVO:
        archivo = gold / f"{tabla}.parquet"
        if archivo.exists():
            valores[tabla] = hash_contenido(archivo)
    return valores


def construir(raiz: Path) -> None:
    """Una pasada completa por las capas que producen datos."""
    assert ejecutar_bronze(SETTINGS, CONTRATO, raiz) == 0
    assert ejecutar_silver(SETTINGS, CONTRATO, raiz, clave_hmac=CLAVE) == 0
    assert ejecutar_dq(SETTINGS, CONTRATO, raiz, "silver") == 0
    assert ejecutar_gold(SETTINGS, CONTRATO, raiz) == 0


@pytest.fixture(scope="module")
def dos_ejecuciones(tmp_path_factory, csv_fuente) -> tuple[dict[str, str], dict[str, str]]:
    raiz = tmp_path_factory.mktemp("reproducible")
    landing = raiz / SETTINGS["paths"]["landing"]
    landing.mkdir(parents=True)
    csv_fuente(landing / SETTINGS["source"]["file_name"], n_colegios=4, anios=(2023, 2024), por_grupo=20)
    seguridad = raiz / SETTINGS["security"]["example_file"]
    seguridad.parent.mkdir(parents=True, exist_ok=True)
    seguridad.write_text(
        "email_rector,nombre_colegio\n" + "".join(f"rector.c{i:02d}@example.org,C{i:02d}\n" for i in range(4)),
        encoding="utf-8",
    )
    construir(raiz)
    primera = hashes(raiz)
    construir(raiz)
    return primera, hashes(raiz)


def test_silver_y_gold_tienen_el_mismo_contenido_en_las_dos_ejecuciones(dos_ejecuciones):
    primera, segunda = dos_ejecuciones
    distintas = [t for t in primera if primera[t] != segunda[t]]
    assert distintas == [], f"el contenido cambió entre ejecuciones en: {distintas}"


def test_se_comparan_todas_las_tablas_publicadas(dos_ejecuciones):
    """La prueba pierde valor si deja tablas fuera: se verifica que las cubre todas."""
    primera, _ = dos_ejecuciones
    assert set(primera) == {"silver", TABLA_PARTICIONADA, *TABLAS_ARCHIVO}


def test_las_claves_sustitutas_no_se_desplazan(dos_ejecuciones):
    """ADR-0017: las claves derivan del valor natural, no del orden de llegada."""
    primera, segunda = dos_ejecuciones
    assert primera["dim_colegio"] == segunda["dim_colegio"]
    assert primera[TABLA_PARTICIONADA] == segunda[TABLA_PARTICIONADA]
