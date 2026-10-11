"""El cierre de la orden y el retracto, de comercio contra el catalogo real.

NFR-PRE-06: antes de congelar, comercio relee el precio de cada linea en el
catalogo. Un precio distinto del vigente (uno mas, uno menos) no se cobra; un
catalogo caido es 503 y no un cobro a ciegas. Para cortar el catalogo se levanta
una copia de comercio con `TUKIT_CATALOGO_URL` hacia un puerto cerrado: el stack
compartido no se toca. El precio vigente tampoco se cambia en el catalogo; se
manda el viejo desde la orden, que es lo que veria un acudiente con la pagina
abierta desde antes del cambio.

NFR-SEG-09 (decision 9 de `acuerdos.md`): el retracto de la Ley 1480 dentro y
fuera de los cinco dias habiles y sobre un pedido ajeno. Para salir del plazo se
corre hacia atras `envio.entregado_en` del pedido que la propia prueba creo y
entrego, en la base desechable del stack de integracion.

Desde 173ee80 (CONTRATO_API §9) crear, pagar y retractar una orden son llamadas
internas: la ventana y la reserva se miden directo contra comercio, y lo que
alcanza un cliente cualquiera (el titular, otro acudiente, un anonimo) se mide
por la puerta.
"""

from __future__ import annotations

from pathlib import Path

import httpx
import pytest
from sqlalchemy import text
from stack_vivo import (
    COMERCIO,
    conexion_a,
    crear_orden,
    instancia,
    orden_pagada,
    portador,
    puerto_libre,
)

pytestmark = pytest.mark.integracion

# --------------------------------------------------------------- NFR-PRE-06


@pytest.mark.nfr("NFR-PRE-06")
def test_con_el_precio_vigente_la_orden_se_cierra(cliente: httpx.Client, sesiones: dict, producto: dict):
    respuesta = crear_orden(cliente, sesiones["acudiente"]["usuario_id"], producto)

    assert respuesta.status_code == 201, respuesta.text
    assert respuesta.json()["estado"] == "pendiente_pago"
    assert respuesta.json()["total"] == producto["precio_desde"]


@pytest.mark.nfr("NFR-PRE-06")
@pytest.mark.parametrize("diferencia", [-1, 1], ids=["un-peso-menos", "un-peso-mas"])
def test_un_precio_que_no_es_el_vigente_no_se_cobra(
    cliente: httpx.Client, sesiones: dict, producto: dict, diferencia: int
):
    respuesta = crear_orden(
        cliente,
        sesiones["acudiente"]["usuario_id"],
        producto,
        linea={"precio_unitario": producto["precio_desde"] + diferencia},
    )

    assert respuesta.status_code == 422
    assert respuesta.json()["error"] == "precio_cambiado"


@pytest.mark.nfr("NFR-PRE-06")
def test_un_sku_que_el_catalogo_no_conoce_no_se_cobra(cliente: httpx.Client, sesiones: dict, producto: dict):
    respuesta = crear_orden(
        cliente, sesiones["acudiente"]["usuario_id"], producto, linea={"sku": "QA-SKU-QUE-NO-EXISTE"}
    )

    assert respuesta.status_code == 422
    assert respuesta.json()["error"] == "precio_cambiado"


@pytest.mark.nfr("NFR-PRE-06")
def test_con_el_catalogo_caido_la_orden_no_se_cierra(
    tmp_path: Path, sesiones: dict, producto: dict, consultar, correlacion_id: str
):
    with (
        instancia(
            "tukit_comercio.api",
            tmp_path / "comercio.log",
            TUKIT_CATALOGO_URL=f"http://127.0.0.1:{puerto_libre()}",
        ) as base,
        httpx.Client(base_url=base, timeout=60, headers={"x-correlation-id": correlacion_id}) as http,
    ):
        respuesta = crear_orden(http, sesiones["acudiente"]["usuario_id"], producto, comercio=base)

    assert respuesta.status_code == 503
    assert respuesta.json()["error"] == "catalogo_no_disponible"


