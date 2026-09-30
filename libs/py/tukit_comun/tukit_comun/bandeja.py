"""Drenador compartido de la bandeja de salida (outbox), ADR 0022.

La bandeja de salida es la fuente de verdad de los eventos: se escribe en la
MISMA transaccion que el cambio que lo origina (patron outbox, ADR 0007), y un
drenador la lee despues y entrega el evento a donde tenga que ir. Esa lectura
—reflejar la tabla, `SELECT ... FOR UPDATE SKIP LOCKED` sobre los no-publicados,
iterar, marcar publicado o subir intentos— estaba TRIPLICADA en el repartidor de
operacion y en los pollers de identidad e inteligencia. Aqui vive una sola vez.

Cada llamador aporta solo su `manejar(conexion, fila) -> Resultado`:

- `HECHO`      -> marca el evento publicado y lo cuenta.
- `OMITIR`     -> marca publicado pero no lo cuenta (un tipo que no me toca; no
                  hay que reprocesarlo cada pasada).
- `REINTENTAR` -> sube `intentos` y lo deja pendiente (fallo transitorio de
                  entrega; se reintenta en la proxima pasada).

Antes de llamar a `manejar`, el drenador RE-VINCULA el `correlacion_id` que viajo
en la carga del evento (§A.6): asi el trabajo disparado por un evento drenado
recupera el hilo de la peticion original en logs y trazas. Es tambien el unico
punto natural para el span OTel del consumo (ADR 0021).

`SKIP LOCKED` permite que varias replicas del drenador corran a la vez sin tomar
el mismo evento; el `begin()` envuelve la pasada en una transaccion, asi que las
filas quedan bloqueadas hasta el commit.
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

# `carga` es JSON portable: nativo JSONB en Postgres, JSON en SQLite (mismo
# criterio que los `Texto` de los modelos). El drenador solo lee la bandeja
# ajena reflejada, nunca importa el modelo del otro servicio (regla 1).
_CARGA = JSON().with_variant(JSONB(), "postgresql")


class Resultado(Enum):
    """Lo que `manejar` le dice al drenador que haga con el evento."""

    HECHO = auto()
    OMITIR = auto()
    REINTENTAR = auto()


@runtime_checkable
class Sink(Protocol):
    """La costura de entrega al broker (ADR 0022): un destino intercambiable.

    Es ADITIVO al `manejar`, no lo reemplaza: el outbox sigue siendo la fuente de
    verdad y `manejar` sigue notificando; el sink, si se inyecta, recibe ademas
    cada evento HECHO para publicarlo al broker (push/fan-out/replay). Sin sink
    (el default) el comportamiento es identico al de hoy. `BrokerSink` vive en
    `tukit_comun.broker` para no arrastrar `aio-pika` a quien no lo use."""

    async def publicar(self, fila: Any) -> None: ...


def bandeja_reflejada(metadatos: MetaData | None = None) -> Table:
    """La `bandeja_salida` con solo las columnas comunes a todos los servicios.

    Se declara, no se importa: la forma (`tipo, agregado_tipo, agregado_id,
    carga, publicado_en, intentos`) es identica en Inteligencia, Comercio,
    Catalogo e Identidad a proposito. Un `MetaData` propio por llamada evita
    colisiones si se reflejan dos bandejas en el mismo proceso.
    """
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
    """Estampa el `correlacion_id` de la peticion en curso en la carga del evento.

    El productor lo llama al armar la `carga` que inserta en la bandeja; el
    drenador lo re-vincula al consumir (arriba). Es el otro extremo del hilo de
    correlacion a traves del outbox (§A.6). Si no hay peticion (un poller que
    origina un evento), no anexa nada —no se inventa un id— y el consumo queda
    sin correlacion, que es honesto: nadie lo pidio por HTTP."""
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
    """Drena hasta `limite` eventos no publicados y devuelve cuantos dieron `HECHO`.

    Args:
        motor: Motor a la base DUEÑA de la bandeja (puede ser una base ajena: es
            la unica excepcion outbox declarada, ver los pollers).
        manejar: Corrutina `(conexion, fila) -> Resultado` que entrega el evento.
        tipo: Si se da, solo se drenan eventos de ese `tipo`; si no, todos.
        limite: Cota de eventos por pasada.
        sink: Destino de broker OPCIONAL (ADR 0022). Si se da, cada evento HECHO
            se publica ademas al broker; el outbox sigue siendo la fuente de
            verdad. `None` (el default) = comportamiento de hoy, sin broker.

    Returns:
        Cuantos eventos se entregaron con exito (`Resultado.HECHO`).
    """
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
