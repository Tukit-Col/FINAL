"""Banco de pruebas de Identidad: SQLite en memoria, sin base externa.

Los modelos usan tipos portables a proposito, asi que el mismo esquema corre
aqui y en Postgres. Los indices parciales se declaran con `postgresql_where` y
`sqlite_where` a la vez: si en SQLite degradaran a indices totales, la prueba
del historial de asignaciones pasaria por el motivo equivocado.

Las fixtures viven aqui; las funciones de siembra y los montajes de cliente,
en `_ayudas_identidad.py`.
"""

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
    """Las pruebas corren sin RabbitMQ aunque quien las lance tenga `RABBITMQ_URL`.

    La variable cambia el modo del sondeador de colegios (ADR 0046): con ella
    consume su cola en vez de sondear. Las que prueban el modo con broker la
    ponen ellas.
    """
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
    """La base PROPIA de Identidad como `MotorServicio`, con el API del runtime."""
    async with motor_sqlite() as m:
        yield m


async def _sembrar_colegios(sesion) -> None:
    """San Pedro ("2.4") con perfil completo y una sede; "Sin Perfil" ("9.9") sin
    perfil ni sede, para que los campos de perfil serialicen null."""
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
    """Cliente HTTP contra la app con dos colegios sembrados (ver `_sembrar_colegios`).

    Los archivos que necesitan otra siembra definen su propio `cliente`."""
    async with cliente_api(_sembrar_colegios) as http:
        yield http


@pytest.fixture
def id_nuevo():
    return lambda: uuid.uuid4()
