"""Valores esperados de los KPIs del dashboard estratégico, calculados con DuckDB sobre Gold (F6).

Uso (desde la raíz, con PYTHONPATH=src):
    python -m saber11.bi.kpi_control            # imprime escenario | kpi | valor y guarda JSON
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import duckdb

from saber11.config import PROJECT_ROOT, get_settings
from saber11.quality.rules import resolver_sql

SQL = PROJECT_ROOT / "tests" / "bi" / "kpi_control.sql"
TOLERANCIA = 0.01


def calcular(ruta_gold: Path) -> list[tuple[str, str, float]]:
    con = duckdb.connect()
    try:
        con.execute(resolver_sql(SQL.read_text(encoding="utf-8"), {"gold": ruta_gold.as_posix()}))
        return [(e, k, float(v)) for e, k, v in con.execute("SELECT escenario, kpi, valor FROM kpi_control").fetchall()]
    finally:
        con.close()


def comparar(esperados: list[tuple[str, str, float]], obtenidos: dict[tuple[str, str], float | None],
             tolerancia: float = TOLERANCIA) -> list[dict]:
    filas = []
    for escenario, kpi, esperado in esperados:
        obtenido = obtenidos.get((escenario, kpi))
        diferencia = None if obtenido is None else abs(obtenido - esperado)
        filas.append({"escenario": escenario, "kpi": kpi, "esperado": esperado, "obtenido": obtenido,
                      "diferencia": diferencia, "cumple": diferencia is not None and diferencia <= tolerancia})
    return filas


def main() -> int:
    settings = get_settings()
    gold = PROJECT_ROOT / settings["paths"]["gold"]
    esperados = calcular(gold)
    destino = PROJECT_ROOT / settings["paths"]["reports"] / "bi" / "kpi_esperados.json"
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(json.dumps([{"escenario": e, "kpi": k, "valor": v} for e, k, v in esperados],
                                  ensure_ascii=False, indent=2), encoding="utf-8")
    for e, k, v in esperados:
        print(f"{e:28s} | {k:34s} | {v:.6f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
