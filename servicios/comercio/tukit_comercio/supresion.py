"""Supresion del titular en Comercio (Ley 1581).

Decisiones:
- Se enmascara la copia congelada del envio de cada pedido del titular (destinatario, direccion,
  telefono, documento e indicaciones) y el motivo libre de sus devoluciones.
- Se conservan el pedido, sus lineas, pagos e historial, y la ciudad y localidad del envio: la ley
  obliga a guardar los soportes contables y lo necesario para la garantia y el retracto.
- La confirmacion `supresion_confirmada` se escribe en la bandeja en la misma transaccion que el
  enmascarado.
- Es idempotente: enmascarar lo ya enmascarado no cambia nada, asi que una entrega doble del broker
  no rompe nada.
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
                    latitud=None,
                    longitud=None,
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
