# ADR-0019: Cuentas de prueba de RLS en el tenant de ensayo (no `example.org`)

## Estado
Aceptado (post-F7, despliegue en Power BI Service / Fabric)

## Contexto
El plan (§15.5, F7) fijó cuentas ficticias con el dominio reservado `example.org` para los casos RLS-01..11.
Eso funciona en Power BI Desktop, porque *Ver como → Otro usuario* acepta cualquier cadena como UPN.

Al desplegar el informe con la prueba de 60 días de Power BI Service / Fabric (pendiente registrado en F7),
el SUP comprobó que **el Service no acepta UPN que no existan en el tenant**: para asignar miembros a un rol
de RLS y para que `USERPRINCIPALNAME()` devuelva un valor útil, la identidad debe ser una cuenta real del
directorio. Con `rector.abc@example.org` no es posible asignar el rol ni probar como *Viewer*.

## Decisión
Las cuentas de prueba de RLS son **cuentas creadas en el tenant de ensayo del proyecto**,
`@aldinti.onmicrosoft.com`, una por colegio más `rector.multi@…` (ABC y RST, caso RLS-04):

- `config/seguridad_rectores.example.csv` **se versiona** con esas 18 filas (17 cuentas) y es la fuente que
  usa Gold mientras no exista `config/seguridad_rectores.csv`.
- `config/seguridad_rectores.csv` sigue **excluido de git** y mantiene su papel: los correos de los rectores
  reales cuando el proyecto pase a producción. Si existe, tiene precedencia (`security.source_file`).
- Los casos de `tests/rls/casos_rls.md` usan estos UPN; la cuenta no registrada de RLS-03 es
  `no.registrado@aldinti.onmicrosoft.com` (no existe en `seguridad_rectores`).

## Consecuencias
- **Positivas:** RLS se puede validar de extremo a extremo en el Service con cuentas *Viewer* reales, que es
  el único escenario donde RLS actúa como control de acceso (§15.5); Desktop y Service usan las mismas
  identidades, así que la matriz RLS es comparable entre ambos.
- **Negativas / mitigaciones:** el repositorio versiona direcciones de correo. Son buzones de ensayo creados
  para el proyecto en un tenant propio, sin datos personales de terceros, y no identifican a ninguna persona
  real; la regla de no versionar correos de rectores reales (§21.10) se mantiene intacta sobre
  `seguridad_rectores.csv`. El tenant de ensayo debe darse de baja, o rotar sus cuentas, al terminar el
  periodo de prueba.
- Las evidencias DAX de F7 (`reports/bi/rls_simulacion_dax.csv`) se generaron antes de este cambio y
  conservan los UPN `example.org`: la expresión de filtro evaluada es la misma y los valores esperados no
  cambian, solo la literal comparada con `USERPRINCIPALNAME()`.
