from __future__ import annotations

import logging
import os
from typing import Any

_log = logging.getLogger(__name__)
_configurado = False


def configurar_telemetria(app: Any, titulo: str) -> None:
    endpoint = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT")
    if not endpoint:
        return

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
        lector = PeriodicExportingMetricReader(OTLPMetricExporter(endpoint=endpoint))
        metrics.set_meter_provider(MeterProvider(resource=recurso, metric_readers=[lector]))
        HTTPXClientInstrumentor().instrument()
        _configurado = True

    FastAPIInstrumentor.instrument_app(app)


def instrumentar_motor(engine: Any) -> None:
    if not os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT"):
        return
    try:
        from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
    except ImportError:
        return
    SQLAlchemyInstrumentor().instrument(engine=getattr(engine, "sync_engine", engine))


__all__ = ["configurar_telemetria", "instrumentar_motor"]
