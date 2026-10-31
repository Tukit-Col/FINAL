"""Un pago avisa una sola vez (H-B-03, ADR 0042).

En CH-15 un solo pago aviso dos veces `pedido_pagado` al acudiente. El
repartidor envia el aviso y registra la `notificacion` (en la base de Operacion)
antes de publicar el evento al broker y de marcarlo en la bandeja de Comercio.
Si la publicacion falla, la transaccion de la bandeja vuelve atras y la
siguiente pasada entrega el mismo evento otra vez: un segundo envio y una
segunda fila.

Ahora la notificacion guarda de que evento sale (`evento_origen`, `evento_id`) y
el repartidor, antes de resolver el contacto o enviar, mira si ese evento ya se
aviso. Lo que fija esta prueba:

1. **El mismo evento dos veces da un solo envio y una sola fila**, y el evento
   queda publicado cuando el broker vuelve.
2. **La reentrega sigue funcionando** para lo que no se aviso: un envio fallido
   se reintenta y sale.
3. **Eventos distintos dan avisos distintos**, tambien si dos bandejas de origen
   repiten el mismo `id`.
4. **La base lo respalda:** un indice unico parcial no deja dos filas `enviada`
   del mismo evento, y si deja varias `fallida`.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from typing import Any

import pytest
import pytest_asyncio
import sqlalchemy as sa
from sqlalchemy import insert, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from test_repartidor import USUARIO, IdentidadContacto, _sembrar_kits_publicados, _tablas_origen
from tukit_comun.bd import MotorServicio
from tukit_operacion.modelos import Base
from tukit_operacion.notificador import Envio, NotificadorFalso
from tukit_operacion.repartidor import NOTIFICACION, Repartidor


# aiormq no se importa: las pruebas de los servicios corren sin el. Misma base
# que la de aiormq.
class AMQPConnectionError(ConnectionError):
    pass


class _SinkQueFalla:
    """Un `BrokerSink` con RabbitMQ caido las primeras `caidas` veces que publica."""

    def __init__(self, caidas: int = 1) -> None:
        self.caidas = caidas
        self.publicados: list[int] = []

    async def publicar(self, fila: Any) -> None:
        if self.caidas:
            self.caidas -= 1
            raise AMQPConnectionError("[Errno 111] Connection refused")
        self.publicados.append(fila.id)


class _NotificadorQueFallaPrimero(NotificadorFalso):
    """El primer envio no sale (por ejemplo, el proveedor de correo no responde)."""

    def __init__(self) -> None:
        super().__init__()
        self.intentos = 0

    async def enviar(self, contacto, plantilla, datos) -> Envio:
        self.intentos += 1
        if self.intentos == 1:
            return Envio(canal=self.canal, exito=False, detalle="proveedor_caido")
        return await super().enviar(contacto, plantilla, datos)


@pytest_asyncio.fixture
async def motor_operacion() -> AsyncIterator[MotorServicio]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conexion:
        await conexion.run_sync(Base.metadata.create_all)
    fabrica = async_sessionmaker(engine, expire_on_commit=False)
    yield MotorServicio(servicio="operacion", engine=engine, _fabrica=fabrica)
    await engine.dispose()


async def _origen() -> tuple[Any, Any, Any]:
    metadatos, bandeja, trabajo = _tablas_origen()
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conexion:
        await conexion.run_sync(metadatos.create_all)
    return engine, bandeja, trabajo


@pytest_asyncio.fixture
async def comercio() -> AsyncIterator[tuple[Any, Any, Any]]:
    engine, bandeja, trabajo = await _origen()
    yield engine, bandeja, trabajo
    await engine.dispose()


@pytest_asyncio.fixture
async def inteligencia() -> AsyncIterator[tuple[Any, Any, Any]]:
    engine, bandeja, trabajo = await _origen()
    yield engine, bandeja, trabajo
    await engine.dispose()


async def _sembrar_pedido_pagado(engine: Any, bandeja: Any) -> int:
    pedido_id = uuid.uuid4()
    async with engine.begin() as conexion:
        resultado = await conexion.execute(
            insert(bandeja).values(
                tipo="pedido_pagado",
                agregado_tipo="pedido",
                agregado_id=pedido_id,
                carga={"usuario_id": str(USUARIO), "pedido_id": str(pedido_id)},
                intentos=0,
            )
        )
    return resultado.inserted_primary_key[0]


def _repartidor(origen: str, motor_operacion, engine, notificador, sink=None, identidad=None) -> Repartidor:
    return Repartidor(
        origen=origen,
        motor_operacion=motor_operacion,
        motor_origen=engine,
        notificador=notificador,
        identidad=identidad or IdentidadContacto(),
        sink=sink,
    )


async def _notificaciones(motor_operacion) -> list[Any]:
    async with motor_operacion.engine.begin() as conexion:
        return list(await conexion.execute(select(NOTIFICACION).order_by(NOTIFICACION.c.creado_en)))


async def _publicado(engine: Any, bandeja: Any, evento_id: int) -> bool:
    async with engine.begin() as conexion:
        publicado_en = await conexion.scalar(select(bandeja.c.publicado_en).where(bandeja.c.id == evento_id))
    return publicado_en is not None


class TestElMismoEventoAvisaUnaVez:
    async def test_si_el_broker_falla_la_reentrega_no_vuelve_a_avisar(self, motor_operacion, comercio):
        engine, bandeja, _trabajo = comercio
        evento_id = await _sembrar_pedido_pagado(engine, bandeja)
        notificador = NotificadorFalso()
        identidad = IdentidadContacto()
        sink = _SinkQueFalla(caidas=1)
        reparto = _repartidor("comercio", motor_operacion, engine, notificador, sink, identidad)

        # Primera pasada: el aviso sale y queda registrado, pero publicar falla
        # y la bandeja vuelve atras. Es lo que paso en CH-15.
        with pytest.raises(AMQPConnectionError):
            await reparto.pasada()
        assert not await _publicado(engine, bandeja, evento_id)

        # Segunda pasada, con el broker de vuelta: el mismo evento llega otra vez.
        assert await reparto.pasada() == 1

        assert [envio["plantilla"] for envio in notificador.enviados] == ["pedido_pagado"]
        # Ni siquiera se resolvio otra vez el contacto del acudiente.
        assert identidad.consultados == [str(USUARIO)]
        [fila] = await _notificaciones(motor_operacion)
        assert (fila.plantilla, fila.estado) == ("pedido_pagado", "enviada")
        assert (fila.evento_origen, fila.evento_id) == ("comercio", evento_id)
        # El evento queda publicado al broker y marcado en la bandeja.
        assert sink.publicados == [evento_id]
        assert await _publicado(engine, bandeja, evento_id)

    async def test_varias_caidas_del_broker_siguen_dando_un_solo_aviso(self, motor_operacion, comercio):
        engine, bandeja, _trabajo = comercio
        evento_id = await _sembrar_pedido_pagado(engine, bandeja)
        notificador = NotificadorFalso()
        reparto = _repartidor("comercio", motor_operacion, engine, notificador, _SinkQueFalla(caidas=3))

        for _ in range(3):
            with pytest.raises(AMQPConnectionError):
                await reparto.pasada()
        assert await reparto.pasada() == 1

        assert len(notificador.enviados) == 1
        assert len(await _notificaciones(motor_operacion)) == 1
        assert await _publicado(engine, bandeja, evento_id)


class TestLaReentregaSigueParaLoQueNoSeAviso:
    async def test_un_envio_fallido_se_reintenta_y_sale(self, motor_operacion, comercio):
        engine, bandeja, _trabajo = comercio
        evento_id = await _sembrar_pedido_pagado(engine, bandeja)
        notificador = _NotificadorQueFallaPrimero()
        reparto = _repartidor("comercio", motor_operacion, engine, notificador)

        assert await reparto.pasada() == 0
        assert not await _publicado(engine, bandeja, evento_id)
        assert await reparto.pasada() == 1

        assert notificador.intentos == 2
        assert len(notificador.enviados) == 1
        filas = await _notificaciones(motor_operacion)
        assert [f.estado for f in filas] == ["fallida", "enviada"]
        assert {(f.evento_origen, f.evento_id) for f in filas} == {("comercio", evento_id)}
        assert await _publicado(engine, bandeja, evento_id)

    async def test_dos_pagos_distintos_dan_dos_avisos(self, motor_operacion, comercio):
        engine, bandeja, _trabajo = comercio
        primero = await _sembrar_pedido_pagado(engine, bandeja)
        segundo = await _sembrar_pedido_pagado(engine, bandeja)
        notificador = NotificadorFalso()

        assert await _repartidor("comercio", motor_operacion, engine, notificador).pasada() == 2

        assert len(notificador.enviados) == 2
        filas = await _notificaciones(motor_operacion)
        assert sorted(f.evento_id for f in filas) == sorted([primero, segundo])

    async def test_el_mismo_id_en_otra_bandeja_es_otro_evento(self, motor_operacion, comercio, inteligencia):
        # Cada bandeja numera sus eventos por su cuenta: el evento 1 de Comercio
        # y el evento 1 de Inteligencia son dos avisos distintos.
        engine_comercio, bandeja_comercio, _ = comercio
        engine_inteligencia, bandeja_inteligencia, trabajo = inteligencia
        id_comercio = await _sembrar_pedido_pagado(engine_comercio, bandeja_comercio)
        await _sembrar_kits_publicados(engine_inteligencia, bandeja_inteligencia, trabajo, uuid.uuid4())
        notificador = NotificadorFalso()

        assert (
            await _repartidor("inteligencia", motor_operacion, engine_inteligencia, notificador).pasada() == 1
        )
        assert await _repartidor("comercio", motor_operacion, engine_comercio, notificador).pasada() == 1

        assert [envio["plantilla"] for envio in notificador.enviados] == ["kits_publicados", "pedido_pagado"]
        filas = await _notificaciones(motor_operacion)
        assert {(f.evento_origen, f.evento_id) for f in filas} == {
            ("inteligencia", 1),
            ("comercio", id_comercio),
        }
        assert id_comercio == 1


async def _insertar_notificacion(conexion, estado: str, *, evento_origen: str | None, evento_id: int | None):
    await conexion.execute(
        insert(NOTIFICACION).values(
            id=uuid.uuid4(),
            usuario_id=USUARIO,
            canal="correo",
            plantilla="pedido_pagado",
            datos={},
            estado=estado,
            evento_origen=evento_origen,
            evento_id=evento_id,
        )
    )


class TestLaBaseLoRespalda:
    async def test_no_admite_dos_avisos_enviados_del_mismo_evento(self, motor_operacion):
        async with motor_operacion.engine.connect() as conexion:
            await _insertar_notificacion(conexion, "enviada", evento_origen="comercio", evento_id=7)
            with pytest.raises(sa.exc.IntegrityError):
                async with conexion.begin_nested():
                    await _insertar_notificacion(conexion, "enviada", evento_origen="comercio", evento_id=7)

    async def test_admite_varios_fallidos_y_avisos_sin_evento(self, motor_operacion):
        async with motor_operacion.engine.begin() as conexion:
            await _insertar_notificacion(conexion, "fallida", evento_origen="comercio", evento_id=7)
            await _insertar_notificacion(conexion, "fallida", evento_origen="comercio", evento_id=7)
            await _insertar_notificacion(conexion, "enviada", evento_origen="comercio", evento_id=7)
            await _insertar_notificacion(conexion, "enviada", evento_origen="inteligencia", evento_id=7)
            # Las notificaciones de antes de esta columna no tienen evento.
            await _insertar_notificacion(conexion, "enviada", evento_origen=None, evento_id=None)
            await _insertar_notificacion(conexion, "enviada", evento_origen=None, evento_id=None)

        assert len(await _notificaciones(motor_operacion)) == 6
