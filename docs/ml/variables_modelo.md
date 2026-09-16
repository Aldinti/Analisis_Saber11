# Catálogo de variables del modelo (F8)

> Generado por `saber11.ml` en la ejecución `20260916T052758Z-1edef148`. No editar a mano.

Objetivo: `puntaje_global` · Variable de agrupamiento en la validación: `nombre_colegio`.

## Incluidas

| Variable | Tipo en el modelo | Tratamiento |
|---|---|---|
| `periodo` | Categórica | One-Hot (`handle_unknown="ignore"`) |
| `naturaleza_colegio` | Categórica | One-Hot (`handle_unknown="ignore"`) |
| `modelo_pedagogico` | Categórica | One-Hot (`handle_unknown="ignore"`) |
| `zona` | Categórica | One-Hot (`handle_unknown="ignore"`) |
| `sexo` | Categórica | One-Hot (`handle_unknown="ignore"`) |
| `anio` | Numérica | `StandardScaler` en los modelos lineales; sin escalar en XGBoost |
| `estrato` | Numérica | `StandardScaler` en los modelos lineales; sin escalar en XGBoost |

## Excluidas

| Variable | Motivo |
|---|---|
| `nombre_colegio` | se usa como grupo de validación, no como predictora (§16.3) |
| `puntaje_global` | es la variable objetivo |
| `resultado_id` | identificador de fila o persona |

## Alias del diseño (dependencias funcionales)

Estas variables quedan determinadas por otras, así que el modelo reparte el crédito
entre ellas: sus coeficientes y sus valores SHAP no son interpretables por separado.

| Variable | Determinada por |
|---|---|
| `periodo` | `naturaleza_colegio`, `zona` |
| `naturaleza_colegio` | `periodo`, `zona` |
| `zona` | `periodo`, `naturaleza_colegio` |
