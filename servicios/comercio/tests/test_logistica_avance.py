from __future__ import annotations

import uuid

import pytest
from _ayudas_comercio import (
    CELULAR,
    HISTORIAL,
    OPERADOR_HDR,
    PEDIDO,
    REPARTIDOR,
    USUARIO,
    avanzar,
    avisos_de,
    filas_de,
    pedido_pagado,
    poner_estado,
)
from conftest import ADMIN, OPERADOR, TOKEN_ADMIN, TOKEN_OPERADOR, bearer, sesiones_por_omision
from sqlalchemy import update
from tukit_comercio.api import app
from tukit_comercio.dominio.despacho import AVANCES_DE_LOGISTICA
from tukit_comercio.modelos import EstadoPago, EstadoPedido
from tukit_comercio.repositorios.pedidos import RepoPedidos

DATOS_POR_DESTINO = {
    "despachado": REPARTIDOR,
    "incidencia": {"tipo_incidencia": "no_habia_nadie"},
}
AVISO_POR_DESTINO = {
    "en_preparacion": "pedido_en_preparacion",
    "despachado": "pedido_despachado",
    "en_reparto": "pedido_en_reparto",
    "entregado": "pedido_entregado",
    "incidencia": "incidencia",
}
AVANCES_SIN_CANCELAR = sorted(
    (desde.value, hacia.value)
    for desde, destinos in AVANCES_DE_LOGISTICA.items()
    for hacia in destinos
    if hacia is not EstadoPedido.CANCELADO
)


def test_son_nueve_avances_sin_cancelar():
    assert len(AVANCES_SIN_CANCELAR) == 9


@pytest.mark.parametrize(("desde", "hacia"), AVANCES_SIN_CANCELAR)
async def test_cada_avance_deja_historial_y_su_aviso(cliente, desde, hacia):
    pedido_id = await pedido_pagado(cliente)
    await poner_estado(pedido_id, desde)

    respuesta = await avanzar(
        cliente, pedido_id, {"destino": hacia, "nota": "nota interna", **DATOS_POR_DESTINO.get(hacia, {})}
    )
    assert respuesta.status_code == 200, respuesta.json()
    cuerpo = respuesta.json()
    assert cuerpo["estado"] == hacia

    historial = await filas_de(HISTORIAL, pedido_id)
    assert len(historial) == 1
    assert (historial[0].estado_desde, historial[0].estado_hacia) == (desde, hacia)
    assert historial[0].actor_id == uuid.UUID(OPERADOR)
    assert cuerpo["historial"][0]["estado_hacia"] == hacia

    avisos = await avisos_de(pedido_id)
    if hacia in AVISO_POR_DESTINO:
        assert [a.tipo for a in avisos] == [AVISO_POR_DESTINO[hacia]]
        carga = avisos[0].carga
        assert carga["pedido_id"] == pedido_id
        assert carga["usuario_id"] == USUARIO
        assert CELULAR not in str(carga)
        assert "nota interna" not in str(carga)
        assert "tipo_incidencia" not in carga
    else:
        assert avisos == []


async def test_el_aviso_de_despacho_lleva_el_nombre_del_repartidor(cliente):
    pedido_id = await pedido_pagado(cliente)
    await poner_estado(pedido_id, "en_preparacion")
    await avanzar(cliente, pedido_id, {"destino": "despachado", **REPARTIDOR})
    (aviso,) = await avisos_de(pedido_id)
    assert aviso.carga["repartidor"] == "Luis Gomez"


async def test_el_admin_tambien_avanza_y_queda_como_actor(cliente):
    pedido_id = await pedido_pagado(cliente)
    respuesta = await avanzar(cliente, pedido_id, {"destino": "en_preparacion"}, headers=bearer(TOKEN_ADMIN))
    assert respuesta.status_code == 200
    assert respuesta.json()["historial"][0]["actor_id"] == ADMIN


async def test_el_historial_guarda_el_correo_de_quien_avanzo(cliente):
    pedido_id = await pedido_pagado(cliente)
    respuesta = await avanzar(cliente, pedido_id, {"destino": "en_preparacion"})
    assert respuesta.status_code == 200
    correo = sesiones_por_omision()[TOKEN_OPERADOR]["correo"]
    assert respuesta.json()["historial"][0]["actor_correo"] == correo
    (fila,) = await filas_de(HISTORIAL, pedido_id)
    assert fila.actor_correo == correo


async def test_avanzar_pedido_pagado_a_en_preparacion(cliente):
    pedido_id = await pedido_pagado(cliente)
    respuesta = await cliente.post(
        f"/v1/ordenes/{pedido_id}/avanzar", headers=OPERADOR_HDR, json={"destino": "en_preparacion"}
    )
    assert respuesta.status_code == 200
    assert respuesta.json()["estado"] == EstadoPedido.EN_PREPARACION.value


async def test_avanzar_a_destino_ilegal_da_409(cliente):
    pedido_id = await pedido_pagado(cliente)
    respuesta = await cliente.post(
        f"/v1/ordenes/{pedido_id}/avanzar", headers=OPERADOR_HDR, json={"destino": "entregado"}
    )
    assert respuesta.status_code == 409
    assert respuesta.json()["error"] == "transicion_invalida"


