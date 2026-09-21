"""Motor y sesiones async de SQLAlchemy, compartidos por todos los servicios.

Un servicio no crea su propio `create_async_engine`: pide un `MotorServicio`
a la libreria pasando su nombre. La libreria lee la URL del entorno (ver
`config.py`), arma el motor y la fabrica de sesiones, y expone un context
manager de sesion por peticion.

Por que aqui y no en cada servicio:

- La regla 1 (`test_ningun_servicio_importa_otro_servicio`) obliga a que lo
  compartido viva en `libs/`. El acceso a base es el ejemplo canonico de codigo
  compartido: identico en los cinco servicios salvo el nombre de la base.
- La regla 3 (`test_ningun_servicio_nombra_la_base_de_otro`) falla si el nombre
  de una base aparece en un `.py` de servicio. Como el nombre se deriva aqui,
  desde el argumento, el codigo del servicio nunca lo escribe.

Async porque los modelos ya lo son: el banco de pruebas de identidad y catalogo
usa `create_async_engine` + `AsyncSession`, asi que el runtime real debe hablar
el mismo dialecto para que el mismo modelo corra en la prueba y en produccion.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from .config import url_desde_entorno


@dataclass
class MotorServicio:
    """El motor de un servicio y su fabrica de sesiones.

    Se crea una vez al arrancar el servicio y se comparte. Cada peticion abre y
    cierra su propia sesion con `async with motor.sesion() as db:`.
    """

    servicio: str
    engine: AsyncEngine
    _fabrica: async_sessionmaker[AsyncSession]

    @asynccontextmanager
    async def sesion(self) -> AsyncIterator[AsyncSession]:
        """Una sesion por unidad de trabajo. Hace commit si todo sale bien,
        rollback si algo revienta, y siempre cierra."""
        async with self._fabrica() as db:
            try:
                yield db
                await db.commit()
            except Exception:
                await db.rollback()
                raise

    async def crear_esquema(self, base: type[DeclarativeBase]) -> None:
        """Materializa todas las tablas del servicio en su base.

        Es el mismo `Base.metadata.create_all` que ya usan los conftest, pero
        contra la base real del servicio. Sirve para el arranque de desarrollo
        y para la primera provision; el versionado incremental del esquema
        (migraciones) queda para un paso posterior con Alembic. Ver la deuda
        anotada en el README."""
        async with self.engine.begin() as conexion:
            await conexion.run_sync(base.metadata.create_all)

    async def cerrar(self) -> None:
        await self.engine.dispose()


def crear_motor(servicio: str, *, echo: bool = False) -> MotorServicio:
    """Arma el motor async del servicio a partir de su entorno.

    `servicio` es el nombre canonico ('identidad', 'catalogo', ...). La URL
    sale de `url_desde_entorno`, que la lee del entorno o la deriva de las
    piezas comunes. El servicio no escribe el nombre de su base como literal.
    """
    url = url_desde_entorno(servicio)
    engine = create_async_engine(url, echo=echo, pool_pre_ping=True)
    fabrica = async_sessionmaker(engine, expire_on_commit=False)
    return MotorServicio(servicio=servicio, engine=engine, _fabrica=fabrica)


def sesion_de_prueba(base: type[DeclarativeBase]) -> MotorServicio:
    """Motor SQLite en memoria, para pruebas que quieran el mismo API que el
    runtime real sin levantar Postgres.

    No reemplaza los conftest existentes; es la version reutilizable de su
    fixture, por si un servicio nuevo la quiere sin volver a copiarla."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    fabrica = async_sessionmaker(engine, expire_on_commit=False)
    return MotorServicio(servicio="prueba", engine=engine, _fabrica=fabrica)
