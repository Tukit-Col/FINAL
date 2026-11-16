"""Sincronizar el pago al regreso del acudiente (`/v1/pagos/{transaccion}/sincronizar`).

El navegador vuelve de Wompi con el id de la transaccion; Comercio la consulta
y aplica el resultado con las mismas reglas del webhook: idempotente, sin
revivir un rechazo, sin duplicar el aviso `pedido_pagado`, y con una red de
seguridad si llega una aprobacion para un pedido ya cancelado.
"""

from __future__ import annotations

import uuid

from _ayudas_comercio import (
    SOLICITUD_PAGO,
    URL_RESULTADO,
    avisos_en_bandeja,
    centavos,
    nueva_orden,
    pedido_con_pago,
    total_de,
)
from sqlalchemy.exc import IntegrityError
from tukit_comercio.api import app
from tukit_comercio.modelos import EstadoPago, EstadoPedido
from tukit_comercio.pasarela import PasarelaCaida


async def test_sincronizar_aprobado_marca_pagado(cliente):
    pedido_id, ref = await pedido_con_pago(cliente)
    r = await cliente.post(f"/v1/pagos/falsa-APPROVED-{ref}/sincronizar")
    assert r.status_code == 200
    assert r.json() == {
        "pedido_id": pedido_id,
        "total": total_de(nueva_orden()),
        "estado_pago": "aprobado",
        "estado_pedido": "pagado",
        "trabajo_id": None,
    }


async def test_sincronizar_devuelve_el_trabajo_del_pedido(cliente):
    trabajo = str(uuid.uuid4())
    orden = {**nueva_orden(), "trabajo_id": trabajo}
    pedido_id = (await cliente.post("/v1/ordenes", json=orden)).json()["pedido_id"]
    pago = (
        await cliente.post(
            f"/v1/ordenes/{pedido_id}/pago",
            json={**SOLICITUD_PAGO, "url_redireccion": URL_RESULTADO},
        )
    ).json()
    r = await cliente.post(f"/v1/pagos/falsa-DECLINED-{pago['referencia_wompi']}/sincronizar")
    assert r.status_code == 200
    assert r.json()["trabajo_id"] == trabajo


async def test_pendiente_tardio_no_revive_un_pago_rechazado(cliente):
    _, ref = await pedido_con_pago(cliente)
    await cliente.post(f"/v1/pagos/falsa-DECLINED-{ref}/sincronizar")
    r = await cliente.post(f"/v1/pagos/falsa-PENDING-{ref}/sincronizar")
    assert r.status_code == 200
    assert r.json()["estado_pago"] == "rechazado"
    assert r.json()["estado_pedido"] == "pendiente_pago"


async def test_sincronizar_dos_veces_no_duplica_el_aviso(cliente):
    _, ref = await pedido_con_pago(cliente)
    primera = await cliente.post(f"/v1/pagos/falsa-APPROVED-{ref}/sincronizar")
    segunda = await cliente.post(f"/v1/pagos/falsa-APPROVED-{ref}/sincronizar")
    assert primera.status_code == segunda.status_code == 200
    assert primera.json() == segunda.json()
    assert await avisos_en_bandeja("pedido_pagado") == 1


async def test_webhook_despues_de_sincronizar_es_repetido(cliente):
    _, ref = await pedido_con_pago(cliente)
    await cliente.post(f"/v1/pagos/falsa-APPROVED-{ref}/sincronizar")
    evento = app.state.pasarela.emitir_evento(
        referencia=ref,
        transaccion_id=f"falsa-APPROVED-{ref}",
        estado_wompi="APPROVED",
        monto_centavos=centavos(nueva_orden()),
    )
    r = await cliente.post("/v1/webhooks/wompi", json=evento)
    assert r.json()["estado"] == "repetido"
    assert await avisos_en_bandeja("pedido_pagado") == 1


