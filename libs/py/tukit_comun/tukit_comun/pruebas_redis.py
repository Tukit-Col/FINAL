"""Lo que comparten las pruebas de la cache y el limite (ADR 0047).

Dos cosas:

- **El doble.** `RedisEnMemoria` es el motor en memoria de `cache.py` con dos
  modos de fallo (caido y lento) y un registro de lo que se le pidio. Con el, las
  pruebas unitarias cuentan cuantas veces se leyo o se guardo sin un Redis de
  verdad y sin `fakeredis`.
- **El Redis de las pruebas de integracion.** Las marcadas `redis` hablan con el
  Redis de `TUKIT_PRUEBAS_REDIS_URL` (por omision la base 15 del local, nunca la
  0 de `.env.ejemplo`) y se saltan si no responde. Cada prueba usa un prefijo
  propio y borra sus claves al terminar, con `SCAN` y `DEL`, que solo usan las
  pruebas. Para mirar lo que quedo guardado usan `lo_guardado`: ni las pruebas
  de los servicios importan `redis` (lo vigila `arquitectura/test_fronteras.py`).

No es `REDIS_URL` a proposito: esa variable cambia el modo de los procesos, y
una prueba no deberia cambiar de modo porque alguien la tenga exportada. Con
`TUKIT_PRUEBAS_REDIS_OBLIGATORIO`, una prueba sin Redis falla en vez de
saltarse; CI la pone.
"""

from __future__ import annotations

import asyncio
import os
import time
import uuid
from collections.abc import AsyncIterator, Callable, Mapping, Sequence
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any

from .broker import sin_clave
from .cache import ClienteRedis, MotorEnMemoria, MotorRedis, responde


class RedisCaido(ConnectionError):
    """Lo que levanta el doble cuando esta caido."""


class RedisEnMemoria(MotorEnMemoria):
    """El motor en memoria, con fallos a pedido y un registro de llamadas.

    - `caido = True`: cada operacion levanta `RedisCaido`, como un Redis que
      cerro la conexion.
    - `demora = s`: cada operacion espera `s` segundos antes de responder, como
      un Redis lento. Con una `demora` mayor que la espera del cliente, el
      cliente se rinde antes.
    - `llamadas`: `(operacion, claves)` por cada llamada que llego al motor,
      incluidas las que fallaron.
    """

    errores: tuple[type[BaseException], ...] = (RedisCaido,)

    def __init__(self, *, reloj: Callable[[], float] = time.monotonic) -> None:
        super().__init__(reloj=reloj)
        self.caido = False
        self.demora = 0.0
        self.llamadas: list[tuple[str, tuple[str, ...]]] = []

    def operaciones(self, operacion: str) -> list[tuple[str, ...]]:
        """Las claves de cada llamada a `operacion`."""
        return [claves for nombre, claves in self.llamadas if nombre == operacion]

    async def _antes(self, operacion: str, claves: Sequence[str]) -> None:
        self.llamadas.append((operacion, tuple(claves)))
        if self.demora:
            await asyncio.sleep(self.demora)
        if self.caido:
            raise RedisCaido("el Redis de la prueba esta caido")

    async def leer_varias(self, claves: Sequence[str]) -> list[bytes | None]:
        await self._antes("leer", claves)
        return await super().leer_varias(claves)

    async def guardar_varias(self, pares: Mapping[str, bytes], ttl: int) -> None:
        await self._antes("guardar", list(pares))
        await super().guardar_varias(pares, ttl)

    async def contar(self, claves: Sequence[tuple[str, int]]) -> list[tuple[int, int]]:
        await self._antes("contar", [c for c, _ in claves])
        return await super().contar(claves)

    def guardado(self, clave: str) -> bytes | None:
        """El valor guardado en `clave` (con prefijo), sin pasar por el registro."""
        valor = self._valores.get(clave)
        return valor[0] if valor is not None else None

    def claves(self) -> list[str]:
        """Las claves guardadas o contadas, con prefijo."""
        return [*self._valores, *self._cuentas]


def cliente_en_memoria(
    motor: RedisEnMemoria | None = None, *, espera: float = 0.05, pausa: float = 5.0, **opciones: Any
) -> ClienteRedis:
    """Un `ClienteRedis` sobre el doble, con una espera corta para que el modo
    lento no demore la prueba."""
    motor = motor if motor is not None else RedisEnMemoria()
    return ClienteRedis(motor, espera=espera, pausa=pausa, **opciones)


