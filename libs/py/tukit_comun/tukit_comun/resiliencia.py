"""Resiliencia entre servicios: disyuntor y politica de reintento.

Decisiones:
- Un disyuntor por destino: tras `umbral` fallos rechaza en el acto con `CircuitoAbierto`; pasado
  el `ttl` prueba una vez. El limite por destino hace de bulkhead.
- Reintento solo en GET idempotentes: reintentar un POST a ciegas puede cobrar doble.
  `reintentable=True` sobre otro metodo es un error de programacion y se rechaza al construir. Las
  escrituras se protegen con idempotencia de aplicacion (clave natural y tabla de deduplicacion).
- Los bucles de fondo usan `bucle_resiliente`: sobreviven a caidas de Postgres o RabbitMQ en vez
  de morir.
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
ESPERA_INICIAL_BUCLE = 1.0
ESPERA_TOPE_BUCLE = 30.0

log = logging.getLogger(__name__)


class CircuitoAbierto(RuntimeError):
    pass


class _Estado(Enum):
    CERRADO = "cerrado"
    ABIERTO = "abierto"
    MEDIO_ABIERTO = "medio_abierto"


class Disyuntor:
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
                self._estado = _Estado.MEDIO_ABIERTO
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
            self._estado = _Estado.CERRADO
            self._fallos = 0
            return False
        if self._estado is _Estado.MEDIO_ABIERTO:
            self._estado = _Estado.ABIERTO
            self._abierto_desde = self._reloj()
        else:
            self._fallos += 1
            if self._fallos >= self.umbral:
                self._estado = _Estado.ABIERTO
                self._abierto_desde = self._reloj()
        return False


_disyuntores: dict[str, Disyuntor] = {}


def disyuntor_de(destino: str) -> Disyuntor:
    if destino not in _disyuntores:
        _disyuntores[destino] = Disyuntor(destino)
    return _disyuntores[destino]


reintentar_get = retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=0.2, max=2.0),
    retry=retry_if_not_exception_type(CircuitoAbierto),
    reraise=True,
)


def llamada_protegida(destino: str, *, metodo: str, reintentable: bool = False) -> Disyuntor:
    if reintentable and metodo.upper() != "GET":
        raise ValueError(
            f"reintentable=True solo se permite en GET idempotentes, no en {metodo.upper()}: "
            "reintentar una escritura a nivel de transporte es un doble cobro. "
            "Protege la escritura con idempotencia de aplicacion (clave + dedup)."
        )
    return disyuntor_de(destino)


_CAIDAS_POR_NOMBRE = frozenset(
    {
        "OperatorInterventionError",
        "PostgresConnectionError",
        "TooManyConnectionsError",
        "ChannelInvalidStateError",
        "DeliveryError",
    }
)
_OSERROR_DE_ARCHIVOS = (
    FileNotFoundError,
    FileExistsError,
    IsADirectoryError,
    NotADirectoryError,
    PermissionError,
)


def _eslabones(error: BaseException) -> Iterator[BaseException]:
    vistos: set[int] = set()
    actual: BaseException | None = error
    while actual is not None and id(actual) not in vistos:
        vistos.add(id(actual))
        yield actual
        original = getattr(actual, "orig", None)
        actual = original if isinstance(original, BaseException) else actual.__cause__


def es_caida_transitoria(error: BaseException) -> bool:
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
