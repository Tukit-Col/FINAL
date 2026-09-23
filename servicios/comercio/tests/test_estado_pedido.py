"""La maquina de estados del pedido, como dato y no como cadena de `if`.

Se prueba cada par de transiciones: las permitidas pasan, todas las demas se
rechazan, y los estados terminales (`entregado`, `cancelado`) no dejan salir a
ningun lado.
"""

from __future__ import annotations

from itertools import product

from tukit_comercio.modelos import EstadoPedido, transicion_valida
from tukit_comercio.modelos.base import TRANSICIONES_PEDIDO

TERMINALES = {EstadoPedido.ENTREGADO, EstadoPedido.CANCELADO}


def test_transiciones_permitidas_pasan():
    for desde, permitidos in TRANSICIONES_PEDIDO.items():
        for hacia in permitidos:
            assert transicion_valida(desde.value, hacia.value), f"{desde}->{hacia} deberia valer"


def test_transiciones_no_declaradas_se_rechazan():
    for desde, hacia in product(EstadoPedido, EstadoPedido):
        esperado = hacia in TRANSICIONES_PEDIDO[desde]
        assert transicion_valida(desde.value, hacia.value) is esperado


def test_estados_terminales_no_salen():
    for terminal in TERMINALES:
        assert TRANSICIONES_PEDIDO[terminal] == frozenset()
        for hacia in EstadoPedido:
            assert not transicion_valida(terminal.value, hacia.value)


def test_valores_desconocidos_no_lanzan():
    assert transicion_valida("no_existe", "pagado") is False
    assert transicion_valida("pagado", "no_existe") is False


def test_pendiente_pago_solo_a_pagado_o_cancelado():
    assert transicion_valida("pendiente_pago", "pagado")
    assert transicion_valida("pendiente_pago", "cancelado")
    assert not transicion_valida("pendiente_pago", "en_preparacion")
    assert not transicion_valida("pendiente_pago", "entregado")
