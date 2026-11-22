"""Publicacion de los eventos del outbox a RabbitMQ (`BrokerSink`).

Decisiones:
- El outbox sigue siendo la fuente de verdad; el broker solo mejora la entrega (fan-out,
  reintentos, descartados). El tipo del evento es la routing key.
- Sin `RABBITMQ_URL`, `sink_desde_entorno()` devuelve `None` y todo funciona sondeando las bases.
- `aio-pika` se importa dentro de las funciones para que importar el modulo no exija el broker.
- `python -m tukit_comun.broker` dice si el broker responde; `make arriba` lo usa para elegir modo.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlsplit, urlunsplit

EXCHANGE = "tukit.eventos"


def url_broker() -> str | None:
    return os.environ.get("RABBITMQ_URL") or None


@dataclass
class BrokerSink:

    url: str
    exchange: str = EXCHANGE
    _conexion: Any = None
    _canal: Any = None
    _exchange: Any = None

    async def _asegurar(self) -> Any:
        if self._exchange is not None:
            return self._exchange
        import aio_pika

        self._conexion = await aio_pika.connect_robust(self.url)
        self._canal = await self._conexion.channel()
        self._exchange = await self._canal.declare_exchange(
            self.exchange, aio_pika.ExchangeType.TOPIC, durable=True
        )
        return self._exchange

    async def publicar(self, fila: Any) -> None:
        import aio_pika

        exchange = await self._asegurar()
        cuerpo = json.dumps(fila.carga or {}, default=str).encode()
        carga = fila.carga if isinstance(fila.carga, dict) else {}
        mensaje = aio_pika.Message(
            body=cuerpo,
            content_type="application/json",
            delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
            correlation_id=carga.get("correlacion_id"),
            message_id=str(getattr(fila, "id", uuid.uuid4())),
            type=fila.tipo,
        )
        await exchange.publish(mensaje, routing_key=fila.tipo)

    async def cerrar(self) -> None:
        if self._conexion is not None:
            await self._conexion.close()
            self._conexion = self._canal = self._exchange = None


def sink_desde_entorno() -> BrokerSink | None:
    url = url_broker()
    return BrokerSink(url=url) if url else None


async def responde(
    url: str, *, espera: float = 15.0, conectar: Callable[[str], Awaitable[Any]] | None = None
) -> str | None:
    try:
        if conectar is None:
            import aio_pika

            conectar = aio_pika.connect
        conexion = await asyncio.wait_for(conectar(url), espera)
    except TimeoutError:
        return f"no saludo en {espera:g} s"
    except Exception as error:  # noqa: BLE001 - cualquier fallo es un "no responde"
        return f"{type(error).__name__}: {error}" if str(error) else type(error).__name__
    await conexion.close()
    return None


def sin_clave(url: str) -> str:
    partes = urlsplit(url)
    if partes.password is None:
        return url
    usuario = partes.username or ""
    servidor = partes.hostname or ""
    if partes.port is not None:
        servidor = f"{servidor}:{partes.port}"
    return urlunsplit(partes._replace(netloc=f"{usuario}:***@{servidor}"))


def main(*, espera: float = 15.0, conectar: Callable[[str], Awaitable[Any]] | None = None) -> int:
    url = url_broker()
    if url is None:
        print("Sin RABBITMQ_URL: no hay broker que comprobar.", file=sys.stderr)
        return 2
    motivo = asyncio.run(responde(url, espera=espera, conectar=conectar))
    if motivo is not None:
        print(f"RabbitMQ no responde en {sin_clave(url)} ({motivo}).", file=sys.stderr)
        return 1
    print(f"RabbitMQ responde en {sin_clave(url)}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["EXCHANGE", "BrokerSink", "main", "responde", "sin_clave", "sink_desde_entorno", "url_broker"]
