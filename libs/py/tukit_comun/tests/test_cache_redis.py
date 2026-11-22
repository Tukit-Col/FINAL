from __future__ import annotations

import asyncio

import pytest
from tukit_comun.cache import responde
from tukit_comun.pruebas_redis import borrar_prefijo, clientes_de_prueba, prefijo_de_prueba, url_de_pruebas

redis_asincrono = pytest.importorskip("redis.asyncio")

pytestmark = pytest.mark.redis

URL = url_de_pruebas()


async def _ttl_ms(clave: str) -> int:
    conexion = redis_asincrono.from_url(URL)
    try:
        return int(await conexion.pttl(clave))
    finally:
        await conexion.aclose()


async def test_guarda_y_lee_con_el_vencimiento_pedido():
    async with clientes_de_prueba() as (cliente,):
        await cliente.guardar_varias("vector", {"a": b"\x00\x01", "c": b"tres"}, 120)

        assert await cliente.leer_varias("vector", ["a", "b", "c"]) == [b"\x00\x01", None, b"tres"]
        assert 119_000 < await _ttl_ms(cliente.prefijo + "a") <= 120_000
        assert not cliente.degradado


async def test_el_conteo_suma_y_pone_la_ventana():
    async with clientes_de_prueba() as (cliente,):
        primera = await cliente.contar([("token:x", 60), ("ip:y", 600)])
        segunda = await cliente.contar([("token:x", 60), ("ip:y", 600)])

        assert [cuenta for cuenta, _ in primera] == [1, 1]
        assert [cuenta for cuenta, _ in segunda] == [2, 2]
        assert 59_000 < segunda[0][1] <= 60_000
        assert 599_000 < segunda[1][1] <= 600_000


async def test_la_ventana_vence_y_la_cuenta_vuelve_a_empezar():
    async with clientes_de_prueba() as (cliente,):
        await cliente.contar([("token:x", 1)])
        await cliente.contar([("token:x", 1)])
        await asyncio.sleep(1.2)

        assert (await cliente.contar([("token:x", 1)]))[0][0] == 1


async def test_dos_clientes_comparten_la_cuenta():
    async with clientes_de_prueba(2) as (uno, otro):
        await uno.contar([("ip:y", 60)])
        await otro.contar([("ip:y", 60)])

        assert (await uno.contar([("ip:y", 60)]))[0][0] == 3


async def test_el_conteo_es_atomico_con_peticiones_a_la_vez():
    async with clientes_de_prueba(2) as (uno, otro):
        tareas = [(uno if i % 2 else otro).contar([("ip:y", 60)]) for i in range(100)]
        cuentas = sorted(resultado[0][0] for resultado in await asyncio.gather(*tareas))

        assert cuentas == list(range(1, 101))


async def test_una_clave_sin_vencimiento_lo_recupera_al_contar():
    async with clientes_de_prueba() as (cliente,):
        conexion = redis_asincrono.from_url(URL)
        try:
            await conexion.set(cliente.prefijo + "token:x", 5)
        finally:
            await conexion.aclose()

        cuenta, resta = (await cliente.contar([("token:x", 60)]))[0]

        assert cuenta == 6
        assert 59_000 < resta <= 60_000
        assert 59_000 < await _ttl_ms(cliente.prefijo + "token:x") <= 60_000


async def test_al_salir_no_queda_ninguna_clave():
    async with clientes_de_prueba() as (cliente,):
        prefijo = cliente.prefijo
        await cliente.guardar("vector", "a", b"1", 60)
        await cliente.contar([("ip:y", 60)])

    assert await borrar_prefijo(URL, prefijo) == 0


async def test_responde_y_borrar_prefijo_solo_toca_lo_suyo():
    assert await responde(URL) is None
    async with clientes_de_prueba() as (cliente,):
        ajeno = prefijo_de_prueba()
        conexion = redis_asincrono.from_url(URL)
        try:
            await conexion.set(ajeno + "a", 1, ex=60)
            await cliente.guardar("vector", "a", b"1", 60)

            assert await borrar_prefijo(URL, cliente.prefijo) == 1
            assert await conexion.get(ajeno + "a") == b"1"
        finally:
            await conexion.delete(ajeno + "a")
            await conexion.aclose()
