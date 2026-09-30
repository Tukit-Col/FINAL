"""El checkout de punta a punta contra la pasarela falsa (§9 del contrato).

Se prueba con `ASGITransport`, sin levantar uvicorn: la app se llama en el mismo
proceso. El motor, la pasarela y el cliente de Catalogo se inyectan a mano en
`app.state` para no abrir conexiones reales ni salir a la red. La pasarela es la
`PasarelaFalsa`, que firma sus propios eventos con el mismo algoritmo que Wompi,
asi que la verificacion de firma se ejerce de verdad.

Lo que se defiende es lo que el §9 promete:

- Re-verificacion antes de cobrar: si el precio de Catalogo cambio respecto al
  aprobado, la orden no se cierra (`422 precio_cambiado`).
- El precio queda congelado en la linea al confirmar (ADR 0012).
- El webhook es idempotente: el mismo evento dos veces mueve el pedido una vez.
- Solo se guarda id de transaccion y estado; ni un dato de tarjeta (SG-03).
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator

import httpx
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from tukit_comercio.api import app
from tukit_comercio.modelos import Base, EstadoPago, EstadoPedido
from tukit_comercio.pasarela import PasarelaFalsa, TransaccionCreada
from tukit_comun.bd import MotorServicio


class PasarelaCaida(PasarelaFalsa):
    """Pasarela que revienta al cobrar, como Wompi caido o devolviendo 5xx.

    Hereda la verificacion/parseo de firma de la falsa; solo `crear_transaccion`
    lanza el error httpx que el adaptador real levantaria (`raise_for_status` o
    un fallo de red), para probar que el checkout lo traduce a un sobre y no a un
    500 con el traceback de la pasarela."""

    async def crear_transaccion(self, **_: object) -> TransaccionCreada:
        raise httpx.ConnectError("wompi no responde")


class CatalogoFalso:
    """Doble del cliente de Catalogo: resuelve id + precio fijo por sku.

    Sin salir a la red. `precios` mapea sku -> precio; un sku ausente devuelve
    `None` (sku que no existe), y un precio `None` es el "sin precio vigente"
    del contrato de Catalogo. El id canonico es determinista por sku.
    """

    def __init__(self, precios: dict[str, int] | None = None) -> None:
        self.precios = precios or {}

    async def resolver(self, sku: str):
        if sku not in self.precios:
            return None
        return uuid.uuid5(uuid.NAMESPACE_OID, sku), self.precios[sku]


PRODUCTO = "11111111-1111-5111-8111-111111111111"
USUARIO = "22222222-2222-5222-8222-222222222222"


def _orden(precio: int = 4500, cantidad: int = 2, sku: str = "TK-C001-ECO") -> dict:
    return {
        "usuario_id": USUARIO,
        "hijos": 1,
        "colegios": ["Colegio San Jose"],
        "lineas": [
            {
                "producto_canonico_id": PRODUCTO,
                "sku": sku,
                "nombre": "Cuaderno cuadriculado",
                "cantidad": cantidad,
                "precio_unitario": precio,
            }
        ],
        "entrega": {
            "destinatario": "Ana Perez",
            "direccion": "Calle 1 # 2-3",
            "ciudad": "Bogota",
        },
    }


@pytest_asyncio.fixture
async def cliente() -> AsyncIterator[httpx.AsyncClient]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conexion:
        await conexion.run_sync(Base.metadata.create_all)
    fabrica = async_sessionmaker(engine, expire_on_commit=False)
    app.state.motor = MotorServicio(servicio="prueba", engine=engine, _fabrica=fabrica)
    app.state.pasarela = PasarelaFalsa()
    app.state.catalogo = CatalogoFalso({"TK-C001-ECO": 4500})
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://prueba") as http:
        yield http
    await engine.dispose()


async def test_crear_orden_sin_id_canonico_lo_resuelve_por_sku(cliente):
    # Quien arma la orden nunca ve el id canonico (RPO cero): manda solo sku,
    # y Comercio lo resuelve contra Catalogo. La orden se cierra igual.
    orden = _orden()
    orden["lineas"][0].pop("producto_canonico_id")
    respuesta = await cliente.post("/v1/ordenes", json=orden)
    assert respuesta.status_code == 201


async def test_crear_orden_congela_precio_y_reserva(cliente):
    respuesta = await cliente.post("/v1/ordenes", json=_orden())
    assert respuesta.status_code == 201
    cuerpo = respuesta.json()
    assert cuerpo["estado"] == EstadoPedido.PENDIENTE_PAGO.value
    assert cuerpo["total"] == 9000  # 4500 x 2
    assert cuerpo["lineas"][0]["precio_unitario"] == 4500
    # La direccion quedo congelada en el envio (ADR 0015).
    assert cuerpo["envio"]["ciudad"] == "Bogota"


async def test_crear_orden_congela_los_datos_extendidos_de_entrega(cliente):
    # telefono/departamento/documento/indicaciones son parte de la copia
    # congelada del hecho de entrega (ADR 0015): entran por la solicitud y
    # vuelven en el envio serializado, no apuntan a la libreta de Identidad.
    orden = _orden()
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
    # La solicitud legada (solo destinatario/direccion/ciudad) sigue cerrando:
    # los cuatro campos nuevos son nullable y quedan en None.
    cuerpo = (await cliente.post("/v1/ordenes", json=_orden())).json()
    envio = cuerpo["envio"]
    assert envio["telefono"] is None
    assert envio["departamento"] is None
    assert envio["documento_destinatario"] is None
    assert envio["indicaciones"] is None


async def test_reverificacion_rechaza_si_el_precio_cambio(cliente):
    # El acudiente aprobo 4500, pero Catalogo ahora dice otro precio.
    app.state.catalogo = CatalogoFalso({"TK-C001-ECO": 5200})
    respuesta = await cliente.post("/v1/ordenes", json=_orden(precio=4500))
    assert respuesta.status_code == 422
    assert respuesta.json()["error"] == "precio_cambiado"


async def test_reverificacion_rechaza_si_no_hay_precio(cliente):
    app.state.catalogo = CatalogoFalso({})  # producto sin precio vigente
    respuesta = await cliente.post("/v1/ordenes", json=_orden())
    assert respuesta.status_code == 422
    assert respuesta.json()["error"] == "precio_cambiado"


async def test_iniciar_pago_guarda_solo_referencia_y_estado(cliente):
    pedido_id = (await cliente.post("/v1/ordenes", json=_orden())).json()["pedido_id"]
    respuesta = await cliente.post(
        f"/v1/ordenes/{pedido_id}/pago",
        json={"correo_cliente": "ana@ejemplo.com", "metodo": "pse"},
    )
    assert respuesta.status_code == 201
    cuerpo = respuesta.json()
    # El primer intento es `-1`; el sufijo de intento es lo que deja reintentar
    # tras un rechazo sin chocar con el indice unico de la referencia.
    assert cuerpo["referencia_wompi"] == f"tukit-{pedido_id}-1"
    assert cuerpo["estado"] == EstadoPago.INICIADO.value


async def test_iniciar_pago_con_pasarela_caida_da_502(cliente):
    # Wompi caido no puede volverse un 500 con el traceback de la pasarela: es
    # un sobre tipado que el checkout puede mostrar y el cliente reintentar.
    pedido_id = (await cliente.post("/v1/ordenes", json=_orden())).json()["pedido_id"]
    app.state.pasarela = PasarelaCaida()
    respuesta = await cliente.post(
        f"/v1/ordenes/{pedido_id}/pago",
        json={"correo_cliente": "ana@ejemplo.com", "metodo": "pse"},
    )
    assert respuesta.status_code == 502
    assert respuesta.json()["error"] == "pasarela_no_disponible"


async def _flujo_hasta_webhook(cliente, estado_wompi: str):
    pedido_id = (await cliente.post("/v1/ordenes", json=_orden())).json()["pedido_id"]
    pago = (
        await cliente.post(
            f"/v1/ordenes/{pedido_id}/pago",
            json={"correo_cliente": "ana@ejemplo.com", "metodo": "pse"},
        )
    ).json()
    evento = app.state.pasarela.emitir_evento(
        referencia=pago["referencia_wompi"],
        transaccion_id=pago["transaccion_wompi"],
        estado_wompi=estado_wompi,
    )
    return pedido_id, evento


async def test_webhook_aprobado_transiciona_a_pagado(cliente):
    pedido_id, evento = await _flujo_hasta_webhook(cliente, "APPROVED")
    respuesta = await cliente.post("/v1/webhooks/wompi", json=evento)
    assert respuesta.status_code == 200
    assert respuesta.json()["estado"] == "aplicado"

    pedido = (await cliente.get(f"/v1/ordenes/{pedido_id}")).json()
    assert pedido["estado"] == EstadoPedido.PAGADO.value
    assert pedido["pago"]["estado"] == EstadoPago.APROBADO.value


async def test_webhook_idempotente_no_mueve_dos_veces(cliente):
    pedido_id, evento = await _flujo_hasta_webhook(cliente, "APPROVED")
    primera = await cliente.post("/v1/webhooks/wompi", json=evento)
    segunda = await cliente.post("/v1/webhooks/wompi", json=evento)
    assert primera.json()["estado"] == "aplicado"
    assert segunda.json()["estado"] == "repetido"

    # Un solo evento procesado, aunque llego dos veces.
    async with app.state.motor.sesion() as db:
        conexion = await db.connection()
        tabla = Base.metadata.tables["evento_pasarela_procesado"]
        procesados = list(await conexion.execute(select(tabla)))
    assert len(procesados) == 1


async def test_webhook_con_firma_invalida_se_ignora(cliente):
    _, evento = await _flujo_hasta_webhook(cliente, "APPROVED")
    evento["signature"]["checksum"] = "firma_que_no_cuadra"
    respuesta = await cliente.post("/v1/webhooks/wompi", json=evento)
    assert respuesta.json()["estado"] == "ignorado"
    assert respuesta.json()["motivo"] == "firma_invalida"


async def test_webhook_rechazado_no_pasa_a_pagado(cliente):
    pedido_id, evento = await _flujo_hasta_webhook(cliente, "DECLINED")
    await cliente.post("/v1/webhooks/wompi", json=evento)
    pedido = (await cliente.get(f"/v1/ordenes/{pedido_id}")).json()
    assert pedido["estado"] == EstadoPedido.PENDIENTE_PAGO.value
    assert pedido["pago"]["estado"] == EstadoPago.RECHAZADO.value


async def test_reintento_tras_rechazo_no_colisiona_la_referencia(cliente):
    # El primer intento se rechaza y el acudiente reintenta. La referencia
    # lleva el numero de intento (`-1`, `-2`), asi que el segundo pago no choca
    # con el indice unico de `referencia_wompi` y no revienta con un 500.
    pedido_id, evento = await _flujo_hasta_webhook(cliente, "DECLINED")
    await cliente.post("/v1/webhooks/wompi", json=evento)

    reintento = await cliente.post(
        f"/v1/ordenes/{pedido_id}/pago",
        json={"correo_cliente": "ana@ejemplo.com", "metodo": "pse"},
    )
    assert reintento.status_code == 201
    assert reintento.json()["referencia_wompi"] == f"tukit-{pedido_id}-2"


async def _pedido_pagado(cliente) -> str:
    pedido_id, evento = await _flujo_hasta_webhook(cliente, "APPROVED")
    await cliente.post("/v1/webhooks/wompi", json=evento)
    return pedido_id


async def test_avanzar_pedido_pagado_a_en_preparacion(cliente):
    pedido_id = await _pedido_pagado(cliente)
    respuesta = await cliente.post(f"/v1/ordenes/{pedido_id}/avanzar", json={"destino": "en_preparacion"})
    assert respuesta.status_code == 200
    assert respuesta.json()["estado"] == EstadoPedido.EN_PREPARACION.value


async def test_avanzar_a_destino_ilegal_da_409(cliente):
    # pagado -> entregado se salta pasos: la tabla lo rechaza con 409.
    pedido_id = await _pedido_pagado(cliente)
    respuesta = await cliente.post(f"/v1/ordenes/{pedido_id}/avanzar", json={"destino": "entregado"})
    assert respuesta.status_code == 409
    assert respuesta.json()["error"] == "transicion_invalida"


async def test_despachar_sin_guia_da_422(cliente):
    pedido_id = await _pedido_pagado(cliente)
    await cliente.post(f"/v1/ordenes/{pedido_id}/avanzar", json={"destino": "en_preparacion"})
    respuesta = await cliente.post(f"/v1/ordenes/{pedido_id}/avanzar", json={"destino": "despachado"})
    assert respuesta.status_code == 422
    assert respuesta.json()["error"] == "despacho_incompleto"


async def test_despachar_con_guia_sella_el_envio(cliente):
    pedido_id = await _pedido_pagado(cliente)
    await cliente.post(f"/v1/ordenes/{pedido_id}/avanzar", json={"destino": "en_preparacion"})
    respuesta = await cliente.post(
        f"/v1/ordenes/{pedido_id}/avanzar",
        json={"destino": "despachado", "transportadora": "Servientrega", "guia": "ABC123"},
    )
    assert respuesta.status_code == 200
    pedido = (await cliente.get(f"/v1/ordenes/{pedido_id}")).json()
    assert pedido["estado"] == EstadoPedido.DESPACHADO.value
    assert pedido["envio"]["transportadora"] == "Servientrega"
    assert pedido["envio"]["guia"] == "ABC123"


async def test_avanzar_hasta_entregado_marca_entregado_en(cliente):
    pedido_id = await _pedido_pagado(cliente)
    for cuerpo in (
        {"destino": "en_preparacion"},
        {"destino": "despachado", "transportadora": "Servientrega", "guia": "ABC123"},
        {"destino": "en_reparto"},
        {"destino": "entregado"},
    ):
        respuesta = await cliente.post(f"/v1/ordenes/{pedido_id}/avanzar", json=cuerpo)
        assert respuesta.status_code == 200, respuesta.json()
    pedido = (await cliente.get(f"/v1/ordenes/{pedido_id}")).json()
    assert pedido["estado"] == EstadoPedido.ENTREGADO.value
    assert pedido["envio"]["entregado_en"] is not None


async def test_avanzar_pedido_inexistente_da_404(cliente):
    respuesta = await cliente.post(f"/v1/ordenes/{uuid.uuid4()}/avanzar", json={"destino": "en_preparacion"})
    assert respuesta.status_code == 404
    assert respuesta.json()["error"] == "pedido_no_existe"


async def test_mis_pedidos_solo_devuelve_los_del_acudiente(cliente):
    # Dos pedidos del acudiente conocido y uno de otro usuario.
    await cliente.post("/v1/ordenes", json=_orden())
    await cliente.post("/v1/ordenes", json=_orden())
    otro = _orden()
    otro["usuario_id"] = "33333333-3333-5333-8333-333333333333"
    await cliente.post("/v1/ordenes", json=otro)

    mios = (await cliente.get(f"/v1/comercio/mis-pedidos?usuario_id={USUARIO}")).json()
    assert mios["total"] == 2
    assert all(p["total"] == 9000 for p in mios["pedidos"])

    ajenos = (await cliente.get(f"/v1/comercio/mis-pedidos?usuario_id={otro['usuario_id']}")).json()
    assert ajenos["total"] == 1


async def test_retracto_cancela_y_marca_reembolso(cliente):
    pedido_id, evento = await _flujo_hasta_webhook(cliente, "APPROVED")
    await cliente.post("/v1/webhooks/wompi", json=evento)
    respuesta = await cliente.post(f"/v1/ordenes/{pedido_id}/retracto", json={"motivo": "no lo quiero"})
    assert respuesta.status_code == 201
    cuerpo = respuesta.json()
    assert cuerpo["devolucion_id"]
    # `pagado -> cancelado` es una transicion valida (ADR/tabla), asi que el
    # retracto cancela el pedido y marca el pago para reembolso.
    assert cuerpo["cancelado"] is True
    assert cuerpo["estado"] == EstadoPedido.CANCELADO.value

    pedido = (await cliente.get(f"/v1/ordenes/{pedido_id}")).json()
    assert pedido["estado"] == EstadoPedido.CANCELADO.value
    assert pedido["pago"]["estado"] == EstadoPago.REEMBOLSADO.value
