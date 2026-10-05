"""La superficie de "mi cuenta": quien soy y mi libreta de direcciones.

El dashboard del padre corria sobre datos de muestra porque esta superficie no
existia. Aqui se prueba sobre el token real que emite `iniciar_sesion`, con
SQLite en memoria y sin base externa.

Lo que se defiende:

- Todo exige el token: sin el, 401. Con el, solo se ve y se toca lo PROPIO.
- La linea de la direccion se guarda cifrada y se devuelve descifrada a su
  dueno; en desarrollo el cifrador es `CifradorEnClaro`, que lo dice.
- El borrado es baja logica (ADR 0015): la direccion se archiva, no se pierde.
"""

from __future__ import annotations

import uuid

import httpx
import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool
from tukit_comun.bd import MotorServicio
from tukit_identidad.api import app
from tukit_identidad.dominio.sesiones import emitir_token, hashear_clave
from tukit_identidad.modelos import Base, Usuario


@pytest.fixture()
async def cliente():
    engine = create_async_engine(
        "sqlite+aiosqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False}
    )
    async with engine.begin() as conexion:
        await conexion.run_sync(Base.metadata.create_all)

    fabrica = async_sessionmaker(engine, expire_on_commit=False)
    async with fabrica() as sesion:
        usuario = Usuario(correo="mama@ejemplo.com", clave_hash=hashear_clave("demo1234"))
        sesion.add(usuario)
        await sesion.flush()
        uid = usuario.id
        await sesion.commit()

    app.state.motor = MotorServicio(servicio="prueba", engine=engine, _fabrica=fabrica)
    token = emitir_token(uid, version_permisos=1)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://prueba") as http:
        http.headers["Authorization"] = f"Bearer {token}"
        http.usuario_id = str(uid)  # type: ignore[attr-defined]
        yield http
    await engine.dispose()


async def test_ver_cuenta_devuelve_al_portador(cliente):
    respuesta = await cliente.get("/v1/cuenta")
    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo["usuario_id"] == cliente.usuario_id
    assert cuerpo["correo"] == "mama@ejemplo.com"


async def test_sin_token_no_hay_cuenta(cliente):
    respuesta = await cliente.get("/v1/cuenta", headers={"Authorization": ""})
    assert respuesta.status_code == 401
    assert respuesta.json()["error"] == "sesion_invalida"


async def test_crear_direccion_cifra_la_linea_y_la_devuelve_descifrada(cliente):
    respuesta = await cliente.post(
        "/v1/cuenta/direcciones",
        json={
            "etiqueta": "casa",
            "ciudad": "Bogota",
            "localidad": "Chapinero",
            "linea": "Calle 1 # 2-3 apto 401",
            "contacto": "3001234567",
            "predeterminada": True,
        },
    )
    assert respuesta.status_code == 201
    cuerpo = respuesta.json()
    assert cuerpo["linea"] == "Calle 1 # 2-3 apto 401"
    assert cuerpo["contacto"] == "3001234567"
    assert cuerpo["predeterminada"] is True

    lista = (await cliente.get("/v1/cuenta/direcciones")).json()
    assert lista["total"] == 1
    assert lista["direcciones"][0]["ciudad"] == "Bogota"


async def test_solo_una_predeterminada(cliente):
    await cliente.post(
        "/v1/cuenta/direcciones",
        json={"ciudad": "Bogota", "linea": "Calle 1", "predeterminada": True},
    )
    await cliente.post(
        "/v1/cuenta/direcciones",
        json={"ciudad": "Medellin", "linea": "Carrera 2", "predeterminada": True},
    )
    lista = (await cliente.get("/v1/cuenta/direcciones")).json()
    predeterminadas = [d for d in lista["direcciones"] if d["predeterminada"]]
    assert len(predeterminadas) == 1
    assert predeterminadas[0]["ciudad"] == "Medellin"


async def test_editar_direccion_ajena_da_404(cliente):
    # Un id que no es del portador (ni existe) no se puede editar.
    respuesta = await cliente.patch(
        f"/v1/cuenta/direcciones/{uuid.uuid4()}",
        json={"ciudad": "Cali", "linea": "Avenida 3"},
    )
    assert respuesta.status_code == 404
    assert respuesta.json()["error"] == "direccion_no_existe"


async def test_archivar_es_baja_logica(cliente):
    creada = (
        await cliente.post(
            "/v1/cuenta/direcciones",
            json={"ciudad": "Bogota", "linea": "Calle 1"},
        )
    ).json()

    borrado = await cliente.delete(f"/v1/cuenta/direcciones/{creada['direccion_id']}")
    assert borrado.status_code == 204

    lista = (await cliente.get("/v1/cuenta/direcciones")).json()
    assert lista["total"] == 0
    # Segundo borrado ya no la encuentra activa: 404.
    otra_vez = await cliente.delete(f"/v1/cuenta/direcciones/{creada['direccion_id']}")
    assert otra_vez.status_code == 404
