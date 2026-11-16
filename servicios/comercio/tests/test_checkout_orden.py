"""Crear la orden: re-verificar el precio, congelarlo y congelar la entrega (§9).

Lo que se defiende:

- Re-verificacion antes de cobrar: si el precio de Catalogo cambio respecto al
  aprobado, la orden no se cierra (`422 precio_cambiado`).
- El precio queda congelado en la linea al confirmar (ADR 0012, R-PRECIO): la
  linea guarda su propio `precio_unitario`, sin llave hacia el de Catalogo.
- La direccion queda congelada en el envio (ADR 0015) con sus datos extendidos,
  la localidad, el lugar de Google y el pin de OpenStreetMap (ADR 0049).
"""

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

# --- El precio congelado en la linea (a nivel de dato) ----------------------


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
    # El precio vive en la linea: dos renglones pueden diferir aunque el
    # catalogo tenga un solo precio publico hoy.
    assert a.precio_unitario == 4500
    assert b.precio_unitario == 5200


# --- Crear la orden por HTTP ------------------------------------------------


async def test_crear_orden_sin_id_canonico_lo_resuelve_por_sku(cliente):
    # Quien arma la orden nunca ve el id canonico (RPO cero): manda solo sku,
    # y Comercio lo resuelve contra Catalogo. La orden se cierra igual.
    orden = nueva_orden()
    orden["lineas"][0].pop("producto_canonico_id")
    respuesta = await cliente.post("/v1/ordenes", json=orden)
    assert respuesta.status_code == 201
    # El contrato no expone el id canonico; se mira la linea guardada.
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
    # La direccion quedo congelada en el envio (ADR 0015).
    assert cuerpo["envio"]["ciudad"] == "Bogota"
    # Y la reserva de inventario quedo tomada.
    assert await reservas_de(cuerpo["pedido_id"]) == ["activa"]


async def test_crear_orden_congela_los_datos_extendidos_de_entrega(cliente):
    # telefono/departamento/documento/indicaciones son parte de la copia
    # congelada del hecho de entrega (ADR 0015): entran por la solicitud y
    # vuelven en el envio serializado, no apuntan a la libreta de Identidad.
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
    # Una entrega con solo destinatario/direccion/ciudad cierra igual: los
    # campos opcionales son nullable y quedan en None.
    cuerpo = (await cliente.post("/v1/ordenes", json=nueva_orden())).json()
    envio = cuerpo["envio"]
    assert envio["telefono"] is None
    assert envio["departamento"] is None
    assert envio["documento_destinatario"] is None
    assert envio["indicaciones"] is None
    assert envio["localidad"] is None
    assert envio["google_place_id"] is None


async def test_crear_orden_congela_la_localidad_y_el_lugar_de_google(cliente):
    # El checkout con Google Places manda la localidad canonica y el place_id
    # de la sugerencia elegida; los dos quedan en la copia del envio.
    orden = nueva_orden()
    orden["entrega"].update(
        {
            "localidad": "Chapinero",
            "google_place_id": "ChIJx9Lr6tqZP44RQ1rNpuKDdeA",
            "indicaciones": "Apto 502, torre 2",
        }
    )
    cuerpo = (await cliente.post("/v1/ordenes", json=orden)).json()
    envio = cuerpo["envio"]
    assert envio["localidad"] == "Chapinero"
    assert envio["google_place_id"] == "ChIJx9Lr6tqZP44RQ1rNpuKDdeA"
    assert envio["indicaciones"] == "Apto 502, torre 2"
    # Y vuelve igual al leer el pedido.
    leido = (await cliente.get(f"/v1/comercio/pedidos/{cuerpo['pedido_id']}", headers=OPERADOR_HDR)).json()
    assert leido["envio"]["localidad"] == "Chapinero"
    assert leido["envio"]["google_place_id"] == "ChIJx9Lr6tqZP44RQ1rNpuKDdeA"


async def test_crear_orden_congela_el_pin_confirmado_en_openstreetmap(cliente):
    # Sin Google, el acudiente confirma su direccion en un mapa de OSM y el
    # punto queda en la copia del envio (ADR 0049).
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
        {"latitud": 4.65},  # una sola no sirve
        {"longitud": -74.05},
        {"latitud": 40.4, "longitud": -3.7},  # Madrid: homonimo de otro pais
        {"latitud": 4.65, "longitud": -140.0},
    ],
)
async def test_coordenadas_incompletas_o_fuera_de_colombia_se_rechazan(cliente, coordenadas):
    orden = nueva_orden()
    orden["entrega"].update(coordenadas)
    assert (await cliente.post("/v1/ordenes", json=orden)).status_code == 400


@pytest.mark.parametrize(("campo", "largo"), [("localidad", 65), ("google_place_id", 513)])
async def test_una_localidad_o_un_place_id_demasiado_largos_se_rechazan(cliente, campo, largo):
    # Como todo cuerpo que no cumple el esquema en Comercio: 400.
    orden = nueva_orden()
    orden["entrega"][campo] = "x" * largo
    respuesta = await cliente.post("/v1/ordenes", json=orden)
    assert respuesta.status_code == 400


async def test_reverificacion_rechaza_si_el_precio_cambio(cliente):
    # El acudiente aprobo un precio, pero Catalogo ahora dice otro.
    app.state.catalogo = CatalogoFalso({SKU: PRECIO + 700})
    respuesta = await cliente.post("/v1/ordenes", json=nueva_orden(precio=PRECIO))
    assert respuesta.status_code == 422
    assert respuesta.json()["error"] == "precio_cambiado"


async def test_reverificacion_rechaza_si_no_hay_precio(cliente):
    app.state.catalogo = CatalogoFalso({})  # producto sin precio vigente
    respuesta = await cliente.post("/v1/ordenes", json=nueva_orden())
    assert respuesta.status_code == 422
    assert respuesta.json()["error"] == "precio_cambiado"
