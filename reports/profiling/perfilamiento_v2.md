# Informe de perfilamiento v2 — ResultadosICFES.csv

> Datos **ficticios**. Las cifras describen el archivo, no la realidad educativa. El informe no contiene valores de columnas con datos personales directos.

## 0. Metadatos

| Campo | Valor |
|---|---|
| version | v2 |
| archivo | ResultadosICFES.csv |
| sha256 | e34ff52d14ad2cd6c3b5b1432b402e7832369d4115e5534af97ee363cef6b00f |
| generado_utc | 2026-09-14T04:58:51+00:00 |
| filas | 14666 |
| columnas | 23 |
| encoding | cp1252 |
| separador | ; |
| fin_de_linea | CRLF |

## 1. Hallazgos

| ID | Tema | Estado | Evidencia |
|---|---|---|---|
| H1 | Formato de la fuente | Conservado (esperado) | encoding=cp1252, separador=';', fin de línea=CRLF, 14666 filas × 23 columnas |
| H2 | Variables constantes | Resuelto | constantes: pais, departamento, municipio |
| H3 | Modelo pedagógico ≡ colegio | Resuelto | Aprendizaje basado en proyectos: 4 colegios, 2 naturalezas; Constructivista: 4 colegios, 2 naturalezas; Pedagogía conceptual: 4 colegios, 2 naturalezas; Tradicional: 4 colegios, 2 naturalezas |
| H4 | Global = f(áreas) | Conservado (riesgo de leakage) | fórmula rint(5·(3·(LC+MAT+SOC+CN)+ING)/13) se cumple en 100.00 % de filas |
| H5 | nroDoc enumerable | Parcial (sigue siendo enumerable) | secuencial 1..n: no; 6.1 % de documentos ≤ 1.000.000; único: sí |
| H6 | PII directa en la fuente | Presente (se elimina en Silver) | columnas: nroDoc, nombre1, nombre2, apellido1, apellido2 |
| H7 | Estructura de agrupamiento | Resuelto | 16 colegios; registros repetidos por estudiante: 0; años: 4 |
| H8 | Balance por sexo | Resuelto | % Femenino global 50.1; mín. por colegio-año 50.0; máx. 50.2 |
| H9 | Codificación de `grupo` | Conservado | 3 valores; caracteres no ASCII: ['°'] |
| H10 | Rangos de puntajes | Dentro de escala | escala válida: áreas 0–100, Global 0–500; observado: Global 206–500, áreas 29–100 |
| H11 | Confusión entre factores | Resuelto | Cramér V máx = 0.0335 (año~naturaleza_colegio); umbral independencia ≤ 0.05; no evaluables: 0 pares |

## 1b. Comparación con v1 (ResultadosICFES.original.csv)

| Métrica | v1 | v2 |
|---|---|---|
| Filas | 899 | 14666 |
| Colegios | 3 | 16 |
| Columnas constantes | 6 | 3 |
| k mínimo (cuasi-identificadores) | 1 | 1 |
| % filas con k<5 | 28.48 | 14.69 |
| SHA-256 | d7c84e2133b6… | e34ff52d14ad… |

| Hallazgo | Estado v1 | Estado v2 |
|---|---|---|
| H1 | Conservado (esperado) | Conservado (esperado) |
| H2 | Presente | Resuelto |
| H3 | Presente | Resuelto |
| H4 | Conservado (riesgo de leakage) | Conservado (riesgo de leakage) |
| H5 | Presente | Parcial (sigue siendo enumerable) |
| H6 | Presente (se elimina en Silver) | Presente (se elimina en Silver) |
| H7 | Presente | Resuelto |
| H8 | Presente | Resuelto |
| H9 | Conservado | Conservado |
| H10 | Dentro de escala | Dentro de escala |
| H11 | No evaluable (factores constantes) | Resuelto |

## 2. Columnas

