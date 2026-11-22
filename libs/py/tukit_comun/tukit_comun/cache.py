"""Redis para la cache y el limite de tasa.

Decisiones:
- Redis guarda solo lo que se puede perder: lecturas costosas de recalcular y los contadores del
  limite. Postgres sigue siendo la fuente de verdad.
- Un Redis que falla no tumba nada: cada operacion espera como maximo `TUKIT_REDIS_ESPERA_MS`
  (250 ms por omision); si falla, la cache dice que no esta y el limite cuenta en la memoria del
  proceso.
- Tras un fallo el cliente deja de preguntar durante `PAUSA_TRAS_FALLO` segundos y luego vuelve a
  probar; cada episodio deja un solo WARNING.
- Solo este modulo habla con Redis (lo verifica `arquitectura/test_fronteras.py`).
"""

from __future__ import annotations

import asyncio
import logging
import math
import os
import sys
import time
from collections.abc import Awaitable, Callable, Mapping, Sequence
from typing import Any, Protocol, TypeVar

from . import metricas
from .broker import sin_clave

PREFIJO = "tukit:"
ESPERA_POR_OMISION_MS = 250
PAUSA_TRAS_FALLO = 5.0
TOPE_EN_MEMORIA = 50_000

log = logging.getLogger(__name__)

T = TypeVar("T")

_CONTAR_LUA = """
local salida = {}
for i, clave in ipairs(KEYS) do
  local cuenta = redis.call('INCR', clave)
  local resta = redis.call('PTTL', clave)
  if cuenta == 1 or resta < 0 then
    redis.call('EXPIRE', clave, ARGV[i])
    resta = tonumber(ARGV[i]) * 1000
  end
  salida[#salida + 1] = cuenta
  salida[#salida + 1] = resta
end
return salida
"""


class Motor(Protocol):
    errores: tuple[type[BaseException], ...]

    async def leer_varias(self, claves: Sequence[str]) -> list[bytes | None]: ...

    async def guardar_varias(self, pares: Mapping[str, bytes], ttl: int) -> None: ...

    async def contar(self, claves: Sequence[tuple[str, int]]) -> list[tuple[int, int]]: ...

    async def cerrar(self) -> None: ...


class MotorEnMemoria:
    errores: tuple[type[BaseException], ...] = ()

    def __init__(self, *, reloj: Callable[[], float] = time.monotonic, tope: int = TOPE_EN_MEMORIA) -> None:
        self._reloj = reloj
        self._tope = tope
        self._valores: dict[str, tuple[bytes, float]] = {}
        self._cuentas: dict[str, tuple[int, float]] = {}

    async def leer_varias(self, claves: Sequence[str]) -> list[bytes | None]:
        ahora = self._reloj()
        salida: list[bytes | None] = []
        for clave in claves:
            guardado = self._valores.get(clave)
            salida.append(guardado[0] if guardado is not None and guardado[1] > ahora else None)
        return salida

    async def guardar_varias(self, pares: Mapping[str, bytes], ttl: int) -> None:
        vence = self._reloj() + ttl
        for clave, valor in pares.items():
            self._valores[clave] = (valor, vence)
        self._podar(self._valores)

    async def contar(self, claves: Sequence[tuple[str, int]]) -> list[tuple[int, int]]:
        ahora = self._reloj()
        salida: list[tuple[int, int]] = []
        for clave, ventana in claves:
            cuenta, vence = self._cuentas.get(clave, (0, 0.0))
            if vence <= ahora:
                cuenta, vence = 0, ahora + ventana
            cuenta += 1
            self._cuentas[clave] = (cuenta, vence)
            salida.append((cuenta, math.ceil((vence - ahora) * 1000)))
        self._podar(self._cuentas)
        return salida

    async def cerrar(self) -> None:
        return None

    def vence_en(self, clave: str) -> float | None:
        guardado = self._valores.get(clave) or self._cuentas.get(clave)
        if guardado is None or guardado[1] <= self._reloj():
            return None
        return guardado[1] - self._reloj()

    def _podar(self, datos: dict[str, Any]) -> None:
        if len(datos) <= self._tope:
            return
        ahora = self._reloj()
        for clave in [c for c, (_, vence) in datos.items() if vence <= ahora]:
            del datos[clave]
        if len(datos) > self._tope:
            sobran = sorted(datos, key=lambda c: datos[c][1])[: len(datos) - self._tope]
            for clave in sobran:
                del datos[clave]


