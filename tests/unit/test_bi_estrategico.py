"""Pruebas del dashboard estratégico (F6): informe PBIR, catálogo DAX y control de KPIs."""
from __future__ import annotations

import importlib.util
import json
import shutil
import sys
from pathlib import Path

import pytest

from saber11.bi.catalogo_medidas import DESTINO, generar
from saber11.bi.kpi_control import comparar

RAIZ = Path(__file__).resolve().parents[2]
REPORTE = RAIZ / "powerbi" / "Saber11_Estrategico.Report" / "definition"

spec = importlib.util.spec_from_file_location("generar_reporte_estrategico", RAIZ / "scripts" / "generar_reporte_estrategico.py")
gen = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = gen
spec.loader.exec_module(gen)


def test_campos_del_informe_existen_en_el_modelo():
    assert gen.validar() == []


def test_validacion_detecta_campo_inexistente():
    paginas = [("Prueba", [gen.tarjeta(gen.med("Medida Que No Existe"), 320, 100)])]
    assert any("Medida Que No Existe" in e for e in gen.validar(paginas))


def test_informe_tiene_las_5_paginas_del_plan_con_segmentadores_y_rotulo(tmp_path):
    copia = tmp_path / "definition"
    shutil.copytree(REPORTE, copia)
    ids = gen.generar(copia, forzar=True)
    paginas = json.loads((copia / "pages" / "pages.json").read_text(encoding="utf-8"))
    assert paginas["pageOrder"] == ids and len(ids) == 5
    titulos = [json.loads((copia / "pages" / i / "page.json").read_text(encoding="utf-8"))["displayName"] for i in ids]
    assert titulos == ["P1 Resumen", "P2 Áreas", "P3 Tendencias", "P4 Benchmarking", "P5 Distribución"]
    for pid in ids:
        visuales = [json.loads(v.read_text(encoding="utf-8")) for v in (copia / "pages" / pid / "visuals").glob("*/visual.json")]
        segmentados = {p["queryRef"] for v in visuales if v["visual"]["visualType"] == "slicer"
                       for p in v["visual"]["query"]["queryState"]["Values"]["projections"]}
        assert segmentados == {"dim_tiempo.anio", "dim_colegio.nombre_colegio", "dim_perfil_estudiante.estrato",
                               "dim_perfil_estudiante.sexo", "dim_area.area"}
        rotulos = [v for v in visuales if any(p["queryRef"] == "_Medidas.Etiqueta Datos Ficticios"
                                              for r in v["visual"]["query"]["queryState"].values() for p in r["projections"])]
        assert len(rotulos) == 1
        assert all(v["$schema"].endswith("visualContainer/2.12.0/schema.json") for v in visuales)
        for v in visuales:
            for rol, contenido in v["visual"]["query"]["queryState"].items():
                explorable = rol == "Category" or (v["visual"]["visualType"] == "slicer" and rol == "Values")
                if not explorable:
                    assert all("active" not in p for p in contenido["projections"]), (v["visual"]["visualType"], rol)


def test_tablas_del_informe_publicado_sin_active():
    # Regresión: "active" en tableEx rompe la representación al filtrar por colegio (P4, P5).
    for archivo in REPORTE.rglob("visual.json"):
        visual = json.loads(archivo.read_text(encoding="utf-8"))["visual"]
        if visual["visualType"] == "tableEx":
            assert all("active" not in p for r in visual["query"]["queryState"].values() for p in r["projections"])


def test_no_regenera_sobre_formato_manual(tmp_path):
    copia = tmp_path / "definition"
    shutil.copytree(REPORTE, copia)
    if not gen.tiene_formato_manual(copia):
        pytest.skip("el informe no tiene formato manual")
    with pytest.raises(SystemExit):
        gen.generar(copia)


def test_generacion_es_determinista(tmp_path):
    a, b = tmp_path / "a", tmp_path / "b"
    shutil.copytree(REPORTE, a)
    shutil.copytree(REPORTE, b)
    gen.generar(a, forzar=True)
    gen.generar(b, forzar=True)
    archivos = sorted(p.relative_to(a) for p in (a / "pages").rglob("*.json"))
    assert archivos == sorted(p.relative_to(b) for p in (b / "pages").rglob("*.json"))
    assert all((a / f).read_bytes() == (b / f).read_bytes() for f in archivos)


def test_catalogo_dax_sincronizado_con_el_modelo():
    assert DESTINO.read_text(encoding="utf-8") == generar(), "Regenerar: python -m saber11.bi.catalogo_medidas"


def test_comparacion_de_kpis_con_tolerancia():
    esperados = [("Todos", "Promedio Global", 400.0), ("Todos", "Evaluados", 10.0)]
    filas = comparar(esperados, {("Todos", "Promedio Global"): 400.005, ("Todos", "Evaluados"): 11.0})
    assert [f["cumple"] for f in filas] == [True, False]
    assert comparar(esperados[:1], {})[0]["cumple"] is False


@pytest.mark.skipif(not (RAIZ / "reports" / "bi" / "validacion_kpis_estrategico.md").exists(), reason="sin evidencia")
def test_evidencia_de_validacion_aprobada():
    texto = (RAIZ / "reports" / "bi" / "validacion_kpis_estrategico.md").read_text(encoding="utf-8")
    assert "**Resultado: APROBADO**" in texto and "❌" not in texto
