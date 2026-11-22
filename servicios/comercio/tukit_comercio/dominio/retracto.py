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

festivos = festivos_colombia


def vence_retracto(entregado_en: datetime) -> datetime:
    ultimo = plazo_retracto(entregado_en)
    assert ultimo is not None
    return datetime(ultimo.year, ultimo.month, ultimo.day, 23, 59, 59, tzinfo=BOGOTA).astimezone(UTC)


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

    puede: bool
    razon: str | None
    vence_en: datetime | None
    antes_de_entrega: bool


def evaluar_retracto(
    estado: str, entregado_en: datetime | None, ahora: datetime, *, ya_solicitado: bool
) -> EstadoRetracto:
    if ya_solicitado:
        return EstadoRetracto(False, "ya_solicitado", None, False)
    if estado in _ANTES_DE_LA_ENTREGA:
        return EstadoRetracto(True, None, None, True)
    if estado == EstadoPedido.ENTREGADO.value:
        if entregado_en is None:
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
    pasos: list[dict[str, Any]] = [{"estado": EstadoPedido.PENDIENTE_PAGO.value, "en": creado_en}]
    if pago_aprobado_en is not None:
        pasos.append({"estado": EstadoPedido.PAGADO.value, "en": pago_aprobado_en})
    for fila in historial:
        pasos.append({"estado": fila["estado_hacia"], "en": fila["creado_en"]})
    if entregado_en is not None and not any(p["estado"] == EstadoPedido.ENTREGADO.value for p in pasos):
        pasos.append({"estado": EstadoPedido.ENTREGADO.value, "en": entregado_en})
    return [{**p, "etiqueta": _ETIQUETA_PASO.get(p["estado"], p["estado"])} for p in pasos]


linea_de_tiempo = pasos_del_pedido
