"""Ejecución de F10: evalúa el desempeño por subgrupo y publica el informe de sesgos."""
from __future__ import annotations

import itertools
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from saber11.ml import evaluate as ev
from saber11.ml import fairness as fr
from saber11.ml import graficos
from saber11.ml.experimento import ADVERTENCIA
from saber11.ml.informe import NOMBRES, num
from saber11.profiling.profile import cramer_v

FRASE_LECTURA = (
    "Una brecha de error indica que el modelo **funciona peor** para ese grupo; "
    "no que el grupo tenga peores resultados."
)
UMBRAL_CONFUSION = 0.20  # Cramér V a partir del cual se advierte de una asociación entre factores


class ErrorSesgos(RuntimeError):
    """No hay predicciones con las que evaluar el desempeño por subgrupo."""


def ejecutar(settings: dict[str, Any], raiz: Path, run_id: str, run_id_ml: str) -> fr.ResultadoSesgos:
    ml = settings["ml"]
    objetivo = ml["target"]
    directorio = raiz / settings["paths"]["models"] / run_id_ml
    predicciones = directorio / "predicciones_test.parquet"
    if not predicciones.exists():
        raise ErrorSesgos(
            f"No existe {predicciones.relative_to(raiz).as_posix()}. Ejecute: run --stage ml"
        )
    df = pd.read_parquet(predicciones)
    metricas = json.loads((directorio / "metrics.json").read_text(encoding="utf-8"))

    n_min = int(ml.get("n_min_subgrupo", fr.N_MIN_CONCLUYENTE))
    umbral = float(ml.get("umbral_brecha_rmse", fr.UMBRAL_BRECHA_RMSE))
    dimensiones = fr.evaluar(
        df, objetivo, n_min=n_min, umbral=umbral, semilla=int(ml["random_state"])
    )
    sesgo, ic_sesgo = fr.sesgo_global(df, objetivo, semilla=int(ml["random_state"]))
    resultado = fr.ResultadoSesgos(
        run_id=run_id,
        run_id_ml=run_id_ml,
        modelo=metricas.get("seleccionado", "desconocido"),
        metricas_globales=ev.metricas(
            df[objetivo].to_numpy(dtype=float), df["prediccion"].to_numpy(dtype=float)
        ),
        dimensiones=dimensiones,
        n_min=n_min,
        umbral_brecha=umbral,
        filas=len(df),
        sesgo_global=sesgo,
        ic_sesgo_global=ic_sesgo,
    )
    resultado.rutas = _publicar(resultado, df, settings, raiz)
    return resultado


def asociaciones(df: pd.DataFrame, columnas: tuple[str, ...] = ("estrato", "naturaleza_colegio",
                                                                "zona", "sexo", "modelo_pedagogico")) -> list[tuple[str, str, float]]:
    """Cramér V entre los factores del conjunto: detecta confusiones al interpretar (§19)."""
    presentes = [c for c in columnas if c in df.columns]
    return sorted(
        ((a, b, cramer_v(df[a], df[b])) for a, b in itertools.combinations(presentes, 2)),
        key=lambda t: -t[2],
    )


def _publicar(
    resultado: fr.ResultadoSesgos, df: pd.DataFrame, settings: dict[str, Any], raiz: Path
) -> dict[str, Path]:
    destino = raiz / settings["paths"]["reports"] / "fairness"
    destino.mkdir(parents=True, exist_ok=True)
    rutas = {"subgrupos": destino / "desempeno_subgrupos.csv"}
    resultado.tabla().to_csv(rutas["subgrupos"], index=False, encoding="utf-8")

    brechas = {
        d.nombre: d.brecha for d in resultado.dimensiones if d.evaluable and d.brecha is not None
    }
    if brechas:
        rutas["brechas"] = graficos.barras_importancia(
            brechas, destino / "brechas_rmse.png",
            f"Brecha de RMSE entre subgrupos (RMSE global "
            f"{resultado.metricas_globales['rmse']:.1f})".replace(".", ","),
        )
    rutas["informe"] = destino / "informe_sesgos.md"
    rutas["informe"].write_text(_informe(resultado, df, settings), encoding="utf-8")
    return {k: v.relative_to(raiz) for k, v in rutas.items()}


