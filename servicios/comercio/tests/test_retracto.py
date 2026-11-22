from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, timedelta

from _ayudas_comercio import ENVIO, PEDIDO, flujo_hasta_webhook, nueva_orden, pedido_pagado, total_de
from conftest import TOKEN_ACUDIENTE, TOKEN_OTRO, bearer
from sqlalchemy import update
from tukit_comercio.api import app
from tukit_comercio.dominio.retracto import (
    evaluar_retracto,
    festivos,
    linea_de_tiempo,
    sumar_dias_habiles,
    vence_retracto,
)
from tukit_comercio.modelos import EstadoPago, EstadoPedido


def test_los_festivos_de_colombia_2026_incluyen_los_trasladados():
    f = festivos(2026)
    assert date(2026, 1, 1) in f
    assert date(2026, 1, 12) in f
    assert date(2026, 4, 2) in f and date(2026, 4, 3) in f
    assert date(2026, 11, 2) in f
    assert date(2026, 11, 16) in f
    assert date(2026, 12, 8) in f and date(2026, 12, 25) in f
    assert date(2026, 11, 3) not in f


def test_cinco_dias_habiles_se_saltan_fines_de_semana_y_festivos():
    assert sumar_dias_habiles(date(2026, 10, 30), 1) == date(2026, 11, 3)
    assert sumar_dias_habiles(date(2026, 10, 30), 5) == date(2026, 11, 9)
    assert sumar_dias_habiles(date(2026, 3, 4), 5) == date(2026, 3, 11)


def test_el_plazo_cierra_al_final_del_dia_local_no_en_utc():
    entregado = datetime(2026, 3, 5, 1, 0, tzinfo=UTC)
    vence = vence_retracto(entregado)
    assert vence == datetime(2026, 3, 12, 4, 59, 59, tzinfo=UTC)


def test_pedido_entregado_dentro_y_fuera_del_plazo():
    entregado = datetime(2026, 3, 4, 15, 0, tzinfo=UTC)
    dentro = evaluar_retracto("entregado", entregado, entregado + timedelta(days=6), ya_solicitado=False)
    assert dentro.puede and dentro.vence_en is not None
    fuera = evaluar_retracto("entregado", entregado, entregado + timedelta(days=9), ya_solicitado=False)
    assert not fuera.puede and fuera.razon == "plazo_vencido"


def test_estados_sin_retracto():
    ahora = datetime(2026, 3, 4, tzinfo=UTC)
    assert evaluar_retracto("pendiente_pago", None, ahora, ya_solicitado=False).razon == "sin_pagar"
    assert evaluar_retracto("cancelado", None, ahora, ya_solicitado=False).razon == "cancelado"
    assert evaluar_retracto("pagado", None, ahora, ya_solicitado=True).razon == "ya_solicitado"
    assert evaluar_retracto("pagado", None, ahora, ya_solicitado=False).antes_de_entrega


def test_la_linea_de_tiempo_no_filtra_al_equipo_interno():
    t0 = datetime(2026, 3, 1, tzinfo=UTC)
    pasos = linea_de_tiempo(
        creado_en=t0,
        pago_aprobado_en=t0 + timedelta(minutes=5),
        historial=[
            {
                "estado_hacia": "incidencia",
                "creado_en": t0 + timedelta(days=1),
                "actor_correo": "operador@tukit.co",
                "nota": "interno",
            }
        ],
        entregado_en=None,
    )
    assert [p["estado"] for p in pasos] == ["pendiente_pago", "pagado", "incidencia"]
    assert all(set(p) == {"estado", "en", "etiqueta"} for p in pasos)


async def _entregar(pedido_id: str, entregado_en: datetime) -> None:
    async with app.state.motor.sesion() as db:
        conexion = await db.connection()
        pid = uuid.UUID(pedido_id)
        await conexion.execute(update(PEDIDO).where(PEDIDO.c.id == pid).values(estado="entregado"))
        await conexion.execute(
            update(ENVIO).where(ENVIO.c.pedido_id == pid).values(entregado_en=entregado_en)
        )


def _retracto(cliente, pedido_id, token=TOKEN_ACUDIENTE, motivo="no lo necesito"):
    return cliente.post(
        f"/v1/comercio/mis-pedidos/{pedido_id}/retracto", json={"motivo": motivo}, headers=bearer(token)
    )


async def test_retracto_dentro_del_plazo_registra_la_solicitud_y_se_puede_pedir_una_sola_vez(cliente, reloj):
    pedido_id = await pedido_pagado(cliente)
    entregado = datetime(2026, 3, 4, 15, 0, tzinfo=UTC)
    await _entregar(pedido_id, entregado)
    reloj(entregado + timedelta(days=3))

    ficha = (
        await cliente.get(f"/v1/comercio/mis-pedidos/{pedido_id}", headers=bearer(TOKEN_ACUDIENTE))
    ).json()
    assert ficha["retracto"]["puede"] is True
    assert ficha["retracto"]["vence_en"].startswith("2026-03-12")

    respuesta = await _retracto(cliente, pedido_id)
    assert respuesta.status_code == 201
    cuerpo = respuesta.json()
    assert cuerpo["devolucion_id"] and cuerpo["monto"] == total_de(nueva_orden())
    assert cuerpo["cancelado"] is False

    ficha = (
        await cliente.get(f"/v1/comercio/mis-pedidos/{pedido_id}", headers=bearer(TOKEN_ACUDIENTE))
    ).json()
    assert ficha["retracto"]["puede"] is False
    assert ficha["retracto"]["razon"] == "ya_solicitado"
    assert ficha["retracto"]["solicitado_en"]

    otra = await _retracto(cliente, pedido_id)
    assert otra.status_code == 409
    assert otra.json()["error"] == "retracto_ya_solicitado"


