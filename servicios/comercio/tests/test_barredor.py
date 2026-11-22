from __future__ import annotations

import socket
import uuid
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine
from tukit_comercio import barredor
from tukit_comercio.dominio.saga import TTL_RESERVA
from tukit_comercio.modelos import Base, EstadoPedido, Pedido, ReservaInventario
from tukit_comun.resiliencia import ESPERA_INICIAL_BUCLE

AHORA = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
_TTL_MIN = int(TTL_RESERVA.total_seconds() // 60)


@pytest_asyncio.fixture
async def motor():
    m = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with m.begin() as conexion:
        await conexion.run_sync(Base.metadata.create_all)
    yield m
    await m.dispose()


async def _pedido_con_reserva(motor, *, edad_min: float, pedido_estado: str, reserva_estado: str):
    pid = uuid.uuid4()
    async with motor.begin() as conexion:
        await conexion.execute(
            Pedido.__table__.insert().values(
                id=pid,
                usuario_id=uuid.uuid4(),
                total=0,
                hijos=1,
                colegios=["C"],
                estado=pedido_estado,
            )
        )
        await conexion.execute(
            ReservaInventario.__table__.insert().values(
                id=uuid.uuid4(),
                pedido_id=pid,
                producto_canonico_id=uuid.uuid4(),
                cantidad=1,
                estado=reserva_estado,
                creado_en=AHORA - timedelta(minutes=edad_min),
            )
        )
    return pid


async def _estados(motor, pid):
    async with motor.begin() as conexion:
        pedido = await conexion.scalar(select(Pedido.__table__.c.estado).where(Pedido.__table__.c.id == pid))
        reserva = await conexion.scalar(
            select(ReservaInventario.__table__.c.estado).where(ReservaInventario.__table__.c.pedido_id == pid)
        )
    return pedido, reserva


async def test_libera_reserva_vieja_sin_pagar_y_cancela_el_pedido(motor):
    pid = await _pedido_con_reserva(
        motor, edad_min=_TTL_MIN + 1, pedido_estado="pendiente_pago", reserva_estado="activa"
    )

    n = await barredor.pasada(motor, ahora=AHORA, limite=100)

    assert n == 1
    assert await _estados(motor, pid) == (EstadoPedido.CANCELADO.value, "liberada")


async def test_no_toca_reserva_reciente(motor):
    pid = await _pedido_con_reserva(
        motor, edad_min=_TTL_MIN - 1, pedido_estado="pendiente_pago", reserva_estado="activa"
    )

    assert await barredor.pasada(motor, ahora=AHORA) == 0
    assert await _estados(motor, pid) == ("pendiente_pago", "activa")


async def test_no_toca_reserva_de_pedido_pagado(motor):
    pid = await _pedido_con_reserva(
        motor, edad_min=_TTL_MIN * 2, pedido_estado="pagado", reserva_estado="activa"
    )

    assert await barredor.pasada(motor, ahora=AHORA) == 0
    assert await _estados(motor, pid) == ("pagado", "activa")


_INTERVALO = 60.0


class _Corte(Exception):
    pass


class _MotorIntermitente:

    def __init__(self, real, *errores: BaseException) -> None:
        self.real = real
        self.errores = list(errores)
        self.engine = self

    @asynccontextmanager
    async def begin(self):
        if self.errores:
            raise self.errores.pop(0)
        async with self.real.begin() as conexion:
            yield conexion

    async def cerrar(self) -> None:
        pass


def _dormir_que_corta(esperas: list[float]):
    async def dormir(segundos: float) -> None:
        esperas.append(segundos)
        if segundos == _INTERVALO:
            raise _Corte

    return dormir


async def test_el_barredor_vuelve_tras_una_caida_de_postgres(motor, monkeypatch):
    pid = await _pedido_con_reserva(
        motor, edad_min=_TTL_MIN + 1, pedido_estado="pendiente_pago", reserva_estado="activa"
    )
    intermitente = _MotorIntermitente(
        motor,
        ConnectionRefusedError(61, "Connect call failed ('127.0.0.1', 5432)"),
        ConnectionRefusedError(61, "Connect call failed ('127.0.0.1', 5432)"),
        socket.gaierror(8, "nodename nor servname provided, or not known"),
    )
    monkeypatch.setattr(barredor, "crear_motor", lambda _servicio: intermitente)
    esperas: list[float] = []

    with pytest.raises(_Corte):
        await barredor._bucle(_INTERVALO, dormir=_dormir_que_corta(esperas))

    assert esperas == [ESPERA_INICIAL_BUCLE * 2**i for i in range(3)] + [_INTERVALO]
    assert await _estados(motor, pid) == (EstadoPedido.CANCELADO.value, "liberada")


async def test_un_error_de_programacion_termina_el_barredor(motor, monkeypatch):
    monkeypatch.setattr(
        barredor, "crear_motor", lambda _servicio: _MotorIntermitente(motor, ValueError("bug"))
    )
    esperas: list[float] = []

    with pytest.raises(ValueError):
        await barredor._bucle(_INTERVALO, dormir=_dormir_que_corta(esperas))

    assert esperas == []


async def test_el_bucle_duerme_con_el_asyncio_sleep_de_cuando_corre(monkeypatch):
    vueltas: list[int] = []

    async def _nada() -> int:
        vueltas.append(1)
        if len(vueltas) > 1:
            raise _Corte
        return 0

    esperas: list[float] = []
    monkeypatch.setattr(barredor, "correr_una_vez", _nada)
    monkeypatch.setattr(barredor, "asyncio", SimpleNamespace(sleep=_dormir_que_corta(esperas)))

    with pytest.raises(_Corte):
        await barredor._bucle(_INTERVALO)

    assert esperas == [_INTERVALO]


def test_el_barredor_configura_el_log_al_arrancar(monkeypatch):
    titulos: list[str] = []
    monkeypatch.setattr(barredor, "configurar_registro", titulos.append)

    async def _nada() -> int:
        return 0

    monkeypatch.setattr(barredor, "correr_una_vez", _nada)

    assert barredor.main([]) == 0
    assert titulos == ["comercio-barredor"]
