from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime

import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from tukit_comun.bandeja import Resultado
from tukit_comun.bd import MotorServicio
from tukit_comun.mensajes import Evento
from tukit_comun.supresion import MARCA_SUPRIMIDO
from tukit_operacion.modelos import Base, Caso, EventoCaso
from tukit_operacion.repositorios.casos import BANDEJA
from tukit_operacion.supresion import Supresor

TITULAR = uuid.uuid4()
OTRO = uuid.uuid4()
SOLICITUD = uuid.uuid4()
ABIERTO = datetime(2026, 10, 1, 9, 0, tzinfo=UTC)


@pytest_asyncio.fixture
async def motor() -> AsyncIterator[MotorServicio]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conexion:
        await conexion.run_sync(Base.metadata.create_all)
    fabrica = async_sessionmaker(engine, expire_on_commit=False)
    yield MotorServicio(servicio="operacion", engine=engine, _fabrica=fabrica)
    await engine.dispose()


async def _caso(motor: MotorServicio, usuario_id: uuid.UUID) -> uuid.UUID:
    cid = uuid.uuid4()
    async with motor.sesion() as db:
        db.add(
            Caso(
                id=cid,
                origen="acudiente",
                categoria="queja",
                estado="resuelto",
                asunto="No llego el kit de Sofia",
                descripcion="Vivo en la Cra 7 # 45-10, mi celular es 3001234567",
                usuario_id=usuario_id,
                abierto_en=ABIERTO,
                resuelto_en=ABIERTO,
            )
        )
        await db.flush()
        db.add(EventoCaso(caso_id=cid, tipo="comentario_acudiente", datos={"texto": "Soy Ana Perez"}))
        db.add(EventoCaso(caso_id=cid, tipo="respuesta", datos={"texto": "Hola Ana, ya salio"}))
        db.add(EventoCaso(caso_id=cid, tipo="estado", datos={"desde": "abierto", "hacia": "resuelto"}))
    return cid


def _evento(id_: int = 7) -> Evento:
    return Evento(
        id=id_,
        origen="identidad",
        tipo="titular_suprimido",
        agregado_tipo="solicitud_supresion",
        agregado_id=SOLICITUD,
        carga={"usuario_id": str(TITULAR), "solicitud_id": str(SOLICITUD)},
    )


async def test_redacta_el_texto_libre_y_conserva_estado_y_fechas(motor):
    cid = await _caso(motor, TITULAR)

    assert await Supresor(motor).manejar(_evento()) is Resultado.HECHO

    async with motor.sesion() as db:
        caso = await db.get(Caso, cid)
        assert caso.asunto == MARCA_SUPRIMIDO
        assert caso.descripcion == MARCA_SUPRIMIDO
        assert (caso.estado, caso.categoria, caso.origen) == ("resuelto", "queja", "acudiente")
        assert caso.abierto_en.replace(tzinfo=UTC) == ABIERTO
        assert caso.resuelto_en is not None
        eventos = {e.tipo: e.datos for e in (await db.execute(select(EventoCaso))).scalars()}
        assert eventos["comentario_acudiente"] == {"texto": MARCA_SUPRIMIDO}
        assert eventos["respuesta"] == {"texto": MARCA_SUPRIMIDO}
        assert eventos["estado"] == {"desde": "abierto", "hacia": "resuelto"}


async def test_no_toca_los_casos_de_otro(motor):
    ajeno = await _caso(motor, OTRO)

    await Supresor(motor).manejar(_evento())

    async with motor.sesion() as db:
        caso = await db.get(Caso, ajeno)
        assert caso.asunto == "No llego el kit de Sofia"
        textos = [e.datos.get("texto") for e in (await db.execute(select(EventoCaso))).scalars()]
        assert "Soy Ana Perez" in textos


async def test_confirma_una_sola_vez_aunque_el_evento_se_repita(motor):
    await _caso(motor, TITULAR)
    supresor = Supresor(motor)

    assert await supresor.manejar(_evento()) is Resultado.HECHO
    assert await supresor.manejar(_evento()) is Resultado.HECHO

    async with motor.engine.connect() as conexion:
        filas = (
            await conexion.execute(select(BANDEJA).where(BANDEJA.c.tipo == "supresion_confirmada"))
        ).all()
    assert len(filas) == 1
    assert filas[0].agregado_id == SOLICITUD
    assert filas[0].carga["servicio"] == "operacion"
    async with motor.sesion() as db:
        caso = (await db.execute(select(Caso))).scalar_one()
        assert caso.descripcion == MARCA_SUPRIMIDO


async def test_omite_lo_que_no_es_suyo_o_viene_roto(motor):
    supresor = Supresor(motor)
    assert await supresor.manejar(Evento(id=1, origen="identidad", tipo="pedido_pagado")) is Resultado.OMITIR
    roto = Evento(id=2, origen="identidad", tipo="titular_suprimido", carga={})
    assert await supresor.manejar(roto) is Resultado.OMITIR
