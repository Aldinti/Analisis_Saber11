"""Fixtures compartidas por las pruebas."""
from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import numpy as np
import pandas as pd
import pytest


def _marco_ml(
    n_colegios: int = 4, anios: tuple[int, ...] = (2021, 2022, 2023, 2024), por_grupo: int = 10
) -> pd.DataFrame:
    """Conjunto sintético con la misma forma que `gold.ml_dataset` (F8)."""
    rng = np.random.default_rng(7)
    filas = []
    for i in range(n_colegios):
        for anio in anios:
            for j in range(por_grupo):
                privada = bool(i % 2)
                estrato = int(rng.integers(1, 7))
                filas.append({
                    "resultado_id": len(filas) + 1,
                    "anio": anio,
                    "periodo": "I" if privada else "II",
                    "nombre_colegio": f"C{i}",
                    "naturaleza_colegio": "Privada" if privada else "Pública",
                    "modelo_pedagogico": ["Tradicional", "Constructivista"][i % 2],
                    "zona": "Urbana" if i < n_colegios // 2 else "Rural",
                    "sexo": "Femenino" if j % 2 else "Masculino",
                    "estrato": estrato,
                    "puntaje_global": float(
                        380 + 12 * estrato + (20 if privada else 0) + rng.normal(0, 30)
                    ),
                })
    return pd.DataFrame(filas)


@pytest.fixture()
def marco_ml() -> Callable[..., pd.DataFrame]:
    """Fábrica del conjunto sintético de modelado."""
    return _marco_ml


@pytest.fixture()
def settings_ml(tmp_path: Path) -> dict:
    """Configuración mínima de F8 apuntando a un proyecto temporal."""
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
