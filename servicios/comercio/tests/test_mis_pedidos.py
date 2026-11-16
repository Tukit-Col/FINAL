"""Los pedidos del acudiente (`/v1/comercio/mis-pedidos`): solo los suyos, sin datos del staff.

El usuario sale de la SESION, nunca de la URL. Un pedido ajeno responde 404 como
uno inexistente. La linea de tiempo de `/pedidos/[id]` muestra que paso y
cuando, sin actor, correo, nota ni el celular del repartidor.
"""

from __future__ import annotations

import uuid

from _ayudas_comercio import (
    CELULAR,
    REPARTIDOR,
    SOLICITUD_PAGO,
    USUARIO,
    avanzar,
    nueva_orden,
    pedido_pagado,
    total_de,
)
from conftest import OPERADOR, OTRO_ACUDIENTE, TOKEN_ACUDIENTE, TOKEN_OTRO, bearer
from sqlalchemy import select
from tukit_comercio.api import app
from tukit_comercio.modelos import EstadoPedido, Pedido

# --- El listado ---------------------------------------------------------------


async def test_mis_pedidos_exige_sesion(cliente):
    respuesta = await cliente.get("/v1/comercio/mis-pedidos")
    assert respuesta.status_code == 401
    con_sesion = await cliente.get("/v1/comercio/mis-pedidos", headers=bearer(TOKEN_ACUDIENTE))
    assert con_sesion.status_code == 200
    assert con_sesion.json() == {"total": 0, "pedidos": []}


async def test_mis_pedidos_ignora_el_usuario_de_la_url(cliente):
    # El pedido es del acudiente; "otro" pide los suyos con el id del acudiente
    # en la URL y recibe solo los propios (ninguno).
    await pedido_pagado(cliente)
    acudiente = USUARIO
    respuesta = await cliente.get(
        f"/v1/comercio/mis-pedidos?usuario_id={acudiente}", headers=bearer(TOKEN_OTRO)
    )
    assert respuesta.status_code == 200
    assert respuesta.json()["total"] == 0


async def test_mis_pedidos_solo_devuelve_los_del_acudiente(cliente):
    # Dos pedidos del acudiente conocido y uno de otro usuario.
    await cliente.post("/v1/ordenes", json=nueva_orden())
    await cliente.post("/v1/ordenes", json=nueva_orden())
    otro = nueva_orden()
    otro["usuario_id"] = OTRO_ACUDIENTE
    await cliente.post("/v1/ordenes", json=otro)

    # El usuario sale del token, no de la URL.
    mios = (await cliente.get("/v1/comercio/mis-pedidos", headers=bearer(TOKEN_ACUDIENTE))).json()
    assert mios["total"] == 2
    assert all(p["total"] == total_de(nueva_orden()) for p in mios["pedidos"])
    # Cada pedido trae su linea de tiempo, sin actor ni notas del staff.
    for p in mios["pedidos"]:
        assert [x["paso"] for x in p["linea_de_tiempo"]["pasos"]][0] == "creado"
        assert "historial" not in p["linea_de_tiempo"]

    ajenos = (await cliente.get("/v1/comercio/mis-pedidos", headers=bearer(TOKEN_OTRO))).json()
    assert ajenos["total"] == 1


# --- Un pedido propio ----------------------------------------------------------


async def test_el_acudiente_ve_paga_y_cancela_su_pedido_con_su_sesion(cliente):
    pedido_id = (await cliente.post("/v1/ordenes", json=nueva_orden())).json()["pedido_id"]
    propio = bearer(TOKEN_ACUDIENTE)

    visto = await cliente.get(f"/v1/comercio/mis-pedidos/{pedido_id}", headers=propio)
    assert visto.status_code == 200
    assert visto.json()["pedido_id"] == pedido_id

    pago = await cliente.post(
        f"/v1/comercio/mis-pedidos/{pedido_id}/pago",
        json=SOLICITUD_PAGO,
        headers=propio,
    )
    assert pago.status_code == 201
    assert pago.json()["referencia_wompi"] == f"tukit-{pedido_id}-1"

    cancelado = await cliente.post(f"/v1/comercio/mis-pedidos/{pedido_id}/cancelar", headers=propio)
    assert cancelado.status_code == 200
    assert cancelado.json()["estado"] == EstadoPedido.CANCELADO.value