@pytest.mark.nfr("NFR-PRE-06")
@pytest.mark.xfail(
    strict=True,
    reason=(
        "H-A-35: comercio no mira existencias al cerrar la orden; "
        "con el inventario vacio acepta 100000 unidades"
    ),
)
def test_una_cantidad_sin_existencias_no_se_cobra(cliente: httpx.Client, sesiones: dict, producto: dict):
    respuesta = crear_orden(
        cliente, sesiones["acudiente"]["usuario_id"], producto, linea={"cantidad": 100000}
    )

    assert respuesta.status_code in (409, 422), f"{respuesta.status_code}: {respuesta.text[:200]}"


# --------------------------------------------------------------- NFR-SEG-09


async def _fila(consultar, sql: str, **parametros) -> tuple:
    filas = await consultar("comercio", sql, **parametros)
    assert filas, f"sin filas para {parametros}"
    return tuple(filas[0])


def _retractar(http: httpx.Client, pedido_id: str) -> httpx.Response:
    """La llamada interna del retracto, directo a comercio (no pide sesion), con la cabecera de la prueba."""
    return http.post(f"{COMERCIO}/v1/ordenes/{pedido_id}/retracto", json={"motivo": "Prueba ficticia de QA"})


def _entregar(http: httpx.Client, sesiones: dict, pedido_id: str) -> None:
    """Lleva el pedido hasta `entregado` por la puerta, con la sesion del operador.

    El avance pide rol de staff y el despacho, nombre y celular del repartidor
    (`dominio/despacho.py:validar_avance`); los dos son ficticios.
    """
    for destino, extra in [
        ("en_preparacion", {}),
        ("despachado", {"repartidor_nombre": "Repartidor Ficticio QA", "repartidor_celular": "3000000000"}),
        ("en_reparto", {}),
        ("entregado", {}),
    ]:
        respuesta = http.post(
            f"/v1/ordenes/{pedido_id}/avanzar",
            json={"destino": destino, **extra},
            headers=portador(sesiones, "operador"),
        )
        assert respuesta.status_code == 200, respuesta.text


@pytest.mark.nfr("NFR-SEG-09")
async def test_el_retracto_antes_del_despacho_cancela_y_reembolsa(
    cliente: httpx.Client, sesiones: dict, producto: dict, consultar
):
    pedido = orden_pagada(cliente, sesiones["acudiente"]["usuario_id"], producto)
    respuesta = _retractar(cliente, pedido)

    assert respuesta.status_code == 201, respuesta.text
    assert respuesta.json()["cancelado"] is True
    assert (await _fila(consultar, "select estado from pedido where id = :p", p=pedido)) == ("cancelado",)
    assert (await _fila(consultar, "select estado from pago where pedido_id = :p", p=pedido)) == (
        "reembolsado",
    )
    monto = await _fila(consultar, "select monto from devolucion where pedido_id = :p", p=pedido)
    assert monto == (producto["precio_desde"],)


@pytest.mark.nfr("NFR-SEG-09")
async def test_el_retracto_dentro_del_plazo_tras_la_entrega_registra_la_devolucion(
    cliente: httpx.Client, sesiones: dict, producto: dict, consultar
):
    pedido = orden_pagada(cliente, sesiones["acudiente"]["usuario_id"], producto)
    _entregar(cliente, sesiones, pedido)
    respuesta = _retractar(cliente, pedido)

    assert respuesta.status_code == 201, respuesta.text
    assert respuesta.json()["estado"] == "entregado"
    assert await consultar("comercio", "select id from devolucion where pedido_id = :p", p=pedido)


@pytest.mark.nfr("NFR-SEG-09")
@pytest.mark.xfail(
    strict=True, reason="H-A-14: el retracto no mira la fecha de entrega; a los 30 dias se acepta"
)
async def test_el_retracto_fuera_de_los_cinco_dias_habiles_se_rechaza(
    cliente: httpx.Client, sesiones: dict, producto: dict, record_property
):
    pedido = orden_pagada(cliente, sesiones["acudiente"]["usuario_id"], producto)
    _entregar(cliente, sesiones, pedido)
    async with conexion_a("comercio") as conexion:
        await conexion.execute(
            text("update envio set entregado_en = now() - interval '30 days' where pedido_id = :p"),
            {"p": pedido},
        )
        await conexion.commit()
    respuesta = _retractar(cliente, pedido)

    record_property("estado_retracto_30_dias", respuesta.status_code)
    assert 400 <= respuesta.status_code < 500, f"{respuesta.status_code}: {respuesta.text[:200]}"


