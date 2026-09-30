"""El guard del avance de un pedido por la cadena de entrega, como dominio puro.

Que una transicion sea legal lo responde la tabla `TRANSICIONES_PEDIDO`; aqui se
prueba la unica regla que la tabla no expresa (un despacho sin transportadora ni
guia no se puede rastrear) y que el guard reusa la tabla en vez de repetirla.
"""

from __future__ import annotations

from tukit_comercio.dominio.despacho import validar_avance


def test_avance_legal_devuelve_none():
    assert validar_avance("pagado", "en_preparacion", transportadora=None, guia=None) is None


def test_transicion_ilegal_se_rechaza_por_la_tabla():
    # pagado -> entregado se salta pasos: la tabla lo prohibe.
    rechazo = validar_avance("pagado", "entregado", transportadora=None, guia=None)
    assert rechazo is not None
    assert rechazo.razon == "transicion_invalida"
    assert rechazo.estado == 409


def test_destino_desconocido_se_rechaza():
    rechazo = validar_avance("pagado", "teletransportado", transportadora=None, guia=None)
    assert rechazo is not None
    assert rechazo.razon == "destino_invalido"
    assert rechazo.estado == 422


def test_despachar_sin_transportadora_ni_guia_se_rechaza():
    rechazo = validar_avance("en_preparacion", "despachado", transportadora=None, guia=None)
    assert rechazo is not None
    assert rechazo.razon == "despacho_incompleto"


def test_despachar_con_solo_guia_no_basta():
    rechazo = validar_avance("en_preparacion", "despachado", transportadora=None, guia="ABC123")
    assert rechazo is not None
    assert rechazo.razon == "despacho_incompleto"


def test_despachar_con_transportadora_y_guia_pasa():
    assert (
        validar_avance("en_preparacion", "despachado", transportadora="Servientrega", guia="ABC123")
        is None
    )


def test_incidencia_desde_cualquier_estado_posterior_al_pago_pasa():
    # incidencia es un desvio no terminal que la tabla admite desde el pago en
    # adelante; no exige datos de despacho.
    assert validar_avance("en_reparto", "incidencia", transportadora=None, guia=None) is None
