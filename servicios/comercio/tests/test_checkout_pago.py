from __future__ import annotations

from _ayudas_comercio import (
    SOLICITUD_PAGO,
    URL_RESULTADO,
    PasarelaQueNoResponde,
    centavos,
    flujo_hasta_webhook,
    nueva_orden,
)
from sqlalchemy import select
from tukit_comercio.api import app
from tukit_comercio.modelos import Base, EstadoPago, EstadoPedido
from tukit_comercio.pasarela import WompiSandbox, datos_widget


async def test_iniciar_pago_guarda_solo_referencia_y_estado(cliente):
    pedido_id = (await cliente.post("/v1/ordenes", json=nueva_orden())).json()["pedido_id"]
    respuesta = await cliente.post(
        f"/v1/ordenes/{pedido_id}/pago",
        json=SOLICITUD_PAGO,
    )
    assert respuesta.status_code == 201
    cuerpo = respuesta.json()
    assert cuerpo["referencia_wompi"] == f"tukit-{pedido_id}-1"
    assert cuerpo["estado"] == EstadoPago.INICIADO.value


async def test_iniciar_pago_en_sandbox_devuelve_el_widget_sin_redireccion(cliente):
    app.state.pasarela = WompiSandbox(llave_publica="pub_test_x", secreto_integridad="test_integrity_x")
    pedido_id = (await cliente.post("/v1/ordenes", json=nueva_orden())).json()["pedido_id"]
    cuerpo = (
        await cliente.post(
            f"/v1/ordenes/{pedido_id}/pago",
            json={**SOLICITUD_PAGO, "url_redireccion": URL_RESULTADO},
        )
    ).json()
    assert cuerpo["url_redireccion"] is None
    assert cuerpo["widget"]["redirectUrl"] == URL_RESULTADO
    assert cuerpo["widget"] == datos_widget(
        llave_publica="pub_test_x",
        referencia=cuerpo["referencia_wompi"],
        monto_centavos=centavos(nueva_orden()),
        secreto_integridad="test_integrity_x",
        correo=SOLICITUD_PAGO["correo_cliente"],
        url_redireccion=URL_RESULTADO,
    )


async def test_iniciar_pago_en_modo_falso_no_trae_widget(cliente):
    pedido_id = (await cliente.post("/v1/ordenes", json=nueva_orden())).json()["pedido_id"]
    cuerpo = (
        await cliente.post(
            f"/v1/ordenes/{pedido_id}/pago",
            json={**SOLICITUD_PAGO, "url_redireccion": URL_RESULTADO},
        )
    ).json()
    assert cuerpo["widget"] is None
    assert cuerpo["url_redireccion"].endswith("/pago/simulado?ref=" + cuerpo["referencia_wompi"])


async def test_iniciar_pago_con_pasarela_caida_da_502(cliente):
    pedido_id = (await cliente.post("/v1/ordenes", json=nueva_orden())).json()["pedido_id"]
    app.state.pasarela = PasarelaQueNoResponde()
    respuesta = await cliente.post(
        f"/v1/ordenes/{pedido_id}/pago",
        json=SOLICITUD_PAGO,
    )
    assert respuesta.status_code == 502
    assert respuesta.json()["error"] == "pasarela_no_disponible"


async def test_webhook_aprobado_transiciona_a_pagado(cliente):
    pedido_id, evento = await flujo_hasta_webhook(cliente, "APPROVED")
    respuesta = await cliente.post("/v1/webhooks/wompi", json=evento)
    assert respuesta.status_code == 200
    assert respuesta.json()["estado"] == "aplicado"

    pedido = (await cliente.get(f"/v1/ordenes/{pedido_id}")).json()
    assert pedido["estado"] == EstadoPedido.PAGADO.value
    assert pedido["pago"]["estado"] == EstadoPago.APROBADO.value


async def test_webhook_idempotente_no_mueve_dos_veces(cliente):
    pedido_id, evento = await flujo_hasta_webhook(cliente, "APPROVED")
    primera = await cliente.post("/v1/webhooks/wompi", json=evento)
    segunda = await cliente.post("/v1/webhooks/wompi", json=evento)
    assert primera.json()["estado"] == "aplicado"
    assert segunda.json()["estado"] == "repetido"

    async with app.state.motor.sesion() as db:
        conexion = await db.connection()
        tabla = Base.metadata.tables["evento_pasarela_procesado"]
        procesados = list(await conexion.execute(select(tabla)))
    assert len(procesados) == 1


async def test_webhook_con_firma_invalida_se_ignora(cliente):
    _, evento = await flujo_hasta_webhook(cliente, "APPROVED")
    evento["signature"]["checksum"] = "firma_que_no_cuadra"
    respuesta = await cliente.post("/v1/webhooks/wompi", json=evento)
    assert respuesta.json()["estado"] == "ignorado"
    assert respuesta.json()["motivo"] == "firma_invalida"


