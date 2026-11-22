from __future__ import annotations

import enum

from sqlalchemy import JSON
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


Texto = JSON().with_variant(JSONB(), "postgresql")


class EstadoPedido(enum.StrEnum):
    PENDIENTE_PAGO = "pendiente_pago"
    PAGADO = "pagado"
    EN_PREPARACION = "en_preparacion"
    DESPACHADO = "despachado"
    EN_REPARTO = "en_reparto"
    ENTREGADO = "entregado"
    INCIDENCIA = "incidencia"
    CANCELADO = "cancelado"


TRANSICIONES_PEDIDO: dict[EstadoPedido, frozenset[EstadoPedido]] = {
    EstadoPedido.PENDIENTE_PAGO: frozenset({EstadoPedido.PAGADO, EstadoPedido.CANCELADO}),
    EstadoPedido.PAGADO: frozenset(
        {EstadoPedido.EN_PREPARACION, EstadoPedido.INCIDENCIA, EstadoPedido.CANCELADO}
    ),
    EstadoPedido.EN_PREPARACION: frozenset({EstadoPedido.DESPACHADO, EstadoPedido.INCIDENCIA}),
    EstadoPedido.DESPACHADO: frozenset({EstadoPedido.EN_REPARTO, EstadoPedido.INCIDENCIA}),
    EstadoPedido.EN_REPARTO: frozenset({EstadoPedido.ENTREGADO, EstadoPedido.INCIDENCIA}),
    EstadoPedido.ENTREGADO: frozenset(),
    EstadoPedido.INCIDENCIA: frozenset({EstadoPedido.EN_PREPARACION, EstadoPedido.CANCELADO}),
    EstadoPedido.CANCELADO: frozenset(),
}


def transicion_valida(actual: str, siguiente: str) -> bool:
    try:
        desde = EstadoPedido(actual)
        hacia = EstadoPedido(siguiente)
    except ValueError:
        return False
    return hacia in TRANSICIONES_PEDIDO[desde]


class EstadoPago(enum.StrEnum):
    INICIADO = "iniciado"
    APROBADO = "aprobado"
    RECHAZADO = "rechazado"
    REEMBOLSADO = "reembolsado"


class MetodoPago(enum.StrEnum):
    PSE = "pse"
    NEQUI = "nequi"
    TARJETA = "tarjeta"
