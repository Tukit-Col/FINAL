"""Banco de pruebas de Comercio: SQLite en memoria, sin base externa.

Los modelos usan tipos portables a proposito (BigInteger degradado a Integer,
JSONB a JSON, indices parciales con `postgresql_where` y `sqlite_where` a la
vez), asi que el mismo esquema corre aqui y en Postgres.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator

import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from tukit_comercio.modelos import Base, LineaPedido, Pedido


@pytest_asyncio.fixture
async def db() -> AsyncIterator[AsyncSession]:
    motor = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with motor.begin() as conexion:
        await conexion.run_sync(Base.metadata.create_all)
    fabrica = async_sessionmaker(motor, expire_on_commit=False)
    async with fabrica() as sesion:
        yield sesion
    await motor.dispose()


async def crear_pedido(db: AsyncSession, **extra) -> Pedido:
    datos = dict(usuario_id=uuid.uuid4(), total=0, hijos=1, colegios=["Colegio de prueba"])
    datos.update(extra)
    p = Pedido(**datos)
    db.add(p)
    await db.flush()
    return p


async def agregar_linea(db: AsyncSession, pedido: Pedido, precio: int, cantidad: int = 1) -> LineaPedido:
    linea = LineaPedido(
        pedido_id=pedido.id,
        producto_canonico_id=uuid.uuid4(),
        sku="SKU-1",
        nombre="Cuaderno cosido 100 hojas",
        cantidad=cantidad,
        precio_unitario=precio,
    )
    db.add(linea)
    await db.flush()
    return linea
