from __future__ import annotations

import uuid
from collections.abc import AsyncIterator, Callable
from datetime import datetime
from typing import Any

import httpx
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from tukit_comercio.api import app
from tukit_comercio.modelos import Base, LineaPedido, Pedido
from tukit_comercio.pasarela import PasarelaFalsa
from tukit_comercio.remoto import IdentidadCaida
from tukit_comun.bd import MotorServicio

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
    def __init__(self, sesiones: dict[str, dict[str, Any]] | None = None, *, caida: bool = False) -> None:
        self.sesiones = sesiones if sesiones is not None else sesiones_por_omision()
        self.caida = caida

    async def sesion(self, token: str) -> dict[str, Any] | None:
        if self.caida:
            raise IdentidadCaida("identidad no responde")
        return self.sesiones.get(token)


def sesiones_por_omision() -> dict[str, dict[str, Any]]:
    def sesion(usuario: str, *roles: str) -> dict[str, Any]:
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


@pytest_asyncio.fixture
async def cliente() -> AsyncIterator[httpx.AsyncClient]:
    from _ayudas_comercio import PRECIO, SKU, CatalogoFalso

    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conexion:
        await conexion.run_sync(Base.metadata.create_all)
    fabrica = async_sessionmaker(engine, expire_on_commit=False)
    app.state.motor = MotorServicio(servicio="prueba", engine=engine, _fabrica=fabrica)
    app.state.pasarela = PasarelaFalsa()
    app.state.catalogo = CatalogoFalso({SKU: PRECIO})
    app.state.identidad = IdentidadFalsa()
    app.state.reloj = None
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://prueba") as http:
        yield http
    app.state.reloj = None
    await engine.dispose()


@pytest.fixture
def reloj() -> Callable[[datetime], None]:

    def fijar(instante: datetime) -> None:
        app.state.reloj = lambda: instante

    yield fijar
    app.state.reloj = None
