# Informe de perfilamiento v1 — ResultadosICFES.original.csv

> Datos **ficticios**. Las cifras describen el archivo, no la realidad educativa. El informe no contiene valores de columnas con datos personales directos.

## 0. Metadatos

| Campo | Valor |
|---|---|
| version | v1 |
| archivo | ResultadosICFES.original.csv |
| sha256 | d7c84e2133b6ab8e8c1d188c7b7451e5a666768bb9b8d2439be2c7213466c13f |
| generado_utc | 2026-09-14T04:58:49+00:00 |
| filas | 899 |
| columnas | 23 |
| encoding | cp1252 |
| separador | ; |
| fin_de_linea | CRLF |

## 1. Hallazgos

| ID | Tema | Estado | Evidencia |
|---|---|---|---|
| H1 | Formato de la fuente | Conservado (esperado) | encoding=cp1252, separador=';', fin de línea=CRLF, 899 filas × 23 columnas |
| H2 | Variables constantes | Presente | constantes: periodo, pais, departamento, municipio, zona, naturaleza_colegio |
| H3 | Modelo pedagógico ≡ colegio | Presente | Aprendizaje basado en proyectos: 1 colegios, 1 naturalezas; Constructivista: 1 colegios, 1 naturalezas; Pedagogía conceptual: 1 colegios, 1 naturalezas |
| H4 | Global = f(áreas) | Conservado (riesgo de leakage) | fórmula rint(5·(3·(LC+MAT+SOC+CN)+ING)/13) se cumple en 100.00 % de filas |
| H5 | nroDoc enumerable | Presente | secuencial 1..n: sí; 100.0 % de documentos ≤ 1.000.000; único: sí |
| H6 | PII directa en la fuente | Presente (se elimina en Silver) | columnas: nroDoc, nombre1, nombre2, apellido1, apellido2 |
| H7 | Estructura de agrupamiento | Presente | 3 colegios; registros repetidos por estudiante: 0; años: 4 |
| H8 | Balance por sexo | Presente | % Femenino global 22.1; mín. por colegio-año 14.5; máx. 30.8 |
| H9 | Codificación de `grupo` | Conservado | 3 valores; caracteres no ASCII: ['°'] |
| H10 | Rangos de puntajes | Dentro de escala | escala válida: áreas 0–100, Global 0–500; observado: Global 291–477, áreas 45–100 |
| H11 | Confusión entre factores | No evaluable (factores constantes) | Cramér V máx = 0.0591 (estrato~modelopedag_colegio); umbral independencia ≤ 0.05; no evaluables: 15 pares |

## 2. Columnas

