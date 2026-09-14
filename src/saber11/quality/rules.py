"""Catálogo de reglas de calidad (F5a): carga, validación estructural y resolución de parámetros.

El motor que ejecuta las reglas y aplica el gate pertenece a F5b.
"""
from __future__ import annotations

import re
from typing import Any

from saber11.config import get_dq_rules, get_settings

CAMPOS_OBLIGATORIOS = ("id", "dimension", "tabla", "descripcion", "severidad", "umbral_max_fallos")
DIMENSIONES = {
    "integridad", "completitud", "unicidad", "validez", "consistencia",
    "exactitud", "integridad_referencial", "privacidad", "volumen",
}
SEVERIDADES = {"bloqueante", "advertencia"}
METRICAS = {"conteo", "proporcion"}
PATRON_ID = re.compile(r"^DQ-[A-Z]{3}-\d{3}$")
PATRON_PARAMETRO = re.compile(r"\$\{(\w+)\}")


def parametros_desde_settings(settings: dict[str, Any] | None = None, run_id: str = "") -> dict[str, Any]:
    """Valores disponibles para los marcadores ${...} de las reglas."""
    privacidad = (settings or get_settings())["privacy"]
    return {
        "k_min": int(privacidad["k_min"]),
        "min_schools_comparative": int(privacidad["min_schools_comparative"]),
        "run_id": run_id,
    }


def validar_catalogo(reglas: list[dict[str, Any]], parametros_permitidos: set[str]) -> list[str]:
    """Devuelve la lista de errores del catálogo (vacía si es válido)."""
    errores: list[str] = []
    ids = [r.get("id") for r in reglas]
    errores += [f"id duplicado: {i}" for i in sorted({i for i in ids if ids.count(i) > 1})]
    for r in reglas:
        rid = r.get("id", "<sin id>")
        errores += [f"{rid}: falta el campo '{c}'" for c in CAMPOS_OBLIGATORIOS if c not in r]
        if not PATRON_ID.match(str(rid)):
            errores.append(f"{rid}: id con formato inválido")
        if r.get("dimension") not in DIMENSIONES:
            errores.append(f"{rid}: dimensión inválida '{r.get('dimension')}'")
        if r.get("severidad") not in SEVERIDADES:
            errores.append(f"{rid}: severidad inválida '{r.get('severidad')}'")
        metrica = r.get("metrica", "conteo")
        if metrica not in METRICAS:
            errores.append(f"{rid}: métrica inválida '{metrica}'")
        umbral = r.get("umbral_max_fallos")
        if not isinstance(umbral, (int, float)) or umbral < 0 or (metrica == "proporcion" and umbral > 1):
            errores.append(f"{rid}: umbral inválido {umbral!r} para métrica {metrica}")
        desconocidos = set(PATRON_PARAMETRO.findall(r.get("sql", ""))) - parametros_permitidos
        errores += [f"{rid}: parámetro desconocido ${{{p}}}" for p in sorted(desconocidos)]
    return errores


def resolver_sql(sql: str, parametros: dict[str, Any]) -> str:
    """Sustituye los marcadores ${nombre}; falla si alguno no tiene valor."""
    faltantes = set(PATRON_PARAMETRO.findall(sql)) - set(parametros)
    if faltantes:
        raise KeyError(f"Parámetros sin valor: {sorted(faltantes)}")
    return PATRON_PARAMETRO.sub(lambda m: str(parametros[m.group(1)]), sql)


def cargar_reglas() -> list[dict[str, Any]]:
    """Carga el catálogo y lo valida; lanza ValueError si hay errores."""
    reglas = get_dq_rules()["rules"]
    errores = validar_catalogo(reglas, set(parametros_desde_settings()))
    if errores:
        raise ValueError("Catálogo de reglas DQ inválido:\n- " + "\n- ".join(errores))
    return reglas
