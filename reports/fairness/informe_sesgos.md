# Evaluación de sesgos — F10

> ⚠️ Los datos son ficticios (plan §4, supuesto S7): estos resultados validan el pipeline, no describen la realidad educativa.
> Una brecha de error indica que el modelo **funciona peor** para ese grupo; no que el grupo tenga peores resultados.

Ejecución `20260916T052912Z-d6cc0e24` sobre el modelo de F8 `20260916T052758Z-1edef148` (Lasso).

## 1. Qué se evalúa

- **Conjunto:** las 3509 filas del año de prueba (2024), las mismas con las que se midió el modelo en F8.
- **Desempeño global:** R² 0,250 · RMSE 41,03 · MAE 33,02.
- **Métricas por subgrupo:** n, RMSE, MAE, sesgo medio del residuo (predicción − real), R² y la desviación típica del resultado real, con IC 95 % bootstrap. La desviación típica sirve de referencia: un grupo con resultados más dispersos tiene más error que perder.
- **Grupos pequeños:** con n < 30 el error no distingue señal de ruido; el grupo se reporta con su n, se marca **no concluyente** y queda fuera del cálculo de brechas.
- **Umbral de alerta:** brecha de RMSE mayor que el 10 % del RMSE global, es decir 4,10 puntos.
- **Unidad de remuestreo:** colegios, salvo en la dimensión `nombre_colegio`, donde cada grupo ya es un colegio y se remuestrean filas.

## 2. Resumen de brechas

| Dimensión | Subgrupos (concluyentes) | RMSE mínimo | RMSE máximo | Brecha | IC 95 % brecha | Alerta |
|---|--:|--:|--:|--:|---|:--:|
| `sexo` | 2 (2) | 40,48 (Femenino) | 41,58 (Masculino) | 1,09 | [0,08; 2,78] | ✅ |
| `estrato` | 6 (6) | 36,38 (6) | 42,36 (2) | 5,98 | [3,50; 10,01] | ⚠️ |
| `zona` | 2 (2) | 39,26 (Urbana) | 42,59 (Rural) | 3,33 | [1,54; 5,19] | ✅ |
| `naturaleza_colegio` | 2 (2) | 40,24 (Privada) | 41,89 (Pública) | 1,65 | [0,12; 3,77] | ✅ |
| `modelo_pedagogico` | 4 (4) | 39,64 (Constructivista) | 42,16 (Tradicional) | 2,52 | [1,04; 7,36] | ✅ |
| `nombre_colegio` | 16 (16) | 34,83 (ABC) | 46,12 (DEF) | 11,29 | [8,46; 17,44] | ⚠️ |
| `anio` | 0 | — | — | — | — | no evaluable: un solo valor en el conjunto de prueba (2024) |
| `periodo` | 2 (2) | 39,93 (II) | 42,01 (I) | 2,09 | [0,13; 4,58] | ✅ |
| `naturaleza_colegio · zona` | 4 (4) | 38,77 (Pública · Urbana) | 44,29 (Pública · Rural) | 5,52 | [3,53; 8,73] | ⚠️ |
| `sexo · estrato` | 12 (12) | 35,91 (Femenino · 6) | 43,16 (Masculino · 3) | 7,24 | [5,44; 12,96] | ⚠️ |

**Dimensiones con alerta: `estrato`, `nombre_colegio`, `naturaleza_colegio · zona`, `sexo · estrato`.** La diferencia entre el mejor y el peor subgrupo supera el umbral; revísese el detalle y el intervalo antes de concluir.

Figura: `brechas_rmse.png`. Detalle completo en `desempeno_subgrupos.csv`.

### Qué hay detrás de cada alerta

- **`estrato`** — brecha 5,98 puntos entre 2 (42,36) y 6 (36,38). El RMSE sigue de cerca a la dispersión del resultado real (correlación 0,952): un grupo con resultados más concentrados tiene menos error que perder, así que la brecha mide sobre todo esa diferencia de dispersión y no que el modelo trate peor a un grupo.
- **`nombre_colegio`** — brecha 11,29 puntos entre DEF (46,12) y ABC (34,83). Es la brecha esperada: la identidad del colegio no es una variable del modelo —se reserva como grupo de validación—, así que el efecto propio de cada centro queda entero en el error. Mide cuánto varía ese efecto no observado.
- **`naturaleza_colegio · zona`** — brecha 5,52 puntos entre Pública · Rural (44,29) y Pública · Urbana (38,77). Misma lectura: el RMSE acompaña a la dispersión del resultado (correlación 0,993).
- **`sexo · estrato`** — brecha 7,24 puntos entre Masculino · 3 (43,16) y Femenino · 6 (35,91). Misma lectura: el RMSE acompaña a la dispersión del resultado (correlación 0,903).

