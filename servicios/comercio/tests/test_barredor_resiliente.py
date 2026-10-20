"""El barredor vuelve solo tras una caida de Postgres (H-B-02, ADR 0041).

Con Postgres caido, `motor.begin()` lanzaba `ConnectionRefusedError` y el
proceso moria con codigo 1; ya no volvia cuando la base regresaba (CH-12). En
Docker el nombre del contenedor muerto deja de resolver, asi que lo esperable
ahi es `socket.gaierror`. Aqui el motor falla las primeras veces con esos dos
errores y despues responde: el bucle de verdad (`_bucle`) espera, reintenta y
libera la reserva vencida. Un error de programacion sigue terminandolo.
"""

from __future__ import annotations

import socket
from contextlib import asynccontextmanager

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from test_barredor import _TTL_MIN, _estados, _pedido_con_reserva
from tukit_comercio import barredor
from tukit_comercio.modelos import Base, EstadoPedido

_INTERVALO = 60.0


class _Corte(Exception):
    """La lanza el `dormir` de la prueba para salir del bucle infinito."""


class _MotorIntermitente:
    """Un `MotorServicio` cuya base no responde las primeras veces que se abre.

    Lanza los errores dados, en orden, al abrir una transaccion, como asyncpg
    con Postgres caido; despues delega en el motor de verdad.
    """

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


@pytest_asyncio.fixture
async def motor():
    m = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with m.begin() as conexion:
        await conexion.run_sync(Base.metadata.create_all)
    yield m
    await m.dispose()


async def test_el_barredor_vuelve_tras_una_caida_de_postgres(motor, monkeypatch):
    # `correr_una_vez` mira el reloj real, y la reserva es vieja tambien para
    # el: `_pedido_con_reserva` la fecha contra un `AHORA` que ya paso.
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

    assert esperas == [1.0, 2.0, 4.0, _INTERVALO]
    assert await _estados(motor, pid) == (EstadoPedido.CANCELADO.value, "liberada")


async def test_un_error_de_programacion_sigue_terminando_el_barredor(motor, monkeypatch):
    monkeypatch.setattr(
        barredor, "crear_motor", lambda _servicio: _MotorIntermitente(motor, ValueError("bug"))
    )
    esperas: list[float] = []

    with pytest.raises(ValueError):
        await barredor._bucle(_INTERVALO, dormir=_dormir_que_corta(esperas))

    assert esperas == []


def test_el_barredor_configura_el_log_al_arrancar(monkeypatch):
    titulos: list[str] = []
    monkeypatch.setattr(barredor, "configurar_registro", titulos.append)

    async def _nada() -> int:
        return 0

    monkeypatch.setattr(barredor, "correr_una_vez", _nada)

    assert barredor.main([]) == 0
    assert titulos == ["comercio-barredor"]
