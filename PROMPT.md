# PROMPT

## Rol

Actúa como **arquitecto de datos, ingeniero de datos, ingeniero de analítica y director técnico de proyectos de datos**, con experiencia en diseño e implementación de soluciones Data Lakehouse, Business Intelligence, Machine Learning, gobierno de datos, seguridad de la información y proyectos educativos basados en datos.

Tienes experiencia práctica con:

* Python.
* DuckDB.
* Apache Parquet.
* SQL.
* Pandas.
* Scikit-Learn.
* XGBoost.
* SHAP.
* Power BI Desktop.
* DAX.
* Modelos dimensionales y modelo estrella.
* Row-Level Security (RLS).
* Calidad y gobierno de datos.
* Anonimización y seudonimización.
* Validación de modelos de Machine Learning.
* Documentación y reproducibilidad de proyectos.

Tu tarea es transformar los objetivos contenidos en el archivo **`Objetivos.md`** en un **plan de trabajo técnico, detallado, ejecutable y verificable**, que permita construir el proyecto desde cero hasta su validación y entrega final.

---

# 1. FUENTE PRINCIPAL DE INFORMACIÓN

Analiza primero y exhaustivamente el archivo:

**`Objetivos.md`**

El contenido de este archivo constituye la **fuente principal y obligatoria para determinar el alcance funcional del proyecto**.

Debes conservar y desarrollar los objetivos, requerimientos, tecnologías y conceptos planteados allí.

No elimines objetivos ni cambies arbitrariamente su finalidad.

Puedes proponer mejoras técnicas, controles adicionales, reorganización de actividades o medidas de seguridad cuando sean necesarias para que el proyecto sea viable, robusto, reproducible y profesional.

Cuando propongas algo que **no esté explícitamente contemplado en `Objetivos.md`**, identifícalo claramente como:

> **Recomendación técnica adicional**

No presentes recomendaciones adicionales como si fueran requisitos originales del proyecto.

---

# 2. OBJETIVO GENERAL

Diseña un **plan maestro de implementación** para construir una solución de datos y analítica basada en los objetivos del documento, utilizando:

### Data Lakehouse y procesamiento

* Python.
* DuckDB.
* Apache Parquet.
* SQL.
* Arquitectura Medallion: Bronze, Silver y Gold.

### Business Intelligence

* Power BI Desktop.
* DAX.
* Modelo dimensional / modelo estrella.
* Dashboard estratégico.
* Dashboard operativo.
* Row-Level Security (RLS).

### Analítica avanzada

* Scikit-Learn.
* XGBoost.
* SHAP.
* Python.
* Técnicas apropiadas de validación y evaluación de modelos.

El proyecto debe diseñarse buscando **costo cero de licenciamiento**, utilizando componentes open source siempre que sea técnicamente posible.

Sin embargo, debes distinguir expresamente entre:

* **software open source**, y
* **software gratuito pero propietario**.

En particular, **Power BI Desktop no debe ser descrito como software open source**. Debe tratarse como un componente gratuito/propietario del stack.

---

# 3. PRIMERA TAREA: ANALIZAR EL PROYECTO

Antes de elaborar el cronograma, realiza un diagnóstico de `Objetivos.md`.

Identifica:

1. Objetivo general inferido.
2. Objetivos específicos.
3. Productos esperados.
4. Fuentes de datos.
5. Tecnologías.
6. Procesos de transformación.
7. Requerimientos de Business Intelligence.
8. Requerimientos de seguridad.
9. Requerimientos de Machine Learning.
10. Requerimientos de explicabilidad.
11. Dependencias entre objetivos.
12. Riesgos técnicos.
13. Vacíos o aspectos que requieren definición.
14. Supuestos necesarios para ejecutar el proyecto.

No inventes información que no esté disponible.

Cuando un dato no esté definido, escribe:

> **Pendiente de definición**

y explica qué decisión debe tomarse.

---

# 4. ARQUITECTURA OBJETIVO

Diseña la arquitectura lógica y física propuesta.

Debe contemplar, como mínimo:

```text
CSV / fuente de datos
        │
        ▼
     BRONZE
        │
        ▼
      SILVER
        │
        ▼
       GOLD
       /   \
      /     \
     ▼       ▼
Power BI    Machine Learning
   │             │
   ▼             ▼
Dashboards      Modelos
RLS             SHAP
```

Explica detalladamente:

* flujo de datos;
* componentes;
* responsabilidades;
* entradas y salidas;
* formatos;
* ubicación de archivos;
* dependencias;
* controles de calidad;
* seguridad;
* trazabilidad.

Incluye un **diagrama de arquitectura en Mermaid** cuando sea útil.

---

# 5. PLAN DE TRABAJO

Construye el proyecto mediante fases ordenadas lógicamente.

Como mínimo considera:

### Fase 0 — Preparación y gobierno

* estructura del proyecto;
* repositorio;
* entorno Python;
* dependencias;
* convenciones;
* configuración;
* gestión de datos sensibles;
* documentación inicial.

### Fase 1 — Perfilamiento de datos

* exploración del CSV;
* estructura;
* tipos;
* nulos;
* duplicados;
* cardinalidad;
* rangos;
* valores anómalos;
* variables sensibles;
* análisis estadístico inicial.

### Fase 2 — Data Lakehouse Bronze

* ingesta;
* preservación del archivo original;
* trazabilidad;
* metadatos;
* identificación de la fuente.

### Fase 3 — Data Lakehouse Silver

* normalización;
* tipificación;
* limpieza;
* tratamiento de nulos;
* tratamiento de inconsistencias;
* validaciones;
* anonimización/seudonimización;
* estandarización de categorías.

### Fase 4 — Data Lakehouse Gold

* modelo dimensional;
* modelo estrella;
* tabla de hechos;
* dimensiones;
* claves;
* métricas;
* particionamiento;
* optimización de Parquet.

### Fase 5 — Calidad de datos

Diseña un sistema formal de reglas de calidad.

Incluye ejemplos como:

* integridad;
* completitud;
* unicidad;
* validez;
* consistencia;
* exactitud cuando pueda medirse;
* integridad referencial.

Define indicadores de calidad y criterios de aprobación/rechazo.

### Fase 6 — Dashboard estratégico

Diseña:

* páginas;
* KPIs;
* medidas DAX;
* filtros;
* segmentadores;
* comparaciones;
* tendencias;
* benchmarking;
* visualizaciones.

### Fase 7 — Dashboard operativo y RLS

Diseña:

* tabla de seguridad;
* relación con el modelo;
* reglas RLS;
* pruebas;
* casos de acceso;
* comportamiento para usuarios no autorizados.

Explica claramente las limitaciones de RLS cuando se trabaja únicamente con Power BI Desktop frente a escenarios de publicación/distribución.

### Fase 8 — Machine Learning

Implementa progresivamente:

1. baseline.
2. Ridge/Lasso.
3. XGBoost.
4. selección/preparación de variables.
5. entrenamiento.
6. validación.
7. optimización de hiperparámetros.
8. comparación de modelos.
9. selección del modelo final.

### Fase 9 — Explicabilidad con SHAP

Incluye:

* importancia global;
* summary/beeswarm;
* dependencia;
* explicaciones locales cuando sean pertinentes;
* interpretación correcta de los resultados.

Aclara expresamente que:

> SHAP explica el comportamiento del modelo; no demuestra causalidad.

### Fase 10 — Evaluación de sesgos

Considera, cuando sea metodológicamente apropiado:

* sexo;
* estrato;
* zona;
* naturaleza del colegio;
* ubicación;
* otros grupos disponibles.

Evalúa el desempeño del modelo por subgrupos.

### Fase 11 — Automatización

Diseña un pipeline reproducible:

```text
Ingesta
   ↓
Validación
   ↓
Bronze
   ↓
Silver
   ↓
Quality Checks
   ↓
Gold
   ↓
ML
   ↓
SHAP
   ↓
Artefactos
```

### Fase 12 — Pruebas

Incluye:

* pruebas unitarias;
* pruebas de datos;
* pruebas de integración;
* pruebas funcionales;
* pruebas de RLS;
* pruebas de reproducibilidad.

### Fase 13 — Seguridad

Considera:

* datos personales;
* `nroDoc`;
* hashing;
* seudonimización;
* control de acceso;
* archivos temporales;
* logs;
* backups;
* archivos Parquet;
* archivos `.pbix`;
* tabla de seguridad.

### Fase 14 — Documentación y entrega

Define toda la documentación necesaria y los artefactos finales.

---

# 6. PARA CADA FASE

No te limites a indicar actividades generales.

Para **cada fase** debes proporcionar:

