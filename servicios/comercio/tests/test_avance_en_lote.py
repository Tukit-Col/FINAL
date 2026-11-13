"""Avance en lote: por pedido, con resumen, y solo destinos simples."""

from __future__ import annotations

import uuid

from conftest import TOKEN_ACUDIENTE, bearer
from test_logistica import (  # noqa: F401
    HISTORIAL,
    OPERADOR,
    OPERADOR_HDR,
    _filas,
    _pedido_pagado,
    _poner_estado,
    cliente,
)
from tukit_comercio.repositorios.pedidos import RepoPedidos

URL = "/v1/comercio/pedidos/avanzar-lote"


async def _lote(cliente, ids, destino, headers=OPERADOR_HDR):
    return await cliente.post(URL, headers=headers, json={"pedido_ids": ids, "destino": destino})


async def test_tres_pagados_pasan_a_preparacion_con_historial_del_actor(cliente):
    ids = [await _pedido_pagado(cliente) for _ in range(3)]
    r = await _lote(cliente, ids, "en_preparacion")
    assert r.status_code == 200, r.text
    assert sorted(r.json()["avanzados"]) == sorted(ids)
    assert r.json()["fallidos"] == []
    for i in ids:
        filas = await _filas(HISTORIAL, i)
        assert len(filas) == 1
        assert str(filas[0].actor_id) == OPERADOR


async def test_uno_invalido_falla_y_los_buenos_persisten(cliente):
    a, b, c = [await _pedido_pagado(cliente) for _ in range(3)]
    await _poner_estado(c, "entregado")
    r = await _lote(cliente, [a, b, c], "en_preparacion")
    cuerpo = r.json()
    assert sorted(cuerpo["avanzados"]) == sorted([a, b])
    assert [f["pedido_id"] for f in cuerpo["fallidos"]] == [c]
    assert cuerpo["fallidos"][0]["codigo"] == "transicion_invalida"
    detalle = (await cliente.get(f"/v1/comercio/pedidos/{a}", headers=OPERADOR_HDR)).json()
    assert detalle["estado"] == "en_preparacion"


async def test_pedido_inexistente_va_a_fallidos(cliente):
    a = await _pedido_pagado(cliente)
    fantasma = str(uuid.uuid4())
    r = await _lote(cliente, [a, fantasma], "en_preparacion")
    assert r.json()["avanzados"] == [a]
    assert r.json()["fallidos"][0]["codigo"] == "pedido_no_existe"


async def test_carrera_se_reporta_y_los_demas_siguen(cliente, monkeypatch):
    a, b = [await _pedido_pagado(cliente) for _ in range(2)]
    original = RepoPedidos.avanzar_despacho

    async def con_carrera(self, *, pedido_id, **resto):
        if str(pedido_id) == a:
            return False
        return await original(self, pedido_id=pedido_id, **resto)

    monkeypatch.setattr(RepoPedidos, "avanzar_despacho", con_carrera)
    r = await _lote(cliente, [a, b], "en_preparacion")
    assert r.json()["avanzados"] == [b]
    assert r.json()["fallidos"][0]["pedido_id"] == a
    assert r.json()["fallidos"][0]["codigo"] == "avance_concurrente"
    assert await _filas(HISTORIAL, a) == []


async def test_validaciones_de_forma(cliente):
    ids = [str(uuid.uuid4()) for _ in range(51)]
    r = await _lote(cliente, ids, "en_preparacion")
    assert r.status_code == 422
    r = await _lote(cliente, ids[:2], "despachado")
    assert r.status_code == 422
    assert r.json()["error"] == "destino_no_apto_para_lote"
    for destino in ("incidencia", "cancelado"):
        assert (await _lote(cliente, ids[:1], destino)).status_code == 422
    assert (await _lote(cliente, [ids[0], ids[0]], "en_preparacion")).status_code == 422
    assert (await _lote(cliente, [], "en_preparacion")).status_code == 422


async def test_solo_staff(cliente):
    a = await _pedido_pagado(cliente)
    assert (await _lote(cliente, [a], "en_preparacion", headers={})).status_code == 401
    assert (await _lote(cliente, [a], "en_preparacion", headers=bearer(TOKEN_ACUDIENTE))).status_code == 403
