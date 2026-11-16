"""Deduplicar ordenes del mismo kit (trabajo).

Si el acudiente vuelve a cerrar el mismo kit con la misma entrega, Comercio
reutiliza el pedido pendiente; si cambia la entrega (otra direccion, localidad,
apartamento o pin), cancela el pendiente y crea otro, porque el envio es una
copia congelada (ADR 0015). Un pendiente con pago en curso no se cancela, y uno
vencido no se reutiliza. Las ordenes sin kit nunca se deduplican.
"""

from __future__ import annotations

import pytest
from _ayudas_comercio import (
    OPERADOR_HDR,
    envejecer,
    estado_de,
    nueva_orden,
    pagar,
)
from tukit_comercio.api import app
from tukit_comercio.dominio.pagos import VIGENCIA_PAGO
from tukit_comercio.modelos import EstadoPedido

TRABAJO = "33333333-3333-5333-8333-333333333333"


def _orden_kit(**cambios) -> dict:
    """Una orden ligada a un kit (trabajo), que es lo que deduplica Comercio."""
    return {**nueva_orden(), "trabajo_id": TRABAJO, **cambios}


def _con_otra_direccion() -> dict:
    orden = _orden_kit()
    orden["entrega"] = {**orden["entrega"], "direccion": "Carrera 9 # 8-7"}
    return orden


def _con_entrega(**campos) -> dict:
    orden = _orden_kit()
    orden["entrega"] = {**orden["entrega"], **campos}
    return orden


async def test_orden_identica_del_mismo_kit_reutiliza_el_pedido_pendiente(cliente):
    primero = (await cliente.post("/v1/ordenes", json=_orden_kit())).json()
    segundo = await cliente.post("/v1/ordenes", json=_orden_kit())
    assert segundo.status_code == 201
    assert segundo.json()["pedido_id"] == primero["pedido_id"]
    tablero = (await cliente.get("/v1/comercio/pedidos", headers=OPERADOR_HDR)).json()
    assert tablero["resumen"]["pedidos_totales"] == 1


async def test_orden_identica_con_localidad_reutiliza_aunque_cambie_el_place_id(cliente):
    # El place_id apunta al mismo texto de la direccion: no hace otra entrega.
    primero = (
        await cliente.post("/v1/ordenes", json=_con_entrega(localidad="Suba", google_place_id="a"))
    ).json()
    segundo = (
        await cliente.post("/v1/ordenes", json=_con_entrega(localidad="Suba", google_place_id="b"))
    ).json()
    assert segundo["pedido_id"] == primero["pedido_id"]


async def test_orden_con_campos_de_entrega_vacios_reutiliza_la_que_no_los_traia(cliente):
    # Un campo ausente y uno vacio son la misma entrega.
    primero = (await cliente.post("/v1/ordenes", json=_orden_kit())).json()
    segundo = (await cliente.post("/v1/ordenes", json=_con_entrega(localidad="", indicaciones=""))).json()
    assert segundo["pedido_id"] == primero["pedido_id"]


@pytest.mark.parametrize(
    "cambio",
    [{"localidad": "Usaquén"}, {"indicaciones": "Apto 301"}, {"departamento": "Cundinamarca"}],
)
async def test_orden_del_mismo_kit_con_otra_entrega_cancela_y_crea(cliente, cambio):
    # El envio es una copia congelada (ADR 0015): reutilizar el pendiente con
    # otra localidad u otro apartamento despacharia con los datos viejos.
    primero = (await cliente.post("/v1/ordenes", json=_con_entrega(localidad="Chapinero"))).json()
    segundo = (
        await cliente.post("/v1/ordenes", json=_con_entrega(**{"localidad": "Chapinero", **cambio}))
    ).json()
    assert segundo["pedido_id"] != primero["pedido_id"]
    assert segundo["envio"] == {**segundo["envio"], **cambio}
    assert await estado_de(cliente, primero["pedido_id"]) == EstadoPedido.CANCELADO.value


async def test_orden_distinta_del_mismo_kit_cancela_la_pendiente_anterior(cliente):
    primero = (await cliente.post("/v1/ordenes", json=_orden_kit())).json()
    segundo = (await cliente.post("/v1/ordenes", json=_con_otra_direccion())).json()
    assert segundo["pedido_id"] != primero["pedido_id"]
    assert await estado_de(cliente, primero["pedido_id"]) == EstadoPedido.CANCELADO.value


async def test_orden_distinta_no_cancela_la_anterior_si_su_pago_esta_en_curso(cliente):
    primero = (await cliente.post("/v1/ordenes", json=_orden_kit())).json()
    pago = await pagar(cliente, primero["pedido_id"])
    app.state.pasarela.fijar_resultado(pago["referencia_wompi"], "PENDING")
    segundo = (await cliente.post("/v1/ordenes", json=_con_otra_direccion())).json()
    assert segundo["pedido_id"] != primero["pedido_id"]
    assert await estado_de(cliente, primero["pedido_id"]) == EstadoPedido.PENDIENTE_PAGO.value


async def test_orden_identica_pero_vencida_crea_otra_y_cancela_la_vieja(cliente):
    primero = (await cliente.post("/v1/ordenes", json=_orden_kit())).json()
    await envejecer(primero["pedido_id"], horas=VIGENCIA_PAGO.total_seconds() / 3600 + 1)
    segundo = (await cliente.post("/v1/ordenes", json=_orden_kit())).json()
    assert segundo["pedido_id"] != primero["pedido_id"]
    assert await estado_de(cliente, primero["pedido_id"]) == EstadoPedido.CANCELADO.value


async def test_ordenes_sin_kit_no_se_deduplican(cliente):
    a = (await cliente.post("/v1/ordenes", json=nueva_orden())).json()
    b = (await cliente.post("/v1/ordenes", json=nueva_orden())).json()
    assert a["pedido_id"] != b["pedido_id"]


async def test_mover_el_pin_no_reutiliza_el_pendiente(cliente):
    # Mismo texto, otro punto: el repartidor iria al sitio viejo si se reutilizara.
    a = (await cliente.post("/v1/ordenes", json=_con_entrega(latitud=4.65, longitud=-74.05))).json()
    b = (await cliente.post("/v1/ordenes", json=_con_entrega(latitud=4.70, longitud=-74.07))).json()
    c = (await cliente.post("/v1/ordenes", json=_con_entrega(latitud=4.70, longitud=-74.07))).json()
    assert a["pedido_id"] != b["pedido_id"]
    assert b["pedido_id"] == c["pedido_id"]
