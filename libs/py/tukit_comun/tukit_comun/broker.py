"""El `BrokerSink`: publica los eventos del outbox a RabbitMQ (ADR 0007/0022).

El outbox es la fuente de verdad; esto es un *upgrade de entrega* (push, fan-out,
replay), no un cambio de arquitectura. `drenar` (en `bandeja.py`) llama a
`sink.publicar(fila)` por cada evento HECHO; aqui eso se traduce en un publish al
exchange con el TIPO del evento como routing key. RabbitMQ hace el fan-out a las
colas de cada consumidor y las DLQ.

**Degrada honestamente:** `sink_desde_entorno()` devuelve `None` si no hay
`RABBITMQ_URL`, y `drenar(..., sink=None)` se comporta igual que hoy (solo el
`manejar`/NotifierSink). La tesis corre sin RabbitMQ; quien lo quiera lo levanta
con `make infra-arriba` y exporta la URL.

`aio-pika` se importa DENTRO de las funciones a proposito: importar este modulo
no debe fallar ni cargar el driver en un proceso que no publica al broker (las
pruebas de dominio, un CLI de seed). El outbox nunca desaparece: si el broker
esta caido, `publicar` levanta, `drenar` NO marca el evento y se reintenta en la
proxima pasada (at-least-once; los consumidores son idempotentes, ADR 0022).
"""

from __future__ import annotations

import json
import os
import uuid
from dataclasses import dataclass
from typing import Any

# El nombre del exchange topic al que se publican todos los eventos del outbox.
# Uno solo para todo el monorepo: el routing key (el tipo del evento) y los
# bindings de cada cola deciden quien recibe que, no el exchange.
EXCHANGE = "tukit.eventos"


def url_broker() -> str | None:
    """La URL de RabbitMQ del entorno, o `None` si no hay (degrada a sin-broker)."""
    return os.environ.get("RABBITMQ_URL") or None


@dataclass
class BrokerSink:
    """Publica cada evento HECHO al exchange topic de RabbitMQ.

    Abre la conexion perezosamente en el primer `publicar` y la reusa: un
    drenador de vida larga no debe abrir un socket por evento. `cerrar()` la
    suelta al apagar el proceso.
    """

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
        # `correlation_id` de la cabecera AMQP para que el consumidor re-vincule
        # el hilo (ADR 0021); tambien viaja en la carga, pero la cabecera es la
        # que las herramientas de RabbitMQ muestran.
        carga = fila.carga if isinstance(fila.carga, dict) else {}
        mensaje = aio_pika.Message(
            body=cuerpo,
            content_type="application/json",
            delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
            correlation_id=carga.get("correlacion_id"),
            message_id=str(getattr(fila, "id", uuid.uuid4())),
            type=fila.tipo,
        )
        # El routing key ES el tipo del evento: `kits_publicados`, `pedido_pagado`,
        # etc. Cada consumidor hace bind de su cola al patron que le toca.
        await exchange.publish(mensaje, routing_key=fila.tipo)

    async def cerrar(self) -> None:
        if self._conexion is not None:
            await self._conexion.close()
            self._conexion = self._canal = self._exchange = None


def sink_desde_entorno() -> BrokerSink | None:
    """El sink del entorno: `BrokerSink` si hay `RABBITMQ_URL`, si no `None`.

    `None` no es un error: es la degradacion honesta del ADR 0022. `drenar` con
    `sink=None` entrega solo por el `manejar` de siempre (NotifierSink)."""
    url = url_broker()
    return BrokerSink(url=url) if url else None


__all__ = ["EXCHANGE", "BrokerSink", "sink_desde_entorno", "url_broker"]
