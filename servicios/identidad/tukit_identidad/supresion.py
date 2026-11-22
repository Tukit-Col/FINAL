"""Cierre de la solicitud de supresion del titular (Ley 1581).

Decisiones:
- `suprimir_titular` anonimiza lo de Identidad, deja la solicitud en `propagando` y escribe
  `titular_suprimido` en la bandeja. Comercio, Operacion e Inteligencia borran lo suyo y responden
  `supresion_confirmada`; la solicitud pasa a `completada` solo cuando estan las tres.
- Es idempotente: `confirmar` no repite un servicio ya anotado y una solicitud cerrada no se
  reabre. Una confirmacion de un servicio que no es suscriptor o de una solicitud inexistente se
  omite, porque reintentarla no la arregla.
"""

from __future__ import annotations

import argparse
import asyncio
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from tukit_comun.bandeja import Resultado
from tukit_comun.bd import MotorServicio, crear_motor
from tukit_comun.broker import url_broker
from tukit_comun.consumidor import Consumidor, consumir
from tukit_comun.mensajes import Evento
from tukit_comun.registro import configurar_registro
from tukit_comun.supresion import SUPRESION_CONFIRMADA, SUSCRIPTORES_SUPRESION
from tukit_comun.topologia import SUPRESION_CONFIRMADA as COLA_CONFIRMADA

from .modelos import SolicitudSupresion

_ABIERTAS = ("pendiente", "propagando")


@dataclass
class Cierre:

    motor: MotorServicio

    async def manejar(self, evento: Evento) -> Resultado:
        if evento.tipo != SUPRESION_CONFIRMADA:
            return Resultado.OMITIR
        carga = evento.carga or {}
        servicio = carga.get("servicio")
        if servicio not in SUSCRIPTORES_SUPRESION:
            return Resultado.OMITIR
        try:
            solicitud_id = uuid.UUID(str(carga["solicitud_id"]))
        except (KeyError, TypeError, ValueError):
            return Resultado.OMITIR
        async with self.motor.sesion() as db:
            solicitud = (
                await db.execute(
                    select(SolicitudSupresion).where(SolicitudSupresion.id == solicitud_id).with_for_update()
                )
            ).scalar_one_or_none()
            if solicitud is None:
                return Resultado.OMITIR
            if solicitud.estado not in _ABIERTAS:
                return Resultado.HECHO
            if solicitud.confirmar(servicio, SUSCRIPTORES_SUPRESION):
                solicitud.estado = "completada"
                solicitud.resuelto_en = datetime.now(UTC)
        return Resultado.HECHO


async def escuchar_cola(url: str, *, seguir: bool, intervalo: float = 5.0) -> int:
    motor = crear_motor("identidad")
    try:
        return await consumir(
            url,
            Consumidor(cola=COLA_CONFIRMADA, manejar=Cierre(motor).manejar),
            seguir=seguir,
            proceso="identidad-supresion",
            intervalo=intervalo,
        )
    finally:
        await motor.cerrar()


def main(argv: list[str] | None = None) -> int:
    analizador = argparse.ArgumentParser(description="Cierra las solicitudes de supresion confirmadas.")
    analizador.add_argument("--seguir", action="store_true", help="Escucha en vez de una pasada.")
    analizador.add_argument("--intervalo", type=float, default=5.0, help="Segundos entre reconexiones.")
    argumentos = analizador.parse_args(argv)
    configurar_registro("identidad-supresion")
    url = url_broker()
    if not url:
        print("[supresion-identidad] falta RABBITMQ_URL; la supresion viaja solo por el broker.")
        return 2
    procesados = asyncio.run(escuchar_cola(url, seguir=argumentos.seguir, intervalo=argumentos.intervalo))
    if not argumentos.seguir:
        print(f"[supresion-identidad] mensajes de {COLA_CONFIRMADA.nombre}: {procesados}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["Cierre", "escuchar_cola", "main"]
