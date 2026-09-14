"""Motor de reglas de calidad y quality gate (fase F5b).

Evalúa el catálogo `config/dq_rules.yaml` sobre una capa del lakehouse:

    silver  reglas de tablas Bronze y Silver: se ejecuta tras F3 y debe aprobar antes de construir Gold
    gold    reglas de tablas Gold (dimensiones, hechos, agregados, seguridad): tras F4, antes de BI/ML

Cada regla produce una fila en `data/metadata/dq_results.parquet` (PASA / FALLA / ERROR) y cada
ejecución un informe `reports/quality/dq_<run_id>.md`. El gate aprueba solo si todas las reglas
bloqueantes pasan; un ERROR en una regla bloqueante también bloquea. Ni los resultados ni el informe
contienen valores de filas: solo métricas.
"""
from __future__ import annotations

import json
import math
import os
import time
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import duckdb

from saber11.metadata import run_log
from saber11.quality.rules import cargar_reglas, parametros_desde_settings, resolver_sql
from saber11.transform.naming import normalize_colname

CAPAS = ("silver", "gold")
TABLAS_BRONZE = {"bronze_resultados"}
TABLAS_SILVER = {"silver_resultados", "silver_rechazos"}
TABLAS_GOLD = {
    "dim_tiempo", "dim_colegio", "dim_ubicacion", "dim_perfil_estudiante", "dim_area",
    "fact_resultado", "fact_resultado_area", "agg_benchmark_distrito", "agg_operativo_colegio",
    "seguridad_rectores", "ml_dataset",
}
ESQUEMA_RESULTADOS = """
    run_id VARCHAR, capa VARCHAR, run_id_evaluado VARCHAR, ingest_id VARCHAR, regla_id VARCHAR,
    dimension VARCHAR, tabla VARCHAR, severidad VARCHAR, metrica VARCHAR, umbral DOUBLE, valor DOUBLE,
    estado VARCHAR, mensaje VARCHAR, duracion_ms DOUBLE, evaluado_utc TIMESTAMP
"""


class CapaNoDisponibleError(RuntimeError):
    """No existen los datos mínimos para evaluar la capa solicitada."""


@dataclass
class ResultadoRegla:
    regla_id: str
    dimension: str
    tabla: str
    severidad: str
    metrica: str
    umbral: float
    valor: float | None
    estado: str          # PASA | FALLA | ERROR
    mensaje: str = ""
    duracion_ms: float = 0.0

    @property
    def bloquea(self) -> bool:
        return self.severidad == "bloqueante" and self.estado != "PASA"


@dataclass
class ResultadoGate:
    run_id: str
    capa: str
    run_id_evaluado: str | None
    ingest_id: str | None
    evaluado_utc: datetime
    resultados: list[ResultadoRegla] = field(default_factory=list)
    filas_cuarentena: int | None = None
    rutas: dict[str, Path] = field(default_factory=dict)

    @property
    def aprobado(self) -> bool:
        return bool(self.resultados) and not any(r.bloquea for r in self.resultados)

    @property
    def score(self) -> float:
        return sum(r.estado == "PASA" for r in self.resultados) / len(self.resultados) if self.resultados else 0.0

    def resumen(self) -> dict[str, Any]:
        return {
            "capa": self.capa, "aprobado": self.aprobado, "run_id_evaluado": self.run_id_evaluado,
            "ingest_id": self.ingest_id, "reglas": len(self.resultados), "score_dq": round(self.score, 4),
            "bloqueantes_fallidas": [r.regla_id for r in self.resultados if r.bloquea],
            "advertencias": [r.regla_id for r in self.resultados if r.severidad == "advertencia" and r.estado != "PASA"],
            "filas_cuarentena": self.filas_cuarentena,
        }


# ---------------------------------------------------------------- selección de reglas
def capa_de_tabla(tabla: str) -> str:
    if tabla in TABLAS_BRONZE or tabla in TABLAS_SILVER:
        return "silver"
    if tabla in TABLAS_GOLD:
        return "gold"
    raise ValueError(f"Tabla sin capa asignada en el motor DQ: {tabla}")


def reglas_de_capa(reglas: list[dict[str, Any]], capa: str) -> list[dict[str, Any]]:
    """Reglas evaluadas por el gate de la capa. DQ-PRI-001 aplica a ambas (sin PII en Silver ni Gold)."""
    return [r for r in reglas if capa_de_tabla(r["tabla"]) == capa or r["id"] == "DQ-PRI-001"]


# ---------------------------------------------------------------- contexto de datos
def _lit(valor: object) -> str:
    return "'" + str(valor).replace("'", "''") + "'"


