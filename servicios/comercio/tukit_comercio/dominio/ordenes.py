from __future__ import annotations

import uuid
from collections.abc import Iterable
from dataclasses import dataclass


@dataclass(frozen=True)
class LineaResuelta:
    sku: str
    precio_aprobado: int
    cantidad: int
    id_canonico: uuid.UUID | None
    precio_actual: int | None


@dataclass(frozen=True)
class CambioPrecio:
    sku: str
    precio_aprobado: int
    precio_actual: int | None


def reverificar_precios(lineas: Iterable[LineaResuelta]) -> list[CambioPrecio]:
    return [
        CambioPrecio(sku=ln.sku, precio_aprobado=ln.precio_aprobado, precio_actual=ln.precio_actual)
        for ln in lineas
        if ln.precio_actual is None or ln.precio_actual != ln.precio_aprobado
    ]


def total_orden(lineas: Iterable[LineaResuelta]) -> int:
    return sum(ln.precio_aprobado * ln.cantidad for ln in lineas)
