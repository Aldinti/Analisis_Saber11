"""Ejecución del pipeline completo con un solo comando (F11; plan §23).

Dos niveles: la lógica de la cadena se prueba con etapas simuladas (rápido y exhaustivo) y
el criterio de aceptación —«desde cero termina con código 0 y se puede repetir»— se prueba
de verdad, con un proyecto temporal y un CSV en formato de fuente.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import pytest
import yaml

from saber11 import pipeline
from saber11.config import get_settings, get_source_contract
from saber11.metadata import run_log

CLAVE = "clave-de-prueba-0123456789abcdef0123456789"


# ---------------------------------------------------------------- cadena con etapas simuladas
@pytest.fixture()
def secuencia_simulada(monkeypatch):
    """Sustituye las etapas por funciones que solo registran su nombre."""
    ejecutadas: list[str] = []

    def etapa(nombre: str, codigo: int = 0):
        def _ejecutar(settings, contrato, raiz):
            ejecutadas.append(nombre)
            return codigo
        return _ejecutar

    def instalar(codigos: dict[str, int] | None = None):
        codigos = codigos or {}
        monkeypatch.setattr(pipeline, "SECUENCIA", tuple(
            (n, etapa(n, codigos.get(n, 0))) for n in pipeline.NOMBRES_SECUENCIA
        ))
        return ejecutadas

    return instalar


def settings_temporal(raiz: Path) -> dict:
    settings = get_settings()
    settings["paths"] = {**settings["paths"], "metadata": "data/metadata", "reports": "reports"}
    return settings


def test_ejecuta_todas_las_etapas_en_orden(tmp_path, secuencia_simulada):
    ejecutadas = secuencia_simulada()
    codigo, resultados = pipeline.ejecutar_todo(settings_temporal(tmp_path), {}, tmp_path)
    assert codigo == 0
    assert ejecutadas == list(pipeline.NOMBRES_SECUENCIA)
    assert [r.nombre for r in resultados] == list(pipeline.NOMBRES_SECUENCIA)
    assert all(r.exitosa for r in resultados)


def test_se_detiene_en_la_primera_etapa_que_falla(tmp_path, secuencia_simulada):
    ejecutadas = secuencia_simulada({"gold": 4})
    codigo, resultados = pipeline.ejecutar_todo(settings_temporal(tmp_path), {}, tmp_path)
    assert codigo == 4
    assert ejecutadas[-1] == "gold"
    assert "ml" not in ejecutadas, "no deben ejecutarse las etapas posteriores al fallo"
    assert [r.nombre for r in resultados][-1] == "gold"


def test_desde_arranca_en_la_etapa_indicada(tmp_path, secuencia_simulada):
    ejecutadas = secuencia_simulada()
    codigo, _ = pipeline.ejecutar_todo(settings_temporal(tmp_path), {}, tmp_path, desde="ml")
    assert codigo == 0
    assert ejecutadas == ["ml", "shap", "fairness"]


def test_desde_rechaza_una_etapa_inexistente(tmp_path, secuencia_simulada):
    secuencia_simulada()
    with pytest.raises(ValueError, match="Etapa desconocida"):
        pipeline.ejecutar_todo(settings_temporal(tmp_path), {}, tmp_path, desde="inexistente")


def test_publica_manifiesto_y_registra_la_ejecucion(tmp_path, secuencia_simulada):
    secuencia_simulada({"silver": 1})
    pipeline.ejecutar_todo(settings_temporal(tmp_path), {}, tmp_path)

    manifiesto = (tmp_path / "reports/operacion/ultima_ejecucion.md").read_text(encoding="utf-8")
    assert "detenida (código 1)" in manifiesto
    assert "`silver`" in manifiesto
    assert "Etapas no ejecutadas:" in manifiesto and "`gold`" in manifiesto

    registros = run_log.leer(tmp_path / "data/metadata/run_log.parquet")
    fila = next(r for r in registros if r["etapa"] == "pipeline")
    assert fila["estado"] == "fallido"
    detalle = json.loads(fila["detalle"])
    assert detalle["codigo"] == 1
    assert [e["etapa"] for e in detalle["etapas"]] == ["validate-source", "bronze", "silver"]


# ---------------------------------------------------------------- CLI
def espiar_ejecutar_todo(monkeypatch) -> dict:
    """Sustituye la cadena completa por un doble que anota con qué la llamaron."""
    visto: dict = {}

    def doble(settings, contrato, raiz, desde=None):
        visto.update(desde=desde, nombre=settings.get("app", {}).get("name"))
        return 0, []

    monkeypatch.setattr(pipeline, "ejecutar_todo", doble)
    return visto


def test_la_cli_sin_stage_ejecuta_la_cadena_completa(monkeypatch):
    visto = espiar_ejecutar_todo(monkeypatch)
    assert pipeline.main(["run"]) == 0
    assert visto["desde"] is None


def test_la_cli_pasa_el_from(monkeypatch):
    visto = espiar_ejecutar_todo(monkeypatch)
    assert pipeline.main(["run", "--from", "gold"]) == 0
    assert visto["desde"] == "gold"


def test_stage_y_from_son_excluyentes():
    with pytest.raises(SystemExit):
        pipeline.main(["run", "--stage", "ml", "--from", "gold"])


def test_config_alternativo(tmp_path, monkeypatch):
    """`--config` permite apuntar a otra configuración sin tocar la del repositorio."""
    settings = get_settings()
    settings["app"]["name"] = "Config_De_Prueba"
    ruta = tmp_path / "otro_settings.yaml"
    ruta.write_text(yaml.safe_dump(settings, allow_unicode=True), encoding="utf-8")
    visto = espiar_ejecutar_todo(monkeypatch)
    assert pipeline.main(["--config", str(ruta), "run"]) == 0
    assert visto["nombre"] == "Config_De_Prueba"


# ---------------------------------------------------------------- criterio de aceptación F11
@dataclass
class Ejecucion:
    raiz: Path
    settings: dict
    codigo: int
    resultados: list


def _proyecto_desde_cero(raiz: Path, csv_fuente, monkeypatch) -> dict:
    """Proyecto vacío con solo lo que necesita una instalación nueva: el CSV y la configuración."""
    monkeypatch.setenv("SABER11_HMAC_KEY", CLAVE)
    settings = get_settings()
    settings["ml"] = {**settings["ml"], "cv_splits": 3}
    landing = raiz / settings["paths"]["landing"]
    landing.mkdir(parents=True)
    csv_fuente(landing / settings["source"]["file_name"])
    seguridad = raiz / settings["security"]["example_file"]
    seguridad.parent.mkdir(parents=True, exist_ok=True)
    seguridad.write_text(
        "email_rector,nombre_colegio\n" + "".join(f"rector.c{i:02d}@example.org,C{i:02d}\n" for i in range(6)),
        encoding="utf-8",
    )
    return settings


@pytest.fixture(scope="module")
def ejecucion_desde_cero(tmp_path_factory, csv_fuente) -> Ejecucion:
    with pytest.MonkeyPatch.context() as mp:
        raiz = tmp_path_factory.mktemp("f11")
        settings = _proyecto_desde_cero(raiz, csv_fuente, mp)
        codigo, resultados = pipeline.ejecutar_todo(settings, get_source_contract(), raiz)
        yield Ejecucion(raiz, settings, codigo, resultados)


def test_desde_cero_termina_con_codigo_cero(ejecucion_desde_cero):
    """Criterio de aceptación de F11: un entorno limpio corre el pipeline entero de un comando."""
    assert ejecucion_desde_cero.codigo == 0, [
        (r.nombre, r.codigo) for r in ejecucion_desde_cero.resultados
    ]
    assert [r.nombre for r in ejecucion_desde_cero.resultados] == list(pipeline.NOMBRES_SECUENCIA)


def test_desde_cero_deja_todos_los_artefactos(ejecucion_desde_cero):
    raiz = ejecucion_desde_cero.raiz
    for relativa in (
        "data/bronze", "data/silver/silver_resultados.parquet", "data/gold/ml_dataset.parquet",
        "data/gold/fact_resultado", "data/metadata/run_log.parquet",
        "reports/ml/comparacion_modelos.md", "reports/shap/interpretacion.md",
        "reports/fairness/informe_sesgos.md", "reports/operacion/ultima_ejecucion.md",
        "docs/ml/variables_modelo.md",
    ):
        assert (raiz / relativa).exists(), relativa


def test_la_reejecucion_es_idempotente_y_reproducible(ejecucion_desde_cero):
    """Segunda pasada con los mismos datos y semilla: Bronze se omite y las métricas no cambian."""
    raiz, settings = ejecucion_desde_cero.raiz, ejecucion_desde_cero.settings
    metricas_antes = (raiz / "reports/ml/comparacion_modelos.md").read_text(encoding="utf-8")

    with pytest.MonkeyPatch.context() as mp:
        mp.setenv("SABER11_HMAC_KEY", CLAVE)
        codigo, _ = pipeline.ejecutar_todo(settings, get_source_contract(), raiz)
    assert codigo == 0

    registros = run_log.leer(raiz / "data/metadata/run_log.parquet")
    bronze = [r for r in registros if r["etapa"] == "bronze"]
    assert bronze[-1]["estado"] == "omitido", "el mismo archivo no debe reingerirse"

    despues = (raiz / "reports/ml/comparacion_modelos.md").read_text(encoding="utf-8")
    def sin_run_id(texto: str) -> str:
        return "\n".join(x for x in texto.splitlines() if not x.startswith("Ejecución `"))

    assert sin_run_id(despues) == sin_run_id(metricas_antes)
