# Comparación de modelos — F8

> ⚠️ Los datos son ficticios (plan §4, supuesto S7): estos resultados validan el pipeline, no describen la realidad educativa.

Ejecución `20260916T052758Z-1edef148` · semilla `20260913` · objetivo `puntaje_global`.

## 1. Conjunto y esquema de validación

- **Origen:** `data/gold/ml_dataset.parquet` — 14666 filas, 16 colegios.
- **Entrenamiento:** años anteriores a 2024 (11157 filas). **Prueba:** 2024 (3509 filas), usada una sola vez.
- **Comparación y ajuste:** CV anidada con `GroupKFold` por `nombre_colegio` (5 pliegues fuera, 3 dentro con `RandomizedSearchCV`).
- **Por qué no un `train_test_split` aleatorio:** mezclaría años y estudiantes del mismo
  colegio entre entrenamiento y prueba, lo que infla el desempeño y no refleja el uso real
  (predecir cohortes futuras y colegios nuevos) — plan §16.3.
- **Control de fuga (§18):** el preprocesamiento vive dentro del `Pipeline`, los puntajes por
  área quedan fuera del conjunto y la separación temporal se verifica en código.

## 2. Variables

- **Predictoras (7):** `periodo`, `naturaleza_colegio`, `modelo_pedagogico`, `zona`, `sexo`, `anio`, `estrato`.
- **Excluidas (3):** `nombre_colegio` (se usa como grupo de validación, no como predictora (§16.3)), `puntaje_global` (es la variable objetivo), `resultado_id` (identificador de fila o persona).
- Catálogo completo: `docs/ml/variables_modelo.md`.
- **Alias del diseño:** `periodo` = f(naturaleza_colegio, zona); `naturaleza_colegio` = f(periodo, zona); `zona` = f(periodo, naturaleza_colegio). Son variables redundantes: el modelo reparte su crédito
  entre ellas, así que no deben interpretarse por separado (relevante para F9).

## 3. Comparación por validación cruzada anidada

`GroupKFold` por `nombre_colegio` fuera y dentro; media de los pliegues ± error
estándar de la media. El conjunto de prueba no interviene aquí.

| Modelo | R² | RMSE | MAE | EE (RMSE) | Hiperparámetros elegidos |
|---|--:|--:|--:|--:|---|
| Baseline (media) | -0,093 | 48,22 | 38,80 | 1,29 | — |
| Ridge | 0,189 | 41,54 | 33,17 | 0,67 | `alpha`=500.0 |
| Lasso | 0,193 | 41,42 | 33,02 | 0,60 | `alpha`=0.3 |
| XGBoost | 0,190 | 41,51 | 33,15 | 0,71 | `colsample_bytree`=0.7, `learning_rate`=0.05, `max_depth`=2, `min_child_weight`=1, `n_estimators`=200, `reg_lambda`=20.0, `subsample`=0.9 |

El R² del baseline es negativo porque cada pliegue deja fuera colegios completos: la media
de los colegios de entrenamiento no es la media de los colegios evaluados. Es justamente la
dificultad que mide este esquema y la razón de comparar contra él.

## 4. Robustez temporal (validación expansiva)

Entrenar con los años previos y validar con el siguiente, sin reajustar hiperparámetros.

| Modelo | Entrena hasta | Valida | n validación | R² | RMSE | MAE |
|---|--:|--:|--:|--:|--:|--:|
| Baseline (media) | 2021 | 2022 | 3723 | -0,004 | 47,56 | 38,15 |
| Baseline (media) | 2022 | 2023 | 3653 | -0,007 | 47,27 | 37,98 |
| Ridge | 2021 | 2022 | 3723 | 0,240 | 41,37 | 32,99 |
| Ridge | 2022 | 2023 | 3653 | 0,230 | 41,34 | 32,94 |
| Lasso | 2021 | 2022 | 3723 | 0,245 | 41,24 | 32,83 |
| Lasso | 2022 | 2023 | 3653 | 0,231 | 41,31 | 32,95 |
| XGBoost | 2021 | 2022 | 3723 | 0,252 | 41,06 | 32,68 |
| XGBoost | 2022 | 2023 | 3653 | 0,229 | 41,36 | 33,12 |

## 5. Modelo seleccionado

**Lasso** — menor RMSE en validación cruzada (41,420); ningún modelo de menor complejidad queda dentro de 1 error estándar.

Regla aplicada (§16.4): menor RMSE en CV; si otro modelo queda dentro de 1 error estándar,
se prefiere el más simple; además debe superar al baseline en la prueba con un IC que no
incluya 0.

## 6. Año de prueba 2024 (evaluación única)

Todos los modelos se evalúan en una sola pasada, después de que la regla de selección ya
decidió con la validación cruzada. IC 95 % bootstrap remuestreando colegios.

| Modelo | R² | RMSE | MAE | IC 95 % RMSE |
|---|--:|--:|--:|---|
| Baseline (media) | -0,024 | 47,94 | 39,09 | [46,34; 49,38] |
| Ridge | 0,250 | 41,03 | 33,01 | [39,77; 42,25] |
| Lasso **(seleccionado)** | 0,250 | 41,03 | 33,02 | [39,81; 42,27] |
| XGBoost | 0,244 | 41,21 | 33,18 | [39,95; 42,45] |

**Mejora del modelo seleccionado sobre el baseline** (RMSE del baseline − RMSE del modelo): 6,91 puntos, IC 95 % [5,37; 8,54]. El intervalo no incluye 0: la mejora sobre el baseline es estadísticamente distinguible.

## 7. Colegios nunca vistos en el entrenamiento

El modelo seleccionado se reentrena sin `ABC`, `MNO` (9690 filas) y se evalúa en sus estudiantes de 2024 (352 filas). Es el escenario de uso real: un centro que el modelo no conoce.

| Colegio | n | R² | RMSE | MAE |
|---|--:|--:|--:|--:|
| `ABC` | 128 | 0,278 | 34,76 | 26,93 |
| `MNO` | 224 | 0,220 | 38,65 | 30,27 |
| **Conjunto** | 352 | 0,263 | 37,28 | 29,05 |

## 8. Referencia: media histórica del colegio

Predecir con la media del colegio en los años de entrenamiento —información que los modelos
no reciben, porque `nombre_colegio` se reserva como variable de agrupamiento— da R² 0,073, RMSE 45,63, MAE 36,98 en 2024. No es un modelo comparable:
no generaliza a colegios nuevos (cae a la media global) y por eso no entra en la selección.

## 9. Limitaciones

- Los efectos que los modelos recuperan fueron introducidos por el generador de datos
  ficticios (`reports/datos_ficticios/parametros_generacion.json`). Sirven para comprobar que
  el pipeline los recupera, no como evidencia educativa.
- El techo de R² está fijado por diseño: la mayor parte de la varianza del puntaje es
  habilidad individual y ruido por área, que ninguna variable del conjunto observa.
- `anio` entra como numérica: los modelos de árboles no extrapolan la tendencia más allá del
  último año visto, a diferencia de los lineales.
- El efecto propio de cada colegio no es un predictor (se usa como grupo), así que el modelo
  no puede distinguir dos centros con los mismos atributos.
