"""Supresion del titular en Inteligencia (Ley 1581).

Decisiones:
- Se borran `trabajo_pipeline.preferencias_cifradas`, `kit.pesos_usados_cifrados`, `apodo_subida` y
  `importacion_lista.documento` y `carga`; se quita el apodo de cada hijo y se suelta
  `contacto_referencia`. Una importacion pendiente queda `fallida` con el diagnostico
  `titular_suprimido`.
- Se conservan los kits, sus lineas, su total y el texto de los renglones, que es la lista del
  colegio y no un dato del titular. `hijos` queda solo con referencia, colegio y grado y
  `usuario_id` queda como referencia seudonima.
"""

from __future__ import annotations

import argparse
import asyncio
from dataclasses import dataclass

from sqlalchemy import delete, select, update
from tukit_comun.bandeja import Resultado
from tukit_comun.bd import MotorServicio, crear_motor
from tukit_comun.broker import url_broker
from tukit_comun.consumidor import Consumidor, consumir
from tukit_comun.mensajes import Evento
from tukit_comun.registro import configurar_registro
from tukit_comun.supresion import TITULAR_SUPRIMIDO, anotar_confirmacion, supresion_de
from tukit_comun.topologia import SUPRESION_INTELIGENCIA

from .modelos import Base

_TRABAJO = Base.metadata.tables["trabajo_pipeline"]
_KIT = Base.metadata.tables["kit"]
_IMPORTACION = Base.metadata.tables["importacion_lista"]
_APODO_SUBIDA = Base.metadata.tables["apodo_subida"]
_BANDEJA = Base.metadata.tables["bandeja_salida"]

SERVICIO = "inteligencia"
DIAGNOSTICO = "titular_suprimido"


@dataclass
class Supresor:
    motor: MotorServicio

    async def manejar(self, evento: Evento) -> Resultado:
        if evento.tipo != TITULAR_SUPRIMIDO:
            return Resultado.OMITIR
        supresion = supresion_de(evento.carga)
        if supresion is None:
            return Resultado.OMITIR
        uid = supresion.usuario_id
        async with self.motor.engine.begin() as conexion:
            trabajos = select(_TRABAJO.c.id).where(_TRABAJO.c.usuario_id == uid)
            await conexion.execute(
                update(_TRABAJO).where(_TRABAJO.c.usuario_id == uid).values(preferencias_cifradas=None)
            )
            filas = await conexion.execute(
                select(_TRABAJO.c.id, _TRABAJO.c.hijos).where(_TRABAJO.c.usuario_id == uid)
            )
            for trabajo_id, hijos in filas.all():
                if any(isinstance(h, dict) and "apodo" in h for h in hijos or ()):
                    limpios = [
                        {k: v for k, v in h.items() if k != "apodo"} if isinstance(h, dict) else h
                        for h in hijos
                    ]
                    await conexion.execute(
                        update(_TRABAJO).where(_TRABAJO.c.id == trabajo_id).values(hijos=limpios)
                    )
            await conexion.execute(
                update(_KIT).where(_KIT.c.trabajo_id.in_(trabajos)).values(pesos_usados_cifrados=None)
            )
            suyas = _IMPORTACION.c.contacto_referencia == str(uid)
            await conexion.execute(
                update(_IMPORTACION)
                .where(suyas, _IMPORTACION.c.estado == "pendiente")
                .values(estado="fallida", error=DIAGNOSTICO)
            )
            await conexion.execute(
                update(_IMPORTACION).where(suyas).values(documento=None, carga=None, contacto_referencia=None)
            )
            await conexion.execute(
                delete(_APODO_SUBIDA).where(_APODO_SUBIDA.c.contacto_referencia == str(uid))
            )
            await anotar_confirmacion(conexion, _BANDEJA, supresion, SERVICIO)
        return Resultado.HECHO


async def escuchar_cola(url: str, *, seguir: bool, intervalo: float = 5.0) -> int:
    motor = crear_motor(SERVICIO)
    try:
        return await consumir(
            url,
            Consumidor(cola=SUPRESION_INTELIGENCIA, manejar=Supresor(motor).manejar),
            seguir=seguir,
            proceso="inteligencia-supresion",
            intervalo=intervalo,
        )
    finally:
        await motor.cerrar()


def main(argv: list[str] | None = None) -> int:
    analizador = argparse.ArgumentParser(description="Atiende la supresion del titular en Inteligencia.")
    analizador.add_argument("--seguir", action="store_true", help="Escucha en vez de una pasada.")
    analizador.add_argument("--intervalo", type=float, default=5.0, help="Segundos entre reconexiones.")
    argumentos = analizador.parse_args(argv)
    configurar_registro("inteligencia-supresion")
    url = url_broker()
    if not url:
        print("[supresion-inteligencia] falta RABBITMQ_URL; la supresion viaja solo por el broker.")
        return 2
    procesados = asyncio.run(escuchar_cola(url, seguir=argumentos.seguir, intervalo=argumentos.intervalo))
    if not argumentos.seguir:
        print(f"[supresion-inteligencia] mensajes de {SUPRESION_INTELIGENCIA.nombre}: {procesados}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["DIAGNOSTICO", "SERVICIO", "Supresor", "escuchar_cola", "main"]
