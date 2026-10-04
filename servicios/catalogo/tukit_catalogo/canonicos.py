"""Pone al dia los kits canonicos de las listas que se aprobaron antes de que existieran.

Desde que aprobar una lista emite `lista_aprobada` (ver `admin_http.cerrar_version`),
Inteligencia arma los kits canonicos de cada version al aprobarla. Las listas
aprobadas ANTES de ese cambio no tienen evento, y su grado solo tiene canonico si
algun acudiente llego a publicar el suyo. Este modulo les emite el evento que
les falto, para que el poller de Inteligencia los arme igual que a las nuevas.

Es idempotente: una version que ya tiene un `lista_aprobada` en la bandeja
(procesado o no) no recibe otro, asi que correrlo dos veces no arma dos veces.
Solo cuentan las versiones VIGENTES y revisadas: una version vieja ya no es la
que ve el acudiente.

    python -m tukit_catalogo.canonicos            # dice cuantas faltan, sin tocar nada
    python -m tukit_catalogo.canonicos --emitir   # les deja el evento
"""

from __future__ import annotations

import argparse
import asyncio
from typing import Any

from sqlalchemy import select

from .modelos import Base

LISTA = Base.metadata.tables["lista_oficial"]
VERSION = Base.metadata.tables["version_lista_oficial"]
BANDEJA = Base.metadata.tables["bandeja_salida"]

TIPO = "lista_aprobada"


async def versiones_sin_canonico(conexion: Any) -> list[Any]:
    """Las versiones vigentes y revisadas que nunca emitieron `lista_aprobada`."""
    ya = select(BANDEJA.c.agregado_id).where(BANDEJA.c.tipo == TIPO)
    return list(
        await conexion.execute(
            select(VERSION.c.id, LISTA.c.colegio_id, LISTA.c.grado, LISTA.c.anio_lectivo)
            .select_from(VERSION.join(LISTA, LISTA.c.id == VERSION.c.lista_id))
            .where(
                VERSION.c.revisada_en.is_not(None),
                VERSION.c.vigente.is_(True),
                VERSION.c.id.not_in(ya),
            )
            .order_by(LISTA.c.colegio_id, LISTA.c.grado)
        )
    )


async def emitir(conexion: Any) -> int:
    """Deja un `lista_aprobada` por cada version que no lo tiene. Devuelve cuantos."""
    faltan = await versiones_sin_canonico(conexion)
    for v in faltan:
        await conexion.execute(
            BANDEJA.insert().values(
                tipo=TIPO,
                agregado_tipo="version_lista_oficial",
                agregado_id=v.id,
                carga={
                    "colegio_id": str(v.colegio_id),
                    "grado": v.grado,
                    "anio_lectivo": v.anio_lectivo,
                },
            )
        )
    return len(faltan)


async def _correr(escribir: bool) -> int:
    from tukit_comun.bd import crear_motor

    motor = crear_motor("catalogo")
    try:
        async with motor.engine.begin() as conexion:
            if escribir:
                return await emitir(conexion)
            return len(await versiones_sin_canonico(conexion))
    finally:
        await motor.cerrar()


def main(argv: list[str] | None = None) -> int:
    analizador = argparse.ArgumentParser(
        description="Emite `lista_aprobada` para las listas aprobadas que no tienen kits canonicos."
    )
    analizador.add_argument("--emitir", action="store_true", help="Escribe los eventos (si no, solo cuenta).")
    argumentos = analizador.parse_args(argv)

    cuantas = asyncio.run(_correr(argumentos.emitir))
    if argumentos.emitir:
        print(f"[canonicos] eventos emitidos: {cuantas}. El poller de Inteligencia arma los kits.")
    else:
        print(f"[canonicos] listas aprobadas sin kits canonicos: {cuantas}. Usa --emitir para armarlos.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
