"""Registro de ejecuciones del pipeline (data/metadata/run_log.parquet).

Una fila por etapa ejecutada. Lo consumen la trazabilidad y reglas DQ como DQ-VOL-001
(columnas mínimas: run_id, etapa, estado, filas, finalizado_utc). Nunca contiene datos de filas.
"""
from __future__ import annotations

import json
import os
import platform
import secrets
import subprocess
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import duckdb

ESTADOS = {"exitoso", "omitido", "fallido"}
ESQUEMA = """
    run_id VARCHAR, etapa VARCHAR, estado VARCHAR, iniciado_utc TIMESTAMP, finalizado_utc TIMESTAMP,
    filas BIGINT, source_sha256 VARCHAR, git_sha VARCHAR, python_version VARCHAR, duckdb_version VARCHAR,
    detalle VARCHAR
"""


def nuevo_run_id(ahora: datetime | None = None) -> str:
    ahora = ahora or datetime.now(UTC)
    return f"{ahora:%Y%m%dT%H%M%SZ}-{secrets.token_hex(4)}"


def git_sha(raiz: Path) -> str | None:
    try:
        salida = subprocess.run(["git", "-C", str(raiz), "rev-parse", "HEAD"],
                                capture_output=True, text=True, timeout=10, check=True)
        return salida.stdout.strip() or None
    except (OSError, subprocess.SubprocessError):
        return None


def git_con_cambios(raiz: Path) -> bool | None:
    """True si el árbol de trabajo tiene cambios sin confirmar (el git_sha no describe todo el código)."""
    try:
        salida = subprocess.run(["git", "-C", str(raiz), "status", "--porcelain", "--untracked-files=no"],
                                capture_output=True, text=True, timeout=10, check=True)
        return bool(salida.stdout.strip())
    except (OSError, subprocess.SubprocessError):
        return None


def ahora_utc() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


@dataclass
class RegistroEjecucion:
    run_id: str
    etapa: str
    estado: str
    iniciado_utc: datetime
    finalizado_utc: datetime
    filas: int | None = None
    source_sha256: str | None = None
    git_sha: str | None = None
    detalle: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.estado not in ESTADOS:
            raise ValueError(f"estado inválido: {self.estado}")


def registrar(ruta: Path, registro: RegistroEjecucion) -> None:
    """Agrega un registro al run_log con escritura atómica (archivo temporal + reemplazo)."""
    ruta.parent.mkdir(parents=True, exist_ok=True)
    tmp = ruta.with_name(ruta.name + ".tmp")
    con = duckdb.connect()
    try:
        con.execute(f"CREATE TABLE run_log ({ESQUEMA})")
        if ruta.exists():
            con.execute("INSERT INTO run_log SELECT * FROM read_parquet(?)", [str(ruta)])
        con.execute(
            "INSERT INTO run_log VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [registro.run_id, registro.etapa, registro.estado, registro.iniciado_utc, registro.finalizado_utc,
             registro.filas, registro.source_sha256, registro.git_sha, platform.python_version(),
             duckdb.__version__, json.dumps(registro.detalle, ensure_ascii=False, default=str)],
        )
        con.execute(f"COPY run_log TO '{_sql_literal(tmp)}' (FORMAT parquet)")
    finally:
        con.close()
    os.replace(tmp, ruta)


def leer(ruta: Path) -> list[dict[str, Any]]:
    if not ruta.exists():
        return []
    con = duckdb.connect()
    try:
        cursor = con.execute("SELECT * FROM read_parquet(?) ORDER BY finalizado_utc", [str(ruta)])
        columnas = [d[0] for d in cursor.description]
        return [dict(zip(columnas, fila, strict=True)) for fila in cursor.fetchall()]
    finally:
        con.close()


def _sql_literal(ruta: Path) -> str:
    return str(ruta).replace("'", "''")
