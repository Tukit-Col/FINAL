"""La consecuencia de un pago sobre el pedido, como dominio puro.

`pedido_tras_pago` decide a qué estado pasa el pedido según el resultado del
cobro. Ya era pura dentro de `api.py` (`_pedido_tras_pago`); se mueve aquí para
que el webhook sólo la consulte y persista, y para que la regla se pruebe sin
levantar la pasarela. El llamador sigue validando la transición contra
`transicion_valida` antes de escribir: esta función dice el destino deseado, no
que sea legal.
"""

from __future__ import annotations

from ..modelos import EstadoPago, EstadoPedido


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
