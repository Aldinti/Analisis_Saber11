# Informe final — Análisis Saber 11

Cierre del proyecto: qué se construyó, qué se comprobó y qué **no** se puede concluir con
ello. Fecha: 16 de septiembre de 2026.

---

## 1. Léase esto antes que los resultados

| Limitación | Consecuencia práctica |
|---|---|
| **Los datos son ficticios.** El CSV de origen era un ejemplo inventado y se amplió con un generador (F1b) de efectos conocidos | Ningún número de este informe describe la educación real. Los resultados de ML y SHAP **validan el pipeline**, no miden el sistema educativo |
| **`periodo` es un alias del diseño**: queda determinado por naturaleza × zona | Esas tres variables se reparten el crédito; no son interpretables por separado |
| **El efecto propio de cada colegio no es una variable** del modelo (se reserva para validar) | El modelo explica atributos del colegio, no el centro concreto |
| **El RLS no se validó con cuentas reales en el servicio** | El diseño está probado en Desktop y prevalidado en DAX; falta la prueba con *Viewers* reales (ADR-0015) |
| **Los umbrales de calidad se calibraron con estos datos** | Habrá que revisarlos con datos auténticos |

Con datos reales hay que **reejecutar todo y reinterpretar desde cero**; ninguna conclusión
de las secciones 3 a 6 se traslada.

---

## 2. Qué se entregó

| Objetivo de `Objetivos.md` | Estado |
|---|---|
| O1 · Lakehouse Medallion en Parquet | ✅ Bronze/Silver/Gold con dos quality gates y trazabilidad por ejecución |
| O2 · Dashboard estratégico | ✅ 5 páginas, 25 medidas DAX, 21/21 KPIs iguales al SQL de control |
| O3 · Dashboard operativo con RLS | ✅ 3 páginas, 23 medidas, 11 casos RLS aprobados, supresión de grupos pequeños |
| O4 · Modelos + SHAP | ✅ 4 modelos comparados, explicabilidad verificada y evaluación de sesgos |

Además, sin estar en los objetivos originales: sistema formal de calidad (19 reglas),
pipeline de un comando, 276 pruebas automáticas y la documentación de operación, pruebas,
seguridad y linaje.

---

## 3. O1 — Lakehouse

14 666 evaluaciones · 16 colegios · 2021–2024 · 11 tablas Gold.

- **Bronze** conserva el CSV original por `sha256`, de solo lectura; reingerir el mismo
  archivo se omite.
- **Silver** elimina documento y nombres, tipa, normaliza categorías y seudonimiza con
  HMAC-SHA-256. `Silver + rechazos = Bronze` en todas las ejecuciones.
- **Gold** publica el modelo estrella con claves sustitutas estables (ADR-0017), particionado
  `anio/periodo`, y agregados **con supresión aplicada antes de salir de la capa**.
- **Calidad:** 19 reglas en dos gates. Gold no se construye sin el gate de Silver aprobado;
  ML no entrena sin el de Gold. Últimas ejecuciones: 100 % de reglas aprobadas.
- **Reproducibilidad comprobada:** dos ejecuciones dejan el mismo contenido en Silver y en
  las 11 tablas Gold (hash de contenido), y las mismas métricas de ML.

## 4. O2 — Dashboard estratégico

Cinco páginas (Resumen, Áreas, Tendencias, Benchmarking, Distribución) sobre el modelo
estrella, con 25 medidas DAX documentadas.

- **21 de 21 KPIs** coinciden con la consulta SQL de control dentro de 0,01.
- Las comparaciones que los datos no soportan muestran un aviso explícito, nunca un cero.
- El proyecto se versiona como PBIP (TMDL + PBIR): el modelo y el informe son texto revisable,
  sin caché de datos.

## 5. O3 — Dashboard operativo y RLS

- **Modelo propio solo con agregados** (ADR-0018): ni siquiera oculta existe una fila por
  estudiante. Es la única forma de que un *Viewer* con permiso Build no llegue a microdatos.
- **RLS dinámico** por `USERPRINCIPALNAME()` con tabla de seguridad desconectada.
- **11 casos RLS aprobados**, incluidos el usuario sin colegio, el rector con dos colegios,
  las mayúsculas del UPN y la supresión de grupos pequeños (validada con un Gold de fixture).
- **13 de 13 KPIs** iguales al SQL calculado desde los hechos.
- El comparativo distrital no se filtra con el rol: viene de una tabla agregada sin relación
  con `dim_colegio`, porque `ALL()` no puede quitar un filtro de RLS.

