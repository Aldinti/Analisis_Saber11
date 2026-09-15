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

import hashlib
import json
import re
import shutil
import sys
from dataclasses import dataclass, field
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
REPORTE = RAIZ / "powerbi" / "Saber11_Estrategico.Report" / "definition"
MODELO = RAIZ / "powerbi" / "Saber11_Estrategico.SemanticModel" / "definition"
SCHEMA = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition"
ESQUEMA_VISUAL = f"{SCHEMA}/visualContainer/2.12.0/schema.json"
ESQUEMA_PAGINA = f"{SCHEMA}/page/2.1.0/schema.json"
ESQUEMA_PAGINAS = f"{SCHEMA}/pagesMetadata/1.1.0/schema.json"
ANCHO, ALTO = 1920, 1080
M = "_Medidas"


# ---------------------------------------------------------------- campos
@dataclass(frozen=True)
class Campo:
    tabla: str
    nombre: str
    es_medida: bool

    def json(self) -> dict:
        tipo = "Measure" if self.es_medida else "Column"
        return {tipo: {"Expression": {"SourceRef": {"Entity": self.tabla}}, "Property": self.nombre}}

    def proyeccion(self, rol_explorable: bool) -> dict:
        p = {"field": self.json(), "queryRef": f"{self.tabla}.{self.nombre}", "nativeQueryRef": self.nombre}
        if rol_explorable and not self.es_medida:
            p["active"] = True
        return p


def col(tabla: str, nombre: str) -> Campo:
    return Campo(tabla, nombre, False)


def med(nombre: str) -> Campo:
    return Campo(M, nombre, True)


# ---------------------------------------------------------------- visuales
@dataclass
class Visual:
    tipo: str
    roles: dict[str, list[Campo]]
    x: float
    y: float
    ancho: float
    alto: float
    objetos: dict = field(default_factory=dict)
    orden: tuple[Campo, str] | None = None

    def rol_explorable(self, rol: str) -> bool:
        return rol == "Category" or (self.tipo == "slicer" and rol == "Values")

    def json(self, nombre: str, z: int) -> dict:
        consulta: dict = {"queryState": {rol: {"projections": [c.proyeccion(self.rol_explorable(rol)) for c in campos]}
                                         for rol, campos in self.roles.items()}}
        if self.orden:
            campo, direccion = self.orden
            consulta["sortDefinition"] = {"sort": [{"field": campo.json(), "direction": direccion}], "isDefaultSort": True}
        visual = {"visualType": self.tipo, "query": consulta, "drillFilterOtherVisuals": True}
        if self.objetos:
            visual["objects"] = self.objetos
        return {"$schema": ESQUEMA_VISUAL, "name": nombre,
                "position": {"x": self.x, "y": self.y, "z": z, "height": self.alto, "width": self.ancho, "tabOrder": z},
                "visual": visual}


def literal(valor: str) -> dict:
    return {"expr": {"Literal": {"Value": f"'{valor}'"}}}


def tarjeta(campo: Campo, x, y, ancho=300, alto=150) -> Visual:
    return Visual("card", {"Values": [campo]}, x, y, ancho, alto)


def segmentador(campo: Campo, y, modo="Dropdown") -> Visual:
    return Visual("slicer", {"Values": [campo]}, 20, y, 280, 110, {"data": [{"properties": {"mode": literal(modo)}}]})


def barras(categoria: Campo, valores: list[Campo], x, y, ancho, alto, serie: Campo | None = None,
           tipo="clusteredBarChart", orden: tuple[Campo, str] | None = None) -> Visual:
    roles = {"Category": [categoria], "Y": valores}
    if serie:
        roles["Series"] = [serie]
    return Visual(tipo, roles, x, y, ancho, alto, orden=orden)


def tabla(campos: list[Campo], x, y, ancho, alto) -> Visual:
    return Visual("tableEx", {"Values": campos}, x, y, ancho, alto)


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


