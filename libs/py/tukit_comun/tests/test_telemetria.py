"""Telemetria OTel: no-op honesto sin endpoint (ADR 0021).

Lo unico que se puede fijar sin un collector es la degradacion: sin
`OTEL_EXPORTER_OTLP_ENDPOINT`, `configurar_telemetria`/`instrumentar_motor` no
tocan nada y no revientan aunque OTel no este instalado. Es la garantia de que
la tesis corre sin infra extra.
"""

from __future__ import annotations

from tukit_comun.telemetria import configurar_telemetria, instrumentar_motor


def test_sin_endpoint_no_hace_nada(monkeypatch):
    monkeypatch.delenv("OTEL_EXPORTER_OTLP_ENDPOINT", raising=False)
    # Ni app ni engine reales: si intentara instrumentar, reventaria. No-op => pasa.
    configurar_telemetria(app=None, titulo="prueba")
    instrumentar_motor(engine=None)
