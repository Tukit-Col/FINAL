"""La superficie de Comercio: el tablero de logistica y el detalle de un pedido.

Esta es la superficie de LECTURA que el back-office de logistica consume
(`libs/ts/tukit-contrato/src/comercio.ts`). El checkout, el pago y el webhook
de Wompi (la superficie de ESCRITURA) viven en `pedido.py` y se montan aparte.

La forma de la respuesta es la del contrato y no una traduccion suya:
`TableroComercio {resumen, pedidos[]}`, donde cada `Pedido` trae sus lineas, su
pago (o null) y su envio (o null). El `resumen` se calcula con agregados sobre
la misma base, para que la tarjeta de arriba no recuente en cada pantalla.

    python -m tukit_comercio.api            # localhost:8014
"""

from __future__ import annotations

import argparse
import uuid
from datetime import datetime
from typing import Any

from fastapi import FastAPI
from sqlalchemy import func, select
from tukit_comun.bd import crear_motor
from tukit_comun.http import ErrorDominio, crear_app

from .modelos import Base, EstadoPedido

PUERTO_POR_OMISION = 8014

PEDIDO = Base.metadata.tables["pedido"]
LINEA_PEDIDO = Base.metadata.tables["linea_pedido"]
PAGO = Base.metadata.tables["pago"]
ENVIO = Base.metadata.tables["envio"]

# Los estados que cuentan como ingreso confirmado: ya se pago, aunque todavia
# no se entregue. `entregado` incluido; `cancelado` e `incidencia` no.
_ESTADOS_CONFIRMADOS = frozenset(
    {
        EstadoPedido.PAGADO.value,
        EstadoPedido.EN_PREPARACION.value,
        EstadoPedido.DESPACHADO.value,
        EstadoPedido.EN_REPARTO.value,
        EstadoPedido.ENTREGADO.value,
    }
)

# Un pedido pagado que todavia no llega es una entrega pendiente. `entregado`
# ya llego; los previos al pago aun no cuentan.
_ESTADOS_ENTREGA_PENDIENTE = frozenset(
    {
        EstadoPedido.PAGADO.value,
        EstadoPedido.EN_PREPARACION.value,
        EstadoPedido.DESPACHADO.value,
        EstadoPedido.EN_REPARTO.value,
    }
)


async def _arrancar(app: FastAPI) -> None:
    app.state.motor = crear_motor("comercio")


async def _apagar(app: FastAPI) -> None:
    await app.state.motor.cerrar()


app = crear_app(
    titulo="Tukit Comercio",
    descripcion=(
        "Pedidos, inventario, pagos (Wompi PSE) y entrega. Superficie de lectura del "
        "back-office de logistica y superficie de checkout del acudiente."
    ),
    al_arrancar=_arrancar,
    al_apagar=_apagar,
)


def _iso(valor: datetime | None) -> str | None:
    return valor.isoformat() if valor is not None else None


def _serializar_pago(fila: Any) -> dict[str, Any] | None:
    if fila is None:
        return None
    return {
        "referencia_wompi": fila.referencia_wompi,
        "metodo": fila.metodo,
        "estado": fila.estado,
        "monto": int(fila.monto),
    }


def _serializar_envio(fila: Any) -> dict[str, Any] | None:
    if fila is None:
        return None
    return {
        "destinatario": fila.destinatario,
        "direccion": fila.direccion,
        "ciudad": fila.ciudad,
        "transportadora": fila.transportadora,
        "guia": fila.guia,
        "entrega_estimada": _iso(fila.entrega_estimada),
        "entregado_en": _iso(fila.entregado_en),
    }


def _serializar_linea(fila: Any) -> dict[str, Any]:
    return {
        "sku": fila.sku,
        "nombre": fila.nombre,
        "cantidad": int(fila.cantidad),
        "precio_unitario": int(fila.precio_unitario),
    }


