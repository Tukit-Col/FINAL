from __future__ import annotations

import pytest
from tukit_comun.identificadores import derivar
from tukit_identidad.api import app

from tests._ayudas_identidad import bearer, cliente_api, sembrar_rol_acudiente_y_colegio


@pytest.fixture()
async def cliente():
    async with cliente_api(sembrar_rol_acudiente_y_colegio) as http:
        yield http


async def test_crear_cuenta_devuelve_sesion_y_token(cliente):
    r = await cliente.post(
        "/v1/cuenta",
        json={
            "correo": "nueva@ejemplo.com",
            "clave": "clave1234",
            "nombre": "Ana",
            "celular": "+57 300",
            "acepta_terminos": True,
        },
    )
    assert r.status_code == 201
    cuerpo = r.json()
    assert cuerpo["sesion"]["correo"] == "nueva@ejemplo.com"
    actual = await cliente.get("/v1/sesiones/actual", headers=bearer(cuerpo["token"]))
    assert actual.json()["correo"] == "nueva@ejemplo.com"


async def test_crear_cuenta_sin_aceptar_terminos_es_422_y_no_crea_nada(cliente):
    datos = {"correo": "sin@ejemplo.com", "clave": "clave1234", "nombre": "Ana"}
    r = await cliente.post("/v1/cuenta", json=datos)
    assert r.status_code == 422
    assert r.json()["error"] == "consentimiento_requerido"
    aceptando = await cliente.post("/v1/cuenta", json={**datos, "acepta_terminos": True})
    assert aceptando.status_code == 201
    assert aceptando.json()["sesion"]["correo"] == "sin@ejemplo.com"


async def test_crear_cuenta_deja_el_consentimiento_del_titular(cliente):
    from sqlalchemy import select
    from tukit_identidad.modelos import Consentimiento

    datos = {"correo": "con@ejemplo.com", "clave": "clave1234", "nombre": "Ana", "acepta_terminos": True}
    assert (await cliente.post("/v1/cuenta", json=datos)).status_code == 201
    async with app.state.motor.sesion() as db:
        filas = (await db.execute(select(Consentimiento))).scalars().all()
    assert [f.regimen for f in filas] == ["registro_titular"]


async def test_correo_con_credencial_es_409(cliente):
    datos = {
        "correo": "dup@ejemplo.com",
        "clave": "clave1234",
        "nombre": "Ana",
        "celular": None,
        "acepta_terminos": True,
    }
    await cliente.post("/v1/cuenta", json=datos)
    r = await cliente.post("/v1/cuenta", json=datos)
    assert r.status_code == 409
    assert r.json()["error"] == "correo_ya_registrado"


async def test_clave_corta_es_422(cliente):
    r = await cliente.post(
        "/v1/cuenta",
        json={
            "correo": "x@ejemplo.com",
            "clave": "corta",
            "nombre": "Ana",
            "celular": None,
            "acepta_terminos": True,
        },
    )
    assert r.status_code == 422
    assert r.json()["error"] == "clave_debil"


async def test_registrar_hijo_sin_colegio_es_422(cliente):
    login = (
        await cliente.post(
            "/v1/cuenta",
            json={
                "correo": "papa@ejemplo.com",
                "clave": "clave1234",
                "nombre": "Papa",
                "celular": None,
                "acepta_terminos": True,
            },
        )
    ).json()
    tok = {"Authorization": f"Bearer {login['token']}"}
    r = await cliente.post(
        "/v1/cuenta/hijos",
        headers=tok,
        json={"apodo": "Pepe", "grado": "Tercero", "anio_lectivo": 2026, "consentimiento": True},
    )
    assert r.status_code == 422
    assert r.json()["error"] == "hijo_sin_colegio"


async def test_registrar_hijo_sin_consentimiento_es_422(cliente):
    login = (
        await cliente.post(
            "/v1/cuenta",
            json={
                "correo": "mama@ejemplo.com",
                "clave": "clave1234",
                "nombre": "Mama",
                "celular": None,
                "acepta_terminos": True,
            },
        )
    ).json()
    tok = {"Authorization": f"Bearer {login['token']}"}
    cid = str(derivar("colegio", "2.4"))
    sid = str(derivar("sede", "2.4", "u"))
    r = await cliente.post(
        "/v1/cuenta/hijos",
        headers=tok,
        json={
            "apodo": "Pepe",
            "colegio_id": cid,
            "sede_id": sid,
            "grado": "Tercero",
            "anio_lectivo": 2026,
            "consentimiento": False,
        },
    )
    assert r.status_code == 422
    assert r.json()["error"] == "consentimiento_requerido"


async def test_registrar_hijo_y_listarlo_devuelve_apodo(cliente):
    login = (
        await cliente.post(
            "/v1/cuenta",
            json={
                "correo": "tia@ejemplo.com",
                "clave": "clave1234",
                "nombre": "Tia",
                "celular": None,
                "acepta_terminos": True,
            },
        )
    ).json()
    tok = {"Authorization": f"Bearer {login['token']}"}
    cid = str(derivar("colegio", "2.4"))
    sid = str(derivar("sede", "2.4", "u"))
    creado = await cliente.post(
        "/v1/cuenta/hijos",
        headers=tok,
        json={
            "apodo": "Pepe",
            "colegio_id": cid,
            "sede_id": sid,
            "grado": "Tercero",
            "anio_lectivo": 2026,
            "consentimiento": True,
        },
    )
    assert creado.status_code == 201
    listado = (await cliente.get("/v1/cuenta/hijos", headers=tok)).json()
    assert listado["total"] == 1
    assert listado["hijos"][0]["apodo"] == "Pepe"
    assert listado["hijos"][0]["grado"] == "Tercero"