def url_de_pruebas() -> str:
    """El Redis de las pruebas de integracion."""
    return os.environ.get("TUKIT_PRUEBAS_REDIS_URL", "redis://localhost:6379/15")


def redis_obligatorio() -> bool:
    """Si una prueba sin Redis debe fallar en vez de saltarse."""
    return bool(os.environ.get("TUKIT_PRUEBAS_REDIS_OBLIGATORIO"))


_disponible: dict[str, bool] = {}


async def redis_disponible(url: str) -> bool:
    """Si el Redis de `url` responde; se pregunta una vez por proceso."""
    if url not in _disponible:
        _disponible[url] = await responde(url) is None
    return _disponible[url]


async def exigir_redis(url: str) -> None:
    """Salta la prueba si el Redis de `url` no responde, o la hace fallar si
    `TUKIT_PRUEBAS_REDIS_OBLIGATORIO` lo exige."""
    import pytest

    if not await redis_disponible(url):
        if redis_obligatorio():
            pytest.fail(f"no hay Redis en {sin_clave(url)} y TUKIT_PRUEBAS_REDIS_OBLIGATORIO lo exige")
        pytest.skip(f"no hay Redis en {sin_clave(url)}")


def prefijo_de_prueba() -> str:
    """Un prefijo unico por prueba, para no pisar las claves de nadie."""
    return f"prueba-{uuid.uuid4().hex[:10]}:"


async def borrar_prefijo(url: str, prefijo: str) -> int:
    """Borra las claves que empiezan por `prefijo`; devuelve cuantas."""
    import redis.asyncio as redis_asincrono

    conexion = redis_asincrono.from_url(url)
    try:
        claves = [clave async for clave in conexion.scan_iter(match=prefijo + "*", count=500)]
        if claves:
            await conexion.delete(*claves)
        return len(claves)
    finally:
        await conexion.aclose()


@dataclass(frozen=True)
class Guardado:
    """Una clave tal como quedo en Redis: su valor y lo que le falta para vencer."""

    valor: bytes
    vence_en_ms: int


async def lo_guardado(prefijo: str) -> dict[str, Guardado]:
    """Lo que hay en el Redis de las pruebas bajo `prefijo`, por clave completa."""
    import redis.asyncio as redis_asincrono

    conexion = redis_asincrono.from_url(url_de_pruebas())
    try:
        guardado: dict[str, Guardado] = {}
        claves = [clave.decode() async for clave in conexion.scan_iter(match=prefijo + "*", count=500)]
        for clave in sorted(claves):
            # Sin `decode_responses` el valor llega en bytes; `None` si vencio entre el SCAN y el GET.
            valor = await conexion.get(clave)
            if isinstance(valor, bytes):
                guardado[clave] = Guardado(valor, await conexion.pttl(clave))
        return guardado
    finally:
        await conexion.aclose()


@asynccontextmanager
async def clientes_de_prueba(cuantos: int = 1, *, espera: float = 1.0) -> AsyncIterator[list[ClienteRedis]]:
    """`cuantos` clientes contra el Redis de las pruebas, cada uno con su
    conexion y todos con el mismo prefijo, como varias replicas de un servicio.
    Al salir cierra las conexiones y borra lo que dejaron.

    La espera es mas holgada que la de los servicios: aqui se prueba lo que
    Redis guarda, no cuanto tarda, y un CI cargado no debe volver la prueba
    intermitente."""
    url = url_de_pruebas()
    await exigir_redis(url)
    prefijo = prefijo_de_prueba()
    clientes = [
        ClienteRedis(MotorRedis(url, espera=espera), espera=espera, prefijo=prefijo) for _ in range(cuantos)
    ]
    try:
        yield clientes
    finally:
        for cliente in clientes:
            await cliente.cerrar()
        await borrar_prefijo(url, prefijo)


__all__ = [
    "Guardado",
    "RedisCaido",
    "RedisEnMemoria",
    "borrar_prefijo",
    "cliente_en_memoria",
    "clientes_de_prueba",
    "exigir_redis",
    "lo_guardado",
    "prefijo_de_prueba",
    "redis_disponible",
    "redis_obligatorio",
    "url_de_pruebas",
]
