"""GET /v1/comercio/pedidos-pagados: el cruce mínimo para otros servicios.

Solo los pedidos en un estado confirmado (`_ESTADOS_CONFIRMADOS`) y con
`trabajo_id`, con su `{trabajo_id, usuario_id, estado}` y sin PII. Se prueba con
`ASGITransport`, sin levantar uvicorn ni salir a la red.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator

import httpx
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from tukit_comercio.api import app
from tukit_comercio.modelos import Base, EstadoPedido, Pedido
from tukit_comun.bd import MotorServicio


@pytest_asyncio.fixture
async def entorno() -> AsyncIterator[tuple[httpx.AsyncClient, MotorServicio]]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conexion:
        await conexion.run_sync(Base.metadata.create_all)
    fabrica = async_sessionmaker(engine, expire_on_commit=False)
    motor = MotorServicio(servicio="prueba", engine=engine, _fabrica=fabrica)
    app.state.motor = motor
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://prueba") as http:
        yield http, motor
    await engine.dispose()


async def _sembrar(motor: MotorServicio, *, estado: str, trabajo_id: uuid.UUID | None) -> Pedido:
    async with motor.sesion() as db:
        pedido = Pedido(
            usuario_id=uuid.uuid4(),
            trabajo_id=trabajo_id,
            estado=estado,
            total=0,
            hijos=1,
            colegios=[],
        )
        db.add(pedido)
        await db.commit()
    return pedido


async def test_solo_estados_confirmados(entorno):
    http, motor = entorno
    t_pagado = uuid.uuid4()
    t_entregado = uuid.uuid4()
    await _sembrar(motor, estado=EstadoPedido.PAGADO.value, trabajo_id=t_pagado)
    await _sembrar(motor, estado=EstadoPedido.ENTREGADO.value, trabajo_id=t_entregado)
    # No confirmados: no deben aparecer.
    await _sembrar(motor, estado=EstadoPedido.PENDIENTE_PAGO.value, trabajo_id=uuid.uuid4())
    await _sembrar(motor, estado=EstadoPedido.CANCELADO.value, trabajo_id=uuid.uuid4())

    respuesta = await http.get("/v1/comercio/pedidos-pagados")
    assert respuesta.status_code == 200
    trabajos = {p["trabajo_id"] for p in respuesta.json()["pedidos"]}
    assert trabajos == {str(t_pagado), str(t_entregado)}


async def test_omite_pedidos_sin_trabajo(entorno):
    http, motor = entorno
    # Un pago sin trabajo (compra fuera del flujo de kit) no sirve para el cruce.
    await _sembrar(motor, estado=EstadoPedido.PAGADO.value, trabajo_id=None)
    con_trabajo = await _sembrar(motor, estado=EstadoPedido.PAGADO.value, trabajo_id=uuid.uuid4())

    respuesta = await http.get("/v1/comercio/pedidos-pagados")
    pedidos = respuesta.json()["pedidos"]
    assert [p["trabajo_id"] for p in pedidos] == [str(con_trabajo.trabajo_id)]
    # Trae el id del padre para el cruce, y nada de PII.
    assert pedidos[0]["usuario_id"] == str(con_trabajo.usuario_id)
    assert set(pedidos[0].keys()) == {"trabajo_id", "usuario_id", "estado"}
