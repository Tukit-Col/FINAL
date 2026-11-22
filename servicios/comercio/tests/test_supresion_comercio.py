from __future__ import annotations

import uuid
from collections.abc import AsyncIterator

import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from tukit_comercio.modelos import Base, Devolucion, Envio, LineaPedido, Pago, Pedido
from tukit_comercio.repositorios.pedidos import BANDEJA
from tukit_comercio.supresion import Supresor
from tukit_comun.bandeja import Resultado
from tukit_comun.bd import MotorServicio
from tukit_comun.mensajes import Evento
from tukit_comun.supresion import MARCA_SUPRIMIDO

TITULAR = uuid.uuid4()
OTRO = uuid.uuid4()
SOLICITUD = uuid.uuid4()


@pytest_asyncio.fixture
async def motor() -> AsyncIterator[MotorServicio]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conexion:
        await conexion.run_sync(Base.metadata.create_all)
    fabrica = async_sessionmaker(engine, expire_on_commit=False)
    yield MotorServicio(servicio="comercio", engine=engine, _fabrica=fabrica)
    await engine.dispose()


async def _pedido(motor: MotorServicio, usuario_id: uuid.UUID) -> uuid.UUID:
    pid = uuid.uuid4()
    async with motor.sesion() as db:
        db.add(Pedido(id=pid, usuario_id=usuario_id, total=45_000, hijos=1, colegios=["C"], estado="pagado"))
        await db.flush()
        db.add(
            LineaPedido(
                pedido_id=pid,
                producto_canonico_id=uuid.uuid4(),
                sku="SKU-1",
                nombre="Cuaderno",
                cantidad=2,
                precio_unitario=22_500,
            )
        )
        db.add(Pago(pedido_id=pid, referencia_wompi=f"ref-{pid}", monto=45_000, estado="aprobado"))
        db.add(
            Envio(
                pedido_id=pid,
                destinatario="Ana Perez",
                direccion="Cra 7 # 45-10",
                ciudad="Bogota",
                telefono="3001234567",
                documento_destinatario="1020304050",
                indicaciones="Porteria, preguntar por Ana",
                localidad="Chapinero",
                latitud=4.6518,
                longitud=-74.051,
            )
        )
        db.add(Devolucion(pedido_id=pid, usuario_id=usuario_id, motivo="Mi hija Sofia no lo uso", monto=1))
    return pid


def _evento(id_: int = 7) -> Evento:
    return Evento(
        id=id_,
        origen="identidad",
        tipo="titular_suprimido",
        agregado_tipo="solicitud_supresion",
        agregado_id=SOLICITUD,
        carga={"usuario_id": str(TITULAR), "solicitud_id": str(SOLICITUD)},
    )


async def test_enmascara_el_envio_y_conserva_lo_que_la_ley_obliga(motor):
    pid = await _pedido(motor, TITULAR)

    assert await Supresor(motor).manejar(_evento()) is Resultado.HECHO

    async with motor.sesion() as db:
        envio = (await db.execute(select(Envio).where(Envio.pedido_id == pid))).scalar_one()
        assert envio.destinatario == MARCA_SUPRIMIDO
        assert envio.direccion == MARCA_SUPRIMIDO
        assert envio.telefono is None
        assert envio.documento_destinatario is None
        assert envio.indicaciones is None
        assert (envio.latitud, envio.longitud) == (None, None)
        assert (envio.ciudad, envio.localidad) == ("Bogota", "Chapinero")
        devolucion = (await db.execute(select(Devolucion))).scalar_one()
        assert devolucion.motivo == MARCA_SUPRIMIDO
        assert devolucion.monto == 1
        pedido = await db.get(Pedido, pid)
        assert (pedido.total, pedido.estado, pedido.usuario_id) == (45_000, "pagado", TITULAR)
        linea = (await db.execute(select(LineaPedido))).scalar_one()
        assert (linea.nombre, linea.cantidad, linea.precio_unitario) == ("Cuaderno", 2, 22_500)
        pago = (await db.execute(select(Pago))).scalar_one()
        assert (pago.monto, pago.estado) == (45_000, "aprobado")


async def test_no_toca_los_pedidos_de_otro(motor):
    ajeno = await _pedido(motor, OTRO)

    await Supresor(motor).manejar(_evento())

    async with motor.sesion() as db:
        envio = (await db.execute(select(Envio).where(Envio.pedido_id == ajeno))).scalar_one()
        assert envio.destinatario == "Ana Perez"
        assert envio.telefono == "3001234567"


async def test_confirma_en_su_bandeja_una_sola_vez_aunque_el_evento_se_repita(motor):
    await _pedido(motor, TITULAR)
    supresor = Supresor(motor)

    assert await supresor.manejar(_evento()) is Resultado.HECHO
    assert await supresor.manejar(_evento()) is Resultado.HECHO

    async with motor.engine.connect() as conexion:
        filas = (
            await conexion.execute(select(BANDEJA).where(BANDEJA.c.tipo == "supresion_confirmada"))
        ).all()
    assert len(filas) == 1
    [fila] = filas
    assert fila.agregado_id == SOLICITUD
    assert fila.carga["servicio"] == "comercio"
    assert fila.carga["solicitud_id"] == str(SOLICITUD)
    assert "Ana" not in str(fila.carga)


async def test_confirma_aunque_el_titular_no_tenga_pedidos(motor):
    assert await Supresor(motor).manejar(_evento()) is Resultado.HECHO
    async with motor.engine.connect() as conexion:
        assert await conexion.scalar(select(BANDEJA.c.carga)) is not None


async def test_omite_lo_que_no_es_suyo_o_viene_roto(motor):
    supresor = Supresor(motor)
    otro_tipo = Evento(id=1, origen="identidad", tipo="colegio_verificado")
    roto = Evento(id=2, origen="identidad", tipo="titular_suprimido", carga={"usuario_id": "no-es-uuid"})

    assert await supresor.manejar(otro_tipo) is Resultado.OMITIR
    assert await supresor.manejar(roto) is Resultado.OMITIR
