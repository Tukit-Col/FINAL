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
"""

from __future__ import annotations

from pathlib import Path

import httpx
import pytest
from sqlalchemy import text
from stack_vivo import conexion_a, crear_orden, instancia, orden_pagada, portador, puerto_libre

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
        respuesta = crear_orden(http, sesiones["acudiente"]["usuario_id"], producto)

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


def _entregar(http: httpx.Client, pedido_id: str) -> None:
    for destino, extra in [
        ("en_preparacion", {}),
        ("despachado", {"transportadora": "Transportadora Ficticia QA", "guia": "QA-GUIA-0001"}),
        ("en_reparto", {}),
        ("entregado", {}),
    ]:
        respuesta = http.post(f"/v1/ordenes/{pedido_id}/avanzar", json={"destino": destino, **extra})
        assert respuesta.status_code == 200, respuesta.text


@pytest.mark.nfr("NFR-SEG-09")
async def test_el_retracto_antes_del_despacho_cancela_y_reembolsa(
    cliente: httpx.Client, sesiones: dict, producto: dict, consultar
):
    pedido = orden_pagada(cliente, sesiones["acudiente"]["usuario_id"], producto)
    respuesta = cliente.post(
        f"/v1/ordenes/{pedido}/retracto",
        json={"motivo": "Prueba ficticia de QA"},
        headers=portador(sesiones, "acudiente"),
    )

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
    _entregar(cliente, pedido)
    respuesta = cliente.post(
        f"/v1/ordenes/{pedido}/retracto",
        json={"motivo": "Prueba ficticia de QA"},
        headers=portador(sesiones, "acudiente"),
    )

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
    _entregar(cliente, pedido)
    async with conexion_a("comercio") as conexion:
        await conexion.execute(
            text("update envio set entregado_en = now() - interval '30 days' where pedido_id = :p"),
            {"p": pedido},
        )
        await conexion.commit()
    respuesta = cliente.post(
        f"/v1/ordenes/{pedido}/retracto",
        json={"motivo": "Prueba ficticia de QA"},
        headers=portador(sesiones, "acudiente"),
    )

    record_property("estado_retracto_30_dias", respuesta.status_code)
    assert 400 <= respuesta.status_code < 500, f"{respuesta.status_code}: {respuesta.text[:200]}"


@pytest.mark.nfr("NFR-SEG-09")
@pytest.mark.xfail(strict=True, reason="H-A-15: cancelar por retracto deja la reserva de inventario activa")
async def test_el_retracto_libera_la_reserva(
    cliente: httpx.Client, sesiones: dict, producto: dict, consultar
):
    pedido = orden_pagada(cliente, sesiones["acudiente"]["usuario_id"], producto)
    cliente.post(f"/v1/ordenes/{pedido}/retracto", json={"motivo": "Prueba ficticia de QA"})

    estados = {
        fila[0]
        for fila in await consultar(
            "comercio", "select estado from reserva_inventario where pedido_id = :p", p=pedido
        )
    }
    assert estados, "el pedido no tiene reserva"
    assert "activa" not in estados


@pytest.mark.nfr("NFR-SEG-09")
@pytest.mark.xfail(
    strict=True, reason="H-C-06: el retracto no pide sesion; cualquiera cancela el pedido de otro"
)
@pytest.mark.parametrize("quien", ["otro_acudiente", "anonimo"])
def test_nadie_mas_retracta_el_pedido_de_un_acudiente(
    cliente: httpx.Client, sesiones: dict, producto: dict, quien: str
):
    pedido = orden_pagada(cliente, sesiones["acudiente"]["usuario_id"], producto)
    cabeceras = portador(sesiones, "acudiente_2") if quien == "otro_acudiente" else {}
    respuesta = cliente.post(
        f"/v1/ordenes/{pedido}/retracto", json={"motivo": "Prueba ficticia de QA"}, headers=cabeceras
    )

    assert respuesta.status_code in (401, 403, 404), f"{respuesta.status_code}: {respuesta.text[:200]}"
