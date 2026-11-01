"""Banco de pruebas de Operacion: SQLite en memoria, sin base externa ni Identidad.

El cliente de Identidad se sustituye por un doble que devuelve un id fijo, para
poder probar el alta de casos sin levantar Identidad. Es la misma tecnica que
Inteligencia usa con su `ClienteCatalogo`.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator

import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from tukit_operacion.modelos import Base


@pytest_asyncio.fixture
async def db() -> AsyncIterator[AsyncSession]:
    motor = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with motor.begin() as conexion:
        await conexion.run_sync(Base.metadata.create_all)
    fabrica = async_sessionmaker(motor, expire_on_commit=False)
    async with fabrica() as sesion:
        yield sesion
    await motor.dispose()


class IdentidadFalsa:
    """Devuelve siempre el mismo id sin salir a la red. Registra que le pidieron."""

    def __init__(self, usuario_id: str | None = None) -> None:
        self.usuario_id = usuario_id or str(uuid.uuid4())
        self.llamadas: list[tuple[str, str | None]] = []

    async def resolver_contacto(self, correo: str, celular: str | None = None) -> str | None:
        self.llamadas.append((correo, celular))
        return self.usuario_id


ACUDIENTE = "22222222-2222-5222-8222-222222222222"
OTRO_ACUDIENTE = "33333333-3333-5333-8333-333333333333"
TOKEN_ACUDIENTE = "token-acudiente"
TOKEN_OTRO = "token-otro"


class IdentidadConSesiones(IdentidadFalsa):
    """Como `IdentidadFalsa`, y ademas valida tokens de sesion (token -> usuario)."""

    def __init__(self, caida: bool = False) -> None:
        super().__init__()
        self.caida = caida
        self.sesiones = {
            TOKEN_ACUDIENTE: {"usuario_id": ACUDIENTE, "correo": "a@x.com", "roles": []},
            TOKEN_OTRO: {"usuario_id": OTRO_ACUDIENTE, "correo": "b@x.com", "roles": []},
        }

    async def sesion(self, token: str):
        from tukit_operacion.remoto import IdentidadCaida

        if self.caida:
            raise IdentidadCaida("no responde")
        return self.sesiones.get(token)
