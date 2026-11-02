"""El derecho de retracto del consumidor y la linea de tiempo del pedido, como dominio puro.

Ley 1480 de 2011, art. 47: en ventas a distancia el consumidor puede retractarse
dentro de los cinco (5) dias habiles siguientes a la entrega del bien. Aqui vive
solo la regla (plazo, quien puede pedirlo y cuando); el router lee la base y
persiste. Todo recibe y devuelve datos planos.

Los dias habiles (lunes a viernes sin los festivos de Colombia, Ley 51 de 1983)
y la hora de Bogota los calcula `dominio.ley1480`, el mismo calendario que ve el
back-office: el acudiente y el staff nunca ven dos fechas limite distintas.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from ..modelos import EstadoPedido
from .ley1480 import (
    BOGOTA,
    DIAS_HABILES_RETRACTO,
    es_dia_habil,
    festivos_colombia,
    plazo_retracto,
    sumar_dias_habiles,
)

__all__ = [
    "DIAS_HABILES_RETRACTO",
    "EstadoRetracto",
    "es_dia_habil",
    "evaluar_retracto",
    "festivos",
    "linea_de_tiempo",
    "pasos_del_pedido",
    "sumar_dias_habiles",
    "vence_retracto",
]

# El calendario (festivos de Colombia, dias habiles, hora de Bogota y el plazo
# de 5 dias habiles) vive en UN solo lugar: `dominio.ley1480`, que tambien
# usa el back-office. Aqui solo se decide que puede hacer el acudiente.
festivos = festivos_colombia


def vence_retracto(entregado_en: datetime) -> datetime:
    """El instante en que se cierra el plazo: fin del 5.o dia habil tras la entrega
    (23:59:59 en Bogota), expresado en UTC."""
    ultimo = plazo_retracto(entregado_en)
    assert ultimo is not None
    return datetime(ultimo.year, ultimo.month, ultimo.day, 23, 59, 59, tzinfo=BOGOTA).astimezone(UTC)


# Estados en los que el pedido ya se pago y aun puede deshacerse antes de llegar.
_ANTES_DE_LA_ENTREGA = frozenset(
    {
        EstadoPedido.PAGADO.value,
        EstadoPedido.EN_PREPARACION.value,
        EstadoPedido.DESPACHADO.value,
        EstadoPedido.EN_REPARTO.value,
    }
)


@dataclass(frozen=True)
class EstadoRetracto:
    """Lo que el acudiente puede hacer con el retracto de un pedido, hoy.

    `razon` (cuando `puede` es falso) es un identificador estable: la pantalla
    elige el texto. `vence_en` es el cierre del plazo, o `None` si la entrega
    aun no ocurre (el plazo empieza a correr cuando llegue).
    """

    puede: bool
    razon: str | None
    vence_en: datetime | None
    antes_de_entrega: bool


def evaluar_retracto(
    estado: str, entregado_en: datetime | None, ahora: datetime, *, ya_solicitado: bool
) -> EstadoRetracto:
    """Si el acudiente puede retractarse de un pedido en este estado y momento."""
    if ya_solicitado:
        return EstadoRetracto(False, "ya_solicitado", None, False)
    if estado in _ANTES_DE_LA_ENTREGA:
        return EstadoRetracto(True, None, None, True)
    if estado == EstadoPedido.ENTREGADO.value:
        if entregado_en is None:
            # Entregado sin fecha: no se puede medir el plazo, asi que lo decide una persona.
            return EstadoRetracto(False, "sin_fecha_de_entrega", None, False)
        vence = vence_retracto(entregado_en)
        if ahora > vence:
            return EstadoRetracto(False, "plazo_vencido", vence, False)
        return EstadoRetracto(True, None, vence, False)
    if estado == EstadoPedido.PENDIENTE_PAGO.value:
        return EstadoRetracto(False, "sin_pagar", None, False)
    if estado == EstadoPedido.CANCELADO.value:
        return EstadoRetracto(False, "cancelado", None, False)
    return EstadoRetracto(False, "estado_no_permite", None, False)


# Que dice cada paso de la linea de tiempo, en palabras del acudiente.
_ETIQUETA_PASO = {
    EstadoPedido.PENDIENTE_PAGO.value: "Pedido creado",
    EstadoPedido.PAGADO.value: "Pago confirmado",
    EstadoPedido.EN_PREPARACION.value: "Estamos alistando tu pedido",
    EstadoPedido.DESPACHADO.value: "Salió de la bodega",
    EstadoPedido.EN_REPARTO.value: "Va en camino",
    EstadoPedido.ENTREGADO.value: "Entregado",
    EstadoPedido.INCIDENCIA.value: "Hubo un inconveniente con la entrega",
    EstadoPedido.CANCELADO.value: "Pedido cancelado",
}


def pasos_del_pedido(
    *,
    creado_en: datetime,
    pago_aprobado_en: datetime | None,
    historial: list[dict[str, Any]],
    entregado_en: datetime | None,
) -> list[dict[str, Any]]:
    """Los pasos del pedido en orden, sin datos del equipo interno.

    Sale de lo que ya existe: la creacion, el pago aprobado y los avances del
    back-office. Del historial solo se toman el estado y la hora; el actor, la
    nota y el tipo de incidencia son del equipo y no salen. Si la entrega no
    quedo en el historial pero el envio la trae, se agrega.
    """
    pasos: list[dict[str, Any]] = [{"estado": EstadoPedido.PENDIENTE_PAGO.value, "en": creado_en}]
    if pago_aprobado_en is not None:
        pasos.append({"estado": EstadoPedido.PAGADO.value, "en": pago_aprobado_en})
    for fila in historial:
        pasos.append({"estado": fila["estado_hacia"], "en": fila["creado_en"]})
    if entregado_en is not None and not any(p["estado"] == EstadoPedido.ENTREGADO.value for p in pasos):
        pasos.append({"estado": EstadoPedido.ENTREGADO.value, "en": entregado_en})
    return [{**p, "etiqueta": _ETIQUETA_PASO.get(p["estado"], p["estado"])} for p in pasos]


# Nombre de la rama S3; `linea_de_tiempo` a secas es la de `dominio.linea_de_tiempo`.
linea_de_tiempo = pasos_del_pedido