async def test_retracto_con_el_plazo_vencido_es_409(cliente, reloj):
    pedido_id = await pedido_pagado(cliente)
    entregado = datetime(2026, 3, 4, 15, 0, tzinfo=UTC)
    await _entregar(pedido_id, entregado)
    reloj(entregado + timedelta(days=10))

    respuesta = await _retracto(cliente, pedido_id)
    assert respuesta.status_code == 409
    assert respuesta.json()["error"] == "retracto_plazo_vencido"
    ficha = (
        await cliente.get(f"/v1/comercio/mis-pedidos/{pedido_id}", headers=bearer(TOKEN_ACUDIENTE))
    ).json()
    assert ficha["retracto"]["puede"] is False and ficha["retracto"]["razon"] == "plazo_vencido"


async def test_retracto_de_un_pedido_ajeno_es_403_y_no_toca_nada(cliente, reloj):
    pedido_id = await pedido_pagado(cliente)
    reloj(datetime(2026, 3, 5, tzinfo=UTC))

    respuesta = await _retracto(cliente, pedido_id, token=TOKEN_OTRO)
    assert respuesta.status_code == 403
    assert respuesta.json()["error"] == "pedido_ajeno"
    ficha = (
        await cliente.get(f"/v1/comercio/mis-pedidos/{pedido_id}", headers=bearer(TOKEN_ACUDIENTE))
    ).json()
    assert ficha["estado"] == EstadoPedido.PAGADO.value
    assert ficha["retracto"]["puede"] is True


async def test_retracto_sin_sesion_es_401_y_de_un_pedido_inexistente_404(cliente):
    pedido_id = await pedido_pagado(cliente)
    sin = await cliente.post(f"/v1/comercio/mis-pedidos/{pedido_id}/retracto", json={})
    assert sin.status_code == 401
    inexistente = await _retracto(cliente, uuid.uuid4())
    assert inexistente.status_code == 404


async def test_retracto_antes_de_la_entrega_cancela_y_marca_el_reembolso(cliente, reloj):
    pedido_id = await pedido_pagado(cliente)
    reloj(datetime(2026, 3, 5, tzinfo=UTC))

    respuesta = await _retracto(cliente, pedido_id)
    assert respuesta.status_code == 201
    assert respuesta.json()["cancelado"] is True

    ficha = (
        await cliente.get(f"/v1/comercio/mis-pedidos/{pedido_id}", headers=bearer(TOKEN_ACUDIENTE))
    ).json()
    assert ficha["estado"] == EstadoPedido.CANCELADO.value
    assert ficha["pago"]["estado"] == EstadoPago.REEMBOLSADO.value


async def test_el_retracto_por_la_ruta_interna_cancela_y_marca_reembolso(cliente):
    pedido_id, evento = await flujo_hasta_webhook(cliente, "APPROVED")
    await cliente.post("/v1/webhooks/wompi", json=evento)
    respuesta = await cliente.post(f"/v1/ordenes/{pedido_id}/retracto", json={"motivo": "no lo quiero"})
    assert respuesta.status_code == 201
    cuerpo = respuesta.json()
    assert cuerpo["devolucion_id"]
    assert cuerpo["cancelado"] is True
    assert cuerpo["estado"] == EstadoPedido.CANCELADO.value

    pedido = (await cliente.get(f"/v1/ordenes/{pedido_id}")).json()
    assert pedido["estado"] == EstadoPedido.CANCELADO.value
    assert pedido["pago"]["estado"] == EstadoPago.REEMBOLSADO.value


async def test_pedido_sin_pagar_no_admite_retracto(cliente, reloj):
    orden = (await cliente.post("/v1/ordenes", json=nueva_orden())).json()
    reloj(datetime(2026, 3, 5, tzinfo=UTC))
    respuesta = await _retracto(cliente, orden["pedido_id"])
    assert respuesta.status_code == 409
    assert respuesta.json()["error"] == "retracto_sin_pagar"


async def test_mis_pedidos_trae_linea_de_tiempo_sin_datos_internos(cliente):
    await pedido_pagado(cliente)
    cuerpo = (await cliente.get("/v1/comercio/mis-pedidos", headers=bearer(TOKEN_ACUDIENTE))).json()
    pedido = cuerpo["pedidos"][0]
    estados = [p["estado"] for p in pedido["seguimiento"]]
    assert estados[:2] == ["pendiente_pago", "pagado"]
    assert "retracto" in pedido
    assert "repartidor_celular" not in (pedido["envio"] or {})
    assert "historial" not in pedido


def test_acudiente_y_back_office_ven_el_mismo_plazo():
    from tukit_comercio.dominio.ley1480 import BOGOTA, evaluar_devolucion

    for entregado in (
        datetime(2026, 3, 5, 1, 0, tzinfo=UTC),
        datetime(2026, 10, 30, 15, 0, tzinfo=UTC),
        datetime(2026, 4, 1, 12, 0, tzinfo=UTC),
    ):
        vence = vence_retracto(entregado)
        staff = evaluar_devolucion(entregado, entregado)
        assert vence.astimezone(BOGOTA).date().isoformat() == staff["plazo_retracto"]
