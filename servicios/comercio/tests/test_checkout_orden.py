from __future__ import annotations

import pytest
from _ayudas_comercio import (
    OPERADOR_HDR,
    PRECIO,
    SKU,
    CatalogoFalso,
    filas_de,
    nueva_orden,
    reservas_de,
    total_de,
)
from conftest import agregar_linea, crear_pedido
from tukit_comercio.api import app
from tukit_comercio.modelos import Base, EstadoPedido

LINEA = Base.metadata.tables["linea_pedido"]


async def test_precio_de_linea_se_conserva(db):
    pedido = await crear_pedido(db)
    linea = await agregar_linea(db, pedido, precio=4500, cantidad=3)
    await db.refresh(linea)
    assert linea.precio_unitario == 4500
    assert linea.cantidad == 3


async def test_dos_lineas_mismo_producto_precios_independientes(db):
    pedido = await crear_pedido(db)
    a = await agregar_linea(db, pedido, precio=4500)
    b = await agregar_linea(db, pedido, precio=5200)
    await db.refresh(a)
    await db.refresh(b)
    assert a.precio_unitario == 4500
    assert b.precio_unitario == 5200


async def test_crear_orden_sin_id_canonico_lo_resuelve_por_sku(cliente):
    orden = nueva_orden()
    orden["lineas"][0].pop("producto_canonico_id")
    respuesta = await cliente.post("/v1/ordenes", json=orden)
    assert respuesta.status_code == 201
    (linea,) = await filas_de(LINEA, respuesta.json()["pedido_id"])
    assert linea.producto_canonico_id == CatalogoFalso.id_canonico(SKU)


async def test_crear_orden_congela_precio_y_reserva(cliente):
    orden = nueva_orden()
    respuesta = await cliente.post("/v1/ordenes", json=orden)
    assert respuesta.status_code == 201
    cuerpo = respuesta.json()
    assert cuerpo["estado"] == EstadoPedido.PENDIENTE_PAGO.value
    assert cuerpo["total"] == total_de(orden)
    assert cuerpo["lineas"][0]["precio_unitario"] == PRECIO
    assert cuerpo["envio"]["ciudad"] == "Bogota"
    assert await reservas_de(cuerpo["pedido_id"]) == ["activa"]


async def test_crear_orden_congela_los_datos_extendidos_de_entrega(cliente):
    orden = nueva_orden()
    orden["entrega"].update(
        {
            "telefono": "3001234567",
            "departamento": "Cundinamarca",
            "documento_destinatario": "CC 1020304050",
            "indicaciones": "Dejar en porteria, torre 3",
        }
    )
    cuerpo = (await cliente.post("/v1/ordenes", json=orden)).json()
    envio = cuerpo["envio"]
    assert envio["telefono"] == "3001234567"
    assert envio["departamento"] == "Cundinamarca"
    assert envio["documento_destinatario"] == "CC 1020304050"
    assert envio["indicaciones"] == "Dejar en porteria, torre 3"


async def test_crear_orden_sin_datos_extendidos_los_deja_nulos(cliente):
    cuerpo = (await cliente.post("/v1/ordenes", json=nueva_orden())).json()
    envio = cuerpo["envio"]
    assert envio["telefono"] is None
    assert envio["departamento"] is None
    assert envio["documento_destinatario"] is None
    assert envio["indicaciones"] is None
    assert envio["localidad"] is None


async def test_crear_orden_congela_la_localidad_y_las_indicaciones(cliente):
    orden = nueva_orden()
    orden["entrega"].update(
        {
            "localidad": "Chapinero",
            "indicaciones": "Apto 502, torre 2",
        }
    )
    cuerpo = (await cliente.post("/v1/ordenes", json=orden)).json()
    envio = cuerpo["envio"]
    assert envio["localidad"] == "Chapinero"
    assert envio["indicaciones"] == "Apto 502, torre 2"
    leido = (await cliente.get(f"/v1/comercio/pedidos/{cuerpo['pedido_id']}", headers=OPERADOR_HDR)).json()
    assert leido["envio"]["localidad"] == "Chapinero"


async def test_crear_orden_congela_el_pin_confirmado_en_openstreetmap(cliente):
    orden = nueva_orden()
    orden["entrega"].update({"latitud": 4.651818, "longitud": -74.051003})
    cuerpo = (await cliente.post("/v1/ordenes", json=orden)).json()
    assert (cuerpo["envio"]["latitud"], cuerpo["envio"]["longitud"]) == (4.651818, -74.051003)
    leido = (await cliente.get(f"/v1/comercio/pedidos/{cuerpo['pedido_id']}", headers=OPERADOR_HDR)).json()
    assert (leido["envio"]["latitud"], leido["envio"]["longitud"]) == (4.651818, -74.051003)


async def test_sin_pin_el_envio_trae_coordenadas_nulas(cliente):
    envio = (await cliente.post("/v1/ordenes", json=nueva_orden())).json()["envio"]
    assert (envio["latitud"], envio["longitud"]) == (None, None)


@pytest.mark.parametrize(
    "coordenadas",
    [
        {"latitud": 4.65},
        {"longitud": -74.05},
        {"latitud": 40.4, "longitud": -3.7},
        {"latitud": 4.65, "longitud": -140.0},
    ],
)
async def test_coordenadas_incompletas_o_fuera_de_colombia_se_rechazan(cliente, coordenadas):
    orden = nueva_orden()
    orden["entrega"].update(coordenadas)
    assert (await cliente.post("/v1/ordenes", json=orden)).status_code == 400


async def test_una_localidad_demasiado_larga_se_rechaza(cliente):
    orden = nueva_orden()
    orden["entrega"]["localidad"] = "x" * 65
    respuesta = await cliente.post("/v1/ordenes", json=orden)
    assert respuesta.status_code == 400


async def test_reverificacion_rechaza_si_el_precio_cambio(cliente):
    app.state.catalogo = CatalogoFalso({SKU: PRECIO + 700})
    respuesta = await cliente.post("/v1/ordenes", json=nueva_orden(precio=PRECIO))
    assert respuesta.status_code == 422
    assert respuesta.json()["error"] == "precio_cambiado"


async def test_reverificacion_rechaza_si_no_hay_precio(cliente):
    app.state.catalogo = CatalogoFalso({})
    respuesta = await cliente.post("/v1/ordenes", json=nueva_orden())
    assert respuesta.status_code == 422
    assert respuesta.json()["error"] == "precio_cambiado"
