"""Pruebas del helper de resiliencia (ADR 0020).

Tres invariantes que no se negocian:

1. **Rechaza retry en escrituras.** `llamada_protegida(..., reintentable=True)`
   sobre un metodo que NO es GET es un error de programacion: un reintento ciego
   de un POST es un doble cobro, el modo de falla mas caro. El helper lo rechaza
   con `ValueError` al construirse, no en tiempo de ejecucion.
2. **El disyuntor abre tras N fallos** y deja de golpear al destino caido;
   rechaza en el acto con `CircuitoAbierto` mientras esta abierto.
3. **Tras el TTL prueba de nuevo** (medio-abierto): un exito lo cierra, un fallo
   lo reabre.
"""

from __future__ import annotations

import pytest
from tukit_comun.resiliencia import (
    CircuitoAbierto,
    Disyuntor,
    llamada_protegida,
    reintentar_get,
)


def test_rechaza_reintentable_en_no_get():
    with pytest.raises(ValueError):
        llamada_protegida("catalogo", metodo="POST", reintentable=True)


def test_permite_reintentable_en_get():
    # No debe levantar.
    llamada_protegida("catalogo", metodo="GET", reintentable=True)


async def test_el_disyuntor_abre_tras_el_umbral():
    d = Disyuntor("catalogo", umbral=3, ttl=30.0, reloj=lambda: 0.0)

    async def cae():
        async with d:
            raise RuntimeError("destino caido")

    for _ in range(3):
        with pytest.raises(RuntimeError):
            await cae()

    # Cuarta llamada: el circuito ya esta abierto, rechaza sin tocar al destino.
    with pytest.raises(CircuitoAbierto):
        await cae()


async def test_tras_el_ttl_prueba_y_un_exito_lo_cierra():
    ahora = {"t": 0.0}
    d = Disyuntor("catalogo", umbral=2, ttl=30.0, reloj=lambda: ahora["t"])

    async def cae():
        async with d:
            raise RuntimeError("caido")

    for _ in range(2):
        with pytest.raises(RuntimeError):
            await cae()
    with pytest.raises(CircuitoAbierto):
        await cae()

    # Pasa el TTL: el circuito pasa a medio-abierto y deja pasar una prueba.
    ahora["t"] = 31.0

    async with d:
        pass  # exito

    # Cerrado de nuevo: una llamada normal pasa.
    async with d:
        pass


async def test_reintentar_get_insiste_hasta_tres_veces_y_luego_relanza():
    intentos = {"n": 0}

    @reintentar_get
    async def lectura_inestable():
        intentos["n"] += 1
        raise TimeoutError("red lenta")

    with pytest.raises(TimeoutError):
        await lectura_inestable()
    assert intentos["n"] == 3  # 1 intento + 2 reintentos


async def test_reintentar_get_no_reintenta_circuito_abierto():
    intentos = {"n": 0}

    @reintentar_get
    async def lectura():
        intentos["n"] += 1
        raise CircuitoAbierto("abierto")

    with pytest.raises(CircuitoAbierto):
        await lectura()
    assert intentos["n"] == 1  # no insiste si el circuito ya esta abierto


async def test_un_fallo_en_medio_abierto_reabre():
    ahora = {"t": 0.0}
    d = Disyuntor("catalogo", umbral=1, ttl=30.0, reloj=lambda: ahora["t"])

    async def cae():
        async with d:
            raise RuntimeError("caido")

    with pytest.raises(RuntimeError):
        await cae()
    with pytest.raises(CircuitoAbierto):
        await cae()

    ahora["t"] = 31.0  # medio-abierto
    with pytest.raises(RuntimeError):
        await cae()  # la prueba falla -> reabre

    ahora["t"] = 31.5  # aun dentro del nuevo TTL
    with pytest.raises(CircuitoAbierto):
        await cae()
