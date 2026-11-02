"""La topologia de las colas en RabbitMQ: exchange, colas y descartados (ADR 0046).

Vive en un solo lugar porque la declaran los dos extremos. Cada publicador de
bandeja la declara antes de publicar y cada consumidor antes de escuchar: asi da
igual quien arranca primero, y un evento publicado antes de que su consumidor
exista no se pierde, porque su cola ya esta atada al exchange.

Por consumidor hay tres colas, todas clasicas y durables:

- **La principal** (`operacion.avisos`, ...), atada a `tukit.eventos` por el
  tipo de cada evento que le toca. Lo que rechaza sin reencolar va a la de
  descartados (dead-letter por el exchange por omision).
- **`<cola>.reintentos`**: el consumidor deja aqui un mensaje que fallo, con su
  intento en la cabecera `tukit-intentos`. Nadie la escucha: cuando vence su
  TTL, RabbitMQ lo devuelve a la principal. Es la espera entre intentos.
- **`<cola>.descartados`**: lo que agoto sus intentos o no se pudo leer. Queda
  ahi, visible en la consola, hasta que alguien lo mire.

`x-queue-type: classic` se declara aunque sea el tipo por omision: un 4.x con
otro tipo por omision (`default_queue_type`) cambiaria la semantica de las colas
sin avisar. Las colas son durables porque RabbitMQ 4 rechaza las transitorias
que no son exclusivas. Declarar es idempotente mientras los argumentos no
cambien; cambiarlos exige borrar la cola antes (RabbitMQ responde
`PRECONDITION_FAILED`, y eso tumba el proceso: es configuracion, no una caida).

`aio-pika` se importa dentro de `declarar`, como en `broker.py`: las pruebas con
dobles y los procesos sin broker no lo cargan.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any

from .broker import EXCHANGE

# La espera entre intentos de un mensaje que fallo. Es el TTL de la cola de
# reintentos, asi que cambiarlo exige borrar esa cola en el broker.
ESPERA_REINTENTO_MS = 10_000
# La cabecera que cuenta los intentos fallidos de un mensaje.
CABECERA_INTENTOS = "tukit-intentos"
# Por que se descarto un mensaje, para quien lo mire en la consola.
CABECERA_MOTIVO = "tukit-motivo"


@dataclass(frozen=True)
class Cola:
    """La cola de un consumidor y los tipos de evento que recibe."""

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


# Las claves de los avisos son las plantillas del repartidor de Operacion; una
# prueba del servicio fija que no se separen.
AVISOS = Cola(
    "operacion.avisos",
    (
        "kits_publicados",
        "pedido_pagado",
        "incidencia",
        "pedido_despachado",
        "pedido_en_reparto",
        "pedido_entregado",
        # Respuesta del back-office a un caso (S5): aviso por plantilla, sin el texto.
        "caso_respuesta",
    ),
)
COLEGIOS = Cola("identidad.colegios", ("colegio_verificado",))
LISTAS = Cola("inteligencia.listas", ("lista_verificada", "lista_aprobada"))
TRABAJOS = Cola("inteligencia.trabajos", ("trabajo_encolado",))
# La supresion del titular (Ley 1581, ADR 0048): Identidad publica
# `titular_suprimido` y cada servicio con datos del titular tiene su cola, asi
# que el mismo evento llega a los tres. Cada uno confirma con
# `supresion_confirmada`, que Identidad recoge en la suya.
SUPRESION_COMERCIO = Cola("comercio.supresion", ("titular_suprimido",))
SUPRESION_OPERACION = Cola("operacion.supresion", ("titular_suprimido",))
SUPRESION_INTELIGENCIA = Cola("inteligencia.supresion", ("titular_suprimido",))
SUPRESION_CONFIRMADA = Cola("identidad.supresion", ("supresion_confirmada",))


@dataclass(frozen=True)
class Topologia:
    """El exchange y las colas que se declaran juntos."""

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
        """La cola llamada `nombre` (sin prefijo), o `KeyError`."""
        for cola in self.colas:
            if cola.nombre == nombre or cola.nombre.endswith(f".{nombre}"):
                return cola
        raise KeyError(nombre)

    def con_prefijo(self, prefijo: str, *, espera_reintento_ms: int | None = None) -> Topologia:
        """La misma topologia con otros nombres, para que una prueba contra un
        broker de verdad no toque las colas de quien lo esta usando."""
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
    """Declara las tres colas de un consumidor y ata la principal al exchange.
    Devuelve la principal."""
    await canal.declare_queue(cola.descartados, durable=True, arguments=cola.argumentos_descartados())
    await canal.declare_queue(cola.reintentos, durable=True, arguments=cola.argumentos_reintentos())
    principal = await canal.declare_queue(cola.nombre, durable=True, arguments=cola.argumentos())
    for clave in cola.claves:
        await principal.bind(exchange, routing_key=clave)
    return principal


async def declarar(canal: Any, topologia: Topologia = TOPOLOGIA) -> tuple[Any, dict[str, Any]]:
    """Declara el exchange y todas las colas. Devuelve el exchange y las colas
    principales por nombre."""
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
