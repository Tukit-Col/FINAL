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

Se escribio a mano (sin `purgatory`) porque el estado del disyuntor son ~40
lineas puras y testeables con `assert`, y la unica libreria async del ecosistema
arrastra `pkg_resources` (setuptools<81, API ya marcada para eliminacion). El
backend es in-memory por proceso; para multi-replica se cambia el almacen del
estado sin tocar la interfaz (misma postura que el `Sink` del outbox).
"""

from __future__ import annotations

import time
from collections.abc import Callable
from enum import Enum
from typing import Any

from tenacity import retry, retry_if_not_exception_type, stop_after_attempt, wait_exponential

UMBRAL_POR_OMISION = 5
TTL_POR_OMISION = 30.0


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
