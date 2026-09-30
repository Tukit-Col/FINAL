"""El `BrokerSink` y la degradacion honesta del entorno (ADR 0022).

No se levanta RabbitMQ aqui: se fija (1) que sin `RABBITMQ_URL` el sink es
`None` —la tesis corre sin broker—, (2) que con la URL es un `BrokerSink`, y
(3) que `publicar` usa el TIPO del evento como routing key sobre un exchange
falso (el `connect_robust` real necesitaria un broker vivo).
"""

from __future__ import annotations

from types import SimpleNamespace

from tukit_comun.broker import BrokerSink, sink_desde_entorno


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
    sink._exchange = ExchangeFalso()  # salta connect_robust: no hay broker

    fila = SimpleNamespace(id=7, tipo="pedido_pagado", carga={"pedido_id": "p1", "correlacion_id": "c1"})
    await sink.publicar(fila)

    assert len(publicados) == 1
    routing_key, cuerpo = publicados[0]
    assert routing_key == "pedido_pagado"
    assert b"p1" in cuerpo
