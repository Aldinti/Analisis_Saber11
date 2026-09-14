# ADR-0002: Formato de almacenamiento columnar Parquet con compresión Snappy

## Estado
Aceptado

## Contexto
Se requiere almacenar las capas Bronze, Silver y Gold asegurando tipos estrictos, alta compresión y compatibilidad directa tanto con Python (DuckDB/Pandas/PyArrow) como con Power BI Desktop.

## Decisión
Adoptar **Apache Parquet** comprimido con **Snappy** como formato único para los datos persistidos en el Lakehouse.

## Consecuencias
- **Positivas:**
  - Formato abierto (Apache 2.0) e interoperable.
  - Almacenamiento por columnas que acelera consultas analíticas agregadas y minimiza I/O en disco.
  - Esquema y tipos embebidos en los metadatos de los archivos.
  - Compatibilidad out-of-the-box con Power BI Desktop.
- **Negativas / Mitigaciones:**
  - No admite actualizaciones *in-place*; mitigado aplicando escrituras particionadas inmutables y recreación atómica por lotes.
