from __future__ import annotations

import asyncio
from types import SimpleNamespace

from tukit_comun.broker import BrokerSink, main, responde, sin_clave, sink_desde_entorno


def test_sin_url_no_hay_sink(monkeypatch):
    monkeypatch.delenv("RABBITMQ_URL", raising=False)
    assert sink_desde_entorno() is None


def test_con_url_es_brokersink(monkeypatch):
    monkeypatch.setenv("RABBITMQ_URL", "amqp://guest:guest@localhost/")
    sink = sink_desde_entorno()
    assert isinstance(sink, BrokerSink)
    assert sink.url == "amqp://guest:guest@localhost/"


async def test_publicar_usa_el_tipo_como_routing_key():
    publicados: list[tuple[str, bytes]] = []

    class ExchangeFalso:
        async def publish(self, mensaje, routing_key):
            publicados.append((routing_key, mensaje.body))

    sink = BrokerSink(url="amqp://x")
    sink._exchange = ExchangeFalso()

    fila = SimpleNamespace(id=7, tipo="pedido_pagado", carga={"pedido_id": "p1", "correlacion_id": "c1"})
    await sink.publicar(fila)

    assert len(publicados) == 1
    routing_key, cuerpo = publicados[0]
    assert routing_key == "pedido_pagado"
    assert b"p1" in cuerpo


class _ConexionFalsa:
    cerrada = False

    async def close(self):
        self.cerrada = True


async def test_responde_si_el_broker_acepta_la_conexion():
    conexion = _ConexionFalsa()

    async def conectar(url):
        return conexion

    assert await responde("amqp://x", conectar=conectar) is None
    assert conexion.cerrada


async def test_no_responde_si_rechaza_la_conexion():
    async def conectar(url):
        raise ConnectionRefusedError("Connection refused")

    motivo = await responde("amqp://x", conectar=conectar)
    assert motivo == "ConnectionRefusedError: Connection refused"


async def test_no_responde_si_no_saluda_a_tiempo():
    async def conectar(url):
        await asyncio.sleep(10)

    assert await responde("amqp://x", espera=0.01, conectar=conectar) == "no saludo en 0.01 s"


def test_sin_clave_tapa_la_contrasena():
    assert sin_clave("amqp://guest:guest@localhost:5672/") == "amqp://guest:***@localhost:5672/"
    assert sin_clave("amqp://localhost/") == "amqp://localhost/"


def test_main_sin_url_sale_con_2(monkeypatch):
    monkeypatch.delenv("RABBITMQ_URL", raising=False)
    assert main() == 2


def test_main_dice_si_responde_sin_mostrar_la_clave(monkeypatch, capsys):
    monkeypatch.setenv("RABBITMQ_URL", "amqp://guest:secreta@localhost:5672/")

    async def conectar(url):
        assert url == "amqp://guest:secreta@localhost:5672/"
        return _ConexionFalsa()

    assert main(conectar=conectar) == 0
    salida = capsys.readouterr()
    assert "responde en amqp://guest:***@localhost:5672/" in salida.out
    assert "secreta" not in salida.out + salida.err


def test_main_sale_con_1_si_no_responde(monkeypatch, capsys):
    monkeypatch.setenv("RABBITMQ_URL", "amqp://guest:secreta@localhost:5672/")

    async def conectar(url):
        raise OSError("sin ruta")

    assert main(conectar=conectar) == 1
    salida = capsys.readouterr()
    assert "no responde en amqp://guest:***@localhost:5672/ (OSError: sin ruta)" in salida.err
    assert "secreta" not in salida.out + salida.err
