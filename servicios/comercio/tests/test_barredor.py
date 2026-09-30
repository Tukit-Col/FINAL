"""El barredor de reservas vencidas contra base (C1 de la saga, ADR 0023).

La decision pura ya se prueba en `test_dominio_saga.py`. Aqui se fija el I/O:
que el join reserva↔pedido + escritura efectivamente libere la reserva vieja de
un pedido sin pagar y cancele ese pedido, sin tocar las recientes ni las ya
pagadas. SQLite en memoria; el `SKIP LOCKED` es no-op aqui (Postgres-only), asi
que se verifica el efecto observable, no la concurrencia.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine
from tukit_comercio import barredor
from tukit_comercio.modelos import Base, EstadoPedido, Pedido, ReservaInventario

AHORA = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)


@pytest_asyncio.fixture
async def motor():
    m = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with m.begin() as conexion:
        await conexion.run_sync(Base.metadata.create_all)
    yield m
    await m.dispose()


async def _pedido_con_reserva(motor, *, edad_min: float, pedido_estado: str, reserva_estado: str):
    pid = uuid.uuid4()
    async with motor.begin() as conexion:
        await conexion.execute(
            Pedido.__table__.insert().values(
                id=pid,
                usuario_id=uuid.uuid4(),
                total=0,
                hijos=1,
                colegios=["C"],
                estado=pedido_estado,
            )
        )
        await conexion.execute(
            ReservaInventario.__table__.insert().values(
                id=uuid.uuid4(),
                pedido_id=pid,
                producto_canonico_id=uuid.uuid4(),
                cantidad=1,
                estado=reserva_estado,
                creado_en=AHORA - timedelta(minutes=edad_min),
            )
        )
    return pid


async def _estados(motor, pid):
    async with motor.begin() as conexion:
        pedido = await conexion.scalar(select(Pedido.__table__.c.estado).where(Pedido.__table__.c.id == pid))
        reserva = await conexion.scalar(
            select(ReservaInventario.__table__.c.estado).where(ReservaInventario.__table__.c.pedido_id == pid)
        )
    return pedido, reserva


async def test_libera_reserva_vieja_sin_pagar_y_cancela_el_pedido(motor):
    pid = await _pedido_con_reserva(
        motor, edad_min=31, pedido_estado="pendiente_pago", reserva_estado="activa"
    )

    n = await barredor.pasada(motor, ahora=AHORA, limite=100)

    assert n == 1
    assert await _estados(motor, pid) == (EstadoPedido.CANCELADO.value, "liberada")


async def test_no_toca_reserva_reciente(motor):
    pid = await _pedido_con_reserva(
        motor, edad_min=29, pedido_estado="pendiente_pago", reserva_estado="activa"
    )

    assert await barredor.pasada(motor, ahora=AHORA) == 0
    assert await _estados(motor, pid) == ("pendiente_pago", "activa")


async def test_no_toca_reserva_de_pedido_pagado(motor):
    pid = await _pedido_con_reserva(motor, edad_min=99, pedido_estado="pagado", reserva_estado="activa")

    assert await barredor.pasada(motor, ahora=AHORA) == 0
    assert await _estados(motor, pid) == ("pagado", "activa")
