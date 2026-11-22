from __future__ import annotations

import httpx
from _ayudas_comercio import BANDEJA, HISTORIAL, OPERADOR_HDR, SOLICITUD_PAGO, filas_de, nueva_orden
from conftest import TOKEN_ADMIN, bearer
from tukit_comercio.api import app
from tukit_comercio.pasarela import PasarelaCaida


async def _pendiente(cliente: httpx.AsyncClient) -> tuple[str, str]:
    orden = (await cliente.post("/v1/ordenes", json=nueva_orden())).json()
    pedido_id = orden["pedido_id"]
    pago = (await cliente.post(f"/v1/ordenes/{pedido_id}/pago", json=SOLICITUD_PAGO)).json()
    return pedido_id, pago["referencia_wompi"]


def _url(pedido_id: str) -> str:
    return f"/v1/comercio/pedidos/{pedido_id}/reconciliar-pago"


async def _avisos_pagado(pedido_id: str) -> int:
    return len([f for f in await filas_de(BANDEJA, pedido_id) if f.tipo == "pedido_pagado"])


async def test_aprobado_en_wompi_pasa_a_pagado_una_sola_vez(cliente):
    pedido_id, referencia = await _pendiente(cliente)
    app.state.pasarela.fijar_resultado(referencia, "APPROVED")
    r = await cliente.post(_url(pedido_id), headers=OPERADOR_HDR)
    assert r.status_code == 200, r.text
    assert r.json() == {"pedido_id": pedido_id, "resultado": "pagado", "estado_pedido": "pagado"}
    assert await _avisos_pagado(pedido_id) == 1
    historial = await filas_de(HISTORIAL, pedido_id)
    assert [(h.estado_desde, h.estado_hacia) for h in historial] == [("pendiente_pago", "pagado")]

    segunda = await cliente.post(_url(pedido_id), headers=OPERADOR_HDR)
    assert segunda.status_code == 409
    assert segunda.json()["error"] == "pedido_no_reconciliable"
    assert await _avisos_pagado(pedido_id) == 1


async def test_en_curso_no_cambia_el_estado(cliente):
    pedido_id, referencia = await _pendiente(cliente)
    app.state.pasarela.fijar_resultado(referencia, "PENDING")
    r = await cliente.post(_url(pedido_id), headers=OPERADOR_HDR)
    assert r.json() == {"pedido_id": pedido_id, "resultado": "en_curso", "estado_pedido": "pendiente_pago"}
    assert await filas_de(HISTORIAL, pedido_id) == []


async def test_rechazado_queda_libre(cliente):
    pedido_id, referencia = await _pendiente(cliente)
    app.state.pasarela.fijar_resultado(referencia, "DECLINED")
    r = await cliente.post(_url(pedido_id), headers=OPERADOR_HDR)
    assert r.json()["resultado"] == "libre"
    assert r.json()["estado_pedido"] == "pendiente_pago"


async def test_pasarela_caida_es_502_y_deja_el_pedido_intacto(cliente):
    pedido_id, _ = await _pendiente(cliente)

    async def caida(referencia):
        raise PasarelaCaida("sin red")

    app.state.pasarela.consultar_por_referencia = caida
    r = await cliente.post(_url(pedido_id), headers=OPERADOR_HDR)
    assert r.status_code == 502
    assert r.json()["error"] == "pasarela_no_disponible"
    detalle = (await cliente.get(f"/v1/comercio/pedidos/{pedido_id}", headers=OPERADOR_HDR)).json()
    assert detalle["estado"] == "pendiente_pago"


async def test_pedido_inexistente_es_404(cliente):
    r = await cliente.post(_url("00000000-0000-4000-8000-000000000000"), headers=OPERADOR_HDR)
    assert r.status_code == 404


async def test_el_admin_tambien_reconcilia(cliente):
    pedido_id, referencia = await _pendiente(cliente)
    app.state.pasarela.fijar_resultado(referencia, "DECLINED")
    r = await cliente.post(_url(pedido_id), headers=bearer(TOKEN_ADMIN))
    assert r.status_code == 200
    assert r.json() == {"pedido_id": pedido_id, "resultado": "libre", "estado_pedido": "pendiente_pago"}
