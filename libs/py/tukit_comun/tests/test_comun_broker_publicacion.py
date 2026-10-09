"""NFR-MAN-01: el `BrokerSink` publica al exchange topic sin un broker vivo (ADR 0022).

Solo se sustituye `aio_pika.connect_robust` (la unica costura con la red); el
`Message`, `DeliveryMode` y `ExchangeType` son los reales de la libreria, asi que
se verifica que lo que el sink arma es aceptado por `aio-pika` y con que
propiedades sale: persistente, JSON, con el `correlation_id` en la cabecera AMQP
y el TIPO del evento como routing key.

Importa porque el broker es un upgrade de entrega encima del outbox: si publicar
pierde la correlacion o el tipo, el consumidor no puede enrutar ni re-vincular el
hilo de la peticion; y si una conexion se abre por evento, un drenador de vida
larga agota los sockets.
"""

from __future__ import annotations

import json
import uuid
from types import SimpleNamespace
from typing import Any

import aio_pika
import pytest
from tukit_comun.broker import EXCHANGE, BrokerSink, sink_desde_entorno, url_broker

pytestmark = pytest.mark.nfr("NFR-MAN-01")


class ExchangeFalso:
    def __init__(self) -> None:
        self.publicados: list[tuple[str, aio_pika.Message]] = []

    async def publish(self, mensaje: aio_pika.Message, routing_key: str) -> None:
        self.publicados.append((routing_key, mensaje))


class CanalFalso:
    def __init__(self) -> None:
        self.exchange = ExchangeFalso()
        self.declarados: list[tuple[str, Any, bool]] = []

    async def declare_exchange(self, nombre: str, tipo: Any, *, durable: bool) -> ExchangeFalso:
        self.declarados.append((nombre, tipo, durable))
        return self.exchange


class ConexionFalsa:
    def __init__(self) -> None:
        self.canal = CanalFalso()
        self.cerrada = False

    async def channel(self) -> CanalFalso:
        return self.canal

    async def close(self) -> None:
        self.cerrada = True


@pytest.fixture
def broker(monkeypatch: pytest.MonkeyPatch) -> SimpleNamespace:
    """Sustituye la conexion robusta por una falsa y cuenta cuantas se abren."""
    estado = SimpleNamespace(conexiones=[], urls=[], caida=False)

    async def connect_robust(url: str, *args: Any, **kwargs: Any) -> ConexionFalsa:
        estado.urls.append(url)
        if estado.caida:
            raise ConnectionError("broker caido")
        conexion = ConexionFalsa()
        estado.conexiones.append(conexion)
        return conexion

    monkeypatch.setattr(aio_pika, "connect_robust", connect_robust)
    return estado


def _fila(**kw: Any) -> SimpleNamespace:
    base = {"id": 41, "tipo": "pedido_pagado", "carga": {"pedido_id": "p1", "correlacion_id": "req-7"}}
    return SimpleNamespace(**{**base, **kw})


class TestLaConexionSeAbreUnaVezYSeDeclaraElExchangeTopic:
    async def test_declara_el_exchange_topic_durable_con_el_nombre_unico_del_monorepo(self, broker):
        sink = BrokerSink(url="amqp://invitado@broker.example.test/")

        await sink.publicar(_fila())

        assert broker.urls == ["amqp://invitado@broker.example.test/"]
        assert broker.conexiones[0].canal.declarados == [("tukit.eventos", aio_pika.ExchangeType.TOPIC, True)]
        assert EXCHANGE == "tukit.eventos"

    async def test_reusa_la_conexion_entre_publicaciones(self, broker):
        sink = BrokerSink(url="amqp://x")

        for i in range(5):
            await sink.publicar(_fila(id=i))

        assert len(broker.conexiones) == 1  # un drenador de vida larga no abre un socket por evento
        assert len(broker.conexiones[0].canal.exchange.publicados) == 5

    async def test_un_exchange_personalizado_se_respeta(self, broker):
        await BrokerSink(url="amqp://x", exchange="otro.exchange").publicar(_fila())

        assert broker.conexiones[0].canal.declarados[0][0] == "otro.exchange"


