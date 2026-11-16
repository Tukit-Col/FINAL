"""Cancelar un pedido pendiente y la vigencia del pago.

Cancelar a ciegas cobraria sin entregar: antes de cancelar, Comercio pregunta a
Wompi. Sin pago alla, cancela y libera la reserva; con un pago aprobado lo
aplica y no cancela; con uno en curso no toca nada; con Wompi caido, 502 y el
pedido intacto. Un pedido mas viejo que `VIGENCIA_PAGO` ya no se paga.
"""

from __future__ import annotations

from _ayudas_comercio import (
    SOLICITUD_PAGO,
    avisos_en_bandeja,
    envejecer,
    estado_de,
    nueva_orden,
    pagar,
    pedido_con_pago,
    reservas_de,
)
from tukit_comercio.api import app
from tukit_comercio.dominio.pagos import VIGENCIA_PAGO
from tukit_comercio.modelos import EstadoPedido
from tukit_comercio.pasarela import PasarelaCaida, PasarelaFalsa

_HORAS_VIGENCIA = VIGENCIA_PAGO.total_seconds() / 3600


async def test_cancelar_sin_pago_en_wompi_cancela_y_libera_la_reserva(cliente):
    pedido_id = (await cliente.post("/v1/ordenes", json=nueva_orden())).json()["pedido_id"]
    await pagar(cliente, pedido_id)  # intento abandonado: Wompi no tiene nada
    r = await cliente.post(f"/v1/ordenes/{pedido_id}/cancelar")
    assert r.status_code == 200
    assert r.json()["estado"] == EstadoPedido.CANCELADO.value
    assert await reservas_de(pedido_id) == ["liberada"]


async def test_cancelar_con_pago_aprobado_en_wompi_lo_aplica_y_no_cancela(cliente):
    # El acudiente pago por PSE y no volvio: Tukit no lo sabia. Cancelar a
    # ciegas cobraria sin entregar.
    pedido_id = (await cliente.post("/v1/ordenes", json=nueva_orden())).json()["pedido_id"]
    pago = await pagar(cliente, pedido_id)
    app.state.pasarela.fijar_resultado(pago["referencia_wompi"], "APPROVED")
    r = await cliente.post(f"/v1/ordenes/{pedido_id}/cancelar")
    assert r.status_code == 409
    assert r.json()["error"] == "pedido_ya_pagado"
    assert await estado_de(cliente, pedido_id) == EstadoPedido.PAGADO.value
    assert await avisos_en_bandeja("pedido_pagado") == 1


async def test_cancelar_con_pago_en_curso_no_cancela(cliente):
    pedido_id = (await cliente.post("/v1/ordenes", json=nueva_orden())).json()["pedido_id"]
    pago = await pagar(cliente, pedido_id)
    app.state.pasarela.fijar_resultado(pago["referencia_wompi"], "PENDING")
    r = await cliente.post(f"/v1/ordenes/{pedido_id}/cancelar")
    assert r.status_code == 409
    assert r.json()["error"] == "pago_en_curso"
    assert await estado_de(cliente, pedido_id) == EstadoPedido.PENDIENTE_PAGO.value


async def test_cancelar_un_pedido_pagado_es_409(cliente):
    pedido_id, ref = await pedido_con_pago(cliente)
    await cliente.post(f"/v1/pagos/falsa-APPROVED-{ref}/sincronizar")
    r = await cliente.post(f"/v1/ordenes/{pedido_id}/cancelar")
    assert r.status_code == 409
    assert r.json()["error"] == "pedido_no_cancelable"


async def test_cancelar_con_wompi_caido_es_502_y_no_cancela(cliente):
    pedido_id = (await cliente.post("/v1/ordenes", json=nueva_orden())).json()["pedido_id"]
    await pagar(cliente, pedido_id)

    class Caida(PasarelaFalsa):
        async def consultar_por_referencia(self, referencia):
            raise PasarelaCaida("sin red")

    app.state.pasarela = Caida(montos=app.state.pasarela.montos)
    r = await cliente.post(f"/v1/ordenes/{pedido_id}/cancelar")
    assert r.status_code == 502
    assert await estado_de(cliente, pedido_id) == EstadoPedido.PENDIENTE_PAGO.value


async def test_pagar_un_pedido_vencido_es_409(cliente):
    # La vigencia del pago (24 h, `VIGENCIA_PAGO`) es la que promete el checkout.
    pedido_id = (await cliente.post("/v1/ordenes", json=nueva_orden())).json()["pedido_id"]
    await envejecer(pedido_id, horas=_HORAS_VIGENCIA + 1)
    r = await cliente.post(f"/v1/ordenes/{pedido_id}/pago", json=SOLICITUD_PAGO)
    assert r.status_code == 409
    assert r.json()["error"] == "pedido_vencido"


async def test_pagar_un_pedido_aun_vigente_se_permite(cliente):
    pedido_id = (await cliente.post("/v1/ordenes", json=nueva_orden())).json()["pedido_id"]
    await envejecer(pedido_id, horas=_HORAS_VIGENCIA - 1)
    r = await cliente.post(f"/v1/ordenes/{pedido_id}/pago", json=SOLICITUD_PAGO)
    assert r.status_code == 201
    assert r.json()["referencia_wompi"] == f"tukit-{pedido_id}-1"
