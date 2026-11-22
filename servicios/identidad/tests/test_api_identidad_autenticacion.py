from __future__ import annotations

import uuid

import pytest
from tukit_comun.identificadores import derivar
from tukit_identidad.dominio.privacidad import FRASE_CONFIRMACION

_COLEGIO = str(derivar("colegio", "2.4"))
_HIJO = {"colegio_id": _COLEGIO, "grado": "Quinto"}

RUTAS_CON_SESION = [
    ("GET", "/v1/sesiones/actual", None),
    ("GET", "/v1/cuenta", None),
    ("GET", "/v1/cuenta/direcciones", None),
    ("POST", "/v1/cuenta/direcciones", {"ciudad": "Bogota", "linea": "Calle 1"}),
    ("PATCH", f"/v1/cuenta/direcciones/{uuid.uuid4()}", {"ciudad": "Cali", "linea": "Avenida 3"}),
    ("DELETE", f"/v1/cuenta/direcciones/{uuid.uuid4()}", None),
    ("GET", "/v1/cuenta/hijos", None),
    (
        "POST",
        "/v1/cuenta/hijos",
        {
            "apodo": "Pepe",
            "colegio_id": _COLEGIO,
            "sede_id": str(derivar("sede", "2.4", "Sede unica")),
            "grado": "Tercero",
            "anio_lectivo": 2026,
            "consentimiento": True,
        },
    ),
    ("GET", "/v1/cuenta/matriculas", None),
    ("POST", "/v1/cuenta/matriculas", {"hijos": [_HIJO]}),
    ("PUT", f"/v1/cuenta/matriculas/{uuid.uuid4()}", _HIJO),
    ("DELETE", f"/v1/cuenta/matriculas/{uuid.uuid4()}", None),
    ("GET", "/v1/cuenta/mis-datos", None),
    ("GET", "/v1/cuenta/mis-datos/exportar", None),
    ("POST", "/v1/cuenta/consentimientos/revocar", None),
    ("POST", "/v1/cuenta/supresion", {"confirmacion": FRASE_CONFIRMACION}),
    ("GET", f"/v1/usuarios/nombres?ids={uuid.uuid4()}", None),
    ("GET", "/v1/admin/acudientes", None),
    ("GET", "/v1/admin/acudientes?ids=nope", None),
]

CREDENCIALES_QUE_NO_VALEN = {
    "sin_cabecera": {},
    "cabecera_vacia": {"Authorization": ""},
    "token_inventado": {"Authorization": "Bearer no-sirve"},
}


@pytest.mark.parametrize("cabeceras", CREDENCIALES_QUE_NO_VALEN.values(), ids=CREDENCIALES_QUE_NO_VALEN)
@pytest.mark.parametrize(
    ("metodo", "ruta", "cuerpo"), RUTAS_CON_SESION, ids=[f"{m} {r}" for m, r, _ in RUTAS_CON_SESION]
)
async def test_sin_token_valido_es_401_y_solo_el_sobre(cliente, metodo, ruta, cuerpo, cabeceras):
    r = await cliente.request(metodo, ruta, json=cuerpo, headers=cabeceras)

    assert r.status_code == 401
    assert r.json()["error"] == "sesion_invalida"
    assert set(r.json()) <= {"error", "mensaje", "campo"}
