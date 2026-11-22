"""Linea de tiempo del pedido que ve el acudiente, como dominio puro.

Decisiones:
- La regla de en que paso va el pedido vive en Comercio, dueno de la maquina de estados; el
  frontend pinta lo que recibe y no recalcula.
- No es lineal: una incidencia devuelve a preparacion, asi que la posicion sale del estado actual
  y no del paso mas lejano al que se llego.
- Las fechas no se inventan: salen del pedido, del pago aprobado y del historial; sin dato, `None`.
- Las entradas son vistas recortadas (`PagoVisto`, `AvanceVisto`, `EnvioVisto`) para que los datos
  de staff y el celular del repartidor no puedan llegar al acudiente.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from ..modelos import EstadoPago, EstadoPedido
from .pagos import VIGENCIA_PAGO, vencido

_E = EstadoPedido

PASOS = ("creado", "pagado", "en_preparacion", "despachado", "en_reparto", "entregado")

_PASO_DE_ESTADO = {
    _E.PENDIENTE_PAGO.value: "creado",
    _E.PAGADO.value: "pagado",
    _E.EN_PREPARACION.value: "en_preparacion",
    _E.DESPACHADO.value: "despachado",
    _E.EN_REPARTO.value: "en_reparto",
    _E.ENTREGADO.value: "entregado",
}


@dataclass(frozen=True)
class PagoVisto:
    estado: str
    actualizado_en: datetime | None


@dataclass(frozen=True)
class AvanceVisto:
    estado_desde: str
    estado_hacia: str
    tipo_incidencia: str | None
    creado_en: datetime | None


@dataclass(frozen=True)
class EnvioVisto:
    repartidor_nombre: str | None
    entrega_estimada: datetime | None
    entregado_en: datetime | None


def _iso(valor: datetime | None) -> str | None:
    if valor is None:
        return None
    if valor.tzinfo is None:
        valor = valor.replace(tzinfo=UTC)
    return valor.isoformat()


def _ultimo_hacia(historial: Sequence[AvanceVisto], estado: str, hasta: int | None = None) -> int | None:
    fin = len(historial) if hasta is None else hasta
    for i in range(fin - 1, -1, -1):
        if historial[i].estado_hacia == estado:
            return i
    return None


def _posicion(estado: str, historial: Sequence[AvanceVisto], pagos: Sequence[PagoVisto]) -> str:
    if estado in _PASO_DE_ESTADO:
        return _PASO_DE_ESTADO[estado]
    hasta: int | None = None
    buscado = estado
    while buscado in (_E.INCIDENCIA.value, _E.CANCELADO.value):
        i = _ultimo_hacia(historial, buscado, hasta)
        if i is None:
            break
        buscado, hasta = historial[i].estado_desde, i
    if buscado in _PASO_DE_ESTADO:
        return _PASO_DE_ESTADO[buscado]
    hubo_pago = any(p.estado in (EstadoPago.APROBADO.value, EstadoPago.REEMBOLSADO.value) for p in pagos)
    return "pagado" if hubo_pago else "creado"


def _fecha_del_paso(
    paso: str,
    creado_en: datetime,
    pagos: Sequence[PagoVisto],
    historial: Sequence[AvanceVisto],
    envio: EnvioVisto | None,
) -> datetime | None:
    if paso == "creado":
        return creado_en
    if paso == "pagado":
        aprobados = [p.actualizado_en for p in pagos if p.estado == EstadoPago.APROBADO.value]
        return aprobados[-1] if aprobados else None
    i = _ultimo_hacia(historial, paso)
    if i is not None:
        return historial[i].creado_en
    if paso == "entregado" and envio is not None:
        return envio.entregado_en
    return None


def linea_de_tiempo(
    *,
    estado: str,
    creado_en: datetime,
    pagos: Sequence[PagoVisto],
    historial: Sequence[AvanceVisto],
    envio: EnvioVisto | None,
    ahora: datetime | None = None,
) -> dict[str, Any]:
    posicion = PASOS.index(_posicion(estado, historial, pagos))
    cancelado = estado == _E.CANCELADO.value

    pasos: list[dict[str, Any]] = []
    for i, paso in enumerate(PASOS):
        if i < posicion or (i == posicion and cancelado):
            situacion = "hecho"
        elif i == posicion:
            situacion = "actual"
        else:
            situacion = "futuro"
        alcanzado = situacion != "futuro"
        fila: dict[str, Any] = {
            "paso": paso,
            "estado": situacion,
            "fecha": _iso(_fecha_del_paso(paso, creado_en, pagos, historial, envio)) if alcanzado else None,
        }
        if paso == "despachado":
            fila["repartidor_nombre"] = envio.repartidor_nombre if alcanzado and envio else None
        pasos.append(fila)

    especial: dict[str, Any] | None = None
    if estado == _E.INCIDENCIA.value:
        i = _ultimo_hacia(historial, estado)
        avance = historial[i] if i is not None else None
        especial = {
            "tipo": "incidencia",
            "tipo_incidencia": avance.tipo_incidencia if avance else None,
            "fecha": _iso(avance.creado_en) if avance else None,
        }
    elif cancelado:
        i = _ultimo_hacia(historial, estado)
        especial = {"tipo": "cancelado", "fecha": _iso(historial[i].creado_en) if i is not None else None}

    pago_pendiente: dict[str, Any] | None = None
    if estado == _E.PENDIENTE_PAGO.value:
        base = creado_en if creado_en.tzinfo else creado_en.replace(tzinfo=UTC)
        pago_pendiente = {"vence_en": _iso(base + VIGENCIA_PAGO), "vencido": vencido(creado_en, ahora)}

    return {
        "pasos": pasos,
        "especial": especial,
        "entrega_estimada": _iso(envio.entrega_estimada) if envio else None,
        "pago_pendiente": pago_pendiente,
    }
