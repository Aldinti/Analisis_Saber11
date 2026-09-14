# ADR-0012: Seudonimización con HMAC-SHA-256 en sustitución de SHA-256 simple

## Estado
Aceptado

## Contexto
El requerimiento inicial sugería aplicar un hash SHA-256 sobre el número de documento (`nroDoc`). El análisis de datos reveló que en el CSV original `nroDoc` es una secuencia entera de 1 a 899, y en documentos reales el espacio de búsqueda es menor a 10 dígitos. Un hash SHA-256 sin secreto es trivialmente reversible por fuerza bruta o tablas precomputadas en cuestión de milisegundos.

## Decisión
Implementar seudonimización mediante **HMAC-SHA-256** utilizando una clave criptográfica de al menos 32 bytes (`SABER11_HMAC_KEY`) custodiada en variables de entorno fuera del repositorio git.

## Consecuencias
- **Positivas:**
  - Garantiza determinismo (el mismo estudiante en diferentes cargas obtiene el mismo `estudiante_pid`).
  - Previene la reversibilidad por enumeración sin posesión de la clave secreta.
  - Reconoce técnicamente que el dato es **seudónimo** (no anónimo), manteniendo la debida diligencia en privacidad.
- **Negativas / Mitigaciones:**
  - Requiere gestión segura y respaldo de la clave HMAC para no perder la capacidad de vincular cargas históricas.
