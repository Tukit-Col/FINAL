from __future__ import annotations

from datetime import UTC, date, datetime, timedelta, timezone
from functools import lru_cache
from typing import Any

BOGOTA = timezone(timedelta(hours=-5))

DIAS_HABILES_RETRACTO = 5
DIAS_REEMBOLSO = 30


def _pascua(anio: int) -> date:
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
    return dia + timedelta(days=(7 - dia.weekday()) % 7)


@lru_cache(maxsize=32)
def festivos_colombia(anio: int) -> frozenset[date]:
    pascua = _pascua(anio)
    fijos = [(1, 1), (5, 1), (7, 20), (8, 7), (12, 8), (12, 25)]
    emiliani = [(1, 6), (3, 19), (6, 29), (8, 15), (10, 12), (11, 1), (11, 11)]
    festivos = {date(anio, m, d) for m, d in fijos}
    festivos |= {_al_lunes(date(anio, m, d)) for m, d in emiliani}
    festivos |= {pascua - timedelta(days=3), pascua - timedelta(days=2)}
    festivos |= {_al_lunes(pascua + timedelta(days=n)) for n in (39, 60, 68)}
    return frozenset(festivos)


def es_dia_habil(dia: date) -> bool:
    return dia.weekday() < 5 and dia not in festivos_colombia(dia.year)


def sumar_dias_habiles(desde: date, dias: int) -> date:
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
    if entregado_en is None:
        return None
    return sumar_dias_habiles(_dia_bogota(entregado_en), DIAS_HABILES_RETRACTO)


def limite_reembolso(solicitado_en: datetime) -> date:
    return _dia_bogota(solicitado_en) + timedelta(days=DIAS_REEMBOLSO)


def evaluar_devolucion(solicitado_en: datetime, entregado_en: datetime | None) -> dict[str, Any]:
    limite = plazo_retracto(entregado_en)
    a_tiempo = limite is None or _dia_bogota(solicitado_en) <= limite
    return {
        "plazo_retracto": limite.isoformat() if limite else None,
        "dentro_de_plazo": a_tiempo,
        "limite_reembolso": limite_reembolso(solicitado_en).isoformat(),
    }
