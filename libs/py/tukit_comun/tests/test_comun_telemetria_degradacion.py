"""NFR-MAN-01: la telemetria OTel degrada sin romper el arranque (ADR 0021, B.4).

`test_telemetria.py` solo prueba que sin endpoint no revienta. Aqui se demuestra
cada rama de la degradacion y, con un OTel de mentira inyectado en `sys.modules`,
lo que `configurar_telemetria` arma cuando SI hay endpoint: un solo proveedor por
proceso, el nombre del servicio como recurso, HTTPX instrumentado una vez y cada
app FastAPI instrumentada. El OTel real no esta instalado en la CI (es un extra),
por eso el doble vive en el borde: los mismos nombres de modulo que importa el
producto, con clases que solo anotan lo que se les hizo.

Importa porque la tesis corre sin collector: que falte el endpoint, el extra o
una sola de sus piezas debe significar "sin trazas", nunca "el servicio no
arranca". Y una instalacion a medias no debe dejar un proveedor global a medio
configurar.
"""

from __future__ import annotations

import logging
import sys
from types import ModuleType, SimpleNamespace
from typing import Any

import pytest
from tukit_comun import telemetria
from tukit_comun.telemetria import configurar_telemetria, instrumentar_motor

pytestmark = pytest.mark.nfr("NFR-MAN-01")

ENDPOINT = "http://collector.example.test:4317"
VARIABLE = "OTEL_EXPORTER_OTLP_ENDPOINT"


def _modulo(nombre: str, **atributos: Any) -> ModuleType:
    modulo = ModuleType(nombre)
    modulo.__path__ = []  # se comporta como paquete: admite submodulos en sys.modules
    for clave, valor in atributos.items():
        setattr(modulo, clave, valor)
    return modulo


def _sin_otel(monkeypatch: pytest.MonkeyPatch) -> None:
    """Fuerza `ImportError` en cualquier import de OTel, este o no instalado."""
    for nombre in [n for n in sys.modules if n == "opentelemetry" or n.startswith("opentelemetry.")]:
        monkeypatch.delitem(sys.modules, nombre)
    monkeypatch.setitem(sys.modules, "opentelemetry", None)
    for nombre in (
        "opentelemetry.exporter.otlp.proto.grpc.metric_exporter",
        "opentelemetry.exporter.otlp.proto.grpc.trace_exporter",
        "opentelemetry.instrumentation.fastapi",
        "opentelemetry.instrumentation.httpx",
        "opentelemetry.instrumentation.sqlalchemy",
        "opentelemetry.sdk.metrics",
        "opentelemetry.sdk.metrics.export",
        "opentelemetry.sdk.resources",
        "opentelemetry.sdk.trace",
        "opentelemetry.sdk.trace.export",
    ):
        monkeypatch.setitem(sys.modules, nombre, None)


def _instalar_otel(monkeypatch: pytest.MonkeyPatch) -> SimpleNamespace:
    """Instala un OTel de mentira que anota todo lo que el producto le pide."""
    otel = SimpleNamespace(
        proveedores_de_traza=[],
        proveedores_de_metricas=[],
        httpx_instrumentado=0,
        apps=[],
        motores=[],
    )

    class Resource:
        def __init__(self, atributos: dict[str, str]) -> None:
            self.atributos = atributos

        @classmethod
        def create(cls, atributos: dict[str, str]) -> Resource:
            return cls(atributos)

    class OTLPSpanExporter:
        def __init__(self, endpoint: str) -> None:
            self.endpoint = endpoint

    class BatchSpanProcessor:
        def __init__(self, exportador: OTLPSpanExporter) -> None:
            self.exportador = exportador

    class TracerProvider:
        def __init__(self, resource: Resource) -> None:
            self.resource = resource
            self.procesadores: list[BatchSpanProcessor] = []

        def add_span_processor(self, procesador: BatchSpanProcessor) -> None:
            self.procesadores.append(procesador)

    class OTLPMetricExporter:
        def __init__(self, endpoint: str) -> None:
            self.endpoint = endpoint

    class PeriodicExportingMetricReader:
        def __init__(self, exportador: OTLPMetricExporter) -> None:
            self.exportador = exportador

    class MeterProvider:
        def __init__(self, resource: Resource, metric_readers: list[Any]) -> None:
            self.resource = resource
            self.lectores = metric_readers

    class HTTPXClientInstrumentor:
        def instrument(self) -> None:
            otel.httpx_instrumentado += 1

    class FastAPIInstrumentor:
        @staticmethod
        def instrument_app(app: Any) -> None:
            otel.apps.append(app)

    class SQLAlchemyInstrumentor:
        def instrument(self, *, engine: Any) -> None:
            otel.motores.append(engine)

    trace = SimpleNamespace(set_tracer_provider=otel.proveedores_de_traza.append)
    metrics = SimpleNamespace(set_meter_provider=otel.proveedores_de_metricas.append)
    modulos = {
        "opentelemetry": _modulo("opentelemetry", trace=trace, metrics=metrics),
        "opentelemetry.exporter.otlp.proto.grpc.metric_exporter": _modulo(
            "m", OTLPMetricExporter=OTLPMetricExporter
        ),
        "opentelemetry.exporter.otlp.proto.grpc.trace_exporter": _modulo(
            "t", OTLPSpanExporter=OTLPSpanExporter
        ),
        "opentelemetry.instrumentation.fastapi": _modulo("f", FastAPIInstrumentor=FastAPIInstrumentor),
        "opentelemetry.instrumentation.httpx": _modulo("h", HTTPXClientInstrumentor=HTTPXClientInstrumentor),
        "opentelemetry.instrumentation.sqlalchemy": _modulo(
            "s", SQLAlchemyInstrumentor=SQLAlchemyInstrumentor
        ),
        "opentelemetry.sdk.metrics": _modulo("sm", MeterProvider=MeterProvider),
        "opentelemetry.sdk.metrics.export": _modulo(
            "sme", PeriodicExportingMetricReader=PeriodicExportingMetricReader
        ),
        "opentelemetry.sdk.resources": _modulo("sr", SERVICE_NAME="service.name", Resource=Resource),
        "opentelemetry.sdk.trace": _modulo("st", TracerProvider=TracerProvider),
        "opentelemetry.sdk.trace.export": _modulo("ste", BatchSpanProcessor=BatchSpanProcessor),
    }
    for nombre in [n for n in sys.modules if n == "opentelemetry" or n.startswith("opentelemetry.")]:
        monkeypatch.delitem(sys.modules, nombre)
    for nombre, modulo in modulos.items():
        monkeypatch.setitem(sys.modules, nombre, modulo)
    return otel


