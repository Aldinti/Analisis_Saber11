"""Capa Gold (fase F4): modelo estrella, agregados con supresión, dataset ML y seguridad RLS.

Entrada: `data/silver/silver_resultados.parquet` aprobado por el quality gate de Silver.
Salida (reemplazo completo de `data/gold/`, publicado por intercambio de carpeta):

    dim_tiempo, dim_colegio, dim_ubicacion, dim_perfil_estudiante, dim_area          .parquet
    fact_resultado/anio=*/periodo=*/*.parquet    (anio y periodo también DENTRO de los archivos, ADR-0005)
    fact_resultado_area, agg_operativo_colegio, agg_benchmark_distrito,
    seguridad_rectores, ml_dataset                                                   .parquet

La lógica relacional está en sql/gold/0*.sql. Antes de publicar se verifican los criterios de
aceptación del plan y las reglas DQ de la capa Gold; si algo falla, Gold vigente no se toca.
"""
from __future__ import annotations

import os
import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import duckdb

from saber11.config import PROJECT_ROOT
from saber11.logging_utils import setup_logger
from saber11.quality.engine import evaluar_regla, reglas_de_capa
from saber11.quality.rules import cargar_reglas, parametros_desde_settings, resolver_sql

SQL_DIR = PROJECT_ROOT / "sql" / "gold"
PASOS_SQL = ("01_dimensiones.sql", "02_hechos.sql", "03_agregados.sql", "04_ml_y_seguridad.sql")
TABLAS_ARCHIVO = (
    "dim_tiempo", "dim_colegio", "dim_ubicacion", "dim_perfil_estudiante", "dim_area",
    "fact_resultado_area", "agg_operativo_colegio", "agg_benchmark_distrito", "seguridad_rectores", "ml_dataset",
)
TABLA_PARTICIONADA = "fact_resultado"
TABLAS_GOLD = (*TABLAS_ARCHIVO, TABLA_PARTICIONADA)
AREAS_SILVER = ("punt_lectura_critica", "punt_matematicas", "punt_sociales", "punt_ciencias", "punt_ingles")
PATRON_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
log = setup_logger("saber11.gold")


class VerificacionGoldError(RuntimeError):
    """Gold no cumple sus criterios de aceptación; no se publica."""


@dataclass
class ResultadoGold:
    filas_silver: int
    filas: dict[str, int] = field(default_factory=dict)
    celdas_suprimidas: dict[str, int] = field(default_factory=dict)
    reglas_dq: dict[str, str] = field(default_factory=dict)
    origen_seguridad: str = ""
    ruta: Path | None = None

    def detalle(self) -> dict[str, Any]:
        return {"filas_silver": self.filas_silver, "filas": self.filas, "celdas_suprimidas": self.celdas_suprimidas,
                "reglas_dq": self.reglas_dq, "origen_seguridad": self.origen_seguridad}


def _lit(valor: object) -> str:
    return "'" + str(valor).replace("'", "''") + "'"


def fuente_seguridad(settings: dict[str, Any], raiz: Path) -> Path:
    """CSV real de seguridad si existe; si no, el ejemplo ficticio versionado."""
    seg = settings["security"]
    real = raiz / seg["source_file"]
    return real if real.exists() else raiz / seg["example_file"]


def _cargar_seguridad(con: duckdb.DuckDBPyConnection, ruta: Path) -> None:
    if not ruta.exists():
        raise FileNotFoundError(f"No existe el archivo de seguridad {ruta}")
    con.execute(f"""
        CREATE OR REPLACE TABLE seguridad_fuente AS
        SELECT email_rector, nombre_colegio
        FROM read_csv({_lit(ruta)}, header = true, all_varchar = true)
    """)
    invalidos = [e for (e,) in con.execute("SELECT email_rector FROM seguridad_fuente").fetchall()
                 if not e or not PATRON_EMAIL.match(e.strip())]
    if invalidos:
        raise VerificacionGoldError(f"{len(invalidos)} correos inválidos en {ruta.name}")


def construir_tablas(con: duckdb.DuckDBPyConnection, parquet_silver: Path, ruta_seguridad: Path,
                     settings: dict[str, Any]) -> None:
    con.execute(f"CREATE OR REPLACE VIEW silver_resultados AS SELECT * FROM read_parquet({_lit(parquet_silver)})")
    _cargar_seguridad(con, ruta_seguridad)
    parametros = parametros_desde_settings(settings)
    for paso in PASOS_SQL:
        con.execute(resolver_sql((SQL_DIR / paso).read_text(encoding="utf-8"), parametros))


