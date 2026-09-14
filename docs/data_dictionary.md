# Diccionario de datos — Saber 11

> Datos **ficticios** (ver F1b). Clasificación según [data_classification.md](data_classification.md).
> Esta versión documenta **Silver (F3)** y **Gold (F4)**.

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

## Gold — `data/gold/` (F4)

Modelo estrella + agregados. Reemplazo completo por intercambio de carpeta, solo si el Silver consumido tiene el
quality gate aprobado. Sin PII directa ni `estudiante_pid`. Clasificación: **Interna** (dimensiones, hechos,
`ml_dataset`), **Restringida** (`seguridad_rectores` con correos reales). Código: `sql/gold/01_dimensiones.sql` …
`04_ml_y_seguridad.sql`, orquestado por `src/saber11/transform/gold.py`.

**Claves sustitutas (ADR-0017):** cada `*_id` es `CAST(md5_number_upper(prefijo + clave natural normalizada) >> 1 AS BIGINT)`.
Son estables entre ejecuciones y no cambian al agregar colegios o cargas. `tiempo_id = anio*10 + periodo` (I=1, II=2, sin periodo=0).

### `dim_tiempo`

| Columna | Tipo | Descripción | Origen / regla |
|---|---|---|---|
| `tiempo_id` | INTEGER | Clave del periodo de aplicación | anio*10 + (I→1, II→2, NULL→0) |
| `anio` | SMALLINT | Año | Silver `anio` |
| `periodo` | VARCHAR | Periodo (`I`, `II`) | Silver `periodo` |
| `jornada` | VARCHAR | Alias exigido por `Objetivos.md` | Silver `jornada` |

### `dim_colegio`

| Columna | Tipo | Descripción | Origen / regla |
|---|---|---|---|
| `colegio_id` | BIGINT | Clave estable del colegio; base del filtro RLS | MD5 del nombre normalizado |
| `nombre_colegio` | VARCHAR | Nombre del colegio | Silver |
| `naturaleza_colegio` | VARCHAR | `Pública` / `Privada` | Valor del año más reciente si cambió (DQ-CON-001) |
| `modelo_pedagogico` | VARCHAR | Modelo pedagógico | Valor del año más reciente si cambió |

### `dim_ubicacion`

| Columna | Tipo | Descripción | Origen / regla |
|---|---|---|---|
| `ubicacion_id` | BIGINT | Clave estable de la ubicación | MD5 de país, departamento, municipio y zona |
| `pais` | VARCHAR | País | Silver |
| `departamento` | VARCHAR | Departamento | Silver |
| `municipio` | VARCHAR | Municipio (distrito) | Silver |
| `zona` | VARCHAR | `Urbana` / `Rural` | Silver |

### `dim_perfil_estudiante`

| Columna | Tipo | Descripción | Origen / regla |
|---|---|---|---|
| `perfil_id` | BIGINT | Clave de la combinación sexo × estrato (dimensión *junk*) | MD5 de sexo y estrato |
| `sexo` | VARCHAR | `Masculino` / `Femenino` / `No informado` | Silver; NULL → `No informado` |
| `estrato` | TINYINT | Estrato 1–6 (NULL si no informado) | Silver |

### `dim_area`

| Columna | Tipo | Descripción | Origen / regla |
|---|---|---|---|
| `area_id` | TINYINT | 1 Lectura Crítica, 2 Matemáticas, 3 Sociales y Ciudadana, 4 Ciencias Naturales, 5 Inglés | Constante |
| `area` | VARCHAR | Nombre del área | Constante |
| `peso_global` | TINYINT | Peso en el puntaje global (3, 3, 3, 3, 1) | Fórmula verificada H4 |

### `fact_resultado`

Grano: una evaluación. Particionada en `fact_resultado/anio=*/periodo=*/`; por ADR-0005, `anio` y `periodo`
también se guardan **dentro** de cada archivo (Power BI las lee sin derivarlas de la ruta).

| Columna | Tipo | Descripción | Origen / regla |
|---|---|---|---|
| `resultado_id` | BIGINT | Clave estable de la evaluación (no publica el seudónimo) | MD5 de seudónimo, año y periodo |
| `tiempo_id` | INTEGER | FK `dim_tiempo` | |
| `colegio_id` | BIGINT | FK `dim_colegio` | |
| `ubicacion_id` | BIGINT | FK `dim_ubicacion` | |
| `perfil_id` | BIGINT | FK `dim_perfil_estudiante` | |
| `grupo` | VARCHAR | Grupo escolar | Silver |
| `puntaje_global` | SMALLINT | Puntaje global 0–500 | Silver |
| `punt_lectura_critica` | TINYINT | 0–100 (convertir a INTEGER antes de sumar) | Silver |
| `punt_matematicas` | TINYINT | 0–100 | Silver |
| `punt_sociales` | TINYINT | 0–100 | Silver |
| `punt_ciencias` | TINYINT | 0–100 | Silver |
| `punt_ingles` | TINYINT | 0–100 | Silver |
| `anio` | SMALLINT | Año (columna de partición, también en el archivo) | Silver |
| `periodo` | VARCHAR | Periodo (columna de partición, también en el archivo) | Silver |