class MotorRedis:
    def __init__(self, url: str, *, espera: float) -> None:
        from redis import exceptions

        self.url = url
        self._espera = espera
        self.errores: tuple[type[BaseException], ...] = (exceptions.RedisError, OSError)
        self._conexion: Any = None
        self._bucle: asyncio.AbstractEventLoop | None = None
        self._script: Any = None

    def _redis(self) -> Any:
        bucle = asyncio.get_running_loop()
        if self._conexion is None or self._bucle is not bucle:
            import redis.asyncio as redis_asincrono
            from redis.asyncio.retry import Retry
            from redis.backoff import NoBackoff

            self._conexion = redis_asincrono.from_url(
                self.url,
                socket_timeout=self._espera,
                socket_connect_timeout=self._espera,
                retry=Retry(NoBackoff(), 0),
            )
            self._script = self._conexion.register_script(_CONTAR_LUA)
            self._bucle = bucle
        return self._conexion

    async def leer_varias(self, claves: Sequence[str]) -> list[bytes | None]:
        if not claves:
            return []
        return list(await self._redis().mget(list(claves)))

    async def guardar_varias(self, pares: Mapping[str, bytes], ttl: int) -> None:
        if not pares:
            return
        async with self._redis().pipeline(transaction=False) as tuberia:
            for clave, valor in pares.items():
                tuberia.set(clave, valor, ex=ttl)
            await tuberia.execute()

    async def contar(self, claves: Sequence[tuple[str, int]]) -> list[tuple[int, int]]:
        self._redis()
        crudo = await self._script(keys=[c for c, _ in claves], args=[v for _, v in claves])
        return [(int(crudo[i]), int(crudo[i + 1])) for i in range(0, len(crudo), 2)]

    async def cerrar(self) -> None:
        if self._conexion is not None:
            conexion, self._conexion = self._conexion, None
            if self._bucle is asyncio.get_running_loop():
                await conexion.aclose()


class _SinRedis:
    pass


_SIN_REDIS = _SinRedis()


class ClienteRedis:
    def __init__(
        self,
        motor: Motor | None,
        *,
        espera: float = ESPERA_POR_OMISION_MS / 1000,
        pausa: float = PAUSA_TRAS_FALLO,
        prefijo: str = PREFIJO,
        reloj: Callable[[], float] = time.monotonic,
    ) -> None:
        self._motor = motor
        self._espera = espera
        self._pausa = pausa
        self.prefijo = prefijo
        self._reloj = reloj
        self._memoria = MotorEnMemoria(reloj=reloj)
        self._caido_desde: float | None = None
        self._probar_desde = 0.0

    @property
    def con_redis(self) -> bool:
        return self._motor is not None

    @property
    def degradado(self) -> bool:
        return self._caido_desde is not None

    async def leer(self, uso: str, clave: str) -> bytes | None:
        return (await self.leer_varias(uso, [clave]))[0]

    async def leer_varias(self, uso: str, claves: Sequence[str]) -> list[bytes | None]:
        if not claves:
            return []
        resultado = await self._llamar(uso, lambda m: m.leer_varias([self.prefijo + c for c in claves]))
        if isinstance(resultado, _SinRedis):
            return [None] * len(claves)
        aciertos = sum(v is not None for v in resultado)
        metricas.contar_cache(uso, aciertos=aciertos, fallos=len(resultado) - aciertos)
        return resultado

    async def guardar(self, uso: str, clave: str, valor: bytes, ttl: int) -> None:
        await self.guardar_varias(uso, {clave: valor}, ttl)

    async def guardar_varias(self, uso: str, pares: Mapping[str, bytes], ttl: int) -> None:
        if not pares or ttl <= 0:
            return
        prefijados = {self.prefijo + c: v for c, v in pares.items()}
        await self._llamar(uso, lambda m: m.guardar_varias(prefijados, ttl))

    async def contar(self, claves: Sequence[tuple[str, int]]) -> list[tuple[int, int]]:
        if not claves:
            return []
        prefijadas = [(self.prefijo + c, ventana) for c, ventana in claves]
        resultado = await self._llamar("limite", lambda m: m.contar(prefijadas))
        if isinstance(resultado, _SinRedis):
            return await self._memoria.contar(prefijadas)
        return resultado

    async def cerrar(self) -> None:
        if self._motor is not None:
            await self._motor.cerrar()

    async def _llamar(self, uso: str, operacion: Callable[[Motor], Awaitable[T]]) -> T | _SinRedis:
        motor = self._motor
        if motor is None or self._reloj() < self._probar_desde:
            return _SIN_REDIS
        fallos: tuple[type[BaseException], ...] = (TimeoutError, *motor.errores)
        try:
            async with asyncio.timeout(self._espera):
                resultado = await operacion(motor)
        except fallos as error:
            self._fallo(uso, error)
            return _SIN_REDIS
        if self._caido_desde is not None:
            caido = self._reloj() - self._caido_desde
            log.info("Redis volvio tras %.0f s: la cache y el limite lo usan otra vez", caido)
            self._caido_desde = None
        return resultado

    def _fallo(self, uso: str, error: BaseException) -> None:
        metricas.contar_redis_degradado(uso)
        ahora = self._reloj()
        self._probar_desde = ahora + self._pausa
        if self._caido_desde is None:
            self._caido_desde = ahora
            log.warning(
                "Redis no responde (%s): la cache calcula sin guardar y el limite cuenta en memoria "
                "hasta que vuelva",
                type(error).__name__,
            )