def verificar(con: duckdb.DuckDBPyConnection, settings: dict[str, Any], contrato: dict[str, Any]) -> ResultadoGold:
    errores: list[str] = []
    uno = lambda sql: con.execute(sql).fetchone()[0]  # noqa: E731

    filas_silver = uno("SELECT count(*) FROM silver_resultados")
    filas = {t: uno(f"SELECT count(*) FROM {t}") for t in TABLAS_GOLD}
    if filas["fact_resultado"] != filas_silver:
        errores.append(f"fact_resultado ({filas['fact_resultado']}) != filas Silver ({filas_silver})")
    if filas["fact_resultado_area"] != 5 * filas["fact_resultado"]:
        errores.append("fact_resultado_area no tiene 5 filas por evaluación")
    if filas["ml_dataset"] != filas["fact_resultado"]:
        errores.append("ml_dataset no tiene una fila por evaluación")

    # Claves únicas y sin colisiones de hash (una clave por clave natural).
    for tabla, clave, natural in (
        ("dim_tiempo", "tiempo_id", "anio, periodo"),
        ("dim_colegio", "colegio_id", "nombre_colegio"),
        ("dim_ubicacion", "ubicacion_id", "pais, departamento, municipio, zona"),
        ("dim_perfil_estudiante", "perfil_id", "sexo, estrato"),
        ("fact_resultado", "resultado_id", "resultado_id"),
    ):
        n, claves, naturales = con.execute(
            f"SELECT count(*), count(DISTINCT {clave}), count(DISTINCT ({natural})) FROM {tabla}").fetchone()
        if not n == claves == naturales:
            errores.append(f"{tabla}: filas={n} claves={claves} claves_naturales={naturales}")

    # Promedios Gold = promedios Silver por año y colegio (Global y cada área).
    comparaciones = ", ".join(
        f"max(abs(s_{c} - g_{c}))" for c in ("puntaje_global", *AREAS_SILVER))
    columnas_s = ", ".join(f"avg({c}) AS s_{c}" for c in ("puntaje_global", *AREAS_SILVER))
    columnas_g = ", ".join(f"avg(f.{c}) AS g_{c}" for c in ("puntaje_global", *AREAS_SILVER))
    diferencias = con.execute(f"""
        WITH s AS (SELECT anio, nombre_colegio, {columnas_s} FROM silver_resultados GROUP BY ALL),
             g AS (SELECT f.anio, c.nombre_colegio, {columnas_g}
                   FROM fact_resultado f JOIN dim_colegio c USING (colegio_id) GROUP BY ALL)
        SELECT count(*) FILTER (WHERE g.anio IS NULL), {comparaciones}
        FROM s LEFT JOIN g USING (anio, nombre_colegio)""").fetchone()
    if diferencias[0] or any(d is None or d > 1e-9 for d in diferencias[1:]):
        errores.append(f"promedios Gold distintos de Silver: {diferencias}")
    area_vs_ancho = uno("""
        SELECT count(*) FROM fact_resultado_area fa JOIN fact_resultado f USING (resultado_id)
        WHERE fa.puntaje <> CASE fa.area_id WHEN 1 THEN f.punt_lectura_critica WHEN 2 THEN f.punt_matematicas
              WHEN 3 THEN f.punt_sociales WHEN 4 THEN f.punt_ciencias WHEN 5 THEN f.punt_ingles END""")
    if area_vs_ancho:
        errores.append(f"{area_vs_ancho} puntajes por área no coinciden con fact_resultado")

    # Totales operativos coherentes con los hechos.
    totales = uno("""
        SELECT count(*) FROM agg_operativo_colegio a
        JOIN (SELECT colegio_id, anio, count(*) AS n FROM fact_resultado GROUP BY ALL) f USING (colegio_id, anio)
        WHERE a.dimension = 'Total' AND a.n <> f.n""")
    if totales:
        errores.append(f"{totales} totales de agg_operativo_colegio no coinciden con fact_resultado")

    # Sin seudónimo en Gold (el plan no lo lleva a Power BI).
    con_pid = [t for t in TABLAS_GOLD
               if "estudiante_pid" in {r[0] for r in con.execute(f"DESCRIBE {t}").fetchall()}]
    if con_pid:
        errores.append(f"tablas Gold con estudiante_pid: {con_pid}")

    # Reglas DQ de la capa Gold (integridad referencial y privacidad) sobre las tablas en memoria.
    ctx = {"tablas": set(TABLAS_GOLD)}
    parametros = parametros_desde_settings(settings)
    reglas = {r["id"]: evaluar_regla(con, r, contrato, ctx, parametros) for r in reglas_de_capa(cargar_reglas(), "gold")}
    errores += [f"{rid} {r.estado} valor={r.valor} {r.mensaje}".strip() for rid, r in reglas.items() if r.estado != "PASA"]

    if errores:
        raise VerificacionGoldError("; ".join(errores))
    suprimidas = {t: uno(f"SELECT count(*) FILTER (WHERE suprimido) FROM {t}")
                  for t in ("agg_operativo_colegio", "agg_benchmark_distrito")}
    return ResultadoGold(filas_silver, filas, suprimidas, {rid: r.estado for rid, r in reglas.items()})


