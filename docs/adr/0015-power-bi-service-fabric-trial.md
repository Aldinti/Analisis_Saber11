# ADR-0015: Incorporación de Power BI Service / Fabric (Trial 60 días) para RLS real

## Estado
Aceptado

## Contexto
Power BI Desktop únicamente permite simular la seguridad por filas mediante la opción "Ver como rol". Un archivo `.pbix` distribuido físicamente otorga permisos de autor a cualquier receptor, anulando la protección de RLS. Para evaluar y demostrar RLS dinámico efectivo se requiere un entorno de servicio en la nube.

## Decisión
Incorporar al alcance del proyecto la publicación del modelo semántico y reportes en **Power BI Service / Fabric** utilizando una licencia de prueba (*Trial*) de 60 días sin costo.

## Consecuencias
- **Positivas:**
  - Permite verificar la asignación de usuarios reales o de prueba al rol `Rol_Rector` con permisos de *Viewer*, garantizando que el RLS restrinja efectivamente los datos.
  - Habilita la demostración integral de la arquitectura sin costos de licenciamiento permanente durante la fase académica.
  - Valida el flujo corporativo completo de BI moderno (Desarrollo local -> Publicación -> Consumo gobernado).
- **Negativas / Mitigaciones:**
  - La ventana de prueba está acotada a 60 días; mitigado planificando las pruebas de RLS en nube dentro de dicho periodo.
