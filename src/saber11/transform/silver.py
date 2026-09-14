"""Capa Silver (fase F3): limpieza, tipado, estandarización y seudonimización.

Entrada: una partición Bronze (`ingest_id`). Salida (reemplazo completo, publicación atómica):
    data/silver/silver_resultados.parquet   filas válidas, sin PII directa
    data/silver/silver_rechazos.parquet     cuarentena con motivo_rechazo (sin PII directa)

La lógica relacional está en sql/silver/0*.sql; aquí se orquesta, se calcula el seudónimo
HMAC-SHA-256 (la clave nunca entra en el texto SQL) y se verifican los criterios de aceptación
antes de publicar.
"""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import duckdb
from duckdb.sqltypes import VARCHAR

from saber11.config import PROJECT_ROOT
from saber11.logging_utils import setup_logger
from saber11.metadata import run_log
from saber11.security.pseudonymize import pseudonymize_id
from saber11.transform.naming import normalize_colname

SQL_DIR = PROJECT_ROOT / "sql" / "silver"
PASOS_SQL_PREVIOS = ("01_texto.sql", "02_tipado.sql")
PASOS_SQL_POSTERIORES = ("03_evaluacion.sql", "04_salidas.sql")

# normalize_colname(columna Bronze) -> nombre Silver del plan (§6, §8 F3)
RENOMBRES = {
    "global": "puntaje_global",
    "lectura_critica": "punt_lectura_critica",
    "matematicas": "punt_matematicas",
    "sociales_y_ciudadana": "punt_sociales",
    "ciencias_naturales": "punt_ciencias",
    "ingles": "punt_ingles",
    "modelopedag_colegio": "modelo_pedagogico",
}
COLUMNAS_PII = ("nrodoc", "nombre1", "nombre2", "apellido1", "apellido2")
COLUMNAS_SILVER = (
    "anio", "periodo", "jornada", "pais", "departamento", "municipio", "zona", "estrato",
    "nombre_colegio", "naturaleza_colegio", "modelo_pedagogico", "estudiante_pid", "sexo", "grupo",
    "puntaje_global", "punt_lectura_critica", "punt_matematicas", "punt_sociales", "punt_ciencias",
    "punt_ingles", "flag_atipico", "flag_inconsistencia_global", "_ingest_id", "_source_sha256",
)
TIPOS_SILVER = {
    "anio": "SMALLINT", "estrato": "TINYINT", "puntaje_global": "SMALLINT",
    **dict.fromkeys(("punt_lectura_critica", "punt_matematicas", "punt_sociales", "punt_ciencias", "punt_ingles"), "TINYINT"),
    "flag_atipico": "BOOLEAN", "flag_inconsistencia_global": "BOOLEAN",
}
PATRON_SNAKE_ASCII = re.compile(r"^_?[a-z][a-z0-9_]*$")
log = setup_logger("saber11.silver")


class VerificacionSilverError(RuntimeError):
    """Silver no cumple sus criterios de aceptación; no se publica."""


@dataclass
class ResultadoSilver:
    ingest_id: str
    source_sha256: str
    filas_bronze: int
    filas_silver: int
    filas_rechazo: int
    motivos: dict[str, int] = field(default_factory=dict)
    flags: dict[str, int] = field(default_factory=dict)
    rutas: dict[str, Path] = field(default_factory=dict)

    def detalle(self) -> dict[str, Any]:
        return {"ingest_id": self.ingest_id, "filas_bronze": self.filas_bronze,
                "filas_rechazo": self.filas_rechazo, "motivos_rechazo": self.motivos, "flags": self.flags}


def nombre_silver(columna_bronze: str) -> str:
    base = normalize_colname(columna_bronze)
    return RENOMBRES.get(base, base)


def _lit(valor: object) -> str:
    return "'" + str(valor).replace("'", "''") + "'"