| Columna | Tipo | Clasificación | Nulos | Cardinalidad | Constante | Mín | Mediana | Máx | Atípicos IQR | Atípicos |z|>3 |
|---|---|---|---|---|---|---|---|---|---|---|
| año | int64 | Cuasi-identificador | 0 | 4 | no | 2021 | 2022.0 | 2024 | 0 | 0 |
| periodo | str | Analítica | 0 | 1 | sí |  |  |  |  |  |
| pais | str | Analítica | 0 | 1 | sí |  |  |  |  |  |
| departamento | str | Analítica | 0 | 1 | sí |  |  |  |  |  |
| municipio | str | Cuasi-identificador | 0 | 1 | sí |  |  |  |  |  |
| zona | str | Cuasi-identificador | 0 | 1 | sí |  |  |  |  |  |
| estrato | int64 | Cuasi-identificador | 0 | 3 | no | 1 | 2.0 | 3 | 0 | 0 |
| nombre_colegio | str | Cuasi-identificador | 0 | 3 | no |  |  |  |  |  |
| naturaleza_colegio | str | Analítica | 0 | 1 | sí |  |  |  |  |  |
| modelopedag_colegio | str | Analítica | 0 | 3 | no |  |  |  |  |  |
| nroDoc | int64 | PII directa | 0 | 899 | no |  |  |  |  |  |
| nombre1 | str | PII directa | 0 | 899 | no |  |  |  |  |  |
| nombre2 | str | PII directa | 0 | 899 | no |  |  |  |  |  |
| apellido1 | str | PII directa | 0 | 899 | no |  |  |  |  |  |
| apellido2 | str | PII directa | 0 | 899 | no |  |  |  |  |  |
| sexo | str | Cuasi-identificador | 0 | 2 | no |  |  |  |  |  |
| grupo | str | Cuasi-identificador | 0 | 3 | no |  |  |  |  |  |
| Global | int64 | Analítica | 0 | 146 | no | 291 | 388.0 | 477 | 5 | 1 |
| Lectura Crítica | int64 | Analítica | 0 | 56 | no | 45 | 78.0 | 100 | 0 | 0 |
| Matemáticas | int64 | Analítica | 0 | 56 | no | 45 | 77.0 | 100 | 0 | 0 |
| Sociales y Ciudadana | int64 | Analítica | 0 | 56 | no | 45 | 79.0 | 100 | 0 | 0 |
| Ciencias Naturales | int64 | Analítica | 0 | 56 | no | 45 | 79.0 | 100 | 0 | 0 |
| Inglés | int64 | Analítica | 0 | 51 | no | 50 | 80.0 | 100 | 0 | 0 |

### Valores de columnas categóricas (cardinalidad ≤ 30, sin PII)

- **año**: 2021 (258), 2022 (236), 2023 (223), 2024 (182)
- **periodo**: II (899)
- **pais**: Colombia (899)
- **departamento**: Magdalena (899)
- **municipio**: Santa Marta (899)
- **zona**: Urbana (899)
- **estrato**: 1 (317), 2 (291), 3 (291)
- **nombre_colegio**: ABC (295), RST (298), XYZ (306)
- **naturaleza_colegio**: Pública (899)
- **modelopedag_colegio**: Aprendizaje basado en proyectos (306), Constructivista (298), Pedagogía conceptual (295)
- **sexo**: Femenino (199), Masculino (700)
- **grupo**: 11°1 (298), 11°2 (292), 11°3 (309)

## 3. Duplicados

| Criterio | Duplicados |
|---|---|
| Fila completa | 0 |
| nroDoc | 0 |
| nroDoc + año | 0 |

## 4. Distribución de registros

### Colegio × año

| Colegio | 2021 | 2022 | 2023 | 2024 |
|---|---|---|---|---|
| ABC | 83 | 83 | 77 | 52 |
| RST | 84 | 76 | 69 | 69 |
| XYZ | 91 | 77 | 77 | 61 |

### Estrato × naturaleza

| Naturaleza | 1 | 2 | 3 |
|---|---|---|---|
| Pública | 317 | 291 | 291 |

## 5. Puntajes

Consistencia de `Global` con la fórmula de áreas: **100.0 %** de filas.

### Correlaciones (Pearson)

|  | Global | Lectura Crítica | Matemáticas | Sociales y Ciudadana | Ciencias Naturales | Inglés |
|---|---|---|---|---|---|---|
| Global | 1.0 | 0.485 | 0.441 | 0.401 | 0.506 | 0.165 |
| Lectura Crítica | 0.485 | 1.0 | -0.031 | -0.082 | 0.049 | -0.026 |
| Matemáticas | 0.441 | -0.031 | 1.0 | -0.109 | -0.023 | 0.046 |
| Sociales y Ciudadana | 0.401 | -0.082 | -0.109 | 1.0 | -0.075 | -0.039 |
| Ciencias Naturales | 0.506 | 0.049 | -0.023 | -0.075 | 1.0 | 0.018 |
| Inglés | 0.165 | -0.026 | 0.046 | -0.039 | 0.018 | 1.0 |

## 6. Dependencias funcionales

