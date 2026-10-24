"""Dos puertas con su propia conexion comparten el contador (ADR 0047).

Es lo que el conteo en memoria no da: con dos replicas del gateway, cada una
contaria su mitad y el cupo real seria el doble. Aqui las dos tienen su
`ClienteRedis` contra el Redis de `TUKIT_PRUEBAS_REDIS_URL`, y las peticiones se
alternan entre ellas.
"""

from __future__ import annotations

import httpx
import pytest
from tukit_comun.cache import usar_cliente
from tukit_comun.pruebas_redis import clientes_de_prueba, url_de_pruebas
from tukit_gateway.api import app

redis_asincrono = pytest.importorskip("redis.asyncio")

pytestmark = pytest.mark.redis


async def test_dos_puertas_comparten_el_contador(monkeypatch):
    monkeypatch.setenv("TUKIT_LIMITE_GENERAL_IP", "4")
    estados: list[int] = []

    async with clientes_de_prueba(2) as (una, otra):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app, client=("127.0.0.1", 50_000)), base_url="http://prueba"
        ) as http:
            for i in range(6):
                usar_cliente(una if i % 2 == 0 else otra)
                estados.append((await http.get("/v1/inventado")).status_code)
            ultima = await http.get("/v1/inventado")

        assert not una.degradado and not otra.degradado
        conexion = redis_asincrono.from_url(url_de_pruebas())
        try:
            claves = [c.decode() async for c in conexion.scan_iter(match=una.prefijo + "*")]
            cuenta = int(await conexion.get(claves[0]))
            resta = await conexion.pttl(claves[0])
        finally:
            await conexion.aclose()

    # Cada puerta vio tres peticiones, por debajo del tope de cuatro; juntas, seis.
    assert estados == [404, 404, 404, 404, 429, 429]
    assert ultima.status_code == 429
    assert 1 <= int(ultima.headers["Retry-After"]) <= 60
    assert len(claves) == 1
    assert claves[0].startswith(una.prefijo + "limite:general:v1:ip:")
    assert cuenta == 7
    assert 0 < resta <= 60_000
