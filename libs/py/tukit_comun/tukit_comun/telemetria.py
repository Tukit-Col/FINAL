"""Trazas OpenTelemetry, no-op sin endpoint (ADR 0021, B.4).

Una peticion de acudiente cruza gateway→inteligencia→catalogo; sin trazas, es
imposible ver esa cadena como una sola cosa. OTel instrumenta FastAPI y HTTPX
para emitir spans y propagar `traceparent` W3C junto al id de correlacion.

Degradacion honesta (mismo criterio que `WOMPI_MODO=falso` y el broker): SIN
`OTEL_EXPORTER_OTLP_ENDPOINT` esto es un no-op TOTAL —no importa nada de OTel, no
exporta, no cuesta—, de modo que la tesis corre sin collector. CON el endpoint,
requiere el extra `otel` (`uv sync --extra otel`); si falta, se avisa y se sigue
sin trazas en vez de tumbar el arranque."""

from __future__ import annotations

import logging
import os
from typing import Any

_log = logging.getLogger(__name__)
_configurado = False


def configurar_telemetria(app: Any, titulo: str) -> None:
    """Instrumenta la app para OTLP si hay endpoint; si no, no hace nada.

    Idempotente a nivel proveedor (el TracerProvider global se pone una vez por
    proceso). Instrumentar FastAPI+HTTPX cubre spans de servidor y de cliente y
    la propagacion del contexto entre servicios; SQLAlchemy se instrumenta en el
    `_arrancar` de cada servicio, que es quien tiene el engine."""
    endpoint = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT")
    if not endpoint:
        return  # no-op: sin endpoint no se paga nada de OTel

    try:
        from opentelemetry import metrics, trace
        from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
        from opentelemetry.sdk.metrics import MeterProvider
        from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
        from opentelemetry.sdk.resources import SERVICE_NAME, Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
    except ImportError:
        _log.warning(
            "OTEL_EXPORTER_OTLP_ENDPOINT esta puesto pero el extra 'otel' no esta "
            "instalado (uv sync --extra otel). Se sigue SIN trazas ni metricas."
        )
        return

    global _configurado
    if not _configurado:
        recurso = Resource.create({SERVICE_NAME: titulo})
        proveedor = TracerProvider(resource=recurso)
        proveedor.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint)))
        trace.set_tracer_provider(proveedor)
        # MeterProvider para las metricas de dominio (`metricas.py`): sin esto,
        # `get_meter` devuelve un no-op y los counters no salen a ningun lado.
        lector = PeriodicExportingMetricReader(OTLPMetricExporter(endpoint=endpoint))
        metrics.set_meter_provider(MeterProvider(resource=recurso, metric_readers=[lector]))
        HTTPXClientInstrumentor().instrument()
        _configurado = True

    FastAPIInstrumentor.instrument_app(app)


def instrumentar_motor(engine: Any) -> None:
    """Instrumenta un engine SQLAlchemy async si OTel esta activo; si no, no-op.

    Lo llama el `_arrancar` de cada servicio con `app.state.motor.engine`. Sin
    endpoint (o sin el extra) no hace nada."""
    if not os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT"):
        return
    try:
        from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
    except ImportError:
        return
    # El engine async envuelve el sync en `.sync_engine`; es el que instrumenta.
    SQLAlchemyInstrumentor().instrument(engine=getattr(engine, "sync_engine", engine))


__all__ = ["configurar_telemetria", "instrumentar_motor"]
