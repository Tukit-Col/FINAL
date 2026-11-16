"""Ayudas compartidas de las pruebas HTTP de Comercio.

Los dobles (Catalogo, pasarela que no responde), la orden de ejemplo y los
atajos para llevar un pedido a un estado (pagado, con pago iniciado, envejecido)
viven aqui para que ningun archivo de prueba importe de otro. La fixture
`cliente` esta en `conftest.py`.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
from conftest import TOKEN_OPERADOR, bearer
from sqlalchemy import select, update
from tukit_comercio.api import app
from tukit_comercio.modelos import Base
from tukit_comercio.pasarela import PasarelaFalsa, TransaccionCreada

PEDIDO = Base.metadata.tables["pedido"]
HISTORIAL = Base.metadata.tables["historial_pedido"]
BANDEJA = Base.metadata.tables["bandeja_salida"]
RESERVA = Base.metadata.tables["reserva_inventario"]
ENVIO = Base.metadata.tables["envio"]

# Los avances son back-office: van con el token del operador.
OPERADOR_HDR = bearer(TOKEN_OPERADOR)
# Reparto propio: el despacho lleva a quien llamar.
CELULAR = "3109998877"
REPARTIDOR = {"repartidor_nombre": "Luis Gomez", "repartidor_celular": CELULAR}

PRODUCTO = "11111111-1111-5111-8111-111111111111"
# El mismo `ACUDIENTE` de `conftest`: sus pedidos son "suyos" por la sesion.
USUARIO = "22222222-2222-5222-8222-222222222222"
SKU = "TK-C001-ECO"
PRECIO = 4500

SOLICITUD_PAGO = {"correo_cliente": "ana@ejemplo.com", "metodo": "pse"}
URL_RESULTADO = "http://localhost:3000/pago/resultado"


class CatalogoFalso:
    """Doble del cliente de Catalogo: resuelve id + precio fijo por sku.

    Sin salir a la red. `precios` mapea sku -> precio; un sku ausente devuelve
    `None` (sku que no existe), y un precio `None` es el "sin precio vigente"
    del contrato de Catalogo. El id canonico es determinista por sku.
    """

    def __init__(self, precios: dict[str, int] | None = None) -> None:
        self.precios = precios or {}

    @staticmethod
    def id_canonico(sku: str) -> uuid.UUID:
        return uuid.uuid5(uuid.NAMESPACE_OID, sku)

    async def resolver(self, sku: str):
        if sku not in self.precios:
            return None
        return self.id_canonico(sku), self.precios[sku]


class PasarelaQueNoResponde(PasarelaFalsa):
    """Pasarela que revienta al cobrar, como Wompi caido o devolviendo 5xx.

    Hereda la verificacion/parseo de firma de la falsa; solo `crear_transaccion`
    lanza el error httpx que el adaptador real levantaria (`raise_for_status` o
    un fallo de red), para probar que el checkout lo traduce a un sobre y no a un
    500 con el traceback de la pasarela."""

    async def crear_transaccion(self, **_: object) -> TransaccionCreada:
        raise httpx.ConnectError("wompi no responde")


def nueva_orden(precio: int = PRECIO, cantidad: int = 2, sku: str = SKU) -> dict:
    """La orden que arma el checkout: un renglon y una entrega en Bogota."""
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


def total_de(orden: dict) -> int:
    """El total que Comercio debe cobrar por la orden: precio x cantidad."""
    return sum(linea["precio_unitario"] * linea["cantidad"] for linea in orden["lineas"])


def centavos(orden: dict) -> int:
    """El monto que Wompi reporta por la orden (en centavos)."""
    return total_de(orden) * 100


async def pagar(cliente: httpx.AsyncClient, pedido_id: str) -> dict:
    """Inicia el pago del pedido (intento sin resultado aun en Wompi)."""
    respuesta = await cliente.post(
        f"/v1/ordenes/{pedido_id}/pago", json={**SOLICITUD_PAGO, "url_redireccion": URL_RESULTADO}
    )
    return respuesta.json()


async def flujo_hasta_webhook(cliente: httpx.AsyncClient, estado_wompi: str) -> tuple[str, dict]:
    """Crea orden y pago, y devuelve el evento firmado que Wompi mandaria."""
    orden = nueva_orden()
    pedido_id = (await cliente.post("/v1/ordenes", json=orden)).json()["pedido_id"]
    pago = (await cliente.post(f"/v1/ordenes/{pedido_id}/pago", json=SOLICITUD_PAGO)).json()
    evento = app.state.pasarela.emitir_evento(
        referencia=pago["referencia_wompi"],
        transaccion_id=pago["transaccion_wompi"],
        estado_wompi=estado_wompi,
        monto_centavos=centavos(orden),
    )
    return pedido_id, evento


async def pedido_pagado(cliente: httpx.AsyncClient) -> str:
    """Un pedido del acudiente, pagado por el webhook falso (como en la vida)."""
    pedido_id, evento = await flujo_hasta_webhook(cliente, "APPROVED")
    await cliente.post("/v1/webhooks/wompi", json=evento)
    return pedido_id


async def pedido_con_pago(cliente: httpx.AsyncClient) -> tuple[str, str]:
    """Crea orden y pago; devuelve (pedido_id, referencia)."""
    pedido_id = (await cliente.post("/v1/ordenes", json=nueva_orden())).json()["pedido_id"]
    pago = await pagar(cliente, pedido_id)
    return pedido_id, pago["referencia_wompi"]


async def avanzar(
    cliente: httpx.AsyncClient, pedido_id: str, cuerpo: dict[str, Any], headers=OPERADOR_HDR
) -> httpx.Response:
    return await cliente.post(f"/v1/ordenes/{pedido_id}/avanzar", headers=headers, json=cuerpo)


async def estado_de(cliente: httpx.AsyncClient, pedido_id: str) -> str:
    return (await cliente.get(f"/v1/ordenes/{pedido_id}")).json()["estado"]


async def poner_estado(pedido_id: str, estado: str) -> None:
    """Atajo de prueba: deja el pedido en `estado` sin pasar por `/avanzar`."""
    async with app.state.motor.sesion() as db:
        conexion = await db.connection()
        await conexion.execute(
            update(PEDIDO).where(PEDIDO.c.id == uuid.UUID(pedido_id)).values(estado=estado)
        )


async def envejecer(pedido_id: str, horas: float) -> None:
    """Corre hacia atras la creacion del pedido."""
    async with app.state.motor.sesion() as db:
        conexion = await db.connection()
        await conexion.execute(
            update(PEDIDO)
            .where(PEDIDO.c.id == uuid.UUID(pedido_id))
            .values(creado_en=datetime.now(UTC) - timedelta(hours=horas))
        )


async def filas_de(tabla, pedido_id: str) -> list[Any]:
    """Las filas de `tabla` que cuelgan del pedido (por `pedido_id` o `agregado_id`)."""
    async with app.state.motor.sesion() as db:
        conexion = await db.connection()
        columna = tabla.c.pedido_id if "pedido_id" in tabla.c else tabla.c.agregado_id
        return list(await conexion.execute(select(tabla).where(columna == uuid.UUID(pedido_id))))


async def avisos_de(pedido_id: str) -> list[Any]:
    """Los avisos de logistica del pedido (`pedido_pagado` lo escribe el webhook)."""
    return [f for f in await filas_de(BANDEJA, pedido_id) if f.tipo != "pedido_pagado"]


async def avisos_en_bandeja(tipo: str) -> int:
    """Cuantos avisos de `tipo` hay en la bandeja de salida, de cualquier pedido."""
    async with app.state.motor.sesion() as db:
        conexion = await db.connection()
        return len(list(await conexion.execute(select(BANDEJA).where(BANDEJA.c.tipo == tipo))))


async def reservas_de(pedido_id: str) -> list[str]:
    async with app.state.motor.sesion() as db:
        conexion = await db.connection()
        filas = await conexion.execute(
            select(RESERVA.c.estado).where(RESERVA.c.pedido_id == uuid.UUID(pedido_id))
        )
        return [f.estado for f in filas]
