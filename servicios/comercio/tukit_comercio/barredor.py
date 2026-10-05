"""El barredor de reservas vencidas: la compensacion C1 de la saga (ADR 0023).

Si un acudiente crea la orden (T1: reserva + pedido `pendiente_pago`) pero nunca
paga, la reserva de inventario queda tomada para siempre —el unico gap real de
consistencia del flujo de compra—. Este proceso lo cierra: toma las reservas
`activa` de pedidos sin pagar mas viejas que el TTL (con el mismo `SELECT … FOR
UPDATE SKIP LOCKED` del outbox, ADR 0022), las marca `liberada` y cancela el
pedido abandonado.

    python -m tukit_comercio.barredor          # una pasada
    python -m tukit_comercio.barredor --seguir  # bucle

La decision de QUE reservas vencieron es pura (`dominio/saga.reservas_vencidas`);
aqui vive solo el I/O: el join reserva↔pedido, el SKIP LOCKED y la escritura. El
TTL sale del entorno (`TUKIT_TTL_RESERVA_MIN`), con el default conservador del
dominio; es la deuda que el ADR declara calibrar con datos de piloto.
"""

from __future__ import annotations

import argparse
import asyncio
import os
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select, update
from tukit_comun.bd import crear_motor

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
    """Una pasada: libera las reservas vencidas y cancela sus pedidos. Devuelve cuantas.

    `ahora` se inyecta para probar el vencimiento sin esperar; en produccion es
    el reloj. El join trae el `pedido_estado` que la decision pura necesita.
    """
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
        # El pedido abandonado se cancela: es terminal y libera al acudiente de
        # una compra a medias. `pendiente_pago -> cancelado` es transicion legal.
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


async def _bucle(intervalo: float) -> None:
    while True:
        liberadas = await correr_una_vez()
        if liberadas:
            print(f"[barredor] reservas vencidas liberadas: {liberadas}")
        await asyncio.sleep(intervalo)


def main(argv: list[str] | None = None) -> int:
    analizador = argparse.ArgumentParser(
        description="Libera reservas de inventario cuyo pago no confirmo dentro del TTL (ADR 0023, C1)."
    )
    analizador.add_argument("--seguir", action="store_true", help="Corre en bucle en vez de una pasada.")
    analizador.add_argument("--intervalo", type=float, default=60.0, help="Segundos entre pasadas.")
    argumentos = analizador.parse_args(argv)

    if argumentos.seguir:
        asyncio.run(_bucle(argumentos.intervalo))
    else:
        liberadas = asyncio.run(correr_una_vez())
        print(f"[barredor] reservas vencidas liberadas: {liberadas}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["correr_una_vez", "main", "pasada"]
