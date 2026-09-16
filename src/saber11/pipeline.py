"""CLI del pipeline Saber 11.

Uso (desde la raíz del proyecto, con el entorno .venv):
    python -m saber11.pipeline validate-source
    python -m saber11.pipeline run --stage bronze
    python -m saber11.pipeline run --stage silver [--ingest-id <run_id>]
    python -m saber11.pipeline run --stage dq [--layer silver|gold]
    python -m saber11.pipeline run --stage gold
    python -m saber11.pipeline run --stage ml

Solo están implementadas las etapas ya ejecutadas en el plan; las demás informan su fase.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

from saber11.config import PROJECT_ROOT, get_hmac_key, get_settings, get_source_contract
from saber11.ingest.bronze import escribir_reporte_contrato, ingerir_bronze
from saber11.ingest.contract import ContratoFuenteError, validar_fuente
from saber11.logging_utils import setup_logger
from saber11.metadata import run_log
from saber11.ml.experimento import ejecutar as ejecutar_experimento_ml
from saber11.quality.engine import ejecutar_gate, gate_aprobado, ultimo_run
from saber11.transform.gold import construir_gold
from saber11.transform.silver import ingerir_silver

ETAPAS_PENDIENTES = {"shap": "F9", "fairness": "F10"}
log = setup_logger("saber11.pipeline")


def ruta_fuente(settings: dict[str, Any], raiz: Path) -> Path:
    return raiz / settings["paths"]["landing"] / settings["source"]["file_name"]


def ejecutar_bronze(settings: dict[str, Any], contrato: dict[str, Any], raiz: Path,
                    fuente: Path | None = None) -> int:
    run_id = run_log.nuevo_run_id()
    inicio = run_log.ahora_utc()
    fuente = fuente or ruta_fuente(settings, raiz)
    ruta_log = raiz / settings["paths"]["metadata"] / "run_log.parquet"
    sha_git = run_log.git_sha(raiz)
    trazabilidad = {"git_con_cambios": run_log.git_con_cambios(raiz)}
    log.info("Inicio etapa bronze run_id=%s archivo=%s", run_id, fuente.name)
    try:
        r = ingerir_bronze(fuente, settings, contrato, run_id, raiz, inicio)
    except ContratoFuenteError as e:
        run_log.registrar(ruta_log, run_log.RegistroEjecucion(
            run_id, "bronze", "fallido", inicio, run_log.ahora_utc(), git_sha=sha_git,
            detalle={"error": "contrato", **trazabilidad, **e.resultado.a_dict()}))
        log.error("Contrato de fuente incumplido: %s", e.resultado.errores_por_tipo)
        return 2
    except Exception as e:  # noqa: BLE001 - se registra el fallo y se devuelve código de error
        run_log.registrar(ruta_log, run_log.RegistroEjecucion(
            run_id, "bronze", "fallido", inicio, run_log.ahora_utc(), git_sha=sha_git,
            detalle={"error": type(e).__name__, "mensaje": str(e), **trazabilidad}))
        log.error("Etapa bronze fallida: %s: %s", type(e).__name__, e)
        return 1
    run_log.registrar(ruta_log, run_log.RegistroEjecucion(
        run_id, "bronze", r.estado, inicio, run_log.ahora_utc(), filas=r.filas,
        source_sha256=r.source_sha256, git_sha=sha_git, detalle={**r.detalle(), **trazabilidad}))
    log.info("Fin etapa bronze: estado=%s filas=%d ingest_id=%s", r.estado, r.filas, r.ingest_id)
    return 0


def ejecutar_silver(settings: dict[str, Any], contrato: dict[str, Any], raiz: Path,
                    ingest_id: str | None = None, clave_hmac: str | None = None) -> int:
    run_id = run_log.nuevo_run_id()
    inicio = run_log.ahora_utc()
    ruta_log = raiz / settings["paths"]["metadata"] / "run_log.parquet"
    sha_git = run_log.git_sha(raiz)
    trazabilidad = {"git_con_cambios": run_log.git_con_cambios(raiz)}
    log.info("Inicio etapa silver run_id=%s", run_id)
    try:
        r = ingerir_silver(settings, contrato, raiz, clave_hmac or get_hmac_key(), ingest_id)
    except Exception as e:  # noqa: BLE001 - se registra el fallo y se devuelve código de error
        run_log.registrar(ruta_log, run_log.RegistroEjecucion(
            run_id, "silver", "fallido", inicio, run_log.ahora_utc(), git_sha=sha_git,
            detalle={"error": type(e).__name__, "mensaje": str(e), "ingest_id": ingest_id, **trazabilidad}))
        log.error("Etapa silver fallida: %s: %s", type(e).__name__, e)
        return 1
    run_log.registrar(ruta_log, run_log.RegistroEjecucion(
        run_id, "silver", "exitoso", inicio, run_log.ahora_utc(), filas=r.filas_silver,
        source_sha256=r.source_sha256, git_sha=sha_git, detalle={**r.detalle(), **trazabilidad}))
    log.info("Fin etapa silver: filas=%d rechazos=%d ingest_id=%s", r.filas_silver, r.filas_rechazo, r.ingest_id)
    return 0


def ejecutar_dq(settings: dict[str, Any], contrato: dict[str, Any], raiz: Path, capa: str = "silver") -> int:
    """Quality gate. Códigos: 0 aprobado, 4 rechazado (bloqueantes), 1 error técnico."""
    run_id = run_log.nuevo_run_id()
    inicio = run_log.ahora_utc()
    etapa = f"dq_{capa}"
    ruta_log = raiz / settings["paths"]["metadata"] / "run_log.parquet"
    sha_git = run_log.git_sha(raiz)
    trazabilidad = {"git_con_cambios": run_log.git_con_cambios(raiz)}
    log.info("Inicio quality gate capa=%s run_id=%s", capa, run_id)
    try:
        gate = ejecutar_gate(capa, settings, contrato, raiz, run_id, inicio)
    except Exception as e:  # noqa: BLE001 - se registra el fallo y se devuelve código de error
        run_log.registrar(ruta_log, run_log.RegistroEjecucion(
            run_id, etapa, "fallido", inicio, run_log.ahora_utc(), git_sha=sha_git,
            detalle={"error": type(e).__name__, "mensaje": str(e), "aprobado": False, **trazabilidad}))
        log.error("Quality gate %s con error: %s: %s", capa, type(e).__name__, e)
        return 1
    resumen = gate.resumen()
    run_log.registrar(ruta_log, run_log.RegistroEjecucion(
        run_id, etapa, "exitoso" if gate.aprobado else "fallido", inicio, run_log.ahora_utc(),
        filas=len(gate.resultados), git_sha=sha_git,
        detalle={**resumen, "informe": gate.rutas["informe"].relative_to(raiz).as_posix(), **trazabilidad}))
    for r in gate.resultados:
        if r.estado != "PASA":
            log.warning("%s %s %s valor=%s umbral=%s %s", r.regla_id, r.severidad, r.estado, r.valor, r.umbral, r.mensaje)
    log.info("Quality gate %s: %s score=%.1f%% bloqueantes_fallidas=%s informe=%s", capa,
             "APROBADO" if gate.aprobado else "RECHAZADO", 100 * gate.score, resumen["bloqueantes_fallidas"],
             gate.rutas["informe"].relative_to(raiz))
    return 0 if gate.aprobado else 4


def ejecutar_gold(settings: dict[str, Any], contrato: dict[str, Any], raiz: Path,
                  ruta_seguridad: Path | None = None) -> int:
    """Construye Gold solo si el Silver vigente pasó el quality gate. Códigos: 0 éxito, 5 gate no aprobado, 1 error."""
    run_id = run_log.nuevo_run_id()
    inicio = run_log.ahora_utc()
    ruta_log = raiz / settings["paths"]["metadata"] / "run_log.parquet"
    sha_git = run_log.git_sha(raiz)
    trazabilidad = {"git_con_cambios": run_log.git_con_cambios(raiz)}
    silver_run = ultimo_run(run_log.leer(ruta_log), "silver")
    silver_run_id = silver_run["run_id"] if silver_run else None
    log.info("Inicio etapa gold run_id=%s silver=%s", run_id, silver_run_id)
    if not silver_run_id or not gate_aprobado(ruta_log, "silver", silver_run_id):
        motivo = "no hay Silver" if not silver_run_id else "el quality gate de ese Silver no está aprobado"
        run_log.registrar(ruta_log, run_log.RegistroEjecucion(
            run_id, "gold", "fallido", inicio, run_log.ahora_utc(), git_sha=sha_git,
            detalle={"error": "gate_silver_no_aprobado", "mensaje": motivo, "silver_run_id": silver_run_id, **trazabilidad}))
        log.error("Gold bloqueado: %s. Ejecute: run --stage dq --layer silver", motivo)
        return 5
    try:
        r = construir_gold(settings, contrato, raiz, run_id, ruta_seguridad)
    except Exception as e:  # noqa: BLE001 - se registra el fallo y se devuelve código de error
        run_log.registrar(ruta_log, run_log.RegistroEjecucion(
            run_id, "gold", "fallido", inicio, run_log.ahora_utc(), git_sha=sha_git,
            detalle={"error": type(e).__name__, "mensaje": str(e), "silver_run_id": silver_run_id, **trazabilidad}))
        log.error("Etapa gold fallida: %s: %s", type(e).__name__, e)
        return 1
    run_log.registrar(ruta_log, run_log.RegistroEjecucion(
        run_id, "gold", "exitoso", inicio, run_log.ahora_utc(), filas=r.filas["fact_resultado"],
        source_sha256=silver_run["source_sha256"], git_sha=sha_git,
        detalle={**r.detalle(), "silver_run_id": silver_run_id, **trazabilidad}))
    log.info("Fin etapa gold: fact=%d tablas=%d", r.filas["fact_resultado"], len(r.filas))
    return 0


def ejecutar_ml(settings: dict[str, Any], raiz: Path) -> int:
    """Entrena y compara los modelos de F8. Códigos: 0 éxito, 5 gate de Gold no aprobado, 1 error."""
    run_id = run_log.nuevo_run_id()
    inicio = run_log.ahora_utc()
    ruta_log = raiz / settings["paths"]["metadata"] / "run_log.parquet"
    sha_git = run_log.git_sha(raiz)
    trazabilidad = {"git_con_cambios": run_log.git_con_cambios(raiz)}
    gold_run = ultimo_run(run_log.leer(ruta_log), "gold")
    gold_run_id = gold_run["run_id"] if gold_run else None
    log.info("Inicio etapa ml run_id=%s gold=%s", run_id, gold_run_id)
    if not gold_run_id or not gate_aprobado(ruta_log, "gold", gold_run_id):
        motivo = "no hay Gold" if not gold_run_id else "el quality gate de ese Gold no está aprobado"
        run_log.registrar(ruta_log, run_log.RegistroEjecucion(
            run_id, "ml", "fallido", inicio, run_log.ahora_utc(), git_sha=sha_git,
            detalle={"error": "gate_gold_no_aprobado", "mensaje": motivo, "gold_run_id": gold_run_id, **trazabilidad}))
        log.error("ML bloqueado: %s. Ejecute: run --stage dq --layer gold", motivo)
        return 5
    try:
        r = ejecutar_experimento_ml(settings, raiz, run_id)
    except Exception as e:  # noqa: BLE001 - se registra el fallo y se devuelve código de error
        run_log.registrar(ruta_log, run_log.RegistroEjecucion(
            run_id, "ml", "fallido", inicio, run_log.ahora_utc(), git_sha=sha_git,
            detalle={"error": type(e).__name__, "mensaje": str(e), "gold_run_id": gold_run_id, **trazabilidad}))
        log.error("Etapa ml fallida: %s: %s", type(e).__name__, e)
        return 1
    run_log.registrar(ruta_log, run_log.RegistroEjecucion(
        run_id, "ml", "exitoso", inicio, run_log.ahora_utc(), filas=r.filas["entrena"],
        source_sha256=gold_run["source_sha256"], git_sha=sha_git,
        detalle={**r.detalle(), "gold_run_id": gold_run_id, **trazabilidad}))
    metricas = r.resultados[r.seleccionado].metricas_test
    log.info("Fin etapa ml: modelo=%s R2=%.3f RMSE=%.2f MAE=%.2f supera_baseline=%s informe=%s",
             r.seleccionado, metricas["r2"], metricas["rmse"], metricas["mae"],
             r.supera_baseline, r.rutas["informe"])
    return 0


def validar_fuente_cli(settings: dict[str, Any], contrato: dict[str, Any], raiz: Path) -> int:
    run_id = run_log.nuevo_run_id()
    resultado = validar_fuente(ruta_fuente(settings, raiz), contrato)
    reporte = escribir_reporte_contrato(resultado, run_id, raiz / settings["paths"]["reports"] / "quality")
    log.info("Contrato %s: filas=%d errores=%s reporte=%s", "aprobado" if resultado.aprobado else "RECHAZADO",
             resultado.filas_datos, resultado.errores_por_tipo, reporte.relative_to(raiz))
    return 0 if resultado.aprobado else 2


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="saber11.pipeline", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="comando", required=True)
    sub.add_parser("validate-source", help="valida el CSV de landing contra el contrato")
    run = sub.add_parser("run", help="ejecuta una etapa del pipeline")
    run.add_argument("--stage", required=True, choices=["bronze", "silver", "dq", "gold", "ml", *ETAPAS_PENDIENTES])
    run.add_argument("--ingest-id", help="partición Bronze a procesar en silver (por defecto, la vigente)")
    run.add_argument("--layer", choices=["silver", "gold"], default="silver", help="capa evaluada por el quality gate")
    args = parser.parse_args(argv)

    settings, contrato = get_settings(), get_source_contract()
    if args.comando == "validate-source":
        return validar_fuente_cli(settings, contrato, PROJECT_ROOT)
    if args.stage in ETAPAS_PENDIENTES:
        log.error("La etapa '%s' aún no está implementada (fase %s del plan)", args.stage, ETAPAS_PENDIENTES[args.stage])
        return 3
    if args.stage == "ml":
        return ejecutar_ml(settings, PROJECT_ROOT)
    if args.stage == "gold":
        return ejecutar_gold(settings, contrato, PROJECT_ROOT)
    if args.stage == "dq":
        return ejecutar_dq(settings, contrato, PROJECT_ROOT, args.layer)
    if args.stage == "silver":
        return ejecutar_silver(settings, contrato, PROJECT_ROOT, args.ingest_id)
    return ejecutar_bronze(settings, contrato, PROJECT_ROOT)


if __name__ == "__main__":
    sys.exit(main())
