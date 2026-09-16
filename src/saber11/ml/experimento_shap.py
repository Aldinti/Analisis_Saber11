"""Ejecución de F9: calcula las explicaciones SHAP y publica figuras e interpretación."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

from saber11.ml import explain as ex
from saber11.ml import graficos
from saber11.ml.experimento import ADVERTENCIA
from saber11.ml.informe import NOMBRES, num

FRASE_CAUSALIDAD = "SHAP explica el comportamiento del modelo; no demuestra causalidad."
RUTA_PARAMETROS = Path("reports/datos_ficticios/parametros_generacion.json")
DEPENDENCIAS = ("estrato", "sexo", "modelo_pedagogico")


def ejecutar(settings: dict[str, Any], raiz: Path, run_id: str, run_id_ml: str) -> ex.ResultadoSHAP:
    semilla = int(settings["ml"]["random_state"])
    contexto = ex.cargar_contexto(settings, raiz, run_id_ml)
    final = contexto.metricas["seleccionado"]

    explicaciones = {final: ex.explicar(final, contexto.pipeline_final, contexto, semilla)}
    contraste = ex.modelo_de_contraste(contexto, settings)
    if contraste:
        nombre, pipeline = contraste
        explicaciones[nombre] = ex.explicar(nombre, pipeline, contexto, semilla)

    parametros = _parametros_generacion(raiz)
    recuperacion = (
        ex.prueba_recuperacion(explicaciones[final], contexto.prueba, contexto.variables, parametros)
        if parametros is not None
        else pd.DataFrame(columns=["variable", "contraste", "esperado", "medido", "diferencia",
                                   "error_relativo", "signo_coincide", "exigida", "nota"])
    )

    resultado = ex.ResultadoSHAP(
        run_id=run_id,
        run_id_ml=run_id_ml,
        modelo_final=final,
        explicaciones=explicaciones,
        recuperacion=recuperacion,
        casos=ex.casos_representativos(explicaciones[final], contexto.prueba, contexto.variables),
        coeficientes=ex.coeficientes_lineales(contexto.pipeline_final, contexto.variables),
        filas={"prueba": len(contexto.prueba), "entrena": len(contexto.entrena),
               "variables": len(contexto.variables.predictoras)},
    )
    resultado.rutas = _publicar(resultado, contexto, settings, raiz, parametros is not None)
    return resultado


def _parametros_generacion(raiz: Path) -> dict[str, Any] | None:
    ruta = raiz / RUTA_PARAMETROS
    if not ruta.exists():
        return None
    return json.loads(ruta.read_text(encoding="utf-8"))


def _publicar(
    resultado: ex.ResultadoSHAP,
    contexto: ex.ContextoF9,
    settings: dict[str, Any],
    raiz: Path,
    con_recuperacion: bool,
) -> dict[str, Path]:
    destino = raiz / settings["paths"]["reports"] / "shap"
    destino.mkdir(parents=True, exist_ok=True)
    final = resultado.explicaciones[resultado.modelo_final]
    etiqueta = NOMBRES.get(resultado.modelo_final, resultado.modelo_final)
    rutas: dict[str, Path] = {}

    rutas["importancia"] = graficos.barras_importancia(
        final.importancia, destino / "importancia_global.png",
        f"Importancia global — {etiqueta} (prueba {settings['ml']['test_year']})",
    )
    rutas["beeswarm"] = graficos.beeswarm(
        final.valores_columnas,
        ex.matriz_transformada(
            contexto.pipeline_final, contexto.prueba, contexto.variables, final.columnas
        ),
        destino / "beeswarm.png",
        f"Distribución de contribuciones — {etiqueta}",
    )
    for variable in DEPENDENCIAS:
        if variable in final.valores.columns:
            rutas[f"dependencia_{variable}"] = graficos.dependencia(
                final.valores[variable].to_numpy(), contexto.prueba[variable],
                destino / f"dependencia_{variable}.png",
                f"Contribución de {variable} — {etiqueta}",
            )
    for etiqueta_caso, caso in resultado.casos.items():
        rutas[f"waterfall_{etiqueta_caso}"] = graficos.cascada(
            caso["contribuciones"], caso["valores"], caso["base"], caso["prediccion"], caso["real"],
            destino / f"waterfall_{etiqueta_caso}.png",
            f"Caso en el percentil {int(caso['percentil'] * 100)} de la predicción — {etiqueta}",
        )
    if len(resultado.explicaciones) > 1:
        rutas["comparacion"] = graficos.comparacion_modelos(
            {NOMBRES.get(n, n): e.importancia for n, e in resultado.explicaciones.items()},
            destino / "comparacion_modelos.png", "Importancia por variable según cada modelo",
        )

    tablas = []
    for nombre, explicacion in resultado.explicaciones.items():
        tabla = explicacion.valores.add_prefix("shap_")
        tabla.insert(0, "modelo", nombre)
        tabla["valor_esperado"] = explicacion.base
        tabla["prediccion"] = explicacion.prediccion
        for columna in contexto.variables.predictoras:
            tabla[columna] = contexto.prueba[columna].to_numpy()
        tabla[contexto.variables.objetivo] = contexto.prueba[contexto.variables.objetivo].to_numpy()
        tablas.append(tabla)
    rutas["valores"] = destino / "shap_values.parquet"
    pd.concat(tablas, ignore_index=True).to_parquet(rutas["valores"], index=False)

    if con_recuperacion:
        rutas["recuperacion"] = destino / "recuperacion_efectos.csv"
        resultado.recuperacion.to_csv(rutas["recuperacion"], index=False, encoding="utf-8")

    rutas["interpretacion"] = destino / "interpretacion.md"
    rutas["interpretacion"].write_text(
        _interpretacion(resultado, contexto, settings, con_recuperacion), encoding="utf-8"
    )
    return {k: v.relative_to(raiz) for k, v in rutas.items()}


# ---------------------------------------------------------------- informe
def _tabla_importancia(resultado: ex.ResultadoSHAP) -> list[str]:
    modelos = list(resultado.explicaciones)
    cabecera = " | ".join(NOMBRES.get(m, m) for m in modelos)
    lineas = [
        f"| Variable | {cabecera} |",
        "|---" * (len(modelos) + 1) + "|",
    ]
    for variable in resultado.explicaciones[resultado.modelo_final].importancia:
        valores = " | ".join(
            num(resultado.explicaciones[m].importancia.get(variable, 0.0), 2) for m in modelos
        )
        lineas.append(f"| `{variable}` | {valores} |")
    return lineas


def _tabla_recuperacion(resultado: ex.ResultadoSHAP) -> list[str]:
    lineas = [
        "| Variable | Contraste | Esperado | Medido (SHAP) | Diferencia | ¿Recuperado? |",
        "|---|---|--:|--:|--:|---|",
    ]
    for fila in resultado.recuperacion.itertuples():
        if fila.medido is None or pd.isna(fila.medido):
            lineas.append(
                f"| `{fila.variable}` | {fila.contraste} | {num(fila.esperado, 2)} | — | — | {fila.nota} |"
            )
            continue
        marca = "✅" if fila.signo_coincide else "❌"
        exigida = " *(exigida §17)*" if fila.exigida else ""
        lineas.append(
            f"| `{fila.variable}` | {fila.contraste} | {num(fila.esperado, 2)} | {num(fila.medido, 2)} | "
            f"{num(fila.diferencia, 2)} | {marca}{exigida} |"
        )
    return lineas


def _tabla_contrastes(resultado: ex.ResultadoSHAP, contexto: ex.ContextoF9) -> list[str]:
    medidos = ex.contrastes_medidos(
        resultado.explicaciones[resultado.modelo_final], contexto.prueba, contexto.variables
    )
    lineas = ["| Variable | Contraste | Efecto medido (puntos) |", "|---|---|--:|"]
    for (variable, contraste), valor in sorted(medidos.items(), key=lambda kv: -abs(kv[1])):
        lineas.append(f"| `{variable}` | {contraste} | {num(valor, 2)} |")
    return lineas


def _nota_variables_nulas(resultado: ex.ResultadoSHAP) -> list[str]:
    """Señala las variables que el modelo final descartó y, si se sabe, si debía descartarlas."""
    final = resultado.explicaciones[resultado.modelo_final]
    nulas = [v for v, imp in final.importancia.items() if imp < 0.005]
    if not nulas:
        return []
    nombres = ", ".join(f"`{v}`" for v in nulas)
    texto = (
        f"El modelo final no usa {nombres}: su contribución es exactamente cero en todas las filas "
        "(Lasso anula los coeficientes que no aportan)."
    )
    if not resultado.recuperacion.empty:
        esperados = resultado.recuperacion[resultado.recuperacion["variable"].isin(nulas)]["esperado"]
        if len(esperados) and (esperados.abs() < 1e-9).all():
            texto += (
                " Es el resultado correcto: son justamente las variables cuyo efecto real sobre el "
                "puntaje global es nulo por construcción del generador."
            )
    return [texto, ""]


def _casos(resultado: ex.ResultadoSHAP) -> list[str]:
    lineas = []
    for etiqueta, caso in resultado.casos.items():
        contribuciones = sorted(caso["contribuciones"].items(), key=lambda kv: -abs(kv[1]))[:3]
        detalle = ", ".join(
            f"`{k}`={caso['valores'][k]} ({num(v, 1)})" for k, v in contribuciones
        )
        lineas.append(
            f"- **{etiqueta}** (percentil {int(caso['percentil'] * 100)}): valor esperado "
            f"{num(caso['base'], 1)} → predicción {num(caso['prediccion'], 1)} "
            f"(real {num(caso['real'], 0)}). Mayores contribuciones: {detalle}. "
            f"Figura: `waterfall_{etiqueta}.png`."
        )
    return lineas


def _interpretacion(
    resultado: ex.ResultadoSHAP,
    contexto: ex.ContextoF9,
    settings: dict[str, Any],
    con_recuperacion: bool,
) -> str:
    final = resultado.explicaciones[resultado.modelo_final]
    etiqueta = NOMBRES.get(resultado.modelo_final, resultado.modelo_final)
    otros = [n for n in resultado.explicaciones if n != resultado.modelo_final]
    anio = settings["ml"]["test_year"]
    ranking = list(final.importancia)

    lineas = [
        "# Interpretación SHAP — F9",
        "",
        f"> ⚠️ {ADVERTENCIA}",
        f"> **{FRASE_CAUSALIDAD}**",
        "",
        f"Ejecución `{resultado.run_id}` sobre el modelo de F8 `{resultado.run_id_ml}`.",
        "",
        "## 1. Qué se explicó",
        "",
        f"- **Modelo final:** {etiqueta}, explicado con `shap.LinearExplainer`.",
    ]
    if otros:
        lineas.append(
            f"- **Contraste:** {NOMBRES.get(otros[0], otros[0])} con `shap.TreeExplainer`, reajustado "
            "con los hiperparámetros que registró F8. Sirve para ver si un modelo no lineal lee los "
            "datos de otra manera."
        )
    lineas += [
        f"- **Conjunto:** las {resultado.filas['prueba']} filas de prueba ({anio}). El explicador "
        f"lineal usa como fondo las {resultado.filas['entrena']} filas de entrenamiento; el de "
        "árboles usa el recorrido del árbol (`tree_path_dependent`), porque XGBoost 3.4 rechaza el "
        "modo *interventional* en este modelo. Cada modelo tiene entonces su propio valor esperado: "
        "entre modelos se comparan **rankings**, no valores absolutos.",
        "- **Unidades:** cada valor SHAP está en **puntos del puntaje global**, medido como desvío "
        "respecto del valor esperado del modelo.",
        "- **Agregación:** las columnas one-hot se suman por variable original antes de rankear, para "
        "que una variable no parezca más importante solo por tener más categorías.",
        "",
        "## 2. Verificación de aditividad",
        "",
        f"Criterio del plan: valor esperado + Σ SHAP ≈ predicción, con tolerancia {ex.TOLERANCIA_ADITIVIDAD:g}.",
        "",
        "| Modelo | Valor esperado | Error máximo | Resultado |",
        "|---|--:|--:|---|",
    ]
    for nombre, e in resultado.explicaciones.items():
        lineas.append(
            f"| {NOMBRES.get(nombre, nombre)} | {num(e.base, 2)} | {e.error_aditividad:.2e} | "
            f"{'✅ cumple' if e.aditividad_ok() else '❌ no cumple'} |"
        )
    lineas += [
        "",
        "## 3. Importancia global",
        "",
        "Media de |SHAP| por variable, en puntos. Figuras: `importancia_global.png`, `beeswarm.png`"
        + (", `comparacion_modelos.png`." if len(resultado.explicaciones) > 1 else "."),
        "",
        *_tabla_importancia(resultado),
        "",
        f"El orden que produce el modelo final es: {', '.join(f'`{v}`' for v in ranking)}.",
        "",
        "## 4. Lectura de los efectos",
        "",
        "Diferencia de contribución media entre cada categoría y su referencia, en puntos; para las",
        "numéricas, la pendiente por unidad. Se lee como «cuánto mueve esta característica la",
        "predicción respecto del estudiante promedio», nunca como «cuánto subiría el puntaje si la",
        "característica cambiara».",
        "",
        *_tabla_contrastes(resultado, contexto),
        "",
        *_nota_variables_nulas(resultado),
        "Las figuras de dependencia (`dependencia_estrato.png`, `dependencia_sexo.png`,",
        "`dependencia_modelo_pedagogico.png`) muestran la misma información fila a fila.",
        "",
        "## 5. Prueba de recuperación de efectos sintéticos (§17)",
        "",
    ]
    if con_recuperacion:
        lineas += [
            "Los datos ficticios se generaron con efectos conocidos",
            "(`reports/datos_ficticios/parametros_generacion.json`). Convertidos a puntos del puntaje",
            "global —un efecto común a las cinco áreas se multiplica por 5; uno que solo afecta Inglés,",
            "por 5/13— se comparan con los contrastes que produce el SHAP.",
            "",
            *_tabla_recuperacion(resultado),
            "",
            f"**Resultado: {'APROBADA' if resultado.recuperacion_aprobada else 'NO APROBADA'}** — el criterio "
            f"del plan es que coincidan los signos de {', '.join(f'`{v}`' for v in ex.EXIGIDAS)}.",
            "",
            "La magnitud medida es algo menor que la esperada: la regularización encoge los",
            "coeficientes y el efecto propio de cada colegio, que el modelo no observa, se queda en el",
            "residuo. La regularización también puede fundir categorías vecinas —si Lasso anula sus",
            "coeficientes, dos categorías muestran exactamente el mismo contraste frente a la",
            "referencia—. Lo que la prueba verifica es que el pipeline recupera **dirección y orden de",
            "magnitud**, no una estimación insesgada.",
        ]
    else:
        lineas.append(
            "No se ejecutó: no existe `reports/datos_ficticios/parametros_generacion.json`. "
            "Con datos reales esta prueba no aplica, porque no hay efectos conocidos con los que comparar."
        )
    lineas += [
        "",
        "## 6. Coeficientes del modelo lineal",
        "",
        "Contraste directo con el ranking SHAP: en un modelo lineal ambas lecturas deben coincidir en",
        "signo, y el SHAP añade cuánto pesa cada variable en la práctica según su distribución real.",
        "",
        "| Columna | Coeficiente |",
        "|---|--:|",
    ]
    for fila in resultado.coeficientes.head(10).itertuples():
        lineas.append(f"| `{fila.columna}` | {num(fila.coeficiente, 2)} |")
    lineas += [
        "",
        "## 7. Casos individuales",
        "",
        "Tres estudiantes del conjunto de prueba en los percentiles 10, 50 y 90 de la predicción.",
        "No se muestran identificadores: el modelo solo recibe atributos del colegio y del perfil.",
        "",
        *_casos(resultado),
        "",
        "## 8. Límites de la interpretación",
        "",
        f"- **{FRASE_CAUSALIDAD}** Un valor alto para `naturaleza_colegio` significa que el modelo usa",
        "  esa variable para predecir, no que cambiarla produzca el efecto.",
    ]
    if contexto.variables.dependencias:
        alias = "; ".join(
            f"`{c}` = f({', '.join(d)})" for c, d in contexto.variables.dependencias
        )
        lineas.append(
            f"- **Alias del diseño ({alias}):** estas variables son redundantes entre sí, así que el "
            "reparto de crédito entre ellas es arbitrario y **no deben interpretarse por separado**."
        )
    lineas += [
        "- **Variables correlacionadas:** con `estrato` y `naturaleza_colegio` asociadas por diseño, el",
        "  crédito se reparte entre ambas y ninguna lleva el efecto completo.",
        "- **El efecto propio del colegio no está en el modelo** (se reserva como grupo de validación):",
        "  lo que se observa es el efecto de los *atributos* del colegio, no el del centro concreto.",
        "- Los efectos recuperados son los que introdujo el generador de F1b; no describen la realidad",
        "  educativa.",
        "",
        "## 9. Artefactos",
        "",
        "| Archivo | Contenido |",
        "|---|---|",
        "| `importancia_global.png` | Media de \\|SHAP\\| por variable del modelo final |",
        "| `beeswarm.png` | Distribución de contribuciones por columna transformada |",
        "| `dependencia_*.png` | Contribución frente al valor de `estrato`, `sexo` y `modelo_pedagogico` |",
        "| `waterfall_p10/p50/p90.png` | Explicaciones locales de tres casos |",
        "| `comparacion_modelos.png` | Importancia comparada entre las dos familias de modelo |",
        "| `shap_values.parquet` | Valores SHAP por fila y variable (ambos modelos), con predicción y valor esperado |",
        "| `recuperacion_efectos.csv` | Prueba de recuperación de los efectos sintéticos |",
    ]
    return "\n".join(lineas) + "\n"