@pytest.fixture(autouse=True)
def _proveedor_sin_configurar(monkeypatch: pytest.MonkeyPatch) -> None:
    """La bandera `_configurado` es global al proceso: cada prueba parte de cero."""
    monkeypatch.setattr(telemetria, "_configurado", False)
    monkeypatch.delenv(VARIABLE, raising=False)


class TestSinEndpointEsUnNoOpTotal:
    @pytest.mark.parametrize("valor", [None, ""])
    def test_no_importa_nada_de_otel_ni_toca_la_app(self, monkeypatch, caplog, valor):
        """Aunque importar OTel reventara, sin endpoint ni se intenta: la prueba
        falla si el producto lo importara fuera del `try`."""
        _sin_otel(monkeypatch)
        if valor is not None:
            monkeypatch.setenv(VARIABLE, valor)
        app = SimpleNamespace(tocada=False)

        with caplog.at_level(logging.DEBUG, logger="tukit_comun.telemetria"):
            assert configurar_telemetria(app, "servicio-ficticio") is None
            assert instrumentar_motor(SimpleNamespace()) is None

        assert app.tocada is False
        assert telemetria._configurado is False
        assert caplog.records == []  # y tampoco avisa: no hay nada que avisar

    def test_con_otel_disponible_pero_sin_endpoint_tampoco_configura(self, monkeypatch):
        otel = _instalar_otel(monkeypatch)

        configurar_telemetria(SimpleNamespace(), "servicio-ficticio")
        instrumentar_motor(SimpleNamespace(sync_engine="motor"))

        assert otel.proveedores_de_traza == []
        assert otel.proveedores_de_metricas == []
        assert otel.httpx_instrumentado == 0
        assert otel.apps == []
        assert otel.motores == []


class TestConEndpointPeroSinElExtra:
    def test_avisa_una_vez_y_sigue_sin_trazas(self, monkeypatch, caplog):
        _sin_otel(monkeypatch)
        monkeypatch.setenv(VARIABLE, ENDPOINT)

        with caplog.at_level(logging.WARNING, logger="tukit_comun.telemetria"):
            configurar_telemetria(SimpleNamespace(), "servicio-ficticio")

        avisos = [r for r in caplog.records if r.levelno == logging.WARNING]
        assert len(avisos) == 1
        assert VARIABLE in avisos[0].getMessage()
        assert "extra 'otel'" in avisos[0].getMessage()
        assert "SIN trazas" in avisos[0].getMessage()
        assert telemetria._configurado is False

    def test_el_motor_no_se_instrumenta_y_no_revienta(self, monkeypatch):
        _sin_otel(monkeypatch)
        monkeypatch.setenv(VARIABLE, ENDPOINT)

        assert instrumentar_motor(SimpleNamespace(sync_engine="motor")) is None

    def test_una_instalacion_a_medias_no_deja_un_proveedor_global_a_medio_armar(self, monkeypatch, caplog):
        """Si falta UNA sola pieza (aqui, la instrumentacion de FastAPI), todos los
        imports se resuelven antes de tocar nada global: no queda un TracerProvider
        puesto sin su instrumentacion."""
        otel = _instalar_otel(monkeypatch)
        monkeypatch.setitem(sys.modules, "opentelemetry.instrumentation.fastapi", None)
        monkeypatch.setenv(VARIABLE, ENDPOINT)

        with caplog.at_level(logging.WARNING, logger="tukit_comun.telemetria"):
            configurar_telemetria(SimpleNamespace(), "servicio-ficticio")

        assert [r.levelno for r in caplog.records] == [logging.WARNING]
        assert otel.proveedores_de_traza == []
        assert otel.proveedores_de_metricas == []
        assert otel.httpx_instrumentado == 0
        assert telemetria._configurado is False