| Campo                  | Contenido                      |
| ---------------------- | ------------------------------ |
| ID                     | Identificador único            |
| Fase                   | Nombre                         |
| Objetivo               | Qué se pretende conseguir      |
| Actividades            | Acciones concretas             |
| Subactividades         | Descomposición detallada       |
| Entrada                | Insumos necesarios             |
| Proceso                | Cómo se ejecutará              |
| Herramientas           | Software/librerías             |
| Salida                 | Resultado                      |
| Entregable             | Artefacto concreto             |
| Responsable            | Rol responsable                |
| Dependencias           | Qué debe estar terminado antes |
| Criterio de aceptación | Cómo se valida                 |
| Riesgos                | Riesgos relevantes             |
| Mitigación             | Acción preventiva/correctiva   |

---

# 7. WBS

Construye una **Work Breakdown Structure (WBS)** completa.

Utiliza una estructura similar:

```text
1. Preparación
   1.1 Arquitectura
   1.2 Entorno
   1.3 Repositorio
   1.4 Configuración

2. Datos
   2.1 Perfilamiento
   2.2 Bronze
   2.3 Silver
   2.4 Gold
   2.5 Calidad

3. BI
   3.1 Modelo
   3.2 DAX
   3.3 Dashboard estratégico
   3.4 Dashboard operativo
   3.5 RLS

4. ML
   4.1 Preparación
   4.2 Baseline
   4.3 Ridge/Lasso
   4.4 XGBoost
   4.5 Validación
   4.6 SHAP
   4.7 Sesgos

5. QA
   5.1 Tests
   5.2 Validación
   5.3 Seguridad
   5.4 Reproducibilidad

6. Entrega
   6.1 Documentación
   6.2 Manual técnico
   6.3 Manual usuario
   6.4 Entrega final
```

Descompón cada elemento hasta alcanzar un nivel que permita **asignar, ejecutar y verificar el trabajo**.

---

# 8. CRONOGRAMA

Elabora un cronograma realista.

Si no se conoce el número de personas disponibles, utiliza inicialmente una hipótesis de:

> **Equipo de 1 a 2 personas técnicas.**

Declara este supuesto y permite posteriormente recalcular el cronograma.

Presenta:

| ID | Actividad | Duración estimada | Dependencia | Prioridad | Entregable |
| -- | --------- | ----------------: | ----------- | --------- | ---------- |

También presenta un cronograma tipo **Gantt en Mermaid**.

No inventes fechas calendario si no se proporciona una fecha de inicio.

Utiliza duración estimada en días hábiles y especifica los supuestos.

---

# 9. CAMINO CRÍTICO

Identifica:

* actividades críticas;
* dependencias críticas;
* actividades paralelizables;
* posibles cuellos de botella;
* elementos que pueden retrasar todo el proyecto.

Explica qué actividades pueden ejecutarse simultáneamente.

---

# 10. STACK TECNOLÓGICO

Crea una matriz:

| Componente | Tecnología | Propósito | Licencia/naturaleza | Costo de licencia | Justificación |
| ---------- | ---------- | --------- | ------------------- | ----------------- | ------------- |

Incluye como mínimo:

* Python.
* DuckDB.
* Apache Parquet.
* Pandas.
* Scikit-Learn.
* XGBoost.
* SHAP.
* Power BI Desktop.

**Verifica en fuentes oficiales la licencia actual de los componentes antes de afirmar que son open source o gratuitos.**

---

# 11. ESTRUCTURA DEL CÓDIGO

Propón una estructura profesional del repositorio.

Por ejemplo:

```text
proyecto/
├── data/
├── src/
├── tests/
├── notebooks/
├── sql/
├── models/
├── reports/
├── powerbi/
├── config/
├── docs/
├── requirements.txt
└── README.md
```

Explica qué debe contener cada directorio.

---

# 12. ENTREGABLES

Construye una matriz completa de entregables:

| ID | Entregable | Fase | Formato | Descripción | Criterio de aceptación |
| -- | ---------- | ---- | ------- | ----------- | ---------------------- |

Incluye código, datasets derivados, documentación, dashboards, modelos, gráficos SHAP, informes de calidad y documentación técnica.

---

# 13. CRITERIOS DE ACEPTACIÓN

Define criterios objetivos para declarar cada componente terminado.

Ejemplo:

### Data Lakehouse

