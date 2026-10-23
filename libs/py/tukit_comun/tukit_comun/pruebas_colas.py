"""Lo que comparten las pruebas contra un RabbitMQ de verdad (ADR 0046).

Las pruebas marcadas `rabbitmq` hablan con el broker de
`TUKIT_PRUEBAS_RABBITMQ_URL` (por omision el local, el de `.env.ejemplo`) y se
saltan si no responde, para que la suite siga corriendo sin broker. Cada prueba
declara una topologia con un prefijo propio y la borra al terminar: no toca las
colas de quien este usando el broker, ni deja residuo.

No es `RABBITMQ_URL` a proposito: esa variable cambia el modo de los procesos, y
una prueba no deberia cambiar de modo porque alguien la tenga exportada.

Vive en la libreria, como `bd.sesion_de_prueba`, porque la usan las pruebas de
la libreria y las de los servicios.
"""

from __future__ import annotations

import asyncio
import os
import uuid
from typing import Any

from .topologia import TOPOLOGIA, Topologia


def url_de_pruebas() -> str:
    """El broker de las pruebas de integracion."""
    return os.environ.get("TUKIT_PRUEBAS_RABBITMQ_URL", "amqp://guest:guest@localhost:5672/")


# Si el broker respondio, por URL: se pregunta una vez por proceso, porque abrir
# una conexion no es gratis (en la Mac de desarrollo el broker tarda segundos en
# autenticar cada una).
_disponible: dict[str, bool] = {}


async def broker_disponible(url: str, *, espera: float = 15.0) -> bool:
    """Si el broker de `url` acepta una conexion en `espera` segundos."""
    if url not in _disponible:
        try:
            import aio_pika

            conexion = await asyncio.wait_for(aio_pika.connect(url), timeout=espera)
        except Exception:
            _disponible[url] = False
        else:
            await conexion.close()
            _disponible[url] = True
    return _disponible[url]


def topologia_de_prueba(*, espera_reintento_ms: int = 100) -> Topologia:
    """La topologia de siempre, con un prefijo unico y reintentos cortos."""
    return TOPOLOGIA.con_prefijo(f"prueba-{uuid.uuid4().hex[:10]}", espera_reintento_ms=espera_reintento_ms)


class Sonda:
    """Una conexion abierta para mirar y limpiar las colas desde la prueba.

    Una sola por prueba: cada conexion nueva cuesta lo que el broker tarde en
    saludar.
    """

    def __init__(self, url: str) -> None:
        self.url = url
        self._conexion: Any = None
        self._canal: Any = None

    async def __aenter__(self) -> Sonda:
        import aio_pika

        self._conexion = await aio_pika.connect(self.url)
        self._canal = await self._conexion.channel()
        return self

    async def __aexit__(self, *_: object) -> None:
        await self._conexion.close()

    @property
    def version(self) -> str | None:
        """La version que el broker informa al saludar."""
        propiedades = self._conexion.transport.connection.server_properties
        version = propiedades.get("version")
        return None if version is None else str(version)

    async def canal(self) -> Any:
        """Un canal nuevo sobre la misma conexion."""
        return await self._conexion.channel()

    async def cuantos(self, cola: str) -> int:
        """Cuantos mensajes listos hay en `cola`, sin sacarlos."""
        declarada = await self._canal.declare_queue(cola, passive=True)
        return int(declarada.declaration_result.message_count or 0)

    async def borrar(self, topologia: Topologia) -> None:
        """Borra las colas y el exchange que declaro una prueba."""
        for cola in topologia.colas:
            for nombre in (cola.nombre, cola.reintentos, cola.descartados):
                await self._canal.queue_delete(nombre)
        await self._canal.exchange_delete(topologia.exchange)

    async def sacar(self, cola: str) -> list[Any]:
        """Saca (con ack) todos los mensajes que hay en `cola`, para mirarlos."""
        declarada = await self._canal.declare_queue(cola, passive=True)
        sacados = []
        while (mensaje := await declarada.get(no_ack=True, fail=False)) is not None:
            sacados.append(mensaje)
        return sacados


__all__ = [
    "Sonda",
    "broker_disponible",
    "topologia_de_prueba",
    "url_de_pruebas",
]
