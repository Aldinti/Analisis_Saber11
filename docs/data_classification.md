# Clasificación de Datos y Política de Gobierno — Saber 11

## 1. Clasificación de Columnas de Entrada

| Columna Original | Tipo Original | Clasificación de Privacidad | Tratamiento en Lakehouse |
|---|---|---|---|
| `nroDoc` | Entero secuencial | **Identificador Directo (PII)** | Eliminado en Silver. Se deriva `estudiante_pid = HMAC-SHA-256(key, nroDoc)`. |
| `nombre1`, `nombre2` | Texto | **Identificador Directo (PII)** | Eliminados en Silver (Minimización estricta). |
| `apellido1`, `apellido2` | Texto | **Identificador Directo (PII)** | Eliminados en Silver (Minimización estricta). |
| `estrato` | Entero (1–6) | **Cuasi-identificador** | Conservado en Silver/Gold. Sujeto a regla $k_{\min} \ge 5$ en reportes. |
| `sexo` | Texto (F/M) | **Cuasi-identificador** | Conservado en Silver/Gold. Sujeto a regla $k_{\min} \ge 5$ en reportes. |
| `grupo` | Texto ("11°1") | **Cuasi-identificador** | Normalizado a ASCII ("11-1"). Sujeto a regla $k_{\min} \ge 5$. |
| `nombre_colegio` | Texto | Institucional / Atributo Dimensión | Conservado en `dim_colegio`. Base de filtrado RLS. |
| `naturaleza_colegio` | Texto | Institucional / Atributo Dimensión | Conservado en `dim_colegio`. |
| `modelopedag_colegio` | Texto | Institucional / Atributo Dimensión | Conservado en `dim_colegio`. |
| `zona` | Texto (Urbana/Rural) | Geográfico / Atributo Dimensión | Conservado en `dim_ubicacion`. |
| `pais`, `depto`, `mpio` | Texto | Geográfico constante | Conservados en `dim_ubicacion` (excluidos de ML por varianza cero). |
| `año`, `periodo` | Entero / Texto | Temporal | Clave de particionamiento Hive (`anio/periodo`) en `fact_resultado`. |
| `Global`, `punt_*` (5) | Numérico (0–500 / 0–100) | Métricas / Resultados de Examen | Conservados en `fact_resultado` y `fact_resultado_area`. |

---

## 2. Niveles de Clasificación del Repositorio

1. **Zona Restringida (Confidencial / PII):**
   - Carpeta `data/bronze/` y archivos raw.
   - Variable de entorno `SABER11_HMAC_KEY`.
   - Tabla real de asignación de directores `seguridad_rectores.csv`.
   - *Regla:* Excluidos de Git, acceso restringido localmente.

2. **Zona Interna (Gobernada):**
   - Carpeta `data/silver/` y `data/gold/`.
   - Modelos entrenados `.joblib` en `models/`.
   - *Regla:* Sin PII directa, utilizables por analistas y modelos ML.

3. **Zona Pública / Semántica:**
   - Reportes agregados Power BI con supresión de celdas $n < 5$.
   - Informes técnicos y de interpretabilidad SHAP en `reports/`.
