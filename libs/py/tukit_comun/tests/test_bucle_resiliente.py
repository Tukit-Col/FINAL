from __future__ import annotations

import asyncio
import logging
import socket

import aiormq.exceptions
import pytest
from sqlalchemy import exc
from tukit_comun.resiliencia import bucle_resiliente, es_caida_transitoria


class _Corte(Exception):
    pass


class PostgresError(Exception):
    pass


class OperatorInterventionError(PostgresError):
    pass


class CannotConnectNowError(OperatorInterventionError):
    pass


class AdminShutdownError(OperatorInterventionError):
    pass


class PostgresConnectionError(PostgresError):
    pass


class ConnectionDoesNotExistError(PostgresConnectionError):
    pass


class InsufficientResourcesError(PostgresError):
    pass


class TooManyConnectionsError(InsufficientResourcesError):
    pass


class UndefinedTableError(PostgresError):
    pass


def _dbapi(orig: BaseException, *, invalidada: bool = False) -> exc.DBAPIError:
    return exc.DBAPIError("SELECT 1", {}, orig, connection_invalidated=invalidada)


def _con_causa(error: BaseException, causa: BaseException) -> BaseException:
    error.__cause__ = causa
    return error


@pytest.mark.parametrize(
    "error",
    [
        ConnectionRefusedError(61, "Connect call failed ('127.0.0.1', 5432)"),
        socket.gaierror(8, "nodename nor servname provided, or not known"),
        TimeoutError(),
        ConnectionResetError(54, "Connection reset by peer"),
        OSError("Multiple exceptions: [Errno 61] Connect call failed ('::1', 5432, 0, 0)"),
        CannotConnectNowError("the database system is starting up"),
        AdminShutdownError("terminating connection due to administrator command"),
        ConnectionDoesNotExistError("connection was closed in the middle of operation"),
        TooManyConnectionsError("sorry, too many clients already"),
        aiormq.exceptions.AMQPConnectionError("Connection refused"),
        aiormq.exceptions.ConnectionClosed(320, "CONNECTION_FORCED"),
        aiormq.exceptions.ChannelInvalidStateError("No active transport in channel"),
        aiormq.exceptions.DeliveryError(None, None),
        _dbapi(Exception("connection is closed"), invalidada=True),
        _dbapi(ConnectionDoesNotExistError("connection was closed")),
        _con_causa(RuntimeError("envoltorio"), ConnectionRefusedError()),
    ],
    ids=lambda e: type(e).__name__,
)
def test_es_caida_transitoria(error):
    assert es_caida_transitoria(error) is True


@pytest.mark.parametrize(
    "error",
    [
        ValueError("argumento invalido"),
        KeyError("falta"),
        RuntimeError("estado imposible"),
        exc.IntegrityError("INSERT", {}, Exception("duplicate key value")),
        exc.ProgrammingError("SELECT", {}, Exception("syntax error")),
        exc.OperationalError("SELECT", {}, Exception("no such table: reserva_inventario")),
        _dbapi(Exception("division by zero")),
        _dbapi(UndefinedTableError('relation "reserva_inventario" does not exist')),
        UndefinedTableError('relation "reserva_inventario" does not exist'),
        FileNotFoundError(2, "No such file or directory"),
        PermissionError(13, "Permission denied"),
        aiormq.exceptions.ChannelPreconditionFailed("PRECONDITION_FAILED"),
        asyncio.CancelledError(),
    ],
    ids=lambda e: type(e).__name__,
)
def test_no_es_caida_transitoria(error):
    assert es_caida_transitoria(error) is False


class _Vuelta:

    def __init__(self, *errores: BaseException | None) -> None:
        self.errores = list(errores)
        self.llamadas = 0

    async def __call__(self) -> None:
        self.llamadas += 1
        if self.errores:
            error = self.errores.pop(0)
            if error is not None:
                raise error


def _dormir_que_corta(esperas: list[float], *, intervalo: float, vueltas_buenas: int = 1):
    restantes = [vueltas_buenas]

    async def dormir(segundos: float) -> None:
        esperas.append(segundos)
        if segundos == intervalo:
            restantes[0] -= 1
            if restantes[0] == 0:
                raise _Corte

    return dormir


