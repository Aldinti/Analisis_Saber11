"""Ejecución completa del experimento de F8: compara, selecciona y publica artefactos.

Orden deliberado (plan §16.3–§16.4): la CV decide el modelo **antes** de tocar el año de
prueba; el conjunto de prueba se evalúa una sola vez y sirve para medir, no para elegir.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import joblib
import pandas as pd

from saber11.ml import dataset as ds
from saber11.ml import evaluate as ev
from saber11.ml import informe
from saber11.ml import train as tr

ADVERTENCIA = (
    "Los datos son ficticios (plan §4, supuesto S7): estos resultados validan el pipeline, "
    "no describen la realidad educativa."
)


@dataclass
class ResultadoML:
    """Salida de F8: métricas, modelo elegido y rutas de los artefactos publicados."""

    run_id: str
    variables: ds.Variables
    resultados: dict[str, ev.ResultadoModelo]
    seleccionado: str
    motivo_seleccion: str
    mejora_vs_baseline: dict[str, float]
    temporal: dict[str, list[dict[str, Any]]]
    retenidos: dict[str, Any]
    referencia_colegio: dict[str, float]
    filas: dict[str, int]
    rutas: dict[str, Path] = field(default_factory=dict)

    @property
    def supera_baseline(self) -> bool:
        return self.mejora_vs_baseline["ic_inferior"] > 0

    def detalle(self) -> dict[str, Any]:
        return {
            "modelo": self.seleccionado,
            "motivo_seleccion": self.motivo_seleccion,
            "supera_baseline": self.supera_baseline,
            "mejora_vs_baseline": self.mejora_vs_baseline,
            "cv": {n: r.metricas_cv for n, r in self.resultados.items()},
            "test": {n: r.metricas_test for n, r in self.resultados.items()},
            "filas": self.filas,
            "predictoras": self.variables.predictoras,
            "excluidas": self.variables.excluidas,
            "artefactos": {k: v.as_posix() for k, v in self.rutas.items()},
            "advertencia": ADVERTENCIA,
        }


def ejecutar(settings: dict[str, Any], raiz: Path, run_id: str) -> ResultadoML:
    ml = settings["ml"]
    semilla = int(ml["random_state"])
    anio_test = int(ml["test_year"])
    n_splits = int(ml["cv_splits"])

    df = ds.cargar(settings, raiz)
    variables = ds.seleccionar_variables(df, settings)
    entrena, prueba = ds.separar_temporal(df, anio_test)

    # 1) Comparación por CV anidada (el conjunto de prueba todavía no se toca).
    resultados = {
        nombre: tr.validar_cruzado(spec, entrena, variables, semilla, n_splits)
        for nombre, spec in tr.ESPECIFICACIONES.items()
    }

    # 2) Ajuste final en todos los años de entrenamiento y robustez temporal.
    finales: dict[str, Any] = {}
    temporal: dict[str, list[dict[str, Any]]] = {}
    for nombre, spec in tr.ESPECIFICACIONES.items():
        pipeline, parametros = tr.ajustar_final(spec, entrena, variables, semilla, n_splits)
        finales[nombre] = (pipeline, parametros)
        resultados[nombre].mejores_parametros = parametros
        temporal[nombre] = tr.cv_temporal_expansiva(spec, entrena, variables, parametros, semilla)

    # 3) Selección con la regla §16.4, decidida solo con la CV.
    seleccionado, motivo = ev.seleccionar_modelo(resultados)

    # 4) Evaluación única del año de prueba para todos los modelos.
    X_prueba = tr.matriz(prueba, variables)
    y_prueba = prueba[variables.objetivo].to_numpy(dtype=float)
    grupos_prueba = prueba[variables.grupo].to_numpy()
    predicciones = {n: finales[n][0].predict(X_prueba) for n in resultados}
    for nombre, resultado in resultados.items():
        resultado.metricas_test = ev.metricas(y_prueba, predicciones[nombre])
        resultado.ic_test = ev.ic_bootstrap(
            y_prueba, predicciones[nombre], grupos_prueba, semilla=semilla
        )
    mejora = ev.ic_mejora(
        y_prueba, predicciones[seleccionado], predicciones["baseline_media"],
        grupos_prueba, semilla=semilla,
    )
    referencia = ev.metricas(
        y_prueba, ev.prediccion_media_por_grupo(entrena, prueba, variables.objetivo, variables.grupo)
    )

    # 5) Generalización a colegios nunca vistos.
    retenidos = tr.evaluar_colegios_retenidos(
        tr.ESPECIFICACIONES[seleccionado], entrena, prueba, variables,
        finales[seleccionado][1], ds.colegios_retenidos(df, settings), semilla,
    )

    resultado = ResultadoML(
        run_id=run_id,
        variables=variables,
        resultados=resultados,
        seleccionado=seleccionado,
        motivo_seleccion=motivo,
        mejora_vs_baseline=mejora,
        temporal=temporal,
        retenidos=retenidos,
        referencia_colegio=referencia,
        filas={"total": len(df), "entrena": len(entrena), "prueba": len(prueba),
               "colegios": int(df[variables.grupo].nunique())},
    )
    resultado.rutas = _publicar(
        resultado, settings, raiz, finales[seleccionado][0], prueba,
        predicciones[seleccionado], anio_test,
    )
    return resultado


def _publicar(
    resultado: ResultadoML,
    settings: dict[str, Any],
    raiz: Path,
    modelo_final: Any,
    prueba: pd.DataFrame,
    predicciones: Any,
    anio_test: int,
) -> dict[str, Path]:
    variables = resultado.variables
    destino = raiz / settings["paths"]["models"] / resultado.run_id
    destino.mkdir(parents=True, exist_ok=True)
    reportes = raiz / settings["paths"]["reports"] / "ml"
    reportes.mkdir(parents=True, exist_ok=True)

    joblib.dump(modelo_final, destino / "model.joblib")
    (destino / "params.json").write_text(
        json.dumps(
            {
                "run_id": resultado.run_id,
                "modelo": resultado.seleccionado,
                "parametros": resultado.resultados[resultado.seleccionado].mejores_parametros,
                "semilla": settings["ml"]["random_state"],
                "anio_prueba": anio_test,
                "variables": variables.a_dict(),
                "advertencia": ADVERTENCIA,
            },
            ensure_ascii=False, indent=2, default=str,
        ),
        encoding="utf-8",
    )
    (destino / "metrics.json").write_text(
        json.dumps(
            {
                "run_id": resultado.run_id,
                "seleccionado": resultado.seleccionado,
                "motivo_seleccion": resultado.motivo_seleccion,
                "supera_baseline": resultado.supera_baseline,
                "mejora_vs_baseline": resultado.mejora_vs_baseline,
                "referencia_media_colegio": resultado.referencia_colegio,
                "modelos": {n: r.a_dict() for n, r in resultado.resultados.items()},
                "temporal": resultado.temporal,
                "colegios_retenidos": resultado.retenidos,
                "filas": resultado.filas,
                "advertencia": ADVERTENCIA,
            },
            ensure_ascii=False, indent=2, default=str,
        ),
        encoding="utf-8",
    )

    # Predicciones del año de prueba: insumo de F9 (SHAP) y F10 (sesgos). Sin identificadores.
    salida = prueba[[*variables.predictoras, variables.grupo, variables.objetivo]].copy()
    salida["prediccion"] = predicciones
    salida["residuo"] = salida["prediccion"] - salida[variables.objetivo]
    ruta_predicciones = destino / "predicciones_test.parquet"
    salida.to_parquet(ruta_predicciones, index=False)

    filas_cv = [
        {"modelo": nombre, **{k: v for k, v in fold.items() if k != "colegios_valida"},
         "colegios_valida": ", ".join(fold["colegios_valida"])}
        for nombre, r in resultado.resultados.items() for fold in r.folds
    ]
    ruta_cv = reportes / "resultados_cv.csv"
    pd.DataFrame(filas_cv).to_csv(ruta_cv, index=False, encoding="utf-8")

    ruta_informe = reportes / "comparacion_modelos.md"
    ruta_informe.write_text(informe.comparacion(resultado, settings, anio_test), encoding="utf-8")

    ruta_variables = raiz / "docs" / "ml" / "variables_modelo.md"
    ruta_variables.parent.mkdir(parents=True, exist_ok=True)
    ruta_variables.write_text(informe.catalogo_variables(resultado), encoding="utf-8")

    return {
        "modelo": (destino / "model.joblib").relative_to(raiz),
        "params": (destino / "params.json").relative_to(raiz),
        "metricas": (destino / "metrics.json").relative_to(raiz),
        "predicciones": ruta_predicciones.relative_to(raiz),
        "cv": ruta_cv.relative_to(raiz),
        "informe": ruta_informe.relative_to(raiz),
        "variables": ruta_variables.relative_to(raiz),
    }
