"""La cuenta del acudiente: crear, promover al invitado, y registrar hijos."""

from __future__ import annotations

import httpx
import pytest
from sqlalchemy import insert
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool
from tukit_comun.bd import MotorServicio
from tukit_comun.identificadores import derivar
from tukit_identidad.api import app
from tukit_identidad.modelos import Base, Colegio, Sede


@pytest.fixture()
async def cliente():
    engine = create_async_engine(
        "sqlite+aiosqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False}
    )
    async with engine.begin() as conexion:
        await conexion.run_sync(Base.metadata.create_all)
    fabrica = async_sessionmaker(engine, expire_on_commit=False)
    async with fabrica() as s:
        rol = Base.metadata.tables["rol"]
        await s.execute(insert(rol).values(codigo="acudiente", nombre="Acudiente", del_sistema=True))
        colegio = Colegio(id=derivar("colegio", "2.4"), nombre="Colegio San Pedro")
        s.add(colegio)
        await s.flush()
        s.add(Sede(id=derivar("sede", "2.4", "u"), colegio_id=colegio.id, nombre="Sede unica"))
        await s.commit()
    app.state.motor = MotorServicio(servicio="prueba", engine=engine, _fabrica=fabrica)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://prueba") as http:
        yield http
    await engine.dispose()


async def test_crear_cuenta_devuelve_sesion_y_token(cliente):
    r = await cliente.post(
        "/v1/cuenta",
        json={"correo": "nueva@ejemplo.com", "clave": "clave1234", "nombre": "Ana", "celular": "+57 300"},
    )
    assert r.status_code == 201
    cuerpo = r.json()
    assert cuerpo["sesion"]["correo"] == "nueva@ejemplo.com"
    assert cuerpo["token"]


async def test_correo_con_credencial_es_409(cliente):
    datos = {"correo": "dup@ejemplo.com", "clave": "clave1234", "nombre": "Ana", "celular": None}
    await cliente.post("/v1/cuenta", json=datos)
    r = await cliente.post("/v1/cuenta", json=datos)
    assert r.status_code == 409
    assert r.json()["error"] == "correo_ya_registrado"


async def test_clave_corta_es_422(cliente):
    r = await cliente.post(
        "/v1/cuenta", json={"correo": "x@ejemplo.com", "clave": "corta", "nombre": "Ana", "celular": None}
    )
    assert r.status_code == 422
    assert r.json()["error"] == "clave_debil"


async def test_registrar_hijo_sin_colegio_es_422(cliente):
    login = (await cliente.post(
        "/v1/cuenta",
        json={"correo": "papa@ejemplo.com", "clave": "clave1234", "nombre": "Papa", "celular": None},
    )).json()
    tok = {"Authorization": f"Bearer {login['token']}"}
    r = await cliente.post(
        "/v1/cuenta/hijos",
        headers=tok,
        json={"apodo": "Pepe", "grado": "Tercero", "anio_lectivo": 2026, "consentimiento": True},
    )
    assert r.status_code == 422
    assert r.json()["error"] == "hijo_sin_colegio"


async def test_registrar_hijo_sin_consentimiento_es_422(cliente):
    login = (await cliente.post(
        "/v1/cuenta",
        json={"correo": "mama@ejemplo.com", "clave": "clave1234", "nombre": "Mama", "celular": None},
    )).json()
    tok = {"Authorization": f"Bearer {login['token']}"}
    cid = str(derivar("colegio", "2.4"))
    sid = str(derivar("sede", "2.4", "u"))
    r = await cliente.post(
        "/v1/cuenta/hijos",
        headers=tok,
        json={"apodo": "Pepe", "colegio_id": cid, "sede_id": sid, "grado": "Tercero", "anio_lectivo": 2026, "consentimiento": False},
    )
    assert r.status_code == 422
    assert r.json()["error"] == "consentimiento_requerido"


async def test_registrar_hijo_y_listarlo_devuelve_apodo(cliente):
    login = (await cliente.post(
        "/v1/cuenta",
        json={"correo": "tia@ejemplo.com", "clave": "clave1234", "nombre": "Tia", "celular": None},
    )).json()
    tok = {"Authorization": f"Bearer {login['token']}"}
    cid = str(derivar("colegio", "2.4"))
    sid = str(derivar("sede", "2.4", "u"))
    creado = await cliente.post(
        "/v1/cuenta/hijos",
        headers=tok,
        json={"apodo": "Pepe", "colegio_id": cid, "sede_id": sid, "grado": "Tercero", "anio_lectivo": 2026, "consentimiento": True},
    )
    assert creado.status_code == 201
    listado = (await cliente.get("/v1/cuenta/hijos", headers=tok)).json()
    assert listado["total"] == 1
    assert listado["hijos"][0]["apodo"] == "Pepe"
    assert listado["hijos"][0]["grado"] == "Tercero"
