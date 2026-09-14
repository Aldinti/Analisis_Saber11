"""Amplía ResultadosICFES.csv con registros FICTICIOS.

Los datos originales son inventados; este script agrega más registros inventados para
resolver los hallazgos del perfilamiento (H2, H3, H7, H8) sin alterar las filas existentes,
con un diseño que permite a los modelos y a SHAP separar los efectos de cada factor:

* Colegios: fracción ortogonal 2^(3-1) de naturaleza × zona × periodo, con los 4 modelos
  pedagógicos en cada celda (16 colegios). Todo par de factores de colegio queda balanceado.
* Estudiantes: en cada colegio-año, estrato y sexo siguen la MISMA distribución objetivo
  (independientes entre sí y de los factores de colegio). A los colegios originales se les
  agregan estudiantes hasta alcanzar esa composición.
* Puntajes de área en 0..100; Global = rint(5·(3·(LC+MAT+SOC+CN)+ING)/13) en 0..500.

ADVERTENCIA: los efectos usados para generar puntajes son parámetros sintéticos.
Ningún resultado analítico obtenido con estos datos describe la realidad.

Uso:
    python scripts/generar_datos_ficticios.py --csv ResultadosICFES.csv --seed 20260913
    python scripts/generar_datos_ficticios.py --csv ResultadosICFES.csv --force   # regenerar desde el respaldo
"""
from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import math
import shutil
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np
import pandas as pd

ENCODING = "cp1252"
SEP = ";"
ANIOS = (2021, 2022, 2023, 2024)
AREAS = ("Lectura Crítica", "Matemáticas", "Sociales y Ciudadana", "Ciencias Naturales", "Inglés")
COLUMNAS = [
    "año", "periodo", "pais", "departamento", "municipio", "zona", "estrato",
    "nombre_colegio", "naturaleza_colegio", "modelopedag_colegio", "nroDoc",
    "nombre1", "nombre2", "apellido1", "apellido2", "sexo", "grupo", "Global", *AREAS,
]
FACTORES_COLEGIO = ("naturaleza_colegio", "zona", "periodo", "modelopedag_colegio")
FACTORES_ESTUDIANTE = ("estrato", "sexo", "año")
MAX_AREA, MAX_GLOBAL = 100, 500

# ---------------------------------------------------------------- composición objetivo por colegio-año
ESTRATOS = (1, 2, 3, 4, 5, 6)
PROP_ESTRATO = (0.22, 0.22, 0.22, 0.14, 0.12, 0.08)
SEXOS = ("Femenino", "Masculino")
PROP_SEXO = (0.5, 0.5)
VARIACION_TAMANO = 0.05     # ±5 % en el tamaño de colegios nuevos por año

# ---------------------------------------------------------------- parámetros sintéticos
SD_HABILIDAD = 8.0          # habilidad del estudiante compartida entre áreas
SD_RUIDO_AREA = 7.0         # ruido independiente por área
EFECTO_ESTRATO = 2.5        # puntos por nivel de estrato por encima de 2
EFECTO_PRIVADA = 4.0
EFECTO_RURAL = -4.0
EFECTO_PERIODO_I = 0.0      # sin efecto: sirve de control negativo para SHAP
EFECTO_ANIO = 0.8           # tendencia por año desde 2021
EFECTO_MODELO = {
    "Aprendizaje basado en proyectos": 1.5,
    "Constructivista": 1.0,
    "Pedagogía conceptual": 0.5,
    "Tradicional": 0.0,
}
EFECTO_SEXO_AREA = {        # (Femenino, Masculino) por área
    "Matemáticas": (-1.5, 1.5),
    "Lectura Crítica": (1.5, -1.5),
}
EFECTO_INGLES_PRIVADA = 5.0


@dataclass(frozen=True)
class Colegio:
    nombre: str
    naturaleza: str
    zona: str
    modelo: str
    periodo: str
    efecto_colegio: float   # efecto fijo del colegio; suma 0 por modelo y por celda
    n_grupos: int = 3


