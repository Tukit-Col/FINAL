"""La re-verificación de precio antes de cobrar (FU-08), como dominio puro.

La primera invariante del §9 que no se negocia: antes de cerrar una orden se
relee el precio público de cada línea contra Catálogo, y si cambió respecto al
que el acudiente aprobó, la orden NO se cierra. Esta regla vivía embebida en
`crear_orden`, entrelazada con la llamada HTTP a Catálogo y los `insert`; aquí
queda sola, recibiendo líneas ya resueltas (el router hizo el `await`) y
devolviendo los cambios detectados. No sabe de precios cómo se obtuvieron.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterable
from dataclasses import dataclass


@dataclass(frozen=True)
class LineaResuelta:
    """Una línea de la orden con su precio vigente ya leído de Catálogo.

    El router resuelve el sku contra Catálogo (`ClienteCatalogo.resolver`) y
    arma esto: `precio_aprobado` es el que el acudiente vio; `precio_actual` es
    el que Catálogo dice hoy, o `None` si el sku no existe o no tiene precio
    publicado; `id_canonico` es `None` en ese mismo caso.
    """

    sku: str
    precio_aprobado: int
    cantidad: int
    id_canonico: uuid.UUID | None
    precio_actual: int | None


@dataclass(frozen=True)
class CambioPrecio:
    """Una línea cuyo precio no se pudo confirmar igual al aprobado.

    `precio_actual` es `None` cuando el sku no existe o perdió su precio
    vigente: también es un cambio, porque cerrar la orden ahí sería cobrar a
    ciegas, justo lo contrario de la invariante.
    """

    sku: str
    precio_aprobado: int
    precio_actual: int | None


def reverificar_precios(lineas: Iterable[LineaResuelta]) -> list[CambioPrecio]:
    """Las líneas cuyo precio vigente no coincide con el aprobado.

    Lista vacía = todos los precios coinciden y la orden puede cerrarse. Una
    línea entra en la lista si su `precio_actual` es `None` (sin precio vigente)
    o difiere del `precio_aprobado`. El llamador congela sólo si esto sale vacío.
    """
    return [
        CambioPrecio(sku=ln.sku, precio_aprobado=ln.precio_aprobado, precio_actual=ln.precio_actual)
        for ln in lineas
        if ln.precio_actual is None or ln.precio_actual != ln.precio_aprobado
    ]


def total_orden(lineas: Iterable[LineaResuelta]) -> int:
    """El total de la orden: precio aprobado por cantidad, sumado.

    Se calcula sobre el precio aprobado (el que se va a congelar), no sobre el
    vigente: sólo se llega aquí cuando `reverificar_precios` salió vacío, así
    que aprobado y vigente coinciden.
    """
    return sum(ln.precio_aprobado * ln.cantidad for ln in lineas)
