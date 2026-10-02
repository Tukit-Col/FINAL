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
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from tukit_comercio.api import app
from tukit_comercio.modelos import Base, EstadoPago, EstadoPedido
from tukit_comercio.pasarela import PasarelaCaida, PasarelaFalsa
from tukit_comun.bd import MotorServicio


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
    assert cuerpo["referencia_wompi"] == f"tukit-{cuerpo['pago_id']}"
    assert cuerpo["estado"] == EstadoPago.INICIADO.value


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
        monto_centavos=900000,
    )
    return pedido_id, evento


async def test_webhook_con_monto_distinto_no_aprueba(cliente):
    pedido_id, _ = await _flujo_hasta_webhook(cliente, "APPROVED")
    creada = app.state.pasarela.creadas[-1]
    evento = app.state.pasarela.emitir_evento(
        referencia=creada.referencia,
        transaccion_id=creada.transaccion_id,
        estado_wompi="APPROVED",
        monto_centavos=1,
    )
    respuesta = await cliente.post("/v1/webhooks/wompi", json=evento)
    assert respuesta.json()["estado"] == "monto_no_coincide"
    pedido = (await cliente.get(f"/v1/ordenes/{pedido_id}")).json()
    assert pedido["estado"] == EstadoPedido.PENDIENTE_PAGO.value
    assert pedido["pago"]["estado"] == EstadoPago.RECHAZADO.value


async def test_reintento_tras_rechazo_crea_otro_pago(cliente):
    pedido_id, evento = await _flujo_hasta_webhook(cliente, "DECLINED")
    await cliente.post("/v1/webhooks/wompi", json=evento)
    primera = app.state.pasarela.creadas[-1]

    segundo = await cliente.post(
        f"/v1/ordenes/{pedido_id}/pago",
        json={"correo_cliente": "ana@ejemplo.com", "metodo": "pse"},
    )
    assert segundo.status_code == 201
    cuerpo = segundo.json()
    assert cuerpo["referencia_wompi"] != primera.referencia

    evento2 = app.state.pasarela.emitir_evento(
        referencia=cuerpo["referencia_wompi"],
        transaccion_id=cuerpo["transaccion_wompi"],
        estado_wompi="APPROVED",
        monto_centavos=900000,
    )
    await cliente.post("/v1/webhooks/wompi", json=evento2)
    pedido = (await cliente.get(f"/v1/ordenes/{pedido_id}")).json()
    assert pedido["estado"] == EstadoPedido.PAGADO.value


async def test_webhook_guarda_el_metodo_que_reporta_wompi(cliente):
    pedido_id, _ = await _flujo_hasta_webhook(cliente, "APPROVED")
    creada = app.state.pasarela.creadas[-1]
    evento = app.state.pasarela.emitir_evento(
        referencia=creada.referencia,
        transaccion_id=creada.transaccion_id,
        estado_wompi="APPROVED",
        monto_centavos=900000,
        metodo_wompi="CARD",
    )
    await cliente.post("/v1/webhooks/wompi", json=evento)
    pedido = (await cliente.get(f"/v1/ordenes/{pedido_id}")).json()
    assert pedido["pago"]["metodo"] == "tarjeta"


async def test_pago_aprobado_no_retrocede_con_eventos_tardios(cliente):
    pedido_id, evento = await _flujo_hasta_webhook(cliente, "APPROVED")
    await cliente.post("/v1/webhooks/wompi", json=evento)
    creada = app.state.pasarela.creadas[-1]
    for estado_wompi, monto in (("PENDING", 900000), ("DECLINED", 900000), ("APPROVED", 1)):
        tardio = app.state.pasarela.emitir_evento(
            referencia=creada.referencia,
            transaccion_id=creada.transaccion_id,
            estado_wompi=estado_wompi,
            monto_centavos=monto,
        )
        respuesta = await cliente.post("/v1/webhooks/wompi", json=tardio)
        assert respuesta.json()["estado"] == "repetido"
        pedido = (await cliente.get(f"/v1/ordenes/{pedido_id}")).json()
        assert pedido["estado"] == EstadoPedido.PAGADO.value
        assert pedido["pago"]["estado"] == EstadoPago.APROBADO.value


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


# --- Sincronizacion al regreso del acudiente ---------------------------------


async def _pedido_con_pago(cliente) -> tuple[str, str]:
    """Crea orden y pago; devuelve (pedido_id, referencia). Total: 9000."""
    pedido_id = (await cliente.post("/v1/ordenes", json=_orden())).json()["pedido_id"]
    pago = (
        await cliente.post(
            f"/v1/ordenes/{pedido_id}/pago",
            json={
                "correo_cliente": "ana@ejemplo.com",
                "metodo": "pse",
                "url_redireccion": "http://localhost:3000/pago/resultado",
            },
        )
    ).json()
    return pedido_id, pago["referencia_wompi"]


async def _filas_bandeja(tipo: str) -> int:
    async with app.state.motor.sesion() as db:
        conexion = await db.connection()
        tabla = Base.metadata.tables["bandeja_salida"]
        return len(list(await conexion.execute(select(tabla).where(tabla.c.tipo == tipo))))


