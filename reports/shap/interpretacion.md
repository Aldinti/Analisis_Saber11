# Interpretación SHAP — F9

> ⚠️ Los datos son ficticios (plan §4, supuesto S7): estos resultados validan el pipeline, no describen la realidad educativa.
> **SHAP explica el comportamiento del modelo; no demuestra causalidad.**

Ejecución `20260916T052908Z-06492e43` sobre el modelo de F8 `20260916T052758Z-1edef148`.

## 1. Qué se explicó

- **Modelo final:** Lasso, explicado con `shap.LinearExplainer`.
- **Contraste:** XGBoost con `shap.TreeExplainer`, reajustado con los hiperparámetros que registró F8. Sirve para ver si un modelo no lineal lee los datos de otra manera.
- **Conjunto:** las 3509 filas de prueba (2024). El explicador lineal usa como fondo las 11157 filas de entrenamiento; el de árboles usa el recorrido del árbol (`tree_path_dependent`), porque XGBoost 3.4 rechaza el modo *interventional* en este modelo. Cada modelo tiene entonces su propio valor esperado: entre modelos se comparan **rankings**, no valores absolutos.
- **Unidades:** cada valor SHAP está en **puntos del puntaje global**, medido como desvío respecto del valor esperado del modelo.
- **Agregación:** las columnas one-hot se suman por variable original antes de rankear, para que una variable no parezca más importante solo por tener más categorías.

## 2. Verificación de aditividad

Criterio del plan: valor esperado + Σ SHAP ≈ predicción, con tolerancia 0.001.

| Modelo | Valor esperado | Error máximo | Resultado |
|---|--:|--:|---|
| Lasso | 398,08 | 5.68e-14 | ✅ cumple |
| XGBoost | 398,03 | 3.73e-04 | ✅ cumple |

## 3. Importancia global

Media de |SHAP| por variable, en puntos. Figuras: `importancia_global.png`, `beeswarm.png`, `comparacion_modelos.png`.

| Variable | Lasso | XGBoost |
|---|---|---|
| `estrato` | 14,79 | 15,26 |
| `naturaleza_colegio` | 9,95 | 8,70 |
| `zona` | 9,15 | 6,56 |
| `anio` | 4,82 | 2,52 |
| `modelo_pedagogico` | 2,12 | 2,84 |
| `periodo` | 0,00 | 1,47 |
| `sexo` | 0,00 | 0,07 |

El orden que produce el modelo final es: `estrato`, `naturaleza_colegio`, `zona`, `anio`, `modelo_pedagogico`, `periodo`, `sexo`.

## 4. Lectura de los efectos

Diferencia de contribución media entre cada categoría y su referencia, en puntos; para las
numéricas, la pendiente por unidad. Se lee como «cuánto mueve esta característica la
predicción respecto del estudiante promedio», nunca como «cuánto subiría el puntaje si la
característica cambiara».

| Variable | Contraste | Efecto medido (puntos) |
|---|---|--:|
| `naturaleza_colegio` | Privada − Pública | 19,88 |
| `zona` | Rural − Urbana | -18,28 |
| `estrato` | por nivel | 11,49 |
| `modelo_pedagogico` | Aprendizaje basado en proyectos − Tradicional | 8,03 |
| `modelo_pedagogico` | Constructivista − Tradicional | 4,30 |
| `modelo_pedagogico` | Pedagogía conceptual − Tradicional | 4,30 |
| `periodo` | I − II | 0,00 |
| `sexo` | Masculino − Femenino | 0,00 |

El modelo final no usa `periodo`, `sexo`: su contribución es exactamente cero en todas las filas (Lasso anula los coeficientes que no aportan). Es el resultado correcto: son justamente las variables cuyo efecto real sobre el puntaje global es nulo por construcción del generador.

Las figuras de dependencia (`dependencia_estrato.png`, `dependencia_sexo.png`,
`dependencia_modelo_pedagogico.png`) muestran la misma información fila a fila.

## 5. Prueba de recuperación de efectos sintéticos (§17)

Los datos ficticios se generaron con efectos conocidos
(`reports/datos_ficticios/parametros_generacion.json`). Convertidos a puntos del puntaje
global —un efecto común a las cinco áreas se multiplica por 5; uno que solo afecta Inglés,
por 5/13— se comparan con los contrastes que produce el SHAP.

