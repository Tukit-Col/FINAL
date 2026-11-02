"""Banco de pruebas de Operacion: SQLite en memoria, sin base externa ni Identidad.

El cliente de Identidad se sustituye por un doble que devuelve un id fijo, para
poder probar el alta de casos sin levantar Identidad. Es la misma tecnica que
Inteligencia usa con su `ClienteCatalogo`.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from tukit_operacion.modelos import Base


@pytest.fixture(autouse=True)
def _sin_broker(monkeypatch: pytest.MonkeyPatch) -> None:
    """Las pruebas corren sin RabbitMQ aunque quien las lance tenga `RABBITMQ_URL`.

    La variable cambia el modo del repartidor (ADR 0046): con ella consume su
    cola en vez de sondear. Las que prueban el modo con broker la ponen ellas.
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


OPERADOR = "44444444-4444-5444-8444-444444444444"
ADMIN = "55555555-5555-5555-8555-555555555555"
ACUDIENTE = "22222222-2222-5222-8222-222222222222"
TOKEN_OPERADOR = "token-operador"
TOKEN_ADMIN = "token-admin"
TOKEN_ACUDIENTE = "token-acudiente"


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _sesion(usuario: str, rol: str) -> dict:
    return {"usuario_id": usuario, "correo": f"{rol}@tukit.test", "roles": [{"rol": rol, "ambito": None}]}


class IdentidadFalsa:
    """Devuelve siempre el mismo id sin salir a la red. Registra que le pidieron.

    Tambien valida sesiones (token -> sesion) para la puerta de staff; `caida=True`
    imita a Identidad sin responder."""

    def __init__(self, usuario_id: str | None = None, *, caida: bool = False) -> None:
        self.usuario_id = usuario_id or str(uuid.uuid4())
        self.llamadas: list[tuple[str, str | None]] = []
        self.caida = caida
        self.sesiones = {
            TOKEN_OPERADOR: _sesion(OPERADOR, "operador"),
            TOKEN_ADMIN: _sesion(ADMIN, "admin"),
            TOKEN_ACUDIENTE: _sesion(ACUDIENTE, "acudiente"),
        }

    async def sesion(self, token: str):
        if self.caida:
            from tukit_operacion.remoto import IdentidadCaida

            raise IdentidadCaida("identidad no responde")
        return self.sesiones.get(token)

    async def resolver_contacto(self, correo: str, celular: str | None = None) -> str | None:
        self.llamadas.append((correo, celular))
        return self.usuario_id
