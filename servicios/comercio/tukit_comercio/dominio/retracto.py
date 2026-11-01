"""El derecho de retracto del consumidor y la linea de tiempo del pedido, como dominio puro.

Ley 1480 de 2011, art. 47: en ventas a distancia el consumidor puede retractarse
dentro de los cinco (5) dias habiles siguientes a la entrega del bien. Aqui vive
solo la regla (plazo, quien puede pedirlo y cuando); el router lee la base y
persiste. Todo recibe y devuelve datos planos.

Los dias habiles son de lunes a viernes sin los festivos de Colombia (Ley 51 de
1983, "ley Emiliani"): sin ellos el plazo se calcularia corto o largo segun la
semana, y el papa vería una fecha limite equivocada.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Any

from ..modelos import EstadoPedido

DIAS_HABILES_RETRACTO = 5

# Colombia no tiene horario de verano: UTC-5 todo el ano. La fecha de entrega y
# el cierre del plazo se miden en hora local, no en UTC.
_BOGOTA = timedelta(hours=-5)


def _pascua(anio: int) -> date:
    """Domingo de Pascua (algoritmo gregoriano anonimo)."""
    a = anio % 19
    b, c = divmod(anio, 100)
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    ele = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * ele) // 451
    mes, dia = divmod(h + ele - 7 * m + 114, 31)
    return date(anio, mes, dia + 1)


def _al_lunes(fecha: date) -> date:
    """Traslada al lunes siguiente (o se queda si ya es lunes), como la ley Emiliani."""
    return fecha + timedelta(days=(7 - fecha.weekday()) % 7)


def festivos(anio: int) -> frozenset[date]:
    """Los festivos nacionales de Colombia de un ano."""
    pascua = _pascua(anio)
    fijos = [date(anio, 1, 1), date(anio, 5, 1), date(anio, 7, 20), date(anio, 8, 7), date(anio, 12, 8), date(anio, 12, 25)]
    trasladables = [
        date(anio, 1, 6),
        date(anio, 3, 19),
        date(anio, 6, 29),
        date(anio, 8, 15),
        date(anio, 10, 12),
        date(anio, 11, 1),
        date(anio, 11, 11),
    ]
    moviles = [
        pascua - timedelta(days=3),  # jueves santo
        pascua - timedelta(days=2),  # viernes santo
        pascua + timedelta(days=43),  # ascension (lunes)
        pascua + timedelta(days=64),  # corpus christi (lunes)
        pascua + timedelta(days=71),  # sagrado corazon (lunes)
    ]
    return frozenset(fijos + [_al_lunes(f) for f in trasladables] + moviles)


def es_dia_habil(dia: date) -> bool:
    return dia.weekday() < 5 and dia not in festivos(dia.year)


def sumar_dias_habiles(desde: date, dias: int) -> date:
    """El dia habil numero `dias` despues de `desde` (que no se cuenta)."""
    actual = desde
    restantes = dias
    while restantes > 0:
        actual += timedelta(days=1)
        if es_dia_habil(actual):
            restantes -= 1
    return actual


def _local(instante: datetime) -> datetime:
    if instante.tzinfo is None:
        instante = instante.replace(tzinfo=UTC)
    return instante.astimezone(UTC) + _BOGOTA


def vence_retracto(entregado_en: datetime) -> datetime:
    """El instante en que se cierra el plazo: fin del 5.o dia habil tras la entrega."""
    ultimo = sumar_dias_habiles(_local(entregado_en).date(), DIAS_HABILES_RETRACTO)
    # Fin del dia local (23:59:59 en Bogota), expresado en UTC.
    return datetime(ultimo.year, ultimo.month, ultimo.day, 23, 59, 59, tzinfo=UTC) - _BOGOTA


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


def linea_de_tiempo(
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
