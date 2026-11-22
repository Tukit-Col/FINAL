"""Supresion del titular en Operacion (Ley 1581).

Decisiones:
- Se redacta el texto libre de los casos: `asunto`, `descripcion` y el texto de cada entrada de la
  historia, donde la gente suele escribir su direccion o su celular.
- Se conservan estado, categoria, prioridad, origen, fechas y la estructura de la historia, que es
  la prueba de que la PQRS se atendio. `caso.usuario_id` se queda porque en Identidad ya no resuelve
  a nadie.
- El contacto nunca se guarda en Operacion y `notificacion` solo guarda plantilla y variables de
  negocio.
- `supresion_confirmada` se escribe en la bandeja en la misma transaccion; el proceso es idempotente.
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
from tukit_comun.topologia import SUPRESION_OPERACION

from .repositorios.casos import BANDEJA, CASO, EVENTO

SERVICIO = "operacion"

_CLAVES_TEXTO = ("texto",)


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
            casos = select(CASO.c.id).where(CASO.c.usuario_id == supresion.usuario_id)
            await conexion.execute(
                update(CASO)
                .where(CASO.c.usuario_id == supresion.usuario_id)
                .values(asunto=MARCA_SUPRIMIDO, descripcion=MARCA_SUPRIMIDO)
            )
            for fila in await conexion.execute(
                select(EVENTO.c.id, EVENTO.c.datos).where(EVENTO.c.caso_id.in_(casos))
            ):
                datos = dict(fila.datos or {})
                cambiados = {
                    c: MARCA_SUPRIMIDO for c in _CLAVES_TEXTO if c in datos and datos[c] != MARCA_SUPRIMIDO
                }
                if cambiados:
                    await conexion.execute(
                        update(EVENTO).where(EVENTO.c.id == fila.id).values(datos={**datos, **cambiados})
                    )
            await anotar_confirmacion(conexion, BANDEJA, supresion, SERVICIO)
        return Resultado.HECHO


async def escuchar_cola(url: str, *, seguir: bool, intervalo: float = 5.0) -> int:
    motor = crear_motor(SERVICIO)
    try:
        return await consumir(
            url,
            Consumidor(cola=SUPRESION_OPERACION, manejar=Supresor(motor).manejar),
            seguir=seguir,
            proceso="operacion-supresion",
            intervalo=intervalo,
        )
    finally:
        await motor.cerrar()


def main(argv: list[str] | None = None) -> int:
    analizador = argparse.ArgumentParser(description="Atiende la supresion del titular en Operacion.")
    analizador.add_argument("--seguir", action="store_true", help="Escucha en vez de una pasada.")
    analizador.add_argument("--intervalo", type=float, default=5.0, help="Segundos entre reconexiones.")
    argumentos = analizador.parse_args(argv)
    configurar_registro("operacion-supresion")
    url = url_broker()
    if not url:
        print("[supresion-operacion] falta RABBITMQ_URL; la supresion viaja solo por el broker.")
        return 2
    procesados = asyncio.run(escuchar_cola(url, seguir=argumentos.seguir, intervalo=argumentos.intervalo))
    if not argumentos.seguir:
        print(f"[supresion-operacion] mensajes de {SUPRESION_OPERACION.nombre}: {procesados}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["SERVICIO", "Supresor", "escuchar_cola", "main"]
