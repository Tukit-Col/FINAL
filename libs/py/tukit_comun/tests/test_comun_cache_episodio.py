"""NFR-MAN-01: el episodio de la cache (ADR 0047) contra un socket que acepta y no responde.

`test_cache.py` (del equipo) fija el episodio con el doble en memoria: `caido` levanta al momento y
`demora` duerme dentro del doble. Lo que el doble no puede mostrar es el `MotorRedis` de verdad,
con redis-py, frente al Redis enfermo del que habla el ADR: el puerto acepta la conexion y nunca
contesta. Es lo que ve un servicio cuando Redis se cuelga sin cerrar el puerto, y es donde importa
la espera de 250 ms (`TUKIT_REDIS_ESPERA_MS`) y la pausa de 5 s (`PAUSA_TRAS_FALLO`):

- la primera lectura se rinde en unos 250 ms y da «no esta»;
- durante la pausa, ni la lectura ni el conteo vuelven a tocar el socket, y el conteo sigue en
  memoria;
- pasada la pausa, el cliente vuelve a probar y se vuelve a rendir en la espera;
- el episodio deja un solo WARNING, sin la clave ni la contrasena de la URL.

El servidor escucha en 127.0.0.1, en un puerto que elige el sistema, y nunca escribe: no hace falta
un Redis de verdad y nada sale de la maquina. El reloj del cliente es falso (la pausa avanza cuando
la prueba lo dice); la espera de 250 ms es la de asyncio y se mide con el reloj de verdad.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import AsyncIterator

import pytest
from tukit_comun.cache import ESPERA_POR_OMISION_MS, PAUSA_TRAS_FALLO, ClienteRedis, MotorRedis

pytestmark = pytest.mark.nfr("NFR-MAN-01")

pytest.importorskip("redis")

ESPERA = ESPERA_POR_OMISION_MS / 1000
CLAVE = "limite:general:v1:token:huella-de-un-token-ficticio"
CONTRASENA = "clave-ficticia-de-qa"


class Reloj:
    def __init__(self) -> None:
        self.ahora = 1000.0

    def __call__(self) -> float:
        return self.ahora

    def avanzar(self, segundos: float) -> None:
        self.ahora += segundos


class SocketMudo:
    """Un servidor TCP que acepta, lee lo que le mandan y nunca contesta."""

    def __init__(self) -> None:
        self.conexiones = 0
        self.recibido = 0
        self._soltar = asyncio.Event()
        self._servidor: asyncio.Server | None = None
        self.puerto = 0

    async def _atender(self, lector: asyncio.StreamReader, escritor: asyncio.StreamWriter) -> None:
        self.conexiones += 1
        leer = asyncio.ensure_future(self._leer(lector))
        await self._soltar.wait()
        leer.cancel()
        escritor.close()

    async def _leer(self, lector: asyncio.StreamReader) -> None:
        while datos := await lector.read(4096):
            self.recibido += len(datos)

    async def abrir(self) -> None:
        self._servidor = await asyncio.start_server(self._atender, "127.0.0.1", 0)
        self.puerto = self._servidor.sockets[0].getsockname()[1]

    async def cerrar(self) -> None:
        self._soltar.set()
        if self._servidor is not None:
            self._servidor.close()
            await self._servidor.wait_closed()

    def huella(self) -> tuple[int, int]:
        return self.conexiones, self.recibido


@pytest.fixture()
async def mudo() -> AsyncIterator[SocketMudo]:
    servidor = SocketMudo()
    await servidor.abrir()
    yield servidor
    await servidor.cerrar()


@pytest.fixture()
def reloj() -> Reloj:
    return Reloj()


@pytest.fixture()
async def cliente(mudo: SocketMudo, reloj: Reloj) -> AsyncIterator[ClienteRedis]:
    motor = MotorRedis(f"redis://:{CONTRASENA}@127.0.0.1:{mudo.puerto}/0", espera=ESPERA)
    cliente = ClienteRedis(motor, espera=ESPERA, pausa=PAUSA_TRAS_FALLO, reloj=reloj)
    yield cliente
    await cliente.cerrar()


async def _cronometrar(corrutina) -> tuple[object, float]:
    inicio = time.monotonic()
    resultado = await corrutina
    return resultado, time.monotonic() - inicio


def test_los_numeros_son_los_del_adr():
    assert (ESPERA, PAUSA_TRAS_FALLO) == (0.25, 5.0)


async def test_la_primera_lectura_se_rinde_en_la_espera_y_da_no_esta(cliente, mudo, record_property):
    leido, segundos = await _cronometrar(cliente.leer("vector", CLAVE))

    record_property("segundos_primera_lectura", round(segundos, 3))
    assert leido is None
    assert 0.2 <= segundos < 1.0
    assert cliente.degradado
    # Llego a conectarse y a mandar algo: el socket acepta, solo que no contesta.
    assert mudo.conexiones >= 1 and mudo.recibido > 0


async def test_durante_la_pausa_no_vuelve_a_tocar_el_socket_y_cuenta_en_memoria(cliente, mudo, reloj):
    await cliente.leer("vector", CLAVE)
    antes = mudo.huella()

    reloj.avanzar(PAUSA_TRAS_FALLO - 0.1)
    leido, al_leer = await _cronometrar(cliente.leer("vector", CLAVE))
    contado, al_contar = await _cronometrar(cliente.contar([(CLAVE, 60), (CLAVE, 60)]))
    await asyncio.sleep(0.05)

    assert leido is None
    # La cuenta sigue en memoria; lo que falta de la ventana puede salir 60 001 ms por el redondeo.
    assert [cuenta for cuenta, _ in contado] == [1, 2]
    assert all(abs(resta - 60_000) <= 1 for _, resta in contado)
    assert al_leer < 0.1 and al_contar < 0.1
    assert mudo.huella() == antes


async def test_pasada_la_pausa_vuelve_a_probar_y_se_vuelve_a_rendir(cliente, mudo, reloj, record_property):
    await cliente.leer("vector", CLAVE)
    antes = mudo.huella()

    reloj.avanzar(PAUSA_TRAS_FALLO + 0.1)
    leido, segundos = await _cronometrar(cliente.leer("vector", CLAVE))

    record_property("segundos_tras_la_pausa", round(segundos, 3))
    assert leido is None
    assert 0.2 <= segundos < 1.0
    assert mudo.huella() != antes
    assert cliente.degradado


async def test_el_guardado_tampoco_espera_mas_que_la_espera(cliente):
    _, segundos = await _cronometrar(cliente.guardar("percepcion", CLAVE, b"valor", 60))

    assert segundos < 1.0
    assert cliente.degradado


async def test_un_solo_warning_por_episodio_sin_la_clave_ni_la_contrasena(cliente, reloj, caplog):
    caplog.set_level(logging.DEBUG)

    for _ in range(3):
        await cliente.leer("vector", CLAVE)
        await cliente.contar([(CLAVE, 60)])
        reloj.avanzar(PAUSA_TRAS_FALLO + 1)

    avisos = [r for r in caplog.records if r.name == "tukit_comun.cache" and r.levelno == logging.WARNING]
    assert len(avisos) == 1
    # El tipo puede ser el `TimeoutError` de asyncio o el de redis-py: los dos se rinden en 250 ms.
    assert avisos[0].getMessage().startswith("Redis no responde (")
    for dato in (CLAVE, "huella-de-un-token-ficticio", CONTRASENA):
        assert dato not in caplog.text
