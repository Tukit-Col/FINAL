"""NFR-MAN-01: lo que `es_caida_transitoria` y `bucle_resiliente` prometen en el ADR 0041 y
`test_bucle_resiliente.py` no fija.

`test_bucle_resiliente.py` (del equipo) cubre la clasificacion de cada error suelto, las esperas
1, 2, 4 con el tope que se le pasa, que la espera vuelve a empezar y que un bug termina el bucle.
Aqui se prueba el resto de lo que dice el ADR:

- **La cadena de causas.** `_eslabones` sigue el `.orig` de SQLAlchemy y el `raise ... from`,
  tambien uno dentro del otro; no sigue `__context__` (decision 3 del ADR); y una cadena con un
  ciclo termina.
- **El WARNING.** El ADR dice que lleva «el proceso, el intento, la espera y la excepcion»: se
  mira el numero del intento y los segundos de la espera, no solo el nombre del proceso.
- **Los numeros por omision.** Sin `espera_inicial` ni `espera_tope`, 1 s y 30 s.
- **Apagar durante una caida.** Una cancelacion mientras el bucle espera para reintentar sale del
  bucle: un proceso que se detiene con la base caida no se queda colgado.
- **La credencial mala de RabbitMQ.** «Lo que queda abierto» del ADR: el `AuthenticationError` de
  aiormq es un `OSError`, asi que el bucle reintenta con WARNING en vez de morir. Se caracteriza
  como limitacion conocida (ADR 0041), no como hallazgo: si el producto cambia, esta prueba lo
  dice.

Ningun sleep real: `dormir` anota las esperas.
"""

from __future__ import annotations

import asyncio
import logging
import re

import aiormq.exceptions
import pytest
from sqlalchemy import exc
from tukit_comun.resiliencia import bucle_resiliente, es_caida_transitoria

pytestmark = pytest.mark.nfr("NFR-MAN-01")


class _Corte(Exception):
    """Lo lanza el `dormir` de la prueba para salir del bucle infinito."""


class _Vuelta:
    """Una vuelta que falla con los errores dados, en orden, y despues responde."""

    def __init__(self, *errores: BaseException | None) -> None:
        self.errores = list(errores)
        self.llamadas = 0

    async def __call__(self) -> None:
        self.llamadas += 1
        if self.errores:
            error = self.errores.pop(0)
            if error is not None:
                raise error


def _dormir(esperas: list[float], *, intervalo: float):
    """Anota cada espera y corta el bucle en la primera espera de `intervalo` (la vuelta buena)."""

    async def dormir(segundos: float) -> None:
        esperas.append(segundos)
        if segundos == intervalo:
            raise _Corte

    return dormir


def _lanzado_mientras(error: BaseException, manejando: BaseException) -> BaseException:
    """`error` lanzado dentro del `except` de `manejando`: queda en `__context__`, no en `__cause__`."""
    try:
        try:
            raise manejando
        except type(manejando):
            raise error  # noqa: B904 - es justo lo que se prueba: sin `from`
    except type(error) as lanzado:
        return lanzado


# --- La cadena de causas ----------------------------------------------------


def test_un_bug_lanzado_mientras_se_manejaba_una_caida_no_es_caida():
    error = _lanzado_mientras(ValueError("bug en el manejo"), ConnectionRefusedError(61, "refused"))

    assert isinstance(error.__context__, ConnectionRefusedError)
    assert error.__cause__ is None
    assert es_caida_transitoria(error) is False


def test_la_causa_explicita_si_cuenta_aunque_el_contexto_tambien_exista():
    error = _lanzado_mientras(RuntimeError("envoltorio"), ValueError("otro"))
    error.__cause__ = ConnectionRefusedError(61, "refused")

    assert es_caida_transitoria(error) is True


def test_el_orig_de_sqlalchemy_dentro_de_un_raise_from():
    # Lo que deja un repositorio que envuelve el error del motor: RuntimeError <- DBAPIError <- OSError.
    dbapi = exc.DBAPIError("SELECT 1", {}, ConnectionResetError(54, "reset"), connection_invalidated=False)
    envuelto = RuntimeError("no se pudo leer la bandeja")
    envuelto.__cause__ = dbapi

    assert es_caida_transitoria(envuelto) is True


def test_un_orig_que_no_es_excepcion_no_corta_la_cadena():
    # `.orig` que no es una excepcion: se sigue por `__cause__`.
    error = RuntimeError("envoltorio")
    error.orig = "texto del driver"  # type: ignore[attr-defined]
    error.__cause__ = ConnectionRefusedError()

    assert es_caida_transitoria(error) is True


