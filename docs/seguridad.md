# Revisión de seguridad y privacidad (F13)

Checklist del plan §21 con la evidencia de cada punto, verificado el **16-sep-2026** sobre el
commit vigente. Lo que se puede comprobar solo, se comprueba solo:
`tests/unit/test_repo_seguro.py` (10 controles del repositorio) y
`tests/data/test_no_pii.py` (15 controles de los datos publicados) fallan si algo de esto se
rompe, así que esta revisión es repetible y no una foto de un día.

> **Contexto que condiciona todo lo demás:** los datos del proyecto son ficticios (§4, S6).
> Aun así se tratan como si fueran reales, para que los controles queden probados de verdad
> antes de que entren datos auténticos.

---

## 1. Checklist §21

| # | Medida | Estado | Evidencia |
|--:|---|:--:|---|
| 1 | Seudonimización con **HMAC-SHA-256** y clave ≥ 32 bytes fuera del repositorio | ✅ | `src/saber11/security/pseudonymize.py`; `config.get_hmac_key()` exige ≥ 32 caracteres; `tests/unit/test_pseudonymize.py` |
| 2 | El seudónimo **no llega** a Power BI | ✅ | `estudiante_pid` no existe en ninguna tabla Gold: `tests/data/test_no_pii.py::test_gold_no_tiene_columnas_de_identificacion_directa` |
| 3 | Nombres y documento **eliminados en Silver** | ✅ | `tests/data/test_silver_contract.py` (columnas exactas) y `test_no_pii.py` |
| 4 | Bronze en zona restringida | ⚠️ Parcial | La copia original es **de solo lectura** (verificado). La carpeta hereda la ACL del proyecto: `aldin` y Administradores con control total, sin acceso para «Usuarios». Falta el endurecimiento explícito y el cifrado de disco → §3 |
| 5 | Temporales de DuckDB dentro del proyecto | ✅ | `SET temp_directory` en bronze, silver, gold, motor DQ y carga de ML; `data/_tmp` está en `.gitignore` y se limpia con `.\tasks.ps1 clean-tmp` |
| 6 | Logs sin filas de datos | ✅ | `logging_utils.py` escribe solo a consola, sin archivo; los mensajes llevan conteos, `run_id` y rutas. El `run_log` persistido guarda conteos y hashes, nunca celdas (revisado) |
| 7 | Respaldo de Bronze y de la clave, por separado | ⚠️ Pendiente | Decisión del responsable → §3 |
| 8 | Silver/Gold sin PII y con lectura limitada | ✅ | `tests/data/test_no_pii.py`; ninguna capa fuera de Bronze contiene identificadores |
| 9 | Nada de `.pbix` en git; PBIP sin caché de datos | ✅ | `test_repo_seguro.py::test_no_se_versionan_datos_ni_binarios_de_modelo`; `.gitignore` excluye `*.pbix` y `powerbi/**/.pbi/cache.abf` |
| 10 | Tabla de seguridad real sin versionar | ✅ | `config/seguridad_rectores.csv` en `.gitignore`; se versiona solo el archivo con cuentas del tenant de ensayo (ADR-0019) |
| 11 | Cuadernos sin salidas guardadas | ✅ | No hay cuadernos en el repositorio; el control queda activo por si se añaden: `test_los_cuadernos_no_guardan_salidas` |
| 12 | Revisión jurídica del tratamiento de datos | ⚠️ Pendiente | Actividad externa → §3 |

---

## 2. Escaneo del repositorio

Criterio de aceptación de F13. Resultados del escaneo automático sobre los archivos
versionados (`git ls-files`):

| Qué se buscó | Resultado |
|---|---|
| Archivos de datos o binarios de modelo (`.parquet`, `.joblib`, `.pbix`, `.key`, `.pem`, `.abf`) | **Ninguno** |
| Rutas bajo `data/` o `models/` | **Ninguna** |
| Un `.env` versionado | **No existe**; sí está la plantilla `.env.example`, con el valor vacío |
| La clave HMAC local dentro de algún archivo versionado | **No aparece** |
| Cadenas de 64 hexadecimales | 5 coincidencias, **todas son SHA-256 de archivos** (perfilamiento y parámetros de generación), no secretos |
| CSV versionados | 9, todos de configuración, evidencia de BI/ML o fixture de pruebas |
| Nombres o números de documento en `reports/` y `docs/` | **Ninguno** (contrastado contra la copia original de Bronze) |

**Caso a tener presente:** `tests/fixtures/mini_icfes.csv` sí contiene columnas de nombres y
`nroDoc`, a propósito: es el fixture que ejercita la eliminación de PII en Silver. Una prueba
verifica que sus identidades siguen el patrón que produce el generador de F1b —la palabra
«Nombre» o «Apellido», una inicial y un número correlativo—, de modo que nadie pueda
regenerarlo desde datos auténticos sin que la suite se ponga roja.

> Este documento tampoco puede citar identidades de ejemplo: el mismo control lo escanea, y
> escribirlas aquí lo pondría rojo. Es el comportamiento buscado.

---

## 3. Pendientes: decisiones del responsable del dato

No son hallazgos técnicos sino decisiones que el proyecto no puede tomar por su cuenta.
Ninguna bloquea el uso con datos ficticios; **todas deben cerrarse antes de cargar datos
reales**.

| Pendiente | Por qué importa | Qué haría falta |
|---|---|---|
| **Endurecer el acceso a `data/bronze/`** | Es la única capa con datos personales | Restringir la ACL al usuario o grupo autorizado. El comando, para ejecutarlo con una consola de administrador: `icacls "data\bronze" /inheritance:r /grant:r "$env:USERNAME:(OI)(CI)F" /grant:r "SYSTEM:(OI)(CI)F"`. Recomendado además activar BitLocker en el disco |
| **Custodia y respaldo de la clave HMAC** | Si se pierde, los seudónimos de cargas anteriores dejan de ser comparables y hay que re-seudonimizar desde Bronze | Designar responsable y guardarla en un gestor de secretos o archivo cifrado, **separada** del respaldo de Bronze |
| **Política de retención de Bronze** | Guardar PII sin plazo definido es una decisión, no un descuido | Fijar un plazo y un procedimiento de borrado verificable |
| **Revisión jurídica** | Son resultados académicos de personas, posiblemente menores de edad | Validación por el área jurídica antes de tratar datos reales |
| **Usuarios reales de RLS** | Hoy el tenant de ensayo cubre las pruebas | Definir los rectores y la Dirección de Calidad (ADR-0019) |

---

## 4. Lo que estos controles **no** garantizan

- **Anonimato.** La seudonimización con HMAC es robusta frente a enumeración, pero el dato
  sigue siendo personal: con la clave se puede volver a enlazar. Nunca debe describirse el
  resultado como anónimo.
- **Reidentificación por cuasi-identificadores.** `colegio + año + sexo + estrato + grupo`
  puede singularizar a alguien en grupos pequeños. Por eso Gold aplica supresión primaria y
  complementaria (`k_min` = 5) y el modelo operativo solo expone agregados (ADR-0018); ambas
  cosas están verificadas, pero el riesgo se mitiga, no desaparece.
- **Protección del `.pbix` distribuido.** RLS solo actúa en el Service y sobre *Viewers*
  (§15.5): repartir un archivo de Power BI equivale a repartir los datos que contiene.
- **Seguridad del equipo.** Cifrado de disco, antivirus y control de acceso físico quedan
  fuera del alcance del proyecto.