ABP, CON, PCO, TRA = EFECTO_MODELO
# Celdas con naturaleza⊕zona⊕periodo par: (Pública,Urbana,II) (Pública,Rural,I) (Privada,Urbana,I) (Privada,Rural,II).
# La celda (Pública,Urbana,II) ya contiene ABC, RST y XYZ; se completa con YZA.
COLEGIOS_NUEVOS = (
    Colegio("YZA", "Pública", "Urbana", TRA, "II", 0.0),
    Colegio("DEF", "Pública", "Rural", ABP, "I", 1.0),
    Colegio("GHI", "Pública", "Rural", CON, "I", -1.0),
    Colegio("JKL", "Pública", "Rural", PCO, "I", 0.5),
    Colegio("BCD", "Pública", "Rural", TRA, "I", -0.5),
    Colegio("MNO", "Privada", "Urbana", ABP, "I", -1.0),
    Colegio("PQR", "Privada", "Urbana", CON, "I", 1.0),
    Colegio("STU", "Privada", "Urbana", PCO, "I", -0.5),
    Colegio("EFG", "Privada", "Urbana", TRA, "I", 0.5),
    Colegio("HIJ", "Privada", "Rural", ABP, "II", 0.0),
    Colegio("VWX", "Privada", "Rural", CON, "II", 0.0),
    Colegio("KLM", "Privada", "Rural", PCO, "II", 0.0),
    Colegio("NOP", "Privada", "Rural", TRA, "II", 0.0),
)

UMBRAL_CRAMER_V = 0.05


# ---------------------------------------------------------------- utilidades
def sha256_archivo(ruta: Path) -> str:
    h = hashlib.sha256()
    with ruta.open("rb") as f:
        for bloque in iter(lambda: f.read(1 << 20), b""):
            h.update(bloque)
    return h.hexdigest()


def fin_de_linea(ruta: Path) -> str:
    with ruta.open("rb") as f:
        return "\r\n" if b"\r\n" in f.read(65536) else "\n"


def leer_csv(ruta: Path) -> pd.DataFrame:
    df = pd.read_csv(ruta, sep=SEP, encoding=ENCODING, dtype={"nroDoc": "int64"})
    faltantes = set(COLUMNAS) - set(df.columns)
    if faltantes or len(df.columns) != len(COLUMNAS):
        sys.exit(f"Contrato de columnas no coincide. Faltantes: {sorted(faltantes)}")
    return df[COLUMNAS]


def calcular_global(lc, mat, soc, cien, ing) -> np.ndarray:
    # Regla verificada en 899/899 filas del original (H4). 5·x/13 nunca termina en .5 para enteros.
    return np.rint(5 * (3 * (lc + mat + soc + cien) + ing) / 13).astype(int)


def separador_grupo(df: pd.DataFrame) -> str:
    # El original usa "11<carácter>1"; se reutiliza exactamente el mismo carácter.
    return str(df["grupo"].iloc[0])[2]


def cramer_v(a: pd.Series, b: pd.Series) -> float:
    tabla = pd.crosstab(a, b).to_numpy(dtype=float)
    if min(tabla.shape) < 2:
        return 0.0
    esperado = tabla.sum(1, keepdims=True) * tabla.sum(0, keepdims=True) / tabla.sum()
    chi2 = ((tabla - esperado) ** 2 / esperado).sum()
    return float(math.sqrt(chi2 / (tabla.sum() * (min(tabla.shape) - 1))))


def prob_celdas() -> dict[tuple[int, str], float]:
    return {(e, s): pe * ps for (e, pe), (s, ps) in itertools.product(zip(ESTRATOS, PROP_ESTRATO, strict=True), zip(SEXOS, PROP_SEXO, strict=True))}


def asignar_por_restos(n: int, probs: dict) -> dict:
    """Reparte n en celdas proporcionalmente (método del mayor resto): composición exacta, no aleatoria."""
    brutos = {k: n * p for k, p in probs.items()}
    enteros = {k: int(math.floor(v)) for k, v in brutos.items()}
    for k in sorted(brutos, key=lambda k: brutos[k] - enteros[k], reverse=True)[: n - sum(enteros.values())]:
        enteros[k] += 1
    return enteros


# ---------------------------------------------------------------- generación
def media_latente(estrato, sexo_fem, col: Colegio, anio: int, area: str, base: float) -> np.ndarray:
    mu = (
        base
        + EFECTO_ESTRATO * (estrato - 2)
        + (EFECTO_PRIVADA if col.naturaleza == "Privada" else 0.0)
        + (EFECTO_RURAL if col.zona == "Rural" else 0.0)
        + (EFECTO_PERIODO_I if col.periodo == "I" else 0.0)
        + EFECTO_MODELO[col.modelo]
        + col.efecto_colegio
        + EFECTO_ANIO * (anio - ANIOS[0])
    )
    if area in EFECTO_SEXO_AREA:
        fem, masc = EFECTO_SEXO_AREA[area]
        mu = mu + np.where(sexo_fem, fem, masc)
    if area == "Inglés" and col.naturaleza == "Privada":
        mu = mu + EFECTO_INGLES_PRIVADA
    return np.asarray(mu, dtype=float)


