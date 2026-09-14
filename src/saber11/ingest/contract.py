"""Validación del archivo fuente contra config/source_contract.yaml (fase F2).

Solo verifica estructura: encoding, separador, nombres y orden de columnas, número de campos por
fila, obligatorios no vacíos y año de 4 dígitos. La tipificación fina corresponde a Silver (F3).
Los mensajes de error nunca incluyen valores de las celdas (la fuente contiene PII): solo
números de línea y nombres de columna.
"""
from __future__ import annotations

import codecs
import csv
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

MAX_ERRORES_DETALLADOS = 20
PATRON_ANIO = re.compile(r"^\d{4}$")


@dataclass
class ResultadoContrato:
    archivo: str
    aprobado: bool
    filas_datos: int = 0
    columnas: int = 0
    errores: list[str] = field(default_factory=list)
    errores_por_tipo: dict[str, int] = field(default_factory=dict)

    def a_dict(self) -> dict[str, Any]:
        return asdict(self)


class ContratoFuenteError(Exception):
    """El archivo fuente no cumple el contrato."""

    def __init__(self, resultado: ResultadoContrato):
        self.resultado = resultado
        super().__init__(f"Contrato de fuente incumplido ({len(resultado.errores)} errores): "
                         + "; ".join(resultado.errores[:5]))


def _registrar(res: ResultadoContrato, tipo: str, mensaje: str) -> None:
    res.errores_por_tipo[tipo] = res.errores_por_tipo.get(tipo, 0) + 1
    if len(res.errores) < MAX_ERRORES_DETALLADOS:
        res.errores.append(mensaje)


def _es_utf8_no_ascii(ruta: Path) -> bool:
    datos = ruta.read_bytes()
    if datos.isascii():
        return False
    try:
        datos.decode("utf-8")
        return True
    except UnicodeDecodeError:
        return False


def validar_fuente(ruta: Path, contrato: dict[str, Any]) -> ResultadoContrato:
    spec = contrato["source_contract"]
    encoding, delimitador = spec["encoding"], spec["delimiter"]
    esperadas = [c["name"] for c in spec["columns"]]
    obligatorias = {i for i, c in enumerate(spec["columns"]) if c.get("required")}
    res = ResultadoContrato(archivo=ruta.name, aprobado=False)

    if not ruta.is_file() or ruta.stat().st_size == 0:
        _registrar(res, "archivo", "archivo inexistente o vacío")
        return res
    if len(esperadas) != spec["expected_columns_count"]:
        raise ValueError("source_contract.yaml inconsistente: expected_columns_count no coincide con columns")
    if codecs.lookup(encoding).name != "utf-8" and _es_utf8_no_ascii(ruta):
        _registrar(res, "encoding", f"el archivo es UTF-8 con caracteres no ASCII; el contrato exige {encoding}")
        return res

    try:
        with ruta.open(encoding=encoding, errors="strict", newline="") as f:
            lector = csv.reader(f, delimiter=delimitador)
            cabecera = next(lector, None)
            if cabecera is None:
                _registrar(res, "cabecera", "archivo sin cabecera")
                return res
            if cabecera and cabecera[0].startswith("﻿"):
                cabecera[0] = cabecera[0].removeprefix("﻿")
            res.columnas = len(cabecera)
            if len(cabecera) == 1 and delimitador not in cabecera[0]:
                _registrar(res, "separador", f"la cabecera no contiene el separador '{delimitador}'")
                return res
            if cabecera != esperadas:
                faltantes = [c for c in esperadas if c not in cabecera]
                sobrantes = [c for c in cabecera if c not in esperadas]
                detalle = f"faltantes={faltantes}, sobrantes={sobrantes}" if faltantes or sobrantes else "orden distinto"
                _registrar(res, "cabecera", f"columnas no coinciden con el contrato: {detalle}")
                return res

            idx_anio = esperadas.index("año") if "año" in esperadas else None
            for linea, fila in enumerate(lector, start=2):
                if not fila:
                    continue
                res.filas_datos += 1
                if len(fila) != len(esperadas):
                    _registrar(res, "campos", f"línea {linea}: {len(fila)} campos, se esperaban {len(esperadas)}")
                    continue
                vacias = [esperadas[i] for i in obligatorias if not fila[i].strip()]
                if vacias:
                    _registrar(res, "obligatorio_vacio", f"línea {linea}: columnas obligatorias vacías {vacias}")
                if idx_anio is not None and not PATRON_ANIO.match(fila[idx_anio].strip()):
                    _registrar(res, "anio", f"línea {linea}: 'año' no tiene 4 dígitos")
    except UnicodeDecodeError as e:
        _registrar(res, "encoding", f"bytes no decodificables como {encoding} (posición {e.start})")
        return res

    if res.filas_datos == 0:
        _registrar(res, "filas", "el archivo no tiene filas de datos")
    res.aprobado = not res.errores_por_tipo
    return res
