"""NFR-MAN-01: el control de acceso de Comercio: quien ve el tablero, avanza pedidos y lee historiales.

El contrato de hoy declara que Comercio no autentica (CONTRATO_API §12.9: "Ninguna ruta pide token")
y delega en el gateway. Eso es el hallazgo H-C-06 (control de acceso incompleto) y estas pruebas
fijan la conducta CORRECTA para que, cuando se cierre, dejen de ser xfail y protejan la regresion:

- El tablero de logistica y el avance de entrega son del back-office (staff): sin credencial, o con
  la de un acudiente, deben responder 401/403 y no filtrar direcciones ni mover pedidos.
- El historial de un acudiente (`mis-pedidos?usuario_id=`) no puede leerse con solo conocer otro
  `usuario_id` (IDOR): quien no es ese acudiente (ni staff) no ve sus pedidos.

Cada prueba es un xfail estricto: si el producto empieza a exigir credenciales el xfail pasa a XPASS y
la suite avisa para retirar la marca. Las credenciales son cadenas ficticias; no hay red.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from typing import Any

import httpx
import pytest
import pytest_asyncio
from sqlalchemy import update
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from tukit_comercio.api import app
from tukit_comercio.modelos import Base, Pedido
from tukit_comercio.pasarela import PasarelaFalsa
from tukit_comun.bd import MotorServicio

pytestmark = pytest.mark.nfr("NFR-MAN-01")

PEDIDO = Pedido.__table__
ACUDIENTE_A = "22222222-2222-5222-8222-222222222222"
ACUDIENTE_B = "33333333-3333-5333-8333-333333333333"

CREDENCIALES = pytest.mark.parametrize(
    "cabeceras",
    [{}, {"authorization": "Bearer sesion-ficticia-de-un-acudiente"}],
    ids=["sin_credencial", "con_sesion_de_acudiente"],
)


class CatalogoFalso:
    async def resolver(self, sku: str):
        return uuid.uuid5(uuid.NAMESPACE_OID, sku), 4500


@pytest_asyncio.fixture
async def entorno() -> AsyncIterator[tuple[httpx.AsyncClient, MotorServicio]]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conexion:
        await conexion.run_sync(Base.metadata.create_all)
    motor = MotorServicio(
        servicio="prueba", engine=engine, _fabrica=async_sessionmaker(engine, expire_on_commit=False)
    )
    app.state.motor = motor
    app.state.pasarela = PasarelaFalsa()
    app.state.catalogo = CatalogoFalso()
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://prueba") as http:
        yield http, motor
    await engine.dispose()


async def _crear(http: httpx.AsyncClient, usuario: str, destinatario: str) -> str:
    orden: dict[str, Any] = {
        "usuario_id": usuario,
        "hijos": 1,
        "colegios": ["Colegio Ficticio"],
        "lineas": [
            {"sku": "TK-C001-ECO", "nombre": "Cuaderno cuadriculado", "cantidad": 1, "precio_unitario": 4500}
        ],
        "entrega": {"destinatario": destinatario, "direccion": "Calle 1 # 2-3", "ciudad": "Bogota"},
    }
    return (await http.post("/v1/ordenes", json=orden)).json()["pedido_id"]


@pytest.mark.xfail(
    strict=True,
    reason=(
        "H-C-06: el tablero de logistica no exige staff y entrega destinatario y direccion de todos los "
        "pedidos a cualquiera: routers/comercio.py:54-60 (sin dependencia de autenticacion)"
    ),
)
@CREDENCIALES
async def test_el_tablero_de_logistica_exige_staff_y_no_filtra_direcciones(entorno, cabeceras):
    http, _ = entorno
    await _crear(http, ACUDIENTE_A, "Destinatario Ficticio Alfa")

    respuesta = await http.get("/v1/comercio/pedidos", headers=cabeceras)

    assert respuesta.status_code in (401, 403)
    assert "Destinatario Ficticio Alfa" not in respuesta.text


@pytest.mark.xfail(
    strict=True,
    reason=(
        "H-C-06: avanzar un pedido por la cadena de entrega no exige staff; cualquiera puede marcar "
        "despachado/entregado: routers/comercio.py:487-527 (sin dependencia de autenticacion)"
    ),
)
@CREDENCIALES
async def test_avanzar_un_pedido_exige_staff_y_no_lo_mueve_sin_credencial(entorno, cabeceras):
    http, motor = entorno
    pedido_id = await _crear(http, ACUDIENTE_A, "Destinatario Ficticio Alfa")
    async with motor.sesion() as db:
        await db.execute(update(PEDIDO).where(PEDIDO.c.id == uuid.UUID(pedido_id)).values(estado="pagado"))

    respuesta = await http.post(
        f"/v1/ordenes/{pedido_id}/avanzar", json={"destino": "en_preparacion"}, headers=cabeceras
    )

    assert respuesta.status_code in (401, 403)
    assert (await http.get(f"/v1/ordenes/{pedido_id}")).json()["estado"] == "pagado"


@pytest.mark.xfail(
    strict=True,
    reason=(
        "H-C-06: IDOR en mis-pedidos: filtra por el usuario_id del query sin verificar la sesion, asi que "
        "cualquiera lee los pedidos de otro acudiente: routers/comercio.py:63-77"
    ),
)
@CREDENCIALES
async def test_mis_pedidos_no_entrega_los_pedidos_de_otro_acudiente(entorno, cabeceras):
    """El acudiente A (o nadie) pide el historial de B conociendo su `usuario_id`: no debe verlo."""
    http, _ = entorno
    ajeno = await _crear(http, ACUDIENTE_B, "Destinatario Ficticio Beta")

    respuesta = await http.get(
        "/v1/comercio/mis-pedidos", params={"usuario_id": ACUDIENTE_B}, headers=cabeceras
    )

    assert respuesta.status_code in (401, 403, 404)
    assert ajeno not in respuesta.text
    assert "Destinatario Ficticio Beta" not in respuesta.text