async def test_un_pedido_ajeno_es_404_y_sin_sesion_es_401(cliente):
    pedido_id = (await cliente.post("/v1/ordenes", json=nueva_orden())).json()["pedido_id"]

    for metodo, ruta in (
        ("GET", f"/v1/comercio/mis-pedidos/{pedido_id}"),
        ("POST", f"/v1/comercio/mis-pedidos/{pedido_id}/cancelar"),
    ):
        ajeno = await cliente.request(metodo, ruta, headers=bearer(TOKEN_OTRO))
        assert ajeno.status_code == 404
        assert ajeno.json()["error"] == "pedido_no_existe"
        assert (await cliente.request(metodo, ruta)).status_code == 401

    # Nada se movio: el pedido del otro sigue pendiente.
    async with app.state.motor.sesion() as db:
        conexion = await db.connection()
        estado = await conexion.scalar(
            select(Pedido.__table__.c.estado).where(Pedido.__table__.c.id == uuid.UUID(pedido_id))
        )
    assert estado == EstadoPedido.PENDIENTE_PAGO.value


# --- La linea de tiempo de `/pedidos/[id]` -----------------------------------


async def test_el_acudiente_ve_la_linea_de_tiempo_de_su_pedido_sin_datos_del_staff(cliente):
    pedido_id = await pedido_pagado(cliente)
    await avanzar(cliente, pedido_id, {"destino": "en_preparacion"})
    await avanzar(cliente, pedido_id, {"destino": "despachado", **REPARTIDOR})
    await avanzar(
        cliente, pedido_id, {"destino": "incidencia", "tipo_incidencia": "otro", "nota": "Perro bravo"}
    )

    respuesta = await cliente.get(f"/v1/comercio/mis-pedidos/{pedido_id}", headers=bearer(TOKEN_ACUDIENTE))
    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    # La linea de tiempo se agrega al pedido, no lo reemplaza.
    assert cuerpo["pedido_id"] == pedido_id
    assert cuerpo["lineas"] and cuerpo["envio"]["direccion"]

    linea = cuerpo["linea_de_tiempo"]
    assert [(p["paso"], p["estado"]) for p in linea["pasos"]] == [
        ("creado", "hecho"),
        ("pagado", "hecho"),
        ("en_preparacion", "hecho"),
        ("despachado", "actual"),
        ("en_reparto", "futuro"),
        ("entregado", "futuro"),
    ]
    assert all(p["fecha"] for p in linea["pasos"][:4])
    assert linea["pasos"][3]["repartidor_nombre"] == "Luis Gomez"
    assert linea["especial"]["tipo"] == "incidencia"
    assert linea["especial"]["tipo_incidencia"] == "otro"

    # Nada del staff: ni el historial crudo, ni quien avanzo, ni la nota, ni el
    # celular del repartidor.
    texto = respuesta.text
    assert "historial" not in cuerpo
    for prohibido in ("actor_id", "actor_correo", "nota", "Perro bravo", CELULAR, OPERADOR, "@tukit.test"):
        assert prohibido not in texto


async def test_la_linea_de_tiempo_de_un_pedido_ajeno_o_inexistente_da_404(cliente):
    pedido_id = await pedido_pagado(cliente)
    ajeno = await cliente.get(f"/v1/comercio/mis-pedidos/{pedido_id}", headers=bearer(TOKEN_OTRO))
    assert ajeno.status_code == 404
    assert "linea_de_tiempo" not in ajeno.text
    inexistente = await cliente.get(
        f"/v1/comercio/mis-pedidos/{uuid.uuid4()}", headers=bearer(TOKEN_ACUDIENTE)
    )
    assert inexistente.status_code == 404


async def test_la_linea_de_tiempo_exige_sesion(cliente):
    pedido_id = await pedido_pagado(cliente)
    assert (await cliente.get(f"/v1/comercio/mis-pedidos/{pedido_id}")).status_code == 401


async def test_un_pedido_pendiente_trae_su_vencimiento(cliente):
    orden = (await cliente.post("/v1/ordenes", json=nueva_orden())).json()
    respuesta = await cliente.get(
        f"/v1/comercio/mis-pedidos/{orden['pedido_id']}", headers=bearer(TOKEN_ACUDIENTE)
    )
    linea = respuesta.json()["linea_de_tiempo"]
    assert linea["pasos"][0]["estado"] == "actual"
    assert linea["pago_pendiente"]["vencido"] is False
    assert linea["pago_pendiente"]["vence_en"]
