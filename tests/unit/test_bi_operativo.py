"""Pruebas del dashboard operativo con RLS (F7): roles, supresión, informe PBIR y control de KPIs."""
from __future__ import annotations

import importlib.util
import json
import re
import shutil
import sys
from pathlib import Path

import pytest

from saber11.config import get_settings

RAIZ = Path(__file__).resolve().parents[2]
MODELO = RAIZ / "powerbi" / "Saber11_Operativo.SemanticModel" / "definition"
REPORTE = RAIZ / "powerbi" / "Saber11_Operativo.Report" / "definition"

spec = importlib.util.spec_from_file_location("generar_reporte_operativo", RAIZ / "scripts" / "generar_reporte_operativo.py")
gen = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = gen
spec.loader.exec_module(gen)


def texto_tmdl(ruta: str) -> str:
    return (MODELO / ruta).read_text(encoding="utf-8")


def medida(nombre: str) -> str:
    texto = texto_tmdl("tables/_Medidas.tmdl")
    m = re.search(rf"^\tmeasure '?{re.escape(nombre)}'? =(.*?)(?=^\t\t(?:formatString|displayFolder|lineageTag|isHidden))",
                  texto, re.M | re.S)
    assert m, f"medida {nombre} no encontrada"
    return m.group(1)


# ---------------------------------------------------------------- modelo y seguridad
def test_modelo_operativo_solo_contiene_agregados():
    tablas = {p.stem for p in (MODELO / "tables").glob("*.tmdl")}
    assert tablas == {"_Medidas", "dim_colegio", "dim_anio", "dim_area_operativa", "agg_operativo_colegio",
                      "agg_benchmark_distrito", "seguridad_rectores"}
    todo = "".join(p.read_text(encoding="utf-8") for p in (MODELO / "tables").glob("*.tmdl"))
    for prohibido in ("fact_resultado", "estudiante_pid", "resultado_id"):
        assert prohibido not in todo


def test_rol_rector_filtra_por_upn_y_rol_direccion_sin_filtro():
    rector = texto_tmdl("roles/Rol_Rector.tmdl")
    assert "tablePermission dim_colegio" in rector and "tablePermission seguridad_rectores" in rector
    assert rector.count("USERPRINCIPALNAME ()") == 2
    assert "ALL" not in rector
    assert "tablePermission" not in texto_tmdl("roles/Rol_Direccion.tmdl")


def test_tablas_sin_relacion_segun_diseno_rls():
    relaciones = texto_tmdl("relationships.tmdl")
    assert "seguridad_rectores" not in relaciones                       # tabla de seguridad desconectada
    for bloque in re.split(r"^relationship ", relaciones, flags=re.M)[1:]:
        if "agg_benchmark_distrito" in bloque:
            assert "dim_colegio" not in bloque                           # el benchmark no se filtra por RLS
        assert "crossFilteringBehavior: bothDirections" not in bloque


def test_k_min_del_modelo_sincronizado_con_settings():
    assert medida("K Min").strip() == str(get_settings()["privacy"]["k_min"])


def test_medidas_publicables_aplican_salvaguardas_de_supresion():
    celda = medida("Promedio Celda")
    for condicion in ("HASONEVALUE ( agg_operativo_colegio[dimension] )", "HASONEVALUE ( agg_operativo_colegio[area] )",
                      "[K Min]", "[Celdas Suprimidas]"):
        assert condicion in celda
    assert "[Celdas Suprimidas]" in medida("Evaluados Visible")
    for nombre in ("Promedio Distrito", "Promedio Distrito Categoria"):
        assert "ALL (" not in medida(nombre) and "NOT agg_benchmark_distrito[suprimido]" in medida(nombre)


# ---------------------------------------------------------------- informe
def test_campos_del_informe_existen_en_el_modelo():
    assert gen.validar() == []


def test_informe_operativo_generado(tmp_path):
    copia = tmp_path / "definition"
    shutil.copytree(REPORTE, copia)
    ids = gen.generar(copia, forzar=True)
    titulos = [json.loads((copia / "pages" / i / "page.json").read_text(encoding="utf-8"))["displayName"] for i in ids]
    assert titulos == ["O1 Mi colegio", "O2 Subgrupos", "O3 Distribución"]
    for pid in ids:
        visuales = [json.loads(v.read_text(encoding="utf-8")) for v in (copia / "pages" / pid / "visuals").glob("*/visual.json")]
        refs = {p["queryRef"] for v in visuales for r in v["visual"]["query"]["queryState"].values() for p in r["projections"]}
        assert {"_Medidas.Etiqueta Datos Ficticios", "_Medidas.Usuario Actual", "_Medidas.Aviso Sin Colegio"} <= refs
        # Solo medidas protegidas: ninguna visual usa columnas numéricas crudas de los agregados.
        assert not refs & {f"agg_operativo_colegio.{c}" for c in ("n", "promedio", "p10", "p25", "p50", "p75", "p90")}
        assert "_Medidas.Evaluados Grupo" not in refs and "_Medidas.Promedio Celda" not in refs
        for v in visuales:
            if v["visual"]["visualType"] == "tableEx":
                assert all("active" not in p for r in v["visual"]["query"]["queryState"].values() for p in r["projections"])


def test_catalogo_dax_operativo_sincronizado():
    from saber11.bi.catalogo_medidas import TABLEROS, generar
    titulo, modelo, destino = TABLEROS["operativo"]
    mensaje = "Regenerar: python -m saber11.bi.catalogo_medidas --tablero operativo"
    assert destino.read_text(encoding="utf-8") == generar(modelo, titulo), mensaje


@pytest.mark.skipif(not (RAIZ / "reports" / "bi" / "validacion_kpis_operativo.md").exists(), reason="sin evidencia")
def test_evidencia_kpis_operativos_aprobada():
    texto = (RAIZ / "reports" / "bi" / "validacion_kpis_operativo.md").read_text(encoding="utf-8")
    assert "**Resultado: APROBADO**" in texto and "❌" not in texto