| Columna | Tipo | Clasificación | Nulos | Cardinalidad | Constante | Mín | Mediana | Máx | Atípicos IQR | Atípicos |z|>3 |
|---|---|---|---|---|---|---|---|---|---|---|
| año | int64 | Cuasi-identificador | 0 | 4 | no | 2021 | 2022.0 | 2024 | 0 | 0 |
| periodo | str | Analítica | 0 | 2 | no |  |  |  |  |  |
| pais | str | Analítica | 0 | 1 | sí |  |  |  |  |  |
| departamento | str | Analítica | 0 | 1 | sí |  |  |  |  |  |
| municipio | str | Cuasi-identificador | 0 | 1 | sí |  |  |  |  |  |
| zona | str | Cuasi-identificador | 0 | 2 | no |  |  |  |  |  |
| estrato | int64 | Cuasi-identificador | 0 | 6 | no | 1 | 3.0 | 6 | 0 | 0 |
| nombre_colegio | str | Cuasi-identificador | 0 | 16 | no |  |  |  |  |  |
| naturaleza_colegio | str | Analítica | 0 | 2 | no |  |  |  |  |  |
| modelopedag_colegio | str | Analítica | 0 | 4 | no |  |  |  |  |  |
| nroDoc | int64 | PII directa | 0 | 14666 | no |  |  |  |  |  |
| nombre1 | str | PII directa | 0 | 14666 | no |  |  |  |  |  |
| nombre2 | str | PII directa | 0 | 14666 | no |  |  |  |  |  |
| apellido1 | str | PII directa | 0 | 14666 | no |  |  |  |  |  |
| apellido2 | str | PII directa | 0 | 14666 | no |  |  |  |  |  |
| sexo | str | Cuasi-identificador | 0 | 2 | no |  |  |  |  |  |
| grupo | str | Cuasi-identificador | 0 | 3 | no |  |  |  |  |  |
| Global | int64 | Analítica | 0 | 262 | no | 206 | 401.0 | 500 | 77 | 30 |
| Lectura Crítica | int64 | Analítica | 0 | 64 | no | 29 | 80.0 | 100 | 58 | 18 |
| Matemáticas | int64 | Analítica | 0 | 61 | no | 39 | 80.0 | 100 | 54 | 18 |
| Sociales y Ciudadana | int64 | Analítica | 0 | 65 | no | 36 | 80.0 | 100 | 58 | 30 |
| Ciencias Naturales | int64 | Analítica | 0 | 63 | no | 35 | 80.0 | 100 | 53 | 19 |
| Inglés | int64 | Analítica | 0 | 63 | no | 35 | 83.0 | 100 | 41 | 27 |

### Valores de columnas categóricas (cardinalidad ≤ 30, sin PII)

- **año**: 2021 (3781), 2022 (3723), 2023 (3653), 2024 (3509)
- **periodo**: I (7350), II (7316)
- **pais**: Colombia (14666)
- **departamento**: Magdalena (14666)
- **municipio**: Santa Marta (14666)
- **zona**: Rural (7331), Urbana (7335)
- **estrato**: 1 (3252), 2 (3228), 3 (3203), 4 (2067), 5 (1744), 6 (1172)
- **nombre_colegio**: ABC (904), BCD (916), DEF (920), EFG (917), GHI (911), HIJ (904), JKL (932), KLM (922), MNO (915), NOP (921), PQR (931), RST (900), STU (908), VWX (905), XYZ (954), YZA (906)
- **naturaleza_colegio**: Privada (7323), Pública (7343)
- **modelopedag_colegio**: Aprendizaje basado en proyectos (3693), Constructivista (3647), Pedagogía conceptual (3666), Tradicional (3660)
- **sexo**: Femenino (7345), Masculino (7321)
- **grupo**: 11°1 (4862), 11°2 (4843), 11°3 (4961)

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
| ABC | 246 | 302 | 228 | 128 |
| BCD | 229 | 228 | 228 | 231 |
| DEF | 223 | 232 | 240 | 225 |
| EFG | 240 | 227 | 222 | 228 |
| GHI | 231 | 226 | 234 | 220 |
| HIJ | 221 | 220 | 228 | 235 |
| JKL | 231 | 235 | 232 | 234 |
| KLM | 237 | 222 | 232 | 231 |
| MNO | 238 | 228 | 225 | 224 |
| NOP | 232 | 226 | 241 | 222 |
| PQR | 228 | 226 | 236 | 241 |
| RST | 272 | 236 | 202 | 190 |
| STU | 219 | 234 | 223 | 232 |
| VWX | 221 | 226 | 221 | 237 |
| XYZ | 290 | 228 | 236 | 200 |
| YZA | 223 | 227 | 225 | 231 |

### Estrato × naturaleza

| Naturaleza | 1 | 2 | 3 | 4 | 5 | 6 |
|---|---|---|---|---|---|---|
| Privada | 1625 | 1610 | 1597 | 1038 | 867 | 586 |
| Pública | 1627 | 1618 | 1606 | 1029 | 877 | 586 |

## 5. Puntajes

Consistencia de `Global` con la fórmula de áreas: **100.0 %** de filas.

### Correlaciones (Pearson)

|  | Global | Lectura Crítica | Matemáticas | Sociales y Ciudadana | Ciencias Naturales | Inglés |
|---|---|---|---|---|---|---|
| Global | 1.0 | 0.822 | 0.821 | 0.82 | 0.83 | 0.756 |
| Lectura Crítica | 0.822 | 1.0 | 0.562 | 0.571 | 0.587 | 0.58 |
| Matemáticas | 0.821 | 0.562 | 1.0 | 0.568 | 0.583 | 0.589 |
| Sociales y Ciudadana | 0.82 | 0.571 | 0.568 | 1.0 | 0.575 | 0.584 |
| Ciencias Naturales | 0.83 | 0.587 | 0.583 | 0.575 | 1.0 | 0.592 |
| Inglés | 0.756 | 0.58 | 0.589 | 0.584 | 0.592 | 1.0 |

## 6. Dependencias funcionales

Colegio determina un único valor de: `naturaleza_colegio` (sí), `zona` (sí), `modelopedag_colegio` (sí), `periodo` (sí)

