"""Pruebas del catálogo de reglas de calidad (F5a).

Además de la validación estructural, cada regla con SQL se ejecuta en DuckDB contra tablas
de ejemplo con los esquemas del plan (§14, §15.6), una vez con datos correctos (debe pasar)
y, para las reglas nuevas, con un defecto inyectado (debe fallar).
"""
from __future__ import annotations

import re
from datetime import date
from pathlib import Path

import duckdb
import pytest

from saber11.quality.rules import (
    cargar_reglas,
    parametros_desde_settings,
    resolver_sql,
    validar_catalogo,
)

PLAN = Path(__file__).resolve().parents[2] / "docs" / "PLAN_MAESTRO.md"
PID = "a" * 64


def ids_del_plan() -> set[str]:
    texto = PLAN.read_text(encoding="utf-8")
    seccion = texto.split("## 20. Calidad de datos", 1)[1].split("## 21.", 1)[0]
    return set(re.findall(r"^\| (DQ-[A-Z]{3}-\d{3}) \|", seccion, flags=re.M))


@pytest.fixture(scope="module")
def reglas() -> dict[str, dict]:
    return {r["id"]: r for r in cargar_reglas()}


@pytest.fixture()
def con() -> duckdb.DuckDBPyConnection:
    c = duckdb.connect()
    c.execute(f"""
        CREATE TABLE silver_resultados AS SELECT * FROM (VALUES
          (2023, 'II', 'II', 'Colombia', 'Magdalena', 'Santa Marta', 'Urbana', 2, 'ABC', 'Pública',
           'Pedagogía conceptual', '{PID}', 'Femenino', '11-1', 375, 70, 75, 72, 71, 80),
          (2024, 'I', 'I', 'Colombia', 'Magdalena', 'Santa Marta', 'Rural', 5, 'DEF', 'Privada',
           'Tradicional', '{"b" * 64}', 'Masculino', '11-2', 410, 80, 82, 81, 79, 85)
        ) t(anio, periodo, jornada, pais, departamento, municipio, zona, estrato, nombre_colegio, naturaleza_colegio,
            modelo_pedagogico, estudiante_pid, sexo, grupo, puntaje_global, punt_lectura_critica, punt_matematicas,
            punt_sociales, punt_ciencias, punt_ingles);
        UPDATE silver_resultados SET puntaje_global = round(5.0 * (3.0 * (punt_lectura_critica + punt_matematicas
            + punt_sociales + punt_ciencias) + punt_ingles) / 13.0);
        -- Tipos exactos de Silver (TINYINT en áreas): las reglas deben operar sin desbordes.
        ALTER TABLE silver_resultados ALTER anio TYPE SMALLINT;
        ALTER TABLE silver_resultados ALTER estrato TYPE TINYINT;
        ALTER TABLE silver_resultados ALTER puntaje_global TYPE SMALLINT;
        ALTER TABLE silver_resultados ALTER punt_lectura_critica TYPE TINYINT;
        ALTER TABLE silver_resultados ALTER punt_matematicas TYPE TINYINT;
        ALTER TABLE silver_resultados ALTER punt_sociales TYPE TINYINT;
        ALTER TABLE silver_resultados ALTER punt_ciencias TYPE TINYINT;
        ALTER TABLE silver_resultados ALTER punt_ingles TYPE TINYINT;

        CREATE TABLE dim_tiempo AS SELECT 20232 AS tiempo_id;
        CREATE TABLE dim_colegio AS SELECT * FROM (VALUES (1), (2)) t(colegio_id);
        CREATE TABLE dim_ubicacion AS SELECT 1 AS ubicacion_id;
        CREATE TABLE dim_perfil_estudiante AS SELECT 1 AS perfil_id;
        CREATE TABLE dim_area AS SELECT * FROM (VALUES (1), (2)) t(area_id);
        CREATE TABLE fact_resultado AS SELECT * FROM (VALUES (10, 20232, 1, 1, 1), (11, 20232, 2, 1, 1))
            t(resultado_id, tiempo_id, colegio_id, ubicacion_id, perfil_id);
        CREATE TABLE fact_resultado_area AS SELECT * FROM (VALUES (10, 1), (10, 2), (11, 1)) t(resultado_id, area_id);
        CREATE TABLE seguridad_rectores AS SELECT * FROM (VALUES ('rector.abc@example.org', 1)) t(email_rector, colegio_id);

        CREATE TABLE agg_operativo_colegio AS SELECT * FROM (VALUES
          (1, 2023, 'Global', 'Total',   'Total', 40, 380.0, 330.0, 350.0, 380.0, 410.0, 430.0, false),
          (1, 2023, 'Global', 'estrato', '1',     20, 370.0, 320.0, 340.0, 370.0, 400.0, 420.0, false),
          (1, 2023, 'Global', 'estrato', '5',      3, NULL, NULL, NULL, NULL, NULL, NULL, true),
          (1, 2023, 'Global', 'estrato', '6',     17, NULL, NULL, NULL, NULL, NULL, NULL, true)
        ) t(colegio_id, anio, area, dimension, categoria, n, promedio, p10, p25, p50, p75, p90, suprimido);
        CREATE TABLE agg_benchmark_distrito AS SELECT * FROM (VALUES
          (2023, 'Global', 'Total', 'Total', 900, 16, 385.0, 350.0, 385.0, 420.0, false),
          (2023, 'Global', 'naturaleza', 'Privada', 450, 2, NULL, NULL, NULL, NULL, true)
        ) t(anio, area, dimension, categoria, n, n_colegios, promedio, p25, p50, p75, suprimido);

        CREATE TABLE run_log AS SELECT * FROM (VALUES
          ('run-previo', 'silver', 'exitoso', 2, TIMESTAMP '2026-01-01 00:00:00')
        ) t(run_id, etapa, estado, filas, finalizado_utc);
    """)
    yield c
    c.close()


