"""Base declarativa y vocabulario del servicio de Comercio.

Los enums de aqui son los del contrato de lectura (`libs/ts/tukit-contrato/
src/comercio.ts`), no una traduccion suya. La maquina de estados del pedido
vive como dato (`TRANSICIONES_PEDIDO`) y no como una cadena de `if`, por la
misma razon que en Inteligencia: la pregunta que hay que responder rapido es
"por que esta transicion es ilegal", y un diccionario la responde solo. Es el
mismo idiom que `EstadoMatricula.cerrados()` en Identidad.
"""

from __future__ import annotations

import enum

from sqlalchemy import JSON
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


# Nativo en Postgres, degradado en SQLite, para que el mismo modelo corra en la
# prueba y en el motor real. Mismo criterio que Catalogo e Inteligencia.
Texto = JSON().with_variant(JSONB(), "postgresql")


class EstadoPedido(enum.StrEnum):
    """El ciclo de vida de un pedido, del pago a la puerta.

    Los ocho valores son los de `comercio.ts`. `incidencia` no es terminal: un
    pedido con problema de stock o de entrega puede volver a preparacion cuando
    se resuelve. `entregado` y `cancelado` si son terminales: son el final del
    camino y publicar dos veces sobre ellos no es idempotente sino un segundo
    aviso al acudiente.
    """

    PENDIENTE_PAGO = "pendiente_pago"
    PAGADO = "pagado"
    EN_PREPARACION = "en_preparacion"
    DESPACHADO = "despachado"
    EN_REPARTO = "en_reparto"
    ENTREGADO = "entregado"
    INCIDENCIA = "incidencia"
    CANCELADO = "cancelado"


# Desde donde se puede llegar a cada estado. La saga de pago del contrato hace
# observable justo esta progresion: pendiente_pago -> pagado en el webhook,
# luego el back-office de logistica lo empuja por la cadena de entrega. Una
# incidencia puede aparecer en cualquier punto posterior al pago y devuelve a
# preparacion o cancela; nunca se salta pasos hacia adelante.
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
    """Si la transicion de estado del pedido esta permitida.

    Se consulta antes de escribir para poder devolver `409` con un mensaje que
    diga desde donde y hacia donde. Acepta cadenas (lo que llega del enum de la
    columna) y no lanza ante un valor desconocido: devuelve `False`.
    """
    try:
        desde = EstadoPedido(actual)
        hacia = EstadoPedido(siguiente)
    except ValueError:
        return False
    return hacia in TRANSICIONES_PEDIDO[desde]


class EstadoPago(enum.StrEnum):
    """El estado del pago, lo unico que el contrato (§9) fija de la pasarela.

    `iniciado` es "creamos la transaccion en Wompi y esperamos"; los otros tres
    son el desenlace que llega por webhook. Nunca se guarda dato de tarjeta
    (SG-03): solo id de la pasarela y estado.
    """

    INICIADO = "iniciado"
    APROBADO = "aprobado"
    RECHAZADO = "rechazado"
    REEMBOLSADO = "reembolsado"


class MetodoPago(enum.StrEnum):
    """Los medios que Wompi ofrece y que el contrato expone. PSE es el del
    flujo principal (transferencia bancaria); Nequi y tarjeta quedan
    declarados porque la pasarela los soporta y el tipo `Pago` los admite."""

    PSE = "pse"
    NEQUI = "nequi"
    TARJETA = "tarjeta"