def _registrar_parquet(con: duckdb.DuckDBPyConnection, nombre: str, ruta: Path) -> bool:
    if ruta.is_file():
        con.execute(f"CREATE OR REPLACE VIEW {nombre} AS SELECT * FROM read_parquet({_lit(ruta)})")
        return True
    if ruta.is_dir() and any(ruta.rglob("*.parquet")):
        patron = (ruta / "**" / "*.parquet").as_posix()
        con.execute(f"CREATE OR REPLACE VIEW {nombre} AS SELECT * FROM read_parquet({_lit(patron)}, hive_partitioning = true)")
        return True
    return False


def ultimo_run(registros: list[dict[str, Any]], etapa: str) -> dict[str, Any] | None:
    return next((r for r in reversed(registros) if r["etapa"] == etapa and r["estado"] == "exitoso"), None)


def preparar_contexto(con: duckdb.DuckDBPyConnection, capa: str, settings: dict[str, Any], raiz: Path,
                      registros: list[dict[str, Any]]) -> dict[str, Any]:
    p, lh = settings["paths"], settings["lakehouse"]
    ruta_run_log = raiz / p["metadata"] / "run_log.parquet"
    if ruta_run_log.exists():
        con.execute(f"CREATE OR REPLACE VIEW run_log AS SELECT * FROM read_parquet({_lit(ruta_run_log)})")
    else:
        con.execute("CREATE OR REPLACE TABLE run_log (run_id VARCHAR, etapa VARCHAR, estado VARCHAR, filas BIGINT, finalizado_utc TIMESTAMP)")

    silver_dir = raiz / p["silver"]
    ctx: dict[str, Any] = {"tablas": set(), "run_id_evaluado": None, "ingest_id": None}
    if capa == "silver":
        for tabla, archivo in ((lh["silver_table"], "silver_resultados"), (lh["silver_quarantine"], "silver_rechazos")):
            if not _registrar_parquet(con, archivo, silver_dir / f"{tabla}.parquet"):
                raise CapaNoDisponibleError(f"No existe {tabla}.parquet en {silver_dir}; ejecute la etapa silver")
            ctx["tablas"].add(archivo)
        ingest_id = con.execute("SELECT any_value(_ingest_id) FROM silver_resultados").fetchone()[0]
        particion = raiz / p["bronze"] / lh["bronze_table"] / f"ingest_id={ingest_id}"
        if not _registrar_parquet(con, "bronze_resultados", particion):
            raise CapaNoDisponibleError(f"No existe la partición Bronze ingest_id={ingest_id} que originó Silver")
        con.execute("CREATE OR REPLACE VIEW bronze_resultados AS "
                    f"SELECT * FROM read_parquet({_lit((particion / '*.parquet').as_posix())}, hive_partitioning = false)")
        ctx["tablas"].add("bronze_resultados")
        ctx["ingest_id"] = ingest_id
        silver_run = ultimo_run(registros, "silver")
        ctx["run_id_evaluado"] = silver_run["run_id"] if silver_run else None
    else:
        gold_dir = raiz / p["gold"]
        ctx["tablas"] = {t for t in TABLAS_GOLD if _registrar_parquet(con, t, gold_dir / f"{t}.parquet")
                         or _registrar_parquet(con, t, gold_dir / t)}
        if not ctx["tablas"]:
            raise CapaNoDisponibleError(f"No hay tablas Gold en {gold_dir}; ejecute la etapa gold (F4)")
        gold_run = ultimo_run(registros, "gold")
        ctx["run_id_evaluado"] = gold_run["run_id"] if gold_run else None
    return ctx


# ---------------------------------------------------------------- reglas evaluadas en Python
def _columnas(con: duckdb.DuckDBPyConnection, tabla: str) -> list[str]:
    return [fila[0] for fila in con.execute(f"DESCRIBE {tabla}").fetchall()]


def _int_001(con, contrato, ctx) -> tuple[float, str]:
    esperadas = [c["name"] for c in contrato["source_contract"]["columns"]]
    reales = [c for c in _columnas(con, "bronze_resultados") if not c.startswith("_")]
    faltantes = [c for c in esperadas if c not in reales]
    sobrantes = [c for c in reales if c not in esperadas]
    orden_ok = [c for c in reales if c in esperadas] == [c for c in esperadas if c in reales]
    fallos = len(faltantes) + len(sobrantes) + (0 if orden_ok else 1)
    return fallos, f"faltantes={faltantes} sobrantes={sobrantes} orden_correcto={orden_ok}"


