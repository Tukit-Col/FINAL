"""Banco de pruebas de Comercio: SQLite en memoria, sin base externa.

Los modelos usan tipos portables a proposito (BigInteger degradado a Integer,
JSONB a JSON, indices parciales con `postgresql_where` y `sqlite_where` a la
vez), asi que el mismo esquema corre aqui y en Postgres.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from typing import Any

import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from tukit_comercio.modelos import Base, LineaPedido, Pedido
from tukit_comercio.remoto import IdentidadCaida

# Usuarios y tokens fijos de las pruebas HTTP. El acudiente es el mismo
# `USUARIO` de las ordenes de `test_checkout`, para que sus pedidos sean "suyos".
ACUDIENTE = "22222222-2222-5222-8222-222222222222"
OTRO_ACUDIENTE = "33333333-3333-5333-8333-333333333333"
OPERADOR = "44444444-4444-5444-8444-444444444444"
ADMIN = "55555555-5555-5555-8555-555555555555"
TOKEN_ACUDIENTE = "token-acudiente"
TOKEN_OTRO = "token-otro"
TOKEN_OPERADOR = "token-operador"
TOKEN_ADMIN = "token-admin"


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


class IdentidadFalsa:
    """Doble del cliente de Identidad: token -> sesion, sin red.

    Imita `GET /v1/sesiones/actual`: un token desconocido devuelve `None` (el
    401 de Identidad) y `caida=True` lanza `IdentidadCaida`, que es lo que el
    cliente real levanta si Identidad no responde.
    """

    def __init__(self, sesiones: dict[str, dict[str, Any]] | None = None, *, caida: bool = False) -> None:
        self.sesiones = sesiones if sesiones is not None else sesiones_por_omision()
        self.caida = caida

    async def sesion(self, token: str) -> dict[str, Any] | None:
        if self.caida:
            raise IdentidadCaida("identidad no responde")
        return self.sesiones.get(token)


def sesiones_por_omision() -> dict[str, dict[str, Any]]:
    def sesion(usuario: str, *roles: str) -> dict[str, Any]:
        # Como `GET /v1/sesiones/actual`: la sesion trae el correo del portador.
        return {
            "usuario_id": usuario,
            "correo": f"{roles[0]}-{usuario[:8]}@tukit.test",
            "roles": [{"rol": r, "ambito": None} for r in roles],
        }

    return {
        TOKEN_ACUDIENTE: sesion(ACUDIENTE, "acudiente"),
        TOKEN_OTRO: sesion(OTRO_ACUDIENTE, "acudiente"),
        TOKEN_OPERADOR: sesion(OPERADOR, "operador"),
        TOKEN_ADMIN: sesion(ADMIN, "admin"),
    }


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
