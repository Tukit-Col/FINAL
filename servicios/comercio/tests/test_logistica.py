"""Logistica fase 1: el back-office solo para staff, y cada avance con su traza.

Se prueba por HTTP contra la app real (`ASGITransport`), con SQLite en memoria,
la pasarela falsa y un doble de Identidad que mapea token -> sesion. Lo que se
defiende:

- **Acceso.** Tablero, detalle y avance son de operador/admin: 401 sin sesion,
  403 con otro rol, 503 si Identidad no responde (falla cerrada). `mis-pedidos`
  usa el usuario de la SESION e ignora uno que venga en la URL.
- **El celular del repartidor no sale del back-office.** Solo el detalle de
  staff y la respuesta del avance lo traen; ni el tablero, ni `mis-pedidos`, ni
  la ruta interna, ni la carga del evento.
- **Cada avance deja su historial y su aviso, o nada.** Un rechazo (422/409) o
  una carrera no dejan estado, historial ni evento a medias.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from typing import Any

import httpx
import pytest
import pytest_asyncio
from conftest import (
    ADMIN,
    OPERADOR,
    TOKEN_ACUDIENTE,
    TOKEN_ADMIN,
    TOKEN_OPERADOR,
    TOKEN_OTRO,
    IdentidadFalsa,
    bearer,
)
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from test_checkout import CatalogoFalso, _orden
from tukit_comercio.api import app
from tukit_comercio.dominio.despacho import AVANCES_DE_LOGISTICA
from tukit_comercio.modelos import Base, EstadoPago, EstadoPedido
from tukit_comercio.pasarela import PasarelaFalsa
from tukit_comercio.repositorios.pedidos import RepoPedidos
from tukit_comun.bd import MotorServicio

PEDIDO = Base.metadata.tables["pedido"]
HISTORIAL = Base.metadata.tables["historial_pedido"]
BANDEJA = Base.metadata.tables["bandeja_salida"]

OPERADOR_HDR = bearer(TOKEN_OPERADOR)
CELULAR = "3109998877"
REPARTIDOR = {"repartidor_nombre": "Luis Gomez", "repartidor_celular": CELULAR}


@pytest_asyncio.fixture
async def cliente() -> AsyncIterator[httpx.AsyncClient]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conexion:
        await conexion.run_sync(Base.metadata.create_all)
    fabrica = async_sessionmaker(engine, expire_on_commit=False)
    app.state.motor = MotorServicio(servicio="prueba", engine=engine, _fabrica=fabrica)
    app.state.pasarela = PasarelaFalsa()
    app.state.catalogo = CatalogoFalso({"TK-C001-ECO": 4500})
    app.state.identidad = IdentidadFalsa()
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://prueba") as http:
        yield http
    await engine.dispose()


async def _pedido_pagado(cliente: httpx.AsyncClient) -> str:
    """Un pedido del acudiente, pagado por el webhook falso (como en la vida)."""
    orden = (await cliente.post("/v1/ordenes", json=_orden())).json()
    pedido_id = orden["pedido_id"]
    pago = (
        await cliente.post(
            f"/v1/ordenes/{pedido_id}/pago",
            json={"correo_cliente": "ana@ejemplo.com", "metodo": "pse"},
        )
    ).json()
    evento = app.state.pasarela.emitir_evento(
        referencia=pago["referencia_wompi"],
        transaccion_id=pago["transaccion_wompi"],
        estado_wompi="APPROVED",
        # El webhook rechaza un monto que no sea el del pago.
        monto_centavos=int(orden["total"]) * 100,
    )
    await cliente.post("/v1/webhooks/wompi", json=evento)
    return pedido_id


async def _poner_estado(pedido_id: str, estado: str) -> None:
    """Atajo de prueba: deja el pedido en `estado` sin pasar por `/avanzar`."""
    async with app.state.motor.sesion() as db:
        conexion = await db.connection()
        await conexion.execute(
            update(PEDIDO).where(PEDIDO.c.id == uuid.UUID(pedido_id)).values(estado=estado)
        )


async def _filas(tabla, pedido_id: str) -> list[Any]:
    async with app.state.motor.sesion() as db:
        conexion = await db.connection()
        columna = tabla.c.pedido_id if "pedido_id" in tabla.c else tabla.c.agregado_id
        return list(await conexion.execute(select(tabla).where(columna == uuid.UUID(pedido_id))))


async def _avisos(pedido_id: str) -> list[Any]:
    # `pedido_pagado` lo escribe el webhook; aqui interesan los de logistica.
    return [f for f in await _filas(BANDEJA, pedido_id) if f.tipo != "pedido_pagado"]


async def _avanzar(cliente, pedido_id: str, cuerpo: dict[str, Any], headers=OPERADOR_HDR) -> httpx.Response:
    return await cliente.post(f"/v1/ordenes/{pedido_id}/avanzar", headers=headers, json=cuerpo)


# ---------------------------------------------------------------------------
# Acceso
# ---------------------------------------------------------------------------

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
    pedido_id = await _pedido_pagado(cliente)
    respuesta = await cliente.get(f"/v1/comercio/pedidos/{pedido_id}", headers=headers)
    assert respuesta.status_code == esperado


@pytest.mark.parametrize(("headers", "esperado"), CASOS_DE_ACCESO)
async def test_avanzar_solo_para_staff(cliente, headers, esperado):
    pedido_id = await _pedido_pagado(cliente)
    respuesta = await _avanzar(cliente, pedido_id, {"destino": "en_preparacion"}, headers=headers)
    assert respuesta.status_code == esperado
    if esperado != 200:
        # Un rechazo de acceso no mueve nada.
        assert await _filas(HISTORIAL, pedido_id) == []


@pytest.mark.parametrize(
    "ruta", ["/v1/comercio/pedidos", "/v1/comercio/mis-pedidos", f"/v1/comercio/pedidos/{uuid.uuid4()}"]
)
async def test_identidad_caida_falla_cerrada_con_503(cliente, ruta):
    app.state.identidad = IdentidadFalsa(caida=True)
    respuesta = await cliente.get(ruta, headers=OPERADOR_HDR)
    assert respuesta.status_code == 503
    assert respuesta.json()["error"] == "identidad_no_disponible"


async def test_avanzar_con_identidad_caida_da_503_y_no_mueve(cliente):
    pedido_id = await _pedido_pagado(cliente)
    app.state.identidad = IdentidadFalsa(caida=True)
    respuesta = await _avanzar(cliente, pedido_id, {"destino": "en_preparacion"})
    assert respuesta.status_code == 503
    app.state.identidad = IdentidadFalsa()
    detalle = (await cliente.get(f"/v1/comercio/pedidos/{pedido_id}", headers=OPERADOR_HDR)).json()
    assert detalle["estado"] == EstadoPedido.PAGADO.value


async def test_mis_pedidos_exige_sesion(cliente):
    respuesta = await cliente.get("/v1/comercio/mis-pedidos")
    assert respuesta.status_code == 401
    assert (await cliente.get("/v1/comercio/mis-pedidos", headers=bearer(TOKEN_ACUDIENTE))).status_code == 200


async def test_mis_pedidos_ignora_el_usuario_de_la_url(cliente):
    # El pedido es del acudiente; "otro" pide los suyos con el id del acudiente
    # en la URL y recibe solo los propios (ninguno).
    await _pedido_pagado(cliente)
    acudiente = _orden()["usuario_id"]
    respuesta = await cliente.get(
        f"/v1/comercio/mis-pedidos?usuario_id={acudiente}", headers=bearer(TOKEN_OTRO)
    )
    assert respuesta.status_code == 200
    assert respuesta.json()["total"] == 0


async def test_el_celular_no_sale_del_detalle_de_staff(cliente):
    pedido_id = await _pedido_pagado(cliente)
    await _avanzar(cliente, pedido_id, {"destino": "en_preparacion"})
    despacho = await _avanzar(cliente, pedido_id, {"destino": "despachado", **REPARTIDOR})
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


async def test_la_ruta_interna_sigue_sin_token_y_sin_historial(cliente):
    pedido_id = await _pedido_pagado(cliente)
    respuesta = await cliente.get(f"/v1/ordenes/{pedido_id}")
    assert respuesta.status_code == 200
    assert "historial" not in respuesta.json()


# ---------------------------------------------------------------------------
# Avances: historial y aviso
# ---------------------------------------------------------------------------

DATOS_POR_DESTINO = {
    "despachado": REPARTIDOR,
    "incidencia": {"tipo_incidencia": "no_habia_nadie"},
}
AVISO_POR_DESTINO = {
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
    pedido_id = await _pedido_pagado(cliente)
    await _poner_estado(pedido_id, desde)

    respuesta = await _avanzar(
        cliente, pedido_id, {"destino": hacia, "nota": "nota interna", **DATOS_POR_DESTINO.get(hacia, {})}
    )
    assert respuesta.status_code == 200, respuesta.json()
    cuerpo = respuesta.json()
    assert cuerpo["estado"] == hacia

    historial = await _filas(HISTORIAL, pedido_id)
    assert len(historial) == 1
    assert (historial[0].estado_desde, historial[0].estado_hacia) == (desde, hacia)
    assert historial[0].actor_id == uuid.UUID(OPERADOR)
    assert cuerpo["historial"][0]["estado_hacia"] == hacia

    avisos = await _avisos(pedido_id)
    if hacia in AVISO_POR_DESTINO:
        assert [a.tipo for a in avisos] == [AVISO_POR_DESTINO[hacia]]
        carga = avisos[0].carga
        assert carga["pedido_id"] == pedido_id
        assert carga["usuario_id"] == _orden()["usuario_id"]
        # La carga viaja por el broker entera: ni celular, ni nota, ni tipo.
        assert CELULAR not in str(carga)
        assert "nota interna" not in str(carga)
        assert "tipo_incidencia" not in carga
    else:
        assert avisos == []


async def test_el_aviso_de_despacho_lleva_el_nombre_del_repartidor(cliente):
    pedido_id = await _pedido_pagado(cliente)
    await _poner_estado(pedido_id, "en_preparacion")
    await _avanzar(cliente, pedido_id, {"destino": "despachado", **REPARTIDOR})
    (aviso,) = await _avisos(pedido_id)
    assert aviso.carga["repartidor"] == "Luis Gomez"


async def test_el_admin_tambien_avanza_y_queda_como_actor(cliente):
    pedido_id = await _pedido_pagado(cliente)
    respuesta = await _avanzar(cliente, pedido_id, {"destino": "en_preparacion"}, headers=bearer(TOKEN_ADMIN))
    assert respuesta.status_code == 200
    assert respuesta.json()["historial"][0]["actor_id"] == ADMIN


async def test_el_historial_guarda_el_correo_de_quien_avanzo(cliente):
    """El back-office no puede pedirle a Identidad el nombre de otro miembro del
    equipo: el historial guarda una copia del correo de la sesion del actor."""
    pedido_id = await _pedido_pagado(cliente)
    respuesta = await _avanzar(cliente, pedido_id, {"destino": "en_preparacion"})
    assert respuesta.status_code == 200
    correo = f"operador-{OPERADOR[:8]}@tukit.test"
    assert respuesta.json()["historial"][0]["actor_correo"] == correo
    (fila,) = await _filas(HISTORIAL, pedido_id)
    assert fila.actor_correo == correo


@pytest.mark.parametrize(
    ("entradas", "campo"),
    [
        ({}, "repartidor_nombre"),
        ({"repartidor_nombre": "Luis"}, "repartidor_celular"),
        ({"repartidor_celular": CELULAR}, "repartidor_nombre"),
    ],
)
async def test_despacho_incompleto_da_422_y_no_escribe_nada(cliente, entradas, campo):
    pedido_id = await _pedido_pagado(cliente)
    await _poner_estado(pedido_id, "en_preparacion")
    respuesta = await _avanzar(cliente, pedido_id, {"destino": "despachado", **entradas})
    assert respuesta.status_code == 422
    assert respuesta.json()["error"] == "despacho_incompleto"
    assert respuesta.json()["campo"] == campo

    detalle = (await cliente.get(f"/v1/comercio/pedidos/{pedido_id}", headers=OPERADOR_HDR)).json()
    assert detalle["estado"] == "en_preparacion"
    assert detalle["envio"]["repartidor_nombre"] is None
    assert await _filas(HISTORIAL, pedido_id) == []
    assert await _avisos(pedido_id) == []


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
    pedido_id = await _pedido_pagado(cliente)
    respuesta = await _avanzar(cliente, pedido_id, {"destino": "incidencia", **entradas})
    assert respuesta.status_code == 422
    assert (respuesta.json()["error"], respuesta.json()["campo"]) == (error, campo)
    assert await _filas(HISTORIAL, pedido_id) == []


async def test_incidencia_guarda_tipo_y_nota_en_el_historial(cliente):
    pedido_id = await _pedido_pagado(cliente)
    await _avanzar(
        cliente, pedido_id, {"destino": "incidencia", "tipo_incidencia": "otro", "nota": "Perro bravo"}
    )
    (fila,) = await _filas(HISTORIAL, pedido_id)
    assert (fila.tipo_incidencia, fila.nota) == ("otro", "Perro bravo")


async def test_reprogramar_y_cancelar_tras_incidencia(cliente):
    pedido_id = await _pedido_pagado(cliente)
    incidencia = {"destino": "incidencia", "tipo_incidencia": "direccion_errada"}
    assert (await _avanzar(cliente, pedido_id, incidencia)).status_code == 200
    # Reprogramar: vuelve a preparacion, sin aviso.
    assert (await _avanzar(cliente, pedido_id, {"destino": "en_preparacion"})).status_code == 200
    assert (await _avanzar(cliente, pedido_id, incidencia)).status_code == 200

    cancelado = await _avanzar(cliente, pedido_id, {"destino": "cancelado", "nota": "No contesta"})
    assert cancelado.status_code == 200
    cuerpo = cancelado.json()
    assert cuerpo["estado"] == EstadoPedido.CANCELADO.value
    # Como el retracto: el pago aprobado queda marcado para reembolso.
    assert cuerpo["pago"]["estado"] == EstadoPago.REEMBOLSADO.value
    assert [h["estado_hacia"] for h in cuerpo["historial"]] == [
        "incidencia",
        "en_preparacion",
        "incidencia",
        "cancelado",
    ]
    # Solo las dos incidencias avisaron; reprogramar y cancelar no.
    assert [a.tipo for a in await _avisos(pedido_id)] == ["incidencia", "incidencia"]


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
    pedido_id = await _pedido_pagado(cliente)
    await _poner_estado(pedido_id, desde)
    respuesta = await _avanzar(cliente, pedido_id, {"destino": hacia, **DATOS_POR_DESTINO.get(hacia, {})})
    assert respuesta.status_code == 409
    assert respuesta.json()["error"] == "transicion_invalida"
    assert await _filas(HISTORIAL, pedido_id) == []


async def test_el_repositorio_no_mueve_desde_un_estado_desactualizado(cliente):
    pedido_id = await _pedido_pagado(cliente)
    async with app.state.motor.sesion() as db:
        repo = RepoPedidos(await db.connection())
        movido = await repo.avanzar_despacho(
            pedido_id=uuid.UUID(pedido_id),
            desde="en_preparacion",  # el pedido sigue en `pagado`
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
    pedido_id = await _pedido_pagado(cliente)
    original = RepoPedidos.obtener

    async def obtener_y_que_otro_lo_mueva(self, pid):
        # El router lee el pedido en `pagado`; justo despues "otro operador" lo
        # mueve. El UPDATE guardado ya no encuentra la fila en `pagado`.
        fila = await original(self, pid)
        await self.conexion.execute(update(PEDIDO).where(PEDIDO.c.id == pid).values(estado="incidencia"))
        return fila

    monkeypatch.setattr(RepoPedidos, "obtener", obtener_y_que_otro_lo_mueva)
    respuesta = await _avanzar(cliente, pedido_id, {"destino": "en_preparacion"})
    monkeypatch.undo()

    assert respuesta.status_code == 409
    assert respuesta.json()["error"] == "avance_concurrente"
    assert await _filas(HISTORIAL, pedido_id) == []
    assert await _avisos(pedido_id) == []


async def test_entrega_estimada_sin_zona_da_400(cliente):
    pedido_id = await _pedido_pagado(cliente)
    await _poner_estado(pedido_id, "en_preparacion")
    cuerpo = {"destino": "despachado", **REPARTIDOR, "entrega_estimada": "2026-10-05T00:00:00"}
    respuesta = await _avanzar(cliente, pedido_id, cuerpo)
    assert respuesta.status_code == 400
    assert respuesta.json()["campo"] == "entrega_estimada"


async def test_entrega_estimada_con_zona_queda_en_el_envio(cliente):
    pedido_id = await _pedido_pagado(cliente)
    await _poner_estado(pedido_id, "en_preparacion")
    cuerpo = {"destino": "despachado", **REPARTIDOR, "entrega_estimada": "2026-10-05T00:00:00-05:00"}
    respuesta = await _avanzar(cliente, pedido_id, cuerpo)
    assert respuesta.status_code == 200
    assert respuesta.json()["envio"]["entrega_estimada"].startswith("2026-10-05")


# ---------------------------------------------------------------------------
# La linea de tiempo del acudiente (`/pedidos/[id]`)
# ---------------------------------------------------------------------------


async def test_el_acudiente_ve_la_linea_de_tiempo_de_su_pedido_sin_datos_del_staff(cliente):
    pedido_id = await _pedido_pagado(cliente)
    await _avanzar(cliente, pedido_id, {"destino": "en_preparacion"})
    await _avanzar(cliente, pedido_id, {"destino": "despachado", **REPARTIDOR})
    await _avanzar(
        cliente, pedido_id, {"destino": "incidencia", "tipo_incidencia": "otro", "nota": "Perro bravo"}
    )

    respuesta = await cliente.get(f"/v1/comercio/mis-pedidos/{pedido_id}", headers=bearer(TOKEN_ACUDIENTE))
    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    # Lo de siempre sigue ahi: la linea se agrega, no reemplaza.
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
    pedido_id = await _pedido_pagado(cliente)
    ajeno = await cliente.get(f"/v1/comercio/mis-pedidos/{pedido_id}", headers=bearer(TOKEN_OTRO))
    assert ajeno.status_code == 404
    assert "linea_de_tiempo" not in ajeno.text
    inexistente = await cliente.get(
        f"/v1/comercio/mis-pedidos/{uuid.uuid4()}", headers=bearer(TOKEN_ACUDIENTE)
    )
    assert inexistente.status_code == 404


async def test_la_linea_de_tiempo_exige_sesion(cliente):
    pedido_id = await _pedido_pagado(cliente)
    assert (await cliente.get(f"/v1/comercio/mis-pedidos/{pedido_id}")).status_code == 401


async def test_un_pedido_pendiente_trae_su_vencimiento(cliente):
    orden = (await cliente.post("/v1/ordenes", json=_orden())).json()
    respuesta = await cliente.get(
        f"/v1/comercio/mis-pedidos/{orden['pedido_id']}", headers=bearer(TOKEN_ACUDIENTE)
    )
    linea = respuesta.json()["linea_de_tiempo"]
    assert linea["pasos"][0]["estado"] == "actual"
    assert linea["pago_pendiente"]["vencido"] is False
    assert linea["pago_pendiente"]["vence_en"]
