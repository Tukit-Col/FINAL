from __future__ import annotations

from tukit_identidad.sembrar_acceso import PERMISOS, ROL_PERMISO


def test_el_permiso_de_apodo_es_de_menor():
    apodo = next(p for p in PERMISOS if p["codigo"] == "estudiante:leer:apodo")
    assert apodo["campo"] == "apodo"
    assert apodo["clasificacion_minima"] == "menor"


def test_el_permiso_de_nombre_es_personal_no_menor():
    nombre = next(p for p in PERMISOS if p["codigo"] == "usuario:leer:nombre")
    assert nombre["campo"] == "nombre"
    assert nombre["clasificacion_minima"] == "personal"


def test_el_acudiente_ve_apodos_y_el_admin_ve_nombres():
    assert ("acudiente", "estudiante:leer:apodo") in ROL_PERMISO
    assert ("admin", "usuario:leer:nombre") in ROL_PERMISO
    assert ("operador", "usuario:leer:nombre") in ROL_PERMISO
