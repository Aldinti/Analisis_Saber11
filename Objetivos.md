### Objetivo 1: Arquitectura Data Lakehouse con Archivos Parquet

El propósito es tomar el archivo `.csv` de resultados, procesarlo en memoria o disco sin costo de servidores y estructurarlo en capas (*Medallion Architecture*: Bronce, Plata y Oro).

* **Herramienta recomendada:** **DuckDB** integrado en un script de Python. DuckDB es un motor OLAP embebido, gratuito y de alto rendimiento que maneja procesamiento por lotes (*streaming out-of-core*) sin desbordar la memoria RAM.
* **Paso 1: Ingesta y Limpieza (Capa Bronce a Plata):**
* Lectura directa del `.csv` con tipado automático.
* Normalización de nombres de columnas (eliminación de tildes, caracteres especiales y espacios).
* Tratamiento de valores atípicos y nulos (imputación o descarte documentado).
* Anonimización del estudiante mediante hashing criptográfico SHA-256 sobre el campo `nroDoc`.


* **Paso 2: Conversión y Particionamiento (Capa Oro):**
* Se genera el almacenamiento columnar en disco utilizando el formato **Apache Parquet** con compresión *Snappy*.
* Se escribe el dataset particionado físicamente por las carpetas `año` y `jornada` (o `periodo` si actúa como jornada/sesión).



**Script de implementación en Python (`pipeline_lakehouse.py`):**

```python
import duckdb

con = duckdb.connect()

# 1. Ingesta, limpieza y transformación mediante SQL directo
query_transform = """
CREATE OR REPLACE TABLE clean_icfes AS
SELECT 
    año,
    COALESCE(periodo, 'Unica') AS jornada,
    pais,
    departamento,
    municipio,
    zona,
    estrato,
    nombre_colegio,
    naturaleza_colegio,
    modelopedag_colegio,
    sha256(CAST(nroDoc AS VARCHAR)) AS estudiante_id_hash,
    sexo,
    grupo,
    CAST(Global AS FLOAT) AS puntaje_global,
    CAST("Lectura Crítica" AS INTEGER) AS punt_lectura,
    CAST(Matemáticas AS INTEGER) AS punt_matematicas,
    CAST("Sociales y Ciudadana" AS INTEGER) AS punt_sociales,
    CAST("Ciencias Naturales" AS INTEGER) AS punt_ciencias,
    CAST(Inglés AS INTEGER) AS punt_ingles
FROM read_csv_auto('datos_saber11.csv', header=True);
"""
con.execute(query_transform)

# 2. Exportación particionada al Data Lakehouse en formato Parquet
con.execute("""
COPY clean_icfes 
TO 'lakehouse/fact_resultados_saber11' 
(FORMAT PARQUET, PARTITION_BY (año, jornada), COMPRESSION SNAPPY, OVERWRITE_OR_IGNORE 1);
""")
print("Data Lakehouse construido exitosamente en /lakehouse/fact_resultados_saber11")

```

---

### Objetivo 2: Dashboard de Mando Estratégico (Dirección de Calidad)

* **Herramienta recomendada:** **Power BI Desktop** (gratuito para diseño, conexión local y modelado analítico).
* **Paso 1: Conexión al Lakehouse:**
* En Power BI Desktop, seleccionar **Obtener datos** $\rightarrow$ **Carpeta** y apuntar a la ruta `/lakehouse/fact_resultados_saber11`.
* Power BI leerá todos los archivos `.parquet` recursivamente sin descomprimir la información redundante de las particiones.


* **Paso 2: Modelado Dimensional:**
* Crear el modelo estrella vinculando la tabla de hechos con dimensiones creadas mediante DAX o Power Query: `Dim_Colegio`, `Dim_Tiempo`, `Dim_Ubicacion`.


* **Paso 3: Métricas y KPIs en DAX:**
* *Puntaje Promedio Global:*

$$\text{Promedio Global} = \text{AVERAGE}(\text{fact\_resultados\_saber11}[\text{puntaje\_global}])$$


* *Benchmarking Oficial vs. No Oficial:*

$$\text{Diferencial Sector} = \text{CALCULATE}([\text{Promedio Global}], \text{Dim\_Colegio}[\text{naturaleza\_colegio}] = "Pública") - \text{CALCULATE}([\text{Promedio Global}], \text{Dim\_Colegio}[\text{naturaleza\_colegio}] = "Privada")$$


* *Benchmarking Urbano vs. Rural:* Medida similar filtrando por `Dim_Ubicacion[zona]`.


* **Paso 4: Diseño Visual:**
* Tarjetas de KPIs para puntajes distritales consolidados.
* Gráficos de barras agrupadas comparando promedios por componentes (Matemáticas, Lectura, etc.) entre sectores y zonas.
* Líneas de tendencia temporal (2021 a 2024) para identificar evolución del distrito.



---

### Objetivo 3: Dashboard Operativo de Gestión Escolar con RLS

Para evitar crear un informe individual por cada colegio, se parametriza la seguridad dentro del mismo archivo o en un informe dependiente.

* **Paso 1: Tabla de Control de Acceso:**
* Crear una tabla auxiliar `Seguridad_Rectores` en Excel o CSV que mapee el colegio con el identificador del rector:



| nombre_colegio | email_rector |
| --- | --- |
| ABC | rector.abc@sed.gov.co |
| RST | rector.rst@sed.gov.co |
| XYZ | rector.xyz@sed.gov.co |

