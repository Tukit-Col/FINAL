from __future__ import annotations

import pytest

pytest.importorskip("opentelemetry.sdk")

from opentelemetry import metrics, trace  # noqa: E402
from tukit_comun.telemetria import configurar_telemetria, instrumentar_motor  # noqa: E402


class _Intocable:
    def __init__(self) -> None:
        object.__setattr__(self, "accesos", [])

    def __getattr__(self, nombre: str):
        self.accesos.append(nombre)
        raise AttributeError(nombre)

    def __setattr__(self, nombre: str, valor) -> None:
        self.accesos.append(nombre)


def test_sin_endpoint_no_toca_la_app_el_engine_ni_los_proveedores(monkeypatch):
    monkeypatch.delenv("OTEL_EXPORTER_OTLP_ENDPOINT", raising=False)
    trazas, medidas = trace.get_tracer_provider(), metrics.get_meter_provider()
    app, engine = _Intocable(), _Intocable()

    configurar_telemetria(app=app, titulo="prueba")
    instrumentar_motor(engine=engine)

    assert app.accesos == [] and engine.accesos == []
    assert trace.get_tracer_provider() is trazas
    assert metrics.get_meter_provider() is medidas
