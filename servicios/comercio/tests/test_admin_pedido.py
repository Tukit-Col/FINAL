from __future__ import annotations

from _ayudas_comercio import OPERADOR_HDR, REPARTIDOR, avanzar, pedido_pagado, poner_estado
from conftest import TOKEN_ACUDIENTE, bearer


async def _detalle(cliente, pedido_id, headers=OPERADOR_HDR):
    return await cliente.get(f"/v1/comercio/pedidos/{pedido_id}", headers=headers)


async def test_detalle_trae_la_transaccion_de_wompi_solo_para_staff(cliente):
    pedido_id = await pedido_pagado(cliente)
    staff = (await _detalle(cliente, pedido_id)).json()
    assert staff["pago"]["transaccion_wompi"]
    assert staff["pago"]["actualizado_en"]
    suyo = await cliente.get(f"/v1/comercio/mis-pedidos/{pedido_id}", headers=bearer(TOKEN_ACUDIENTE))
    assert "transaccion_wompi" not in (suyo.json().get("pago") or {})


async def test_retracto_aparece_con_plazo_y_limite_de_reembolso(cliente):
    pedido_id = await pedido_pagado(cliente)
    for destino, extra in (
        ("en_preparacion", {}),
        ("despachado", REPARTIDOR),
        ("en_reparto", {}),
        ("entregado", {}),
    ):
        assert (await avanzar(cliente, pedido_id, {"destino": destino, **extra})).json()["estado"] == destino
    await cliente.post(f"/v1/ordenes/{pedido_id}/retracto", json={"motivo": "No me sirvio"})
    devoluciones = (await _detalle(cliente, pedido_id)).json()["devoluciones"]
    assert len(devoluciones) == 1
    d = devoluciones[0]
    assert d["motivo"] == "No me sirvio"
    assert d["plazo_retracto"] is not None
    assert d["dentro_de_plazo"] is True
    assert d["limite_reembolso"]


async def test_sin_retractos_la_lista_viene_vacia(cliente):
    pedido_id = await pedido_pagado(cliente)
    assert (await _detalle(cliente, pedido_id)).json()["devoluciones"] == []


async def test_despacho_por_transportadora_guarda_guia_y_no_repartidor(cliente):
    pedido_id = await pedido_pagado(cliente)
    await poner_estado(pedido_id, "en_preparacion")
    respuesta = await avanzar(
        cliente, pedido_id, {"destino": "despachado", "transportadora": "Servientrega", "guia": "SV-123"}
    )
    assert respuesta.status_code == 200
    envio = respuesta.json()["envio"]
    assert (envio["transportadora"], envio["guia"]) == ("Servientrega", "SV-123")
    assert envio["repartidor_nombre"] is None


async def test_despacho_con_transportadora_sin_guia_da_422(cliente):
    pedido_id = await pedido_pagado(cliente)
    await poner_estado(pedido_id, "en_preparacion")
    cuerpo = {"destino": "despachado", "transportadora": "Servientrega"}
    respuesta = await avanzar(cliente, pedido_id, cuerpo)
    assert respuesta.status_code == 422
    assert respuesta.json()["campo"] == "guia"
    assert (await _detalle(cliente, pedido_id)).json()["estado"] == "en_preparacion"