### `fact_resultado_area`

| Columna | Tipo | Descripción | Origen / regla |
|---|---|---|---|
| `resultado_id` | BIGINT | FK `fact_resultado` | |
| `area_id` | TINYINT | FK `dim_area` | |
| `puntaje` | SMALLINT | Puntaje del área 0–100 (SMALLINT: sumas seguras) | `punt_*` de `fact_resultado` |
| `tiempo_id` | INTEGER | FK `dim_tiempo` | |
| `colegio_id` | BIGINT | FK `dim_colegio` (filtro RLS) | |
| `perfil_id` | BIGINT | FK `dim_perfil_estudiante` | |

### `agg_operativo_colegio`

Base del dashboard operativo (plan §15.6). Una fila por colegio × año × área (`Global` y las 5 áreas) ×
dimensión (`Total`, `sexo`, `estrato`, `grupo`) × categoría. Supresión con `k_min` de `settings.yaml`.

| Columna | Tipo | Descripción | Origen / regla |
|---|---|---|---|
| `colegio_id` | BIGINT | FK `dim_colegio` (filtro RLS) | |
| `anio` | SMALLINT | Año | |
| `area` | VARCHAR | `Global` o nombre del área | |
| `dimension` | VARCHAR | `Total`, `sexo`, `estrato`, `grupo` | |
| `categoria` | VARCHAR | Valor de la dimensión (`Total` en la fila total) | |
| `n` | INTEGER | Estudiantes en la celda | |
| `promedio` | DOUBLE | Promedio; NULL si `suprimido` | DQ-PRI-002 |
| `p10` | DOUBLE | Percentil 10; NULL si `suprimido` | |
| `p25` | DOUBLE | Percentil 25; NULL si `suprimido` | |
| `p50` | DOUBLE | Mediana; NULL si `suprimido` | |
| `p75` | DOUBLE | Percentil 75; NULL si `suprimido` | |
| `p90` | DOUBLE | Percentil 90; NULL si `suprimido` | |
| `suprimido` | BOOLEAN | `n < k_min` (primaria) o la siguiente celda más pequeña si en la dimensión quedó una sola suprimida (complementaria) | DQ-PRI-002, DQ-PRI-003 |

### `agg_benchmark_distrito`

Comparativo distrital sin relación con `dim_colegio` (RLS no lo filtra). Dimensiones: `Total`, `naturaleza_colegio`,
`zona`, `modelo_pedagogico`, `sexo`, `estrato`.

| Columna | Tipo | Descripción | Origen / regla |
|---|---|---|---|
| `anio` | SMALLINT | Año | |
| `area` | VARCHAR | `Global` o nombre del área | |
| `dimension` | VARCHAR | Dimensión comparada | |
| `categoria` | VARCHAR | Valor de la dimensión | |
| `n` | INTEGER | Estudiantes | |
| `n_colegios` | INTEGER | Colegios que aportan a la celda | |
| `promedio` | DOUBLE | Promedio; NULL si `suprimido` | DQ-PRI-002 |
| `p25` | DOUBLE | Percentil 25; NULL si `suprimido` | |
| `p50` | DOUBLE | Mediana; NULL si `suprimido` | |
| `p75` | DOUBLE | Percentil 75; NULL si `suprimido` | |
| `suprimido` | BOOLEAN | `n < k_min` o `n_colegios < min_schools_comparative`, más supresión complementaria | |

### `seguridad_rectores`

Fuente: `config/seguridad_rectores.csv` (real, **no versionado**) o, si no existe, `config/seguridad_rectores.example.csv`
(cuentas ficticias `example.org`). Columnas de la fuente: `email_rector`, `nombre_colegio`. `run_log` registra cuál se usó.

| Columna | Tipo | Descripción | Origen / regla |
|---|---|---|---|
| `email_rector` | VARCHAR | UPN del rector en minúsculas (dato personal) | Fuente de seguridad |
| `colegio_id` | BIGINT | Colegio autorizado | Enlace por nombre normalizado; colegio inexistente → rechazo (DQ-REF-002) |

### `ml_dataset`

Entrada de F8 (plan §16.2). Solo variables admitidas; sin `punt_*`, `grupo`, flags ni seudónimo (prevención de leakage).

| Columna | Tipo | Descripción | Uso en ML |
|---|---|---|---|
| `resultado_id` | BIGINT | Clave de la evaluación | Identificador (no predictor) |
| `anio` | SMALLINT | Año | Predictor y corte temporal (test 2024) |
| `periodo` | VARCHAR | Periodo | Predictor (control negativo en datos ficticios) |
| `nombre_colegio` | VARCHAR | Colegio | **Solo** grupo de validación (`GroupKFold`) |
| `naturaleza_colegio` | VARCHAR | Pública / Privada | Predictor |
| `modelo_pedagogico` | VARCHAR | Modelo pedagógico | Predictor |
| `zona` | VARCHAR | Urbana / Rural | Predictor |
| `sexo` | VARCHAR | Sexo | Predictor y subgrupo de sesgos |
| `estrato` | TINYINT | Estrato | Predictor y subgrupo de sesgos |
| `puntaje_global` | SMALLINT | Puntaje global | Objetivo |
