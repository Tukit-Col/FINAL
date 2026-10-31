"""El repartidor vuelve solo tras una caida de Postgres o de RabbitMQ (H-B-02, ADR 0041).

Con Postgres caido, abrir la bandeja de origen lanzaba `ConnectionRefusedError`;
con RabbitMQ caido, publicar el evento lanzaba el error de conexion de aiormq.
En los dos casos el repartidor moria con codigo 1 y ya no volvia (CH-12 y
CH-15). En Docker el nombre del contenedor muerto deja de resolver, asi que lo
esperable ahi es `socket.gaierror`. Aqui la dependencia falla las primeras veces
y despues responde: el bucle de verdad (`_bucle`) espera, reintenta y entrega el
aviso. Un error de programacion sigue terminandolo.

Cada vuelta abre de nuevo sus motores y su sink, y por eso reconecta.
"""

from __future__ import annotations

import socket
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from types import SimpleNamespace
from typing import Any

import pytest
import pytest_asyncio
from sqlalchemy import insert, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from test_repartidor import USUARIO, IdentidadContacto, _tablas_origen
from tukit_comun.bd import MotorServicio
from tukit_operacion import repartidor
from tukit_operacion.modelos import Base
from tukit_operacion.notificador import NotificadorFalso

_INTERVALO = 5.0


class _Corte(Exception):
    """La lanza el `dormir` de la prueba para salir del bucle infinito."""


# aiormq no se importa: las pruebas de los servicios corren sin el. Estas clases
# tienen los nombres y las bases de las de aiormq (`AMQPConnectionError` es un
# `ConnectionError`; `ChannelInvalidStateError`, un `RuntimeError`).
class AMQPConnectionError(ConnectionError):
    pass


class ChannelInvalidStateError(RuntimeError):
    pass


class _EngineIntermitente:
    """Un `AsyncEngine` cuya base no responde las primeras veces que se abre.

    Lanza los errores dados, en orden, al abrir una transaccion, como asyncpg
    con Postgres caido; despues delega en el engine de verdad. No se cierra: la
    base en memoria de la prueba se perderia.
    """

    def __init__(self, real: Any, *errores: BaseException) -> None:
        self.real = real
        self.errores = list(errores)

    @asynccontextmanager
    async def begin(self):
        if self.errores:
            raise self.errores.pop(0)
        async with self.real.begin() as conexion:
            yield conexion

    async def dispose(self) -> None:
        pass

    def __getattr__(self, nombre: str) -> Any:
        return getattr(self.real, nombre)


class _SinkIntermitente:
    """Un `BrokerSink` con RabbitMQ caido las primeras veces que publica."""

    def __init__(self, *errores: BaseException) -> None:
        self.errores = list(errores)
        self.publicados: list[int] = []

    async def publicar(self, fila: Any) -> None:
        if self.errores:
            raise self.errores.pop(0)
        self.publicados.append(fila.id)

    async def cerrar(self) -> None:
        pass


class _MotorDePrueba:
    """El `MotorServicio` de Operacion de la prueba, que no se cierra."""

    def __init__(self, real: MotorServicio) -> None:
        self.real = real
        self.engine = real.engine

    def sesion(self):
        return self.real.sesion()

    async def cerrar(self) -> None:
        pass


def _dormir_que_corta(esperas: list[float]):
    async def dormir(segundos: float) -> None:
        esperas.append(segundos)
        if segundos == _INTERVALO:
            raise _Corte

    return dormir


@pytest_asyncio.fixture
async def motor_operacion() -> AsyncIterator[MotorServicio]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conexion:
        await conexion.run_sync(Base.metadata.create_all)
    fabrica = async_sessionmaker(engine, expire_on_commit=False)
    yield MotorServicio(servicio="operacion", engine=engine, _fabrica=fabrica)
    await engine.dispose()


@pytest_asyncio.fixture
async def origenes() -> AsyncIterator[dict[str, Any]]:
    """Las bases de Inteligencia y de Comercio, cada una con su bandeja."""
    bandejas: dict[str, Any] = {}
    engines = []
    for origen in ("inteligencia", "comercio"):
        metadatos, bandeja, _trabajo = _tablas_origen()
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        async with engine.begin() as conexion:
            await conexion.run_sync(metadatos.create_all)
        bandejas[origen] = (engine, bandeja)
        engines.append(engine)
    yield bandejas
    for engine in engines:
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


async def _publicado(engine: Any, bandeja: Any, evento_id: int) -> bool:
    async with engine.begin() as conexion:
        publicado_en = await conexion.scalar(select(bandeja.c.publicado_en).where(bandeja.c.id == evento_id))
    return publicado_en is not None


