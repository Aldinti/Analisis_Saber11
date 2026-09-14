"""Perfilamiento reproducible del CSV de resultados Saber 11 (fases F1 / F1c).

Genera un JSON reutilizable y un informe Markdown. El informe solo contiene agregados:
de las columnas con datos personales directos no se publican valores, mínimos ni máximos.

Uso (desde la raíz del proyecto):
    PYTHONPATH=src python -m saber11.profiling.profile --csv ResultadosICFES.csv --version v2 \
        --comparar-con reports/profiling/profile_v1.json
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import itertools
import json
import math
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd

AREAS = ["Lectura Crítica", "Matemáticas", "Sociales y Ciudadana", "Ciencias Naturales", "Inglés"]
PUNTAJES = ["Global", *AREAS]
PII_DIRECTA = ["nroDoc", "nombre1", "nombre2", "apellido1", "apellido2"]
CUASI_IDENTIFICADORES = ["nombre_colegio", "año", "sexo", "estrato", "grupo"]
CLASIFICACION = {
    **dict.fromkeys(PII_DIRECTA, "PII directa"),
    **dict.fromkeys(CUASI_IDENTIFICADORES + ["zona", "municipio"], "Cuasi-identificador"),
}
K_MINIMO = 5
MAX_CATEGORIAS = 30
MAX_AREA, MAX_GLOBAL = 100, 500   # escalas confirmadas por el usuario
FACTORES_COLEGIO = ["naturaleza_colegio", "zona", "periodo", "modelopedag_colegio"]
FACTORES_ESTUDIANTE = ["estrato", "sexo", "año"]
UMBRAL_INDEPENDENCIA, UMBRAL_CONFUSION = 0.05, 0.10


# ---------------------------------------------------------------- lectura
def sha256_archivo(ruta: Path) -> str:
    return hashlib.sha256(ruta.read_bytes()).hexdigest()


def detectar_formato(ruta: Path) -> dict[str, str]:
    crudo = ruta.read_bytes()
    try:
        crudo.decode("utf-8")
        encoding = "utf-8"
    except UnicodeDecodeError:
        encoding = "cp1252"
    cabecera = crudo.split(b"\n", 1)[0].decode(encoding)
    separador = csv.Sniffer().sniff(cabecera, delimiters=";,|\t").delimiter
    fin_linea = "CRLF" if b"\r\n" in crudo[:65536] else "LF"
    return {"encoding": encoding, "separador": separador, "fin_de_linea": fin_linea}


# ---------------------------------------------------------------- métricas
def a_python(valor):
    if isinstance(valor, (np.integer,)):
        return int(valor)
    if isinstance(valor, (np.floating,)):
        return None if np.isnan(valor) else round(float(valor), 4)
    if isinstance(valor, np.bool_):
        return bool(valor)
    return str(valor)


def perfil_columnas(df: pd.DataFrame) -> list[dict]:
    salida = []
    for col in df.columns:
        s = df[col]
        info = {
            "columna": col,
            "tipo_inferido": str(s.dtype),
            "clasificacion": CLASIFICACION.get(col, "Analítica"),
            "nulos": int(s.isna().sum()),
            "pct_nulos": round(float(s.isna().mean() * 100), 2),
            "cardinalidad": int(s.nunique()),
            "constante": bool(s.nunique(dropna=True) <= 1),
        }
        if col in PII_DIRECTA:
            info["unico"] = bool(s.is_unique)
        elif pd.api.types.is_numeric_dtype(s):
            q1, q3 = s.quantile([0.25, 0.75])
            iqr = q3 - q1
            z = (s - s.mean()) / s.std(ddof=0) if s.std(ddof=0) else s * 0
            info.update({
                "min": s.min(), "p25": q1, "p50": s.median(), "p75": q3, "max": s.max(),
                "media": s.mean(), "desv_est": s.std(),
                "atipicos_iqr": int(((s < q1 - 1.5 * iqr) | (s > q3 + 1.5 * iqr)).sum()),
                "atipicos_z3": int((z.abs() > 3).sum()),
            })
        if col not in PII_DIRECTA and s.nunique() <= MAX_CATEGORIAS:
            info["valores"] = {str(k): int(v) for k, v in s.value_counts(dropna=False).sort_index().items()}
        salida.append({k: (a_python(v) if not isinstance(v, (dict, str, bool, int)) else v) for k, v in info.items()})
    return salida


def calcular_global(df: pd.DataFrame) -> pd.Series:
    return np.rint(5 * (3 * df[AREAS[:4]].sum(axis=1) + df["Inglés"]) / 13).astype(int)


def dependencias(df: pd.DataFrame) -> dict:
    por_colegio = df.groupby("nombre_colegio")[["naturaleza_colegio", "zona", "modelopedag_colegio", "periodo"]].nunique()
    por_modelo = df.groupby("modelopedag_colegio").agg(
        colegios=("nombre_colegio", "nunique"), naturalezas=("naturaleza_colegio", "nunique"), zonas=("zona", "nunique"))
    return {
        "colegio_determina_atributo": {c: bool((por_colegio[c] == 1).all()) for c in por_colegio.columns},
        "modelo_pedagogico": {m: {k: int(v) for k, v in fila.items()} for m, fila in por_modelo.iterrows()},
        "modelo_equivale_a_colegio": bool((por_modelo["colegios"] == 1).all()),
    }


def cramer_v(a: pd.Series, b: pd.Series) -> float:
    tabla = pd.crosstab(a, b).to_numpy(dtype=float)
    if min(tabla.shape) < 2:
        return float("nan")
    esperado = tabla.sum(1, keepdims=True) * tabla.sum(0, keepdims=True) / tabla.sum()
    chi2 = ((tabla - esperado) ** 2 / esperado).sum()
    return float(math.sqrt(chi2 / (tabla.sum() * (min(tabla.shape) - 1))))


def independencia(df: pd.DataFrame) -> dict:
    pares = list(itertools.combinations(FACTORES_COLEGIO, 2)) + list(itertools.product(FACTORES_ESTUDIANTE, FACTORES_COLEGIO))
    pares.append(("estrato", "sexo"))
    valores = {f"{a}~{b}": cramer_v(df[a], df[b]) for a, b in pares}
    evaluables = {k: v for k, v in valores.items() if not math.isnan(v)}
    return {
        "cramer_v": {k: (None if math.isnan(v) else round(v, 4)) for k, v in valores.items()},
        "no_evaluables": sorted(k for k, v in valores.items() if math.isnan(v)),
        "max_cramer_v": round(max(evaluables.values()), 4) if evaluables else None,
        "umbral_independencia": UMBRAL_INDEPENDENCIA,
    }


def privacidad(df: pd.DataFrame) -> dict:
    grupos = df.groupby(CUASI_IDENTIFICADORES, dropna=False).size()
    return {
        "cuasi_identificadores": CUASI_IDENTIFICADORES,
        "k_minimo_observado": int(grupos.min()),
        "grupos_con_k_menor_a_umbral": int((grupos < K_MINIMO).sum()),
        "filas_en_grupos_k_menor_a_umbral": int(grupos[grupos < K_MINIMO].sum()),
        "pct_filas_en_riesgo": round(float(grupos[grupos < K_MINIMO].sum() / len(df) * 100), 2),
        "umbral_k": K_MINIMO,
        "columnas_pii_presentes": [c for c in PII_DIRECTA if c in df.columns],
    }


def descriptivos(df: pd.DataFrame) -> dict:
    salida = {}
    for dim in ["año", "periodo", "zona", "naturaleza_colegio", "modelopedag_colegio", "estrato", "sexo", "nombre_colegio"]:
        g = df.groupby(dim)["Global"].agg(["size", "mean", "std"]).round(2)
        salida[dim] = {str(k): {"n": int(f["size"]), "media_global": float(f["mean"]),
                                "desv_est": None if pd.isna(f["std"]) else float(f["std"])} for k, f in g.iterrows()}
    return salida


def hallazgos(df: pd.DataFrame, fmt: dict, cols: list[dict], dep: dict, formula_pct: float, ind: dict) -> list[dict]:
    constantes = [c["columna"] for c in cols if c["constante"]]
    clave_constantes = [c for c in ("zona", "naturaleza_colegio", "periodo") if c in constantes]
    pct_fem = df.groupby(["nombre_colegio", "año"])["sexo"].apply(lambda s: (s == "Femenino").mean() * 100)
    docs = df["nroDoc"]
    secuencial = bool(set(docs) == set(range(1, len(df) + 1)))
    en_rango_pequeno = float((docs <= 1_000_000).mean() * 100)
    repeticiones = int(docs.duplicated().sum())
    no_ascii_grupo = sorted({ch for v in df["grupo"].astype(str) for ch in v if ord(ch) > 127})
    rangos_ok = bool(df[AREAS].stack().between(0, MAX_AREA).all() and df["Global"].between(0, MAX_GLOBAL).all())
    if ind["no_evaluables"]:
        estado_h11 = "No evaluable (factores constantes)"
    elif ind["max_cramer_v"] <= UMBRAL_INDEPENDENCIA:
        estado_h11 = "Resuelto"
    elif ind["max_cramer_v"] <= UMBRAL_CONFUSION:
        estado_h11 = "Parcial"
    else:
        estado_h11 = "Presente"
    peor = max((kv for kv in ind["cramer_v"].items() if kv[1] is not None), key=lambda kv: kv[1], default=("-", None))

    def h(id_, tema, estado, evidencia):
        return {"id": id_, "tema": tema, "estado": estado, "evidencia": evidencia}

    return [
        h("H1", "Formato de la fuente", "Conservado (esperado)",
          f"encoding={fmt['encoding']}, separador='{fmt['separador']}', fin de línea={fmt['fin_de_linea']}, "
          f"{df.shape[0]} filas × {df.shape[1]} columnas"),
        h("H2", "Variables constantes", "Presente" if clave_constantes else "Resuelto",
          f"constantes: {', '.join(constantes) or 'ninguna'}"),
        h("H3", "Modelo pedagógico ≡ colegio", "Presente" if dep["modelo_equivale_a_colegio"] else "Resuelto",
          "; ".join(f"{m}: {v['colegios']} colegios, {v['naturalezas']} naturalezas" for m, v in dep["modelo_pedagogico"].items())),
        h("H4", "Global = f(áreas)", "Conservado (riesgo de leakage)" if formula_pct == 100 else "Parcial",
          f"fórmula rint(5·(3·(LC+MAT+SOC+CN)+ING)/13) se cumple en {formula_pct:.2f} % de filas"),
        h("H5", "nroDoc enumerable", "Presente" if secuencial else "Parcial (sigue siendo enumerable)",
          f"secuencial 1..n: {'sí' if secuencial else 'no'}; {en_rango_pequeno:.1f} % de documentos ≤ 1.000.000; "
          f"único: {'sí' if docs.is_unique else 'no'}"),
        h("H6", "PII directa en la fuente", "Presente (se elimina en Silver)",
          f"columnas: {', '.join(c for c in PII_DIRECTA if c in df.columns)}"),
        h("H7", "Estructura de agrupamiento", "Resuelto" if df["nombre_colegio"].nunique() >= 10 else "Presente",
          f"{df['nombre_colegio'].nunique()} colegios; registros repetidos por estudiante: {repeticiones}; "
          f"años: {df['año'].nunique()}"),
        h("H8", "Balance por sexo", "Resuelto" if pct_fem.min() >= 40 else "Presente",
          f"% Femenino global {float((df['sexo'] == 'Femenino').mean() * 100):.1f}; "
          f"mín. por colegio-año {pct_fem.min():.1f}; máx. {pct_fem.max():.1f}"),
        h("H9", "Codificación de `grupo`", "Conservado", f"{df['grupo'].nunique()} valores; caracteres no ASCII: {no_ascii_grupo}"),
        h("H10", "Rangos de puntajes", "Dentro de escala" if rangos_ok else "Fuera de escala",
          f"escala válida: áreas 0–{MAX_AREA}, Global 0–{MAX_GLOBAL}; observado: Global {int(df['Global'].min())}–"
          f"{int(df['Global'].max())}, áreas {int(df[AREAS].min().min())}–{int(df[AREAS].max().max())}"),
        h("H11", "Confusión entre factores", estado_h11,
          f"Cramér V máx = {ind['max_cramer_v']} ({peor[0]}); umbral independencia ≤ {UMBRAL_INDEPENDENCIA}; "
          f"no evaluables: {len(ind['no_evaluables'])} pares"),
    ]


def perfilar(ruta: Path, version: str) -> dict:
    fmt = detectar_formato(ruta)
    df = pd.read_csv(ruta, sep=fmt["separador"], encoding=fmt["encoding"])
    cols = perfil_columnas(df)
    dep = dependencias(df)
    formula_pct = float((calcular_global(df) == df["Global"]).mean() * 100)
    ind = independencia(df)
    return {
        "metadatos": {
            "version": version, "archivo": ruta.name, "sha256": sha256_archivo(ruta),
            "generado_utc": datetime.now(UTC).isoformat(timespec="seconds"),
            "filas": int(len(df)), "columnas": int(df.shape[1]), **fmt,
        },
        "hallazgos": hallazgos(df, fmt, cols, dep, formula_pct, ind),
        "columnas": cols,
        "duplicados": {
            "filas_completas": int(df.duplicated().sum()),
            "nroDoc": int(df["nroDoc"].duplicated().sum()),
            "nroDoc_año": int(df.duplicated(["nroDoc", "año"]).sum()),
        },
        "consistencia_global_pct": round(formula_pct, 2),
        "correlaciones_puntajes": df[PUNTAJES].corr().round(3).to_dict(),
        "conteo_año_colegio": {str(k): {str(a): int(n) for a, n in v.items()}
                               for k, v in pd.crosstab(df["nombre_colegio"], df["año"]).iterrows()},
        "estrato_por_naturaleza": {str(k): {str(e): int(n) for e, n in v.items()}
                                   for k, v in pd.crosstab(df["naturaleza_colegio"], df["estrato"]).iterrows()},
        "dependencias": dep,
        "independencia": ind,
        "privacidad": privacidad(df),
        "descriptivos_global": descriptivos(df),
    }


# ---------------------------------------------------------------- informe
def tabla(encabezados: list[str], filas: list[list]) -> str:
    lineas = ["| " + " | ".join(encabezados) + " |", "|" + "---|" * len(encabezados)]
    lineas += ["| " + " | ".join("" if v is None else str(v) for v in f) + " |" for f in filas]
    return "\n".join(lineas)


def informe_markdown(p: dict, previo: dict | None) -> str:
    m = p["metadatos"]
    out = [
        f"# Informe de perfilamiento {m['version']} — {m['archivo']}", "",
        "> Datos **ficticios**. Las cifras describen el archivo, no la realidad educativa. "
        "El informe no contiene valores de columnas con datos personales directos.", "",
        "## 0. Metadatos", "",
        tabla(["Campo", "Valor"], [[k, v] for k, v in m.items()]), "",
        "## 1. Hallazgos", "",
        tabla(["ID", "Tema", "Estado", "Evidencia"], [[h["id"], h["tema"], h["estado"], h["evidencia"]] for h in p["hallazgos"]]), "",
    ]
    if previo:
        pm = previo["metadatos"]
        estados_previos = {h["id"]: h["estado"] for h in previo["hallazgos"]}
        out += [
            f"## 1b. Comparación con {pm['version']} ({pm['archivo']})", "",
            tabla(["Métrica", pm["version"], m["version"]], [
                ["Filas", pm["filas"], m["filas"]],
                ["Colegios", len(previo["conteo_año_colegio"]), len(p["conteo_año_colegio"])],
                ["Columnas constantes", sum(c["constante"] for c in previo["columnas"]), sum(c["constante"] for c in p["columnas"])],
                ["k mínimo (cuasi-identificadores)", previo["privacidad"]["k_minimo_observado"], p["privacidad"]["k_minimo_observado"]],
                ["% filas con k<5", previo["privacidad"]["pct_filas_en_riesgo"], p["privacidad"]["pct_filas_en_riesgo"]],
                ["SHA-256", pm["sha256"][:12] + "…", m["sha256"][:12] + "…"],
            ]), "",
            tabla(["Hallazgo", f"Estado {pm['version']}", f"Estado {m['version']}"],
                  [[h["id"], estados_previos.get(h["id"], ""), h["estado"]] for h in p["hallazgos"]]), "",
        ]
    out += [
        "## 2. Columnas", "",
        tabla(["Columna", "Tipo", "Clasificación", "Nulos", "Cardinalidad", "Constante", "Mín", "Mediana", "Máx", "Atípicos IQR", "Atípicos |z|>3"],
              [[c["columna"], c["tipo_inferido"], c["clasificacion"], c["nulos"], c["cardinalidad"], "sí" if c["constante"] else "no",
                c.get("min"), c.get("p50"), c.get("max"), c.get("atipicos_iqr"), c.get("atipicos_z3")] for c in p["columnas"]]), "",
        "### Valores de columnas categóricas (cardinalidad ≤ 30, sin PII)", "",
    ]
    for c in p["columnas"]:
        if "valores" in c and c["columna"] not in PUNTAJES:
            out.append(f"- **{c['columna']}**: " + ", ".join(f"{k} ({v})" for k, v in c["valores"].items()))
    d = p["duplicados"]
    out += [
        "", "## 3. Duplicados", "",
        tabla(["Criterio", "Duplicados"], [["Fila completa", d["filas_completas"]], ["nroDoc", d["nroDoc"]], ["nroDoc + año", d["nroDoc_año"]]]), "",
        "## 4. Distribución de registros", "",
        "### Colegio × año", "",
    ]
    anios = sorted({a for v in p["conteo_año_colegio"].values() for a in v})
    out.append(tabla(["Colegio", *anios], [[k, *[v.get(a, 0) for a in anios]] for k, v in p["conteo_año_colegio"].items()]))
    estratos = sorted({e for v in p["estrato_por_naturaleza"].values() for e in v})
    out += ["", "### Estrato × naturaleza", "",
            tabla(["Naturaleza", *estratos], [[k, *[v.get(e, 0) for e in estratos]] for k, v in p["estrato_por_naturaleza"].items()]), "",
            "## 5. Puntajes", "",
            f"Consistencia de `Global` con la fórmula de áreas: **{p['consistencia_global_pct']} %** de filas.", "",
            "### Correlaciones (Pearson)", ""]
    corr = p["correlaciones_puntajes"]
    out.append(tabla(["", *PUNTAJES], [[f, *[corr[c][f] for c in PUNTAJES]] for f in PUNTAJES]))
    dep = p["dependencias"]
    out += ["", "## 6. Dependencias funcionales", "",
            "Colegio determina un único valor de: " + ", ".join(f"`{k}` ({'sí' if v else 'no'})" for k, v in dep["colegio_determina_atributo"].items()), "",
            tabla(["Modelo pedagógico", "Colegios", "Naturalezas", "Zonas"],
                  [[k, v["colegios"], v["naturalezas"], v["zonas"]] for k, v in dep["modelo_pedagogico"].items()]), ""]
    ind = p["independencia"]
    out += ["### Independencia entre factores (Cramér V)", "",
            f"Máximo evaluable: **{ind['max_cramer_v']}** (umbral de independencia ≤ {ind['umbral_independencia']}).", "",
            tabla(["Par de factores", "Cramér V"], [[k, "no evaluable" if v is None else v] for k, v in ind["cramer_v"].items()]), ""]
    pr = p["privacidad"]
    out += ["## 7. Privacidad", "",
            f"- Columnas con PII directa presentes: {', '.join(pr['columnas_pii_presentes'])} → eliminar en Silver.",
            f"- Cuasi-identificadores evaluados: {', '.join(pr['cuasi_identificadores'])}.",
            f"- k mínimo observado: **{pr['k_minimo_observado']}**; grupos con k<{pr['umbral_k']}: {pr['grupos_con_k_menor_a_umbral']} "
            f"({pr['filas_en_grupos_k_menor_a_umbral']} filas, {pr['pct_filas_en_riesgo']} %).",
            f"- Implicación (requisito confirmado): el dashboard operativo agrega o suprime grupos con menos de {pr['umbral_k']} estudiantes (plan §15.6).", "",
            "## 8. Descriptivos del puntaje Global por grupo", "",
            "> Descriptivos, no causales. En datos ficticios reflejan los parámetros del generador.", ""]
    for dim, grupos in p["descriptivos_global"].items():
        out += [f"### {dim}", "", tabla(["Grupo", "n", "Media", "Desv. est."],
                                        [[g, v["n"], v["media_global"], v["desv_est"]] for g, v in grupos.items()]), ""]
    return "\n".join(out)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--csv", type=Path, required=True)
    ap.add_argument("--version", required=True, help="etiqueta del informe, p. ej. v1, v2")
    ap.add_argument("--salida", type=Path, default=Path("reports/profiling"))
    ap.add_argument("--comparar-con", type=Path, help="JSON de un perfil previo")
    a = ap.parse_args()

    perfil = perfilar(a.csv, a.version)
    previo = json.loads(a.comparar_con.read_text(encoding="utf-8")) if a.comparar_con else None
    a.salida.mkdir(parents=True, exist_ok=True)
    ruta_json = a.salida / f"profile_{a.version}.json"
    ruta_md = a.salida / f"perfilamiento_{a.version}.md"
    ruta_json.write_text(json.dumps(perfil, ensure_ascii=False, indent=2, default=a_python), encoding="utf-8")
    ruta_md.write_text(informe_markdown(perfil, previo), encoding="utf-8")
    print(f"Perfil {a.version}: {perfil['metadatos']['filas']} filas, sha256={perfil['metadatos']['sha256'][:12]}... -> {ruta_md}")


if __name__ == "__main__":
    main()
