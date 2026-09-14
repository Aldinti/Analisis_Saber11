# ADR-0017: Claves sustitutas estables derivadas de MD5 en Gold

## Estado
Aceptado (F4)

## Contexto
El plan (§8 F4) pedía claves sustitutas deterministas "vía `row_number()` ordenado por clave natural, estable entre ejecuciones". `row_number()` es determinista para un mismo conjunto de datos, pero **no** es estable cuando cambia el conjunto: al llegar un colegio cuyo nombre ordena antes (p. ej. `AAA`), todos los `colegio_id` posteriores se desplazan. Eso rompería la tabla de seguridad RLS, las relaciones ya cargadas en Power BI y la comparación entre cargas.

## Decisión
Cada clave es `CAST(md5_number_upper('<prefijo>|<clave natural normalizada>') >> 1 AS BIGINT)`:

| Clave | Clave natural |
|---|---|
| `colegio_id` | nombre del colegio en minúsculas, sin tildes ni espacios extremos |
| `ubicacion_id` | país, departamento, municipio y zona normalizados |
| `perfil_id` | sexo y estrato (`No informado` si faltan) |
| `resultado_id` | `estudiante_pid`, año y periodo |

`tiempo_id` se mantiene legible como `anio*10 + periodo` (I=1, II=2, sin periodo=0) y `area_id` es una constante 1–5. El desplazamiento `>> 1` deja el valor dentro del rango positivo de BIGINT, compatible con el entero de 64 bits de Power BI.

## Consecuencias
- **Positivas:** las claves no cambian al agregar colegios, años o cargas (probado en `tests/integration/test_gold.py`); la tabla de seguridad se enlaza por nombre y obtiene la misma clave en cada ejecución; `resultado_id` no expone el seudónimo del estudiante.
- **Negativas / mitigaciones:** posibilidad teórica de colisión (63 bits); la verificación de F4 compara el número de claves distintas con el de claves naturales distintas y no publica si difieren. Renombrar un colegio genera una clave nueva (es una entidad distinta para el modelo); si ocurre en datos reales, debe gestionarse con una tabla de equivalencias.