## 3. Sesgo sistemático

**Sesgo global del modelo: -2,38 puntos** (IC 95 % [-3,92; -0,91]).

El modelo predice en bloque por debajo del resultado real. Ese desvío **aparece en todos
los subgrupos**, así que un sesgo de grupo solo es propio del grupo si se aparta del
global; esa es la comparación que hace la tabla siguiente.

Subgrupos cuyo sesgo **se aparta del global** (el intervalo de la diferencia no incluye 0).
Un valor negativo significa que el modelo predice por debajo del resultado real del grupo.

| Dimensión | Grupo | n | Sesgo medio | IC 95 % del sesgo | IC 95 % frente al global |
|---|---|--:|--:|---|---|
| `sexo · estrato` | Masculino · 6 | 139 | -10,28 | [-17,21; -3,25] | [-15,56; -0,39] |
| `nombre_colegio` | PQR | 241 | -9,36 | [-13,98; -4,71] | [-11,73; -2,58] |
| `estrato` | 6 | 279 | -7,25 | [-11,60; -3,50] | [-9,26; -0,73] |
| `nombre_colegio` | MNO | 224 | 2,52 | [-2,34; 7,63] | [0,49; 9,62] |

## 4. Detalle por dimensión

### `sexo`

| Grupo | n | RMSE | IC 95 % RMSE | Desv. típica real | MAE | Sesgo medio | R² | |
|---|--:|--:|---|--:|--:|--:|--:|---|
| Masculino | 1751 | 41,58 | [39,76; 43,11] | 48,05 | 33,66 | -2,49 | 0,251 |  |
| Femenino | 1758 | 40,48 | [39,14; 41,74] | 46,74 | 32,37 | -2,27 | 0,249 |  |

### `estrato`

| Grupo | n | RMSE | IC 95 % RMSE | Desv. típica real | MAE | Sesgo medio | R² | |
|---|--:|--:|---|--:|--:|--:|--:|---|
| 2 | 774 | 42,36 | [39,71; 44,46] | 44,73 | 33,89 | -1,50 | 0,102 |  |
| 1 | 780 | 41,77 | [39,87; 43,49] | 44,35 | 33,32 | -1,75 | 0,112 |  |
| 3 | 765 | 41,76 | [39,91; 43,73] | 44,10 | 33,69 | -2,15 | 0,102 |  |
| 4 | 493 | 40,07 | [37,55; 42,58] | 42,05 | 32,40 | -3,44 | 0,090 |  |
| 5 | 418 | 39,82 | [36,90; 42,85] | 43,80 | 32,24 | -1,10 | 0,171 |  |
| 6 | 279 | 36,38 | [32,65; 39,78] | 37,31 | 30,16 | -7,25 | 0,046 | sesgo propio del grupo |

Correlación entre el RMSE de cada grupo y la dispersión de su resultado real: 0,952.

### `zona`

| Grupo | n | RMSE | IC 95 % RMSE | Desv. típica real | MAE | Sesgo medio | R² | |
|---|--:|--:|---|--:|--:|--:|--:|---|
| Rural | 1835 | 42,59 | [41,23; 44,08] | 48,16 | 34,39 | -2,00 | 0,218 |  |
| Urbana | 1674 | 39,26 | [37,88; 40,50] | 44,26 | 31,51 | -2,80 | 0,213 |  |

### `naturaleza_colegio`

| Grupo | n | RMSE | IC 95 % RMSE | Desv. típica real | MAE | Sesgo medio | R² | |
|---|--:|--:|---|--:|--:|--:|--:|---|
| Pública | 1659 | 41,89 | [39,34; 43,85] | 46,98 | 33,68 | -1,91 | 0,204 |  |
| Privada | 1850 | 40,24 | [39,23; 41,16] | 45,36 | 32,42 | -2,80 | 0,213 |  |

### `modelo_pedagogico`

