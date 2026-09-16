"""Fixtures compartidas por las pruebas."""
from __future__ import annotations

from collections.abc import Callable

import numpy as np
import pandas as pd
import pytest

# Efectos sintéticos en puntos del puntaje global, equivalentes a los del generador de F1b
# convertidos con la fórmula del Global (×5). Permiten probar la recuperación de F9.
EFECTO_ESTRATO = 12.5
EFECTO_PRIVADA = 4.0 * 5 + 5.0 * 5 / 13
EFECTO_RURAL = -20.0


def _marco_ml(
    n_colegios: int = 4, anios: tuple[int, ...] = (2021, 2022, 2023, 2024), por_grupo: int = 10
) -> pd.DataFrame:
    """Conjunto sintético con la misma forma y los mismos efectos que `gold.ml_dataset` (F8)."""
    rng = np.random.default_rng(7)
    filas = []
    for i in range(n_colegios):
        privada = bool(i % 2)
        urbana = i < n_colegios // 2
        for anio in anios:
            for j in range(por_grupo):
                estrato = int(rng.integers(1, 7))
                filas.append({
                    "resultado_id": len(filas) + 1,
                    # Igual que el diseño real: el periodo es la interacción naturaleza × zona,
                    # no un alias directo de ninguna de las dos.
                    "periodo": "I" if privada == urbana else "II",
                    "anio": anio,
                    "nombre_colegio": f"C{i}",
                    "naturaleza_colegio": "Privada" if privada else "Pública",
                    "modelo_pedagogico": ["Tradicional", "Constructivista"][i % 2],
                    "zona": "Urbana" if urbana else "Rural",
                    "sexo": "Femenino" if j % 2 else "Masculino",
                    "estrato": estrato,
                    "puntaje_global": float(
                        400
                        + EFECTO_ESTRATO * (estrato - 3)
                        + (EFECTO_PRIVADA if privada else 0.0)
                        + (0.0 if urbana else EFECTO_RURAL)
                        + rng.normal(0, 25)
                    ),
                })
    return pd.DataFrame(filas)


@pytest.fixture(scope="session")
def marco_ml() -> Callable[..., pd.DataFrame]:
    """Fábrica del conjunto sintético de modelado."""
    return _marco_ml


def settings_ml_dict() -> dict:
    """Configuración mínima de F8/F9 para un proyecto temporal (una copia nueva cada vez)."""
    return {
        "paths": {"gold": "data/gold", "models": "models", "reports": "reports"},
        "ml": {
            "target": "puntaje_global",
            "cv_group_col": "nombre_colegio",
            "test_year": 2024,
            "cv_splits": 3,
            "random_state": 20260913,
        },
    }


@pytest.fixture(scope="session")
def settings_ml_factory() -> Callable[[], dict]:
    """Fábrica de configuración, para las fixtures de alcance módulo."""
    return settings_ml_dict


@pytest.fixture()
def settings_ml(settings_ml_factory: Callable[[], dict]) -> dict:
    return settings_ml_factory()