def url_redis() -> str | None:
    return os.environ.get("REDIS_URL", "").strip() or None


def entero_de_entorno(variable: str, por_omision: int) -> int:
    crudo = os.environ.get(variable, "").strip()
    try:
        return int(crudo) if crudo else por_omision
    except ValueError:
        log.warning("%s no es un entero (%r): uso %s", variable, crudo, por_omision)
        return por_omision


def cliente_desde_entorno() -> ClienteRedis:
    espera = entero_de_entorno("TUKIT_REDIS_ESPERA_MS", ESPERA_POR_OMISION_MS) / 1000
    url = url_redis()
    if url is None:
        return ClienteRedis(None, espera=espera)
    try:
        motor = MotorRedis(url, espera=espera)
    except ImportError:
        log.warning("Hay REDIS_URL pero falta el paquete redis: sigo sin Redis")
        return ClienteRedis(None, espera=espera)
    return ClienteRedis(motor, espera=espera)


_cliente: ClienteRedis | None = None


def cliente_redis() -> ClienteRedis:
    global _cliente
    if _cliente is None:
        _cliente = cliente_desde_entorno()
    return _cliente


def usar_cliente(cliente: ClienteRedis | None) -> None:
    global _cliente
    _cliente = cliente


async def cerrar_cliente() -> None:
    if _cliente is not None:
        await _cliente.cerrar()


async def responde(url: str, *, espera: float = 2.0) -> str | None:
    try:
        motor = MotorRedis(url, espera=espera)
    except ImportError:
        return "falta el paquete redis"
    try:
        async with asyncio.timeout(espera):
            await motor.leer_varias([PREFIJO + "sonda"])
    except TimeoutError:
        return f"no contesto en {espera:g} s"
    except Exception as error:  # noqa: BLE001 - cualquier fallo es un "no responde"
        return f"{type(error).__name__}: {error}" if str(error) else type(error).__name__
    finally:
        await motor.cerrar()
    return None


def main(*, espera: float = 2.0) -> int:
    url = url_redis()
    if url is None:
        print("Sin REDIS_URL: no hay Redis que comprobar.", file=sys.stderr)
        return 2
    motivo = asyncio.run(responde(url, espera=espera))
    if motivo is not None:
        print(f"Redis no responde en {sin_clave(url)} ({motivo}).", file=sys.stderr)
        return 1
    print(f"Redis responde en {sin_clave(url)}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "PREFIJO",
    "ClienteRedis",
    "Motor",
    "MotorEnMemoria",
    "MotorRedis",
    "cerrar_cliente",
    "cliente_desde_entorno",
    "cliente_redis",
    "entero_de_entorno",
    "main",
    "responde",
    "url_redis",
    "usar_cliente",
]