# ---------------------------------------------------------------- informe
def _tabla_resumen(resultado: fr.ResultadoSesgos) -> list[str]:
    lineas = [
        "| Dimensión | Subgrupos (concluyentes) | RMSE mínimo | RMSE máximo | Brecha | IC 95 % brecha | Alerta |",
        "|---|--:|--:|--:|--:|---|:--:|",
    ]
    for d in resultado.dimensiones:
        if not d.evaluable:
            lineas.append(
                f"| `{d.nombre}` | {len(d.subgrupos)} | — | — | — | — | no evaluable: {d.motivo_no_evaluable} |"
            )
            continue
        concluyentes = d.concluyentes
        peor = max(concluyentes, key=lambda s: s.rmse)
        mejor = min(concluyentes, key=lambda s: s.rmse)
        ic = f"[{num(d.ic_brecha[0], 2)}; {num(d.ic_brecha[1], 2)}]" if d.ic_brecha else "—"
        lineas.append(
            f"| `{d.nombre}` | {len(d.subgrupos)} ({len(concluyentes)}) | "
            f"{num(mejor.rmse, 2)} ({mejor.grupo}) | {num(peor.rmse, 2)} ({peor.grupo}) | "
            f"{num(d.brecha, 2)} | {ic} | {'⚠️' if d.alerta else '✅'} |"
        )
    return lineas


def _tabla_dimension(d: fr.Dimension) -> list[str]:
    lineas = [
        f"### `{d.nombre}`",
        "",
        "| Grupo | n | RMSE | IC 95 % RMSE | Desv. típica real | MAE | Sesgo medio | R² | |",
        "|---|--:|--:|---|--:|--:|--:|--:|---|",
    ]
    for s in sorted(d.subgrupos, key=lambda s: -s.rmse):
        marcas = []
        if not s.concluyente:
            marcas.append("no concluyente")
        if s.sesgo_especifico:
            marcas.append("sesgo propio del grupo")
        lineas.append(
            f"| {s.grupo} | {s.n} | {num(s.rmse, 2)} | "
            f"[{num(s.ic_rmse[0], 2)}; {num(s.ic_rmse[1], 2)}] | {num(s.sd_real, 2)} | "
            f"{num(s.mae, 2)} | {num(s.sesgo_medio, 2)} | {num(s.r2)} | {', '.join(marcas)} |"
        )
    if not d.evaluable:
        lineas += ["", f"No se calcula brecha: {d.motivo_no_evaluable}."]
    elif not np.isnan(d.correlacion_rmse_dispersion):
        lineas += [
            "",
            f"Correlación entre el RMSE de cada grupo y la dispersión de su resultado real: "
            f"{num(d.correlacion_rmse_dispersion)}.",
        ]
    return lineas


def _seccion_alertas(resultado: fr.ResultadoSesgos) -> list[str]:
    """Explica cada alerta con lo que dicen los datos, no con una interpretación fija."""
    if not resultado.alertas:
        return ["No hay alertas que interpretar."]
    lineas = []
    dispersion_ya_explicada = False
    for d in resultado.alertas:
        correlacion = d.correlacion_rmse_dispersion
        sigue_dispersion = not np.isnan(correlacion) and correlacion >= 0.7
        peor = max(d.concluyentes, key=lambda s: s.rmse)
        mejor = min(d.concluyentes, key=lambda s: s.rmse)
        texto = (
            f"- **`{d.nombre}`** — brecha {num(d.brecha, 2)} puntos entre {peor.grupo} "
            f"({num(peor.rmse, 2)}) y {mejor.grupo} ({num(mejor.rmse, 2)}). "
        )
        if d.nombre == fr.COLUMNA_CLUSTER:
            texto += (
                "Es la brecha esperada: la identidad del colegio no es una variable del modelo "
                "—se reserva como grupo de validación—, así que el efecto propio de cada centro "
                "queda entero en el error. Mide cuánto varía ese efecto no observado."
            )
        elif sigue_dispersion and not dispersion_ya_explicada:
            texto += (
                f"El RMSE sigue de cerca a la dispersión del resultado real (correlación "
                f"{num(correlacion)}): un grupo con resultados más concentrados tiene menos error "
                "que perder, así que la brecha mide sobre todo esa diferencia de dispersión y no "
                "que el modelo trate peor a un grupo."
            )
            dispersion_ya_explicada = True
        elif sigue_dispersion:
            texto += (
                f"Misma lectura: el RMSE acompaña a la dispersión del resultado "
                f"(correlación {num(correlacion)})."
            )
        else:
            texto += (
                f"La dispersión del resultado no explica la brecha (correlación {num(correlacion)}): "
                "conviene revisar este grupo antes de usar el modelo con él."
            )
        lineas.append(texto)
    return lineas