async def test_avanzar_hasta_entregado_marca_entregado_en(cliente):
    pedido_id = await pedido_pagado(cliente)
    for cuerpo in (
        {"destino": "en_preparacion"},
        {"destino": "despachado", **REPARTIDOR},
        {"destino": "en_reparto"},
        {"destino": "entregado"},
    ):
        respuesta = await cliente.post(f"/v1/ordenes/{pedido_id}/avanzar", headers=OPERADOR_HDR, json=cuerpo)
        assert respuesta.status_code == 200, respuesta.json()
    pedido = (await cliente.get(f"/v1/ordenes/{pedido_id}")).json()
    assert pedido["estado"] == EstadoPedido.ENTREGADO.value
    assert pedido["envio"]["entregado_en"] is not None


async def test_avanzar_pedido_inexistente_da_404(cliente):
    respuesta = await cliente.post(
        f"/v1/ordenes/{uuid.uuid4()}/avanzar", headers=OPERADOR_HDR, json={"destino": "en_preparacion"}
    )
    assert respuesta.status_code == 404
    assert respuesta.json()["error"] == "pedido_no_existe"


@pytest.mark.parametrize(
    ("desde", "hacia"),
    [
        ("pendiente_pago", "pagado"),
        ("pendiente_pago", "cancelado"),
        ("pagado", "cancelado"),
        ("incidencia", "despachado"),
    ],
)
async def test_transiciones_fuera_de_la_matriz_dan_409(cliente, desde, hacia):
    pedido_id = await pedido_pagado(cliente)
    await poner_estado(pedido_id, desde)
    respuesta = await avanzar(cliente, pedido_id, {"destino": hacia, **DATOS_POR_DESTINO.get(hacia, {})})
    assert respuesta.status_code == 409
    assert respuesta.json()["error"] == "transicion_invalida"
    assert await filas_de(HISTORIAL, pedido_id) == []


async def test_despachar_sin_repartidor_da_422(cliente):
    pedido_id = await pedido_pagado(cliente)
    await cliente.post(
        f"/v1/ordenes/{pedido_id}/avanzar", headers=OPERADOR_HDR, json={"destino": "en_preparacion"}
    )
    respuesta = await cliente.post(
        f"/v1/ordenes/{pedido_id}/avanzar", headers=OPERADOR_HDR, json={"destino": "despachado"}
    )
    assert respuesta.status_code == 422
    assert respuesta.json()["error"] == "despacho_incompleto"
    assert respuesta.json()["campo"] == "repartidor_nombre"


async def test_despachar_con_repartidor_sella_el_envio(cliente):
    pedido_id = await pedido_pagado(cliente)
    await cliente.post(
        f"/v1/ordenes/{pedido_id}/avanzar", headers=OPERADOR_HDR, json={"destino": "en_preparacion"}
    )
    respuesta = await cliente.post(
        f"/v1/ordenes/{pedido_id}/avanzar",
        headers=OPERADOR_HDR,
        json={"destino": "despachado", **REPARTIDOR},
    )
    assert respuesta.status_code == 200
    assert respuesta.json()["envio"]["repartidor_celular"] == CELULAR
    pedido = (await cliente.get(f"/v1/ordenes/{pedido_id}")).json()
    assert pedido["estado"] == EstadoPedido.DESPACHADO.value
    assert pedido["envio"]["repartidor_nombre"] == REPARTIDOR["repartidor_nombre"]


@pytest.mark.parametrize(
    ("entradas", "campo"),
    [
        ({}, "repartidor_nombre"),
        ({"repartidor_nombre": "Luis"}, "repartidor_celular"),
        ({"repartidor_celular": CELULAR}, "repartidor_nombre"),
    ],
)
async def test_despacho_incompleto_da_422_y_no_escribe_nada(cliente, entradas, campo):
    pedido_id = await pedido_pagado(cliente)
    await poner_estado(pedido_id, "en_preparacion")
    respuesta = await avanzar(cliente, pedido_id, {"destino": "despachado", **entradas})
    assert respuesta.status_code == 422
    assert respuesta.json()["error"] == "despacho_incompleto"
    assert respuesta.json()["campo"] == campo

    detalle = (await cliente.get(f"/v1/comercio/pedidos/{pedido_id}", headers=OPERADOR_HDR)).json()
    assert detalle["estado"] == "en_preparacion"
    assert detalle["envio"]["repartidor_nombre"] is None
    assert await filas_de(HISTORIAL, pedido_id) == []
    assert await avisos_de(pedido_id) == []


