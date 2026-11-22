from __future__ import annotations

import uuid
from collections.abc import AsyncIterator

import httpx
import pytest_asyncio
from conftest import TOKEN_ACUDIENTE, TOKEN_OPERADOR, TOKEN_OTRO, IdentidadConSesiones
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from tukit_comun.bd import MotorServicio
from tukit_operacion.api import app
from tukit_operacion.modelos import Base


@pytest_asyncio.fixture
async def cliente() -> AsyncIterator[httpx.AsyncClient]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conexion:
        await conexion.run_sync(Base.metadata.create_all)
    fabrica = async_sessionmaker(engine, expire_on_commit=False)
    app.state.motor = MotorServicio(servicio="prueba", engine=engine, _fabrica=fabrica)
    app.state.identidad = IdentidadConSesiones()
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://prueba") as http:
        yield http
    await engine.dispose()


def _h(token):
    return {"Authorization": f"Bearer {token}"}


def _caso(**kw):
    cuerpo = {"categoria": "reclamo", "asunto": "Me llegó incompleto", "descripcion": "Faltaron dos cuadernos."}
    cuerpo.update(kw)
    return cuerpo


async def _abrir(cliente, token=TOKEN_ACUDIENTE, **kw) -> str:
    respuesta = await cliente.post("/v1/operacion/mis-casos", json=_caso(**kw), headers=_h(token))
    assert respuesta.status_code == 201
    return respuesta.json()["caso_id"]


async def test_el_caso_queda_a_nombre_de_la_sesion_y_solo_su_dueno_lo_lista(cliente):
    mio = await _abrir(cliente)
    await _abrir(cliente, token=TOKEN_OTRO, asunto="Otro asunto")

    mios = (await cliente.get("/v1/operacion/mis-casos", headers=_h(TOKEN_ACUDIENTE))).json()
    assert [c["caso_id"] for c in mios["casos"]] == [mio]
    assert mios["casos"][0]["estado"] == "abierto"
    assert mios["casos"][0]["vence_en"]

    del_otro = (await cliente.get("/v1/operacion/mis-casos", headers=_h(TOKEN_OTRO))).json()
    assert del_otro["total"] == 1 and del_otro["casos"][0]["caso_id"] != mio


async def test_un_caso_ajeno_es_403_al_leerlo_y_al_comentarlo(cliente):
    caso_id = await _abrir(cliente)

    leer = await cliente.get(f"/v1/operacion/mis-casos/{caso_id}", headers=_h(TOKEN_OTRO))
    assert leer.status_code == 403
    assert leer.json()["error"] == "caso_ajeno"

    comentar = await cliente.post(
        f"/v1/operacion/mis-casos/{caso_id}/comentarios", json={"texto": "intruso"}, headers=_h(TOKEN_OTRO)
    )
    assert comentar.status_code == 403
    detalle = (await cliente.get(f"/v1/operacion/mis-casos/{caso_id}", headers=_h(TOKEN_ACUDIENTE))).json()
    assert detalle["comentarios"] == []


async def test_el_dueno_sigue_su_caso_y_agrega_mensajes(cliente):
    caso_id = await _abrir(cliente)
    for texto in ("Adjunto la foto del paquete.", "Sigo esperando respuesta."):
        r = await cliente.post(
            f"/v1/operacion/mis-casos/{caso_id}/comentarios", json={"texto": texto}, headers=_h(TOKEN_ACUDIENTE)
        )
        assert r.status_code == 201
    detalle = (await cliente.get(f"/v1/operacion/mis-casos/{caso_id}", headers=_h(TOKEN_ACUDIENTE))).json()
    assert [c["texto"] for c in detalle["comentarios"]] == [
        "Adjunto la foto del paquete.",
        "Sigo esperando respuesta.",
    ]
    assert detalle["descripcion"] == "Faltaron dos cuadernos."


async def test_sin_sesion_es_401_y_con_identidad_caida_es_503(cliente):
    assert (await cliente.get("/v1/operacion/mis-casos")).status_code == 401
    assert (await cliente.post("/v1/operacion/mis-casos", json=_caso())).status_code == 401
    assert (await cliente.get("/v1/operacion/mis-casos", headers=_h("token-que-no-existe"))).status_code == 401

    app.state.identidad = IdentidadConSesiones(caida=True)
    caida = await cliente.get("/v1/operacion/mis-casos", headers=_h(TOKEN_ACUDIENTE))
    assert caida.status_code == 503


async def test_inexistente_404_y_categoria_de_sistema_422(cliente):
    assert (
        await cliente.get(f"/v1/operacion/mis-casos/{uuid.uuid4()}", headers=_h(TOKEN_ACUDIENTE))
    ).status_code == 404
    r = await cliente.post("/v1/operacion/mis-casos", json=_caso(categoria="mapeo_lista"), headers=_h(TOKEN_ACUDIENTE))
    assert r.status_code == 422 and r.json()["error"] == "categoria_no_permitida"


async def test_un_caso_puede_apuntar_a_un_pedido(cliente):
    pedido = str(uuid.uuid4())
    caso_id = await _abrir(cliente, pedido_id=pedido)
    detalle = (await cliente.get(f"/v1/operacion/mis-casos/{caso_id}", headers=_h(TOKEN_ACUDIENTE))).json()
    assert detalle["pedido_id"] == pedido
    malo = await cliente.post("/v1/operacion/mis-casos", json=_caso(pedido_id="no-es-uuid"), headers=_h(TOKEN_ACUDIENTE))
    assert malo.status_code == 422


async def test_el_dueno_y_el_staff_comparten_la_conversacion_por_puertas_distintas(cliente):
    caso_id = await _abrir(cliente)
    assert (await cliente.get("/v1/operacion/casos", headers=_h(TOKEN_ACUDIENTE))).status_code == 403
    assert (await cliente.get(f"/v1/operacion/casos/{caso_id}", headers=_h(TOKEN_ACUDIENTE))).status_code == 403

    r = await cliente.post(
        f"/v1/operacion/mis-casos/{caso_id}/comentarios", json={"texto": "Hola?"}, headers=_h(TOKEN_ACUDIENTE)
    )
    assert r.status_code == 201
    staff = (await cliente.get(f"/v1/operacion/casos/{caso_id}", headers=_h(TOKEN_OPERADOR))).json()
    assert [e["tipo"] for e in staff["eventos"]] == ["comentario_acudiente"]

    r = await cliente.post(
        f"/v1/operacion/casos/{caso_id}/responder", json={"texto": "Ya lo revisamos."}, headers=_h(TOKEN_OPERADOR)
    )
    assert r.status_code in (200, 201)
    mio = (await cliente.get(f"/v1/operacion/mis-casos/{caso_id}", headers=_h(TOKEN_ACUDIENTE))).json()
    assert [(c["autor"], c["texto"]) for c in mio["comentarios"]] == [
        ("acudiente", "Hola?"),
        ("equipo", "Ya lo revisamos."),
    ]
    assert all("actor_id" not in c for c in mio["comentarios"])
