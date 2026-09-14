-- F4 Gold · paso 4: dataset de ML y tabla de seguridad RLS.

-- Dataset para F8 (plan §16.2): objetivo puntaje_global; nombre_colegio solo como grupo de validación.
-- Excluidos por leakage: punt_* (determinan el Global), grupo, flags y cualquier seudónimo.
CREATE OR REPLACE TABLE ml_dataset AS
SELECT
    f.resultado_id,
    f.anio,
    f.periodo,
    c.nombre_colegio,
    c.naturaleza_colegio,
    c.modelo_pedagogico,
    u.zona,
    p.sexo,
    p.estrato,
    f.puntaje_global
FROM fact_resultado f
JOIN dim_colegio c USING (colegio_id)
JOIN dim_ubicacion u USING (ubicacion_id)
JOIN dim_perfil_estudiante p USING (perfil_id)
ORDER BY f.anio, f.periodo, f.resultado_id;

-- Tabla de seguridad (plan §15.3). Entrada: seguridad_fuente(email_rector, nombre_colegio), cargada desde
-- config/seguridad_rectores.csv (real, no versionado) o, si no existe, del ejemplo ficticio.
-- Se enlaza por nombre de colegio; un colegio inexistente deja colegio_id NULL y DQ-REF-002 lo rechaza.
CREATE OR REPLACE TABLE seguridad_rectores AS
SELECT DISTINCT
    lower(trim(s.email_rector)) AS email_rector,
    c.colegio_id
FROM seguridad_fuente s
LEFT JOIN dim_colegio c
  ON clave_natural(c.nombre_colegio) = clave_natural(s.nombre_colegio)
ORDER BY email_rector, c.colegio_id;
