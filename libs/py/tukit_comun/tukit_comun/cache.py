"""Redis para la cache y el limite de tasa (ADR 0047).

Redis guarda dos cosas, y las dos se pueden perder (ADR 0007): lo que cuesta
recalcular (la lectura de una lista, el vector de un renglon) y los contadores
del limite de tasa del gateway. Nada de lo que vive aqui es la unica copia de
algo; Postgres sigue siendo la fuente de verdad y RabbitMQ el unico broker.

Por eso un Redis que falla no tumba nada:

- **Espera corta.** Cada operacion espera como mucho `TUKIT_REDIS_ESPERA_MS`
  (250 ms por omision). En la misma red Redis responde en menos de un
  milisegundo; lo que tarda mas ya es un Redis enfermo.
- **Degradacion.** Si falla o vence, la cache dice "no esta" y no guarda, asi
  que el servicio calcula como antes de que hubiera cache; y el limite cuenta en
  la memoria del proceso. Tras un fallo el cliente deja de preguntar durante
  `PAUSA_TRAS_FALLO` segundos, para que un Redis caido no le cobre la espera a
  cada peticion, y despues vuelve a probar.
- **Un registro por episodio.** El primer fallo deja un WARNING con el tipo de
  error y la vuelta un INFO. Las claves no salen en el log: una del limite lleva
  la huella de un token.

Sin `REDIS_URL` el cliente esta en ese modo desde el principio y no importa
`redis`: las pruebas por servicio de CI no lo instalan. Los servicios solo usan
`cliente_redis()`; el motor de verdad (`MotorRedis`) y el de memoria
(`MotorEnMemoria`, que tambien es la base del doble de las pruebas) tienen la
misma interfaz.

Solo usa `MGET`, `SET` con `EX` y un script Lua con `INCR`, `EXPIRE` y `PTTL`,
que se comportan igual en el `redis:7` del compose y en el Redis 8 de Homebrew.

    REDIS_URL=redis://localhost:6379/0 python -m tukit_comun.cache
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
# Cuantas claves guarda el motor en memoria antes de podar. El conteo del
# limite sin Redis es una clave por IP y por token activos en la ventana:
# cincuenta mil alcanza para un gateway y no deja crecer la memoria sin fin.
TOPE_EN_MEMORIA = 50_000

log = logging.getLogger(__name__)

T = TypeVar("T")

# Una sola ida y vuelta para todas las claves de una peticion. La ventana es
# fija: el primer `INCR` le pone el vencimiento, y si una clave quedo sin el
# (un `EXPIRE` que nunca llego) se lo vuelve a poner.
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
    """Lo que el cliente le pide a Redis, o a lo que hace sus veces."""

    # Las excepciones que son "Redis no responde" y degradan. Otra cualquiera es
    # un error de programacion y sube.
    errores: tuple[type[BaseException], ...]

    async def leer_varias(self, claves: Sequence[str]) -> list[bytes | None]: ...

    async def guardar_varias(self, pares: Mapping[str, bytes], ttl: int) -> None: ...

    async def contar(self, claves: Sequence[tuple[str, int]]) -> list[tuple[int, int]]:
        """Por cada `(clave, ventana en segundos)`, la cuenta tras sumar uno y
        los milisegundos que le quedan a la ventana."""
        ...

    async def cerrar(self) -> None: ...


class MotorEnMemoria:
    """Un diccionario con vencimiento, con la interfaz de `Motor`.

    Es lo que cuenta el limite cuando no hay Redis, y la base del doble de las
    pruebas (`pruebas_redis.RedisEnMemoria`). Vive en el proceso: dos gateways
    con este motor no comparten nada.
    """

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
        """Los segundos que le quedan a `clave`, o `None` si no esta."""
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
            # Sigue lleno de claves vivas: se van las que vencen primero.
            sobran = sorted(datos, key=lambda c: datos[c][1])[: len(datos) - self._tope]
            for clave in sobran:
                del datos[clave]


class MotorRedis:
    """El motor de verdad, sobre redis-py asincrono.

    La conexion se abre en el primer uso y se rehace si cambia el bucle de
    eventos: una conexion de asyncio queda atada al bucle que la abrio. Sin
    reintentos propios de redis-py: la espera la pone el cliente y un reintento
    la multiplicaria.
    """

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
    """La marca de "Redis no estuvo": no hay, esta en pausa, o fallo."""


_SIN_REDIS = _SinRedis()


class ClienteRedis:
    """La cache y el contador del limite, con la degradacion del ADR 0047.

    `motor=None` es "sin Redis": `leer` da no esta, `guardar` no hace nada y
    `contar` cuenta en memoria. Con motor, lo mismo pasa durante un episodio de
    fallo. Las claves que reciben los metodos van sin prefijo; el cliente le
    pone el suyo (`tukit:`, o uno por corrida en las pruebas).
    """

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
        """Si hay un Redis detras, aunque ahora este degradado."""
        return self._motor is not None

    @property
    def degradado(self) -> bool:
        """Si esta en un episodio de fallo."""
        return self._caido_desde is not None

    async def leer(self, uso: str, clave: str) -> bytes | None:
        return (await self.leer_varias(uso, [clave]))[0]

    async def leer_varias(self, uso: str, claves: Sequence[str]) -> list[bytes | None]:
        """El valor de cada clave, en orden; `None` si no esta o si Redis no respondio."""
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
        """Guarda cada par por `ttl` segundos. `ttl <= 0` apaga la cache de ese uso."""
        if not pares or ttl <= 0:
            return
        prefijados = {self.prefijo + c: v for c, v in pares.items()}
        await self._llamar(uso, lambda m: m.guardar_varias(prefijados, ttl))

    async def contar(self, claves: Sequence[tuple[str, int]]) -> list[tuple[int, int]]:
        """Suma uno a cada `(clave, ventana)`: en Redis si responde, en memoria si no."""
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
    """`REDIS_URL`, o `None` si no esta o esta vacia."""
    return os.environ.get("REDIS_URL", "").strip() or None


def entero_de_entorno(variable: str, por_omision: int) -> int:
    """Un entero del entorno; el de por omision si falta o no es un entero."""
    crudo = os.environ.get(variable, "").strip()
    try:
        return int(crudo) if crudo else por_omision
    except ValueError:
        log.warning("%s no es un entero (%r): uso %s", variable, crudo, por_omision)
        return por_omision


def cliente_desde_entorno() -> ClienteRedis:
    """Un cliente con `REDIS_URL` y `TUKIT_REDIS_ESPERA_MS`, o sin Redis."""
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
    """El cliente del proceso, armado del entorno en el primer uso."""
    global _cliente
    if _cliente is None:
        _cliente = cliente_desde_entorno()
    return _cliente


def usar_cliente(cliente: ClienteRedis | None) -> None:
    """Cambia el cliente del proceso; `None` lo vuelve a armar del entorno. Para pruebas."""
    global _cliente
    _cliente = cliente


async def cerrar_cliente() -> None:
    """Cierra la conexion del cliente del proceso, si se llego a armar; el
    siguiente uso la vuelve a abrir. Lo llama `crear_app` al apagar."""
    if _cliente is not None:
        await _cliente.cerrar()


async def responde(url: str, *, espera: float = 2.0) -> str | None:
    """`None` si el Redis de `url` contesta antes de `espera` segundos; si no, el motivo."""
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
    """0 si el Redis de `REDIS_URL` responde, 1 si no, 2 si no hay URL."""
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
