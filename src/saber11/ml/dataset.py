"""Conjunto de modelado y selección de variables (F8; plan §16.2 y §18).

La selección de predictoras es automática y conservadora: todo lo que pueda filtrar el
objetivo, identificar a una persona o duplicar la variable de agrupamiento se excluye con
un motivo registrado. El catálogo resultante se publica en el informe de F8, de modo que
las exclusiones son auditables y no dependen de una lista escrita a mano.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from itertools import combinations
from pathlib import Path
from typing import Any

import duckdb
import pandas as pd

# Prefijos de columnas que se derivan del objetivo o se calculan después de conocerlo (§18).
PREFIJOS_FUGA = ("punt_", "pct_", "nivel_", "flag_", "promedio_", "percentil_")
# Columnas que identifican una fila o una persona: nunca son predictoras.
SUFIJOS_IDENTIFICADOR = ("_id", "_pid")
NOMBRES_IDENTIFICADOR = frozenset({"estudiante_pid", "nrodoc"})
# Cuasi-identificadores de subconjuntos del colegio: no generalizan y acercan al efecto colegio.
NOMBRES_CUASI_IDENTIFICADOR = frozenset({"grupo"})

MOTIVOS = {
    "objetivo": "es la variable objetivo",
    "fuga": "se deriva del objetivo o se calcula después de conocerlo (§18)",
    "identificador": "identificador de fila o persona",
    "cuasi_identificador": "cuasi-identificador de subconjuntos del colegio (§16.2)",
    "agrupamiento": "se usa como grupo de validación, no como predictora (§16.3)",
    "varianza_cero": "valor constante en el conjunto",
    "confundida": "cada categoría pertenece a un solo colegio: su efecto no es separable (H3)",
}


class ErrorConjuntoML(ValueError):
    """El conjunto de modelado no cumple los controles de §16.2/§18."""


@dataclass(frozen=True)
class Variables:
    """Catálogo de variables del modelo: qué entra, qué no entra y por qué."""

    objetivo: str
    grupo: str
    categoricas: list[str]
    numericas: list[str]
    excluidas: dict[str, str] = field(default_factory=dict)
    dependencias: list[tuple[str, tuple[str, ...]]] = field(default_factory=list)

    @property
    def predictoras(self) -> list[str]:
        return [*self.categoricas, *self.numericas]

    def a_dict(self) -> dict[str, Any]:
        return {
            "objetivo": self.objetivo,
            "grupo": self.grupo,
            "categoricas": self.categoricas,
            "numericas": self.numericas,
            "excluidas": self.excluidas,
            "dependencias_funcionales": [
                {"columna": c, "determinada_por": list(d)} for c, d in self.dependencias
            ],
        }


def ruta_dataset(settings: dict[str, Any], raiz: Path) -> Path:
    return raiz / settings["paths"]["gold"] / "ml_dataset.parquet"


def cargar(settings: dict[str, Any], raiz: Path) -> pd.DataFrame:
    """Lee `gold.ml_dataset` en un DataFrame con orden determinista."""
    ruta = ruta_dataset(settings, raiz)
    if not ruta.exists():
        raise ErrorConjuntoML(
            f"No existe {ruta.relative_to(raiz).as_posix()}. Ejecute: run --stage gold"
        )
    con = duckdb.connect()
    try:
        return con.execute(
            "SELECT * FROM read_parquet(?) ORDER BY resultado_id", [str(ruta)]
        ).df()
    finally:
        con.close()


def _motivo_exclusion(columna: str, objetivo: str, grupo: str) -> str | None:
    minus = columna.lower()
    if columna == objetivo:
        return "objetivo"
    if columna == grupo:
        return "agrupamiento"
    if minus.startswith(PREFIJOS_FUGA):
        return "fuga"
    if minus in NOMBRES_IDENTIFICADOR or minus.endswith(SUFIJOS_IDENTIFICADOR):
        return "identificador"
    if minus in NOMBRES_CUASI_IDENTIFICADOR:
        return "cuasi_identificador"
    return None


def _confundidas_con_grupo(df: pd.DataFrame, columnas: list[str], grupo: str) -> set[str]:
    """Categóricas cuyo valor identifica un único colegio (confusión H3: efecto no separable)."""
    return {
        c for c in columnas
        if df.groupby(c, observed=True)[grupo].nunique().min() < 2
    }


def dependencias_funcionales(
    df: pd.DataFrame, columnas: list[str], max_orden: int = 2
) -> list[tuple[str, tuple[str, ...]]]:
    """Columnas determinadas por la combinación de otras (alias del diseño experimental).

    Una columna alias no aporta información nueva: el modelo reparte su crédito con las
    columnas que la determinan, así que sus coeficientes y su SHAP no son interpretables
    por separado. Se reporta, no se excluye: excluirla no cambia las predicciones.
    """
    encontradas: list[tuple[str, tuple[str, ...]]] = []
    for objetivo in columnas:
        otras = [c for c in columnas if c != objetivo]
        for orden in range(1, max_orden + 1):
            hallado = False
            for combo in combinations(otras, orden):
                if df.groupby(list(combo), observed=True)[objetivo].nunique().max() == 1:
                    encontradas.append((objetivo, combo))
                    hallado = True
                    break
            if hallado:
                break
    return encontradas


def seleccionar_variables(df: pd.DataFrame, settings: dict[str, Any]) -> Variables:
    """Clasifica las columnas del conjunto en predictoras y excluidas con su motivo."""
    objetivo = settings["ml"]["target"]
    grupo = settings["ml"]["cv_group_col"]
    for requerida in (objetivo, grupo):
        if requerida not in df.columns:
            raise ErrorConjuntoML(f"Falta la columna '{requerida}' en el conjunto de modelado")

    excluidas: dict[str, str] = {}
    candidatas: list[str] = []
    for columna in df.columns:
        motivo = _motivo_exclusion(columna, objetivo, grupo)
        if motivo:
            excluidas[columna] = MOTIVOS[motivo]
        elif df[columna].nunique(dropna=False) <= 1:
            excluidas[columna] = MOTIVOS["varianza_cero"]
        else:
            candidatas.append(columna)

    categoricas = [c for c in candidatas if not pd.api.types.is_numeric_dtype(df[c])]
    for columna in sorted(_confundidas_con_grupo(df, categoricas, grupo)):
        excluidas[columna] = MOTIVOS["confundida"]
        categoricas.remove(columna)
        candidatas.remove(columna)
    numericas = [c for c in candidatas if c not in categoricas]

    if not candidatas:
        raise ErrorConjuntoML("No queda ninguna variable predictora tras aplicar las exclusiones")
    return Variables(
        objetivo=objetivo,
        grupo=grupo,
        categoricas=categoricas,
        numericas=numericas,
        excluidas=excluidas,
        dependencias=dependencias_funcionales(df, categoricas),
    )


def separar_temporal(
    df: pd.DataFrame, anio_test: int, columna_anio: str = "anio"
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Divide en entrenamiento (< `anio_test`) y prueba (`anio_test`), con los controles de §18."""
    if columna_anio not in df.columns:
        raise ErrorConjuntoML(f"Falta la columna temporal '{columna_anio}'")
    entrena = df[df[columna_anio] < anio_test].reset_index(drop=True)
    prueba = df[df[columna_anio] == anio_test].reset_index(drop=True)
    if entrena.empty or prueba.empty:
        raise ErrorConjuntoML(
            f"La separación temporal en {anio_test} deja un conjunto vacío "
            f"(entrenamiento={len(entrena)}, prueba={len(prueba)})"
        )
    if entrena[columna_anio].max() >= prueba[columna_anio].min():
        raise ErrorConjuntoML("El entrenamiento contiene años del conjunto de prueba (§18)")
    return entrena, prueba


def colegios_retenidos(df: pd.DataFrame, settings: dict[str, Any]) -> list[str]:
    """Colegios que se excluyen del entrenamiento para probar generalización a centros nuevos.

    Se toma la lista de `settings`; si no está o no existe algún colegio, se elige de forma
    determinista el primero de cada naturaleza en orden alfabético.
    """
    grupo = settings["ml"]["cv_group_col"]
    configurados = settings["ml"].get("colegios_retenidos") or []
    disponibles = set(df[grupo].unique())
    if configurados and set(configurados) <= disponibles:
        return list(configurados)
    if "naturaleza_colegio" not in df.columns:
        return sorted(disponibles)[:2]
    primeros = (
        df[[grupo, "naturaleza_colegio"]]
        .drop_duplicates()
        .sort_values([grupo])
        .groupby("naturaleza_colegio", observed=True)[grupo]
        .first()
    )
    return sorted(primeros.tolist())