def ingest_id_vigente(ruta_run_log: Path, dataset_bronze: Path) -> str:
    """Ingesta Bronze de la fuente actual: la del último bronze exitoso/omitido; si no hay registro, la más reciente."""
    for registro in reversed(run_log.leer(ruta_run_log)):
        if registro["etapa"] == "bronze" and registro["estado"] in {"exitoso", "omitido"}:
            ingest_id = json.loads(registro["detalle"] or "{}").get("ingest_id")
            if ingest_id and (dataset_bronze / f"ingest_id={ingest_id}").is_dir():
                return ingest_id
    particiones = sorted(p.name.removeprefix("ingest_id=") for p in dataset_bronze.glob("ingest_id=*") if p.is_dir())
    if not particiones:
        raise FileNotFoundError(f"No hay particiones Bronze en {dataset_bronze}")
    return particiones[-1]


def _ejecutar_sql(con: duckdb.DuckDBPyConnection, archivo: str) -> None:
    con.execute((SQL_DIR / archivo).read_text(encoding="utf-8"))


def construir_silver(parquet_bronze: list[Path], columnas_contrato: list[str], clave_hmac: str,
                     destino: Path, tmp: Path) -> ResultadoSilver:
    """Construye y publica Silver a partir de archivos Parquet Bronze (todas las columnas VARCHAR)."""
    if not clave_hmac:
        raise ValueError("Se requiere la clave HMAC para seudonimizar")
    destino.mkdir(parents=True, exist_ok=True)
    tmp.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect()
    try:
        con.execute(f"SET temp_directory = {_lit(tmp)}")
        con.execute("SET preserve_insertion_order = true")
        seleccion = ",\n".join(f'"{c.replace(chr(34), chr(34) * 2)}" AS {nombre_silver(c)}' for c in columnas_contrato)
        archivos = "[" + ", ".join(_lit(p) for p in parquet_bronze) + "]"
        con.execute(f"""
            CREATE OR REPLACE VIEW bronze_normalizado AS
            SELECT {seleccion}, _ingest_id, _source_sha256,
                   row_number() OVER () AS _fila_fuente
            FROM read_parquet({archivos})
        """)
        for paso in PASOS_SQL_PREVIOS:
            _ejecutar_sql(con, paso)

        con.create_function("hmac_pid", lambda doc: pseudonymize_id(clave_hmac, doc),
                            [VARCHAR], VARCHAR, side_effects=False)
        con.execute("ALTER TABLE s_tipado ADD COLUMN estudiante_pid VARCHAR")
        con.execute("UPDATE s_tipado SET estudiante_pid = hmac_pid(CAST(nrodoc AS VARCHAR)) WHERE nrodoc IS NOT NULL")
        con.remove_function("hmac_pid")

        for paso in PASOS_SQL_POSTERIORES:
            _ejecutar_sql(con, paso)

        resultado = _verificar(con, columnas_contrato)
        rutas = {"silver": destino / "silver_resultados.parquet", "rechazos": destino / "silver_rechazos.parquet"}
        temporales = {k: tmp / f"{v.stem}.parquet.tmp" for k, v in rutas.items()}
        con.execute(f"COPY silver_resultados TO {_lit(temporales['silver'])} (FORMAT parquet, COMPRESSION snappy)")
        con.execute(f"COPY silver_rechazos TO {_lit(temporales['rechazos'])} (FORMAT parquet, COMPRESSION snappy)")
    finally:
        con.close()
    for clave, ruta in rutas.items():
        os.replace(temporales[clave], ruta)
    resultado.rutas = rutas
    return resultado