def test_una_cadena_con_un_ciclo_termina():
    uno, otro = RuntimeError("uno"), ValueError("otro")
    uno.__cause__, otro.__cause__ = otro, uno

    assert es_caida_transitoria(uno) is False


def test_un_ciclo_con_una_caida_dentro_es_caida():
    uno, caida = RuntimeError("uno"), ConnectionRefusedError()
    uno.__cause__, caida.__cause__ = caida, uno

    assert es_caida_transitoria(uno) is True


# --- El WARNING y los numeros por omision ------------------------------------


async def test_el_warning_lleva_el_intento_y_la_espera(caplog):
    vuelta = _Vuelta(ConnectionRefusedError(61, "refused"), ConnectionRefusedError(61, "refused"))
    caplog.set_level(logging.WARNING, logger="tukit_comun.resiliencia")

    with pytest.raises(_Corte):
        await bucle_resiliente(
            vuelta, intervalo=5.0, proceso="operacion-repartidor", dormir=_dormir([], intervalo=5.0)
        )

    mensajes = [r.getMessage() for r in caplog.records if r.name == "tukit_comun.resiliencia"]
    assert len(mensajes) == 2
    intentos = [int(re.search(r"intento (\d+)", m).group(1)) for m in mensajes]
    esperas = [int(re.search(r"reintenta en (\d+) s", m).group(1)) for m in mensajes]
    assert intentos == [1, 2]
    assert esperas == [1, 2]
    assert all("operacion-repartidor" in m and "ConnectionRefusedError" in m for m in mensajes)


async def test_sin_espera_inicial_ni_tope_son_un_segundo_y_treinta():
    vuelta = _Vuelta(*[ConnectionRefusedError() for _ in range(8)])
    esperas: list[float] = []

    with pytest.raises(_Corte):
        await bucle_resiliente(
            vuelta, intervalo=5.0, proceso="prueba", dormir=_dormir(esperas, intervalo=5.0)
        )

    assert esperas == [1.0, 2.0, 4.0, 8.0, 16.0, 30.0, 30.0, 30.0, 5.0]
    assert vuelta.llamadas == 9


async def test_cancelar_mientras_espera_el_reintento_sale_del_bucle():
    vuelta = _Vuelta(*[ConnectionRefusedError() for _ in range(5)])
    esperas: list[float] = []

    async def dormir(segundos: float) -> None:
        esperas.append(segundos)
        if len(esperas) == 2:
            raise asyncio.CancelledError

    with pytest.raises(asyncio.CancelledError):
        await bucle_resiliente(vuelta, intervalo=5.0, proceso="prueba", dormir=dormir)

    assert esperas == [1.0, 2.0]
    assert vuelta.llamadas == 2


# --- La credencial mala de RabbitMQ (limitacion conocida, ADR 0041) -----------


@pytest.mark.parametrize(
    "error",
    [
        # Lo que da aiormq cuando el broker no ofrece el mecanismo pedido.
        aiormq.exceptions.AuthenticationError(["AMQPLAIN", "PLAIN"], ["PLAIN"]),
        # Lo que da aiormq cuando el broker cierra con 403 (usuario o clave malos).
        aiormq.exceptions.ProbableAuthenticationError("ACCESS_REFUSED - Login was refused"),
    ],
    ids=lambda e: type(e).__name__,
)
def test_una_credencial_mala_de_rabbitmq_cuenta_como_caida(error):
    assert isinstance(error, OSError)
    assert es_caida_transitoria(error) is True


async def test_con_una_credencial_mala_el_bucle_reintenta_con_warning_y_no_muere(caplog):
    malas = [aiormq.exceptions.ProbableAuthenticationError("ACCESS_REFUSED") for _ in range(7)]
    vuelta = _Vuelta(*malas)
    esperas: list[float] = []
    caplog.set_level(logging.WARNING, logger="tukit_comun.resiliencia")

    with pytest.raises(_Corte):
        await bucle_resiliente(
            vuelta, intervalo=5.0, proceso="operacion-repartidor", dormir=_dormir(esperas, intervalo=5.0)
        )

    avisos = [r for r in caplog.records if r.name == "tukit_comun.resiliencia"]
    assert esperas[:-1] == [1.0, 2.0, 4.0, 8.0, 16.0, 30.0, 30.0]
    assert len(avisos) == 7
    assert all(
        r.levelno == logging.WARNING and "ProbableAuthenticationError" in r.getMessage() for r in avisos
    )