```
*   Relacionar `Seguridad_Rectores[nombre_colegio]` con `Dim_Colegio[nombre_colegio]` en relación $1:\text{Varios}$ con dirección de filtro cruzado en ambas direcciones.

```

* **Paso 2: Configuración de Reglas RLS en Power BI Desktop:**
* Ir a la pestaña **Modelado** $\rightarrow$ **Administrar roles**.
* Crear un nuevo rol denominado `Rol_Rector`.
* Seleccionar la tabla `Seguridad_Rectores` y agregar la expresión DAX:
```dax
[email_rector] = USERPRINCIPALNAME()

```


* Para pruebas locales sin suscripción corporativa, se puede definir un rol por nombre de colegio o usar la función **Ver como rol** ingresando el correo del directivo para comprobar que la visualización queda restringida exclusivamente a sus datos.


* **Paso 3: Vistas Operativas:**
* Distribución interna de estudiantes por percentiles y niveles de desempeño.
* Comparativo del colegio frente al promedio distrital (usando DAX `ALL()` para mostrar la media del distrito como línea de referencia sin exponer datos de otros colegios).



---

### Objetivo 4: Modelos de Aprendizaje Automático y Análisis SHAP

* **Herramientas recomendadas:** **Python**, **Scikit-Learn**, **XGBoost**, **SHAP** (todos paquetes de código abierto ejecutables en Jupyter Notebook o scripts locales).
* **Paso 1: Preparación del Dataset:**
* Cargar los datos limpios desde el directorio Parquet utilizando DuckDB o Pandas.
* Definir la variable objetivo ($Y = \text{puntaje\_global}$ o puntajes por área) y las variables predictoras ($X$): estrato, zona, naturaleza del colegio, modelo pedagógico, sexo, etc.
* Aplicar codificación One-Hot (*One-Hot Encoding*) a las variables categóricas y escalamiento estándar a las numéricas.


* **Paso 2: Entrenamiento y Evaluación de Modelos:**
* **Regresión Lineal Regularizada (Ridge / Lasso):** Permite cuantificar coeficientes lineales directos penalizando la colinealidad.
* **XGBoost Regressor:** Captura relaciones no lineales e interacciones complejas entre factores demográficos y pedagógicos.
* Métricas de validación: Comparar mediante $R^2$, RMSE y MAE usando validación cruzada ($k$-fold).


* **Paso 3: Explicabilidad e Inferencia con SHAP:**
* Instanciar `shap.TreeExplainer` sobre el modelo XGBoost entrenado.
* Generar el gráfico de resumen (`shap.summary_plot` tipo *beeswarm*), el cual indica la magnitud del impacto (positivo o negativo) de cada categoría (por ejemplo: impacto exacto en puntos del Estrato 1 frente a Estrato 3, o del Modelo Pedagógico ABP).



**Script de implementación analítica (`modelos_ml_shap.py`):**

```python
import duckdb
import pandas as pd
import xgboost as xgb
from sklearn.model_selection import train_test_split
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_squared_error, r2_score
import shap
import matplotlib.pyplot as plt

# 1. Carga directa de la capa analítica desde Parquet
con = duckdb.connect()
df = con.execute("SELECT * FROM 'lakehouse/fact_resultados_saber11/**/*.parquet'").df()

# 2. Selección de variables
features = ['zona', 'estrato', 'naturaleza_colegio', 'modelopedag_colegio', 'sexo']
target = 'puntaje_global'

X = pd.get_dummies(df[features], drop_first=True)
y = df[target]

X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

# 3. Modelo 1: Regresión Regularizada
ridge_model = Ridge(alpha=1.0)
ridge_model.fit(X_train, y_train)
y_pred_ridge = ridge_model.predict(X_test)
print(f"Ridge R2: {r2_score(y_test, y_pred_ridge):.3f} | RMSE: {mean_squared_error(y_test, y_pred_ridge, squared=False):.3f}")

# 4. Modelo 2: XGBoost
xgb_model = xgb.XGBRegressor(n_estimators=100, max_depth=4, learning_rate=0.05, random_state=42)
xgb_model.fit(X_train, y_train)
y_pred_xgb = xgb_model.predict(X_test)
print(f"XGBoost R2: {r2_score(y_test, y_pred_xgb):.3f} | RMSE: {mean_squared_error(y_test, y_pred_xgb, squared=False):.3f}")

# 5. Inferencia Estadística con SHAP
explainer = shap.TreeExplainer(xgb_model)
shap_values = explainer(X_test)

# Generar gráfico de importancia de variables y guardarlo
plt.figure(figsize=(10, 6))
shap.summary_plot(shap_values, X_test, show=False)
plt.title("Impacto de Factores en el Puntaje Global (SHAP Values)")
plt.tight_layout()
plt.savefig("impacto_variables_shap.png")
print("Gráfico SHAP exportado como 'impacto_variables_shap.png'")

```

---

### Resumen del Flujo de Datos

```
[Archivo .csv crudo] 
         │
         ▼  (DuckDB + Python: tipado, limpieza, SHA-256)
[Lakehouse Parquet: partición anio / jornada]
         │
         ├───► [Power BI Desktop] ──► Dashboard Estratégico (Benchmarking KPIs)
         │                         └──► Dashboard Operativo (Filtros RLS Rectores)
         │
         └───► [Scikit-Learn / XGBoost / SHAP] ──► Cuantificación de impacto sociodemográfico

```