| Modelo pedagógico | Colegios | Naturalezas | Zonas |
|---|---|---|---|
| Aprendizaje basado en proyectos | 4 | 2 | 2 |
| Constructivista | 4 | 2 | 2 |
| Pedagogía conceptual | 4 | 2 | 2 |
| Tradicional | 4 | 2 | 2 |

### Independencia entre factores (Cramér V)

Máximo evaluable: **0.0335** (umbral de independencia ≤ 0.05).

| Par de factores | Cramér V |
|---|---|
| naturaleza_colegio~zona | 0.0023 |
| naturaleza_colegio~periodo | 0.0003 |
| naturaleza_colegio~modelopedag_colegio | 0.0084 |
| zona~periodo | 0.0014 |
| zona~modelopedag_colegio | 0.0088 |
| periodo~modelopedag_colegio | 0.0059 |
| estrato~naturaleza_colegio | 0.0028 |
| estrato~zona | 0.0024 |
| estrato~periodo | 0.0022 |
| estrato~modelopedag_colegio | 0.0024 |
| sexo~naturaleza_colegio | 0.0001 |
| sexo~zona | 0.0004 |
| sexo~periodo | 0.0 |
| sexo~modelopedag_colegio | 0.0003 |
| año~naturaleza_colegio | 0.0335 |
| año~zona | 0.0322 |
| año~periodo | 0.0274 |
| año~modelopedag_colegio | 0.0166 |
| estrato~sexo | 0.0008 |

## 7. Privacidad

- Columnas con PII directa presentes: nroDoc, nombre1, nombre2, apellido1, apellido2 → eliminar en Silver.
- Cuasi-identificadores evaluados: nombre_colegio, año, sexo, estrato, grupo.
- k mínimo observado: **1**; grupos con k<5: 707 (2155 filas, 14.69 %).
- Implicación (requisito confirmado): el dashboard operativo agrega o suprime grupos con menos de 5 estudiantes (plan §15.6).

## 8. Descriptivos del puntaje Global por grupo

> Descriptivos, no causales. En datos ficticios reflejan los parámetros del generador.

### año

| Grupo | n | Media | Desv. est. |
|---|---|---|---|
| 2021 | 3781 | 395.38 | 47.46 |
| 2022 | 3723 | 398.31 | 47.48 |
| 2023 | 3653 | 400.66 | 47.13 |
| 2024 | 3509 | 405.36 | 47.39 |

### periodo

| Grupo | n | Media | Desv. est. |
|---|---|---|---|
| I | 7350 | 399.92 | 50.09 |
| II | 7316 | 399.73 | 44.75 |

### zona

| Grupo | n | Media | Desv. est. |
|---|---|---|---|
| Rural | 7331 | 390.17 | 48.21 |
| Urbana | 7335 | 409.48 | 44.75 |

### naturaleza_colegio

| Grupo | n | Media | Desv. est. |
|---|---|---|---|
| Privada | 7323 | 410.46 | 46.01 |
| Pública | 7343 | 389.22 | 46.59 |

### modelopedag_colegio

| Grupo | n | Media | Desv. est. |
|---|---|---|---|
| Aprendizaje basado en proyectos | 3693 | 404.31 | 45.3 |
| Constructivista | 3647 | 401.1 | 47.8 |
| Pedagogía conceptual | 3666 | 398.84 | 46.73 |
| Tradicional | 3660 | 395.01 | 49.61 |

### estrato

| Grupo | n | Media | Desv. est. |
|---|---|---|---|
| 1 | 3252 | 377.24 | 45.28 |
| 2 | 3228 | 388.89 | 44.44 |
| 3 | 3203 | 398.32 | 44.04 |
| 4 | 2067 | 414.09 | 43.29 |
| 5 | 1744 | 423.96 | 42.21 |
| 6 | 1172 | 435.67 | 39.91 |

### sexo

| Grupo | n | Media | Desv. est. |
|---|---|---|---|
| Femenino | 7345 | 399.75 | 47.82 |
| Masculino | 7321 | 399.9 | 47.18 |

### nombre_colegio

| Grupo | n | Media | Desv. est. |
|---|---|---|---|
| ABC | 904 | 398.0 | 41.8 |
| BCD | 916 | 372.41 | 48.36 |
| DEF | 920 | 390.21 | 46.18 |
| EFG | 917 | 418.2 | 44.03 |
| GHI | 911 | 375.41 | 47.25 |
| HIJ | 904 | 403.49 | 45.96 |
| JKL | 932 | 380.75 | 47.81 |
| KLM | 922 | 401.06 | 45.56 |
| MNO | 915 | 420.03 | 43.15 |
| NOP | 921 | 396.03 | 47.81 |
| PQR | 931 | 426.31 | 42.25 |
| RST | 900 | 399.83 | 42.09 |
| STU | 908 | 416.0 | 44.67 |
| VWX | 905 | 402.3 | 45.24 |
| XYZ | 954 | 403.6 | 40.96 |
| YZA | 906 | 393.36 | 47.3 |
