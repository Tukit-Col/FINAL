"""Topologia de las colas en RabbitMQ: exchange, colas y descartados.

Decisiones:
- Se declara en un solo lugar porque la declaran los dos extremos (publicador y consumidor): da
  igual quien arranque primero y un evento publicado antes de que exista su consumidor no se pierde.
- Por consumidor hay tres colas durables: la principal, atada a `tukit.eventos` por tipo de evento;
  `<cola>.reintentos`, que devuelve el mensaje a la principal al vencer su TTL; y
  `<cola>.descartados`, donde queda lo que agoto sus intentos o no se pudo leer.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any

from .broker import EXCHANGE

ESPERA_REINTENTO_MS = 10_000
CABECERA_INTENTOS = "tukit-intentos"
CABECERA_MOTIVO = "tukit-motivo"


@dataclass(frozen=True)
class Cola:
    nombre: str
    claves: tuple[str, ...]
    espera_reintento_ms: int = ESPERA_REINTENTO_MS

    @property
    def reintentos(self) -> str:
        return f"{self.nombre}.reintentos"

    @property
    def descartados(self) -> str:
        return f"{self.nombre}.descartados"

    def argumentos(self) -> dict[str, Any]:
        return {
            "x-queue-type": "classic",
            "x-dead-letter-exchange": "",
            "x-dead-letter-routing-key": self.descartados,
        }

    def argumentos_reintentos(self) -> dict[str, Any]:
        return {
            "x-queue-type": "classic",
            "x-message-ttl": self.espera_reintento_ms,
            "x-dead-letter-exchange": "",
            "x-dead-letter-routing-key": self.nombre,
        }

    def argumentos_descartados(self) -> dict[str, Any]:
        return {"x-queue-type": "classic"}


AVISOS = Cola(
    "operacion.avisos",
    (
        "kits_publicados",
        "pedido_pagado",
        "incidencia",
        "pedido_en_preparacion",
        "pedido_despachado",
        "pedido_en_reparto",
        "pedido_entregado",
        "pedido_cancelado",
        "caso_respuesta",
    ),
)
COLEGIOS = Cola("identidad.colegios", ("colegio_verificado",))
LISTAS = Cola("inteligencia.listas", ("lista_verificada", "lista_aprobada"))
TRABAJOS = Cola("inteligencia.trabajos", ("trabajo_encolado",))
SUPRESION_COMERCIO = Cola("comercio.supresion", ("titular_suprimido",))
SUPRESION_OPERACION = Cola("operacion.supresion", ("titular_suprimido",))
SUPRESION_INTELIGENCIA = Cola("inteligencia.supresion", ("titular_suprimido",))
SUPRESION_CONFIRMADA = Cola("identidad.supresion", ("supresion_confirmada",))


@dataclass(frozen=True)
class Topologia:
    exchange: str = EXCHANGE
    colas: tuple[Cola, ...] = field(
        default=(
            AVISOS,
            COLEGIOS,
            LISTAS,
            TRABAJOS,
            SUPRESION_COMERCIO,
            SUPRESION_OPERACION,
            SUPRESION_INTELIGENCIA,
            SUPRESION_CONFIRMADA,
        )
    )

    def cola(self, nombre: str) -> Cola:
        for cola in self.colas:
            if cola.nombre == nombre or cola.nombre.endswith(f".{nombre}"):
                return cola
        raise KeyError(nombre)

    def con_prefijo(self, prefijo: str, *, espera_reintento_ms: int | None = None) -> Topologia:
        colas = tuple(
            replace(
                cola,
                nombre=f"{prefijo}.{cola.nombre}",
                espera_reintento_ms=espera_reintento_ms or cola.espera_reintento_ms,
            )
            for cola in self.colas
        )
        return Topologia(exchange=f"{prefijo}.{self.exchange}", colas=colas)


TOPOLOGIA = Topologia()


async def declarar_cola(canal: Any, cola: Cola, exchange: Any) -> Any:
    await canal.declare_queue(cola.descartados, durable=True, arguments=cola.argumentos_descartados())
    await canal.declare_queue(cola.reintentos, durable=True, arguments=cola.argumentos_reintentos())
    principal = await canal.declare_queue(cola.nombre, durable=True, arguments=cola.argumentos())
    for clave in cola.claves:
        await principal.bind(exchange, routing_key=clave)
    return principal


async def declarar(canal: Any, topologia: Topologia = TOPOLOGIA) -> tuple[Any, dict[str, Any]]:
    import aio_pika

    exchange = await canal.declare_exchange(topologia.exchange, aio_pika.ExchangeType.TOPIC, durable=True)
    colas = {cola.nombre: await declarar_cola(canal, cola, exchange) for cola in topologia.colas}
    return exchange, colas


__all__ = [
    "AVISOS",
    "CABECERA_INTENTOS",
    "CABECERA_MOTIVO",
    "COLEGIOS",
    "ESPERA_REINTENTO_MS",
    "LISTAS",
    "SUPRESION_COMERCIO",
    "SUPRESION_CONFIRMADA",
    "SUPRESION_INTELIGENCIA",
    "SUPRESION_OPERACION",
    "TOPOLOGIA",
    "TRABAJOS",
    "Cola",
    "Topologia",
    "declarar",
    "declarar_cola",
]