def calibrar_base(original: pd.DataFrame, colegios: dict[str, Colegio]) -> float:
    """Nivel base de área tal que el modelo reproduzca la media de las áreas del CSV original."""
    residuos = []
    for area in AREAS:
        for nombre, g in original.groupby("nombre_colegio"):
            mu0 = np.concatenate([
                media_latente(ga["estrato"].to_numpy(), (ga["sexo"] == "Femenino").to_numpy(), colegios[nombre], anio, area, 0.0)
                for anio, ga in g.groupby("año")
            ])
            obs = np.concatenate([ga[area].to_numpy() for _, ga in g.groupby("año")])
            residuos.append(obs - mu0)
    return round(float(np.concatenate(residuos).mean()), 3)


def generar_estudiantes(rng, col: Colegio, anio: int, conteos: dict, base: float, sep_grupo: str, fijo: dict) -> pd.DataFrame:
    estrato = np.array([e for (e, s), n in conteos.items() for _ in range(n)], dtype=int)
    sexo = np.array([s for (e, s), n in conteos.items() for _ in range(n)], dtype=object)
    n = len(estrato)
    if n == 0:
        return pd.DataFrame(columns=COLUMNAS)
    orden = rng.permutation(n)
    estrato, sexo = estrato[orden], sexo[orden]
    habilidad = rng.normal(0, SD_HABILIDAD, n)
    datos = {}
    for area in AREAS:
        mu = media_latente(estrato, sexo == "Femenino", col, anio, area, base) + habilidad
        datos[area] = np.clip(np.rint(mu + rng.normal(0, SD_RUIDO_AREA, n)), 0, MAX_AREA).astype(int)
    df = pd.DataFrame(datos)
    df["Global"] = calcular_global(*(df[a].to_numpy() for a in AREAS))
    df["año"] = anio
    df["periodo"] = col.periodo
    df["zona"] = col.zona
    df["estrato"] = estrato
    df["nombre_colegio"] = col.nombre
    df["naturaleza_colegio"] = col.naturaleza
    df["modelopedag_colegio"] = col.modelo
    df["sexo"] = sexo
    df["grupo"] = [f"11{sep_grupo}{g}" for g in rng.integers(1, col.n_grupos + 1, n)]
    for k, v in fijo.items():
        df[k] = v
    return df


def asignar_identidades(rng, df_nuevo: pd.DataFrame, existentes: set[int], inicio: int) -> pd.DataFrame:
    necesarios = len(df_nuevo)
    docs: set[int] = set()
    while len(docs) < necesarios:  # documentos ficticios de 10 dígitos, sin colisiones
        docs.update(int(x) for x in rng.integers(1_000_000_000, 9_999_999_999, necesarios * 2))
        docs -= existentes
    df_nuevo["nroDoc"] = rng.permutation(sorted(docs))[:necesarios]
    idx = np.arange(inicio, inicio + necesarios)
    df_nuevo["nombre1"] = [f"NombreL{i}" for i in idx]
    df_nuevo["nombre2"] = [f"NombreM{i}" for i in idx]
    df_nuevo["apellido1"] = [f"ApellidoN{i}" for i in idx]
    df_nuevo["apellido2"] = [f"ApellidoO{i}" for i in idx]
    return df_nuevo


def colegios_existentes(df: pd.DataFrame) -> dict[str, Colegio]:
    return {
        nombre: Colegio(nombre, g["naturaleza_colegio"].mode()[0], g["zona"].mode()[0],
                        g["modelopedag_colegio"].mode()[0], g["periodo"].mode()[0], 0.0,
                        max(3, g["grupo"].nunique()))
        for nombre, g in df.groupby("nombre_colegio")
    }


def plan_de_conteos(original: pd.DataFrame, n_nuevos: int | None, rng) -> tuple[dict, dict, int]:
    """Estudiantes a agregar por (colegio, año, estrato, sexo)."""
    probs = prob_celdas()
    agregar_existentes, totales = {}, []
    for (nombre, anio), g in original.groupby(["nombre_colegio", "año"]):
        actuales = g.groupby(["estrato", "sexo"]).size().to_dict()
        n_objetivo = math.ceil(max(actuales.get(k, 0) / p for k, p in probs.items()))
        objetivo = {k: math.ceil(n_objetivo * p) for k, p in probs.items()}
        agregar_existentes[(nombre, anio)] = {k: objetivo[k] - actuales.get(k, 0) for k in probs}
        totales.append(sum(objetivo.values()))
    base_nuevos = n_nuevos or round(float(np.mean(totales)))
    agregar_nuevos = {}
    for col in COLEGIOS_NUEVOS:
        for anio in ANIOS:
            n = int(round(base_nuevos * (1 + rng.uniform(-VARIACION_TAMANO, VARIACION_TAMANO))))
            agregar_nuevos[(col.nombre, anio)] = asignar_por_restos(n, probs)
    return agregar_existentes, agregar_nuevos, base_nuevos


