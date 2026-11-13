"""Alertas de pedido: pagado sin avanzar, pago atascado, incidencia."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from conftest import crear_pedido
from sqlalchemy import insert
from tukit_comercio.dominio.alertas import alertas_de_pedido
from tukit_comercio.modelos import Base
from tukit_comercio.repositorios.pedidos import RepoPedidos

AHORA = datetime(2026, 11, 12, 12, 0, tzinfo=UTC)
PAGO = Base.metadata.tables["pago"]
HISTORIAL = Base.metadata.tables["historial_pedido"]


def _alertas(estado, *, desde=None, pago=None, pago_hace=None, creado_hace=timedelta(hours=2)):
    return alertas_de_pedido(
        estado=estado,
        estado_desde=AHORA - (desde or timedelta(0)),
        pago_estado=pago,
        pago_iniciado_en=AHORA - pago_hace if pago_hace is not None else None,
        creado_en=AHORA - creado_hace,
        ahora=AHORA,
    )


def test_pagado_mas_de_24h_sin_avanzar():
    assert _alertas("pagado", desde=timedelta(hours=25)) == ("pagado_sin_avanzar",)
    assert _alertas("pagado", desde=timedelta(hours=23)) == ()


def test_pago_atascado_solo_con_pedido_vigente():
    atascado = _alertas("pendiente_pago", pago="iniciado", pago_hace=timedelta(minutes=31))
    assert atascado == ("pago_atascado",)
    assert _alertas("pendiente_pago", pago="iniciado", pago_hace=timedelta(minutes=10)) == ()
    vencido = _alertas(
        "pendiente_pago", pago="iniciado", pago_hace=timedelta(hours=25), creado_hace=timedelta(hours=25)
    )
    assert vencido == ()
    assert _alertas("pendiente_pago", pago="rechazado", pago_hace=timedelta(minutes=40)) == ()
    assert _alertas("pendiente_pago") == ()


def test_incidencia_y_terminales():
    assert _alertas("incidencia") == ("incidencia_abierta",)
    for estado in ("entregado", "cancelado", "en_preparacion", "despachado"):
        assert _alertas(estado, desde=timedelta(days=9)) == ()


async def test_resumen_y_tablero_marcan_los_pedidos_correctos(db):
    viejo = await crear_pedido(db, estado="pagado")  # pagado hace 30 h (via pago aprobado)
    reciente = await crear_pedido(db, estado="pagado")
    atascado = await crear_pedido(db, estado="pendiente_pago")
    incidencia = await crear_pedido(db, estado="incidencia")
    await crear_pedido(db, estado="entregado")
    conexion = await db.connection()
    hace = lambda **k: datetime.now(UTC) - timedelta(**k)  # noqa: E731
    for pedido, estado, edad in (
        (viejo, "aprobado", timedelta(hours=30)),
        (reciente, "aprobado", timedelta(hours=1)),
        (atascado, "iniciado", timedelta(minutes=45)),
    ):
        await conexion.execute(
            insert(PAGO).values(
                pedido_id=pedido.id,
                referencia_wompi=f"ref-{pedido.id}",
                estado=estado,
                monto=1000,
                creado_en=hace(**{"seconds": edad.total_seconds()}),
                actualizado_en=hace(**{"seconds": edad.total_seconds()}),
            )
        )
    # El pedido viejo/atascado se creo hace poco o mucho: la ventana de pago cuenta desde creado_en.
    repo = RepoPedidos(conexion)
    resumen = await repo.resumen()
    assert resumen["alertas"] == {"pagado_sin_avanzar": 1, "pago_atascado": 1, "incidencia_abierta": 1}
    filas = await repo.listar_todos()
    por_id = {p["pedido_id"]: p for p in await repo.pedidos_completos(filas, con_alertas=True)}
    assert por_id[str(viejo.id)]["alertas"] == ["pagado_sin_avanzar"]
    assert por_id[str(reciente.id)]["alertas"] == []
    assert por_id[str(atascado.id)]["alertas"] == ["pago_atascado"]
    assert por_id[str(incidencia.id)]["alertas"] == ["incidencia_abierta"]
    sin = await repo.pedidos_completos(filas)
    assert all("alertas" not in p for p in sin)
