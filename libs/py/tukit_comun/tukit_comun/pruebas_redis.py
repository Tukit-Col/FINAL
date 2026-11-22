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
    pass


class RedisEnMemoria(MotorEnMemoria):
    errores: tuple[type[BaseException], ...] = (RedisCaido,)

    def __init__(self, *, reloj: Callable[[], float] = time.monotonic) -> None:
        super().__init__(reloj=reloj)
        self.caido = False
        self.demora = 0.0
        self.llamadas: list[tuple[str, tuple[str, ...]]] = []

    def operaciones(self, operacion: str) -> list[tuple[str, ...]]:
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
        valor = self._valores.get(clave)
        return valor[0] if valor is not None else None

    def claves(self) -> list[str]:
        return [*self._valores, *self._cuentas]


def cliente_en_memoria(
    motor: RedisEnMemoria | None = None, *, espera: float = 0.05, pausa: float = 5.0, **opciones: Any
) -> ClienteRedis:
    motor = motor if motor is not None else RedisEnMemoria()
    return ClienteRedis(motor, espera=espera, pausa=pausa, **opciones)


def url_de_pruebas() -> str:
    return os.environ.get("TUKIT_PRUEBAS_REDIS_URL", "redis://localhost:6379/15")


def redis_obligatorio() -> bool:
    return bool(os.environ.get("TUKIT_PRUEBAS_REDIS_OBLIGATORIO"))


_disponible: dict[str, bool] = {}


async def redis_disponible(url: str) -> bool:
    if url not in _disponible:
        _disponible[url] = await responde(url) is None
    return _disponible[url]


async def exigir_redis(url: str) -> None:
    import pytest

    if not await redis_disponible(url):
        if redis_obligatorio():
            pytest.fail(f"no hay Redis en {sin_clave(url)} y TUKIT_PRUEBAS_REDIS_OBLIGATORIO lo exige")
        pytest.skip(f"no hay Redis en {sin_clave(url)}")


def prefijo_de_prueba() -> str:
    return f"prueba-{uuid.uuid4().hex[:10]}:"


async def borrar_prefijo(url: str, prefijo: str) -> int:
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
    valor: bytes
    vence_en_ms: int


async def lo_guardado(prefijo: str) -> dict[str, Guardado]:
    import redis.asyncio as redis_asincrono

    conexion = redis_asincrono.from_url(url_de_pruebas())
    try:
        guardado: dict[str, Guardado] = {}
        claves = [clave.decode() async for clave in conexion.scan_iter(match=prefijo + "*", count=500)]
        for clave in sorted(claves):
            valor = await conexion.get(clave)
            if isinstance(valor, bytes):
                guardado[clave] = Guardado(valor, await conexion.pttl(clave))
        return guardado
    finally:
        await conexion.aclose()


@asynccontextmanager
async def clientes_de_prueba(cuantos: int = 1, *, espera: float = 1.0) -> AsyncIterator[list[ClienteRedis]]:
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
