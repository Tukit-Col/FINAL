"""Resiliencia entre servicios: disyuntor + politica de reintento (ADR 0020).

Complementa lo que ya trae la comunicacion del sistema (timeouts por-llamador en
cada `remoto.py`, degradacion honesta) con dos piezas que faltaban:

- **Disyuntor (circuit breaker), uno por destino.** Tras `umbral` fallos deja de
  golpear al destino caido y rechaza en el acto con `CircuitoAbierto`; pasado el
  `ttl` prueba una vez (medio-abierto) y se cierra si esa prueba pasa. El mismo
  limite por-destino es la frontera del bulkhead: un catalogo caido no consume
  los slots de las llamadas a identidad.
- **Reintento SOLO en GET idempotentes.** Un reintento ciego de un POST es un
  doble cobro. `llamada_protegida(..., reintentable=True)` sobre un metodo que no
  es GET es un error de programacion, y se rechaza al construir, no en runtime.
  Las escrituras se protegen con idempotencia de aplicacion (clave natural +
  tabla de dedup, como el webhook Wompi), no con reintento de transporte.
- **Bucle de fondo que sobrevive a las caidas (ADR 0041).** Los procesos de
  fondo (barredor, pollers, trabajador, repartidor) corrian `while True` sin un
  solo `except`: con Postgres o RabbitMQ caidos morian y no volvian (H-B-02).
  `bucle_resiliente` repite cada vuelta tras una caida transitoria
  (`es_caida_transitoria`), con espera exponencial y tope, y deja un WARNING con
  la excepcion. Un error de programacion sigue tumbando el proceso.

Se escribio a mano (sin `purgatory`) porque el estado del disyuntor son ~40
lineas puras y testeables con `assert`, y la unica libreria async del ecosistema
arrastra `pkg_resources` (setuptools<81, API ya marcada para eliminacion). El
backend es in-memory por proceso; para multi-replica se cambia el almacen del
estado sin tocar la interfaz (misma postura que el `Sink` del outbox).
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Awaitable, Callable, Iterator
from enum import Enum
from typing import Any

from sqlalchemy import exc as sa_exc
from tenacity import (
    AsyncRetrying,
    RetryCallState,
    retry,
    retry_if_exception,
    retry_if_not_exception_type,
    stop_after_attempt,
    wait_exponential,
)

UMBRAL_POR_OMISION = 5
TTL_POR_OMISION = 30.0
# La espera de un bucle de fondo tras una caida: 1 s, el doble cada vez, y como
# mucho 30 s. El tope es corto a proposito: un proceso que espera minutos a una
# base que ya volvio deja eventos sin entregar sin que nada lo explique.
ESPERA_INICIAL_BUCLE = 1.0
ESPERA_TOPE_BUCLE = 30.0

log = logging.getLogger(__name__)


class CircuitoAbierto(RuntimeError):
    """El disyuntor esta abierto: se rechaza sin tocar al destino caido."""


class _Estado(Enum):
    CERRADO = "cerrado"
    ABIERTO = "abierto"
    MEDIO_ABIERTO = "medio_abierto"


class Disyuntor:
    """Un circuit breaker async, uno por destino, usable como `async with`.

    Umbrales generosos por omision (abre a 5 fallos, prueba a los 30 s): el
    objetivo es cortar una tormenta de llamadas a un destino claramente caido,
    no reaccionar a un fallo aislado.
    """

    def __init__(
        self,
        destino: str,
        *,
        umbral: int = UMBRAL_POR_OMISION,
        ttl: float = TTL_POR_OMISION,
        reloj: Callable[[], float] = time.monotonic,
    ) -> None:
        self.destino = destino
        self.umbral = umbral
        self.ttl = ttl
        self._reloj = reloj
        self._estado = _Estado.CERRADO
        self._fallos = 0
        self._abierto_desde = 0.0

    @property
    def abierto(self) -> bool:
        return self._estado is _Estado.ABIERTO

    async def __aenter__(self) -> Disyuntor:
        if self._estado is _Estado.ABIERTO:
            if self._reloj() - self._abierto_desde >= self.ttl:
                self._estado = _Estado.MEDIO_ABIERTO  # deja pasar UNA prueba
            else:
                raise CircuitoAbierto(f"circuito abierto para {self.destino!r}")
        return self

    async def __aexit__(
        self,
        tipo: type[BaseException] | None,
        exc: BaseException | None,
        tb: Any,
    ) -> bool:
        if exc is None:
            # Un exito cierra el circuito y limpia el conteo.
            self._estado = _Estado.CERRADO
            self._fallos = 0
            return False
        if self._estado is _Estado.MEDIO_ABIERTO:
            # La prueba fallo: reabrir y reiniciar el reloj del TTL.
            self._estado = _Estado.ABIERTO
            self._abierto_desde = self._reloj()
        else:
            self._fallos += 1
            if self._fallos >= self.umbral:
                self._estado = _Estado.ABIERTO
                self._abierto_desde = self._reloj()
        return False  # nunca traga la excepcion; el llamador decide degradar


# Registro de disyuntores por destino: uno vivo por (proceso, destino).
_disyuntores: dict[str, Disyuntor] = {}


def disyuntor_de(destino: str) -> Disyuntor:
    """El disyuntor compartido de un destino (`catalogo`, `identidad`, ...)."""
    if destino not in _disyuntores:
        _disyuntores[destino] = Disyuntor(destino)
    return _disyuntores[destino]


# Politica tenacity para GET idempotentes: 3 intentos, backoff exponencial. Es
# un decorador listo para envolver un metodo de lectura de `remoto.py`. No
# reintenta ante `CircuitoAbierto` (insistir con el circuito abierto no tiene
# sentido) ni ante `ValueError` de argumentos; reintenta timeouts y 5xx/red.
# Aplicarlo a una escritura seria un doble cobro: por eso el guardia esta en
# `llamada_protegida`, y este decorador se documenta como SOLO-GET.
reintentar_get = retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=0.2, max=2.0),
    retry=retry_if_not_exception_type(CircuitoAbierto),
    reraise=True,
)


def llamada_protegida(destino: str, *, metodo: str, reintentable: bool = False) -> Disyuntor:
    """Devuelve el disyuntor del destino tras validar la politica de reintento.

    Args:
        destino: Nombre canonico del destino (`catalogo`, `identidad`, ...).
        metodo: Metodo HTTP de la llamada (`GET`, `POST`, ...).
        reintentable: Si la llamada puede reintentarse. SOLO permitido en GET.

    Returns:
        El `Disyuntor` compartido del destino, listo para `async with`.

    Raises:
        ValueError: Si `reintentable=True` sobre un metodo que no es GET
            (reintentar una escritura es un doble cobro).
    """
    if reintentable and metodo.upper() != "GET":
        raise ValueError(
            f"reintentable=True solo se permite en GET idempotentes, no en {metodo.upper()}: "
            "reintentar una escritura a nivel de transporte es un doble cobro. "
            "Protege la escritura con idempotencia de aplicacion (clave + dedup)."
        )
    return disyuntor_de(destino)


# Los errores de los drivers que dicen "la base o el broker no estan", por el
# nombre de la clase y no por import: asyncpg es opcional (el extra `postgres`)
# y aio-pika se importa solo donde se publica, asi que este modulo no puede
# cargarlos. Se busca el nombre en toda la jerarquia de la clase.
_CAIDAS_POR_NOMBRE = frozenset(
    {
        # asyncpg: el servidor arranca, se apaga o lo apagaron
        # (`CannotConnectNowError`, `AdminShutdownError`, `CrashShutdownError`).
        "OperatorInterventionError",
        # asyncpg: la conexion se corto o no se pudo abrir
        # (`ConnectionDoesNotExistError`, `ConnectionFailureError`).
        "PostgresConnectionError",
        # asyncpg: el servidor no tiene cupo para otra conexion.
        "TooManyConnectionsError",
        # aiormq: el canal se quedo sin conexion debajo (RabbitMQ cayo).
        "ChannelInvalidStateError",
        # aiormq: el broker respondio nack a una publicacion confirmada (no pudo
        # guardar el mensaje); el publicador lo deja pendiente y reintenta. Las
        # caidas de conexion de aiormq ya son `OSError` (`AMQPConnectionError`).
        "DeliveryError",
    }
)
# Un `OSError` de archivos no es una caida de red: no se arregla esperando.
_OSERROR_DE_ARCHIVOS = (
    FileNotFoundError,
    FileExistsError,
    IsADirectoryError,
    NotADirectoryError,
    PermissionError,
)


def _eslabones(error: BaseException) -> Iterator[BaseException]:
    """El error y sus causas explicitas: el `.orig` de SQLAlchemy o `raise ... from`.

    No sigue `__context__`: un `ValueError` lanzado mientras se manejaba una
    caida es un error de programacion, no una caida.
    """
    vistos: set[int] = set()
    actual: BaseException | None = error
    while actual is not None and id(actual) not in vistos:
        vistos.add(id(actual))
        yield actual
        original = getattr(actual, "orig", None)
        actual = original if isinstance(original, BaseException) else actual.__cause__


def es_caida_transitoria(error: BaseException) -> bool:
    """Si el error es una dependencia que no responde y se arregla sola.

    Cubre lo que se ve cuando Postgres o RabbitMQ se caen o reinician:

    - `OSError` de red: `ConnectionRefusedError`, `TimeoutError`, el
      `socket.gaierror` del nombre de un contenedor muerto que ya no resuelve,
      el `OSError("Multiple exceptions: ...")` de asyncio y el
      `AMQPConnectionError` de aiormq, que tambien es un `OSError`;
    - un `DBAPIError` de SQLAlchemy con `connection_invalidated`, que es como
      SQLAlchemy marca una conexion que se corto;
    - los errores de conexion de asyncpg y el `ChannelInvalidStateError` de
      aiormq, por nombre (`_CAIDAS_POR_NOMBRE`).

    Mira tambien la causa del error (`.orig`, `raise ... from`). Lo demas, como
    un `ValueError`, una restriccion violada o una tabla que no existe, no es
    una caida: es un error de programacion y tiene que tumbar el proceso.
    """
    for eslabon in _eslabones(error):
        if isinstance(eslabon, OSError) and not isinstance(eslabon, _OSERROR_DE_ARCHIVOS):
            return True
        if isinstance(eslabon, sa_exc.DBAPIError) and eslabon.connection_invalidated:
            return True
        if any(clase.__name__ in _CAIDAS_POR_NOMBRE for clase in type(eslabon).__mro__):
            return True
    return False


async def bucle_resiliente(
    vuelta: Callable[[], Awaitable[object]],
    *,
    intervalo: float,
    proceso: str,
    espera_inicial: float = ESPERA_INICIAL_BUCLE,
    espera_tope: float = ESPERA_TOPE_BUCLE,
    dormir: Callable[[float], Awaitable[None]] = asyncio.sleep,
) -> None:
    """El bucle de un proceso de fondo: `vuelta`, `intervalo` segundos, y otra vez.

    Si una vuelta cae por una caida transitoria (`es_caida_transitoria`), espera
    `espera_inicial`, el doble cada vez y como mucho `espera_tope`, y la repite.
    Cada caida deja un WARNING con el proceso y la excepcion, que sale en JSON
    con `TUKIT_LOG_JSON` (`registro.configurar_registro`). Tras una vuelta buena
    la espera vuelve a empezar. La vuelta tiene que abrir sus conexiones, o usar
    un motor con `pool_pre_ping`, para que el reintento reconecte.

    Cualquier otro error sube y termina el proceso, como antes: un bug no se
    esconde detras de reintentos. `dormir` existe para las pruebas.
    """

    def _avisar(estado: RetryCallState) -> None:
        error = estado.outcome.exception() if estado.outcome is not None else None
        espera = estado.next_action.sleep if estado.next_action is not None else 0.0
        log.warning(
            "%s: caida transitoria en el intento %d (%s: %s); se reintenta en %.0f s",
            proceso,
            estado.attempt_number,
            type(error).__name__,
            error,
            espera,
            exc_info=error,
        )

    while True:
        async for intento in AsyncRetrying(
            retry=retry_if_exception(es_caida_transitoria),
            wait=wait_exponential(multiplier=espera_inicial, max=espera_tope),
            sleep=dormir,
            before_sleep=_avisar,
            reraise=True,
        ):
            with intento:
                await vuelta()
        await dormir(intervalo)