| Grupo | n | RMSE | IC 95 % RMSE | Desv. típica real | MAE | Sesgo medio | R² | |
|---|--:|--:|---|--:|--:|--:|--:|---|
| Tradicional | 912 | 42,16 | [40,98; 44,78] | 48,12 | 34,49 | -3,10 | 0,231 |  |
| Aprendizaje basado en proyectos | 884 | 41,56 | [38,66; 44,71] | 47,33 | 33,03 | -1,19 | 0,228 |  |
| Pedagogía conceptual | 825 | 40,67 | [34,83; 43,04] | 47,02 | 32,48 | -1,50 | 0,251 |  |
| Constructivista | 888 | 39,64 | [37,71; 42,16] | 46,86 | 31,98 | -3,64 | 0,284 |  |

Correlación entre el RMSE de cada grupo y la dispersión de su resultado real: 0,898.

### `nombre_colegio`

| Grupo | n | RMSE | IC 95 % RMSE | Desv. típica real | MAE | Sesgo medio | R² | |
|---|--:|--:|---|--:|--:|--:|--:|---|
| DEF | 225 | 46,12 | [42,14; 49,67] | 50,23 | 37,68 | -4,65 | 0,153 |  |
| BCD | 231 | 44,78 | [41,18; 48,49] | 49,23 | 36,67 | 0,42 | 0,169 |  |
| GHI | 220 | 43,16 | [39,75; 46,18] | 47,65 | 35,26 | 1,25 | 0,176 |  |
| JKL | 234 | 43,04 | [39,37; 46,66] | 45,83 | 34,20 | -1,17 | 0,114 |  |
| HIJ | 235 | 41,88 | [38,11; 45,74] | 46,31 | 33,24 | 0,83 | 0,179 |  |
| YZA | 231 | 41,46 | [38,09; 44,86] | 44,49 | 33,96 | -3,64 | 0,128 |  |
| EFG | 228 | 41,26 | [38,19; 44,38] | 44,13 | 34,31 | -4,02 | 0,122 |  |
| STU | 232 | 41,00 | [37,63; 44,53] | 45,33 | 33,26 | 0,58 | 0,179 |  |
| NOP | 222 | 40,98 | [37,58; 44,29] | 44,68 | 32,97 | -5,27 | 0,155 |  |
| KLM | 231 | 40,85 | [37,42; 43,97] | 46,02 | 33,02 | -2,13 | 0,208 |  |
| VWX | 237 | 39,62 | [36,46; 42,59] | 44,70 | 32,25 | -5,27 | 0,211 |  |
| XYZ | 200 | 38,98 | [35,07; 42,33] | 43,31 | 30,85 | -3,84 | 0,186 |  |
| MNO | 224 | 38,52 | [34,65; 42,13] | 43,85 | 30,10 | 2,52 | 0,225 | sesgo propio del grupo |
| PQR | 241 | 37,75 | [34,75; 40,61] | 40,34 | 30,30 | -9,36 | 0,121 | sesgo propio del grupo |
| RST | 190 | 37,69 | [33,89; 41,46] | 40,60 | 29,99 | 0,00 | 0,134 |  |
| ABC | 128 | 34,83 | [30,35; 38,99] | 41,07 | 26,97 | -4,75 | 0,275 |  |

Correlación entre el RMSE de cada grupo y la dispersión de su resultado real: 0,929.

### `anio`

| Grupo | n | RMSE | IC 95 % RMSE | Desv. típica real | MAE | Sesgo medio | R² | |
|---|--:|--:|---|--:|--:|--:|--:|---|

No se calcula brecha: un solo valor en el conjunto de prueba (2024).

### `periodo`

| Grupo | n | RMSE | IC 95 % RMSE | Desv. típica real | MAE | Sesgo medio | R² | |
|---|--:|--:|---|--:|--:|--:|--:|---|
| I | 1835 | 42,01 | [39,95; 43,98] | 50,13 | 33,95 | -1,86 | 0,297 |  |
| II | 1674 | 39,93 | [38,61; 41,03] | 44,20 | 32,00 | -2,95 | 0,184 |  |

### `naturaleza_colegio · zona`

| Grupo | n | RMSE | IC 95 % RMSE | Desv. típica real | MAE | Sesgo medio | R² | |
|---|--:|--:|---|--:|--:|--:|--:|---|
| Pública · Rural | 910 | 44,29 | [43,07; 45,67] | 48,40 | 35,94 | -1,04 | 0,162 |  |
| Privada · Rural | 925 | 40,84 | [39,91; 41,88] | 45,39 | 32,86 | -2,93 | 0,190 |  |
| Privada · Urbana | 925 | 39,64 | [37,75; 41,26] | 43,54 | 31,98 | -2,67 | 0,170 |  |
| Pública · Urbana | 749 | 38,77 | [35,80; 41,46] | 42,70 | 30,93 | -2,96 | 0,174 |  |