def _seccion_sesgo(resultado: fr.ResultadoSesgos) -> list[str]:
    ic = resultado.ic_sesgo_global
    sentido = "por debajo" if resultado.sesgo_global < 0 else "por encima"
    lineas = [
        f"**Sesgo global del modelo: {num(resultado.sesgo_global, 2)} puntos** "
        f"(IC 95 % [{num(ic[0], 2)}; {num(ic[1], 2)}]).",
        "",
    ]
    if resultado.sesgo_global_significativo:
        lineas += [
            f"El modelo predice en bloque {sentido} del resultado real. Ese desvío **aparece en todos",
            "los subgrupos**, así que un sesgo de grupo solo es propio del grupo si se aparta del",
            "global; esa es la comparación que hace la tabla siguiente.",
            "",
        ]
    else:
        lineas += ["El modelo no se desvía en bloque: cualquier sesgo de grupo es propio del grupo.", ""]

    propios = sorted(resultado.subgrupos_con_sesgo_propio, key=lambda s: -abs(s.sesgo_medio))
    if not propios:
        lineas += [
            "**Ningún subgrupo concluyente tiene un sesgo propio:** una vez descontado el desvío",
            f"global, los {len(resultado.subgrupos_con_sesgo)} grupos con sesgo distinto de cero se",
            "explican por ese mismo desvío compartido.",
        ]
        return lineas
    lineas += [
        "Subgrupos cuyo sesgo **se aparta del global** (el intervalo de la diferencia no incluye 0).",
        "Un valor negativo significa que el modelo predice por debajo del resultado real del grupo.",
        "",
        "| Dimensión | Grupo | n | Sesgo medio | IC 95 % del sesgo | IC 95 % frente al global |",
        "|---|---|--:|--:|---|---|",
    ]
    for s in propios:
        lineas.append(
            f"| `{s.dimension}` | {s.grupo} | {s.n} | {num(s.sesgo_medio, 2)} | "
            f"[{num(s.ic_sesgo[0], 2)}; {num(s.ic_sesgo[1], 2)}] | "
            f"[{num(s.ic_sesgo_relativo[0], 2)}; {num(s.ic_sesgo_relativo[1], 2)}] |"
        )
    return lineas


def _seccion_confusiones(df: pd.DataFrame) -> list[str]:
    pares = asociaciones(df)
    fuertes = [(a, b, v) for a, b, v in pares if v >= UMBRAL_CONFUSION]
    lineas = [
        "Al leer las brechas conviene saber qué factores van juntos: si dos están asociados, la",
        "brecha de uno arrastra la del otro. Asociación medida con la V de Cramér sobre el conjunto",
        "de prueba.",
        "",
        "| Par de factores | V de Cramér |",
        "|---|--:|",
    ]
    for a, b, v in pares[:5]:
        lineas.append(f"| `{a}` ~ `{b}` | {num(v)} |")
    lineas.append("")
    if fuertes:
        detalle = "; ".join(f"`{a}`–`{b}` ({num(v)})" for a, b, v in fuertes)
        lineas.append(
            f"**Asociaciones relevantes (V ≥ {num(UMBRAL_CONFUSION, 2)}):** {detalle}. Las brechas de esos "
            "factores no deben interpretarse por separado."
        )
    else:
        lineas.append(
            f"Ningún par supera V = {num(UMBRAL_CONFUSION, 2)}: los factores son prácticamente "
            "independientes entre sí, así que cada brecha puede leerse por su cuenta. Es lo que buscaba "
            "el diseño ortogonal de colegios de F1b, comprobado aquí sobre el conjunto de prueba."
        )
    return lineas


