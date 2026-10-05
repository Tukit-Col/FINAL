"""La consecuencia de un pago sobre el pedido, como dominio puro.

`pedido_tras_pago` decide a qué estado pasa el pedido según el resultado del
cobro. Ya era una función pura dentro de `api.py` (`_pedido_tras_pago`); aquí
vive en `dominio/pagos.py` y se prueba sin webhook ni base.
"""

from __future__ import annotations

from tukit_comercio.dominio.pagos import pedido_tras_pago
from tukit_comercio.modelos import EstadoPago, EstadoPedido


def test_pago_aprobado_lleva_a_pagado():
    destino = pedido_tras_pago(EstadoPago.APROBADO, EstadoPedido.PENDIENTE_PAGO.value)
    assert destino == EstadoPedido.PAGADO.value


def test_pago_rechazado_no_mueve_el_pedido():
    assert pedido_tras_pago(EstadoPago.RECHAZADO, EstadoPedido.PENDIENTE_PAGO.value) is None


def test_pago_reembolsado_no_mueve_el_pedido():
    assert pedido_tras_pago(EstadoPago.REEMBOLSADO, EstadoPedido.PENDIENTE_PAGO.value) is None


def test_pago_iniciado_no_mueve_el_pedido():
    assert pedido_tras_pago(EstadoPago.INICIADO, EstadoPedido.PENDIENTE_PAGO.value) is None
