"""Genera docs/bi/medidas_dax.md a partir del modelo semántico guardado como PBIP (TMDL).

Uso (desde la raíz, con PYTHONPATH=src):
    python -m saber11.bi.catalogo_medidas                       # dashboard estratégico
    python -m saber11.bi.catalogo_medidas --tablero operativo   # dashboard operativo (F7)
"""
from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from pathlib import Path

from saber11.config import PROJECT_ROOT

MODELO = PROJECT_ROOT / "powerbi" / "Saber11_Estrategico.SemanticModel" / "definition"
DESTINO = PROJECT_ROOT / "docs" / "bi" / "medidas_dax.md"
TABLEROS = {
    "estrategico": ("Dashboard estratégico", MODELO, DESTINO),
    "operativo": ("Dashboard operativo", PROJECT_ROOT / "powerbi" / "Saber11_Operativo.SemanticModel" / "definition",
                  PROJECT_ROOT / "docs" / "bi" / "medidas_dax_operativo.md"),
}
PATRON_MEDIDA = re.compile(r"^\tmeasure (?P<nombre>'[^']+'|\S+) =(?P<resto>.*)$")
PROPIEDADES = ("formatString", "displayFolder", "lineageTag", "isHidden", "dataType", "annotation")


@dataclass
class Medida:
    tabla: str
    nombre: str
    expresion: str
    formato: str = ""
    carpeta: str = ""
    descripcion: str = ""


def leer_medidas(archivo: Path) -> list[Medida]:
    lineas = archivo.read_text(encoding="utf-8").splitlines()
    tabla = next(ln.split("table ", 1)[1].strip().strip("'") for ln in lineas if ln.startswith("table "))
    medidas: list[Medida] = []
    descripcion: list[str] = []
    i = 0
    while i < len(lineas):
        linea = lineas[i]
        if linea.startswith("\t///"):
            descripcion.append(linea.removeprefix("\t///").strip())
        else:
            m = PATRON_MEDIDA.match(linea)
            if m:
                cuerpo = [m.group("resto").strip()] if m.group("resto").strip() else []
                i += 1
                while i < len(lineas) and lineas[i].startswith("\t\t") and not any(
                        lineas[i].strip().startswith(f"{p}:") or lineas[i].strip().startswith(f"{p} ") for p in PROPIEDADES):
                    cuerpo.append(lineas[i].removeprefix("\t\t\t").removeprefix("\t\t"))
                    i += 1
                medida = Medida(tabla, m.group("nombre").strip("'"), "\n".join(cuerpo).strip(),
                                descripcion=" ".join(descripcion))
                while i < len(lineas) and lineas[i].startswith("\t\t"):
                    prop = lineas[i].strip()
                    if prop.startswith("formatString:"):
                        medida.formato = prop.split(":", 1)[1].strip()
                    elif prop.startswith("displayFolder:"):
                        medida.carpeta = prop.split(":", 1)[1].strip()
                    i += 1
                medidas.append(medida)
                descripcion = []
                continue
            elif linea.strip():
                descripcion = []
        i += 1
    return medidas


def generar(modelo: Path = MODELO, titulo: str = "Dashboard estratégico") -> str:
    medidas = [m for archivo in sorted((modelo / "tables").glob("*.tmdl")) for m in leer_medidas(archivo)]
    medidas.sort(key=lambda m: (m.carpeta, m.nombre))
    salida = [
        f"# Catálogo de medidas DAX — {titulo}", "",
        f"> Generado desde `{modelo.parent.relative_to(PROJECT_ROOT).as_posix()}` con `python -m saber11.bi.catalogo_medidas`. "
        "No editar a mano: modificar la medida en el modelo y regenerar.", "",
        ("Validación numérica contra SQL: [`reports/bi/validacion_kpis_estrategico.md`](../../reports/bi/validacion_kpis_estrategico.md) "
         "(consultas de control en `tests/bi/kpi_control.sql`)." if "Operativo" not in modelo.parent.name else
         "Validación numérica contra SQL: [`reports/bi/validacion_kpis_operativo.md`](../../reports/bi/validacion_kpis_operativo.md); "
         "casos RLS: [`tests/rls/casos_rls.md`](../../tests/rls/casos_rls.md)."), "",
        "| Carpeta | Medida | Formato | Descripción |", "|---|---|---|---|",
    ]
    salida += [f"| {m.carpeta} | `{m.nombre}` | `{m.formato}` | {m.descripcion} |" for m in medidas]
    salida.append("")
    carpeta_actual = None
    for m in medidas:
        if m.carpeta != carpeta_actual:
            carpeta_actual = m.carpeta
            salida += [f"## {carpeta_actual}", ""]
        salida += [f"### {m.nombre}", ""]
        if m.descripcion:
            salida += [m.descripcion, ""]
        salida += ["```dax", f"{m.nombre} =", m.expresion, "```", ""]
    return "\n".join(salida)


def main() -> int:
    tablero = sys.argv[sys.argv.index("--tablero") + 1] if "--tablero" in sys.argv else "estrategico"
    titulo, modelo, destino = TABLEROS[tablero]
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(generar(modelo, titulo), encoding="utf-8")
    print(f"Catálogo escrito en {destino.relative_to(PROJECT_ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
