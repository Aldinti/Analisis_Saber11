"""Pruebas del perfilador (fases F1 / F1c).
    python -m unittest discover -s tests/unit -v
"""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src"))

from saber11.profiling.profile import PII_DIRECTA, informe_markdown, perfilar  # noqa: E402

ORIGINAL = RAIZ / "ResultadosICFES.original.csv"
AMPLIADO = RAIZ / "ResultadosICFES.csv"


def estados(perfil: dict) -> dict[str, str]:
    return {h["id"]: h["estado"] for h in perfil["hallazgos"]}


@unittest.skipUnless(ORIGINAL.exists() and AMPLIADO.exists(), "requiere CSV original y ampliado (F1b)")
class TestPerfilador(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.v1 = perfilar(ORIGINAL, "v1")
        cls.v2 = perfilar(AMPLIADO, "v2")

    def test_formato_detectado(self) -> None:
        m = self.v1["metadatos"]
        self.assertEqual((m["encoding"], m["separador"], m["filas"], m["columnas"]), ("cp1252", ";", 899, 23))

    def test_hallazgos_original_presentes(self) -> None:
        e = estados(self.v1)
        for h in ("H2", "H3", "H5", "H7", "H8"):
            self.assertEqual(e[h], "Presente", h)

    def test_hallazgos_resueltos_tras_ampliacion(self) -> None:
        e = estados(self.v2)
        for h in ("H2", "H3", "H7", "H8", "H11"):
            self.assertEqual(e[h], "Resuelto", h)
        self.assertEqual(e["H10"], "Dentro de escala")
        self.assertEqual(self.v2["consistencia_global_pct"], 100.0)
        self.assertLessEqual(self.v2["independencia"]["max_cramer_v"], 0.05)

    def test_original_con_factores_no_evaluables(self) -> None:
        self.assertEqual(estados(self.v1)["H11"], "No evaluable (factores constantes)")

    def test_informe_sin_valores_pii(self) -> None:
        texto = informe_markdown(self.v2, self.v1) + json.dumps(self.v2, ensure_ascii=False, default=str)
        for marcador in ("NombreL", "NombreM", "ApellidoN", "ApellidoO"):
            self.assertNotIn(marcador, texto)
        for col in (c for c in self.v2["columnas"] if c["columna"] in PII_DIRECTA):
            self.assertNotIn("valores", col)
            self.assertNotIn("min", col)


if __name__ == "__main__":
    unittest.main()