async def test_webhook_rechazado_no_pasa_a_pagado(cliente):
    pedido_id, evento = await flujo_hasta_webhook(cliente, "DECLINED")
    await cliente.post("/v1/webhooks/wompi", json=evento)
    pedido = (await cliente.get(f"/v1/ordenes/{pedido_id}")).json()
    assert pedido["estado"] == EstadoPedido.PENDIENTE_PAGO.value
    assert pedido["pago"]["estado"] == EstadoPago.RECHAZADO.value


async def test_webhook_con_monto_distinto_no_aprueba(cliente):
    pedido_id, _ = await flujo_hasta_webhook(cliente, "APPROVED")
    creada = app.state.pasarela.creadas[-1]
    evento = app.state.pasarela.emitir_evento(
        referencia=creada.referencia,
        transaccion_id=creada.transaccion_id,
        estado_wompi="APPROVED",
        monto_centavos=1,
    )
    respuesta = await cliente.post("/v1/webhooks/wompi", json=evento)
    assert respuesta.json()["estado"] == "monto_no_coincide"
    pedido = (await cliente.get(f"/v1/ordenes/{pedido_id}")).json()
    assert pedido["estado"] == EstadoPedido.PENDIENTE_PAGO.value
    assert pedido["pago"]["estado"] == EstadoPago.RECHAZADO.value


async def test_webhook_guarda_el_metodo_que_reporta_wompi(cliente):
    pedido_id, _ = await flujo_hasta_webhook(cliente, "APPROVED")
    creada = app.state.pasarela.creadas[-1]
    evento = app.state.pasarela.emitir_evento(
        referencia=creada.referencia,
        transaccion_id=creada.transaccion_id,
        estado_wompi="APPROVED",
        monto_centavos=centavos(nueva_orden()),
        metodo_wompi="CARD",
    )
    await cliente.post("/v1/webhooks/wompi", json=evento)
    pedido = (await cliente.get(f"/v1/ordenes/{pedido_id}")).json()
    assert pedido["pago"]["metodo"] == "tarjeta"


async def test_pago_aprobado_no_retrocede_con_eventos_tardios(cliente):
    pedido_id, evento = await flujo_hasta_webhook(cliente, "APPROVED")
    await cliente.post("/v1/webhooks/wompi", json=evento)
    creada = app.state.pasarela.creadas[-1]
    for estado_wompi, monto in (
        ("PENDING", centavos(nueva_orden())),
        ("DECLINED", centavos(nueva_orden())),
        ("APPROVED", 1),
    ):
        tardio = app.state.pasarela.emitir_evento(
            referencia=creada.referencia,
            transaccion_id=creada.transaccion_id,
            estado_wompi=estado_wompi,
            monto_centavos=monto,
        )
        respuesta = await cliente.post("/v1/webhooks/wompi", json=tardio)
        assert respuesta.json()["estado"] == "repetido"
        pedido = (await cliente.get(f"/v1/ordenes/{pedido_id}")).json()
        assert pedido["estado"] == EstadoPedido.PAGADO.value
        assert pedido["pago"]["estado"] == EstadoPago.APROBADO.value


async def test_reintento_tras_rechazo_crea_otro_pago(cliente):
    pedido_id, evento = await flujo_hasta_webhook(cliente, "DECLINED")
    await cliente.post("/v1/webhooks/wompi", json=evento)
    primera = app.state.pasarela.creadas[-1]

    segundo = await cliente.post(
        f"/v1/ordenes/{pedido_id}/pago",
        json=SOLICITUD_PAGO,
    )
    assert segundo.status_code == 201
    cuerpo = segundo.json()
    assert cuerpo["referencia_wompi"] != primera.referencia

    evento2 = app.state.pasarela.emitir_evento(
        referencia=cuerpo["referencia_wompi"],
        transaccion_id=cuerpo["transaccion_wompi"],
        estado_wompi="APPROVED",
        monto_centavos=centavos(nueva_orden()),
    )
    await cliente.post("/v1/webhooks/wompi", json=evento2)
    pedido = (await cliente.get(f"/v1/ordenes/{pedido_id}")).json()
    assert pedido["estado"] == EstadoPedido.PAGADO.value


async def test_reintento_tras_rechazo_no_colisiona_la_referencia(cliente):
    pedido_id, evento = await flujo_hasta_webhook(cliente, "DECLINED")
    await cliente.post("/v1/webhooks/wompi", json=evento)

    reintento = await cliente.post(
        f"/v1/ordenes/{pedido_id}/pago",
        json=SOLICITUD_PAGO,
    )
    assert reintento.status_code == 201
    assert reintento.json()["referencia_wompi"] == f"tukit-{pedido_id}-2"
