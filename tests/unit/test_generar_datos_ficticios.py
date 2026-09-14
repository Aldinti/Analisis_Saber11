"""Pruebas del generador de datos ficticios (fase F1b).

Escritas con unittest para ejecutarse sin dependencias extra; pytest también las descubre.
    python -m unittest discover -s tests/unit -v
"""
from __future__ import annotations

import hashlib
import importlib.util
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import pandas as pd

RAIZ = Path(__file__).resolve().parents[2]
SCRIPT = RAIZ / "scripts" / "generar_datos_ficticios.py"
# El CSV de trabajo puede estar ya ampliado; las pruebas parten del original si existe.
ORIGINAL = next(p for p in (RAIZ / "ResultadosICFES.original.csv", RAIZ / "ResultadosICFES.csv") if p.exists())

spec = importlib.util.spec_from_file_location("generar_datos_ficticios", SCRIPT)
gen = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = gen
spec.loader.exec_module(gen)


def sha256(ruta: Path) -> str:
    return hashlib.sha256(ruta.read_bytes()).hexdigest()


def ejecutar(csv: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--csv", str(csv), "--reportes", str(csv.parent / "rep"), *args],
        capture_output=True, text=True,
    )


class TestGenerador(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp())
        self.csv = self.tmp / "R.csv"
        shutil.copy2(ORIGINAL, self.csv)

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_misma_semilla_mismo_csv(self) -> None:
        self.assertEqual(ejecutar(self.csv, "--seed", "7").returncode, 0)
        primero = sha256(self.csv)
        self.assertEqual(ejecutar(self.csv, "--seed", "7", "--force").returncode, 0)
        self.assertEqual(primero, sha256(self.csv))

    def test_segunda_ejecucion_sin_force_aborta_sin_modificar(self) -> None:
        self.assertEqual(ejecutar(self.csv).returncode, 0)
        antes = sha256(self.csv)
        r = ejecutar(self.csv)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("--force", r.stderr)
        self.assertEqual(antes, sha256(self.csv))

    def test_validar_detecta_fila_original_alterada(self) -> None:
        original = gen.leer_csv(self.csv)
        nuevos, _ = gen.ampliar(original, 1)
        final = pd.concat([original, nuevos], ignore_index=True)
        self.assertTrue(gen.validar(original, final)["aprobado"])
        final.loc[0, "Global"] = final.loc[0, "Global"] + 1
        reporte = gen.validar(original, final)
        self.assertFalse(reporte["aprobado"])
        self.assertFalse(reporte["checks"]["originales_intactos"])

    def test_factores_independientes_y_confusion_detectada(self) -> None:
        original = gen.leer_csv(self.csv)
        nuevos, _ = gen.ampliar(original, 1)
        final = pd.concat([original, nuevos], ignore_index=True)
        reporte = gen.validar(original, final)
        self.assertLessEqual(max(reporte["cramer_v"].values()), gen.UMBRAL_CRAMER_V)
        self.assertTrue(reporte["checks"]["diseno_colegios_balanceado_por_pares"])
        # Si el estrato dependiera de la naturaleza, la validación debe rechazar el archivo.
        confundido = final.copy()
        confundido.loc[confundido["naturaleza_colegio"] == "Privada", "estrato"] = 6
        self.assertFalse(gen.validar(original, confundido)["aprobado"])

    def test_escalas_de_puntaje(self) -> None:
        self.assertEqual(ejecutar(self.csv).returncode, 0)
        df = pd.read_csv(self.csv, sep=";", encoding="cp1252")
        self.assertTrue(df[list(gen.AREAS)].stack().between(0, 100).all())
        self.assertTrue(df["Global"].between(0, 500).all())

    def test_formato_y_tildes_conservados(self) -> None:
        self.assertEqual(ejecutar(self.csv).returncode, 0)
        cabecera_original = ORIGINAL.read_bytes().splitlines()[0]
        self.assertEqual(self.csv.read_bytes().splitlines()[0], cabecera_original)
        df = pd.read_csv(self.csv, sep=";", encoding="cp1252")
        self.assertIn("Matemáticas", df.columns)
        self.assertEqual(set(df["naturaleza_colegio"]), {"Pública", "Privada"})


if __name__ == "__main__":
    unittest.main()