class TestLoQueSalePorElExchange:
    async def test_el_mensaje_es_persistente_json_y_lleva_la_correlacion_en_la_cabecera(self, broker):
        sink = BrokerSink(url="amqp://x")

        await sink.publicar(_fila(id=41, tipo="pedido_pagado"))

        routing_key, mensaje = broker.conexiones[0].canal.exchange.publicados[0]
        assert routing_key == "pedido_pagado"  # el tipo del evento ES el routing key
        assert mensaje.type == "pedido_pagado"
        assert mensaje.content_type == "application/json"
        assert mensaje.delivery_mode == aio_pika.DeliveryMode.PERSISTENT
        assert mensaje.correlation_id == "req-7"
        assert mensaje.message_id == "41"
        assert json.loads(mensaje.body) == {"pedido_id": "p1", "correlacion_id": "req-7"}

    async def test_sin_correlacion_en_la_carga_el_mensaje_sale_sin_el(self, broker):
        await BrokerSink(url="amqp://x").publicar(_fila(carga={"pedido_id": "p1"}))

        _, mensaje = broker.conexiones[0].canal.exchange.publicados[0]
        assert mensaje.correlation_id is None

    @pytest.mark.parametrize("carga", [None, {}])
    async def test_una_carga_vacia_se_publica_como_objeto_vacio(self, broker, carga):
        await BrokerSink(url="amqp://x").publicar(_fila(carga=carga))

        _, mensaje = broker.conexiones[0].canal.exchange.publicados[0]
        assert json.loads(mensaje.body) == {}
        assert mensaje.correlation_id is None

    async def test_una_carga_que_no_es_objeto_no_rompe_la_cabecera(self, broker):
        await BrokerSink(url="amqp://x").publicar(_fila(carga=[1, 2]))

        _, mensaje = broker.conexiones[0].canal.exchange.publicados[0]
        assert json.loads(mensaje.body) == [1, 2]
        assert mensaje.correlation_id is None

    async def test_los_valores_no_serializables_se_pasan_a_texto_en_vez_de_perder_el_evento(self, broker):
        identificador = uuid.UUID("11111111-1111-5111-8111-111111111111")

        await BrokerSink(url="amqp://x").publicar(_fila(carga={"agregado": identificador}))

        _, mensaje = broker.conexiones[0].canal.exchange.publicados[0]
        assert json.loads(mensaje.body) == {"agregado": str(identificador)}

    async def test_una_fila_sin_id_recibe_un_message_id_propio(self, broker):
        fila = SimpleNamespace(tipo="kits_publicados", carga={})

        await BrokerSink(url="amqp://x").publicar(fila)

        _, mensaje = broker.conexiones[0].canal.exchange.publicados[0]
        assert uuid.UUID(mensaje.message_id)  # un UUID valido, no vacio


class TestElBrokerCaidoNoSeTraga:
    async def test_publicar_levanta_para_que_el_drenador_no_marque_el_evento(self, broker):
        broker.caida = True
        sink = BrokerSink(url="amqp://x")

        with pytest.raises(ConnectionError, match="broker caido"):
            await sink.publicar(_fila())

        # Nada quedo a medio abrir: cuando el broker vuelve, la siguiente publicacion conecta.
        broker.caida = False
        await sink.publicar(_fila())
        assert len(broker.conexiones) == 1
        assert len(broker.conexiones[0].canal.exchange.publicados) == 1


class TestCerrar:
    async def test_cierra_la_conexion_y_la_siguiente_publicacion_reconecta(self, broker):
        sink = BrokerSink(url="amqp://x")
        await sink.publicar(_fila())
        primera = broker.conexiones[0]

        await sink.cerrar()

        assert primera.cerrada is True
        await sink.publicar(_fila())
        assert len(broker.conexiones) == 2

    async def test_cerrar_sin_haber_publicado_no_hace_nada(self, broker):
        await BrokerSink(url="amqp://x").cerrar()

        assert broker.conexiones == []

    async def test_cerrar_dos_veces_es_inofensivo(self, broker):
        sink = BrokerSink(url="amqp://x")
        await sink.publicar(_fila())

        await sink.cerrar()
        await sink.cerrar()

        assert broker.conexiones[0].cerrada is True


class TestElEntornoDecideSiHayBroker:
    @pytest.mark.parametrize("valor", [None, ""])
    def test_sin_url_o_con_url_vacia_no_hay_broker(self, monkeypatch, valor):
        if valor is None:
            monkeypatch.delenv("RABBITMQ_URL", raising=False)
        else:
            monkeypatch.setenv("RABBITMQ_URL", valor)

        assert url_broker() is None
        assert sink_desde_entorno() is None

    def test_con_url_el_sink_apunta_al_exchange_por_omision(self, monkeypatch):
        monkeypatch.setenv("RABBITMQ_URL", "amqp://invitado@broker.example.test/")

        sink = sink_desde_entorno()

        assert sink is not None
        assert (sink.url, sink.exchange) == ("amqp://invitado@broker.example.test/", EXCHANGE)