Correlación entre el RMSE de cada grupo y la dispersión de su resultado real: 0,993.

### `sexo · estrato`

| Grupo | n | RMSE | IC 95 % RMSE | Desv. típica real | MAE | Sesgo medio | R² | |
|---|--:|--:|---|--:|--:|--:|--:|---|
| Masculino · 3 | 382 | 43,16 | [40,48; 45,87] | 45,24 | 35,34 | 0,17 | 0,088 |  |
| Masculino · 1 | 390 | 42,70 | [40,43; 45,06] | 44,62 | 34,38 | -1,41 | 0,082 |  |
| Masculino · 2 | 385 | 42,45 | [38,52; 45,39] | 44,58 | 33,85 | -1,11 | 0,091 |  |
| Femenino · 2 | 389 | 42,28 | [39,21; 45,48] | 44,94 | 33,93 | -1,88 | 0,113 |  |
| Femenino · 5 | 209 | 41,27 | [36,70; 46,31] | 44,69 | 33,71 | 0,77 | 0,143 |  |
| Masculino · 4 | 246 | 41,05 | [37,85; 44,20] | 42,92 | 33,97 | -5,71 | 0,082 |  |
| Femenino · 1 | 390 | 40,81 | [38,90; 42,49] | 44,13 | 32,26 | -2,10 | 0,143 |  |
| Femenino · 3 | 383 | 40,31 | [37,57; 43,07] | 42,86 | 32,04 | -4,46 | 0,113 |  |
| Femenino · 4 | 247 | 39,08 | [35,25; 42,29] | 41,12 | 30,84 | -1,18 | 0,093 |  |
| Masculino · 5 | 209 | 38,32 | [34,24; 41,74] | 42,91 | 30,78 | -2,97 | 0,199 |  |
| Masculino · 6 | 139 | 36,85 | [32,57; 40,62] | 36,19 | 30,32 | -10,28 | -0,044 | sesgo propio del grupo |
| Femenino · 6 | 140 | 35,91 | [31,95; 39,87] | 38,29 | 30,00 | -4,23 | 0,114 |  |

Correlación entre el RMSE de cada grupo y la dispersión de su resultado real: 0,903.

## 5. Factores asociados entre sí

Al leer las brechas conviene saber qué factores van juntos: si dos están asociados, la
brecha de uno arrastra la del otro. Asociación medida con la V de Cramér sobre el conjunto
de prueba.

| Par de factores | V de Cramér |
|---|--:|
| `naturaleza_colegio` ~ `modelo_pedagogico` | 0,050 |
| `zona` ~ `modelo_pedagogico` | 0,049 |
| `naturaleza_colegio` ~ `zona` | 0,049 |
| `estrato` ~ `modelo_pedagogico` | 0,005 |
| `estrato` ~ `zona` | 0,003 |

Ningún par supera V = 0,20: los factores son prácticamente independientes entre sí, así que cada brecha puede leerse por su cuenta. Es lo que buscaba el diseño ortogonal de colegios de F1b, comprobado aquí sobre el conjunto de prueba.

## 6. Lectura y límites

- Una brecha de error indica que el modelo **funciona peor** para ese grupo; no que el grupo tenga peores resultados.
- El modelo solo recibe atributos del colegio y del perfil del estudiante: no puede
  distinguir a dos estudiantes con los mismos atributos, así que el error dentro de cada
  subgrupo está dominado por la variabilidad individual.
- Las diferencias de **nivel** entre grupos (que un grupo puntúe más que otro) son parte de
  lo que el modelo predice; lo que aquí se mide es si **acierta** por igual en todos.
- Los datos son ficticios: estas brechas describen el comportamiento del pipeline sobre los
  efectos que introdujo el generador de F1b, no desigualdades educativas reales.

## 7. Artefactos

| Archivo | Contenido |
|---|---|
| `desempeno_subgrupos.csv` | Una fila por subgrupo con n, métricas, intervalos y marcas |
| `brechas_rmse.png` | Brecha de RMSE por dimensión |
| `informe_sesgos.md` | Este informe |
