from __future__ import annotations

import asyncio

from sqlalchemy.orm import DeclarativeBase

from .bd import crear_motor


def materializar(servicio: str, base: type[DeclarativeBase]) -> None:

    async def _correr() -> int:
        motor = crear_motor(servicio)
        try:
            await motor.crear_esquema(base)
            return len(base.metadata.tables)
        finally:
            await motor.cerrar()

    n = asyncio.run(_correr())
    print(f"[{servicio}] esquema materializado: {n} tablas en tukit_{servicio}")
