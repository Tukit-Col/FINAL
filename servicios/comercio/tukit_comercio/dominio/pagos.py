"""La consecuencia de un pago sobre el pedido, como dominio puro.

`pedido_tras_pago` decide a qué estado pasa el pedido según el resultado del
cobro. Ya era pura dentro de `api.py` (`_pedido_tras_pago`); se mueve aquí para
que el webhook sólo la consulte y persista, y para que la regla se pruebe sin
levantar la pasarela. El llamador sigue validando la transición contra
`transicion_valida` antes de escribir: esta función dice el destino deseado, no
que sea legal.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from ..modelos import EstadoPago, EstadoPedido

# Cuanto tiempo se puede pagar un pedido pendiente. Despues se cobraria un
# precio congelado viejo: el acudiente vuelve a armar el kit y el precio se
# re-verifica contra Catalogo. No hay columna nueva: sale de `creado_en`. Es
# tambien el TTL de la reserva (`saga.TTL_RESERVA`): un pedido que todavia se
# puede pagar no pierde su inventario.
VIGENCIA_PAGO = timedelta(hours=24)

# Un pago en uno de estos estados ya no se mueve: un evento tardio o fuera de
# orden (PENDING despues de APPROVED, p. ej.) se anota y no cambia nada.
ESTADOS_PAGO_FINALES = (EstadoPago.APROBADO.value, EstadoPago.REEMBOLSADO.value)


def vencido(creado_en: datetime, ahora: datetime | None = None) -> bool:
    """Si el pedido ya paso su ventana de pago. SQLite devuelve fechas sin zona:
    se leen como UTC, que es como se escribieron."""
    if creado_en.tzinfo is None:
        creado_en = creado_en.replace(tzinfo=UTC)
    return (ahora or datetime.now(UTC)) - creado_en > VIGENCIA_PAGO


# Los campos de la entrega que hacen "la misma orden": toda la copia congelada
# del envio (ADR 0015). Reutilizar un pendiente con otra localidad u otro
# apartamento despacharia con los datos viejos; que no case cuesta poco (se
# cancela el pendiente y se crea otro).
CAMPOS_FIRMA_ENTREGA = (
    "destinatario",
    "direccion",
    "ciudad",
    "localidad",
    "departamento",
    "indicaciones",
    "telefono",
    "documento_destinatario",
    # El pin de OSM si cuenta: mover el pin sin tocar el texto cambia a donde
    # llega el repartidor, y reutilizar el pendiente lo despacharia al punto viejo.
    "latitud",
    "longitud",
)


def firma_orden(lineas: list[tuple[str, int, int]], entrega: tuple[str | None, ...]) -> tuple[Any, ...]:
    """Lo que hace "la misma orden": productos (sin importar el orden) y entrega.
    Un campo ausente (`None`, el checkout legado) y uno vacio son la misma
    entrega."""
    return (tuple(sorted(lineas)), tuple(campo or "" for campo in entrega))


def pedido_tras_pago(estado_pago: EstadoPago, estado_actual: str) -> str | None:
    """El estado al que pasa el pedido según el resultado del pago.

    Aprobado lleva a `pagado`; cualquier otro desenlace (rechazado,
    reembolsado, aún iniciado) deja el pedido donde estaba y devuelve `None`
    para que el llamador no mueva nada. `estado_actual` se recibe por simetría
    con la máquina de estados y para futuras reglas que dependan de él.
    """
    if estado_pago == EstadoPago.APROBADO:
        return EstadoPedido.PAGADO.value
    return None
