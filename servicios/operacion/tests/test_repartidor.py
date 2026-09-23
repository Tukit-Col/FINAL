"""El repartidor: la mitad de ENTREGA que faltaba (§10 del contrato).

Se prueba con dos bases SQLite en memoria: la de Operacion (donde nace la
notificacion) y una de origen que imita la bandeja de Inteligencia/Comercio. No
se levanta Postgres ni se sale a la red: el `Notificador` es el falso, que
registra lo enviado, y el cliente de Identidad es un doble que devuelve un
contacto fijo.

Lo que se defiende es lo que el §10 promete y lo que el manifiesto exige:

- Un evento no publicado produce EXACTAMENTE una notificacion y se marca
  publicado; una segunda pasada no reprocesa (idempotencia por `publicado_en`).
- El destinatario de `kits_publicados` sale de `trabajo_pipeline.usuario_id`, no
  de la carga; el de `pedido_pagado` sale de la carga.
- La notificacion guardada y su contenido NO llevan correo ni celular: el
  contacto se resuelve al vuelo y se descarta (Ley 1581, deuda del manifiesto).
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator

import pytest_asyncio
from sqlalchemy import (
    BigInteger,
    Column,
    DateTime,
    Integer,
    MetaData,
    String,
    Table,
    Uuid,
    insert,
    select,
)
from sqlalchemy.ext.asyncio import create_async_engine
from tukit_comun.bd import MotorServicio
from tukit_operacion.modelos import Base, Texto
from tukit_operacion.notificador import NotificadorFalso
from tukit_operacion.repartidor import NOTIFICACION, Repartidor

USUARIO = uuid.UUID("22222222-2222-5222-8222-222222222222")
CORREO = "ana@ejemplo.com"
CELULAR = "3001234567"


# La bandeja y los trabajos del servicio de origen, declarados igual que en el
# repartidor (no se importan: regla 1). `carga` usa el tipo portable.
def _tablas_origen() -> tuple[MetaData, Table, Table]:
    metadatos = MetaData()
    bandeja = Table(
        "bandeja_salida",
        metadatos,
        Column("id", BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True),
        Column("tipo", String(128)),
        Column("agregado_tipo", String(64)),
        Column("agregado_id", Uuid(as_uuid=True)),
        Column("carga", Texto),
        Column("publicado_en", DateTime(timezone=True)),
        Column("intentos", Integer, default=0),
    )
    trabajo = Table(
        "trabajo_pipeline",
        metadatos,
        Column("id", Uuid(as_uuid=True), primary_key=True),
        Column("usuario_id", Uuid(as_uuid=True)),
    )
    return metadatos, bandeja, trabajo


class IdentidadContacto:
    """Doble del cliente de Identidad: devuelve un contacto fijo por id.

    Registra a quien le preguntaron para comprobar que el repartidor resuelve el
    contacto al vuelo (y no lo guarda)."""

    def __init__(self, correo: str | None = CORREO, celular: str | None = CELULAR) -> None:
        self.correo = correo
        self.celular = celular
        self.consultados: list[str] = []

    async def contacto_de(self, usuario_id: str) -> dict[str, str | None] | None:
        self.consultados.append(usuario_id)
        return {"correo": self.correo, "celular": self.celular}


@pytest_asyncio.fixture
async def motor_operacion() -> AsyncIterator[MotorServicio]:
    from sqlalchemy.ext.asyncio import async_sessionmaker

    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conexion:
        await conexion.run_sync(Base.metadata.create_all)
    fabrica = async_sessionmaker(engine, expire_on_commit=False)
    yield MotorServicio(servicio="operacion", engine=engine, _fabrica=fabrica)
    await engine.dispose()


@pytest_asyncio.fixture
async def motor_origen():
    metadatos, bandeja, trabajo = _tablas_origen()
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conexion:
        await conexion.run_sync(metadatos.create_all)
    yield engine, bandeja, trabajo
    await engine.dispose()


async def _sembrar_kits_publicados(engine, bandeja, trabajo, trabajo_id: uuid.UUID) -> None:
    async with engine.begin() as conexion:
        await conexion.execute(insert(trabajo).values(id=trabajo_id, usuario_id=USUARIO))
        await conexion.execute(
            insert(bandeja).values(
                tipo="kits_publicados",
                agregado_tipo="trabajo_pipeline",
                agregado_id=trabajo_id,
                carga={},
                intentos=0,
            )
        )


async def _contar_notificaciones(motor_operacion) -> list:
    async with motor_operacion.engine.begin() as conexion:
        return list(await conexion.execute(select(NOTIFICACION)))


async def _pendientes(engine, bandeja) -> list:
    async with engine.begin() as conexion:
        return list(
            await conexion.execute(select(bandeja).where(bandeja.c.publicado_en.is_(None)))
        )


def _repartidor(motor_operacion, engine, notificador, identidad) -> Repartidor:
    return Repartidor(
        origen="inteligencia",
        motor_operacion=motor_operacion,
        motor_origen=engine,
        notificador=notificador,
        identidad=identidad,
    )


async def test_una_pasada_crea_una_notificacion_y_marca_publicado(motor_operacion, motor_origen):
    engine, bandeja, trabajo = motor_origen
    trabajo_id = uuid.uuid4()
    await _sembrar_kits_publicados(engine, bandeja, trabajo, trabajo_id)

    notificador = NotificadorFalso()
    identidad = IdentidadContacto()
    entregados = await _repartidor(motor_operacion, engine, notificador, identidad).pasada()

    assert entregados == 1
    filas = await _contar_notificaciones(motor_operacion)
    assert len(filas) == 1
    # El destinatario se resolvio desde trabajo_pipeline.usuario_id, no de la carga.
    assert filas[0].usuario_id == USUARIO
    # La fuente quedo marcada como publicada.
    assert await _pendientes(engine, bandeja) == []
    # Se resolvio el contacto al vuelo y el notificador registro un envio.
    assert identidad.consultados == [str(USUARIO)]
    assert len(notificador.enviados) == 1


async def test_segunda_pasada_no_reprocesa(motor_operacion, motor_origen):
    engine, bandeja, trabajo = motor_origen
    await _sembrar_kits_publicados(engine, bandeja, trabajo, uuid.uuid4())

    notificador = NotificadorFalso()
    reparto = _repartidor(motor_operacion, engine, notificador, IdentidadContacto())
    assert await reparto.pasada() == 1
    # La segunda pasada no encuentra nada sin publicar: cero entregas nuevas.
    assert await reparto.pasada() == 0
    assert len(await _contar_notificaciones(motor_operacion)) == 1
    assert len(notificador.enviados) == 1


async def test_notificacion_y_contenido_no_llevan_contacto(motor_operacion, motor_origen):
    engine, bandeja, trabajo = motor_origen
    await _sembrar_kits_publicados(engine, bandeja, trabajo, uuid.uuid4())

    notificador = NotificadorFalso()
    await _repartidor(motor_operacion, engine, notificador, IdentidadContacto()).pasada()

    filas = await _contar_notificaciones(motor_operacion)
    guardado = f"{filas[0].datos} {filas[0].canal} {filas[0].plantilla}"
    assert CORREO not in guardado
    assert CELULAR not in guardado
    # Y lo que se envio tampoco repite el contacto en el cuerpo.
    texto = notificador.enviados[0]["texto"]
    assert CORREO not in texto
    assert CELULAR not in texto


async def test_pedido_pagado_saca_el_usuario_de_la_carga(motor_operacion, motor_origen):
    engine, bandeja, trabajo = motor_origen
    pedido_id = uuid.uuid4()
    async with engine.begin() as conexion:
        await conexion.execute(
            insert(bandeja).values(
                tipo="pedido_pagado",
                agregado_tipo="pedido",
                agregado_id=pedido_id,
                carga={"usuario_id": str(USUARIO), "pedido_id": str(pedido_id)},
                intentos=0,
            )
        )

    notificador = NotificadorFalso()
    entregados = await _repartidor(motor_operacion, engine, notificador, IdentidadContacto()).pasada()

    assert entregados == 1
    filas = await _contar_notificaciones(motor_operacion)
    assert filas[0].usuario_id == USUARIO
    assert filas[0].plantilla == "pedido_pagado"


async def test_fallo_de_envio_sube_intentos_y_no_publica(motor_operacion, motor_origen):
    engine, bandeja, trabajo = motor_origen
    trabajo_id = uuid.uuid4()
    await _sembrar_kits_publicados(engine, bandeja, trabajo, trabajo_id)

    # Identidad no resuelve el contacto: el envio no puede salir.
    class SinContacto:
        async def contacto_de(self, usuario_id: str):
            return None

    class NotificadorQueFalla:
        canal = "correo"

        async def enviar(self, contacto, plantilla, datos):
            from tukit_operacion.notificador import Envio

            return Envio(canal="correo", exito=False, detalle="sin_correo")

    entregados = await _repartidor(
        motor_operacion, engine, NotificadorQueFalla(), SinContacto()
    ).pasada()

    assert entregados == 0
    # La fila sigue pendiente para reintentar, con intentos subido.
    pendientes = await _pendientes(engine, bandeja)
    assert len(pendientes) == 1
    assert pendientes[0].intentos == 1
    # Se registro el intento fallido como notificacion fallida.
    filas = await _contar_notificaciones(motor_operacion)
    assert len(filas) == 1
    assert filas[0].estado == "fallida"