| Variable | Contraste | Esperado | Medido (SHAP) | Diferencia | ¿Recuperado? |
|---|---|--:|--:|--:|---|
| `estrato` | por nivel | 12,50 | 11,49 | -1,01 | ✅ *(exigida §17)* |
| `naturaleza_colegio` | Privada − Pública | 21,92 | 19,88 | -2,04 | ✅ *(exigida §17)* |
| `zona` | Rural − Urbana | -20,00 | -18,28 | 1,72 | ✅ *(exigida §17)* |
| `periodo` | I − II | 0,00 | 0,00 | 0,00 | ✅ |
| `anio` | por año | 4,00 | — | — | no evaluable en el conjunto de prueba (valor único) |
| `modelo_pedagogico` | Aprendizaje basado en proyectos − Tradicional | 7,50 | 8,03 | 0,53 | ✅ |
| `modelo_pedagogico` | Constructivista − Tradicional | 5,00 | 4,30 | -0,70 | ✅ |
| `modelo_pedagogico` | Pedagogía conceptual − Tradicional | 2,50 | 4,30 | 1,80 | ✅ |
| `sexo` | Masculino − Femenino | 0,00 | 0,00 | 0,00 | ✅ |

**Resultado: APROBADA** — el criterio del plan es que coincidan los signos de `estrato`, `naturaleza_colegio`, `zona`.

La magnitud medida es algo menor que la esperada: la regularización encoge los
coeficientes y el efecto propio de cada colegio, que el modelo no observa, se queda en el
residuo. La regularización también puede fundir categorías vecinas —si Lasso anula sus
coeficientes, dos categorías muestran exactamente el mismo contraste frente a la
referencia—. Lo que la prueba verifica es que el pipeline recupera **dirección y orden de
magnitud**, no una estimación insesgada.

## 6. Coeficientes del modelo lineal

Contraste directo con el ranking SHAP: en un modelo lineal ambas lecturas deben coincidir en
signo, y el SHAP añade cuánto pesa cada variable en la práctica según su distribución real.

| Columna | Coeficiente |
|---|--:|
| `naturaleza_colegio=Privada` | 19,88 |
| `zona=Rural` | -18,28 |
| `estrato` | 17,95 |
| `modelo_pedagogico=Tradicional` | -4,30 |
| `modelo_pedagogico=Aprendizaje basado en proyectos` | 3,72 |
| `anio` | 1,96 |
| `zona=Urbana` | 0,00 |
| `naturaleza_colegio=Pública` | 0,00 |
| `periodo=I` | 0,00 |
| `periodo=II` | 0,00 |

## 7. Casos individuales

Tres estudiantes del conjunto de prueba en los percentiles 10, 50 y 90 de la predicción.
No se muestran identificadores: el modelo solo recibe atributos del colegio y del perfil.

- **p10** (percentil 10): valor esperado 398,1 → predicción 373,0 (real 432). Mayores contribuciones: `estrato`=2 (-11,0), `naturaleza_colegio`=Pública (-9,8), `zona`=Rural (-9,3). Figura: `waterfall_p10.png`.
- **p50** (percentil 50): valor esperado 398,1 → predicción 402,8 (real 313). Mayores contribuciones: `naturaleza_colegio`=Pública (-9,8), `zona`=Urbana (9,0), `anio`=2024 (4,8). Figura: `waterfall_p50.png`.
- **p90** (percentil 90): valor esperado 398,1 → predicción 434,2 (real 391). Mayores contribuciones: `estrato`=4 (12,0), `naturaleza_colegio`=Privada (10,1), `zona`=Urbana (9,0). Figura: `waterfall_p90.png`.

## 8. Límites de la interpretación

- **SHAP explica el comportamiento del modelo; no demuestra causalidad.** Un valor alto para `naturaleza_colegio` significa que el modelo usa
  esa variable para predecir, no que cambiarla produzca el efecto.
- **Alias del diseño (`periodo` = f(naturaleza_colegio, zona); `naturaleza_colegio` = f(periodo, zona); `zona` = f(periodo, naturaleza_colegio)):** estas variables son redundantes entre sí, así que el reparto de crédito entre ellas es arbitrario y **no deben interpretarse por separado**.
- **Variables correlacionadas:** con `estrato` y `naturaleza_colegio` asociadas por diseño, el
  crédito se reparte entre ambas y ninguna lleva el efecto completo.
- **El efecto propio del colegio no está en el modelo** (se reserva como grupo de validación):
  lo que se observa es el efecto de los *atributos* del colegio, no el del centro concreto.
- Los efectos recuperados son los que introdujo el generador de F1b; no describen la realidad
  educativa.

## 9. Artefactos

| Archivo | Contenido |
|---|---|
| `importancia_global.png` | Media de \|SHAP\| por variable del modelo final |
| `beeswarm.png` | Distribución de contribuciones por columna transformada |
| `dependencia_*.png` | Contribución frente al valor de `estrato`, `sexo` y `modelo_pedagogico` |
| `waterfall_p10/p50/p90.png` | Explicaciones locales de tres casos |
| `comparacion_modelos.png` | Importancia comparada entre las dos familias de modelo |
| `shap_values.parquet` | Valores SHAP por fila y variable (ambos modelos), con predicción y valor esperado |
| `recuperacion_efectos.csv` | Prueba de recuperación de los efectos sintéticos |
