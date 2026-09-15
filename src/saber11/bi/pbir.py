"""Construcción de páginas PBIR (Power BI Project, formato de informe mejorado) validadas contra el modelo TMDL.

El formato JSON se fijó con visuales creadas en Power BI Desktop 2.157 (agosto 2026): visualContainer 2.12.0,
page 2.1.0, pagesMetadata 1.1.0. Reglas aprendidas en F6:

* "active": true solo en roles con jerarquía de exploración (Category de gráficos, Values de segmentadores).
  En tablas (tableEx) provoca "Cannot read properties of undefined (reading 'isMeasure')" al filtrar.
* No se escriben propiedades de formato no observadas en visuales reales de la versión en uso.
* Regenerar descarta el formato hecho en Desktop: se exige forzar=True si existe.
"""
from __future__ import annotations

import hashlib
import json
import re
import shutil
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

SCHEMA = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition"
ESQUEMA_VISUAL = f"{SCHEMA}/visualContainer/2.12.0/schema.json"
ESQUEMA_PAGINA = f"{SCHEMA}/page/2.1.0/schema.json"
ESQUEMA_PAGINAS = f"{SCHEMA}/pagesMetadata/1.1.0/schema.json"
ANCHO, ALTO = 1920, 1080
TABLA_MEDIDAS = "_Medidas"


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


def med(nombre: str, tabla: str = TABLA_MEDIDAS) -> Campo:
    return Campo(tabla, nombre, True)


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


def segmentador(campo: Campo, y, modo="Dropdown", x=20, ancho=280, alto=110) -> Visual:
    return Visual("slicer", {"Values": [campo]}, x, y, ancho, alto, {"data": [{"properties": {"mode": literal(modo)}}]})


def barras(categoria: Campo, valores: list[Campo], x, y, ancho, alto, serie: Campo | None = None,
           tipo="clusteredBarChart", orden: tuple[Campo, str] | None = None) -> Visual:
    roles = {"Category": [categoria], "Y": valores}
    if serie:
        roles["Series"] = [serie]
    return Visual(tipo, roles, x, y, ancho, alto, orden=orden)


def tabla(campos: list[Campo], x, y, ancho, alto) -> Visual:
    return Visual("tableEx", {"Values": campos}, x, y, ancho, alto)


Paginas = list[tuple[str, list[Visual]]]


# ---------------------------------------------------------------- validación contra el modelo
def campos_del_modelo(modelo: Path) -> dict[str, dict[str, set[str]]]:
    catalogo: dict[str, dict[str, set[str]]] = {}
    limpiar = lambda s: s.strip().strip("'")  # noqa: E731
    for archivo in (modelo / "tables").glob("*.tmdl"):
        texto = archivo.read_text(encoding="utf-8")
        nombre = limpiar(re.search(r"^table (.+)$", texto, re.M).group(1))
        catalogo[nombre] = {
            "columnas": {limpiar(m) for m in re.findall(r"^\tcolumn ('[^']+'|[^=\s]+)", texto, re.M)},
            "medidas": {limpiar(m) for m in re.findall(r"^\tmeasure ('[^']+'|[^=\s]+)", texto, re.M)},
        }
    return catalogo


def validar(paginas: Paginas, panel: list[Visual], catalogo: dict) -> list[str]:
    errores = []
    for titulo, visuales in paginas:
        for v in [*panel, *visuales]:
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


def generar(reporte: Path, paginas: Paginas, panel: Callable[[], list[Visual]], errores: list[str],
            forzar: bool = False) -> list[str]:
    if tiene_formato_manual(reporte) and not forzar:
        raise SystemExit("El informe tiene formato hecho en Power BI Desktop; regenerar lo descartaría. "
                         "Use --forzar solo si es intencional.")
    if errores:
        raise SystemExit("No se generó el informe:\n- " + "\n- ".join(errores))
    paginas_dir = reporte / "pages"
    orden = []
    staging = reporte / "pages_nuevo"
    shutil.rmtree(staging, ignore_errors=True)
    for titulo, visuales in paginas:
        pid = identificador("pagina", titulo)
        orden.append(pid)
        destino = staging / pid
        (destino / "visuals").mkdir(parents=True)
        (destino / "page.json").write_text(json.dumps({
            "$schema": ESQUEMA_PAGINA, "name": pid, "displayName": titulo,
            "displayOption": "FitToPage", "height": ALTO, "width": ANCHO}, ensure_ascii=False, indent=2), encoding="utf-8")
        for z, visual in enumerate([*panel(), *visuales]):
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
