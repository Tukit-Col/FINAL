from __future__ import annotations

import os
import uuid
from typing import Any

from .broker import responde
from .topologia import TOPOLOGIA, Topologia


def url_de_pruebas() -> str:
    return os.environ.get("TUKIT_PRUEBAS_RABBITMQ_URL", "amqp://guest:guest@localhost:5672/")


def broker_obligatorio() -> bool:
    return bool(os.environ.get("TUKIT_PRUEBAS_RABBITMQ_OBLIGATORIO"))


_disponible: dict[str, bool] = {}


async def broker_disponible(url: str, *, espera: float = 15.0) -> bool:
    if url not in _disponible:
        _disponible[url] = await responde(url, espera=espera) is None
    return _disponible[url]


def topologia_de_prueba(*, espera_reintento_ms: int = 100) -> Topologia:
    return TOPOLOGIA.con_prefijo(f"prueba-{uuid.uuid4().hex[:10]}", espera_reintento_ms=espera_reintento_ms)


class Sonda:
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
        propiedades = self._conexion.transport.connection.server_properties
        version = propiedades.get("version")
        return None if version is None else str(version)

    async def canal(self) -> Any:
        return await self._conexion.channel()

    async def cuantos(self, cola: str) -> int:
        declarada = await self._canal.declare_queue(cola, passive=True)
        return int(declarada.declaration_result.message_count or 0)

    async def borrar(self, topologia: Topologia) -> None:
        for cola in topologia.colas:
            for nombre in (cola.nombre, cola.reintentos, cola.descartados):
                await self._canal.queue_delete(nombre)
        await self._canal.exchange_delete(topologia.exchange)

    async def sacar(self, cola: str) -> list[Any]:
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
