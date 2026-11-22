"""Drenador compartido de la bandeja de salida (outbox).

Decisiones:
- La bandeja es la fuente de verdad de los eventos: se escribe en la misma transaccion que el
  cambio que los origina y un drenador la lee despues (`SELECT ... FOR UPDATE SKIP LOCKED`).
- Cada llamador aporta solo `manejar(conexion, fila) -> Resultado`: HECHO marca publicado y
  cuenta, OMITIR marca publicado sin contar, REINTENTAR sube `intentos` y deja el evento pendiente.
- Antes de llamar a `manejar` se vuelve a vincular el `correlacion_id` del evento, para que los
  registros del consumidor sigan a la peticion que lo origino.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from enum import Enum, auto
from typing import Any, Protocol, runtime_checkable

from sqlalchemy import (
    BigInteger,
    Column,
    DateTime,
    Integer,
    MetaData,
    String,
    Table,
    Uuid,
    select,
    update,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncEngine
from sqlalchemy.types import JSON

from .http import fijar_correlacion, id_de_correlacion, reset_correlacion

_CARGA = JSON().with_variant(JSONB(), "postgresql")


class Resultado(Enum):
    HECHO = auto()
    OMITIR = auto()
    REINTENTAR = auto()


@runtime_checkable
class Sink(Protocol):
    async def publicar(self, fila: Any) -> None: ...


def bandeja_reflejada(metadatos: MetaData | None = None) -> Table:
    return Table(
        "bandeja_salida",
        metadatos if metadatos is not None else MetaData(),
        Column("id", BigInteger, primary_key=True, autoincrement=True),
        Column("tipo", String(128)),
        Column("agregado_tipo", String(64)),
        Column("agregado_id", Uuid(as_uuid=True)),
        Column("carga", _CARGA),
        Column("publicado_en", DateTime(timezone=True)),
        Column("intentos", Integer, default=0),
    )


def con_correlacion(carga: dict[str, Any]) -> dict[str, Any]:
    cid = id_de_correlacion()
    return {**carga, "correlacion_id": cid} if cid else carga


Manejador = Callable[[Any, Any], Awaitable[Resultado]]


async def drenar(
    motor: AsyncEngine,
    manejar: Manejador,
    *,
    tipo: str | None = None,
    limite: int = 100,
    sink: Sink | None = None,
) -> int:
    bandeja = bandeja_reflejada()
    entregados = 0
    async with motor.begin() as conexion:
        condicion: Any = bandeja.c.publicado_en.is_(None)
        if tipo is not None:
            condicion = condicion & (bandeja.c.tipo == tipo)
        pendientes = list(
            await conexion.execute(
                select(bandeja)
                .where(condicion)
                .order_by(bandeja.c.id)
                .limit(limite)
                .with_for_update(skip_locked=True)
            )
        )
        for fila in pendientes:
            carga = fila.carga or {}
            token = fijar_correlacion(carga.get("correlacion_id") if isinstance(carga, dict) else None)
            try:
                resultado = await manejar(conexion, fila)
            finally:
                reset_correlacion(token)

            if resultado is Resultado.REINTENTAR:
                await conexion.execute(
                    update(bandeja).where(bandeja.c.id == fila.id).values(intentos=(fila.intentos or 0) + 1)
                )
                continue
            await conexion.execute(
                update(bandeja).where(bandeja.c.id == fila.id).values(publicado_en=datetime.now(UTC))
            )
            if resultado is Resultado.HECHO:
                if sink is not None:
                    await sink.publicar(fila)
                entregados += 1
    return entregados
