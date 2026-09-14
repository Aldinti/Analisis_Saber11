"""Módulo de configuración centralizada para el proyecto Saber 11."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv

# Cargar variables de entorno desde .env si existe
load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONFIG_DIR = PROJECT_ROOT / "config"
SETTINGS_PATH = CONFIG_DIR / "settings.yaml"


def load_yaml(path: Path) -> dict[str, Any]:
    """Carga de forma segura un archivo YAML."""
    if not path.exists():
        raise FileNotFoundError(f"Archivo de configuración no encontrado: {path}")
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def get_settings() -> dict[str, Any]:
    """Obtiene la configuración general desde settings.yaml."""
    return load_yaml(SETTINGS_PATH)


def get_source_contract() -> dict[str, Any]:
    """Obtiene el contrato de la fuente de datos."""
    return load_yaml(CONFIG_DIR / "source_contract.yaml")


def get_dq_rules() -> dict[str, Any]:
    """Obtiene el catálogo de reglas de calidad de datos."""
    return load_yaml(CONFIG_DIR / "dq_rules.yaml")


def get_hmac_key() -> str:
    """Obtiene la clave secreta para seudonimización HMAC-SHA-256."""
    key = os.getenv("SABER11_HMAC_KEY", "").strip()
    if not key:
        raise ValueError(
            "La variable de entorno SABER11_HMAC_KEY no está definida o está vacía. "
            "Defínela en el archivo .env o en el entorno del sistema."
        )
    if len(key) < 32:
        raise ValueError(
            "La clave SABER11_HMAC_KEY es demasiado corta. Debe tener al menos 32 caracteres."
        )
    return key
