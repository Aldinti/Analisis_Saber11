"""Utilidades de logging estructurado sin exposición de datos personales."""
from __future__ import annotations

import logging
import sys


def setup_logger(name: str = "saber11", level: int = logging.INFO) -> logging.Logger:
    """Configura y retorna un logger formateado para la consola y trazabilidad."""
    logger = logging.getLogger(name)
    if not logger.handlers:
        logger.setLevel(level)
        handler = logging.StreamHandler(sys.stdout)
        formatter = logging.Formatter(
            fmt="%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    return logger
