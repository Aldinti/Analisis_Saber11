# Diccionario de datos — Saber 11

> Datos **ficticios** (ver F1b). Clasificación según [data_classification.md](data_classification.md).
> Las secciones Bronze y Gold se completan en sus fases; esta versión documenta **Silver (F3)**.

## Silver — `data/silver/silver_resultados.parquet`

Una fila por evaluación válida (estudiante × año × periodo). Reemplazo completo en cada ejecución
a partir de la partición Bronze vigente. Sin PII directa: `nroDoc`, `nombre1`, `nombre2`,
`apellido1` y `apellido2` no llegan a Silver. Clasificación de la tabla: **Interna**.
Código: `sql/silver/01_texto.sql` … `04_salidas.sql`, orquestado por `src/saber11/transform/silver.py`.

| Columna | Tipo | Descripción | Clasificación | Origen (Bronze) | Transformación | Reglas DQ |
|---|---|---|---|---|---|---|
| `anio` | SMALLINT | Año de presentación del examen | Temporal / cuasi-identificador | `año` | `TRY_CAST`; fuera de 2000..año actual → rechazo | DQ-COM-001, DQ-VAL-001 |
| `periodo` | VARCHAR | Periodo de aplicación (`I`, `II`) | Temporal | `periodo` | `i`/`1` → `I`, `ii`/`2` → `II`; otro valor → rechazo; vacío → NULL | DQ-CON-002 |
| `jornada` | VARCHAR | Alias de periodo exigido por `Objetivos.md` | Temporal | `periodo` | `COALESCE(periodo, 'Unica')` | DQ-CON-002 |
| `pais` | VARCHAR | País | Geográfico | `pais` | Recorte y espacios; escritura canónica más frecuente; vacío → `No informado` | DQ-CON-002 |
| `departamento` | VARCHAR | Departamento | Geográfico | `departamento` | Igual que `pais` | DQ-CON-002 |
| `municipio` | VARCHAR | Municipio (distrito) | Geográfico / cuasi-identificador | `municipio` | Igual que `pais` | DQ-CON-002 |
| `zona` | VARCHAR | `Urbana` o `Rural` | Geográfico / cuasi-identificador | `zona` | Mapa cerrado sin tildes ni mayúsculas; vacío u otro valor → rechazo | DQ-VAL-004, DQ-CON-002 |
| `estrato` | TINYINT | Estrato socioeconómico 1–6 | Cuasi-identificador | `estrato` | `TRY_CAST`; no numérico o fuera de 1..6 → rechazo; vacío → NULL | DQ-COM-002, DQ-VAL-004 |
| `nombre_colegio` | VARCHAR | Nombre del colegio | Institucional / cuasi-identificador | `nombre_colegio` | Escritura canónica más frecuente; vacío → rechazo | DQ-COM-001, DQ-CON-001, DQ-CON-002 |
| `naturaleza_colegio` | VARCHAR | `Pública` o `Privada` | Institucional | `naturaleza_colegio` | `publica`/`oficial` → `Pública`; `privada`/`no oficial` → `Privada`; otro → rechazo; vacío → `No informado` | DQ-CON-001, DQ-CON-002 |
| `modelo_pedagogico` | VARCHAR | Modelo pedagógico del colegio | Institucional | `modelopedag_colegio` | Escritura canónica más frecuente; vacío → `No informado` | DQ-CON-001, DQ-CON-002 |
| `estudiante_pid` | VARCHAR(64) | Seudónimo del estudiante | **Seudónimo (dato personal)** | `nroDoc` | `HMAC-SHA-256(SABER11_HMAC_KEY, CAST(nroDoc AS BIGINT))` en hexadecimal; documento vacío o no numérico → rechazo | DQ-UNI-001, DQ-VAL-005 |
| `sexo` | VARCHAR | `Masculino` o `Femenino` | Cuasi-identificador | `sexo` | `masculino`/`m`, `femenino`/`f`; otro → rechazo; vacío → NULL | DQ-COM-002, DQ-VAL-004, DQ-CON-002 |
| `grupo` | VARCHAR | Grupo escolar (`11-1`) | Cuasi-identificador | `grupo` | Secuencias no alfanuméricas → `-` (`11°1` → `11-1`); vacío → `No informado` | DQ-CON-002 |
| `puntaje_global` | SMALLINT | Puntaje global 0–500 | Resultado | `Global` | `TRY_CAST`; vacío, no numérico o fuera de 0..500 → rechazo | DQ-COM-001, DQ-VAL-003, DQ-EXA-001 |
| `punt_lectura_critica` | TINYINT | Lectura Crítica 0–100 | Resultado | `Lectura Crítica` | `TRY_CAST`; vacío, no numérico o fuera de 0..100 → rechazo | DQ-COM-001, DQ-VAL-002 |
| `punt_matematicas` | TINYINT | Matemáticas 0–100 | Resultado | `Matemáticas` | Igual que `punt_lectura_critica` | DQ-COM-001, DQ-VAL-002 |
| `punt_sociales` | TINYINT | Sociales y Ciudadana 0–100 | Resultado | `Sociales y Ciudadana` | Igual que `punt_lectura_critica` | DQ-COM-001, DQ-VAL-002 |
| `punt_ciencias` | TINYINT | Ciencias Naturales 0–100 | Resultado | `Ciencias Naturales` | Igual que `punt_lectura_critica` | DQ-COM-001, DQ-VAL-002 |
| `punt_ingles` | TINYINT | Inglés 0–100 | Resultado | `Inglés` | Igual que `punt_lectura_critica` | DQ-COM-001, DQ-VAL-002 |
| `flag_atipico` | BOOLEAN | Algún puntaje fuera de Q1 − 1,5·IQR / Q3 + 1,5·IQR de la carga | Calidad | Derivada | IQR sobre filas válidas de la carga; la fila se conserva, no se imputa | — |
| `flag_inconsistencia_global` | BOOLEAN | `puntaje_global` ≠ `round(5·(3·(LC+MAT+SOC+CN)+ING)/13)` | Calidad | Derivada | Se marca, no se rechaza | DQ-EXA-001 |
| `_ingest_id` | VARCHAR | Partición Bronze de origen | Linaje | `_ingest_id` | Copia | — |
| `_source_sha256` | VARCHAR | SHA-256 del CSV de origen | Linaje | `_source_sha256` | Copia | — |

