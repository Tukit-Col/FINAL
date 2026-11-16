"""De donde sale la IP del cliente que cuenta el limite (ADR 0047).

Solo se cree `X-Forwarded-For` si la conexion viene de un proxy de confianza
(`TUKIT_PROXIES_CONFIANZA`), y solo la puerta decide: uvicorn se lanza sin
leer esa cabecera, o confiaria en 127.0.0.1 y cada IP inventada tendria cupo.
"""

from __future__ import annotations

import ipaddress
import logging
import sys

import httpx
import pytest
from _ayudas_gateway import codigos, http_de
from tukit_gateway import api, limite

CONFIANZA = (ipaddress.ip_network("127.0.0.1/32"), ipaddress.ip_network("::1/128"))


@pytest.mark.parametrize(
    ("conexion", "reenviada", "esperada"),
    [
        # Sin cabecera, la de la conexion.
        ("127.0.0.1", None, "127.0.0.1"),
        ("203.0.113.9", None, "203.0.113.9"),
        # Desde un proxy de confianza: la primera sin confianza desde la derecha.
        ("127.0.0.1", "198.51.100.7", "198.51.100.7"),
        ("127.0.0.1", "10.9.9.9, 198.51.100.7", "198.51.100.7"),
        ("127.0.0.1", "198.51.100.7, 127.0.0.1", "198.51.100.7"),
        ("::1", "2001:db8::5", "2001:db8::5"),
        # Todas de confianza: la de mas a la izquierda.
        ("127.0.0.1", "127.0.0.1, ::1", "127.0.0.1"),
        # Algo que no es una IP corta el recorrido: vale la ultima de confianza.
        ("127.0.0.1", "198.51.100.7, basura, 127.0.0.1", "127.0.0.1"),
        ("127.0.0.1", "198.51.100.7, unknown", "127.0.0.1"),
        # Las entradas vacias no cortan nada.
        ("127.0.0.1", "198.51.100.7, ", "198.51.100.7"),
        # Desde una conexion sin confianza, la cabecera la escribio el cliente.
        ("203.0.113.9", "198.51.100.7", "203.0.113.9"),
        ("203.0.113.9", "127.0.0.1", "203.0.113.9"),
        # Una IPv4 escrita como IPv6 es la misma IPv4.
        ("::ffff:127.0.0.1", "198.51.100.7", "198.51.100.7"),
        ("127.0.0.1", "::ffff:198.51.100.7", "198.51.100.7"),
        # Sin conexion conocida.
        (None, "198.51.100.7", "desconocida"),
    ],
)
def test_la_ip_del_cliente(conexion, reenviada, esperada):
    assert limite.ip_del_cliente(conexion, reenviada, CONFIANZA) == esperada


def test_los_proxies_de_confianza_se_configuran_con_redes(monkeypatch, caplog):
    monkeypatch.setenv("TUKIT_PROXIES_CONFIANZA", "127.0.0.1, 172.16.0.0/12, no-es-una-red")
    with caplog.at_level(logging.WARNING):
        redes = limite.proxies_de_confianza()

    assert redes == (ipaddress.ip_network("127.0.0.1/32"), ipaddress.ip_network("172.16.0.0/12"))
    assert "no-es-una-red" in caplog.text
    assert limite.ip_del_cliente("172.18.0.1", "198.51.100.7", redes) == "198.51.100.7"


async def test_x_forwarded_for_desde_un_proxy_de_confianza_separa_a_los_clientes(atras, redis, monkeypatch):
    monkeypatch.setenv("TUKIT_LIMITE_GENERAL_IP", "2")
    async with http_de(("127.0.0.1", 50_000)) as http:
        de_una = await codigos(http, 3, "GET", "/v1/colegios", headers={"X-Forwarded-For": "198.51.100.7"})
        de_otra = await codigos(http, 2, "GET", "/v1/colegios", headers={"X-Forwarded-For": "198.51.100.8"})

    assert de_una == [200, 200, 429]
    assert de_otra == [200, 200]


async def test_x_forwarded_for_desde_un_cliente_cualquiera_no_cambia_la_ip(atras, redis, monkeypatch):
    monkeypatch.setenv("TUKIT_LIMITE_GENERAL_IP", "2")
    async with http_de(("203.0.113.9", 50_000)) as http:
        estados = [
            (await http.get("/v1/colegios", headers={"X-Forwarded-For": f"198.51.100.{i}"})).status_code
            for i in range(3)
        ]

    assert estados == [200, 200, 429]


def _como_se_lanza(monkeypatch) -> tuple[tuple, dict]:
    """Con que argumentos lanza `api.main` a uvicorn, sin lanzarlo."""
    lanzada: list[tuple[tuple, dict]] = []

    class Uvicorn:
        @staticmethod
        def run(*args, **kwargs) -> None:
            lanzada.append((args, kwargs))

    with monkeypatch.context() as m:
        m.setitem(sys.modules, "uvicorn", Uvicorn)
        assert api.main(["--puerto", "18999"]) == 0
    assert len(lanzada) == 1
    return lanzada[0]


def test_la_puerta_se_lanza_sin_que_uvicorn_lea_x_forwarded_for(monkeypatch):
    _, opciones = _como_se_lanza(monkeypatch)

    assert opciones["proxy_headers"] is False


async def test_solo_la_puerta_decide_de_quien_es_x_forwarded_for(atras, redis, monkeypatch):
    # Con la pila que arma uvicorn al lanzar la puerta. Si uvicorn leyera la
    # cabecera, confiaria en 127.0.0.1 aunque `TUKIT_PROXIES_CONFIANZA` no, y
    # cada IP inventada tendria su cupo.
    uvicorn = pytest.importorskip("uvicorn")
    args, opciones = _como_se_lanza(monkeypatch)
    # Sin `log_config`, uvicorn reconfiguraria el registro de toda la corrida.
    configuracion = uvicorn.Config(*args, **{**opciones, "log_config": None})
    configuracion.load()
    monkeypatch.setenv("TUKIT_PROXIES_CONFIANZA", "192.0.2.1")
    monkeypatch.setenv("TUKIT_LIMITE_GENERAL_IP", "5")

    transporte = httpx.ASGITransport(app=configuracion.loaded_app, client=("127.0.0.1", 50_000))
    async with httpx.AsyncClient(transport=transporte, base_url="http://prueba") as http:
        estados = [
            (await http.get("/v1/colegios", headers={"X-Forwarded-For": f"198.51.100.{i}"})).status_code
            for i in range(6)
        ]

    assert estados == [200] * 5 + [429]