# ---------------------------------------------------------------- validación contra el modelo
def campos_del_modelo(modelo: Path = MODELO) -> dict[str, dict[str, set[str]]]:
    catalogo: dict[str, dict[str, set[str]]] = {}
    for archivo in (modelo / "tables").glob("*.tmdl"):
        texto = archivo.read_text(encoding="utf-8")
        nombre = re.search(r"^table (.+)$", texto, re.M).group(1).strip().strip("'")
        limpiar = lambda s: s.strip().strip("'")  # noqa: E731
        catalogo[nombre] = {
            "columnas": {limpiar(m) for m in re.findall(r"^\tcolumn ('[^']+'|[^=\s]+)", texto, re.M)},
            "medidas": {limpiar(m) for m in re.findall(r"^\tmeasure ('[^']+'|[^=\s]+)", texto, re.M)},
        }
    return catalogo


def validar(paginas=PAGINAS, catalogo=None) -> list[str]:
    catalogo = catalogo or campos_del_modelo()
    errores = []
    for titulo, visuales in paginas:
        for v in [*panel_comun(), *visuales]:
            for campos in v.roles.values():
                for c in campos:
                    grupo = "medidas" if c.es_medida else "columnas"
                    if c.nombre not in catalogo.get(c.tabla, {}).get(grupo, set()):
                        errores.append(f"{titulo}: {grupo[:-1]} inexistente {c.tabla}[{c.nombre}]")
            if v.x + v.ancho > ANCHO or v.y + v.alto > ALTO:
                errores.append(f"{titulo}: visual {v.tipo} fuera del lienzo")
    return errores


# ---------------------------------------------------------------- escritura
def identificador(*partes: object) -> str:
    return hashlib.md5("|".join(map(str, partes)).encode("utf-8")).hexdigest()[:20]


def tiene_formato_manual(reporte: Path) -> bool:
    return any('"visualContainerObjects"' in v.read_text(encoding="utf-8")
               for v in (reporte / "pages").rglob("visual.json"))


def generar(reporte: Path = REPORTE, forzar: bool = False) -> list[str]:
    if tiene_formato_manual(reporte) and not forzar:
        raise SystemExit("El informe tiene formato hecho en Power BI Desktop; regenerar lo descartaría. "
                         "Use --forzar solo si es intencional.")
    errores = validar()
    if errores:
        raise SystemExit("No se generó el informe:\n- " + "\n- ".join(errores))
    paginas_dir = reporte / "pages"
    orden = []
    staging = reporte / "pages_nuevo"
    shutil.rmtree(staging, ignore_errors=True)
    for titulo, visuales in PAGINAS:
        pid = identificador("pagina", titulo)
        orden.append(pid)
        destino = staging / pid
        (destino / "visuals").mkdir(parents=True)
        (destino / "page.json").write_text(json.dumps({
            "$schema": ESQUEMA_PAGINA, "name": pid, "displayName": titulo,
            "displayOption": "FitToPage", "height": ALTO, "width": ANCHO}, ensure_ascii=False, indent=2), encoding="utf-8")
        for z, visual in enumerate([*panel_comun(), *visuales]):
            vid = identificador("visual", titulo, z)
            (destino / "visuals" / vid).mkdir()
            (destino / "visuals" / vid / "visual.json").write_text(
                json.dumps(visual.json(vid, z), ensure_ascii=False, indent=2), encoding="utf-8")
    (staging / "pages.json").write_text(json.dumps(
        {"$schema": ESQUEMA_PAGINAS, "pageOrder": orden, "activePageName": orden[0]}, ensure_ascii=False, indent=2),
        encoding="utf-8")
    shutil.rmtree(paginas_dir, ignore_errors=True)
    staging.rename(paginas_dir)
    return orden


if __name__ == "__main__":
    ids = generar(forzar="--forzar" in sys.argv)
    print(f"Informe generado: {len(ids)} páginas en {REPORTE.relative_to(RAIZ)}")
    sys.exit(0)