def evaluar(con, regla: dict) -> tuple[float, bool]:
    sql = resolver_sql(regla["sql"], parametros_desde_settings(run_id="run-actual"))
    valor = con.execute(sql).fetchone()[0]
    return float(valor), float(valor) <= regla["umbral_max_fallos"]


# ---------------------------------------------------------------- estructura
def test_catalogo_cubre_todas_las_reglas_del_plan(reglas):
    assert ids_del_plan() == set(reglas)


def test_catalogo_estructuralmente_valido(reglas):
    assert validar_catalogo(list(reglas.values()), set(parametros_desde_settings())) == []


def test_validacion_detecta_errores():
    malas = [
        {"id": "DQ-X-1", "dimension": "otra", "tabla": "t", "descripcion": "d", "severidad": "alta", "umbral_max_fallos": -1},
        {"id": "DQ-VAL-900", "dimension": "validez", "tabla": "t", "descripcion": "d", "severidad": "advertencia",
         "umbral_max_fallos": 2, "metrica": "proporcion", "sql": "SELECT ${desconocido}"},
    ]
    errores = "\n".join(validar_catalogo(malas, {"k_min"}))
    for fragmento in ("formato inválido", "dimensión inválida", "severidad inválida", "umbral inválido", "${desconocido}"):
        assert fragmento in errores


def test_ninguna_regla_tiene_anios_ni_k_min_fijos(reglas):
    for regla in reglas.values():
        sql = regla.get("sql", "")
        assert not re.search(r"\b20[3-9]\d\b|\b202[1-9]\b", sql), f"{regla['id']} tiene un año fijo"
        assert not re.search(r"\bn\s*<\s*\d", sql), f"{regla['id']} tiene k_min fijo; use ${{k_min}}"


def test_resolver_sql_exige_parametros():
    assert resolver_sql("n < ${k_min}", {"k_min": 5}) == "n < 5"
    with pytest.raises(KeyError):
        resolver_sql("n < ${k_min}", {})


# ---------------------------------------------------------------- ejecución con datos correctos
def test_todas_las_reglas_sql_ejecutan_y_pasan_con_datos_correctos(con, reglas):
    for regla in (r for r in reglas.values() if "sql" in r):
        valor, pasa = evaluar(con, regla)
        assert pasa, f"{regla['id']} falla con datos correctos (valor={valor})"