* Pipeline reproducible.
* Bronze preserva la fuente.
* Silver cumple reglas de calidad.
* Gold contiene el modelo analítico.
* Parquet correctamente particionado.
* No se exponen identificadores personales innecesariamente.

### Power BI

* Modelo estrella funcional.
* KPIs validados.
* filtros funcionando;
* benchmarking correcto;
* RLS validado mediante casos de prueba.

### Machine Learning

* baseline establecido;
* modelos comparados;
* métricas calculadas;
* validación apropiada;
* ausencia de leakage;
* SHAP generado;
* limitaciones documentadas.

---

# 14. CALIDAD Y VALIDACIÓN DEL MACHINE LEARNING

No aceptes automáticamente el enfoque de `train_test_split()` aleatorio propuesto en el documento.

Analiza primero si existen:

* múltiples registros por estudiante;
* múltiples años;
* múltiples registros por colegio;
* agrupaciones geográficas;
* dependencia temporal.

Determina qué estrategia de validación es apropiada.

Considera, según corresponda:

* `GroupKFold`;
* `StratifiedGroupKFold` cuando sea aplicable;
* validación temporal;
* `KFold`;
* train/test por colegio;
* train/test por periodo.

Explica cuál utilizarías y **por qué**.

---

# 15. PREVENCIÓN DE DATA LEAKAGE

Identifica explícitamente posibles fuentes de leakage.

Analiza:

* variables derivadas del objetivo;
* variables calculadas posteriormente al resultado;
* duplicación de estudiantes;
* información futura;
* transformación antes de separar train/test;
* variables institucionales que puedan incorporar indirectamente el resultado.

Incluye controles preventivos.

---

# 16. GOBIERNO DE DATOS

Propón como mínimo:

* diccionario de datos;
* catálogo de variables;
* linaje;
* reglas de calidad;
* metadatos;
* versiones;
* trazabilidad;
* responsables;
* clasificación de información;
* política de acceso.

No inventes requisitos legales específicos si no se solicitan. Si consideras necesaria una revisión normativa, indícala como actividad pendiente de validación jurídica.

---

# 17. SEGURIDAD Y PRIVACIDAD

Analiza especialmente el campo:

```text
nroDoc
```

Evalúa técnicamente el uso de SHA-256.

Explica la diferencia entre:

* anonimización;
* seudonimización;
* hashing;
* cifrado.

No afirmes que SHA-256 convierte automáticamente un dato personal en un dato anónimo.

Propón medidas de protección adecuadas.

---

# 18. RIESGOS

Construye una matriz:

| ID | Riesgo | Probabilidad | Impacto | Nivel | Mitigación | Contingencia |
| -- | ------ | ------------ | ------- | ----- | ---------- | ------------ |

Considera al menos:

* calidad de datos;
* cambios en el CSV;
* problemas de memoria;
* rendimiento;
* identificación personal;
* leakage;
* sesgo;
* RLS;
* incompatibilidades de Power BI;
* reproducibilidad;
* dependencia de software propietario;
* cambios de versiones.

---

# 19. REPRODUCIBILIDAD

El proyecto debe poder ejecutarse nuevamente.

Diseña mecanismos para:

* fijar versiones;
* registrar dependencias;
* controlar configuración;
* registrar versión de datos;
* registrar fecha de ejecución;
* registrar parámetros;
* registrar métricas;
* conservar artefactos;
* documentar el pipeline.

Define qué debe ocurrir cuando llegue un nuevo CSV.

---

# 20. OPERACIÓN DEL PIPELINE

Diseña el procedimiento operativo para:

### Primera ejecución

```text
Instalar
↓
Configurar
↓
Validar fuente
↓
Ejecutar pipeline
↓
Validar resultados
↓
Construir/actualizar BI
↓
Ejecutar ML
```

### Nueva actualización de datos

```text
Nuevo CSV
↓
Validación
↓
Ingesta
↓
Transformación
↓
Quality checks
↓
Gold
↓
Actualización BI
↓
Reentrenamiento ML
↓
Comparación de modelos
```

---

# 21. DECISIONES TÉCNICAS

Incluye una sección denominada:

## Decisiones arquitectónicas

Para cada decisión importante explica:

* decisión;
* alternativas;
* opción seleccionada;
* justificación;
* ventajas;
* desventajas;
* impacto.

Como mínimo analiza:

* DuckDB vs alternativas;
* Parquet;
* particionamiento;
* modelo estrella;
* estrategia de RLS;
* Ridge vs XGBoost;
* estrategia de validación;
* SHAP;
* almacenamiento local.

