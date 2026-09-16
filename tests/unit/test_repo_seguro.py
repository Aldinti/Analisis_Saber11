"""Controles de seguridad sobre lo que el repositorio publica (F13; plan §21).

El criterio de aceptación de F13 —«escaneo del repo sin PII ni secretos»— se ejecuta aquí
para que no dependa de que alguien se acuerde de mirarlo. Todo se comprueba sobre los
archivos **versionados** (`git ls-files`): lo que no está en git no se distribuye.
"""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

import pytest

from saber11.config import PROJECT_ROOT

EXTENSIONES_PROHIBIDAS = {".parquet", ".joblib", ".bin", ".onnx", ".pbix", ".key", ".pem", ".abf"}
CSV_PERMITIDOS = {"config/", "reports/", "tests/fixtures/"}
CARPETAS_PROHIBIDAS = ("data/", "models/")
ENTRADAS_GITIGNORE = (
    "data/", ".env", "*.pbix", "models/", "config/seguridad_rectores.csv",
    "powerbi/**/.pbi/cache.abf",
)
# Identidades que produce el generador de F1b: cualquier otra cosa sería un dato real.
PATRON_NOMBRE_FICTICIO = re.compile(r"^(Nombre[LM]|Apellido[NO])\d+$")


@pytest.fixture(scope="module")
def versionados() -> list[str]:
    try:
        salida = subprocess.run(["git", "-C", str(PROJECT_ROOT), "ls-files"],
                                capture_output=True, text=True, timeout=30, check=True)
    except (OSError, subprocess.SubprocessError):  # pragma: no cover - entorno sin git
        pytest.skip("el proyecto no está en un repositorio git")
    return [linea for linea in salida.stdout.splitlines() if linea]


def contenido(ruta: str) -> str:
    return (PROJECT_ROOT / ruta).read_text(encoding="utf-8", errors="ignore")


# ---------------------------------------------------------------- qué se versiona
def test_no_se_versionan_datos_ni_binarios_de_modelo(versionados):
    prohibidos = [r for r in versionados if Path(r).suffix.lower() in EXTENSIONES_PROHIBIDAS]
    assert prohibidos == []


def test_no_se_versiona_ninguna_carpeta_de_datos(versionados):
    dentro = [r for r in versionados if r.startswith(CARPETAS_PROHIBIDAS)]
    assert dentro == []


def test_no_se_versiona_el_archivo_de_entorno(versionados):
    assert [r for r in versionados if Path(r).name == ".env"] == []
    assert ".env.example" in versionados, "la plantilla sí debe estar, para poder reproducir"


def test_los_csv_versionados_son_configuracion_evidencia_o_fixture(versionados):
    """Ningún CSV de datos debe colarse: solo configuración, evidencia de BI/ML y fixtures."""
    csv = [r for r in versionados if r.endswith(".csv")]
    inesperados = [r for r in csv if not r.startswith(tuple(CSV_PERMITIDOS))]
    assert inesperados == []


def test_el_gitignore_cubre_lo_sensible():
    lineas = {linea.strip() for linea in contenido(".gitignore").splitlines()}
    assert [e for e in ENTRADAS_GITIGNORE if e not in lineas] == []


# ---------------------------------------------------------------- secretos
def test_la_clave_hmac_no_esta_en_ningun_archivo_versionado(versionados):
    ruta_env = PROJECT_ROOT / ".env"
    if not ruta_env.exists():
        pytest.skip("no hay .env local con el que contrastar")
    clave = ""
    for linea in ruta_env.read_text(encoding="utf-8", errors="ignore").splitlines():
        if linea.startswith("SABER11_HMAC_KEY="):
            clave = linea.split("=", 1)[1].strip()
    if len(clave) < 16:
        pytest.skip("la clave local está vacía o es demasiado corta para buscarla")
    filtrados = [r for r in versionados if Path(r).suffix in {".py", ".md", ".json", ".csv", ".yaml", ".toml", ".ps1"}
                 and clave in contenido(r)]
    assert filtrados == []


def test_la_plantilla_de_entorno_no_trae_la_clave_rellenada():
    for linea in contenido(".env.example").splitlines():
        if linea.startswith("SABER11_HMAC_KEY="):
            assert linea.split("=", 1)[1].strip() in {"", '""'}, (
                "`.env.example` debe quedar con el valor vacío: es una plantilla, no un secreto"
            )


# ---------------------------------------------------------------- PII
def test_el_fixture_solo_contiene_identidades_ficticias():
    """Guarda contra regenerar el fixture desde datos reales (§4, supuesto S6)."""
    lineas = contenido("tests/fixtures/mini_icfes.csv").splitlines()
    cabecera = lineas[0].split(";")
    indices = [cabecera.index(c) for c in ("nombre1", "nombre2", "apellido1", "apellido2")]
    reales = [
        campo
        for linea in lineas[1:]
        for campo in (linea.split(";")[i] for i in indices)
        if not PATRON_NOMBRE_FICTICIO.match(campo)
    ]
    assert reales == [], "el fixture lleva nombres que no produce el generador de datos ficticios"


def test_los_cuadernos_no_guardan_salidas(versionados):
    """§21.11: un cuaderno con salidas puede llevar filas de datos dentro del repositorio."""
    with_salidas = []
    for ruta in (r for r in versionados if r.endswith(".ipynb")):
        celdas = json.loads(contenido(ruta)).get("cells", [])
        if any(celda.get("outputs") for celda in celdas):
            with_salidas.append(ruta)
    assert with_salidas == []


# ---------------------------------------------------------------- zona restringida
def test_la_copia_original_de_bronze_es_de_solo_lectura():
    """La inmutabilidad de Bronze es la garantía de poder reconstruir cualquier capa."""
    raw = PROJECT_ROOT / "data" / "bronze" / "raw"
    if not raw.exists():
        pytest.skip("no hay Bronze publicado en esta máquina")
    archivos = list(raw.glob("*.csv"))
    assert archivos, "Bronze existe pero no conserva el CSV original"
    escribibles = [a.name for a in archivos if a.stat().st_mode & 0o200]
    assert escribibles == [], f"la copia inmutable admite escritura: {escribibles}"