Colegio determina un único valor de: `naturaleza_colegio` (sí), `zona` (sí), `modelopedag_colegio` (sí), `periodo` (sí)

| Modelo pedagógico | Colegios | Naturalezas | Zonas |
|---|---|---|---|
| Aprendizaje basado en proyectos | 1 | 1 | 1 |
| Constructivista | 1 | 1 | 1 |
| Pedagogía conceptual | 1 | 1 | 1 |

### Independencia entre factores (Cramér V)

Máximo evaluable: **0.0591** (umbral de independencia ≤ 0.05).

| Par de factores | Cramér V |
|---|---|
| naturaleza_colegio~zona | no evaluable |
| naturaleza_colegio~periodo | no evaluable |
| naturaleza_colegio~modelopedag_colegio | no evaluable |
| zona~periodo | no evaluable |
| zona~modelopedag_colegio | no evaluable |
| periodo~modelopedag_colegio | no evaluable |
| estrato~naturaleza_colegio | no evaluable |
| estrato~zona | no evaluable |
| estrato~periodo | no evaluable |
| estrato~modelopedag_colegio | 0.0591 |
| sexo~naturaleza_colegio | no evaluable |
| sexo~zona | no evaluable |
| sexo~periodo | no evaluable |
| sexo~modelopedag_colegio | 0.0084 |
| año~naturaleza_colegio | no evaluable |
| año~zona | no evaluable |
| año~periodo | no evaluable |
| año~modelopedag_colegio | 0.0446 |
| estrato~sexo | 0.0487 |

## 7. Privacidad

- Columnas con PII directa presentes: nroDoc, nombre1, nombre2, apellido1, apellido2 → eliminar en Silver.
- Cuasi-identificadores evaluados: nombre_colegio, año, sexo, estrato, grupo.
- k mínimo observado: **1**; grupos con k<5: 102 (256 filas, 28.48 %).
- Implicación (requisito confirmado): el dashboard operativo agrega o suprime grupos con menos de 5 estudiantes (plan §15.6).

## 8. Descriptivos del puntaje Global por grupo

> Descriptivos, no causales. En datos ficticios reflejan los parámetros del generador.

### año

| Grupo | n | Media | Desv. est. |
|---|---|---|---|
| 2021 | 258 | 386.97 | 32.66 |
| 2022 | 236 | 388.47 | 29.95 |
| 2023 | 223 | 387.88 | 29.13 |
| 2024 | 182 | 386.55 | 31.48 |

### periodo

| Grupo | n | Media | Desv. est. |
|---|---|---|---|
| II | 899 | 387.5 | 30.83 |

### zona

| Grupo | n | Media | Desv. est. |
|---|---|---|---|
| Urbana | 899 | 387.5 | 30.83 |

### naturaleza_colegio

| Grupo | n | Media | Desv. est. |
|---|---|---|---|
| Pública | 899 | 387.5 | 30.83 |

### modelopedag_colegio

| Grupo | n | Media | Desv. est. |
|---|---|---|---|
| Aprendizaje basado en proyectos | 306 | 391.21 | 27.89 |
| Constructivista | 298 | 386.6 | 30.99 |
| Pedagogía conceptual | 295 | 384.57 | 33.19 |

### estrato

| Grupo | n | Media | Desv. est. |
|---|---|---|---|
| 1 | 317 | 388.61 | 31.82 |
| 2 | 291 | 387.19 | 29.64 |
| 3 | 291 | 386.61 | 30.96 |

### sexo

| Grupo | n | Media | Desv. est. |
|---|---|---|---|
| Femenino | 199 | 387.52 | 30.88 |
| Masculino | 700 | 387.5 | 30.83 |

### nombre_colegio

| Grupo | n | Media | Desv. est. |
|---|---|---|---|
| ABC | 295 | 384.57 | 33.19 |
| RST | 298 | 386.6 | 30.99 |
| XYZ | 306 | 391.21 | 27.89 |