## 6. O4 — Modelos y explicabilidad

**Esquema de validación:** el año más reciente (2024) se apartó al inicio y se evaluó **una
sola vez**; la comparación y el ajuste se hicieron con validación cruzada anidada agrupada por
colegio, para que ningún estudiante del colegio evaluado interviniera en su propio ajuste.

| Modelo | RMSE (CV) | R² (2024) | RMSE (2024) |
|---|--:|--:|--:|
| Baseline (media) | 48,22 | −0,024 | 47,94 |
| Ridge | 41,54 | 0,250 | 41,03 |
| **Lasso** (elegido) | **41,42** | 0,250 | 41,03 |
| XGBoost | 41,51 | 0,244 | 41,21 |

- Mejora sobre el baseline: **6,91 puntos de RMSE**, IC 95 % [5,37; 8,54].
- En dos colegios nunca vistos en el entrenamiento el modelo mantiene R² 0,258.
- **XGBoost no aporta:** los efectos son aditivos por construcción y la búsqueda lo lleva a
  árboles de profundidad 2. El techo de R² ≈ 0,25 también es de diseño: el resto de la
  varianza es habilidad individual, que ninguna variable observa.

**SHAP.** Aditividad verificada (error máximo 3,7e-04). Orden de importancia: estrato,
naturaleza del colegio, zona, año, modelo pedagógico. **La prueba de recuperación de efectos
sintéticos se aprobó**: estrato 11,49 medido frente a 12,50 esperado; privada − pública 19,88
frente a 21,92; rural − urbana −18,28 frente a −20,00. Es decir, el pipeline recupera lo que
el generador puso, con el encogimiento que produce la regularización. Lasso anula
exactamente `periodo` y `sexo`, las dos variables cuyo efecto real sobre el global es nulo.

> SHAP explica el comportamiento del modelo; no demuestra causalidad.

**Sesgos.** El hallazgo relevante fue metodológico: el modelo predice **2,38 puntos por
debajo en todo 2024**, un desvío global que aparecía en 14 subgrupos y simulaba sesgos por
sexo, zona y naturaleza que no existen. Separando el sesgo global del propio de cada grupo
quedan solo 4 subgrupos con desvío específico. Y las cuatro brechas de error que superan el
umbral se explican por la dispersión del resultado (correlación 0,90–0,99), no por un trato
desigual del modelo: en estrato 6 el techo de la escala comprime los resultados.

---

## 7. Cómo se sostiene esto

| Control | Estado |
|---|---|
| Pruebas automáticas | 276 verdes; cobertura 94 %, con el umbral de 80 % exigido por la propia suite |
| Pipeline completo | Un comando, 82 s, código 0; se detiene en la primera etapa que falla |
| Escaneo de seguridad | Automatizado: sin datos, secretos ni PII en lo versionado |
| Decisiones registradas | 10 ADR |
| Documentación | Operación, pruebas, seguridad, linaje, diccionario, manual técnico y manual de usuario |

---

## 8. Pendientes al cierre

Ninguno impide usar la plataforma con datos ficticios; **todos deben resolverse antes de
cargar datos reales**.

1. **Decisiones del responsable del dato** ([seguridad.md](../docs/seguridad.md) §3):
   endurecer el acceso a Bronze, custodia y respaldo de la clave HMAC, política de retención
   y revisión jurídica.
2. **Publicación en Power BI Service** con la prueba de 60 días y repetición de los casos RLS
   con cuentas *Viewer* reales (ADR-0015).
3. **Usuarios reales** de `seguridad_rectores` y del rol de Dirección.
4. **Puntos de corte oficiales** de los niveles de desempeño del ICFES: mientras no existan,
   el tablero usa percentiles.
5. **Recalibrar umbrales de calidad** y reentrenar con los datos auténticos.

---

## 9. Lo que este proyecto demuestra

Que se puede construir una plataforma analítica completa —lakehouse, calidad, BI con
seguridad por fila, modelos y explicabilidad— sin costo de licencias ni servidores, y que
cada afirmación que produce es verificable: los KPIs contra SQL, las métricas contra un
baseline con intervalos, las explicaciones contra los efectos conocidos, y la privacidad
contra pruebas que fallan si alguien la rompe.

Lo que **no** demuestra es nada sobre la educación en el distrito. Para eso hacen falta los
datos reales y el mismo rigor aplicado otra vez.