async def test_pendiente_y_luego_aprobado_avanza(cliente):
    _, ref = await pedido_con_pago(cliente)
    pendiente = await cliente.post(f"/v1/pagos/falsa-PENDING-{ref}/sincronizar")
    assert pendiente.status_code == 200
    assert pendiente.json()["estado_pago"] == "iniciado"
    assert pendiente.json()["estado_pedido"] == "pendiente_pago"
    aprobado = await cliente.post(f"/v1/pagos/falsa-APPROVED-{ref}/sincronizar")
    assert aprobado.json()["estado_pago"] == "aprobado"
    assert aprobado.json()["estado_pedido"] == "pagado"


async def test_sincronizar_rechazado_deja_pendiente(cliente):
    _, ref = await pedido_con_pago(cliente)
    r = await cliente.post(f"/v1/pagos/falsa-DECLINED-{ref}/sincronizar")
    assert r.status_code == 200
    assert r.json()["estado_pago"] == "rechazado"
    assert r.json()["estado_pedido"] == "pendiente_pago"


async def test_sincronizar_transaccion_desconocida_es_404(cliente):
    r = await cliente.post("/v1/pagos/falsa-APPROVED-tukit-nada/sincronizar")
    assert r.status_code == 404
    assert r.json()["error"] == "transaccion_no_existe"


async def test_sincronizar_referencia_sin_pago_es_404(cliente):
    # La pasarela la conoce pero Comercio no tiene ese pago.
    app.state.pasarela.montos["tukit-huerfano"] = centavos(nueva_orden())
    r = await cliente.post("/v1/pagos/falsa-APPROVED-tukit-huerfano/sincronizar")
    assert r.status_code == 404
    assert r.json()["error"] == "pago_no_existe"


async def test_sincronizar_con_pasarela_caida_es_502(cliente):
    class PasarelaCaidaDoble:
        async def consultar_transaccion(self, transaccion_id):
            raise PasarelaCaida("sin red")

    app.state.pasarela = PasarelaCaidaDoble()
    r = await cliente.post("/v1/pagos/falsa-APPROVED-tukit-x/sincronizar")
    assert r.status_code == 502
    assert r.json()["error"] == "pasarela_no_disponible"


async def test_sincronizar_reintenta_una_vez_si_choca_el_indice_unico(cliente, monkeypatch):
    """Webhook y regreso del usuario simultaneos: el segundo INSERT falla y se reintenta."""
    from tukit_comercio.repositorios import RepoPedidos

    pedido_id, ref = await pedido_con_pago(cliente)
    original = RepoPedidos.aplicar_resultado
    llamadas = {"n": 0}

    async def con_choque(repo, datos):
        llamadas["n"] += 1
        if llamadas["n"] == 1:
            # La "otra entrega" gana la carrera: aplica y confirma en su sesion.
            async with app.state.motor.sesion() as otra:
                await original(RepoPedidos(await otra.connection()), datos)
            raise IntegrityError("INSERT", {}, Exception("UNIQUE evento_id"))
        return await original(repo, datos)

    monkeypatch.setattr(RepoPedidos, "aplicar_resultado", con_choque)
    r = await cliente.post(f"/v1/pagos/falsa-APPROVED-{ref}/sincronizar")
    assert r.status_code == 200
    assert r.json() == {
        "pedido_id": pedido_id,
        "total": total_de(nueva_orden()),
        "estado_pago": "aprobado",
        "estado_pedido": "pagado",
        "trabajo_id": None,
    }
    assert llamadas["n"] == 2
    assert await avisos_en_bandeja("pedido_pagado") == 1


async def test_pago_aprobado_tras_cancelar_deja_una_incidencia(cliente):
    # Red de seguridad: si aun asi llega una aprobacion para un pedido
    # cancelado, el dinero no se pierde en silencio.
    pedido_id, ref = await pedido_con_pago(cliente)
    await cliente.post(f"/v1/ordenes/{pedido_id}/cancelar")
    r = await cliente.post(f"/v1/pagos/falsa-APPROVED-{ref}/sincronizar")
    assert r.json()["estado_pedido"] == EstadoPedido.CANCELADO.value
    assert r.json()["estado_pago"] == EstadoPago.APROBADO.value
    assert await avisos_en_bandeja("incidencia") == 1
    assert await avisos_en_bandeja("pedido_pagado") == 0
