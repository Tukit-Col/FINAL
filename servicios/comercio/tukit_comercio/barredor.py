"""Barredor de reservas vencidas: compensacion C1 de la saga de compra.

Decisiones:
- Una reserva `activa` de un pedido sin pagar mas vieja que el TTL (`TUKIT_TTL_RESERVA_MIN`) se
  marca `liberada` y el pedido abandonado se cancela; si no, el inventario queda tomado para siempre.
- La decision de que reservas vencieron es pura (`dominio/saga.reservas_vencidas`); aqui vive solo
  el I/O, con `SELECT ... FOR UPDATE SKIP LOCKED` como el outbox.
- El bucle corre sobre `bucle_resiliente`: si la base cae, espera con backoff y reconecta; un error
  de programacion termina el proceso.

Uso:  python -m tukit_comercio.barredor [--seguir]
"""

from __future__ import annotations

import argparse
import asyncio
import os
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select, update
from tukit_comun.bd import crear_motor
from tukit_comun.registro import configurar_registro
from tukit_comun.resiliencia import bucle_resiliente

from .dominio.saga import TTL_RESERVA, reservas_vencidas
from .modelos import Base, EstadoPedido

RESERVA = Base.metadata.tables["reserva_inventario"]
PEDIDO = Base.metadata.tables["pedido"]


def _ttl() -> timedelta:
    crudo = os.environ.get("TUKIT_TTL_RESERVA_MIN")
    if not crudo:
        return TTL_RESERVA
    return timedelta(minutes=float(crudo))


async def pasada(motor: Any, *, ahora: datetime | None = None, limite: int = 200) -> int:
    ahora = ahora or datetime.now(UTC)
    ttl = _ttl()
    async with motor.begin() as conexion:
        filas = list(
            await conexion.execute(
                select(
                    RESERVA.c.id,
                    RESERVA.c.pedido_id,
                    RESERVA.c.estado,
                    RESERVA.c.creado_en,
                    PEDIDO.c.estado.label("pedido_estado"),
                )
                .select_from(RESERVA.join(PEDIDO, RESERVA.c.pedido_id == PEDIDO.c.id))
                .where(RESERVA.c.estado == "activa")
                .limit(limite)
                .with_for_update(skip_locked=True)
            )
        )
        vencidas = reservas_vencidas(filas, ahora=ahora, ttl=ttl)
        if not vencidas:
            return 0
        ids_reserva = [f.id for f in vencidas]
        pedidos = {f.pedido_id for f in vencidas}
        await conexion.execute(update(RESERVA).where(RESERVA.c.id.in_(ids_reserva)).values(estado="liberada"))
        await conexion.execute(
            update(PEDIDO).where(PEDIDO.c.id.in_(pedidos)).values(estado=EstadoPedido.CANCELADO.value)
        )
        return len(ids_reserva)


async def correr_una_vez() -> int:
    motor = crear_motor("comercio")
    try:
        return await pasada(motor.engine)
    finally:
        await motor.cerrar()


async def _bucle(intervalo: float, *, dormir: Callable[[float], Awaitable[None]] | None = None) -> None:
    async def _vuelta() -> None:
        liberadas = await correr_una_vez()
        if liberadas:
            print(f"[barredor] reservas vencidas liberadas: {liberadas}")

    await bucle_resiliente(
        _vuelta, intervalo=intervalo, proceso="comercio-barredor", dormir=dormir or asyncio.sleep
    )


def main(argv: list[str] | None = None) -> int:
    analizador = argparse.ArgumentParser(
        description="Libera reservas de inventario cuyo pago no confirmo dentro del TTL (ADR 0023, C1)."
    )
    analizador.add_argument("--seguir", action="store_true", help="Corre en bucle en vez de una pasada.")
    analizador.add_argument("--intervalo", type=float, default=60.0, help="Segundos entre pasadas.")
    argumentos = analizador.parse_args(argv)
    configurar_registro("comercio-barredor")

    if argumentos.seguir:
        asyncio.run(_bucle(argumentos.intervalo))
    else:
        liberadas = asyncio.run(correr_una_vez())
        print(f"[barredor] reservas vencidas liberadas: {liberadas}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["correr_una_vez", "main", "pasada"]
