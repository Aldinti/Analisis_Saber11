from saber11.transform.naming import normalize_colname


def test_normalize_colname():
    assert normalize_colname("Lectura Crítica") == "lectura_critica"
    assert normalize_colname("Matemáticas") == "matematicas"
    assert normalize_colname("Sociales y Ciudadana") == "sociales_y_ciudadana"
    assert normalize_colname("Ciencias Naturales") == "ciencias_naturales"
    assert normalize_colname("Inglés") == "ingles"
    assert normalize_colname("año") == "anio"
    assert normalize_colname("nroDoc") == "nrodoc"
