"""Logistica: el back-office es solo del staff y el celular no sale de el.

Se prueba por HTTP contra la app real (`ASGITransport`), con SQLite en memoria,
la pasarela falsa y un doble de Identidad que mapea token -> sesion. Tablero,
detalle y avance son de operador/admin: 401 sin sesion, 403 con otro rol, 503 si
Identidad no responde (falla cerrada). El celular del repartidor solo lo traen
el detalle de staff y la respuesta del avance.
"""

from __future__ import annotations

import uuid

import pytest
from _ayudas_comercio import (
    CELULAR,
    HISTORIAL,
    OPERADOR_HDR,
    REPARTIDOR,
    avanzar,
    filas_de,
    pedido_pagado,
)
from conftest import (
    TOKEN_ACUDIENTE,
    TOKEN_ADMIN,
    TOKEN_OPERADOR,
    IdentidadFalsa,
    bearer,
)
from tukit_comercio.api import app
from tukit_comercio.modelos import EstadoPedido

CASOS_DE_ACCESO = [
    ({}, 401),
    (bearer("token-que-no-existe"), 401),
    (bearer(TOKEN_ACUDIENTE), 403),
    (bearer(TOKEN_OPERADOR), 200),
    (bearer(TOKEN_ADMIN), 200),
]


@pytest.mark.parametrize(("headers", "esperado"), CASOS_DE_ACCESO)
async def test_tablero_solo_para_staff(cliente, headers, esperado):
    respuesta = await cliente.get("/v1/comercio/pedidos", headers=headers)
    assert respuesta.status_code == esperado
    if esperado == 401:
        assert respuesta.json()["error"] == "sesion_invalida"
    if esperado == 403:
        assert respuesta.json()["error"] == "acceso_denegado"


@pytest.mark.parametrize(("headers", "esperado"), CASOS_DE_ACCESO)
async def test_detalle_solo_para_staff(cliente, headers, esperado):
    pedido_id = await pedido_pagado(cliente)
    respuesta = await cliente.get(f"/v1/comercio/pedidos/{pedido_id}", headers=headers)
    assert respuesta.status_code == esperado


@pytest.mark.parametrize(("headers", "esperado"), CASOS_DE_ACCESO)
async def test_avanzar_solo_para_staff(cliente, headers, esperado):
    pedido_id = await pedido_pagado(cliente)
    respuesta = await avanzar(cliente, pedido_id, {"destino": "en_preparacion"}, headers=headers)
    assert respuesta.status_code == esperado
    if esperado != 200:
        # Un rechazo de acceso no mueve nada.
        assert await filas_de(HISTORIAL, pedido_id) == []


# Las demas rutas de back-office sobre un pedido. El cuerpo es valido para que un
# rechazo no pueda venir de la validacion: 401/403 tienen que salir del acceso.
RUTAS_DE_STAFF = [
    ("GET", "/v1/comercio/pedidos/{id}/vista-previa?destino=en_preparacion", None),
    ("POST", "/v1/comercio/pedidos/{id}/reconciliar-pago", None),
    ("POST", "/v1/comercio/pedidos/avanzar-lote", {"destino": "en_preparacion"}),
]


@pytest.mark.parametrize(("metodo", "ruta", "cuerpo"), RUTAS_DE_STAFF)
@pytest.mark.parametrize(("headers", "esperado"), [c for c in CASOS_DE_ACCESO if c[1] != 200])
async def test_las_rutas_de_back_office_rechazan_sin_sesion_o_sin_rol(
    cliente, metodo, ruta, cuerpo, headers, esperado
):
    pedido_id = await pedido_pagado(cliente)
    json = {**cuerpo, "pedido_ids": [pedido_id]} if cuerpo is not None else None
    respuesta = await cliente.request(metodo, ruta.format(id=pedido_id), headers=headers, json=json)
    assert respuesta.status_code == esperado
    assert respuesta.json()["error"] == ("sesion_invalida" if esperado == 401 else "acceso_denegado")
    # Un rechazo de acceso no mueve nada.
    assert await filas_de(HISTORIAL, pedido_id) == []


@pytest.mark.parametrize(
    "ruta", ["/v1/comercio/pedidos", "/v1/comercio/mis-pedidos", f"/v1/comercio/pedidos/{uuid.uuid4()}"]
)
async def test_identidad_caida_falla_cerrada_con_503(cliente, ruta):
    app.state.identidad = IdentidadFalsa(caida=True)
    respuesta = await cliente.get(ruta, headers=OPERADOR_HDR)
    assert respuesta.status_code == 503
    assert respuesta.json()["error"] == "identidad_no_disponible"


async def test_avanzar_con_identidad_caida_da_503_y_no_mueve(cliente):
    pedido_id = await pedido_pagado(cliente)
    app.state.identidad = IdentidadFalsa(caida=True)
    respuesta = await avanzar(cliente, pedido_id, {"destino": "en_preparacion"})
    assert respuesta.status_code == 503
    app.state.identidad = IdentidadFalsa()
    detalle = (await cliente.get(f"/v1/comercio/pedidos/{pedido_id}", headers=OPERADOR_HDR)).json()
    assert detalle["estado"] == EstadoPedido.PAGADO.value


async def test_el_celular_no_sale_del_detalle_de_staff(cliente):
    pedido_id = await pedido_pagado(cliente)
    await avanzar(cliente, pedido_id, {"destino": "en_preparacion"})
    despacho = await avanzar(cliente, pedido_id, {"destino": "despachado", **REPARTIDOR})
    assert despacho.json()["envio"]["repartidor_celular"] == CELULAR

    detalle = (await cliente.get(f"/v1/comercio/pedidos/{pedido_id}", headers=OPERADOR_HDR)).json()
    assert detalle["envio"]["repartidor_celular"] == CELULAR

    tablero = (await cliente.get("/v1/comercio/pedidos", headers=OPERADOR_HDR)).text
    mios = (await cliente.get("/v1/comercio/mis-pedidos", headers=bearer(TOKEN_ACUDIENTE))).text
    interna = (await cliente.get(f"/v1/ordenes/{pedido_id}")).text
    for cuerpo in (tablero, mios, interna):
        assert CELULAR not in cuerpo
        # El nombre si se muestra: el papa sabe quien le lleva el pedido.
        assert "Luis Gomez" in cuerpo


async def test_la_ruta_interna_no_pide_token_ni_trae_historial(cliente):
    pedido_id = await pedido_pagado(cliente)
    respuesta = await cliente.get(f"/v1/ordenes/{pedido_id}")
    assert respuesta.status_code == 200
    assert "historial" not in respuesta.json()