def ampliar(original: pd.DataFrame, seed: int, n_colegio_anio: int | None = None) -> tuple[pd.DataFrame, dict]:
    rng = np.random.default_rng(seed)
    existentes = colegios_existentes(original)
    faltan = set(original["modelopedag_colegio"]) - set(EFECTO_MODELO)
    if faltan:
        sys.exit(f"Modelos pedagógicos no reconocidos: {faltan}")
    colegios = {**existentes, **{c.nombre: c for c in COLEGIOS_NUEVOS}}
    base = calibrar_base(original, colegios)
    sep_grupo = separador_grupo(original)
    fijo = {c: original[c].mode()[0] for c in ("pais", "departamento", "municipio")}

    agregar_existentes, agregar_nuevos, base_nuevos = plan_de_conteos(original, n_colegio_anio, rng)
    lotes = [
        generar_estudiantes(rng, colegios[nombre], anio, conteos, base, sep_grupo, fijo)
        for (nombre, anio), conteos in {**agregar_existentes, **agregar_nuevos}.items()
    ]
    nuevos = pd.concat([lote for lote in lotes if len(lote)], ignore_index=True)
    nuevos = asignar_identidades(rng, nuevos, set(original["nroDoc"].tolist()), inicio=len(original) + 2)
    return nuevos[COLUMNAS], {"base_area_calibrada": base, "tamano_colegio_nuevo_por_anio": base_nuevos}


# ---------------------------------------------------------------- validación
def diagnostico_independencia(df: pd.DataFrame) -> dict[str, float]:
    pares = list(itertools.combinations(FACTORES_COLEGIO, 2)) + list(itertools.product(FACTORES_ESTUDIANTE, FACTORES_COLEGIO))
    pares.append(("estrato", "sexo"))
    return {f"{a}~{b}": round(cramer_v(df[a], df[b]), 4) for a, b in pares}


def validar(original: pd.DataFrame, final: pd.DataFrame) -> dict[str, object]:
    colegios = final.drop_duplicates("nombre_colegio")
    balance_colegios = all(
        np.unique(pd.crosstab(colegios[a], colegios[b]).to_numpy()).size == 1
        for a, b in itertools.combinations(FACTORES_COLEGIO, 2)
    )
    por_modelo = final.groupby("modelopedag_colegio")[["nombre_colegio", "naturaleza_colegio", "zona", "periodo"]].nunique()
    exist = final[final["nombre_colegio"].isin(original["nombre_colegio"].unique())]
    fem = final.groupby(["nombre_colegio", "año"])["sexo"].apply(lambda s: (s == "Femenino").mean())
    estratos_por_factor = all(
        final.groupby(f)["estrato"].nunique().min() == len(ESTRATOS) for f in FACTORES_COLEGIO
    )
    independencia = diagnostico_independencia(final)
    formula_ok = (calcular_global(*(final[a].to_numpy() for a in AREAS)) == final["Global"].to_numpy()).mean()
    checks = {
        "originales_intactos": bool(final.iloc[: len(original)].reset_index(drop=True).equals(original.reset_index(drop=True))),
        "H2_zona_naturaleza_periodo_con_2_valores": bool(all(final[c].nunique() == 2 for c in ("zona", "naturaleza_colegio", "periodo"))),
        "H3_cada_modelo_en_ambos_niveles_de_cada_factor": bool((por_modelo[["naturaleza_colegio", "zona", "periodo"]] == 2).all(axis=None)),
        "H3_cada_modelo_en_4_colegios": bool((por_modelo["nombre_colegio"] == 4).all()),
        "diseno_colegios_balanceado_por_pares": bool(balance_colegios),
        "H7_colegios_>=16": bool(final["nombre_colegio"].nunique() >= 16),
        "H8_femenino_45_55pct_por_colegio_anio": bool(fem.between(0.45, 0.55).all()),
        "estratos_1_6_en_cada_nivel_de_factor": bool(estratos_por_factor),
        f"independencia_cramer_v_<={UMBRAL_CRAMER_V}": bool(max(independencia.values()) <= UMBRAL_CRAMER_V),
        "H4_formula_global_100pct": bool(formula_ok == 1.0),
        "nroDoc_unico": bool(final["nroDoc"].is_unique),
        "rango_areas_0_100": bool(final[list(AREAS)].stack().between(0, MAX_AREA).all()),
        "rango_global_0_500": bool(final["Global"].between(0, MAX_GLOBAL).all()),
        "sin_nulos": bool(not final.isna().any().any()),
    }
    return {
        "checks": checks,
        "aprobado": all(checks.values()),
        "filas_originales": len(original),
        "filas_finales": len(final),
        "filas_agregadas": len(final) - len(original),
        "filas_agregadas_a_colegios_originales": len(exist) - len(original),
        "cramer_v": independencia,
        "distribucion_sexo": final["sexo"].value_counts().to_dict(),
        "filas_por_colegio": final["nombre_colegio"].value_counts().sort_index().to_dict(),
    }