def escribir(con: duckdb.DuckDBPyConnection, carpeta: Path) -> None:
    carpeta.mkdir(parents=True)
    for tabla in TABLAS_ARCHIVO:
        con.execute(f"COPY {tabla} TO {_lit(carpeta / f'{tabla}.parquet')} (FORMAT parquet, COMPRESSION snappy)")
    con.execute(f"""
        COPY {TABLA_PARTICIONADA} TO {_lit(carpeta / TABLA_PARTICIONADA)}
        (FORMAT parquet, COMPRESSION snappy, PARTITION_BY (anio, periodo), WRITE_PARTITION_COLUMNS true)""")


def verificar_escritura(carpeta: Path, filas_fact: int) -> None:
    """Criterio del plan: la lectura hive devuelve anio y periodo; y (ADR-0005) también están dentro de los archivos."""
    patron = _lit((carpeta / TABLA_PARTICIONADA / "**" / "*.parquet").as_posix())
    con = duckdb.connect()
    try:
        n, columnas_hive = con.execute(
            f"SELECT count(*), (SELECT list(column_name) FROM (DESCRIBE SELECT * FROM read_parquet({patron}, hive_partitioning = true))) "
            f"FROM read_parquet({patron}, hive_partitioning = true)").fetchone()
        columnas_archivo = [r[0] for r in con.execute(
            f"DESCRIBE SELECT * FROM read_parquet({patron}, hive_partitioning = false)").fetchall()]
    finally:
        con.close()
    faltan = [c for c in ("anio", "periodo") if c not in columnas_hive or c not in columnas_archivo]
    if n != filas_fact or faltan:
        raise VerificacionGoldError(f"fact_resultado escrito: filas={n} (esperadas {filas_fact}); columnas faltantes={faltan}")


def publicar(staging: Path, destino: Path) -> None:
    """Intercambia la carpeta Gold completa: la versión previa solo se borra tras publicar la nueva."""
    previo = destino.with_name(f".{destino.name}_previo_{staging.name.rsplit('_', 1)[-1]}")
    if destino.exists():
        os.replace(destino, previo)
    try:
        os.replace(staging, destino)
    except OSError:
        if previo.exists():
            os.replace(previo, destino)
        raise
    shutil.rmtree(previo, ignore_errors=True)


def construir_gold(settings: dict[str, Any], contrato: dict[str, Any], raiz: Path, run_id: str,
                   ruta_seguridad: Path | None = None) -> ResultadoGold:
    p = settings["paths"]
    parquet_silver = raiz / p["silver"] / f"{settings['lakehouse']['silver_table']}.parquet"
    if not parquet_silver.exists():
        raise FileNotFoundError(f"No existe {parquet_silver}; ejecute silver y el quality gate")
    ruta_seguridad = ruta_seguridad or fuente_seguridad(settings, raiz)
    destino = raiz / p["gold"]
    staging = destino.with_name(f".{destino.name}_staging_{run_id.replace('-', '')}")
    shutil.rmtree(staging, ignore_errors=True)
    (raiz / p["tmp"]).mkdir(parents=True, exist_ok=True)

    con = duckdb.connect()
    try:
        con.execute(f"SET temp_directory = {_lit(raiz / p['tmp'])}")
        construir_tablas(con, parquet_silver, ruta_seguridad, settings)
        resultado = verificar(con, settings, contrato)
        escribir(con, staging)
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    finally:
        con.close()
    try:
        verificar_escritura(staging, resultado.filas["fact_resultado"])
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    publicar(staging, destino)
    resultado.origen_seguridad = (ruta_seguridad.relative_to(raiz).as_posix()
                                  if ruta_seguridad.is_relative_to(raiz) else ruta_seguridad.name)
    resultado.ruta = destino
    log.info("Gold publicado: fact=%d suprimidas=%s seguridad=%s", resultado.filas["fact_resultado"],
             resultado.celdas_suprimidas, resultado.origen_seguridad)
    return resultado
