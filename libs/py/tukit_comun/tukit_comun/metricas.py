from __future__ import annotations

import logging
import os
from typing import Any

_log = logging.getLogger(__name__)
_contadores: dict[str, Any] = {}
_gauge_registrado = False


def _meter() -> Any | None:
    try:
        from opentelemetry import metrics
    except ImportError:
        return None
    return metrics.get_meter("tukit")


def _contar(
    nombre: str, descripcion: str, cantidad: int = 1, atributos: dict[str, str] | None = None
) -> None:
    if cantidad <= 0:
        return
    if nombre not in _contadores:
        meter = _meter()
        if meter is None:
            return
        _contadores[nombre] = meter.create_counter(nombre, description=descripcion)
    if atributos:
        _contadores[nombre].add(cantidad, atributos)
    else:
        _contadores[nombre].add(cantidad)


def contar_orden_creada() -> None:
    _contar("tukit.ordenes.creadas", "Ordenes de compra creadas (T1 de la saga).")


def contar_pago_aprobado() -> None:
    _contar("tukit.pagos.aprobados", "Pagos confirmados por webhook (T3 de la saga).")


def contar_trabajo_publicado() -> None:
    _contar("tukit.trabajos.publicados", "Trabajos del pipeline que llegaron a publicado/revision.")


def contar_cache(uso: str, *, aciertos: int, fallos: int) -> None:
    _contar("tukit.cache.aciertos", "Lecturas de la cache que encontraron el valor.", aciertos, {"uso": uso})
    _contar("tukit.cache.fallos", "Lecturas de la cache que no lo encontraron.", fallos, {"uso": uso})


def contar_redis_degradado(uso: str) -> None:
    _contar(
        "tukit.redis.degradaciones",
        "Operaciones con Redis que fallaron o vencieron y degradaron.",
        atributos={"uso": uso},
    )


def contar_limite_rechazado(nivel: str) -> None:
    _contar("tukit.limite.rechazos", "Peticiones que el gateway rechazo con 429.", atributos={"nivel": nivel})


def contar_supresion_atascada(motivo: str, cantidad: int = 1) -> None:
    _contar(
        "tukit.supresion.atascadas",
        "Solicitudes de supresion en propagando que el barrido reenvio o encontro vencidas.",
        cantidad,
        {"motivo": motivo},
    )


def configurar_metricas() -> None:
    global _gauge_registrado
    if _gauge_registrado or not os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT"):
        return
    meter = _meter()
    if meter is None:
        return

    try:
        from opentelemetry.metrics import Observation
    except ImportError:
        return

    from .resiliencia import _disyuntores

    def _observar_breakers(_opciones: Any) -> list[Any]:
        return [Observation(1 if d.abierto else 0, {"destino": nombre}) for nombre, d in _disyuntores.items()]

    meter.create_observable_gauge(
        "tukit.breaker.abierto",
        callbacks=[_observar_breakers],
        description="1 si el disyuntor del destino esta abierto, 0 si no (ADR 0020).",
    )
    _gauge_registrado = True


__all__ = [
    "configurar_metricas",
    "contar_cache",
    "contar_limite_rechazado",
    "contar_orden_creada",
    "contar_pago_aprobado",
    "contar_redis_degradado",
    "contar_supresion_atascada",
    "contar_trabajo_publicado",
]