@pytest.mark.nfr("NFR-SEG-09")
@pytest.mark.xfail(strict=True, reason="H-A-15: cancelar por retracto deja la reserva de inventario activa")
async def test_el_retracto_libera_la_reserva(
    cliente: httpx.Client, sesiones: dict, producto: dict, consultar
):
    pedido = orden_pagada(cliente, sesiones["acudiente"]["usuario_id"], producto)
    retracto = _retractar(cliente, pedido)
    assert retracto.status_code == 201, retracto.text
    assert retracto.json()["cancelado"] is True

    estados = {
        fila[0]
        for fila in await consultar(
            "comercio", "select estado from reserva_inventario where pedido_id = :p", p=pedido
        )
    }
    assert estados, "el pedido no tiene reserva"
    assert "activa" not in estados


@pytest.mark.nfr("NFR-SEG-09")
@pytest.mark.parametrize("quien", ["otro_acudiente", "anonimo"])
async def test_nadie_mas_retracta_el_pedido_de_un_acudiente(
    cliente: httpx.Client, sesiones: dict, producto: dict, consultar, quien: str
):
    """Control de no regresion de H-C-06 (retracto ajeno): la puerta ya no deja pasar el retracto.

    Desde 173ee80 `bloqueada` (`servicios/gateway/tukit_gateway/api.py`) solo
    expone `/v1/ordenes/{id}/avanzar` bajo `/v1/ordenes`: otro acudiente o un
    anonimo reciben 404 y el pedido sigue pagado.
    """
    pedido = orden_pagada(cliente, sesiones["acudiente"]["usuario_id"], producto)
    cabeceras = portador(sesiones, "acudiente_2") if quien == "otro_acudiente" else {}
    respuesta = cliente.post(
        f"/v1/ordenes/{pedido}/retracto", json={"motivo": "Prueba ficticia de QA"}, headers=cabeceras
    )

    assert respuesta.status_code in (401, 403, 404), f"{respuesta.status_code}: {respuesta.text[:200]}"
    assert (await _fila(consultar, "select estado from pedido where id = :p", p=pedido)) == ("pagado",)


@pytest.mark.nfr("NFR-SEG-09")
@pytest.mark.xfail(
    strict=True,
    reason=(
        "H-A-61: el titular no tiene por donde retractar; la puerta responde 404 "
        "a /v1/ordenes/{id}/retracto y /v1/comercio/mis-pedidos/{id} no tiene retracto"
    ),
)
def test_el_titular_retracta_su_pedido_por_la_puerta(
    cliente: httpx.Client, sesiones: dict, producto: dict, record_property
):
    """La otra mitad de «solo el titular»: el titular, con su sesion, si puede retractar.

    Se prueban las dos entradas que tendria desde el navegador: la del contrato
    (`/v1/ordenes/{id}/retracto`) y la de sus pedidos (`/v1/comercio/mis-pedidos/{id}`,
    por donde paga y cancela segun CONTRATO_API §9).
    """
    pedido = orden_pagada(cliente, sesiones["acudiente"]["usuario_id"], producto)
    codigos = {}
    for ruta in (f"/v1/ordenes/{pedido}/retracto", f"/v1/comercio/mis-pedidos/{pedido}/retracto"):
        respuesta = cliente.post(
            ruta, json={"motivo": "Prueba ficticia de QA"}, headers=portador(sesiones, "acudiente")
        )
        codigos[ruta.replace(pedido, "{id}")] = respuesta.status_code

    record_property("retracto_del_titular", codigos)
    assert 201 in codigos.values(), f"el titular no pudo retractar: {codigos}"