def _verificar(con: duckdb.DuckDBPyConnection, columnas_contrato: list[str]) -> ResultadoSilver:
    errores: list[str] = []
    esquema = dict(con.execute(
        "SELECT column_name, data_type FROM information_schema.columns "
        "WHERE table_name = 'silver_resultados' ORDER BY ordinal_position").fetchall())
    columnas = tuple(esquema)
    if columnas != COLUMNAS_SILVER:
        errores.append(f"columnas Silver distintas al plan: {columnas}")
    errores += [f"tipo de {c}: {esquema.get(c)} (esperado {t})" for c, t in TIPOS_SILVER.items() if esquema.get(c) != t]
    rechazo_cols = [r[0] for r in con.execute(
        "SELECT column_name FROM information_schema.columns WHERE table_name = 'silver_rechazos'").fetchall()]
    for tabla, cols in (("silver_resultados", columnas), ("silver_rechazos", rechazo_cols)):
        pii = [c for c in cols if c in COLUMNAS_PII]
        no_snake = [c for c in cols if not PATRON_SNAKE_ASCII.match(c)]
        if pii:
            errores.append(f"{tabla} contiene PII directa: {pii}")
        if no_snake:
            errores.append(f"{tabla} tiene nombres no snake_case ASCII: {no_snake}")

    filas_bronze = con.execute("SELECT count(*) FROM bronze_normalizado").fetchone()[0]
    filas_silver = con.execute("SELECT count(*) FROM silver_resultados").fetchone()[0]
    filas_rechazo = con.execute("SELECT count(*) FROM silver_rechazos").fetchone()[0]
    if filas_silver + filas_rechazo != filas_bronze:
        errores.append(f"filas_silver + filas_rechazo ({filas_silver} + {filas_rechazo}) != filas_bronze ({filas_bronze})")

    pid_invalidos, duplicados = con.execute("""
        SELECT count(*) FILTER (WHERE estudiante_pid IS NULL OR NOT regexp_matches(estudiante_pid, '^[0-9a-f]{64}$')),
               count(*) - count(DISTINCT (estudiante_pid, anio, periodo))
        FROM silver_resultados""").fetchone()
    if pid_invalidos:
        errores.append(f"{pid_invalidos} estudiante_pid nulos o sin formato hex de 64")
    if duplicados:
        errores.append(f"{duplicados} evaluaciones duplicadas (estudiante_pid, anio, periodo)")
    if filas_bronze and not filas_silver:
        errores.append("Silver quedó vacío")
    if errores:
        raise VerificacionSilverError("; ".join(errores))

    ingest_id, sha = con.execute("SELECT any_value(_ingest_id), any_value(_source_sha256) FROM bronze_normalizado").fetchone()
    motivos = dict(con.execute("""
        SELECT motivo, count(*) FROM (SELECT unnest(string_split(motivo_rechazo, ';')) AS motivo FROM silver_rechazos)
        GROUP BY motivo ORDER BY motivo""").fetchall())
    flags = dict(zip(("flag_atipico", "flag_inconsistencia_global", "sexo_nulo", "estrato_nulo"), con.execute("""
        SELECT count(*) FILTER (WHERE flag_atipico), count(*) FILTER (WHERE flag_inconsistencia_global),
               count(*) FILTER (WHERE sexo IS NULL), count(*) FILTER (WHERE estrato IS NULL)
        FROM silver_resultados""").fetchone(), strict=True))
    return ResultadoSilver(ingest_id, sha, filas_bronze, filas_silver, filas_rechazo, motivos, flags)


def ingerir_silver(settings: dict[str, Any], contrato: dict[str, Any], raiz: Path, clave_hmac: str,
                   ingest_id: str | None = None) -> ResultadoSilver:
    p = settings["paths"]
    dataset = raiz / p["bronze"] / settings["lakehouse"]["bronze_table"]
    ingest_id = ingest_id or ingest_id_vigente(raiz / p["metadata"] / "run_log.parquet", dataset)
    archivos = sorted((dataset / f"ingest_id={ingest_id}").glob("*.parquet"))
    if not archivos:
        raise FileNotFoundError(f"La partición Bronze ingest_id={ingest_id} no tiene archivos Parquet")
    columnas = [c["name"] for c in contrato["source_contract"]["columns"]]
    log.info("Construyendo Silver desde ingest_id=%s", ingest_id)
    resultado = construir_silver(archivos, columnas, clave_hmac, raiz / p["silver"], raiz / p["tmp"])
    log.info("Silver publicado: filas=%d rechazos=%d flags=%s", resultado.filas_silver, resultado.filas_rechazo,
             resultado.flags)
    return resultado
