from __future__ import annotations

import uuid
from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from tukit_comun.bd import MotorServicio
from tukit_comun.identificadores import derivar
from tukit_identidad.modelos import Base, Colegio, Sede

from tests._ayudas_identidad import cliente_api, motor_sqlite


@pytest.fixture(autouse=True)
def _sin_broker(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("RABBITMQ_URL", raising=False)


@pytest_asyncio.fixture
async def db() -> AsyncIterator[AsyncSession]:
    motor = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with motor.begin() as conexion:
        await conexion.run_sync(Base.metadata.create_all)
    fabrica = async_sessionmaker(motor, expire_on_commit=False)
    async with fabrica() as sesion:
        yield sesion
    await motor.dispose()


@pytest_asyncio.fixture
async def motor() -> AsyncIterator[MotorServicio]:
    async with motor_sqlite() as m:
        yield m


async def _sembrar_colegios(sesion) -> None:
    colegio = Colegio(
        id=derivar("colegio", "2.4"),
        nombre="Colegio San Pedro",
        dane="311001093652",
        logo_url="https://cdn.tukit.co/colegios/san-pedro.png",
        sitio_web="https://sanpedro.edu.co",
        contacto_nombre="Secretaria academica",
        contacto_email="secretaria@sanpedro.edu.co",
        contacto_telefono="+57 1 2345678",
        direccion="Calle 1 # 2-3, Bogota",
    )
    sesion.add(colegio)
    await sesion.flush()
    sesion.add(Sede(id=derivar("sede", "2.4", "Sede unica"), colegio_id=colegio.id, nombre="Sede unica"))
    sesion.add(Colegio(id=derivar("colegio", "9.9"), nombre="Colegio Sin Perfil"))


@pytest.fixture()
async def cliente():
    async with cliente_api(_sembrar_colegios) as http:
        yield http


@pytest.fixture
def id_nuevo():
    return lambda: uuid.uuid4()
