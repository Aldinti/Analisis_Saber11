# Manual de usuario — tableros Saber 11

Para quienes leen los tableros: la Dirección de Calidad y los rectores. No hace falta saber
nada de programación.

> ⚠️ **Los datos son ficticios.** Se generaron para poner a prueba la plataforma, no describen
> a ningún colegio ni estudiante real. Todas las páginas llevan ese rótulo a la vista. No se
> deben tomar decisiones con estas cifras hasta cargar los datos auténticos.

---

## 1. Cuál es su tablero

| Si usted es… | Abra | Qué ve |
|---|---|---|
| Dirección de Calidad | `powerbi/Saber11_Estrategico.pbip` | Todos los colegios del distrito, comparados entre sí |
| Rector de un colegio | `powerbi/Saber11_Operativo.pbip` | **Solo su colegio**, comparado con el promedio del distrito |

Se abren con Power BI Desktop. Si movió la carpeta del proyecto, ajuste la ruta en
*Inicio → Transformar datos → Parámetro `RutaGold`* y pulse **Actualizar**.

---

## 2. Tablero estratégico (5 páginas)

**P1 Resumen.** Las cuatro cifras de cabecera: promedio global, número de evaluados,
variación frente al año anterior y porcentaje de estudiantes que superan el percentil 75 del
distrito.

**P2 Áreas.** Promedio de cada una de las cinco áreas, comparable por colegio, estrato o
sexo. Sirve para ver dónde está la fortaleza y la debilidad, no solo el promedio general.

**P3 Tendencias.** Evolución 2021–2024 del global y de cada área.

**P4 Benchmarking.** Comparación entre grupos: colegio frente al distrito, pública frente a
privada, urbana frente a rural, por modelo pedagógico y por estrato.

**P5 Distribución.** Cómo se reparten los puntajes, no solo su promedio: dos colegios con el
mismo promedio pueden tener realidades muy distintas.

**Los filtros de arriba (año, colegio, estrato, sexo, área) afectan a toda la página.** Para
volver al estado inicial, use *Restablecer valores predeterminados* en la cinta *Ver*.

---

## 3. Tablero operativo (3 páginas)

Cada rector ve únicamente su colegio: el filtro se aplica a partir de su cuenta, no hay nada
que seleccionar.

**O1 Mi colegio.** Evaluados, promedio del colegio y **brecha frente al distrito**: cuántos
puntos por encima o por debajo está.

**O2 Subgrupos.** El mismo resultado abierto por sexo, estrato o grupo, para encontrar dónde
concentrar el apoyo.

**O3 Distribución.** Percentiles 10, 25, 50, 75 y 90 del colegio: dónde está la mitad de los
estudiantes y qué tan larga es cada cola.

---

## 4. Por qué a veces no aparece un número

No es un fallo. Hay tres motivos, todos deliberados:

| Lo que ve | Qué significa |
|---|---|
| **«Dato suprimido»** o una celda en blanco | Ese grupo tiene **menos de 5 estudiantes**. Mostrar su promedio permitiría deducir el resultado de una persona concreta. A veces se suprime también el segundo grupo más pequeño, porque con el total a la vista el primero se podría despejar por resta |
| **«Usuario sin colegio asignado»** | Su cuenta no está en la tabla de rectores. Solicítelo al administrador del tablero |
| Un comparativo vacío en P4 | No hay datos de los dos lados de la comparación en el filtro actual; el tablero lo dice en lugar de mostrar un cero engañoso |

Un cero y un dato ausente no son lo mismo: el tablero nunca muestra cero donde falta
información.

---

## 5. Cómo leer bien estas cifras

- **El promedio del distrito no cambia al filtrar su colegio.** Es intencional: es la
  referencia fija contra la que se compara.
- **Una brecha no explica su causa.** Que un grupo puntúe distinto no dice por qué; el tablero
  describe, no diagnostica.
- **Los grupos pequeños se mueven mucho.** Con pocos estudiantes, un cambio de un año a otro
  puede ser casualidad. Mire la distribución (P5 / O3) antes de concluir.
- **Los resultados por área no son comparables con el global:** las áreas van de 0 a 100 y el
  global de 0 a 500.

---

## 6. Sobre la protección de los datos

- Ningún tablero contiene nombres ni documentos de estudiantes: esos datos se eliminan antes
  de llegar aquí.
- El tablero operativo solo contiene **datos agregados**; no existe en él una fila por
  estudiante, ni siquiera oculta.
- Cada rector ve solo su colegio. Esa restricción actúa en Power BI Service, no en el archivo:
  **compartir el archivo equivale a compartir todos los datos que contiene**. Distribuya
  siempre el enlace del servicio, nunca el archivo.

---

## 7. Preguntas frecuentes

**¿Cada cuánto se actualizan?** Cuando se procesa una nueva carga de resultados. En Desktop
hay que pulsar *Actualizar*; publicado en el servicio, se programa allí.

**¿Puedo exportar a Excel?** Sí, datos resumidos. El detalle por estudiante no está
disponible por diseño.

**Veo un número distinto al del año pasado en el mismo indicador.** Cada carga reemplaza los
datos. Si hubo correcciones en el origen, los históricos se recalculan; el registro de
ejecuciones guarda qué archivo produjo cada versión.

**¿A quién pregunto?** Al responsable técnico del proyecto; para decidir qué se publica y
quién accede, al responsable del dato.
