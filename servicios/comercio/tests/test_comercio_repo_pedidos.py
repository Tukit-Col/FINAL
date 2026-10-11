"""NFR-MAN-01: el repositorio de pedidos contra su base: unidad de trabajo, proyecciones y candados.

`RepoPedidos` es todo el SQL de Comercio detras de nombres de metodo (ADR 0019). Los tests de rutas lo
ejercen de paso; aqui se llama DIRECTO, con una conexion SQLite, para fijar lo que el router da por
sentado y que, si cambia en silencio, corrompe datos sin que ninguna ruta lo note:

- `insertar_orden` es todo-o-nada: si una linea es invalida no queda pedido, envio ni reserva a medias.
- Las lecturas en lote (`pedidos_completos`) devuelven lo mismo que la de un solo pedido, y el resumen
  suma ingreso solo de lo confirmado.
- El candado de idempotencia del webhook tiene respaldo duro: el mismo evento dos veces es una
  violacion de unicidad, no dos filas.
- `avanzar_despacho` escribe solo lo que llega (desde e82d03c: repartidor y fecha estimada, y solo
  si el pedido SIGUE en el estado de partida); `marcar_pago_reembolsado` toca solo el pago APROBADO
  del pedido pedido; el aviso `pedido_pagado` hereda la correlacion de la peticion y solo si existe.

Sin red: SQLite en memoria; las fechas se fijan a mano.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any

import pytest
import pytest_asyncio
from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError, NoResultFound
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine, create_async_engine
from tukit_comercio.modelos import Base
from tukit_comercio.repositorios import RepoPedidos
from tukit_comercio.repositorios.pedidos import (
    BANDEJA,
    DEVOLUCION,
    ENVIO,
    EVENTO_PROCESADO,
    LINEA_PEDIDO,
    PAGO,
    PEDIDO,
    RESERVA,
)
from tukit_comun.http import fijar_correlacion, reset_correlacion

pytestmark = pytest.mark.nfr("NFR-MAN-01")

AHORA = datetime(2026, 3, 1, 12, 0, tzinfo=UTC)
USUARIO = uuid.UUID("22222222-2222-5222-8222-222222222222")
OTRO_USUARIO = uuid.UUID("33333333-3333-5333-8333-333333333333")


@pytest_asyncio.fixture
async def engine() -> AsyncIterator[AsyncEngine]:
    motor = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with motor.begin() as conexion:
        await conexion.run_sync(Base.metadata.create_all)
    yield motor
    await motor.dispose()


@pytest_asyncio.fixture
async def repo(engine: AsyncEngine) -> AsyncIterator[RepoPedidos]:
    async with engine.begin() as conexion:
        yield RepoPedidos(conexion)


def _entrega(**extra: Any) -> SimpleNamespace:
    """La entrega "legada": solo los tres campos obligatorios, sin los extendidos."""
    return SimpleNamespace(
        destinatario="Acudiente Ficticio", direccion="Calle 1 # 2-3", ciudad="Bogota", **extra
    )


def _linea(sku: str = "TK-C001-ECO", precio: int = 4500, cantidad: int = 2, **extra: Any) -> dict[str, Any]:
    return {
        "matricula_id": None,
        "producto_id": uuid.uuid5(uuid.NAMESPACE_OID, sku),
        "sku": sku,
        "nombre": f"Util {sku}",
        "cantidad": cantidad,
        "precio_unitario": precio,
        **extra,
    }


async def _orden(
    repo: RepoPedidos,
    *,
    usuario: uuid.UUID = USUARIO,
    minutos: int = 0,
    trabajo_id: uuid.UUID | None = None,
    lineas: list[dict[str, Any]] | None = None,
    total: int = 9000,
    entrega: Any = None,
) -> uuid.UUID:
    pedido_id = uuid.uuid4()
    await repo.insertar_orden(
        pedido_id=pedido_id,
        usuario_id=usuario,
        trabajo_id=trabajo_id,
        total=total,
        hijos=1,
        colegios=["Colegio Ficticio"],
        ahora=AHORA + timedelta(minutes=minutos),
        lineas=lineas or [_linea()],
        entrega=entrega or _entrega(),
    )
    return pedido_id


async def _estado(repo: RepoPedidos, pedido_id: uuid.UUID, estado: str) -> None:
    await repo.conexion.execute(update(PEDIDO).where(PEDIDO.c.id == pedido_id).values(estado=estado))


async def _pago(repo: RepoPedidos, pedido_id: uuid.UUID, referencia: str, *, minutos: int = 0) -> uuid.UUID:
    pago_id = uuid.uuid4()
    await repo.registrar_pago_iniciado(
        pago_id=pago_id,
        pedido_id=pedido_id,
        referencia_wompi=referencia,
        transaccion_wompi=f"txn-{referencia}",
        metodo="pse",
        monto=9000,
    )
    await repo.conexion.execute(
        update(PAGO).where(PAGO.c.id == pago_id).values(creado_en=AHORA + timedelta(minutes=minutos))
    )
    return pago_id


async def _contar(conexion: AsyncConnection, tabla: Any) -> int:
    return int(await conexion.scalar(select(func.count()).select_from(tabla)))


# --- insertar_orden: la unidad de trabajo del checkout ------------------------------------------


async def test_insertar_orden_crea_pedido_lineas_reservas_y_envio_en_estado_pendiente(repo):
    pedido_id = uuid.uuid4()
    trabajo_id = uuid.uuid4()
    lineas = [_linea("TK-C001-ECO", 4500, 2), _linea("TK-L002-LAP", 1200, 3)]

    fila = await repo.insertar_orden(
        pedido_id=pedido_id,
        usuario_id=USUARIO,
        trabajo_id=trabajo_id,
        total=12_600,
        hijos=2,
        colegios=["Colegio Ficticio", "Otro Colegio Ficticio"],
        ahora=AHORA,
        lineas=lineas,
        entrega=_entrega(telefono="3000000000", indicaciones="Dejar en porteria"),
    )

    assert (fila.id, fila.usuario_id, fila.trabajo_id) == (pedido_id, USUARIO, trabajo_id)
    assert (fila.estado, fila.total, fila.hijos) == ("pendiente_pago", 12_600, 2)
    assert list(fila.colegios) == ["Colegio Ficticio", "Otro Colegio Ficticio"]
    guardadas = list(await repo.conexion.execute(select(LINEA_PEDIDO).order_by(LINEA_PEDIDO.c.sku)))
    assert [(g.sku, g.cantidad, g.precio_unitario) for g in guardadas] == [
        ("TK-C001-ECO", 2, 4500),
        ("TK-L002-LAP", 3, 1200),
    ]
    reservas = list(await repo.conexion.execute(select(RESERVA).order_by(RESERVA.c.cantidad)))
    assert [(r.cantidad, r.estado, r.pedido_id) for r in reservas] == [
        (2, "activa", pedido_id),
        (3, "activa", pedido_id),
    ]
    assert {r.producto_canonico_id for r in reservas} == {lineas[0]["producto_id"], lineas[1]["producto_id"]}
    envio = (await repo.conexion.execute(select(ENVIO))).one()
    # La direccion queda COPIADA (ADR 0015); los extendidos ausentes del objeto legado son None.
    assert (envio.destinatario, envio.direccion, envio.ciudad) == (
        "Acudiente Ficticio",
        "Calle 1 # 2-3",
        "Bogota",
    )
    assert (envio.telefono, envio.indicaciones) == ("3000000000", "Dejar en porteria")
    assert (envio.departamento, envio.documento_destinatario) == (None, None)


async def test_una_linea_invalida_deja_la_orden_sin_rastro(engine):
    """Todo-o-nada: la segunda linea viola el CHECK de cantidad; la unidad de trabajo se revierte y no
    quedan ni el pedido, ni la primera linea, ni su reserva, ni el envio."""
    pedido_id = uuid.uuid4()
    with pytest.raises(IntegrityError):
        async with engine.begin() as conexion:
            await RepoPedidos(conexion).insertar_orden(
                pedido_id=pedido_id,
                usuario_id=USUARIO,
                trabajo_id=None,
                total=9000,
                hijos=1,
                colegios=[],
                ahora=AHORA,
                lineas=[_linea("TK-C001-ECO"), _linea("TK-MALA", cantidad=0)],
                entrega=_entrega(),
            )

    async with engine.connect() as conexion:
        for tabla in (PEDIDO, LINEA_PEDIDO, RESERVA, ENVIO):
            assert await _contar(conexion, tabla) == 0, tabla.name


# --- lecturas -----------------------------------------------------------------------------------


async def test_pedidos_completos_sin_filas_no_consulta_nada(repo):
    assert await repo.pedidos_completos([]) == []


async def test_el_lote_agrupa_lineas_pago_y_envio_igual_que_la_lectura_de_un_pedido(repo):
    """Dos pedidos, uno con dos lineas y dos intentos de pago: la lectura en lote (3 consultas, sin
    N+1) y la de un solo pedido dan exactamente la misma proyeccion."""
    uno = await _orden(repo, minutos=0, lineas=[_linea("A", 100, 1), _linea("B", 200, 2)], total=500)
    dos = await _orden(repo, minutos=10, trabajo_id=uuid.uuid4())
    await _pago(repo, uno, "ref-vieja", minutos=1)
    await _pago(repo, uno, "ref-nueva", minutos=2)
    await repo.actualizar_estado_pago(
        pago_id=(await repo.pago_por_referencia("ref-vieja")).id, estado="rechazado", transaccion_wompi="t"
    )

    filas = await repo.listar_todos()
    en_lote = await repo.pedidos_completos(filas)
    uno_a_uno = [await repo.pedido_completo(fila) for fila in filas]

    assert [p["pedido_id"] for p in en_lote] == [str(dos), str(uno)]  # el mas reciente primero
    assert en_lote == uno_a_uno
    del_uno = next(p for p in en_lote if p["pedido_id"] == str(uno))
    assert sorted(item["sku"] for item in del_uno["lineas"]) == ["A", "B"]
    assert del_uno["pago"]["referencia_wompi"] == "ref-nueva"
    assert next(p for p in en_lote if p["pedido_id"] == str(dos))["pago"] is None


async def test_el_resumen_suma_ingreso_solo_de_lo_confirmado_y_cuenta_pendientes_de_entrega(repo):
    for minutos, (estado, total) in enumerate(
        [("pendiente_pago", 100), ("pagado", 200), ("pagado", 300), ("despachado", 400), ("cancelado", 800)]
    ):
        pedido_id = await _orden(repo, minutos=minutos, total=total)
        await _estado(repo, pedido_id, estado)

    resumen = await repo.resumen()

    assert resumen["pedidos_totales"] == 5
    assert resumen["por_estado"]["pagado"] == 2
    assert resumen["por_estado"]["en_reparto"] == 0
    assert resumen["ingresos_confirmados"] == 200 + 300 + 400
    assert resumen["entregas_pendientes"] == 3


async def test_listar_de_usuario_filtra_y_ordena_y_obtener_devuelve_none_si_no_existe(repo):
    primero = await _orden(repo, minutos=0)
    ajeno = await _orden(repo, minutos=5, usuario=OTRO_USUARIO)
    ultimo = await _orden(repo, minutos=9)

    suyos = await repo.listar_de_usuario(USUARIO)

    assert [f.id for f in suyos] == [ultimo, primero]
    assert [f.id for f in await repo.listar_de_usuario(OTRO_USUARIO)] == [ajeno]
    assert await repo.listar_de_usuario(uuid.uuid4()) == []
    assert (await repo.obtener(ajeno)).usuario_id == OTRO_USUARIO
    assert await repo.obtener(uuid.uuid4()) is None


async def test_pagados_con_trabajo_devuelve_solo_identificadores_de_confirmados_con_trabajo(repo):
    trabajo = uuid.uuid4()
    confirmado = await _orden(repo, trabajo_id=trabajo)
    await _estado(repo, confirmado, "en_preparacion")
    sin_trabajo = await _orden(repo)
    await _estado(repo, sin_trabajo, "pagado")
    sin_pagar = await _orden(repo, trabajo_id=uuid.uuid4())
    cancelado = await _orden(repo, trabajo_id=uuid.uuid4())
    await _estado(repo, cancelado, "cancelado")

    filas = await repo.pagados_con_trabajo()

    assert [(f.trabajo_id, f.usuario_id, f.estado) for f in filas] == [(trabajo, USUARIO, "en_preparacion")]
    assert {sin_pagar, cancelado} <= {f.id for f in await repo.listar_todos()}


# --- pagos y webhook ----------------------------------------------------------------------------


async def test_contar_pagos_numera_los_intentos_de_un_pedido_y_no_mezcla_pedidos(repo):
    uno, dos = await _orden(repo), await _orden(repo)
    assert await repo.contar_pagos_pedido(uno) == 0

    await _pago(repo, uno, "ref-1")
    await _pago(repo, uno, "ref-2")
    await _pago(repo, dos, "ref-3")

    assert (await repo.contar_pagos_pedido(uno), await repo.contar_pagos_pedido(dos)) == (2, 1)


async def test_registrar_pago_guarda_solo_ids_monto_y_estado_inicial(repo):
    pedido_id = await _orden(repo)

    pago_id = await _pago(repo, pedido_id, "ref-1")

    fila = await repo.pago_por_referencia("ref-1")
    assert (fila.id, fila.pedido_id, fila.transaccion_wompi) == (pago_id, pedido_id, "txn-ref-1")
    assert (fila.metodo, fila.estado, fila.monto) == ("pse", "iniciado", 9000)
    assert await repo.pago_por_referencia("ref-que-no-existe") is None
    # SG-03: ninguna columna de pago guarda datos de medio, solo id, referencia, metodo, estado y monto.
    assert set(PAGO.c.keys()) == {
        "id",
        "pedido_id",
        "referencia_wompi",
        "transaccion_wompi",
        "metodo",
        "estado",
        "monto",
        "creado_en",
        "actualizado_en",
    }


async def test_la_referencia_de_un_pago_es_unica(repo):
    pedido_id = await _orden(repo)
    await _pago(repo, pedido_id, "ref-repetida")

    with pytest.raises(IntegrityError):
        await _pago(repo, pedido_id, "ref-repetida")


async def test_el_candado_de_idempotencia_detecta_el_evento_y_su_respaldo_duro_es_la_unicidad(repo):
    assert await repo.evento_ya_procesado("evt-1") is False

    await repo.marcar_evento_procesado("evt-1")

    assert await repo.evento_ya_procesado("evt-1") is True
    assert await repo.evento_ya_procesado("evt-2") is False
    with pytest.raises(IntegrityError):  # dos entregas simultaneas: la segunda choca con el unique
        await repo.marcar_evento_procesado("evt-1")
    assert await _contar(repo.conexion, EVENTO_PROCESADO) == 1  # una sola fila: la repetida no entro


async def test_actualizar_estado_pago_cambia_estado_y_transaccion_solo_de_ese_pago(repo):
    pedido_id = await _orden(repo)
    objetivo = await _pago(repo, pedido_id, "ref-1")
    await _pago(repo, pedido_id, "ref-2")

    await repo.actualizar_estado_pago(pago_id=objetivo, estado="aprobado", transaccion_wompi="txn-nueva")

    assert (await repo.pago_por_referencia("ref-1")).estado == "aprobado"
    assert (await repo.pago_por_referencia("ref-1")).transaccion_wompi == "txn-nueva"
    assert (await repo.pago_por_referencia("ref-2")).estado == "iniciado"


async def test_pedido_de_y_transicionar_pedido(repo):
    pedido_id = await _orden(repo)
    otro = await _orden(repo)

    await repo.transicionar_pedido(pedido_id=pedido_id, destino="pagado")

    assert (await repo.pedido_de(pedido_id)).estado == "pagado"
    assert (await repo.pedido_de(otro)).estado == "pendiente_pago"
    with pytest.raises(NoResultFound):
        await repo.pedido_de(uuid.uuid4())


# --- avanzar el despacho ------------------------------------------------------------------------


async def _envio(repo: RepoPedidos, pedido_id: uuid.UUID) -> Any:
    return (await repo.conexion.execute(select(ENVIO).where(ENVIO.c.pedido_id == pedido_id))).one()


async def test_avanzar_despacho_escribe_solo_los_campos_que_llegan(repo):
    """Desde e82d03c el despacho es con reparto propio: el envio guarda el repartidor (nombre y
    celular) y la fecha estimada en lugar de transportadora y guia, que el repositorio ya no toca."""
    pedido_id = await _orden(repo)
    await _estado(repo, pedido_id, "en_preparacion")
    estimada = AHORA + timedelta(days=3)

    assert await repo.avanzar_despacho(
        pedido_id=pedido_id,
        desde="en_preparacion",
        destino="despachado",
        repartidor_nombre="Repartidor Ficticio",
        repartidor_celular=None,
        entrega_estimada=None,
    )
    parcial = await _envio(repo, pedido_id)
    assert (parcial.repartidor_nombre, parcial.repartidor_celular, parcial.entrega_estimada) == (
        "Repartidor Ficticio",
        None,
        None,
    )

    assert await repo.avanzar_despacho(
        pedido_id=pedido_id,
        desde="despachado",
        destino="en_reparto",
        repartidor_nombre=None,
        repartidor_celular="3000000000",
        entrega_estimada=estimada,
    )
    completo = await _envio(repo, pedido_id)
    assert (completo.repartidor_nombre, completo.repartidor_celular) == (
        "Repartidor Ficticio",
        "3000000000",
    )  # lo anterior no se pierde
    assert (completo.transportadora, completo.guia) == (None, None)
    assert completo.entrega_estimada.replace(tzinfo=UTC) == estimada
    assert completo.entregado_en is None
    assert (await repo.pedido_de(pedido_id)).estado == "en_reparto"


async def test_avanzar_a_entregado_marca_la_hora_de_entrega_con_el_reloj_real(repo):
    pedido_id = await _orden(repo)
    await _estado(repo, pedido_id, "en_reparto")
    antes = datetime.now(UTC)

    assert await repo.avanzar_despacho(
        pedido_id=pedido_id,
        desde="en_reparto",
        destino="entregado",
        repartidor_nombre=None,
        repartidor_celular=None,
        entrega_estimada=None,
    )

    entregado = (await _envio(repo, pedido_id)).entregado_en.replace(tzinfo=UTC)
    assert antes <= entregado <= datetime.now(UTC)


async def test_avanzar_sin_datos_de_envio_solo_cambia_el_estado_del_pedido(repo):
    pedido_id = await _orden(repo)
    await _estado(repo, pedido_id, "pagado")
    antes = await _envio(repo, pedido_id)

    assert await repo.avanzar_despacho(
        pedido_id=pedido_id,
        desde="pagado",
        destino="en_preparacion",
        repartidor_nombre=None,
        repartidor_celular=None,
        entrega_estimada=None,
    )

    assert (await repo.pedido_de(pedido_id)).estado == "en_preparacion"
    assert await _envio(repo, pedido_id) == antes


async def test_avanzar_desde_un_estado_que_ya_cambio_no_mueve_el_pedido_ni_el_envio(repo):
    """La guarda de e82d03c contra dos operadores a la vez: si el pedido ya no esta en `desde` (el
    estado que el router leyo y valido) devuelve `False` y no escribe nada; el router responde 409."""
    pedido_id = await _orden(repo)
    await _estado(repo, pedido_id, "despachado")
    antes = await _envio(repo, pedido_id)

    movido = await repo.avanzar_despacho(
        pedido_id=pedido_id,
        desde="en_preparacion",
        destino="despachado",
        repartidor_nombre="Repartidor Ficticio",
        repartidor_celular="3000000000",
        entrega_estimada=AHORA,
    )

    assert movido is False
    assert (await repo.pedido_de(pedido_id)).estado == "despachado"
    assert await _envio(repo, pedido_id) == antes


# --- bandeja de salida (outbox) -----------------------------------------------------------------


async def test_el_aviso_pedido_pagado_hereda_la_correlacion_de_la_peticion_si_existe(repo):
    pedido_id = await _orden(repo, total=9000)
    pedido = await repo.pedido_de(pedido_id)

    ficha = fijar_correlacion("cid-ficticio-0042")
    try:
        await repo.encolar_pedido_pagado(pedido)
    finally:
        reset_correlacion(ficha)
    await repo.encolar_pedido_pagado(pedido)  # sin peticion en curso: no se inventa un id

    con, sin = list(await repo.conexion.execute(select(BANDEJA).order_by(BANDEJA.c.id)))
    base = {"pedido_id": str(pedido_id), "usuario_id": str(USUARIO), "total": 9000}
    assert (con.tipo, con.agregado_tipo, con.agregado_id) == ("pedido_pagado", "pedido", pedido_id)
    assert con.carga == {**base, "correlacion_id": "cid-ficticio-0042"}
    assert sin.carga == base
    assert con.publicado_en is None


# --- retracto -----------------------------------------------------------------------------------


async def test_registrar_devolucion_guarda_titular_motivo_y_monto(repo):
    pedido_id = await _orden(repo)
    devolucion_id = uuid.uuid4()

    await repo.registrar_devolucion(
        devolucion_id=devolucion_id,
        pedido_id=pedido_id,
        usuario_id=USUARIO,
        motivo="talla equivocada",
        monto=9000,
    )

    fila = (await repo.conexion.execute(select(DEVOLUCION))).one()
    assert (fila.id, fila.pedido_id, fila.usuario_id) == (devolucion_id, pedido_id, USUARIO)
    assert (fila.motivo, fila.monto) == ("talla equivocada", 9000)


async def test_cancelar_pedido_solo_cambia_el_pedido_indicado_y_no_toca_pagos_ni_reservas(repo):
    objetivo, otro = await _orden(repo), await _orden(repo)
    await _pago(repo, objetivo, "ref-1")

    await repo.cancelar_pedido(objetivo)

    assert (await repo.pedido_de(objetivo)).estado == "cancelado"
    assert (await repo.pedido_de(otro)).estado == "pendiente_pago"
    assert (await repo.pago_por_referencia("ref-1")).estado == "iniciado"
    estados_reserva = list(await repo.conexion.scalars(select(RESERVA.c.estado)))
    assert estados_reserva == ["activa", "activa"]  # cancelar no libera la reserva (ver test del retracto)


async def test_marcar_pago_reembolsado_toca_solo_el_pago_aprobado_del_pedido(repo):
    objetivo, otro = await _orden(repo), await _orden(repo)
    aprobado = await _pago(repo, objetivo, "ref-aprobado")
    rechazado = await _pago(repo, objetivo, "ref-rechazado")
    ajeno = await _pago(repo, otro, "ref-ajeno")
    for pago_id, estado in ((aprobado, "aprobado"), (rechazado, "rechazado"), (ajeno, "aprobado")):
        await repo.actualizar_estado_pago(pago_id=pago_id, estado=estado, transaccion_wompi=None)

    await repo.marcar_pago_reembolsado(objetivo)

    assert (await repo.pago_por_referencia("ref-aprobado")).estado == "reembolsado"
    assert (await repo.pago_por_referencia("ref-rechazado")).estado == "rechazado"
    assert (await repo.pago_por_referencia("ref-ajeno")).estado == "aprobado"