async def _pedido_completo(conexion: Any, fila_pedido: Any) -> dict[str, Any]:
    """Un `Pedido` del contrato: con sus lineas, su pago y su envio anidados.

    Toma la fila del pedido ya leida para no repetir la consulta cuando viene
    del listado. El pago que se muestra es el ultimo intento; el envio es uno a
    uno con el pedido.
    """
    lineas = [
        _serializar_linea(f)
        for f in await conexion.execute(
            select(LINEA_PEDIDO).where(LINEA_PEDIDO.c.pedido_id == fila_pedido.id)
        )
    ]
    pago = (
        await conexion.execute(
            select(PAGO)
            .where(PAGO.c.pedido_id == fila_pedido.id)
            .order_by(PAGO.c.creado_en.desc())
            .limit(1)
        )
    ).one_or_none()
    envio = (
        await conexion.execute(select(ENVIO).where(ENVIO.c.pedido_id == fila_pedido.id))
    ).one_or_none()

    return {
        "pedido_id": str(fila_pedido.id),
        "trabajo_id": str(fila_pedido.trabajo_id) if fila_pedido.trabajo_id is not None else None,
        "estado": fila_pedido.estado,
        "creado_en": _iso(fila_pedido.creado_en),
        "total": int(fila_pedido.total),
        "hijos": int(fila_pedido.hijos),
        "colegios": list(fila_pedido.colegios or []),
        "lineas": lineas,
        "pago": _serializar_pago(pago),
        "envio": _serializar_envio(envio),
    }


async def _resumen(conexion: Any) -> dict[str, Any]:
    """El consolidado que pinta las tarjetas de arriba sin recontar por pantalla."""
    por_estado = {e.value: 0 for e in EstadoPedido}
    total_pedidos = 0
    ingresos = 0
    entregas_pendientes = 0

    filas = await conexion.execute(
        select(PEDIDO.c.estado, func.count().label("n"), func.sum(PEDIDO.c.total).label("suma")).group_by(
            PEDIDO.c.estado
        )
    )
    for f in filas:
        n = int(f.n)
        suma = int(f.suma or 0)
        por_estado[f.estado] = n
        total_pedidos += n
        if f.estado in _ESTADOS_CONFIRMADOS:
            ingresos += suma
        if f.estado in _ESTADOS_ENTREGA_PENDIENTE:
            entregas_pendientes += n

    return {
        "pedidos_totales": total_pedidos,
        "por_estado": por_estado,
        "ingresos_confirmados": ingresos,
        "entregas_pendientes": entregas_pendientes,
    }


@app.get("/v1/comercio/pedidos", tags=["comercio"], summary="Tablero de logistica: resumen + pedidos")
async def tablero() -> dict[str, Any]:
    async with app.state.motor.sesion() as db:
        conexion = await db.connection()
        resumen = await _resumen(conexion)
        pedidos = [
            await _pedido_completo(conexion, f)
            for f in await conexion.execute(select(PEDIDO).order_by(PEDIDO.c.creado_en.desc()))
        ]
    return {"resumen": resumen, "pedidos": pedidos}


@app.get("/v1/comercio/pedidos/{pedido_id}", tags=["comercio"], summary="Un pedido, con lineas, pago y envio")
async def ver_pedido(pedido_id: uuid.UUID) -> dict[str, Any]:
    async with app.state.motor.sesion() as db:
        conexion = await db.connection()
        fila = (
            await conexion.execute(select(PEDIDO).where(PEDIDO.c.id == pedido_id))
        ).one_or_none()
        if fila is None:
            raise ErrorDominio(
                "pedido_no_existe", "No hay ningun pedido con ese identificador.", estado=404
            )
        return await _pedido_completo(conexion, fila)


def main(argv: list[str] | None = None) -> int:
    analizador = argparse.ArgumentParser(description="Levanta la API de Comercio.")
    analizador.add_argument("--puerto", type=int, default=PUERTO_POR_OMISION)
    analizador.add_argument("--host", default="127.0.0.1")
    argumentos = analizador.parse_args(argv)

    import uvicorn

    uvicorn.run(app, host=argumentos.host, port=argumentos.puerto, log_level="info")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
