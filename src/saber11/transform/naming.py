"""Utilidades de estandarización y normalización de nombres de columnas a snake_case ASCII."""
from __future__ import annotations

import re
import unicodedata


def normalize_colname(name: str) -> str:
    """Normaliza un nombre de columna a snake_case ASCII limpio sin tildes ni caracteres especiales.

    Ejemplos:
        'Lectura Crítica' -> 'lectura_critica'
        'año' -> 'anio'
        'Sociales y Ciudadana' -> 'sociales_y_ciudadana'
    """
    # Manejo específico para la eñe antes de descomponer
    text = name.replace("ñ", "ni").replace("Ñ", "Ni")
    # Descomposición Unicode y eliminación de diacríticos
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    # Minúsculas y reemplazo de no alfanuméricos por guion bajo
    text = re.sub(r"[^a-zA-Z0-9]+", "_", text.lower()).strip("_")
    return text
