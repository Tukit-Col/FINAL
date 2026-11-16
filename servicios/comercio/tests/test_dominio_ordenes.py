"""La regla de re-verificación de precio (FU-08), como dominio puro.

Es la invariante más cara del §9 —no cobrar a un precio que cambió— y hasta
ahora solo se podía probar levantando FastAPI + SQLite + un Catálogo falso
(ver `test_checkout_orden.py::test_reverificacion_*`). Extraída a `dominio/ordenes.py`
se prueba con una lista y nada más: sin red, sin base. Ese es el payoff de la
ADR 0019.
"""

from __future__ import annotations

import uuid

from tukit_comercio.dominio.ordenes import (
    CambioPrecio,
    LineaResuelta,
    reverificar_precios,
    total_orden,
)

_ID = uuid.uuid5(uuid.NAMESPACE_OID, "TK-C001-ECO")


def _linea(sku: str = "TK-C001-ECO", aprobado: int = 4500, actual: int | None = 4500, cantidad: int = 2):
    return LineaResuelta(
        sku=sku,
        precio_aprobado=aprobado,
        cantidad=cantidad,
        id_canonico=_ID if actual is not None else None,
        precio_actual=actual,
    )


def test_todos_los_precios_coinciden_no_hay_cambios():
    # Precio aprobado == precio vigente en todas las líneas: la orden puede cerrarse.
    assert reverificar_precios([_linea(), _linea(sku="TK-C002", aprobado=3000, actual=3000)]) == []


def test_un_precio_cambio_se_reporta_con_ambos_valores():
    cambios = reverificar_precios([_linea(aprobado=4500, actual=5200)])
    assert cambios == [CambioPrecio(sku="TK-C001-ECO", precio_aprobado=4500, precio_actual=5200)]


def test_sku_sin_precio_vigente_cuenta_como_cambio():
    # precio_actual None = el sku no existe o no tiene precio publicado hoy.
    # No se cobra a ciegas: es un cambio, no un pase libre.
    cambios = reverificar_precios([_linea(actual=None)])
    assert cambios == [CambioPrecio(sku="TK-C001-ECO", precio_aprobado=4500, precio_actual=None)]


def test_solo_se_reportan_las_lineas_que_cambiaron():
    cambios = reverificar_precios(
        [
            _linea(sku="ok", aprobado=1000, actual=1000),
            _linea(sku="subio", aprobado=1000, actual=1500),
            _linea(sku="sin_precio", aprobado=1000, actual=None),
        ]
    )
    assert {c.sku for c in cambios} == {"subio", "sin_precio"}


def test_total_orden_suma_precio_por_cantidad():
    lineas = [_linea(aprobado=4500, cantidad=2), _linea(sku="TK-C002", aprobado=3000, cantidad=1)]
    assert total_orden(lineas) == 4500 * 2 + 3000
