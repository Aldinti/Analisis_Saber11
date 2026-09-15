"""Genera las 5 páginas PBIR del dashboard estratégico (plan §8 F6) en powerbi/Saber11_Estrategico.Report.

El formato JSON (visualContainer 2.12.0, page 2.1.0, roles y referencias a campos) se tomó de visuales
creadas en Power BI Desktop 2.157 sobre este mismo informe. Antes de escribir, cada campo y medida se
valida contra el modelo TMDL guardado; si alguno no existe, no se escribe nada.

Uso (desde la raíz del proyecto, con Power BI Desktop CERRADO):
    python scripts/generar_reporte_estrategico.py            # solo si el informe no tiene formato manual
    python scripts/generar_reporte_estrategico.py --forzar   # regenera y DESCARTA el formato hecho en Desktop

"active": true solo se escribe en roles con jerarquía de exploración (Category de gráficos y Values de
segmentadores), como hace Desktop. En tablas (tableEx) provoca el error de representación
"Cannot read properties of undefined (reading 'isMeasure')" al filtrar.
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

REPORTE = RAIZ / "powerbi" / "Saber11_Estrategico.Report" / "definition"
MODELO = RAIZ / "powerbi" / "Saber11_Estrategico.SemanticModel" / "definition"


# Panel común: rótulo de datos ficticios y los 5 segmentadores del plan (año, colegio, estrato, sexo, área).
def panel_comun() -> list[Visual]:
    return [
        tarjeta(med("Etiqueta Datos Ficticios"), 320, 10, 1580, 70),
        segmentador(col("dim_tiempo", "anio"), 100, "Basic"),
        segmentador(col("dim_colegio", "nombre_colegio"), 330),
        segmentador(col("dim_perfil_estudiante", "estrato"), 460),
        segmentador(col("dim_perfil_estudiante", "sexo"), 590),
        segmentador(col("dim_area", "area"), 720),
    ]


COLEGIO = col("dim_colegio", "nombre_colegio")
AREA = col("dim_area", "area")
ANIO = col("dim_tiempo", "anio")

PAGINAS: list[tuple[str, list[Visual]]] = [
    ("P1 Resumen", [
        tarjeta(med("Promedio Global"), 320, 100),
        tarjeta(med("Evaluados"), 640, 100),
        tarjeta(med("Variacion Interanual"), 960, 100),
        tarjeta(med("Pct Estudiantes >= P75 Distrital"), 1280, 100),
        tarjeta(med("Promedio Distrito"), 1600, 100),
        barras(COLEGIO, [med("Promedio Global")], 320, 270, 790, 790, orden=(med("Promedio Global"), "Descending")),
        barras(ANIO, [med("Promedio Global")], 1130, 270, 770, 380, tipo="lineChart"),
        barras(col("dim_colegio", "naturaleza_colegio"), [med("Promedio Global")], 1130, 670, 770, 390,
               tipo="clusteredColumnChart"),
    ]),
    ("P2 Áreas", [
        barras(AREA, [med("Promedio Area")], 320, 100, 780, 470, serie=col("dim_perfil_estudiante", "sexo")),
        barras(AREA, [med("Promedio Area")], 1120, 100, 780, 470, serie=col("dim_perfil_estudiante", "estrato")),
        barras(COLEGIO, [med("Promedio Area")], 320, 590, 1580, 470, serie=AREA, tipo="clusteredColumnChart"),
    ]),
    ("P3 Tendencias", [
        barras(ANIO, [med("Promedio Global"), med("Promedio Distrito")], 320, 100, 1580, 470, tipo="lineChart"),
        barras(ANIO, [med("Promedio Area")], 320, 590, 1580, 470, serie=AREA, tipo="lineChart"),
    ]),
    ("P4 Benchmarking", [
        tarjeta(med("Diferencial Sector"), 320, 100, 380, 130),
        tarjeta(med("Aviso Benchmark Sector"), 720, 100, 580, 130),
        tarjeta(med("Diferencial Zona"), 1320, 100, 280, 130),
        tarjeta(med("Aviso Benchmark Zona"), 1620, 100, 280, 130),
        tabla([COLEGIO, med("Evaluados"), med("Promedio Global"), med("Promedio Distrito"), med("Brecha vs Distrito")],
              320, 250, 780, 810),
        barras(col("dim_colegio", "modelo_pedagogico"), [med("Promedio Global")], 1120, 250, 780, 260),
        barras(col("dim_perfil_estudiante", "estrato"), [med("Promedio Global")], 1120, 525, 780, 260,
               tipo="clusteredColumnChart"),
        barras(col("dim_perfil_estudiante", "sexo"), [med("Promedio Global")], 1120, 800, 780, 260),
    ]),
    ("P5 Distribución", [
        barras(col("fact_resultado", "rango_global"), [med("Evaluados")], 320, 100, 1580, 470,
               tipo="clusteredColumnChart", orden=(col("fact_resultado", "rango_global"), "Ascending")),
        tabla([COLEGIO, med("Evaluados"), med("Percentil 25 Global"), med("Mediana Global"),
               med("Percentil 75 Colegio"), med("Promedio Global"), med("Desviacion Estandar Global")],
              320, 590, 1580, 470),
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