# ---------------------------------------------------------------- defectos inyectados
def test_val_001_usa_el_anio_actual(con, reglas):
    regla = reglas["DQ-VAL-001"]
    con.execute(f"UPDATE silver_resultados SET anio = {date.today().year} WHERE nombre_colegio = 'ABC'")
    assert evaluar(con, regla)[1], "el año actual debe ser válido"
    con.execute(f"UPDATE silver_resultados SET anio = {date.today().year + 1} WHERE nombre_colegio = 'ABC'")
    assert evaluar(con, regla) == (1.0, False), "un año futuro debe fallar"


@pytest.mark.parametrize("regla_id, defecto, esperado", [
    ("DQ-CON-001",
     """INSERT INTO silver_resultados SELECT * REPLACE ('Privada' AS naturaleza_colegio, '{c}' AS estudiante_pid)
        FROM silver_resultados WHERE nombre_colegio = 'ABC'""".format(c="c" * 64), 1),
    ("DQ-CON-002",
     """INSERT INTO silver_resultados SELECT * REPLACE ('publica ' AS naturaleza_colegio, '{c}' AS estudiante_pid)
        FROM silver_resultados WHERE nombre_colegio = 'ABC'""".format(c="c" * 64), 1),
    ("DQ-REF-001", "INSERT INTO fact_resultado VALUES (12, 20232, 99, 1, 1); INSERT INTO fact_resultado_area VALUES (77, 1)", 2),
    ("DQ-REF-002", "INSERT INTO seguridad_rectores VALUES ('rector.x@example.org', 99)", 1),
    ("DQ-PRI-002", "UPDATE agg_benchmark_distrito SET promedio = 400 WHERE categoria = 'Privada'", 1),
    ("DQ-PRI-003", "UPDATE agg_operativo_colegio SET suprimido = false, promedio = 390 WHERE categoria = '6'", 1),
    ("DQ-VOL-001", "INSERT INTO silver_resultados SELECT * REPLACE ('{c}' AS estudiante_pid) FROM silver_resultados LIMIT 1"
                   .format(c="c" * 64), 0.5),
])
def test_reglas_nuevas_detectan_su_defecto(con, reglas, regla_id, defecto, esperado):
    regla = reglas[regla_id]
    con.execute(defecto)
    valor, pasa = evaluar(con, regla)
    assert valor == pytest.approx(esperado)
    assert not pasa, f"{regla_id} no detecta el defecto inyectado"


def test_pri_003_dimension_de_una_sola_categoria_no_requiere_complementaria(con, reglas):
    con.execute("""INSERT INTO agg_operativo_colegio VALUES
        (2, 2023, 'Global', 'Total', 'Total', 3, NULL, NULL, NULL, NULL, NULL, NULL, true),
        (2, 2023, 'Global', 'grupo', '11-1', 3, NULL, NULL, NULL, NULL, NULL, NULL, true)""")
    assert evaluar(con, reglas["DQ-PRI-003"]) == (0.0, True)


def test_pri_002_respeta_k_min_de_settings(con, reglas):
    con.execute("UPDATE agg_operativo_colegio SET promedio = 400 WHERE categoria = '5'")  # n=3 < k_min=5
    assert not evaluar(con, reglas["DQ-PRI-002"])[1]


def test_vol_001_sin_ejecucion_previa_es_cero(con, reglas):
    con.execute("DELETE FROM run_log")
    assert evaluar(con, reglas["DQ-VOL-001"]) == (0.0, True)


def test_com_002_y_exa_001_miden_proporciones(con, reglas):
    con.execute("UPDATE silver_resultados SET sexo = NULL WHERE nombre_colegio = 'ABC'")
    assert evaluar(con, reglas["DQ-COM-002"]) == (0.5, False)
    con.execute("UPDATE silver_resultados SET puntaje_global = puntaje_global + 1 WHERE nombre_colegio = 'DEF'")
    assert evaluar(con, reglas["DQ-EXA-001"]) == (0.5, False)
