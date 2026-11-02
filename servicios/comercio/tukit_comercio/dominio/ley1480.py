"""Los plazos del derecho de retracto (Ley 1480 de 2011, art. 47), como dominio puro.

El back-office necesita decir hasta cuando puede el acudiente retractarse y hasta
cuando hay que devolverle la plata. Dos reglas, ambas del art. 47:

- El retracto se ejerce dentro de los **cinco dias habiles** siguientes a la
  entrega del producto. Antes de la entrega el plazo todavia no corre.
- El reembolso se hace en un maximo de **treinta dias calendario** desde que se
  ejerce el retracto.

Dia habil = lunes a viernes que no sea festivo en Colombia. Los festivos se
calculan (Pascua + ley Emiliani) y no se listan, para que el calculo no caduque
con el ano. Colombia no tiene horario de verano, asi que Bogota es un UTC-5 fijo.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta, timezone
from functools import lru_cache
from typing import Any

BOGOTA = timezone(timedelta(hours=-5))

DIAS_HABILES_RETRACTO = 5
DIAS_REEMBOLSO = 30


def _pascua(anio: int) -> date:
    """Domingo de Pascua (calendario gregoriano, algoritmo de Meeus/Jones/Butcher)."""
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


def _al_lunes(dia: date) -> date:
    """La ley Emiliani traslada el festivo al lunes siguiente (el mismo dia si ya es lunes)."""
    return dia + timedelta(days=(7 - dia.weekday()) % 7)


@lru_cache(maxsize=32)
def festivos_colombia(anio: int) -> frozenset[date]:
    pascua = _pascua(anio)
    fijos = [(1, 1), (5, 1), (7, 20), (8, 7), (12, 8), (12, 25)]
    emiliani = [(1, 6), (3, 19), (6, 29), (8, 15), (10, 12), (11, 1), (11, 11)]
    festivos = {date(anio, m, d) for m, d in fijos}
    festivos |= {_al_lunes(date(anio, m, d)) for m, d in emiliani}
    festivos |= {pascua - timedelta(days=3), pascua - timedelta(days=2)}  # jueves y viernes santo
    # Ascension, Corpus Christi y Sagrado Corazon: se trasladan al lunes.
    festivos |= {_al_lunes(pascua + timedelta(days=n)) for n in (39, 60, 68)}
    return frozenset(festivos)


def es_dia_habil(dia: date) -> bool:
    return dia.weekday() < 5 and dia not in festivos_colombia(dia.year)


def sumar_dias_habiles(desde: date, dias: int) -> date:
    """El dia habil numero `dias` despues de `desde` (el propio `desde` no cuenta)."""
    actual = desde
    restantes = dias
    while restantes > 0:
        actual += timedelta(days=1)
        if es_dia_habil(actual):
            restantes -= 1
    return actual


def _dia_bogota(instante: datetime) -> date:
    if instante.tzinfo is None:
        instante = instante.replace(tzinfo=UTC)
    return instante.astimezone(BOGOTA).date()


def plazo_retracto(entregado_en: datetime | None) -> date | None:
    """Ultimo dia para retractarse, o `None` si el pedido aun no se entrega
    (el plazo corre desde la entrega, no desde la compra)."""
    if entregado_en is None:
        return None
    return sumar_dias_habiles(_dia_bogota(entregado_en), DIAS_HABILES_RETRACTO)


def limite_reembolso(solicitado_en: datetime) -> date:
    """Ultimo dia para devolver el dinero: 30 dias calendario desde el retracto."""
    return _dia_bogota(solicitado_en) + timedelta(days=DIAS_REEMBOLSO)


def evaluar_devolucion(solicitado_en: datetime, entregado_en: datetime | None) -> dict[str, Any]:
    """Lo que el back-office muestra de un retracto: su plazo, si se pidio a
    tiempo y hasta cuando se reembolsa. Las fechas salen como ISO `YYYY-MM-DD`.

    `dentro_de_plazo` es `True` mientras no haya entrega (el plazo no corre) y,
    despues, solo si la solicitud llego en o antes del ultimo dia habil."""
    limite = plazo_retracto(entregado_en)
    a_tiempo = limite is None or _dia_bogota(solicitado_en) <= limite
    return {
        "plazo_retracto": limite.isoformat() if limite else None,
        "dentro_de_plazo": a_tiempo,
        "limite_reembolso": limite_reembolso(solicitado_en).isoformat(),
    }
