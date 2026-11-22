from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from ..modelos import EstadoPago, EstadoPedido

VIGENCIA_PAGO = timedelta(hours=24)

ESTADOS_PAGO_FINALES = (EstadoPago.APROBADO.value, EstadoPago.REEMBOLSADO.value)


def vencido(creado_en: datetime, ahora: datetime | None = None) -> bool:
    if creado_en.tzinfo is None:
        creado_en = creado_en.replace(tzinfo=UTC)
    return (ahora or datetime.now(UTC)) - creado_en > VIGENCIA_PAGO


CAMPOS_FIRMA_ENTREGA = (
    "destinatario",
    "direccion",
    "ciudad",
    "localidad",
    "departamento",
    "indicaciones",
    "telefono",
    "documento_destinatario",
    "latitud",
    "longitud",
)


def firma_orden(lineas: list[tuple[str, int, int]], entrega: tuple[str | None, ...]) -> tuple[Any, ...]:
    return (tuple(sorted(lineas)), tuple(campo or "" for campo in entrega))


def pedido_tras_pago(estado_pago: EstadoPago, estado_actual: str) -> str | None:
    if estado_pago == EstadoPago.APROBADO:
        return EstadoPedido.PAGADO.value
    return None
