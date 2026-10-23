"""El publicador de bandeja: lleva los eventos de un servicio a RabbitMQ (ADR 0046).

La bandeja de salida sigue siendo la fuente de verdad (ADR 0007): el evento se
escribe en la misma transaccion que el cambio que lo origina, y si el servicio
cae antes de publicarlo, sigue ahi. Lo que cambia es quien la vacia. Con
RabbitMQ, cada servicio productor publica su propia bandeja; ningun consumidor
vuelve a leer la base de otro.

Por pasada:

1. Toma hasta `limite` eventos sin publicar con `FOR UPDATE SKIP LOCKED`, para
   que dos publicadores del mismo servicio no tomen el mismo evento.
2. Publica cada uno con confirmacion del publicador y lo marca publicado solo
   cuando el broker lo confirma.
3. Si una publicacion falla a mitad, guarda lo que ya se confirmo y deja el
   error subir: `bucle_resiliente` espera y la pasada siguiente sigue donde
   iba. Un evento confirmado cuyo commit se pierde se publica otra vez, y eso
   es lo que los consumidores toleran (al menos una vez).

    python -m tukit_catalogo.publicador            # hasta vaciar la bandeja
    python -m tukit_catalogo.publicador --seguir   # bucle

Cada servicio tiene su modulo, que solo llama a `main_publicador` con su nombre.
El publicador lee la base propia del servicio: no cruza ninguna frontera.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Protocol

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncEngine

from .bandeja import bandeja_reflejada
from .broker import url_broker
from .mensajes import Evento, cuerpo, evento_de_fila
from .resiliencia import bucle_resiliente
from .topologia import TOPOLOGIA, Topologia, declarar

log = logging.getLogger(__name__)

# Cada cuanto se mira la bandeja. Corto: es lo que tarda un evento en salir.
INTERVALO_POR_OMISION = 1.0
LIMITE_POR_OMISION = 100


class Destino(Protocol):
    """A donde se publica. `publicar` vuelve solo cuando el broker confirmo."""

    async def publicar(self, evento: Evento) -> None: ...


async def publicar_pendientes(
    motor: AsyncEngine, destino: Destino, *, origen: str, limite: int = LIMITE_POR_OMISION
) -> int:
    """Publica hasta `limite` eventos de la bandeja de `origen`. Devuelve cuantos.

    Si `destino.publicar` falla, los ya confirmados quedan marcados y el error
    sube despues del commit.
    """
    bandeja = bandeja_reflejada()
    publicados = 0
    falla: Exception | None = None
    async with motor.begin() as conexion:
        pendientes = list(
            await conexion.execute(
                select(bandeja)
                .where(bandeja.c.publicado_en.is_(None))
                .order_by(bandeja.c.id)
                .limit(limite)
                .with_for_update(skip_locked=True)
            )
        )
        for fila in pendientes:
            try:
                await destino.publicar(evento_de_fila(fila, origen=origen))
            except Exception as error:
                falla = error
                break
            await conexion.execute(
                update(bandeja).where(bandeja.c.id == fila.id).values(publicado_en=datetime.now(UTC))
            )
            publicados += 1
    if falla is not None:
        log.warning("%s: %d publicados antes de que fallara la publicacion", origen, publicados)
        raise falla
    return publicados


async def vaciar(
    motor: AsyncEngine, destino: Destino, *, origen: str, limite: int = LIMITE_POR_OMISION
) -> int:
    """Publica pasada tras pasada hasta que la bandeja quede sin pendientes."""
    total = 0
    while True:
        publicados = await publicar_pendientes(motor, destino, origen=origen, limite=limite)
        total += publicados
        if publicados < limite:
            return total


@dataclass
class PublicadorAmqp:
    """Publica en el exchange de la topologia, con confirmacion del publicador.

    La conexion se abre en el primer `publicar` y se reusa. `cerrar` la suelta;
    despues de una caida, el bucle la cierra para que la vuelta siguiente abra
    una nueva.
    """

    url: str
    topologia: Topologia = TOPOLOGIA
    _conexion: Any = None
    _exchange: Any = None

    async def _asegurar(self) -> Any:
        if self._exchange is not None:
            return self._exchange
        import aio_pika

        self._conexion = await aio_pika.connect_robust(self.url)
        canal = await self._conexion.channel(publisher_confirms=True)
        self._exchange, _ = await declarar(canal, self.topologia)
        return self._exchange

    async def publicar(self, evento: Evento) -> None:
        import aio_pika

        exchange = await self._asegurar()
        mensaje = aio_pika.Message(
            body=cuerpo(evento),
            content_type="application/json",
            delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
            message_id=evento.message_id,
            type=evento.tipo,
            app_id=evento.origen,
            correlation_id=evento.correlacion_id,
        )
        # Con confirmaciones, `publish` espera el ack del broker y levanta
        # `DeliveryError` si el broker responde nack. `mandatory=False`: un tipo
        # que ninguna cola recibe se descarta, no es un error del productor.
        await exchange.publish(mensaje, routing_key=evento.tipo, mandatory=False)

    async def cerrar(self) -> None:
        if self._conexion is not None:
            conexion, self._conexion, self._exchange = self._conexion, None, None
            await conexion.close()


async def correr(
    origen: str,
    motor: AsyncEngine,
    destino: Any,
    *,
    seguir: bool,
    intervalo: float = INTERVALO_POR_OMISION,
    limite: int = LIMITE_POR_OMISION,
    dormir: Callable[[float], Awaitable[None]] = asyncio.sleep,
) -> int:
    """Una pasada hasta vaciar, o el bucle con `seguir`. Devuelve cuantos publico
    (en el bucle, solo vuelve por un error que no es una caida)."""
    if not seguir:
        return await vaciar(motor, destino, origen=origen, limite=limite)

    async def _vuelta() -> None:
        try:
            publicados = await vaciar(motor, destino, origen=origen, limite=limite)
        except Exception:
            # La conexion puede haber quedado rota: la vuelta siguiente abre otra.
            await destino.cerrar()
            raise
        if publicados:
            log.info("%s: %d eventos publicados", origen, publicados)

    await bucle_resiliente(_vuelta, intervalo=intervalo, proceso=f"{origen}-publicador", dormir=dormir)
    return 0


def main_publicador(origen: str, argv: list[str] | None = None) -> int:
    """La linea de comandos del publicador de `origen`."""
    from .bd import crear_motor
    from .registro import configurar_registro

    analizador = argparse.ArgumentParser(description=f"Publica en RabbitMQ la bandeja de salida de {origen}.")
    analizador.add_argument("--seguir", action="store_true", help="Corre en bucle en vez de una pasada.")
    analizador.add_argument(
        "--intervalo", type=float, default=INTERVALO_POR_OMISION, help="Segundos entre pasadas."
    )
    argumentos = analizador.parse_args(argv)
    configurar_registro(f"{origen}-publicador")

    url = url_broker()
    if not url:
        # Sin broker no hay a donde publicar: los consumidores sondean la bandeja.
        print(f"[publicador-{origen}] falta RABBITMQ_URL; sin broker, los consumidores sondean la bandeja.")
        return 2

    async def _correr() -> int:
        motor = crear_motor(origen)
        destino = PublicadorAmqp(url)
        try:
            return await correr(
                origen, motor.engine, destino, seguir=argumentos.seguir, intervalo=argumentos.intervalo
            )
        finally:
            await destino.cerrar()
            await motor.cerrar()

    publicados = asyncio.run(_correr())
    if not argumentos.seguir:
        print(f"[publicador-{origen}] publicados: {publicados}")
    return 0


__all__ = [
    "Destino",
    "PublicadorAmqp",
    "correr",
    "main_publicador",
    "publicar_pendientes",
    "vaciar",
]
