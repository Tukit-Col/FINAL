"""Vista previa de lo que verá el acudiente al mover un pedido (solo staff, sin escribir)."""

from __future__ import annotations

import json

from conftest import TOKEN_ACUDIENTE, bearer
from test_logistica import (  # noqa: F401
    OPERADOR_HDR,
    REPARTIDOR,
    _avanzar,
    _filas,
    _pedido_pagado,
    cliente,
)
from test_logistica import HISTORIAL

PROHIBIDAS = ("actor_id", "actor_correo", "nota", "repartidor_celular", "hijo", "apodo")


def _claves(valor, acumulado=None):
    acumulado = set() if acumulado is None else acumulado
    if isinstance(valor, dict):
        for k, v in valor.items():
            acumulado.add(k)
            _claves(v, acumulado)
    elif isinstance(valor, list):
        for v in valor:
            _claves(v, acumulado)
    return acumulado


def _url(pedido_id, destino):
    return f"/v1/comercio/pedidos/{pedido_id}/vista-previa?destino={destino}"


async def _en_preparacion(cliente) -> str:
    pedido_id = await _pedido_pagado(cliente)
    assert (await _avanzar(cliente, pedido_id, {"destino": "en_preparacion"})).status_code == 200
    return pedido_id


def _actual(linea):
    return [p["paso"] for p in linea["pasos"] if p["estado"] == "actual"]


async def test_destino_legal_muestra_el_paso_y_el_aviso(cliente):
    pedido_id = await _en_preparacion(cliente)
    antes = await _filas(HISTORIAL, pedido_id)
    r = await cliente.get(_url(pedido_id, "despachado"), headers=OPERADOR_HDR)
    assert r.status_code == 200
    cuerpo = r.json()
    assert cuerpo["legal"] is True
    assert cuerpo["aviso"] == "pedido_despachado"
    assert _actual(cuerpo["ahora"]) == ["en_preparacion"]
    assert _actual(cuerpo["despues"]) == ["despachado"]
    # No escribe nada.
    assert len(await _filas(HISTORIAL, pedido_id)) == len(antes)
    detalle = (await cliente.get(f"/v1/comercio/pedidos/{pedido_id}", headers=OPERADOR_HDR)).json()
    assert detalle["estado"] == "en_preparacion"


async def test_destino_ilegal_o_desconocido_no_es_error(cliente):
    pedido_id = await _en_preparacion(cliente)
    for destino in ("entregado", "no_existe"):
        r = await cliente.get(_url(pedido_id, destino), headers=OPERADOR_HDR)
        assert r.status_code == 200
        assert r.json()["legal"] is False
        assert r.json()["despues"] is None


async def test_nada_privado_sale_en_la_vista(cliente):
    pedido_id = await _en_preparacion(cliente)
    await _avanzar(cliente, pedido_id, {"destino": "despachado", **REPARTIDOR})
    r = await cliente.get(_url(pedido_id, "en_reparto"), headers=OPERADOR_HDR)
    assert r.json()["legal"] is True
    assert not set(PROHIBIDAS) & _claves(r.json())
    assert REPARTIDOR["repartidor_celular"] not in json.dumps(r.json())


async def test_solo_staff_y_404(cliente):
    pedido_id = await _en_preparacion(cliente)
    assert (await cliente.get(_url(pedido_id, "despachado"))).status_code == 401
    assert (await cliente.get(_url(pedido_id, "despachado"), headers=bearer(TOKEN_ACUDIENTE))).status_code == 403
    r = await cliente.get(_url("00000000-0000-4000-8000-000000000000", "despachado"), headers=OPERADOR_HDR)
    assert r.status_code == 404