class TestConEndpointYElExtra:
    def test_arma_proveedor_de_trazas_con_el_nombre_del_servicio_y_el_endpoint(self, monkeypatch):
        otel = _instalar_otel(monkeypatch)
        monkeypatch.setenv(VARIABLE, ENDPOINT)
        app = SimpleNamespace(nombre="app-ficticia")

        configurar_telemetria(app, "tukit-catalogo")

        (proveedor,) = otel.proveedores_de_traza
        assert proveedor.resource.atributos == {"service.name": "tukit-catalogo"}
        (procesador,) = proveedor.procesadores
        assert procesador.exportador.endpoint == ENDPOINT

    def test_arma_el_proveedor_de_metricas_con_el_mismo_recurso_y_endpoint(self, monkeypatch):
        """Sin MeterProvider las metricas de dominio irian a un no-op: el mismo
        recurso ata trazas y metricas al mismo servicio en el panel."""
        otel = _instalar_otel(monkeypatch)
        monkeypatch.setenv(VARIABLE, ENDPOINT)

        configurar_telemetria(SimpleNamespace(), "tukit-catalogo")

        (meter,) = otel.proveedores_de_metricas
        (lector,) = meter.lectores
        assert lector.exportador.endpoint == ENDPOINT
        assert meter.resource is otel.proveedores_de_traza[0].resource

    def test_instrumenta_httpx_y_la_app(self, monkeypatch):
        otel = _instalar_otel(monkeypatch)
        monkeypatch.setenv(VARIABLE, ENDPOINT)
        app = SimpleNamespace(nombre="app-ficticia")

        configurar_telemetria(app, "tukit-catalogo")

        assert otel.httpx_instrumentado == 1
        assert otel.apps == [app]
        assert telemetria._configurado is True

    def test_es_idempotente_a_nivel_proveedor_pero_instrumenta_cada_app(self, monkeypatch):
        """El proveedor y HTTPX son globales al proceso (una vez); la app FastAPI
        es de cada llamador y siempre se instrumenta."""
        otel = _instalar_otel(monkeypatch)
        monkeypatch.setenv(VARIABLE, ENDPOINT)
        primera, segunda = SimpleNamespace(id=1), SimpleNamespace(id=2)

        configurar_telemetria(primera, "tukit-catalogo")
        configurar_telemetria(segunda, "tukit-comercio")

        assert len(otel.proveedores_de_traza) == 1
        assert len(otel.proveedores_de_metricas) == 1
        assert otel.httpx_instrumentado == 1
        assert otel.apps == [primera, segunda]
        # El nombre de servicio es el de la PRIMERA llamada: el proveedor no se rehace.
        assert otel.proveedores_de_traza[0].resource.atributos == {"service.name": "tukit-catalogo"}


class TestInstrumentarMotor:
    def test_instrumenta_el_engine_sincrono_que_envuelve_el_async(self, monkeypatch):
        otel = _instalar_otel(monkeypatch)
        monkeypatch.setenv(VARIABLE, ENDPOINT)
        sincrono = object()

        instrumentar_motor(SimpleNamespace(sync_engine=sincrono))

        assert otel.motores == [sincrono]

    def test_un_engine_sin_sync_engine_se_instrumenta_tal_cual(self, monkeypatch):
        otel = _instalar_otel(monkeypatch)
        monkeypatch.setenv(VARIABLE, ENDPOINT)
        motor = object()

        instrumentar_motor(motor)

        assert otel.motores == [motor]

    def test_sin_la_pieza_de_sqlalchemy_el_motor_se_deja_en_paz(self, monkeypatch):
        otel = _instalar_otel(monkeypatch)
        monkeypatch.setitem(sys.modules, "opentelemetry.instrumentation.sqlalchemy", None)
        monkeypatch.setenv(VARIABLE, ENDPOINT)

        assert instrumentar_motor(SimpleNamespace(sync_engine=object())) is None
        assert otel.motores == []