def _int_002(con, contrato, ctx) -> tuple[float, str]:
    b, s, r = (con.execute(f"SELECT count(*) FROM {t}").fetchone()[0]
               for t in ("bronze_resultados", "silver_resultados", "silver_rechazos"))
    return abs(s + r - b), f"bronze={b} silver={s} rechazos={r}"


def _pri_001(con, contrato, ctx) -> tuple[float, str]:
    pii = {normalize_colname(c["name"]) for c in contrato["source_contract"]["columns"] if c.get("pii")}
    tablas = sorted(t for t in ctx["tablas"] if not t.startswith("bronze"))
    hallazgos = [f"{t}.{c}" for t in tablas for c in _columnas(con, t) if normalize_colname(c) in pii]
    return len(hallazgos), f"tablas_revisadas={tablas} columnas_pii={hallazgos}"


EVALUADORES_PYTHON: dict[str, Callable[..., tuple[float, str]]] = {
    "DQ-INT-001": _int_001,
    "DQ-INT-002": _int_002,
    "DQ-PRI-001": _pri_001,
}


# ---------------------------------------------------------------- ejecución
def evaluar_regla(con: duckdb.DuckDBPyConnection, regla: dict[str, Any], contrato: dict[str, Any],
                  ctx: dict[str, Any], parametros: dict[str, Any]) -> ResultadoRegla:
    base = {
        "regla_id": regla["id"], "dimension": regla["dimension"], "tabla": regla["tabla"],
        "severidad": regla["severidad"], "metrica": regla.get("metrica", "conteo"),
        "umbral": float(regla["umbral_max_fallos"]),
    }
    inicio = time.perf_counter()
    try:
        if "sql" in regla:
            valor = con.execute(resolver_sql(regla["sql"], parametros)).fetchone()[0]
            mensaje = ""
        elif regla["id"] in EVALUADORES_PYTHON:
            valor, mensaje = EVALUADORES_PYTHON[regla["id"]](con, contrato, ctx)
        else:
            raise NotImplementedError(f"La regla {regla['id']} no tiene SQL ni evaluador Python")
        if valor is None or (isinstance(valor, float) and math.isnan(valor)):
            raise ValueError("la regla devolvió un valor nulo")
        valor = float(valor)
        estado = "PASA" if valor <= base["umbral"] else "FALLA"
    except Exception as e:  # noqa: BLE001 - un error de evaluación se reporta como ERROR de la regla
        valor, estado, mensaje = None, "ERROR", f"{type(e).__name__}: {str(e).splitlines()[0][:300]}"
    return ResultadoRegla(**base, valor=valor, estado=estado, mensaje=mensaje,
                          duracion_ms=round((time.perf_counter() - inicio) * 1000, 2))


def ejecutar_gate(capa: str, settings: dict[str, Any], contrato: dict[str, Any], raiz: Path,
                  run_id: str, momento: datetime) -> ResultadoGate:
    if capa not in CAPAS:
        raise ValueError(f"Capa inválida: {capa}. Opciones: {CAPAS}")
    registros = run_log.leer(raiz / settings["paths"]["metadata"] / "run_log.parquet")
    reglas = reglas_de_capa(cargar_reglas(), capa)
    con = duckdb.connect()
    try:
        con.execute(f"SET temp_directory = {_lit(raiz / settings['paths']['tmp'])}")
        ctx = preparar_contexto(con, capa, settings, raiz, registros)
        # ${run_id} en las reglas identifica la ejecución que produjo los datos evaluados (DQ-VOL-001
        # la excluye para comparar contra la carga anterior).
        parametros = parametros_desde_settings(settings, run_id=ctx["run_id_evaluado"] or run_id)
        gate = ResultadoGate(run_id, capa, ctx["run_id_evaluado"], ctx["ingest_id"], momento,
                             [evaluar_regla(con, r, contrato, ctx, parametros) for r in reglas])
        if "silver_rechazos" in ctx["tablas"]:
            gate.filas_cuarentena = con.execute("SELECT count(*) FROM silver_rechazos").fetchone()[0]
    finally:
        con.close()
    gate.rutas = {
        "resultados": guardar_resultados(raiz / settings["paths"]["metadata"] / "dq_results.parquet", gate),
        "informe": escribir_informe(raiz / settings["paths"]["reports"] / "quality", gate),
    }
    return gate


