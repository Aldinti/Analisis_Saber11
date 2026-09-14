"""Módulo de seudonimización criptográfica segura con HMAC-SHA-256."""
from __future__ import annotations

import hashlib
import hmac


def pseudonymize_id(secret_key: str, doc_id: str | int) -> str:
    """Calcula el identificador seudonimizado determinista (HMAC-SHA-256).

    Parámetros:
        secret_key: Clave secreta conocida solo por el sistema/custodio.
        doc_id: Número de documento o identificador natural.

    Retorna:
        Cadena hexadecimal de 64 caracteres.
    """
    if not secret_key:
        raise ValueError("La clave secreta HMAC no puede estar vacía.")
    raw_id = str(doc_id).strip()
    if not raw_id:
        raise ValueError("El identificador del documento no puede estar vacío.")

    return hmac.new(
        key=secret_key.encode("utf-8"),
        msg=raw_id.encode("utf-8"),
        digestmod=hashlib.sha256,
    ).hexdigest()