async def test_sincronizar_aprobado_marca_pagado(cliente):
    pedido_id, ref = await _pedido_con_pago(cliente)
    r = await cliente.post(f"/v1/pagos/falsa-APPROVED-{ref}/sincronizar")
    assert r.status_code == 200
    assert r.json() == {
        "pedido_id": pedido_id,
        "total": 9000,
        "estado_pago": "aprobado",
        "estado_pedido": "pagado",
    }


async def test_sincronizar_dos_veces_no_duplica_el_aviso(cliente):
    _, ref = await _pedido_con_pago(cliente)
    primera = await cliente.post(f"/v1/pagos/falsa-APPROVED-{ref}/sincronizar")
    segunda = await cliente.post(f"/v1/pagos/falsa-APPROVED-{ref}/sincronizar")
    assert primera.status_code == segunda.status_code == 200
    assert primera.json() == segunda.json()
    assert await _filas_bandeja("pedido_pagado") == 1


async def test_webhook_despues_de_sincronizar_es_repetido(cliente):
    _, ref = await _pedido_con_pago(cliente)
    await cliente.post(f"/v1/pagos/falsa-APPROVED-{ref}/sincronizar")
    evento = app.state.pasarela.emitir_evento(
        referencia=ref,
        transaccion_id=f"falsa-APPROVED-{ref}",
        estado_wompi="APPROVED",
        monto_centavos=900000,
    )
    r = await cliente.post("/v1/webhooks/wompi", json=evento)
    assert r.json()["estado"] == "repetido"
    assert await _filas_bandeja("pedido_pagado") == 1


async def test_pendiente_y_luego_aprobado_avanza(cliente):
    _, ref = await _pedido_con_pago(cliente)
    pendiente = await cliente.post(f"/v1/pagos/falsa-PENDING-{ref}/sincronizar")
    assert pendiente.status_code == 200
    assert pendiente.json()["estado_pago"] == "iniciado"
    assert pendiente.json()["estado_pedido"] == "pendiente_pago"
    aprobado = await cliente.post(f"/v1/pagos/falsa-APPROVED-{ref}/sincronizar")
    assert aprobado.json()["estado_pago"] == "aprobado"
    assert aprobado.json()["estado_pedido"] == "pagado"


async def test_sincronizar_rechazado_deja_pendiente(cliente):
    _, ref = await _pedido_con_pago(cliente)
    r = await cliente.post(f"/v1/pagos/falsa-DECLINED-{ref}/sincronizar")
    assert r.status_code == 200
    assert r.json()["estado_pago"] == "rechazado"
    assert r.json()["estado_pedido"] == "pendiente_pago"


async def test_sincronizar_transaccion_desconocida_es_404(cliente):
    r = await cliente.post("/v1/pagos/falsa-APPROVED-tukit-nada/sincronizar")
    assert r.status_code == 404
    assert r.json()["error"] == "transaccion_no_existe"


async def test_sincronizar_referencia_sin_pago_es_404(cliente):
    # La pasarela la conoce pero Comercio no tiene ese pago.
    app.state.pasarela.montos["tukit-huerfano"] = 900000
    r = await cliente.post("/v1/pagos/falsa-APPROVED-tukit-huerfano/sincronizar")
    assert r.status_code == 404
    assert r.json()["error"] == "pago_no_existe"


async def test_sincronizar_con_pasarela_caida_es_502(cliente):
    class PasarelaCaidaDoble:
        async def consultar_transaccion(self, transaccion_id):
            raise PasarelaCaida("sin red")

    app.state.pasarela = PasarelaCaidaDoble()
    r = await cliente.post("/v1/pagos/falsa-APPROVED-tukit-x/sincronizar")
    assert r.status_code == 502
    assert r.json()["error"] == "pasarela_no_disponible"


async def test_sincronizar_reintenta_una_vez_si_choca_el_indice_unico(cliente, monkeypatch):
    """Webhook y regreso del usuario simultaneos: el segundo INSERT falla y se reintenta."""
    from tukit_comercio import api as api_comercio

    pedido_id, ref = await _pedido_con_pago(cliente)
    original = api_comercio._aplicar_resultado
    llamadas = {"n": 0}

    async def con_choque(conexion, datos):
        llamadas["n"] += 1
        if llamadas["n"] == 1:
            # La "otra entrega" gana la carrera: aplica y confirma en su sesion.
            async with app.state.motor.sesion() as otra:
                await original(await otra.connection(), datos)
            raise IntegrityError("INSERT", {}, Exception("UNIQUE evento_id"))
        return await original(conexion, datos)

    monkeypatch.setattr(api_comercio, "_aplicar_resultado", con_choque)
    r = await cliente.post(f"/v1/pagos/falsa-APPROVED-{ref}/sincronizar")
    assert r.status_code == 200
    assert r.json() == {
        "pedido_id": pedido_id,
        "total": 9000,
        "estado_pago": "aprobado",
        "estado_pedido": "pagado",
    }
    assert llamadas["n"] == 2
    assert await _filas_bandeja("pedido_pagado") == 1
