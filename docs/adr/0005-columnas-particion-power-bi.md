# ADR-0005: Columnas de partición dentro de los archivos Parquet de `fact_resultado`

## Estado
Aceptado (F4, tras el spike técnico previsto en el plan)

## Contexto
`Objetivos.md` exige particionar la tabla de hechos por año y jornada/periodo. El plan (§8 F4, riesgo b) advertía que las columnas de partición podrían no quedar dentro de los archivos y que el conector **Carpeta** de Power BI no las deriva de la ruta, lo que obligaría a extraerlas de `Folder Path` en Power Query. También se aceptó (riesgo a) que el particionado produce archivos pequeños.

## Spike (DuckDB 1.5.5)
- `COPY ... (PARTITION_BY (anio, periodo))` **no** escribe `anio` ni `periodo` dentro de los archivos: solo existen en la ruta `anio=2024/periodo=I/`.
- Con `WRITE_PARTITION_COLUMNS true` las columnas quedan en el archivo **y** la lectura `read_parquet(..., hive_partitioning = true)` sigue devolviendo `anio` y `periodo` con los mismos valores.
- Un periodo nulo se escribe en `periodo=__HIVE_DEFAULT_PARTITION__` y se lee de vuelta como NULL.
- Con hive, DuckDB infiere `anio` como BIGINT (en el archivo es SMALLINT); no afecta a valores ni uniones.

## Decisión
Escribir `fact_resultado` con `PARTITION_BY (anio, periodo), WRITE_PARTITION_COLUMNS true, COMPRESSION snappy`. Power BI puede leer los archivos de la carpeta y obtener `anio` y `periodo` sin transformar la ruta; DuckDB y ML leen con `hive_partitioning = true`. Las demás tablas Gold se escriben sin partición (un archivo cada una).

## Consecuencias
- **Positivas:** se cumple el requisito de partición; Power BI no depende de parsear rutas; la verificación de F4 comprueba ambas lecturas (hive y dentro del archivo).
- **Negativas / mitigaciones:** redundancia mínima de dos columnas por fila. Archivos pequeños (8 particiones con los datos actuales): aceptado por requisito; si crecieran los datos se ajusta `ROW_GROUP_SIZE` o el particionado sin cambiar el esquema.
