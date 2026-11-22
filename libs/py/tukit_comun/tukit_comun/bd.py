"""Motor y sesiones async de SQLAlchemy, compartidos por todos los servicios.

Decisiones:
- Un servicio no crea su propio motor: pide un `MotorServicio` a la libreria con su nombre y la
  libreria deriva la base. Asi el codigo de un servicio nunca escribe el nombre de una base
  (reglas 1 y 3 de `arquitectura/test_fronteras.py`).
- Todo es async porque los modelos y las pruebas ya lo son.
- Las extensiones de Postgres (`vector` y `pg_trgm`, las dos mitades de la busqueda hibrida) se
  piden aqui con `IF NOT EXISTS` antes de crear tablas.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from .config import url_desde_entorno

EXTENSIONES: tuple[str, ...] = ("vector", "pg_trgm")


@dataclass
class MotorServicio:
    servicio: str
    engine: AsyncEngine
    _fabrica: async_sessionmaker[AsyncSession]

    @asynccontextmanager
    async def sesion(self) -> AsyncIterator[AsyncSession]:
        async with self._fabrica() as db:
            try:
                yield db
                await db.commit()
            except Exception:
                await db.rollback()
                raise

    async def asegurar_extensiones(self) -> None:
        if self.engine.dialect.name != "postgresql":
            return
        async with self.engine.begin() as conexion:
            for extension in EXTENSIONES:
                await conexion.execute(text(f'CREATE EXTENSION IF NOT EXISTS "{extension}"'))

    async def crear_esquema(self, base: type[DeclarativeBase]) -> None:
        await self.asegurar_extensiones()
        async with self.engine.begin() as conexion:
            await conexion.run_sync(base.metadata.create_all)

    async def cerrar(self) -> None:
        await self.engine.dispose()


def crear_motor(servicio: str, *, echo: bool = False) -> MotorServicio:
    url = url_desde_entorno(servicio)
    engine = create_async_engine(url, echo=echo, pool_pre_ping=True)
    fabrica = async_sessionmaker(engine, expire_on_commit=False)
    return MotorServicio(servicio=servicio, engine=engine, _fabrica=fabrica)


def sesion_de_prueba(base: type[DeclarativeBase]) -> MotorServicio:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    fabrica = async_sessionmaker(engine, expire_on_commit=False)
    return MotorServicio(servicio="prueba", engine=engine, _fabrica=fabrica)
