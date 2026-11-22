"""La saga orden, pago y despacho, nombrada y con su compensacion pura.

Decisiones:
- La compra cruza dos servicios y una pasarela externa y no cabe en una transaccion: es una saga por
  coreografia, cada servicio reacciona a los eventos que le competen (outbox o broker) sin
  orquestador central.
- T1 reserva inventario y crea el pedido; T2 inicia el cobro; T3 confirma por webhook idempotente y
  emite `pedido_pagado`; T4 despacha (al menos una vez, no compensable).
- Compensaciones: C3 reembolso (`retractar_orden`) y C1 liberar la reserva por vencimiento
  (`reservas_vencidas`, que aplica el barredor).
- `PASOS` documenta la saga como dato en un solo lugar.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

TTL_RESERVA = timedelta(hours=24)

_ACTIVA = "activa"

_SIN_PAGAR = "pendiente_pago"


@dataclass(frozen=True)
class Paso:

    paso: str
    accion: str
    compensacion: str | None


PASOS: tuple[Paso, ...] = (
    Paso("T1", "reservar inventario + crear pedido", "C1: liberar la reserva por vencimiento"),
    Paso("T2", "iniciar el cobro contra la pasarela", "C1 si T2 nunca confirma (la reserva vence)"),
    Paso("T3", "confirmar por webhook idempotente → pedido_pagado", "C3: reembolso (retractar_orden)"),
    Paso("T4", "despachar (Operacion drena pedido_pagado)", None),
)


def reservas_vencidas(filas: Iterable[Any], *, ahora: datetime, ttl: timedelta = TTL_RESERVA) -> list[Any]:
    corte = ahora - ttl

    def _viejo(f: Any) -> bool:
        creado = f.creado_en
        if creado.tzinfo is None:
            creado = creado.replace(tzinfo=UTC)
        return creado < corte

    return [f for f in filas if f.estado == _ACTIVA and f.pedido_estado == _SIN_PAGAR and _viejo(f)]


__all__ = ["PASOS", "TTL_RESERVA", "Paso", "reservas_vencidas"]