def _informe(resultado: fr.ResultadoSesgos, df: pd.DataFrame, settings: dict[str, Any]) -> str:
    g = resultado.metricas_globales
    etiqueta = NOMBRES.get(resultado.modelo, resultado.modelo)
    lineas = [
        "# Evaluación de sesgos — F10",
        "",
        f"> ⚠️ {ADVERTENCIA}",
        f"> {FRASE_LECTURA}",
        "",
        f"Ejecución `{resultado.run_id}` sobre el modelo de F8 `{resultado.run_id_ml}` ({etiqueta}).",
        "",
        "## 1. Qué se evalúa",
        "",
        f"- **Conjunto:** las {resultado.filas} filas del año de prueba ({settings['ml']['test_year']}), "
        "las mismas con las que se midió el modelo en F8.",
        f"- **Desempeño global:** R² {num(g['r2'])} · RMSE {num(g['rmse'], 2)} · MAE {num(g['mae'], 2)}.",
        "- **Métricas por subgrupo:** n, RMSE, MAE, sesgo medio del residuo (predicción − real), R² y "
        "la desviación típica del resultado real, con IC 95 % bootstrap. La desviación típica sirve "
        "de referencia: un grupo con resultados más dispersos tiene más error que perder.",
        f"- **Grupos pequeños:** con n < {resultado.n_min} el error no distingue señal de ruido; el grupo "
        "se reporta con su n, se marca **no concluyente** y queda fuera del cálculo de brechas.",
        f"- **Umbral de alerta:** brecha de RMSE mayor que el {resultado.umbral_brecha * 100:.0f} % "
        f"del RMSE global, es decir {num(resultado.umbral_brecha * g['rmse'], 2)} puntos.",
        "- **Unidad de remuestreo:** colegios, salvo en la dimensión `nombre_colegio`, donde cada grupo "
        "ya es un colegio y se remuestrean filas.",
        "",
        "## 2. Resumen de brechas",
        "",
        *_tabla_resumen(resultado),
        "",
    ]
    if resultado.alertas:
        nombres = ", ".join(f"`{d.nombre}`" for d in resultado.alertas)
        lineas.append(
            f"**Dimensiones con alerta: {nombres}.** La diferencia entre el mejor y el peor subgrupo "
            "supera el umbral; revísese el detalle y el intervalo antes de concluir."
        )
    else:
        lineas.append(
            "**Ninguna dimensión supera el umbral de alerta.** El modelo comete un error de magnitud "
            "comparable en todos los subgrupos concluyentes."
        )
    lineas += [
        "",
        "Figura: `brechas_rmse.png`. Detalle completo en `desempeno_subgrupos.csv`.",
        "",
        "### Qué hay detrás de cada alerta",
        "",
        *_seccion_alertas(resultado),
        "",
        "## 3. Sesgo sistemático",
        "",
        *_seccion_sesgo(resultado),
        "",
        "## 4. Detalle por dimensión",
        "",
    ]
    for d in resultado.dimensiones:
        lineas += [*_tabla_dimension(d), ""]
    lineas += [
        "## 5. Factores asociados entre sí",
        "",
        *_seccion_confusiones(df),
        "",
        "## 6. Lectura y límites",
        "",
        f"- {FRASE_LECTURA}",
        "- El modelo solo recibe atributos del colegio y del perfil del estudiante: no puede",
        "  distinguir a dos estudiantes con los mismos atributos, así que el error dentro de cada",
        "  subgrupo está dominado por la variabilidad individual.",
        "- Las diferencias de **nivel** entre grupos (que un grupo puntúe más que otro) son parte de",
        "  lo que el modelo predice; lo que aquí se mide es si **acierta** por igual en todos.",
        "- Los datos son ficticios: estas brechas describen el comportamiento del pipeline sobre los",
        "  efectos que introdujo el generador de F1b, no desigualdades educativas reales.",
        "",
        "## 7. Artefactos",
        "",
        "| Archivo | Contenido |",
        "|---|---|",
        "| `desempeno_subgrupos.csv` | Una fila por subgrupo con n, métricas, intervalos y marcas |",
        "| `brechas_rmse.png` | Brecha de RMSE por dimensión |",
        "| `informe_sesgos.md` | Este informe |",
    ]
    return "\n".join(lineas) + "\n"
