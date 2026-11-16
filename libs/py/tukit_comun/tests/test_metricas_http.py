"""Metricas de dominio: no-op honesto sin endpoint (ADR 0021).

Sin un collector no se puede afirmar que un contador salio; lo que SI se fija es
que llamar a las metricas nunca revienta el camino de negocio —con o sin OTel
instalado, con o sin endpoint—. Es la garantia de que contar una orden no puede
tumbar el checkout.
"""

from __future__ import annotations

from tukit_comun import metricas


def test_los_contadores_no_revientan_sin_endpoint(monkeypatch):
    monkeypatch.delenv("OTEL_EXPORTER_OTLP_ENDPOINT", raising=False)
    # Sin MeterProvider, `get_meter` da un meter no-op: contar es inocuo.
    metricas.contar_orden_creada()
    metricas.contar_pago_aprobado()
    metricas.contar_trabajo_publicado()


def test_configurar_metricas_sin_endpoint_no_hace_nada(monkeypatch):
    monkeypatch.delenv("OTEL_EXPORTER_OTLP_ENDPOINT", raising=False)
    metricas.configurar_metricas()  # no-op: sin endpoint no registra el gauge