# ---------------------------------------------------------------- main
def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--csv", type=Path, default=Path("ResultadosICFES.csv"))
    p.add_argument("--seed", type=int, default=20260913)
    p.add_argument("--por-colegio-anio", type=int, default=None,
                   help="tamaño de colegios nuevos por año (por defecto: igual al de los colegios originales tras completarlos)")
    p.add_argument("--reportes", type=Path, default=Path("reports/datos_ficticios"))
    p.add_argument("--force", action="store_true", help="regenerar partiendo del respaldo original")
    a = p.parse_args()

    respaldo = a.csv.with_name(a.csv.stem + ".original.csv")
    if not respaldo.exists():
        shutil.copy2(a.csv, respaldo)
        print(f"Respaldo creado: {respaldo} (sha256={sha256_archivo(respaldo)})")

    actual = leer_csv(a.csv)
    if actual["nombre_colegio"].isin({c.nombre for c in COLEGIOS_NUEVOS}).any() and not a.force:
        sys.exit("El CSV ya contiene colegios ficticios. Use --force para regenerar desde el respaldo.")

    original = leer_csv(respaldo)
    nuevos, calibracion = ampliar(original, a.seed, a.por_colegio_anio)
    final = pd.concat([original, nuevos], ignore_index=True)

    reporte = validar(original, final)
    if not reporte["aprobado"]:
        print(json.dumps(reporte, ensure_ascii=False, indent=2, default=str))
        sys.exit("Validación fallida: no se modificó el CSV.")

    tmp = a.csv.with_suffix(".tmp")
    final.to_csv(tmp, sep=SEP, encoding=ENCODING, index=False, lineterminator=fin_de_linea(respaldo))
    leer_csv(tmp)          # verificación de lectura con el mismo contrato
    tmp.replace(a.csv)     # reemplazo atómico

    a.reportes.mkdir(parents=True, exist_ok=True)
    parametros = {
        "seed": a.seed, **calibracion,
        "prop_estrato": dict(zip(map(str, ESTRATOS), PROP_ESTRATO, strict=True)), "prop_sexo": dict(zip(SEXOS, PROP_SEXO, strict=True)),
        "sd_habilidad": SD_HABILIDAD, "sd_ruido_area": SD_RUIDO_AREA,
        "efecto_estrato": EFECTO_ESTRATO, "efecto_privada": EFECTO_PRIVADA, "efecto_rural": EFECTO_RURAL,
        "efecto_periodo_I": EFECTO_PERIODO_I, "efecto_anio": EFECTO_ANIO, "efecto_modelo": EFECTO_MODELO,
        "efecto_sexo_area_(femenino,masculino)": EFECTO_SEXO_AREA, "efecto_ingles_privada": EFECTO_INGLES_PRIVADA,
        "conversion_area_a_global": "efecto común a las 5 áreas × 65/13 = ×5; efecto solo en Inglés × 5/13",
        "colegios_nuevos": [asdict(c) for c in COLEGIOS_NUEVOS],
        "sha256_original": sha256_archivo(respaldo), "sha256_ampliado": sha256_archivo(a.csv),
        "advertencia": "Datos y efectos ficticios; no representan la realidad.",
    }
    (a.reportes / "parametros_generacion.json").write_text(json.dumps(parametros, ensure_ascii=False, indent=2), encoding="utf-8")
    (a.reportes / "validacion_ampliacion.json").write_text(json.dumps(reporte, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(f"CSV ampliado: {reporte['filas_originales']} -> {reporte['filas_finales']} filas "
          f"(+{reporte['filas_agregadas']}). Validación aprobada. Cramér V máx = {max(reporte['cramer_v'].values())}")


if __name__ == "__main__":
    main()
