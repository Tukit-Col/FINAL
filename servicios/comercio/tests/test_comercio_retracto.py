"""NFR-MAN-01: el retracto y la devolucion (FU-04, Ley 1480 de 2011): quien, cuando y que se revierte.

`POST /v1/ordenes/{pedido_id}/retracto` es la compensacion C-charge de la saga: devuelve el dinero
y cancela el pedido. Es el unico lugar donde el sistema deshace un cobro, asi que se fija con
cuidado lo que hace HOY (pasa) y lo que le exige su propio contrato (xfail estricto, con evidencia):

- Hoy: un pedido pagado o en incidencia se cancela, deja una devolucion por el total y marca el pago
  como reembolsado; uno ya en reparto o entregado registra la devolucion pero no se cancela
  (la maquina de estados no lo permite); un pedido inexistente es 404; el efecto no se derrama a otros
  pedidos; el motivo es opcional y acotado.
- Defectos (xfail estricto): no hay ventana de 5 dias habiles tras la entrega, el pedido ajeno se
  puede retractar (no hay actor ni dueño: H-C-06), el retracto no libera la reserva de inventario
  que el modelo promete soltar al cancelar, y la devolucion de un pedido nunca pagado registra
  dinero que nunca entro.

La ventana se prueba SOLO con casos lejos de la frontera (entregado hace 1 dia / hace 30 dias): el
router no tiene reloj inyectable y no se toca el producto. Sin red: SQLite en memoria y `PasarelaFalsa`.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import pytest
import pytest_asyncio
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from tukit_comercio.api import app
from tukit_comercio.modelos import Base, Devolucion, Envio, Pago, Pedido, ReservaInventario
from tukit_comercio.pasarela import PasarelaFalsa
from tukit_comun.bd import MotorServicio

pytestmark = pytest.mark.nfr("NFR-MAN-01")

PEDIDO = Pedido.__table__
ENVIO = Envio.__table__
ACUDIENTE = "22222222-2222-5222-8222-222222222222"
OTRO_ACUDIENTE = "33333333-3333-5333-8333-333333333333"
CORREO = "acudiente@example.test"


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


def _orden(usuario: str = ACUDIENTE) -> dict[str, Any]:
    return {
        "usuario_id": usuario,
        "hijos": 1,
        "colegios": ["Colegio Ficticio"],
        "lineas": [
            {"sku": "TK-C001-ECO", "nombre": "Cuaderno cuadriculado", "cantidad": 2, "precio_unitario": 4500}
        ],
        "entrega": {"destinatario": "Acudiente Ficticio", "direccion": "Calle 1 # 2-3", "ciudad": "Bogota"},
    }


async def _pedido_pagado(http: httpx.AsyncClient, usuario: str = ACUDIENTE) -> str:
    """Una orden de $9.000 creada, cobrada y confirmada por webhook: queda `pagado` con pago `aprobado`."""
    pedido_id = (await http.post("/v1/ordenes", json=_orden(usuario))).json()["pedido_id"]
    pago = (
        await http.post(f"/v1/ordenes/{pedido_id}/pago", json={"correo_cliente": CORREO, "metodo": "pse"})
    ).json()
    # Desde 7c2ae19 el evento firma el monto y desde fe8c030 el webhook lo coteja con el del pago.
    evento = app.state.pasarela.emitir_evento(
        referencia=pago["referencia_wompi"],
        transaccion_id=pago["transaccion_wompi"],
        estado_wompi="APPROVED",
        monto_centavos=app.state.pasarela.montos[pago["referencia_wompi"]],
    )
    assert (await http.post("/v1/webhooks/wompi", json=evento)).json()["estado"] == "aplicado"
    return pedido_id


async def _en_estado(
    motor: MotorServicio, pedido_id: str, estado: str, *, entregado_hace: timedelta | None = None
) -> None:
    async with motor.sesion() as db:
        await db.execute(update(PEDIDO).where(PEDIDO.c.id == uuid.UUID(pedido_id)).values(estado=estado))
        if entregado_hace is not None:
            await db.execute(
                update(ENVIO)
                .where(ENVIO.c.pedido_id == uuid.UUID(pedido_id))
                .values(entregado_en=datetime.now(UTC) - entregado_hace)
            )


async def _retractar(http: httpx.AsyncClient, pedido_id: str, **cuerpo: Any) -> httpx.Response:
    return await http.post(f"/v1/ordenes/{pedido_id}/retracto", json=cuerpo)


async def _devoluciones(motor: MotorServicio, pedido_id: str) -> list[Devolucion]:
    async with motor.sesion() as db:
        return list(await db.scalars(select(Devolucion).where(Devolucion.pedido_id == uuid.UUID(pedido_id))))


async def _estados(motor: MotorServicio, pedido_id: str) -> tuple[str, list[str], list[str]]:
    """(estado del pedido, estados de sus pagos, estados de sus reservas)."""
    async with motor.sesion() as db:
        pedido = await db.scalar(select(Pedido.estado).where(Pedido.id == uuid.UUID(pedido_id)))
        pagos = list(await db.scalars(select(Pago.estado).where(Pago.pedido_id == uuid.UUID(pedido_id))))
        reservas = list(
            await db.scalars(
                select(ReservaInventario.estado).where(ReservaInventario.pedido_id == uuid.UUID(pedido_id))
            )
        )
    return pedido, pagos, reservas


# --- lo que hace hoy: cancelar, devolver, reembolsar --------------------------------------------


async def test_retracto_de_un_pedido_pagado_lo_cancela_registra_la_devolucion_y_reembolsa_el_pago(entorno):
    http, motor = entorno
    pedido_id = await _pedido_pagado(http)

    respuesta = await _retractar(http, pedido_id, motivo="Estudiante Ficticio Uno cambio de colegio")

    assert respuesta.status_code == 201
    cuerpo = respuesta.json()
    assert set(cuerpo) == {"devolucion_id", "pedido_id", "cancelado", "estado"}
    assert (cuerpo["pedido_id"], cuerpo["cancelado"], cuerpo["estado"]) == (pedido_id, True, "cancelado")
    (devolucion,) = await _devoluciones(motor, pedido_id)
    assert str(devolucion.id) == cuerpo["devolucion_id"]
    assert devolucion.usuario_id == uuid.UUID(ACUDIENTE)  # el titular sale del pedido
    assert devolucion.motivo == "Estudiante Ficticio Uno cambio de colegio"
    assert devolucion.monto == 9000  # el total pagado: 2 x $4.500
    assert (await _estados(motor, pedido_id))[:2] == ("cancelado", ["reembolsado"])
    visto = (await http.get(f"/v1/ordenes/{pedido_id}")).json()
    assert (visto["estado"], visto["pago"]["estado"]) == ("cancelado", "reembolsado")


async def test_retracto_de_un_pedido_en_incidencia_tambien_cancela_y_reembolsa(entorno):
    http, motor = entorno
    pedido_id = await _pedido_pagado(http)
    await _en_estado(motor, pedido_id, "incidencia")

    respuesta = await _retractar(http, pedido_id)

    assert (respuesta.status_code, respuesta.json()["cancelado"]) == (201, True)
    assert (await _estados(motor, pedido_id))[:2] == ("cancelado", ["reembolsado"])


@pytest.mark.parametrize("estado", ["en_preparacion", "despachado", "en_reparto", "entregado"])
async def test_si_la_maquina_de_estados_no_permite_cancelar_se_registra_la_devolucion_sin_cancelar(
    entorno, estado
):
    """Un pedido ya en camino no puede volver a `cancelado` (la tabla no lo permite): el retracto queda
    registrado para que logistica lo gestione, la respuesta lo dice (`cancelado: false`) y el estado
    del pedido no se toca."""
    http, motor = entorno
    pedido_id = await _pedido_pagado(http)
    await _en_estado(motor, pedido_id, estado)

    respuesta = await _retractar(http, pedido_id, motivo="no lo quiero")

    assert respuesta.status_code == 201
    cuerpo = respuesta.json()
    assert (cuerpo["cancelado"], cuerpo["estado"]) == (False, estado)
    assert len(await _devoluciones(motor, pedido_id)) == 1
    assert (await _estados(motor, pedido_id))[0] == estado


async def test_retractar_un_pedido_sin_pagar_lo_cancela_pero_no_marca_reembolso_de_lo_no_cobrado(entorno):
    """`pendiente_pago -> cancelado` es legal. El pago `iniciado` (nunca aprobado) no pasa a
    `reembolsado`: solo se reembolsa lo que de verdad se cobro."""
    http, motor = entorno
    pedido_id = (await http.post("/v1/ordenes", json=_orden())).json()["pedido_id"]
    await http.post(f"/v1/ordenes/{pedido_id}/pago", json={"correo_cliente": CORREO})

    respuesta = await _retractar(http, pedido_id)

    assert (respuesta.status_code, respuesta.json()["cancelado"]) == (201, True)
    assert (await _estados(motor, pedido_id))[:2] == ("cancelado", ["iniciado"])


async def test_el_retracto_no_se_derrama_a_otros_pedidos(entorno):
    """La cancelacion y el reembolso se acotan al pedido retractado: el otro sigue pagado y aprobado."""
    http, motor = entorno
    retractado = await _pedido_pagado(http)
    intacto = await _pedido_pagado(http, usuario=OTRO_ACUDIENTE)

    await _retractar(http, retractado)

    assert (await _estados(motor, retractado))[:2] == ("cancelado", ["reembolsado"])
    assert (await _estados(motor, intacto))[:2] == ("pagado", ["aprobado"])
    assert await _devoluciones(motor, intacto) == []


async def test_retractar_un_pedido_que_no_existe_es_404_y_no_registra_nada(entorno):
    http, motor = entorno

    respuesta = await _retractar(http, str(uuid.uuid4()))

    assert respuesta.status_code == 404
    assert respuesta.json() == {
        "error": "pedido_no_existe",
        "mensaje": "No hay ningun pedido con ese identificador.",
    }
    async with motor.sesion() as db:
        assert await db.scalar(select(func.count()).select_from(Devolucion)) == 0


async def test_el_motivo_es_opcional_y_se_guarda_vacio(entorno):
    http, motor = entorno
    pedido_id = await _pedido_pagado(http)

    respuesta = await http.post(f"/v1/ordenes/{pedido_id}/retracto", json={})

    assert respuesta.status_code == 201
    (devolucion,) = await _devoluciones(motor, pedido_id)
    assert devolucion.motivo == ""


@pytest.mark.parametrize(
    ("cuerpo", "campo"),
    [({"motivo": "m" * 513}, "motivo"), ({"motivo": 12345}, "motivo")],
    ids=["motivo_largo", "motivo_no_texto"],
)
async def test_un_motivo_demasiado_largo_o_que_no_es_texto_es_400_y_el_pedido_queda_igual(
    entorno, cuerpo, campo
):
    http, motor = entorno
    pedido_id = await _pedido_pagado(http)

    respuesta = await http.post(f"/v1/ordenes/{pedido_id}/retracto", json=cuerpo)

    assert respuesta.status_code == 400
    assert respuesta.json()["error"] == "entrada_invalida"
    assert respuesta.json()["campo"] == campo
    assert "mmmmmmmm" not in respuesta.text
    assert (await _estados(motor, pedido_id))[:2] == ("pagado", ["aprobado"])
    assert await _devoluciones(motor, pedido_id) == []


# --- la ventana de 5 dias habiles (Ley 1480, art. 47) --------------------------------------------


async def test_un_retracto_un_dia_despues_de_la_entrega_se_acepta_y_registra_la_devolucion(entorno):
    """Dentro de la ventana (entregado ayer): el retracto procede y queda registrado por el total."""
    http, motor = entorno
    pedido_id = await _pedido_pagado(http)
    await _en_estado(motor, pedido_id, "entregado", entregado_hace=timedelta(days=1))

    respuesta = await _retractar(http, pedido_id, motivo="talla equivocada")

    assert respuesta.status_code == 201
    (devolucion,) = await _devoluciones(motor, pedido_id)
    assert (devolucion.motivo, devolucion.monto) == ("talla equivocada", 9000)


@pytest.mark.xfail(
    strict=True,
    reason=(
        "H-A-14: el retracto no valida la ventana de 5 dias habiles posteriores a la entrega "
        "(Ley 1480; FU-04): routers/comercio.py:760-790 acepta un pedido entregado hace 30 dias"
    ),
)
async def test_un_retracto_fuera_de_la_ventana_de_5_dias_habiles_se_rechaza(entorno):
    """Entregado hace 30 dias: el derecho de retracto caduco. Lo correcto es un 4xx y NINGUNA devolucion
    registrada; hoy el endpoint registra la devolucion por el total sin mirar `envio.entregado_en`."""
    http, motor = entorno
    pedido_id = await _pedido_pagado(http)
    await _en_estado(motor, pedido_id, "entregado", entregado_hace=timedelta(days=30))

    respuesta = await _retractar(http, pedido_id, motivo="me arrepenti un mes despues")

    assert 400 <= respuesta.status_code < 500
    assert await _devoluciones(motor, pedido_id) == []


# --- defectos del contrato del retracto ---------------------------------------------------------


@pytest.mark.xfail(
    strict=True,
    reason=(
        "H-C-06: el retracto no identifica al actor ni comprueba que sea el titular del pedido: "
        "routers/comercio.py:760-790 (sin `_pedido_del_portador`, que 63665ec si pone en "
        "pago y cancelar, :734-757) cancela y devuelve el pedido de cualquiera"
    ),
)
async def test_el_retracto_de_un_pedido_ajeno_se_rechaza(entorno):
    """Otro acudiente (con su propia sesion) pide el retracto del pedido de ACUDIENTE: debe ser
    403/404 y el pedido, el pago y las devoluciones quedan intactos."""
    http, motor = entorno
    pedido_id = await _pedido_pagado(http)

    respuesta = await http.post(
        f"/v1/ordenes/{pedido_id}/retracto",
        json={"motivo": "intruso", "usuario_id": OTRO_ACUDIENTE},
        headers={"authorization": "Bearer sesion-ficticia-de-otro-acudiente"},
    )

    assert respuesta.status_code in (401, 403, 404)
    assert (await _estados(motor, pedido_id))[:2] == ("pagado", ["aprobado"])
    assert await _devoluciones(motor, pedido_id) == []


@pytest.mark.xfail(
    strict=True,
    reason=(
        "H-A-15: cancelar por retracto no libera la reserva de inventario "
        "(modelos/inventario.py:56-60 promete liberarla al cancelar); repositorios/pedidos.py:734-737 "
        "solo actualiza el pedido y el barredor ignora pedidos no pendientes (dominio/saga.py:41-43)"
    ),
)
async def test_el_retracto_de_un_pedido_pagado_libera_su_reserva_de_inventario(entorno):
    """El pedido cancelado ya no debe retener stock. Hoy la reserva queda `activa` para siempre:
    el barredor solo recoge reservas de pedidos `pendiente_pago`."""
    http, motor = entorno
    pedido_id = await _pedido_pagado(http)
    assert (await _estados(motor, pedido_id))[2] == ["activa"]

    await _retractar(http, pedido_id)

    estado, _, reservas = await _estados(motor, pedido_id)
    assert estado == "cancelado"
    assert reservas == ["liberada"]


@pytest.mark.xfail(
    strict=True,
    reason=(
        "H-A-16: la devolucion registra el total del pedido aunque nunca se pago, contra su propio "
        "docstring ('el monto del reembolso es el total pagado'): routers/comercio.py:765 y :779"
    ),
)
async def test_la_devolucion_de_un_pedido_nunca_pagado_no_registra_dinero(entorno):
    """Sin pago aprobado no hay nada que devolver: el monto debe ser 0 (el total PAGADO)."""
    http, motor = entorno
    pedido_id = (await http.post("/v1/ordenes", json=_orden())).json()["pedido_id"]

    respuesta = await _retractar(http, pedido_id)

    assert respuesta.status_code == 201
    (devolucion,) = await _devoluciones(motor, pedido_id)
    assert devolucion.monto == 0
