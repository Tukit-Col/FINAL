from __future__ import annotations

import pytest
from tukit_comun.resiliencia import (
    CircuitoAbierto,
    Disyuntor,
    disyuntor_de,
    llamada_protegida,
    reintentar_get,
)


@pytest.mark.parametrize("metodo", ["POST", "put", "PATCH", "DELETE"])
def test_rechaza_reintentable_en_no_get(metodo):
    with pytest.raises(ValueError):
        llamada_protegida("catalogo", metodo=metodo, reintentable=True)


@pytest.mark.parametrize(("metodo", "reintentable"), [("GET", True), ("get", True), ("POST", False)])
def test_lo_permitido_devuelve_el_disyuntor_compartido_del_destino(metodo, reintentable):
    disyuntor = llamada_protegida("catalogo", metodo=metodo, reintentable=reintentable)
    assert disyuntor is disyuntor_de("catalogo")
    assert disyuntor.destino == "catalogo"


async def test_el_disyuntor_abre_tras_el_umbral():
    d = Disyuntor("catalogo", umbral=3, ttl=30.0, reloj=lambda: 0.0)

    async def cae():
        async with d:
            raise RuntimeError("destino caido")

    for _ in range(3):
        with pytest.raises(RuntimeError):
            await cae()

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

    ahora["t"] = 31.0

    async with d:
        pass

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
    assert intentos["n"] == 3


async def test_reintentar_get_no_reintenta_circuito_abierto():
    intentos = {"n": 0}

    @reintentar_get
    async def lectura():
        intentos["n"] += 1
        raise CircuitoAbierto("abierto")

    with pytest.raises(CircuitoAbierto):
        await lectura()
    assert intentos["n"] == 1


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

    ahora["t"] = 31.0
    with pytest.raises(RuntimeError):
        await cae()

    ahora["t"] = 31.5
    with pytest.raises(CircuitoAbierto):
        await cae()