async def test_vuelve_tras_las_caidas_con_espera_exponencial():
    vuelta = _Vuelta(
        ConnectionRefusedError(61, "Connect call failed"),
        ConnectionRefusedError(61, "Connect call failed"),
        socket.gaierror(8, "nodename nor servname provided, or not known"),
    )
    esperas: list[float] = []

    with pytest.raises(_Corte):
        await bucle_resiliente(
            vuelta, intervalo=5.0, proceso="prueba", dormir=_dormir_que_corta(esperas, intervalo=5.0)
        )

    assert vuelta.llamadas == 4
    assert esperas == [1.0, 2.0, 4.0, 5.0]


async def test_la_espera_tiene_tope():
    vuelta = _Vuelta(*[ConnectionRefusedError() for _ in range(7)])
    esperas: list[float] = []

    with pytest.raises(_Corte):
        await bucle_resiliente(
            vuelta,
            intervalo=60.0,
            proceso="prueba",
            espera_tope=30.0,
            dormir=_dormir_que_corta(esperas, intervalo=60.0),
        )

    assert esperas == [1.0, 2.0, 4.0, 8.0, 16.0, 30.0, 30.0, 60.0]


async def test_tras_una_vuelta_buena_la_espera_empieza_de_nuevo():
    vuelta = _Vuelta(ConnectionRefusedError(), ConnectionRefusedError(), None, ConnectionRefusedError())
    esperas: list[float] = []

    with pytest.raises(_Corte):
        await bucle_resiliente(
            vuelta,
            intervalo=5.0,
            proceso="prueba",
            dormir=_dormir_que_corta(esperas, intervalo=5.0, vueltas_buenas=2),
        )

    assert esperas == [1.0, 2.0, 5.0, 1.0, 5.0]


async def test_cada_caida_queda_en_el_log_con_el_proceso_y_la_excepcion(caplog):
    vuelta = _Vuelta(socket.gaierror(8, "nodename nor servname provided, or not known"))
    caplog.set_level(logging.WARNING, logger="tukit_comun.resiliencia")

    with pytest.raises(_Corte):
        await bucle_resiliente(
            vuelta, intervalo=5.0, proceso="barredor", dormir=_dormir_que_corta([], intervalo=5.0)
        )

    [registro] = [r for r in caplog.records if r.name == "tukit_comun.resiliencia"]
    assert registro.levelno == logging.WARNING
    assert "barredor" in registro.getMessage()
    assert "gaierror" in registro.getMessage()
    assert registro.exc_info is not None and isinstance(registro.exc_info[1], socket.gaierror)


@pytest.mark.parametrize("error", [ValueError("bug"), KeyError("falta"), asyncio.CancelledError()])
async def test_un_error_que_no_es_caida_termina_el_bucle_sin_esperar(error):
    vuelta = _Vuelta(error)
    esperas: list[float] = []

    with pytest.raises(type(error)):
        await bucle_resiliente(
            vuelta, intervalo=5.0, proceso="prueba", dormir=_dormir_que_corta(esperas, intervalo=5.0)
        )

    assert vuelta.llamadas == 1
    assert esperas == []


async def test_una_caida_y_despues_un_bug_termina_el_bucle():
    vuelta = _Vuelta(ConnectionRefusedError(), ValueError("bug"))
    esperas: list[float] = []

    with pytest.raises(ValueError):
        await bucle_resiliente(
            vuelta, intervalo=5.0, proceso="prueba", dormir=_dormir_que_corta(esperas, intervalo=5.0)
        )

    assert esperas == [1.0]


def test_los_nombres_coinciden_con_los_de_asyncpg():
    asyncpg_exc = pytest.importorskip("asyncpg.exceptions")

    assert es_caida_transitoria(asyncpg_exc.CannotConnectNowError("the database system is starting up"))
    assert es_caida_transitoria(asyncpg_exc.AdminShutdownError("terminating connection"))
    assert es_caida_transitoria(asyncpg_exc.ConnectionDoesNotExistError("connection was closed"))
    assert es_caida_transitoria(asyncpg_exc.TooManyConnectionsError("sorry, too many clients already"))
    assert not es_caida_transitoria(asyncpg_exc.UndefinedTableError('relation "x" does not exist'))
