"""El avance de un pedido por la cadena de entrega, como dominio puro.

El back-office de logistica empuja el pedido `pagado -> en_preparacion ->
despachado -> en_reparto -> entregado`, con `incidencia` como desvio no terminal
y `cancelado` como salida. Dos preguntas gobiernan cada paso, y esta funcion las
separa del router y del SQL:

1. *Es legal la transicion?* Lo responde la tabla `TRANSICIONES_PEDIDO` que ya
   vive en `modelos/base.py`; no se repite aqui, se consulta con
   `transicion_valida`. Reusarla es lo que mantiene una sola fuente de verdad de
   la maquina de estados.
2. *Estan los datos que el destino exige?* La unica regla que la tabla no puede
   expresar: marcar un pedido `despachado` sin transportadora ni guia lo deja
   sin nada que rastrear. Un despacho es un hecho fisico con un numero; sin el,
   el estado miente.

`validar_avance` es pura: recibe cadenas y datos planos, no toca base ni HTTP, y
devuelve `None` cuando el avance es valido o un `AvanceRechazado` (razon tipada +
codigo HTTP) cuando no. El router traduce ese rechazo a un `ErrorDominio`.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..modelos import EstadoPedido, transicion_valida


@dataclass(frozen=True)
class AvanceRechazado:
    """Por que un avance no procede, con el codigo HTTP que le corresponde.

    `razon` es un identificador estable (no un mensaje) para que el router arme
    el sobre de error; `estado` es el HTTP: `422` cuando el destino ni siquiera
    es un estado o le faltan datos de entrada, `409` cuando el destino es valido
    pero la transicion desde el estado actual no lo es (conflicto de estado).
    """

    razon: str
    estado: int


def validar_avance(
    actual: str,
    destino: str,
    *,
    transportadora: str | None,
    guia: str | None,
) -> AvanceRechazado | None:
    """Valida mover un pedido de `actual` a `destino`. `None` = adelante.

    Rechaza, en orden: un `destino` que no es un estado conocido (`422`), una
    transicion que la tabla no permite (`409`), y un despacho sin transportadora
    y guia (`422`, `despacho_incompleto`). Cualquier otro avance legal pasa.
    """
    try:
        destino_estado = EstadoPedido(destino)
    except ValueError:
        return AvanceRechazado("destino_invalido", 422)

    if not transicion_valida(actual, destino):
        return AvanceRechazado("transicion_invalida", 409)

    if destino_estado is EstadoPedido.DESPACHADO and not (transportadora and guia):
        return AvanceRechazado("despacho_incompleto", 422)

    return None
