"""Capa Bronze (fase F2): preservación íntegra y trazable de la fuente.

1. Valida el contrato de la fuente (si falla, no escribe nada en Bronze).
2. Calcula el SHA-256 del archivo; si ese hash ya fue ingerido, la etapa se omite (idempotencia).
3. Copia inmutable en data/bronze/raw/<sha256>.csv (verificada por hash, solo lectura).
4. Parquet con todas las columnas como VARCHAR + _ingest_id, _source_file, _source_sha256, _ingested_at
   en data/bronze/bronze_resultados/ingest_id=<run_id>/part-0.parquet (escrito en staging y
   publicado por renombrado, para no dejar particiones a medio escribir).

Bronze contiene PII: zona restringida, excluida de git y nunca conectada a Power BI.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import stat
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import duckdb

from saber11.ingest.contract import ContratoFuenteError, ResultadoContrato, validar_fuente
from saber11.logging_utils import setup_logger

COLUMNAS_METADATOS = ("_ingest_id", "_source_file", "_source_sha256", "_ingested_at")
log = setup_logger("saber11.bronze")


@dataclass
class ResultadoBronze:
    estado: str                 # exitoso | omitido
    run_id: str
    source_sha256: str
    filas: int
    ingest_id: str              # ingest_id donde están los datos (el previo si se omitió)
    ruta_parquet: Path | None
    ruta_raw: Path
    contrato: ResultadoContrato

    def detalle(self) -> dict[str, Any]:
        return {"ingest_id": self.ingest_id, "archivo": self.contrato.archivo,
                "columnas": self.contrato.columnas, "filas_contrato": self.contrato.filas_datos}


def sha256_archivo(ruta: Path) -> str:
    h = hashlib.sha256()
    with ruta.open("rb") as f:
        for bloque in iter(lambda: f.read(1 << 20), b""):
            h.update(bloque)
    return h.hexdigest()


def _lit(valor: object) -> str:
    """Literal SQL de texto escapado (solo para rutas y metadatos controlados por el pipeline)."""
    return "'" + str(valor).replace("'", "''") + "'"


def _rutas(raiz: Path, settings: dict[str, Any]) -> dict[str, Path]:
    p = settings["paths"]
    bronze = raiz / p["bronze"]
    return {
        "bronze": bronze,
        "raw": bronze / "raw",
        "dataset": bronze / settings["lakehouse"]["bronze_table"],
        "tmp": raiz / p["tmp"],
        "reportes_calidad": raiz / p["reports"] / "quality",
    }


def ingest_id_existente(dataset: Path, sha: str) -> str | None:
    archivos = sorted(dataset.glob("ingest_id=*/*.parquet"))
    if not archivos:
        return None
    con = duckdb.connect()
    try:
        fila = con.execute(
            "SELECT any_value(_ingest_id) FROM read_parquet(?) WHERE _source_sha256 = ?",
            [[str(a) for a in archivos], sha],
        ).fetchone()
    finally:
        con.close()
    return fila[0] if fila and fila[0] else None


def _copiar_raw_inmutable(fuente: Path, destino: Path, sha: str) -> None:
    if destino.exists():
        if sha256_archivo(destino) != sha:
            raise RuntimeError(f"copia raw corrupta: el hash de {destino.name} no coincide con su nombre")
        return
    destino.parent.mkdir(parents=True, exist_ok=True)
    tmp = destino.with_name(destino.name + ".part")
    shutil.copyfile(fuente, tmp)
    if sha256_archivo(tmp) != sha:
        tmp.unlink(missing_ok=True)
        raise RuntimeError("la copia raw no coincide con el hash de la fuente")
    os.replace(tmp, destino)
    destino.chmod(stat.S_IREAD)


def escribir_reporte_contrato(resultado: ResultadoContrato, run_id: str, carpeta: Path) -> Path:
    carpeta.mkdir(parents=True, exist_ok=True)
    ruta = carpeta / f"source_check_{run_id}.json"
    ruta.write_text(json.dumps({"run_id": run_id, **resultado.a_dict()}, ensure_ascii=False, indent=2),
                    encoding="utf-8")
    return ruta


def ingerir_bronze(fuente: Path, settings: dict[str, Any], contrato: dict[str, Any], run_id: str,
                   raiz: Path, momento: datetime) -> ResultadoBronze:
    rutas = _rutas(raiz, settings)
    resultado_contrato = validar_fuente(fuente, contrato)
    escribir_reporte_contrato(resultado_contrato, run_id, rutas["reportes_calidad"])
    if not resultado_contrato.aprobado:
        raise ContratoFuenteError(resultado_contrato)

    sha = sha256_archivo(fuente)
    ruta_raw = rutas["raw"] / f"{sha}.csv"
    previo = ingest_id_existente(rutas["dataset"], sha)
    if previo:
        log.info("Fuente sha256=%s ya ingerida en ingest_id=%s; etapa omitida", sha[:12], previo)
        _copiar_raw_inmutable(fuente, ruta_raw, sha)
        return ResultadoBronze("omitido", run_id, sha, resultado_contrato.filas_datos, previo, None,
                               ruta_raw, resultado_contrato)

    _copiar_raw_inmutable(fuente, ruta_raw, sha)
    staging = rutas["dataset"] / f".staging_{run_id}"
    final = rutas["dataset"] / f"ingest_id={run_id}"
    shutil.rmtree(staging, ignore_errors=True)
    staging.mkdir(parents=True)
    rutas["tmp"].mkdir(parents=True, exist_ok=True)
    spec = contrato["source_contract"]

    con = duckdb.connect()
    try:
        con.execute(f"SET temp_directory = {_lit(rutas['tmp'])}")
        con.execute(f"""
            COPY (
                SELECT *,
                       {_lit(run_id)} AS _ingest_id,
                       {_lit(fuente.name)} AS _source_file,
                       {_lit(sha)} AS _source_sha256,
                       TIMESTAMP {_lit(momento.strftime('%Y-%m-%d %H:%M:%S'))} AS _ingested_at
                FROM read_csv({_lit(ruta_raw)}, delim={_lit(spec['delimiter'])}, header=true,
                              all_varchar=true, encoding={_lit(spec['encoding'])}, quote='"')
            ) TO {_lit(staging / 'part-0.parquet')} (FORMAT parquet, COMPRESSION snappy)
        """)
        filas, columnas = con.execute(
            "SELECT count(*), (SELECT count(*) FROM (DESCRIBE SELECT * FROM read_parquet(?))) "
            "FROM read_parquet(?)", [str(staging / "part-0.parquet")] * 2).fetchone()
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    finally:
        con.close()

    esperadas = spec["expected_columns_count"] + len(COLUMNAS_METADATOS)
    if filas != resultado_contrato.filas_datos or columnas != esperadas:
        shutil.rmtree(staging, ignore_errors=True)
        raise RuntimeError(f"verificación Bronze fallida: filas {filas} vs {resultado_contrato.filas_datos}, "
                           f"columnas {columnas} vs {esperadas}")
    os.replace(staging, final)
    log.info("Bronze escrito: ingest_id=%s filas=%d sha256=%s", run_id, filas, sha[:12])
    return ResultadoBronze("exitoso", run_id, sha, filas, run_id, final / "part-0.parquet",
                           ruta_raw, resultado_contrato)
