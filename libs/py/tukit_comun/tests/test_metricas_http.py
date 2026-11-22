from __future__ import annotations

import pytest

pytest.importorskip("opentelemetry.sdk")

from opentelemetry import metrics as otel_metrics  # noqa: E402
from opentelemetry.sdk.metrics import MeterProvider  # noqa: E402
from opentelemetry.sdk.metrics.export import InMemoryMetricReader  # noqa: E402
from tukit_comun import metricas  # noqa: E402
from tukit_comun.resiliencia import disyuntor_de  # noqa: E402


@pytest.fixture
def lector(monkeypatch) -> InMemoryMetricReader:
    lector = InMemoryMetricReader()
    proveedor = MeterProvider(metric_readers=[lector])
    monkeypatch.setattr(otel_metrics, "get_meter", lambda nombre, *a, **k: proveedor.get_meter(nombre))
    monkeypatch.setattr(metricas, "_contadores", {})
    monkeypatch.setattr(metricas, "_gauge_registrado", False)
    return lector


def _puntos(lector: InMemoryMetricReader) -> dict[str, list]:
    datos = lector.get_metrics_data()
    if datos is None:
        return {}
    return {
        metrica.name: list(metrica.data.data_points)
        for recurso in datos.resource_metrics
        for alcance in recurso.scope_metrics
        for metrica in alcance.metrics
    }


def test_cada_conteo_suma_uno_a_su_contador(lector):
    metricas.contar_orden_creada()
    metricas.contar_orden_creada()
    metricas.contar_pago_aprobado()
    metricas.contar_trabajo_publicado()

    puntos = _puntos(lector)
    assert [p.value for p in puntos["tukit.ordenes.creadas"]] == [2]
    assert [p.value for p in puntos["tukit.pagos.aprobados"]] == [1]
    assert [p.value for p in puntos["tukit.trabajos.publicados"]] == [1]


def test_la_cache_cuenta_por_uso_y_un_conteo_en_cero_no_emite(lector):
    metricas.contar_cache("percepcion", aciertos=0, fallos=3)

    puntos = _puntos(lector)
    assert "tukit.cache.aciertos" not in puntos
    [fallos] = puntos["tukit.cache.fallos"]
    assert (fallos.value, dict(fallos.attributes)) == (3, {"uso": "percepcion"})


def test_sin_endpoint_no_registra_el_gauge_del_disyuntor(lector, monkeypatch):
    monkeypatch.delenv("OTEL_EXPORTER_OTLP_ENDPOINT", raising=False)

    metricas.configurar_metricas()

    assert "tukit.breaker.abierto" not in _puntos(lector)


def test_con_endpoint_el_gauge_dice_que_disyuntor_esta_abierto(lector, monkeypatch):
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://collector.invalido:4317")
    disyuntor_de("prueba-metricas-cerrado")

    metricas.configurar_metricas()

    estado = {dict(p.attributes)["destino"]: p.value for p in _puntos(lector)["tukit.breaker.abierto"]}
    assert estado["prueba-metricas-cerrado"] == 0
