"""La documentación exigida por el plan existe y no apunta a ninguna parte (F14; §28).

Los enlaces rotos y los documentos prometidos que nunca se escriben son la forma habitual en
que la documentación deja de ser fiable. Comprobarlo cuesta menos que revisarlo a mano.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from saber11.config import PROJECT_ROOT
from saber11.transform.gold import TABLAS_GOLD

ENLACE = re.compile(r"\[[^\]]+\]\(([^)\s]+)\)")
# Rutas que no se versionan: existen en una máquina con datos, no en un clon limpio.
PREFIJOS_NO_VERSIONADOS = ("data/", "models/", "data\\", "models\\")
DOCUMENTOS_DEL_PLAN = (
    "README.md",
    "docs/PLAN_MAESTRO.md",
    "docs/data_dictionary.md",
    "docs/data_classification.md",
    "docs/lineage.md",
    "docs/operacion.md",
    "docs/pruebas.md",
    "docs/seguridad.md",
    "docs/manual_tecnico.md",
    "docs/manual_usuario.md",
    "docs/bi/medidas_dax.md",
    "docs/bi/medidas_dax_operativo.md",
    "docs/ml/variables_modelo.md",
    "reports/informe_final.md",
)


def markdowns() -> list[Path]:
    rutas = [PROJECT_ROOT / "README.md"]
    rutas += sorted((PROJECT_ROOT / "docs").rglob("*.md"))
    rutas += sorted((PROJECT_ROOT / "reports").rglob("*.md"))
    return [r for r in rutas if r.is_file()]


@pytest.mark.parametrize("documento", DOCUMENTOS_DEL_PLAN)
def test_existe_la_documentacion_exigida_por_el_plan(documento):
    assert (PROJECT_ROOT / documento).is_file()


def test_hay_al_menos_una_decision_registrada():
    assert list((PROJECT_ROOT / "docs" / "adr").glob("*.md"))


def test_ningun_enlace_relativo_de_la_documentacion_esta_roto():
    rotos = []
    for documento in markdowns():
        for destino in ENLACE.findall(documento.read_text(encoding="utf-8", errors="ignore")):
            if destino.startswith(("http://", "https://", "#", "mailto:")):
                continue
            ruta = destino.split("#", 1)[0]
            if not ruta or ruta.startswith(PREFIJOS_NO_VERSIONADOS):
                continue
            if not (documento.parent / ruta).exists():
                rotos.append(f"{documento.relative_to(PROJECT_ROOT).as_posix()} → {destino}")
    assert rotos == []


def test_el_linaje_cubre_todas_las_tablas_gold():
    """Si se añade una tabla a Gold, el documento de linaje debe decir de dónde sale."""
    texto = (PROJECT_ROOT / "docs" / "lineage.md").read_text(encoding="utf-8")
    faltantes = [t for t in TABLAS_GOLD if t not in texto]
    assert faltantes == []


@pytest.mark.parametrize("documento", ("docs/manual_usuario.md", "reports/informe_final.md"))
def test_los_documentos_para_leer_advierten_que_los_datos_son_ficticios(documento):
    """§4 S7: quien lea cifras sin contexto debe encontrar la advertencia antes que las cifras."""
    texto = (PROJECT_ROOT / documento).read_text(encoding="utf-8")
    assert "ficticio" in texto.lower()
    assert texto.lower().index("ficticio") < len(texto) // 2, (
        "la advertencia debe ir al principio, no enterrada al final"
    )
