"""El poller de Identidad vuelve solo tras una caida de Postgres (H-B-02, ADR 0041).

Con Postgres caido, abrir la bandeja del Catalogo lanzaba
`ConnectionRefusedError` y el proceso moria con codigo 1; ya no volvia cuando la
base regresaba (CH-12). En Docker el nombre del contenedor muerto deja de
resolver, asi que lo esperable ahi es `socket.gaierror`. Aqui la base falla las
primeras veces con esos dos errores y despues responde: el bucle de verdad
(`_bucle`) espera, reintenta y da de alta el colegio. Un error de programacion
sigue terminandolo.
"""

from __future__ import annotations

import socket
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from tukit_comun.bd import MotorServicio
from tukit_identidad import poller
from tukit_identidad.modelos import Base, Colegio

from tests.test_poller import BANDEJA_CATALOGO, COLEGIO, _sembrar_bandeja

_INTERVALO = 5.0


class _Corte(Exception):
    """La lanza el `dormir` de la prueba para salir del bucle infinito."""


class _Intermitente:
    """Un motor cuya base no responde las primeras veces que se abre.

    Lanza los errores dados, en orden, al abrir una transaccion, como asyncpg
    con Postgres caido; despues delega en el motor de verdad. No se cierra:
    `correr_una_vez` cierra sus motores en cada vuelta, y la base en memoria de
    la prueba se perderia.
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

    async def cerrar(self) -> None:
        pass

    def __getattr__(self, nombre: str) -> Any:
        return getattr(self.real, nombre)


def _dormir_que_corta(esperas: list[float]):
    async def dormir(segundos: float) -> None:
        esperas.append(segundos)
        if segundos == _INTERVALO:
            raise _Corte

    return dormir


@pytest_asyncio.fixture
async def motor() -> AsyncIterator[MotorServicio]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conexion:
        await conexion.run_sync(Base.metadata.create_all)
    fabrica = async_sessionmaker(engine, expire_on_commit=False)
    yield MotorServicio(servicio="identidad", engine=engine, _fabrica=fabrica)
    await engine.dispose()


@pytest_asyncio.fixture
async def motor_catalogo() -> AsyncIterator[Any]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conexion:
        await conexion.run_sync(BANDEJA_CATALOGO.metadata.create_all)
    yield engine
    await engine.dispose()


def _conectar(monkeypatch, motor, catalogo) -> None:
    monkeypatch.setattr(poller, "crear_motor", lambda _servicio: _Intermitente(motor))
    monkeypatch.setattr(poller, "_motor_lectura", lambda _servicio: catalogo)


async def test_el_poller_vuelve_tras_una_caida_de_postgres(motor, motor_catalogo, monkeypatch):
    await _sembrar_bandeja(motor_catalogo, colegio_id=COLEGIO, nombre="Colegio Ficticio de Prueba")
    catalogo = _Intermitente(
        motor_catalogo,
        ConnectionRefusedError(61, "Connect call failed ('127.0.0.1', 5432)"),
        ConnectionRefusedError(61, "Connect call failed ('127.0.0.1', 5432)"),
        socket.gaierror(8, "nodename nor servname provided, or not known"),
    )
    _conectar(monkeypatch, motor, catalogo)
    esperas: list[float] = []

    with pytest.raises(_Corte):
        await poller._bucle(_INTERVALO, dormir=_dormir_que_corta(esperas))

    assert esperas == [1.0, 2.0, 4.0, _INTERVALO]
    async with motor.sesion() as db:
        colegio = (await db.execute(select(Colegio).where(Colegio.id == uuid.UUID(COLEGIO)))).scalar_one()
    assert colegio.nombre == "Colegio Ficticio de Prueba"
    async with motor_catalogo.begin() as conexion:
        publicado = await conexion.scalar(select(BANDEJA_CATALOGO.c.publicado_en))
    assert publicado is not None


async def test_un_error_de_programacion_sigue_terminando_el_poller(motor, motor_catalogo, monkeypatch):
    _conectar(monkeypatch, motor, _Intermitente(motor_catalogo, ValueError("bug")))
    esperas: list[float] = []

    with pytest.raises(ValueError):
        await poller._bucle(_INTERVALO, dormir=_dormir_que_corta(esperas))

    assert esperas == []


def test_el_poller_configura_el_log_al_arrancar(monkeypatch):
    titulos: list[str] = []
    monkeypatch.setattr(poller, "configurar_registro", titulos.append)

    async def _nada() -> int:
        return 0

    monkeypatch.setattr(poller, "correr_una_vez", _nada)

    assert poller.main([]) == 0
    assert titulos == ["identidad-poller"]
