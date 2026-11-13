"""Alertas accionables de un pedido, como dominio puro.

El operador no necesita contar pedidos: necesita saber cuales estan detenidos.
Esta funcion dice, para un pedido, si hay algo que atender. Sin I/O: el
repositorio le pasa las fechas ya leidas. Los umbrales son constantes de
dominio, no numeros sueltos.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from ..modelos import EstadoPago, EstadoPedido
from .pagos import vencido

# Un pedido pagado que lleva mas de esto sin avanzar es el reclamo mas probable.
UMBRAL_PAGADO_SIN_AVANZAR = timedelta(hours=24)
# Un pago `iniciado` con mas de esto de edad, aun dentro de la vigencia del pedido.
UMBRAL_PAGO_ATASCADO = timedelta(minutes=30)

PAGADO_SIN_AVANZAR = "pagado_sin_avanzar"
PAGO_ATASCADO = "pago_atascado"
INCIDENCIA_ABIERTA = "incidencia_abierta"
ALERTAS = (PAGADO_SIN_AVANZAR, PAGO_ATASCADO, INCIDENCIA_ABIERTA)


def _utc(fecha: datetime) -> datetime:
    """SQLite devuelve fechas sin zona: se leen como UTC, como se escribieron."""
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
    """Cero o mas alertas del pedido (ver `ALERTAS`)."""
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
