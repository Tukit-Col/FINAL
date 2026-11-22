from __future__ import annotations

from datetime import UTC, datetime, timedelta

from ..modelos import EstadoPago, EstadoPedido
from .pagos import vencido

UMBRAL_PAGADO_SIN_AVANZAR = timedelta(hours=24)
UMBRAL_PAGO_ATASCADO = timedelta(minutes=30)

PAGADO_SIN_AVANZAR = "pagado_sin_avanzar"
PAGO_ATASCADO = "pago_atascado"
INCIDENCIA_ABIERTA = "incidencia_abierta"
ALERTAS = (PAGADO_SIN_AVANZAR, PAGO_ATASCADO, INCIDENCIA_ABIERTA)


def _utc(fecha: datetime) -> datetime:
    return fecha if fecha.tzinfo is not None else fecha.replace(tzinfo=UTC)


def alertas_de_pedido(
    *,
    estado: str,
    estado_desde: datetime,
    pago_estado: str | None,
    pago_iniciado_en: datetime | None,
    creado_en: datetime,
    ahora: datetime,
) -> tuple[str, ...]:
    ahora = _utc(ahora)
    if estado == EstadoPedido.PAGADO.value:
        if ahora - _utc(estado_desde) > UMBRAL_PAGADO_SIN_AVANZAR:
            return (PAGADO_SIN_AVANZAR,)
        return ()
    if estado == EstadoPedido.PENDIENTE_PAGO.value:
        if (
            pago_estado == EstadoPago.INICIADO.value
            and pago_iniciado_en is not None
            and ahora - _utc(pago_iniciado_en) > UMBRAL_PAGO_ATASCADO
            and not vencido(creado_en if creado_en.tzinfo else _utc(creado_en), ahora)
        ):
            return (PAGO_ATASCADO,)
        return ()
    if estado == EstadoPedido.INCIDENCIA.value:
        return (INCIDENCIA_ABIERTA,)
    return ()