---

# 22. INVESTIGACIÓN WEB

Cuando necesites verificar:

* licencias;
* versiones;
* compatibilidad;
* documentación;
* características;
* limitaciones;
* requisitos técnicos;

realiza investigación web.

Prioriza fuentes oficiales:

* documentación oficial;
* repositorios oficiales;
* documentación de Microsoft;
* documentación de DuckDB;
* documentación de Python;
* documentación de Scikit-Learn;
* documentación de XGBoost;
* documentación de SHAP;
* Apache Software Foundation.

No utilices blogs como fuente principal cuando exista documentación oficial.

Cita las fuentes utilizadas.

---

# 23. REGLAS CONTRA ALUCINACIONES

Estas reglas son obligatorias:

1. No inventes características de herramientas.
2. No inventes licencias.
3. No inventes versiones.
4. No inventes requisitos de hardware.
5. No inventes datos del CSV.
6. No inventes resultados de modelos.
7. No inventes métricas.
8. No inventes fechas.
9. No inventes usuarios o roles.
10. No presentes recomendaciones como requisitos originales.

Si no tienes información suficiente:

> **Indica explícitamente que el dato está pendiente de definición.**

---

# 24. FORMATO FINAL DE LA RESPUESTA

Entrega el resultado siguiendo esta estructura:

1. **Resumen ejecutivo**
2. **Análisis de `Objetivos.md`**
3. **Alcance**
4. **Supuestos**
5. **Arquitectura objetivo**
6. **Flujo de datos**
7. **WBS**
8. **Plan de trabajo por fases**
9. **Cronograma**
10. **Camino crítico**
11. **Stack tecnológico y licenciamiento**
12. **Estructura del repositorio**
13. **Data Lakehouse**
14. **Modelo dimensional**
15. **Power BI y RLS**
16. **Machine Learning**
17. **SHAP**
18. **Prevención de leakage**
19. **Evaluación de sesgos**
20. **Calidad de datos**
21. **Seguridad y privacidad**
22. **Pruebas**
23. **Automatización**
24. **Entregables**
25. **Criterios de aceptación**
26. **Matriz de riesgos**
27. **Decisiones arquitectónicas**
28. **Documentación requerida**
29. **Procedimiento operativo**
30. **Checklist final de puesta en producción**
31. **Fuentes consultadas**

---

# 25. NIVEL DE PROFUNDIDAD

El resultado debe ser suficientemente detallado para que un desarrollador pueda utilizarlo como **documento maestro de ejecución del proyecto**.

No quiero únicamente una descripción conceptual.

Quiero saber:

> **qué hacer → en qué orden → con qué herramienta → qué archivo producir → cómo validarlo → qué dependencia tiene → cuándo se considera terminado.**

Cuando sea posible, incluye ejemplos de:

* estructura de carpetas;
* nombres de scripts;
* nombres de tablas;
* nombres de columnas;
* comandos;
* consultas SQL;
* reglas de calidad;
* medidas DAX;
* pruebas;
* artefactos;
* criterios de aceptación.

No escribas todavía todo el código de implementación. El objetivo de esta etapa es construir el **plan maestro de trabajo técnico** que posteriormente servirá como especificación para desarrollar el proyecto.

## Resultado esperado

El resultado final debe funcionar como un **documento técnico de dirección y ejecución**, permitiendo pasar posteriormente del plan a la implementación sin tener que volver a definir la arquitectura, las fases, las dependencias y los criterios de aceptación fundamentales.

Antes de finalizar, realiza una sección:

# Validación del plan

Comprueba que:

* Los cuatro objetivos de `Objetivos.md` están cubiertos.
* Todas las fases tienen entregables.
* Todas las actividades críticas tienen criterios de aceptación.
* Las dependencias son coherentes.
* El cronograma es ejecutable.
* La arquitectura es consistente.
* La estrategia de seguridad es coherente.
* La estrategia de ML evita leakage.
* RLS está contemplado.
* SHAP está correctamente planteado.
* Las afirmaciones sobre licencias y tecnologías fueron verificadas.
* No se han inventado datos que no estén disponibles.

Si encuentras inconsistencias entre `Objetivos.md` y el plan propuesto, **no las ocultes**: crea una sección denominada **“Inconsistencias y decisiones requeridas”** y explica cómo deberían resolverse.
