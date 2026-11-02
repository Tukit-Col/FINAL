"""La supresion del titular en Comercio (Ley 1581, ADR 0048).

Identidad publica `titular_suprimido` cuando un acudiente pide borrar sus datos.
Este proceso lo consume de `comercio.supresion` y hace la parte de Comercio:

- **Enmascara** la copia congelada del envio de cada pedido del titular: el
  destinatario y la direccion quedan con la marca, y el telefono, el documento,
  las indicaciones y el lugar de Google quedan vacios. El motivo libre de sus
  devoluciones tambien se reemplaza: es texto que el titular escribio.
- **Conserva** el pedido, sus lineas, sus pagos, su historial y la ciudad y
  localidad del envio. La ley obliga a guardar los soportes contables diez anos
  (ET art. 632, C.Co. art. 60) y lo necesario para la garantia y el retracto
  (Ley 1480 arts. 7 y 47). `pedido.usuario_id` se queda: en Identidad ya no
  resuelve a nadie.
- **Confirma** escribiendo `supresion_confirmada` en su propia bandeja, en la
  misma transaccion que el enmascarado. El publicador de Comercio la lleva a
  Identidad, que cierra la solicitud cuando confirman los tres.

Es idempotente: enmascarar lo ya enmascarado deja la base igual y la
confirmacion no se repite, asi que un evento que el broker entrega dos veces no
rompe nada.

    python -m tukit_comercio.supresion           # lo que hay en la cola
    python -m tukit_comercio.supresion --seguir  # escucha

Solo con RabbitMQ: sin broker no hay de donde recibir el evento sin abrir la
base de Identidad, y esa lectura cruzada no se agrega por esto.
"""

from __future__ import annotations

import argparse
import asyncio
from dataclasses import dataclass

from sqlalchemy import select, update
from tukit_comun.bandeja import Resultado
from tukit_comun.bd import MotorServicio, crear_motor
from tukit_comun.broker import url_broker
from tukit_comun.consumidor import Consumidor, consumir
from tukit_comun.mensajes import Evento
from tukit_comun.registro import configurar_registro
from tukit_comun.supresion import MARCA_SUPRIMIDO, TITULAR_SUPRIMIDO, anotar_confirmacion, supresion_de
from tukit_comun.topologia import SUPRESION_COMERCIO

from .modelos import Base

_PEDIDO = Base.metadata.tables["pedido"]
_ENVIO = Base.metadata.tables["envio"]
_DEVOLUCION = Base.metadata.tables["devolucion"]
_BANDEJA = Base.metadata.tables["bandeja_salida"]

SERVICIO = "comercio"


@dataclass
class Supresor:
    """Enmascara lo del titular y confirma. El motor se inyecta para probar sin Postgres."""

    motor: MotorServicio

    async def manejar(self, evento: Evento) -> Resultado:
        if evento.tipo != TITULAR_SUPRIMIDO:
            return Resultado.OMITIR
        supresion = supresion_de(evento.carga)
        if supresion is None:
            return Resultado.OMITIR
        async with self.motor.engine.begin() as conexion:
            pedidos = select(_PEDIDO.c.id).where(_PEDIDO.c.usuario_id == supresion.usuario_id)
            await conexion.execute(
                update(_ENVIO)
                .where(_ENVIO.c.pedido_id.in_(pedidos))
                .values(
                    destinatario=MARCA_SUPRIMIDO,
                    direccion=MARCA_SUPRIMIDO,
                    telefono=None,
                    documento_destinatario=None,
                    indicaciones=None,
                    google_place_id=None,
                )
            )
            await conexion.execute(
                update(_DEVOLUCION)
                .where(_DEVOLUCION.c.usuario_id == supresion.usuario_id)
                .values(motivo=MARCA_SUPRIMIDO)
            )
            await anotar_confirmacion(conexion, _BANDEJA, supresion, SERVICIO)
        return Resultado.HECHO


async def escuchar_cola(url: str, *, seguir: bool, intervalo: float = 5.0) -> int:
    """Consume `comercio.supresion`. Solo abre la base de Comercio."""
    motor = crear_motor(SERVICIO)
    try:
        return await consumir(
            url,
            Consumidor(cola=SUPRESION_COMERCIO, manejar=Supresor(motor).manejar),
            seguir=seguir,
            proceso="comercio-supresion",
            intervalo=intervalo,
        )
    finally:
        await motor.cerrar()


def main(argv: list[str] | None = None) -> int:
    analizador = argparse.ArgumentParser(description="Atiende la supresion del titular en Comercio.")
    analizador.add_argument("--seguir", action="store_true", help="Escucha en vez de una pasada.")
    analizador.add_argument("--intervalo", type=float, default=5.0, help="Segundos entre reconexiones.")
    argumentos = analizador.parse_args(argv)
    configurar_registro("comercio-supresion")
    url = url_broker()
    if not url:
        print("[supresion-comercio] falta RABBITMQ_URL; la supresion viaja solo por el broker.")
        return 2
    procesados = asyncio.run(escuchar_cola(url, seguir=argumentos.seguir, intervalo=argumentos.intervalo))
    if not argumentos.seguir:
        print(f"[supresion-comercio] mensajes de {SUPRESION_COMERCIO.nombre}: {procesados}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["SERVICIO", "Supresor", "escuchar_cola", "main"]
