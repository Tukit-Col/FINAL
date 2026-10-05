"""La saga orden→pago→despacho, nombrada y con su compensacion pura (ADR 0023).

La compra cruza dos servicios y una pasarela externa; no cabe en una transaccion
de base. Se modela como saga por COREOGRAFIA: cada servicio reacciona a los
eventos que le competen (via outbox/broker, ADR 0022) y emite el suyo, sin
orquestador central. Las piezas ya existian dispersas:

- **T1** reservar inventario + crear pedido (`RepoPedidos.crear`).
- **T2** iniciar el cobro contra la pasarela.
- **T3** confirmar por webhook idempotente → emite `pedido_pagado` (ADR 0011).
- **T4** despachar (Operacion drena `pedido_pagado`) — at-least-once, NO compensable.

Compensaciones: **C3** reembolso (`retractar_orden`, ya existe); **C1** liberar
la reserva por vencimiento —el unico gap real de consistencia: inventario
bloqueado por una compra que nunca se pago—. `reservas_vencidas` es la decision
pura de C1 (que reservas liberar); el barredor (`barredor.py`) la aplica con el
mismo `SKIP LOCKED` del outbox.

`PASOS` documenta la saga como dato, en un solo lugar, para compensar que la
coreografia reparte el flujo entre servicios (la consecuencia declarada del ADR).
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

# TTL por omision de una reserva sin pago confirmado (ADR 0023 lo declara como
# deuda a calibrar con datos de piloto). Es la misma ventana en que el pedido se
# puede pagar (`pagos.VIGENCIA_PAGO`, 24 h): un PSE puede quedar en curso horas
# en el banco, y vencer la reserva antes cancelaria un pedido que el acudiente
# todavia puede pagar. Se sobreescribe por entorno en el barredor.
TTL_RESERVA = timedelta(hours=24)

# El estado de una reserva que aun cuenta contra el stock y puede vencer. Una
# `liberada` (ya la solto un barrido) o `consumida` (ya se despacho) no se toca.
_ACTIVA = "activa"

# El estado del pedido en el que una reserva puede vencer: si el pago ya llego
# (`pagado` y mas alla), la reserva se consume al despachar, no se libera.
_SIN_PAGAR = "pendiente_pago"


@dataclass(frozen=True)
class Paso:
    """Un paso de la saga y su compensacion (o `None` si es at-least-once)."""

    paso: str
    accion: str
    compensacion: str | None


# La saga completa como dato: un solo lugar que leer para entenderla, ya que la
# coreografia la reparte entre los manejadores de Comercio y Operacion.
PASOS: tuple[Paso, ...] = (
    Paso("T1", "reservar inventario + crear pedido", "C1: liberar la reserva por vencimiento"),
    Paso("T2", "iniciar el cobro contra la pasarela", "C1 si T2 nunca confirma (la reserva vence)"),
    Paso("T3", "confirmar por webhook idempotente → pedido_pagado", "C3: reembolso (retractar_orden)"),
    Paso("T4", "despachar (Operacion drena pedido_pagado)", None),
)


def reservas_vencidas(filas: Iterable[Any], *, ahora: datetime, ttl: timedelta = TTL_RESERVA) -> list[Any]:
    """Las reservas a liberar (C1): activas, de un pedido sin pagar, mas viejas que el TTL.

    `filas` son reservas con su `estado`, su `creado_en` y el `pedido_estado` del
    pedido al que pertenecen (el barredor hace el join). Pura: recibe el `ahora`
    en vez de leer el reloj, para probar el vencimiento sin esperar.
    """
    corte = ahora - ttl

    # SQLite devuelve `creado_en` naive; Postgres, aware. Se normaliza a UTC para
    # que la comparacion no reviente segun el motor (mismo esquema, distinto tipo).
    def _viejo(f: Any) -> bool:
        creado = f.creado_en
        if creado.tzinfo is None:
            creado = creado.replace(tzinfo=UTC)
        return creado < corte

    return [f for f in filas if f.estado == _ACTIVA and f.pedido_estado == _SIN_PAGAR and _viejo(f)]


__all__ = ["PASOS", "TTL_RESERVA", "Paso", "reservas_vencidas"]
