"""El poller y el trabajador vuelven solos tras una caida de Postgres (H-B-02, ADR 0041).

Con Postgres caido, abrir una transaccion lanzaba `ConnectionRefusedError` y los
dos procesos de fondo de Inteligencia morian con codigo 1; ya no volvian cuando
la base regresaba (CH-12). En Docker el nombre del contenedor muerto deja de
resolver, asi que lo esperable ahi es `socket.gaierror`. Aqui la base falla las
primeras veces con esos dos errores y despues responde: el bucle de verdad
(`_bucle`) de cada proceso espera, reintenta y hace su trabajo. Un error de
programacion sigue terminandolo.

El poller abre sus motores en cada pasada. El trabajador reusa el suyo, y es
`pool_pre_ping` el que reconecta: la prueba deja el mismo motor entre intentos.
"""

from __future__ import annotations

import socket
import uuid
from contextlib import asynccontextmanager
from typing import Any

import pytest
import tukit_comun.bd
from sqlalchemy import select
from test_fastroute import _catalogo_verificado
from test_poller import _carga, _sembrar_bandeja
from test_trabajador import _encolar
from tukit_inteligencia import poller, trabajador, trabajos
from tukit_inteligencia.modelos import EstadoTrabajo

_INTERVALO = 5.0


class _Corte(Exception):
    """La lanza el `dormir` de la prueba para salir del bucle infinito."""


def _caidas() -> list[BaseException]:
    return [
        ConnectionRefusedError(61, "Connect call failed ('127.0.0.1', 5432)"),
        ConnectionRefusedError(61, "Connect call failed ('127.0.0.1', 5432)"),
        socket.gaierror(8, "nodename nor servname provided, or not known"),
    ]


class _EngineIntermitente:
    """Un `AsyncEngine` cuya base no responde las primeras veces que se abre.

    Lanza los errores dados, en orden, al abrir una transaccion o una conexion,
    como asyncpg con Postgres caido; despues delega en el engine de verdad. No
    se cierra: la base en memoria de la prueba se perderia.
    """

    def __init__(self, real: Any, *errores: BaseException) -> None:
        self.real = real
        self.errores = list(errores)

    def _quizas_caer(self) -> None:
        if self.errores:
            raise self.errores.pop(0)

    @asynccontextmanager
    async def begin(self):
        self._quizas_caer()
        async with self.real.begin() as conexion:
            yield conexion

    @asynccontextmanager
    async def connect(self):
        self._quizas_caer()
        async with self.real.connect() as conexion:
            yield conexion

    async def dispose(self) -> None:
        pass

    def __getattr__(self, nombre: str) -> Any:
        return getattr(self.real, nombre)


class _MotorDePrueba:
    """El `MotorServicio` de la prueba, con el engine dado, que no se cierra."""

    def __init__(self, real: Any, engine: Any = None) -> None:
        self.real = real
        self.engine = engine if engine is not None else real.engine

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


def _sin_red(monkeypatch, modulo) -> None:
    monkeypatch.setattr(modulo, "ClienteCatalogo", _catalogo_verificado)


class TestElPollerVuelve:
    async def test_tras_una_caida_de_postgres_arma_el_kit(self, motor, monkeypatch):
        contacto = str(uuid.uuid4())
        await _sembrar_bandeja(motor, **_carga(contacto))
        # Cada pasada abre su motor de lectura al Catalogo; aqui todas reciben el
        # mismo, que falla tres veces y despues responde.
        catalogo = _EngineIntermitente(motor.engine, *_caidas())
        monkeypatch.setattr(poller, "crear_motor", lambda _servicio: _MotorDePrueba(motor))
        monkeypatch.setattr(poller, "_motor_lectura", lambda _servicio: catalogo)
        _sin_red(monkeypatch, poller)
        esperas: list[float] = []

        with pytest.raises(_Corte):
            await poller._bucle(_INTERVALO, dormir=_dormir_que_corta(esperas))

        assert esperas == [1.0, 2.0, 4.0, _INTERVALO]
        async with motor.engine.begin() as conexion:
            fila = (
                await conexion.execute(select(trabajos.TRABAJO.c.usuario_id, trabajos.TRABAJO.c.estado))
            ).one()
        assert (str(fila.usuario_id), fila.estado) == (contacto, EstadoTrabajo.PUBLICADO.value)

    async def test_un_error_de_programacion_lo_sigue_terminando(self, motor, monkeypatch):
        await _sembrar_bandeja(motor, **_carga(str(uuid.uuid4())))
        monkeypatch.setattr(poller, "crear_motor", lambda _servicio: _MotorDePrueba(motor))
        monkeypatch.setattr(
            poller, "_motor_lectura", lambda _servicio: _EngineIntermitente(motor.engine, ValueError("bug"))
        )
        _sin_red(monkeypatch, poller)
        esperas: list[float] = []

        with pytest.raises(ValueError):
            await poller._bucle(_INTERVALO, dormir=_dormir_que_corta(esperas))

        assert esperas == []

    def test_configura_el_log_al_arrancar(self, monkeypatch):
        titulos: list[str] = []
        monkeypatch.setattr(poller, "configurar_registro", titulos.append)

        async def _nada() -> int:
            return 0

        monkeypatch.setattr(poller, "correr_una_vez", _nada)

        assert poller.main([]) == 0
        assert titulos == ["inteligencia-poller"]


class TestElTrabajadorVuelve:
    async def test_tras_una_caida_de_postgres_procesa_el_trabajo(self, motor, monkeypatch):
        trabajo_id = await _encolar(motor)
        # El trabajador abre su motor una sola vez: el mismo engine falla tres
        # veces y despues responde, como un pool con `pool_pre_ping` que reconecta.
        intermitente = _MotorDePrueba(motor, _EngineIntermitente(motor.engine, *_caidas()))
        monkeypatch.setattr(tukit_comun.bd, "crear_motor", lambda _servicio: intermitente)
        _sin_red(monkeypatch, trabajador)
        esperas: list[float] = []

        with pytest.raises(_Corte):
            await trabajador._bucle(_INTERVALO, dormir=_dormir_que_corta(esperas))

        assert esperas == [1.0, 2.0, 4.0, _INTERVALO]
        async with motor.engine.begin() as conexion:
            estado = await conexion.scalar(
                select(trabajos.TRABAJO.c.estado).where(trabajos.TRABAJO.c.id == trabajo_id)
            )
        assert estado == EstadoTrabajo.ESPERA_REVISION.value

    async def test_un_error_de_programacion_lo_sigue_terminando(self, motor, monkeypatch):
        intermitente = _MotorDePrueba(motor, _EngineIntermitente(motor.engine, ValueError("bug")))
        monkeypatch.setattr(tukit_comun.bd, "crear_motor", lambda _servicio: intermitente)
        _sin_red(monkeypatch, trabajador)
        esperas: list[float] = []

        with pytest.raises(ValueError):
            await trabajador._bucle(_INTERVALO, dormir=_dormir_que_corta(esperas))

        assert esperas == []

    def test_configura_el_log_al_arrancar(self, monkeypatch):
        titulos: list[str] = []
        monkeypatch.setattr(trabajador, "configurar_registro", titulos.append)

        async def _nada() -> int:
            return 0

        monkeypatch.setattr(trabajador, "correr_una_vez", _nada)

        assert trabajador.main([]) == 0
        assert titulos == ["inteligencia-trabajador"]