def _conectar(
    monkeypatch,
    motor_operacion,
    origenes,
    *,
    comercio: Any = None,
    sink: Any = None,
    notificador: Any = None,
) -> NotificadorFalso:
    """Cambia lo que `correr_una_vez` saca del entorno por las piezas de la prueba."""
    notificador = notificador or NotificadorFalso()
    # `correr_una_vez` cierra los motores de origen en cada vuelta: sin el
    # envoltorio, la base en memoria se perderia tras la primera.
    motores = {origen: _EngineIntermitente(engine) for origen, (engine, _bandeja) in origenes.items()}
    if comercio is not None:
        motores["comercio"] = comercio
    monkeypatch.setattr(repartidor, "crear_motor", lambda _servicio: _MotorDePrueba(motor_operacion))
    monkeypatch.setattr(repartidor, "_motor_lectura", lambda origen: motores[origen])
    monkeypatch.setattr(repartidor, "notificador_desde_entorno", lambda: notificador)
    monkeypatch.setattr(repartidor, "ClienteIdentidad", IdentidadContacto)
    monkeypatch.setattr(repartidor, "sink_desde_entorno", lambda: sink)
    return notificador


async def test_tras_una_caida_de_postgres_entrega_el_aviso(motor_operacion, origenes, monkeypatch):
    engine, bandeja = origenes["comercio"]
    evento_id = await _sembrar_pedido_pagado(engine, bandeja)
    comercio = _EngineIntermitente(
        engine,
        ConnectionRefusedError(61, "Connect call failed ('127.0.0.1', 5432)"),
        ConnectionRefusedError(61, "Connect call failed ('127.0.0.1', 5432)"),
        socket.gaierror(8, "nodename nor servname provided, or not known"),
    )
    notificador = _conectar(monkeypatch, motor_operacion, origenes, comercio=comercio)
    esperas: list[float] = []

    with pytest.raises(_Corte):
        await repartidor._bucle(_INTERVALO, dormir=_dormir_que_corta(esperas))

    assert esperas == [1.0, 2.0, 4.0, _INTERVALO]
    assert [envio["plantilla"] for envio in notificador.enviados] == ["pedido_pagado"]
    assert await _publicado(engine, bandeja, evento_id)


async def test_tras_una_caida_de_rabbitmq_publica_el_evento(motor_operacion, origenes, monkeypatch):
    engine, bandeja = origenes["comercio"]
    evento_id = await _sembrar_pedido_pagado(engine, bandeja)
    sink = _SinkIntermitente(
        AMQPConnectionError("[Errno 111] Connection refused"),
        ChannelInvalidStateError("No active transport in channel"),
    )
    notificador = _conectar(monkeypatch, motor_operacion, origenes, sink=sink)
    esperas: list[float] = []

    with pytest.raises(_Corte):
        await repartidor._bucle(_INTERVALO, dormir=_dormir_que_corta(esperas))

    assert esperas == [1.0, 2.0, _INTERVALO]
    assert sink.publicados == [evento_id]
    assert await _publicado(engine, bandeja, evento_id)
    # El evento se entrego tres veces, pero el acudiente recibe un solo aviso y
    # queda una sola notificacion, que es lo que mide CH-15 (H-B-03, ADR 0042).
    assert [envio["plantilla"] for envio in notificador.enviados] == ["pedido_pagado"]
    async with motor_operacion.engine.begin() as conexion:
        plantillas = list(await conexion.scalars(select(repartidor.NOTIFICACION.c.plantilla)))
    assert plantillas == ["pedido_pagado"]


async def test_un_error_de_programacion_sigue_terminando_el_repartidor(
    motor_operacion, origenes, monkeypatch
):
    engine, _bandeja = origenes["comercio"]
    _conectar(monkeypatch, motor_operacion, origenes, comercio=_EngineIntermitente(engine, ValueError("bug")))
    esperas: list[float] = []

    with pytest.raises(ValueError):
        await repartidor._bucle(_INTERVALO, dormir=_dormir_que_corta(esperas))

    assert esperas == []


async def test_el_bucle_duerme_con_el_asyncio_sleep_de_cuando_corre(monkeypatch):
    # Sin `dormir`, el bucle usa el `asyncio.sleep` que ve el modulo al correr,
    # no el de cuando se definio: asi lo sustituyen las pruebas de los procesos.
    vueltas: list[int] = []

    async def _nada() -> dict[str, int]:
        # Si el bucle durmiera con el `asyncio.sleep` de verdad, la segunda vuelta corta.
        vueltas.append(1)
        if len(vueltas) > 1:
            raise _Corte
        return {}

    esperas: list[float] = []
    monkeypatch.setattr(repartidor, "correr_una_vez", _nada)
    monkeypatch.setattr(repartidor, "asyncio", SimpleNamespace(sleep=_dormir_que_corta(esperas)))

    with pytest.raises(_Corte):
        await repartidor._bucle(_INTERVALO)

    assert esperas == [_INTERVALO]


def test_el_repartidor_configura_el_log_al_arrancar(monkeypatch):
    titulos: list[str] = []
    monkeypatch.setattr(repartidor, "configurar_registro", titulos.append)

    async def _nada() -> dict[str, int]:
        return {}

    monkeypatch.setattr(repartidor, "correr_una_vez", _nada)

    assert repartidor.main([]) == 0
    assert titulos == ["operacion-repartidor"]