@pytest.mark.parametrize(
    ("entradas", "error", "campo"),
    [
        ({}, "incidencia_sin_tipo", "tipo_incidencia"),
        ({"tipo_incidencia": "marciano"}, "tipo_incidencia_invalido", "tipo_incidencia"),
        ({"tipo_incidencia": "otro"}, "incidencia_sin_nota", "nota"),
        ({"tipo_incidencia": "otro", "nota": "   "}, "incidencia_sin_nota", "nota"),
    ],
)
async def test_incidencia_incompleta_da_422(cliente, entradas, error, campo):
    pedido_id = await pedido_pagado(cliente)
    respuesta = await avanzar(cliente, pedido_id, {"destino": "incidencia", **entradas})
    assert respuesta.status_code == 422
    assert (respuesta.json()["error"], respuesta.json()["campo"]) == (error, campo)
    assert await filas_de(HISTORIAL, pedido_id) == []


async def test_incidencia_guarda_tipo_y_nota_en_el_historial(cliente):
    pedido_id = await pedido_pagado(cliente)
    await avanzar(
        cliente, pedido_id, {"destino": "incidencia", "tipo_incidencia": "otro", "nota": "Perro bravo"}
    )
    (fila,) = await filas_de(HISTORIAL, pedido_id)
    assert (fila.tipo_incidencia, fila.nota) == ("otro", "Perro bravo")


async def test_reprogramar_y_cancelar_tras_incidencia(cliente):
    pedido_id = await pedido_pagado(cliente)
    incidencia = {"destino": "incidencia", "tipo_incidencia": "direccion_errada"}
    assert (await avanzar(cliente, pedido_id, incidencia)).json()["estado"] == "incidencia"
    retoma = await avanzar(cliente, pedido_id, {"destino": "en_preparacion"})
    assert retoma.json()["estado"] == EstadoPedido.EN_PREPARACION.value
    assert (await avanzar(cliente, pedido_id, incidencia)).json()["estado"] == "incidencia"

    cancelado = await avanzar(cliente, pedido_id, {"destino": "cancelado", "nota": "No contesta"})
    assert cancelado.status_code == 200
    cuerpo = cancelado.json()
    assert cuerpo["estado"] == EstadoPedido.CANCELADO.value
    assert cuerpo["pago"]["estado"] == EstadoPago.REEMBOLSADO.value
    assert [h["estado_hacia"] for h in cuerpo["historial"]] == [
        "incidencia",
        "en_preparacion",
        "incidencia",
        "cancelado",
    ]
    avisos = await avisos_de(pedido_id)
    assert [a.tipo for a in avisos] == [
        "incidencia",
        "pedido_en_preparacion",
        "incidencia",
        "pedido_cancelado",
    ]
    assert avisos[1].carga["retoma"] is True and "retoma" not in avisos[0].carga
    assert avisos[3].carga["reembolso"] is True


async def test_entrega_estimada_sin_zona_da_400(cliente):
    pedido_id = await pedido_pagado(cliente)
    await poner_estado(pedido_id, "en_preparacion")
    cuerpo = {"destino": "despachado", **REPARTIDOR, "entrega_estimada": "2026-10-05T00:00:00"}
    respuesta = await avanzar(cliente, pedido_id, cuerpo)
    assert respuesta.status_code == 400
    assert respuesta.json()["campo"] == "entrega_estimada"


async def test_entrega_estimada_con_zona_queda_en_el_envio(cliente):
    pedido_id = await pedido_pagado(cliente)
    await poner_estado(pedido_id, "en_preparacion")
    cuerpo = {"destino": "despachado", **REPARTIDOR, "entrega_estimada": "2026-10-05T00:00:00-05:00"}
    respuesta = await avanzar(cliente, pedido_id, cuerpo)
    assert respuesta.status_code == 200
    assert respuesta.json()["envio"]["entrega_estimada"].startswith("2026-10-05")


async def test_el_repositorio_no_mueve_desde_un_estado_desactualizado(cliente):
    pedido_id = await pedido_pagado(cliente)
    async with app.state.motor.sesion() as db:
        repo = RepoPedidos(await db.connection())
        movido = await repo.avanzar_despacho(
            pedido_id=uuid.UUID(pedido_id),
            desde="en_preparacion",
            destino="despachado",
            repartidor_nombre="Luis",
            repartidor_celular=CELULAR,
            entrega_estimada=None,
        )
    assert movido is False
    detalle = (await cliente.get(f"/v1/comercio/pedidos/{pedido_id}", headers=OPERADOR_HDR)).json()
    assert detalle["estado"] == "pagado"
    assert detalle["envio"]["repartidor_nombre"] is None


async def test_una_carrera_da_409_y_no_deja_rastro(cliente, monkeypatch):
    pedido_id = await pedido_pagado(cliente)
    original = RepoPedidos.obtener

    async def obtener_y_que_otro_lo_mueva(self, pid):
        fila = await original(self, pid)
        await self.conexion.execute(update(PEDIDO).where(PEDIDO.c.id == pid).values(estado="incidencia"))
        return fila

    monkeypatch.setattr(RepoPedidos, "obtener", obtener_y_que_otro_lo_mueva)
    respuesta = await avanzar(cliente, pedido_id, {"destino": "en_preparacion"})
    monkeypatch.undo()

    assert respuesta.status_code == 409
    assert respuesta.json()["error"] == "avance_concurrente"
    assert await filas_de(HISTORIAL, pedido_id) == []
    assert await avisos_de(pedido_id) == []
