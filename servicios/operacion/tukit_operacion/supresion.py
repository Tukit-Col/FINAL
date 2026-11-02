"""La supresion del titular en Operacion (Ley 1581, ADR 0048).

Identidad publica `titular_suprimido`; este proceso lo consume de
`operacion.supresion` y hace la parte de Operacion en los casos (PQRS) del
titular:

- **Redacta** el texto libre: `asunto`, `descripcion` y el `texto` de cada
  entrada de la historia (comentarios del acudiente y respuestas del equipo, que
  suelen repetir su nombre). Ahi es donde la gente escribe su direccion o su
  celular, aunque el formulario no lo pida.
- **Conserva** estado, categoria, prioridad, origen, fechas y la estructura de
  la historia (cambios de estado, asignaciones): es la prueba de que la PQRS se
  atendio (Ley 1581 art. 17, Decreto 1377). `caso.usuario_id` se queda porque en
  Identidad ya no resuelve a nadie.
- El contacto (correo, celular) nunca se guardo en Operacion: se resuelve
  contra Identidad en el momento del envio, y alli ya no existe. `notificacion`
  solo guarda plantilla y variables de negocio, sin texto del titular.
- **Confirma** con `supresion_confirmada` en su bandeja, en la misma transaccion.

Idempotente: redactar lo redactado deja la base igual y la confirmacion no se
repite.

    python -m tukit_operacion.supresion           # lo que hay en la cola
    python -m tukit_operacion.supresion --seguir  # escucha

Solo con RabbitMQ, como el de Comercio.
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

# Las claves de `evento_caso.datos` que llevan texto escrito por una persona.
_CLAVES_TEXTO = ("texto",)


@dataclass
class Supresor:
    """Redacta los casos del titular y confirma."""

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
            # La historia es JSON: se reescribe en Python solo la clave de texto.
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
    """Consume `operacion.supresion`. Solo abre la base de Operacion."""
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