# ---------------------------------------------------------------- persistencia
def guardar_resultados(ruta: Path, gate: ResultadoGate) -> Path:
    ruta.parent.mkdir(parents=True, exist_ok=True)
    tmp = ruta.with_name(ruta.name + ".tmp")
    con = duckdb.connect()
    try:
        con.execute(f"CREATE TABLE dq_results ({ESQUEMA_RESULTADOS})")
        if ruta.exists():
            con.execute("INSERT INTO dq_results SELECT * FROM read_parquet(?)", [str(ruta)])
        con.executemany(
            "INSERT INTO dq_results VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [[gate.run_id, gate.capa, gate.run_id_evaluado, gate.ingest_id, r.regla_id, r.dimension, r.tabla,
              r.severidad, r.metrica, r.umbral, r.valor, r.estado, r.mensaje, r.duracion_ms, gate.evaluado_utc]
             for r in gate.resultados])
        con.execute(f"COPY dq_results TO {_lit(tmp)} (FORMAT parquet)")
    finally:
        con.close()
    os.replace(tmp, ruta)
    return ruta


def _fmt(valor: float | None, metrica: str) -> str:
    if valor is None:
        return "—"
    return f"{valor:.2%}" if metrica == "proporcion" else f"{valor:g}"


def escribir_informe(carpeta: Path, gate: ResultadoGate) -> Path:
    carpeta.mkdir(parents=True, exist_ok=True)
    ruta = carpeta / f"dq_{gate.run_id}.md"
    r = gate.resumen()
    dimensiones: dict[str, list[ResultadoRegla]] = {}
    for res in gate.resultados:
        dimensiones.setdefault(res.dimension, []).append(res)
    lineas = [
        f"# Informe de calidad de datos — capa {gate.capa}", "",
        f"**Gate: {'APROBADO ✅' if gate.aprobado else 'RECHAZADO ❌'}**", "",
        "| Campo | Valor |", "|---|---|",
        f"| run_id | `{gate.run_id}` |",
        f"| Evaluado (UTC) | {gate.evaluado_utc:%Y-%m-%d %H:%M:%S} |",
        f"| Ejecución evaluada | `{gate.run_id_evaluado or '—'}` |",
        f"| Partición Bronze | `{gate.ingest_id or '—'}` |",
        f"| Reglas evaluadas | {r['reglas']} |",
        f"| Score DQ (reglas PASA / total) | {r['score_dq']:.1%} |",
        f"| Bloqueantes no aprobadas | {', '.join(r['bloqueantes_fallidas']) or 'ninguna'} |",
        f"| Advertencias | {', '.join(r['advertencias']) or 'ninguna'} |",
    ]
    if gate.filas_cuarentena is not None:
        lineas.append(f"| Filas en cuarentena (silver_rechazos) | {gate.filas_cuarentena} |")
    lineas += ["", "## Aprobación por dimensión", "", "| Dimensión | Reglas | PASA | % aprobadas |", "|---|---|---|---|"]
    for dim, res in sorted(dimensiones.items()):
        pasa = sum(x.estado == "PASA" for x in res)
        lineas.append(f"| {dim} | {len(res)} | {pasa} | {pasa / len(res):.0%} |")
    lineas += ["", "## Resultado por regla", "",
               "| Regla | Dimensión | Tabla | Severidad | Valor | Umbral | Estado | Detalle |",
               "|---|---|---|---|---|---|---|---|"]
    for x in gate.resultados:
        detalle = x.mensaje.replace("|", "\\|")
        lineas.append(f"| {x.regla_id} | {x.dimension} | {x.tabla} | {x.severidad} | {_fmt(x.valor, x.metrica)} | "
                      f"{_fmt(x.umbral, x.metrica)} | {x.estado} | {detalle} |")
    lineas += ["", "> Criterio de aprobación: 100 % de reglas bloqueantes en estado PASA. "
                   "Un ERROR de evaluación en una regla bloqueante también rechaza el gate. "
                   "El informe contiene solo métricas agregadas."]
    ruta.write_text("\n".join(lineas) + "\n", encoding="utf-8")
    return ruta


# ---------------------------------------------------------------- consulta del gate (para F4 y siguientes)
def gate_aprobado(ruta_run_log: Path, capa: str, run_id_evaluado: str | None) -> bool:
    """True si el último gate de `capa` sobre `run_id_evaluado` fue aprobado."""
    for registro in reversed(run_log.leer(ruta_run_log)):
        if registro["etapa"] != f"dq_{capa}":
            continue
        detalle = json.loads(registro["detalle"] or "{}")
        if detalle.get("run_id_evaluado") == run_id_evaluado:
            return registro["estado"] == "exitoso" and bool(detalle.get("aprobado"))
    return False


def resultados_como_dicts(gate: ResultadoGate) -> list[dict[str, Any]]:
    return [asdict(r) for r in gate.resultados]
