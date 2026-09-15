"""Genera las páginas PBIR del dashboard operativo con RLS (plan §8 F7, §15.6) en powerbi/Saber11_Operativo.Report.

Usa el mismo formato validado en F6 (saber11.bi.pbir). Las visuales solo consumen medidas con salvaguardas de
supresión sobre agregados (sin filas de estudiante); cada campo se valida contra el TMDL del modelo operativo.

Uso (desde la raíz del proyecto, con Power BI Desktop CERRADO):
    python scripts/generar_reporte_operativo.py            # solo si el informe no tiene formato manual
    python scripts/generar_reporte_operativo.py --forzar   # regenera y DESCARTA el formato hecho en Desktop
"""
from __future__ import annotations

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))

from saber11.bi import pbir  # noqa: E402
from saber11.bi.pbir import (  # noqa: E402,F401
    Visual,
    barras,
    col,
    med,
    segmentador,
    tabla,
    tarjeta,
    tiene_formato_manual,
)

REPORTE = RAIZ / "powerbi" / "Saber11_Operativo.Report" / "definition"
MODELO = RAIZ / "powerbi" / "Saber11_Operativo.SemanticModel" / "definition"

ANIO = col("dim_anio", "anio")
CATEGORIA = col("agg_operativo_colegio", "categoria")


# Panel común: rótulo de datos ficticios, identidad evaluada (verificación RLS) y segmentadores.
# El segmentador de colegio solo lista los colegios que el rol permite ver.
def panel_comun() -> list[Visual]:
    return [
        tarjeta(med("Etiqueta Datos Ficticios"), 320, 10, 1080, 70),
        tarjeta(med("Usuario Actual"), 1420, 10, 480, 70),
        segmentador(ANIO, 100, "Basic"),
        segmentador(col("dim_colegio", "nombre_colegio"), 330),
        segmentador(col("dim_area_operativa", "area"), 460),
        segmentador(col("agg_operativo_colegio", "dimension"), 590),
        tarjeta(med("Aviso Sin Colegio"), 20, 720, 280, 150),
    ]


PAGINAS: pbir.Paginas = [
    ("O1 Mi colegio", [
        tarjeta(med("Colegios Visibles"), 320, 100, 460, 140),
        tarjeta(med("Area Mostrada"), 800, 100, 300, 140),
        tarjeta(med("Evaluados Colegio"), 1120, 100, 250, 140),
        tarjeta(med("Promedio Colegio"), 1390, 100, 250, 140),
        tarjeta(med("Promedio Distrito"), 1660, 100, 240, 140),
        tarjeta(med("Brecha vs Distrito"), 320, 260, 460, 140),
        barras(ANIO, [med("Promedio Colegio"), med("Promedio Distrito")], 800, 260, 1100, 800, tipo="lineChart"),
    ]),
    ("O2 Subgrupos", [
        tarjeta(med("Instruccion Subgrupos"), 320, 100, 1580, 90),
        barras(CATEGORIA, [med("Promedio Operativo"), med("Promedio Distrito Categoria")], 320, 210, 900, 850,
               tipo="clusteredColumnChart"),
        tabla([CATEGORIA, med("Evaluados Visible"), med("Promedio Operativo"), med("Promedio Distrito Categoria"),
               med("Etiqueta Supresion")], 1240, 210, 660, 850),
    ]),
    ("O3 Distribución", [
        tarjeta(med("Percentil 10 Colegio"), 320, 100, 300, 140),
        tarjeta(med("Percentil 25 Colegio"), 640, 100, 300, 140),
        tarjeta(med("Mediana Colegio"), 960, 100, 300, 140),
        tarjeta(med("Percentil 75 Colegio"), 1280, 100, 300, 140),
        tarjeta(med("Percentil 90 Colegio"), 1600, 100, 300, 140),
        tabla([ANIO, med("Evaluados Colegio"), med("Percentil 10 Colegio"), med("Percentil 25 Colegio"),
               med("Mediana Colegio"), med("Percentil 75 Colegio"), med("Percentil 90 Colegio"),
               med("Promedio Colegio"), med("Promedio Distrito")], 320, 260, 1580, 800),
    ]),
]


def validar(paginas=PAGINAS, catalogo=None) -> list[str]:
    return pbir.validar(paginas, panel_comun(), catalogo or pbir.campos_del_modelo(MODELO))


def generar(reporte: Path = REPORTE, forzar: bool = False) -> list[str]:
    return pbir.generar(reporte, PAGINAS, panel_comun, validar(), forzar)


if __name__ == "__main__":
    ids = generar(forzar="--forzar" in sys.argv)
    print(f"Informe generado: {len(ids)} páginas en {REPORTE.relative_to(RAIZ)}")
    sys.exit(0)
