# ADR-0001: Adopción de DuckDB como motor de procesamiento OLAP local

## Estado
Aceptado

## Contexto
El proyecto requiere transformar datos desde CSV hacia un Lakehouse Medallion (Bronze/Silver/Gold) en formato columnar Parquet, con costo cero de licenciamiento y sin depender de servicios en la nube ni servidores pesados.

## Decisión
Utilizar **DuckDB** como motor OLAP integrado (*in-process*) mediante su cliente de Python.

## Consecuencias
- **Positivas:**
  - Ejecución analítica vectorial extremadamente rápida y optimizada para memoria.
  - Soporte nativo y directo para lectura y escritura de Apache Parquet con compresión Snappy y particionamiento Hive.
  - Sintaxis SQL estándar que facilita la trazabilidad y separación de capas.
  - Licencia MIT de código abierto sin costos de infraestructura.
- **Negativas / Mitigaciones:**
  - Concurrencia de escritura limitada a un solo proceso; mitigado dado que el pipeline opera por etapas secuenciales/lotes.
