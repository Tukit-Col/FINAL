"""NFR-MAN-01: el control de acceso de Comercio: quien ve el tablero, avanza pedidos y lee historiales.

El contrato declaraba que Comercio no autenticaba (CONTRATO_API §12.9: "Ninguna ruta pide token") y
delegaba en el gateway: el hallazgo H-C-06 (control de acceso incompleto). Estas pruebas fijaban la
conducta CORRECTA como xfail estrictos; e82d03c la implanto en las tres rutas (`_exigir_staff` y
`_usuario_de_sesion` de `routers/comercio.py`, validando la sesion contra Identidad) y desde
entonces protegen la regresion:

- El tablero de logistica y el avance de entrega son del back-office (staff): sin credencial, con
  un token que Identidad no reconoce o con la sesion de un acudiente responden 401/403 y no filtran
  direcciones ni mueven pedidos.
- El historial de un acudiente (`mis-pedidos`) no puede leerse con solo conocer otro `usuario_id`
  (IDOR): sin sesion es 401 y, con la de otro acudiente, el `?usuario_id=` se ignora y solo salen
  los pedidos del portador.

Las credenciales son cadenas ficticias resueltas por `IdentidadFalsa` (`conftest.py`); no hay red.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from typing import Any

import httpx
import pytest
import pytest_asyncio
from conftest import ACUDIENTE, OTRO_ACUDIENTE, TOKEN_ACUDIENTE, IdentidadFalsa, bearer
from sqlalchemy import update
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from tukit_comercio.api import app
from tukit_comercio.modelos import Base, Pedido
from tukit_comercio.pasarela import PasarelaFalsa
from tukit_comun.bd import MotorServicio

pytestmark = pytest.mark.nfr("NFR-MAN-01")

PEDIDO = Pedido.__table__
ACUDIENTE_A = ACUDIENTE
ACUDIENTE_B = OTRO_ACUDIENTE

# (cabeceras, codigo esperado en las rutas del staff). La sesion del acudiente es valida pero sin
# rol de staff: 403; sin token o con uno que Identidad no conoce: 401.
CREDENCIALES = pytest.mark.parametrize(
    ("cabeceras", "codigo"),
    [
        ({}, 401),
        ({"authorization": "Bearer sesion-ficticia-desconocida"}, 401),
        (bearer(TOKEN_ACUDIENTE), 403),
    ],
    ids=["sin_credencial", "token_desconocido", "con_sesion_de_acudiente"],
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
    app.state.identidad = IdentidadFalsa()
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


@CREDENCIALES
async def test_el_tablero_de_logistica_exige_staff_y_no_filtra_direcciones(entorno, cabeceras, codigo):
    """H-C-06 cerrado en e82d03c: `tablero` llama a `_exigir_staff` antes de leer la base."""
    http, _ = entorno
    await _crear(http, ACUDIENTE_A, "Destinatario Ficticio Alfa")

    respuesta = await http.get("/v1/comercio/pedidos", headers=cabeceras)

    assert respuesta.status_code == codigo
    assert respuesta.json()["error"] == ("sesion_invalida" if codigo == 401 else "acceso_denegado")
    assert "Destinatario Ficticio Alfa" not in respuesta.text


@CREDENCIALES
async def test_avanzar_un_pedido_exige_staff_y_no_lo_mueve_sin_credencial(entorno, cabeceras, codigo):
    """H-C-06 cerrado en e82d03c: `avanzar_pedido` llama a `_exigir_staff` antes de abrir la sesion."""
    http, motor = entorno
    pedido_id = await _crear(http, ACUDIENTE_A, "Destinatario Ficticio Alfa")
    async with motor.sesion() as db:
        await db.execute(update(PEDIDO).where(PEDIDO.c.id == uuid.UUID(pedido_id)).values(estado="pagado"))

    respuesta = await http.post(
        f"/v1/ordenes/{pedido_id}/avanzar", json={"destino": "en_preparacion"}, headers=cabeceras
    )

    assert respuesta.status_code == codigo
    assert (await http.get(f"/v1/ordenes/{pedido_id}")).json()["estado"] == "pagado"


@CREDENCIALES
async def test_mis_pedidos_no_entrega_los_pedidos_de_otro_acudiente(entorno, cabeceras, codigo):
    """El acudiente A (o nadie) pide el historial de B conociendo su `usuario_id`: no debe verlo.

    H-C-06 cerrado en e82d03c: `mis_pedidos` toma el usuario de `_usuario_de_sesion`. Sin sesion
    valida es 401; con la de A no hay 403 (es su propio historial) sino 200 con SOLO lo de A."""
    http, _ = entorno
    ajeno = await _crear(http, ACUDIENTE_B, "Destinatario Ficticio Beta")

    respuesta = await http.get(
        "/v1/comercio/mis-pedidos", params={"usuario_id": ACUDIENTE_B}, headers=cabeceras
    )

    if codigo == 403:
        assert (respuesta.status_code, respuesta.json()) == (200, {"total": 0, "pedidos": []})
    else:
        assert respuesta.status_code == 401
    assert ajeno not in respuesta.text
    assert "Destinatario Ficticio Beta" not in respuesta.text