**Duplicados:** si varias filas válidas comparten `estudiante_pid + anio + periodo`, se conserva la primera en
el orden de la fuente y las demás van a cuarentena con `duplicado:estudiante_anio_periodo`.

**Atención para Gold y ML:** los puntajes de área son `TINYINT` (máximo 127). Sumarlos sin convertir
desborda: use `CAST(... AS INTEGER)` antes de operar (así lo hace DQ-EXA-001).

## Silver — `data/silver/silver_rechazos.parquet` (cuarentena)

Filas que no pasan a Silver. Sin PII directa. Los valores se conservan como texto recortado para
diagnóstico; para revisar la fila original se usa `_ingest_id` + `_fila_fuente` en Bronze (zona restringida).

| Columna | Tipo | Descripción |
|---|---|---|
| `_ingest_id` | VARCHAR | Partición Bronze de origen |
| `_source_sha256` | VARCHAR | SHA-256 del CSV de origen |
| `_fila_fuente` | BIGINT | Posición de la fila de datos en la fuente (1 = primera fila después de la cabecera) |
| `motivo_rechazo` | VARCHAR | Motivos separados por `;` con formato `tipo:columna` (`nulo`, `tipo_invalido`, `fuera_de_dominio`, `fuera_de_escala`, `categoria_invalida`, `duplicado`) |
| `estudiante_pid` | VARCHAR | Seudónimo, si el documento era válido |
| `anio` … `punt_ingles` | VARCHAR | Valores de texto recortados de las columnas no personales de la fuente, con nombres Silver |
