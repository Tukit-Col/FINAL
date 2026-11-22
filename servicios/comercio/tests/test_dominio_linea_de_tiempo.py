from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from tukit_comercio.dominio.linea_de_tiempo import (
    PASOS,
    AvanceVisto,
    EnvioVisto,
    PagoVisto,
    linea_de_tiempo,
)

T0 = datetime(2026, 10, 1, 13, 0, tzinfo=UTC)


def _t(horas: int) -> datetime:
    return T0 + timedelta(hours=horas)


PAGO_APROBADO = PagoVisto(estado="aprobado", actualizado_en=_t(1))
ENVIO = EnvioVisto(repartidor_nombre="Luis Gomez", entrega_estimada=_t(48), entregado_en=None)


def _avance(desde: str, hacia: str, horas: int, tipo: str | None = None) -> AvanceVisto:
    return AvanceVisto(estado_desde=desde, estado_hacia=hacia, tipo_incidencia=tipo, creado_en=_t(horas))


CAMINO = [
    _avance("pagado", "en_preparacion", 2),
    _avance("en_preparacion", "despachado", 3),
    _avance("despachado", "en_reparto", 4),
    _avance("en_reparto", "entregado", 5),
]


def _linea(estado: str, *, pagos=(PAGO_APROBADO,), historial=(), envio=ENVIO, ahora=None):
    return linea_de_tiempo(
        estado=estado, creado_en=T0, pagos=list(pagos), historial=list(historial), envio=envio, ahora=ahora
    )


def _estados(linea) -> list[str]:
    return [p["estado"] for p in linea["pasos"]]


@pytest.mark.parametrize(
    ("estado", "filas", "actual"),
    [
        ("pagado", 0, 1),
        ("en_preparacion", 1, 2),
        ("despachado", 2, 3),
        ("en_reparto", 3, 4),
        ("entregado", 4, 5),
    ],
)
def test_cada_estado_del_camino_marca_su_paso_y_fecha_los_alcanzados(estado, filas, actual):
    linea = _linea(estado, historial=CAMINO[:filas])
    assert [p["paso"] for p in linea["pasos"]] == list(PASOS)
    assert _estados(linea) == ["hecho"] * actual + ["actual"] + ["futuro"] * (len(PASOS) - actual - 1)
    fechas = [p["fecha"] for p in linea["pasos"]]
    assert fechas[: actual + 1] == [_t(h).isoformat() for h in range(actual + 1)]
    assert fechas[actual + 1 :] == [None] * (len(PASOS) - actual - 1)
    assert linea["especial"] is None
    assert linea["pago_pendiente"] is None


def test_pendiente_vigente_dice_cuando_vence():
    linea = _linea("pendiente_pago", pagos=(), envio=None, ahora=_t(2))
    assert _estados(linea) == ["actual"] + ["futuro"] * 5
    assert linea["pasos"][0]["fecha"] == T0.isoformat()
    assert linea["pago_pendiente"] == {"vence_en": _t(24).isoformat(), "vencido": False}


def test_pendiente_vencido():
    linea = _linea("pendiente_pago", pagos=(), envio=None, ahora=_t(25))
    assert linea["pago_pendiente"]["vencido"] is True


def test_incidencia_en_reparto_se_queda_en_ese_paso_con_su_tipo():
    historial = [*CAMINO[:3], _avance("en_reparto", "incidencia", 6, "no_habia_nadie")]
    linea = _linea("incidencia", historial=historial)
    assert _estados(linea) == ["hecho"] * 4 + ["actual", "futuro"]
    assert linea["especial"] == {
        "tipo": "incidencia",
        "tipo_incidencia": "no_habia_nadie",
        "fecha": _t(6).isoformat(),
    }


def test_volver_a_preparacion_tras_una_incidencia_reabre_los_pasos_siguientes():
    historial = [
        *CAMINO[:3],
        _avance("en_reparto", "incidencia", 6, "direccion_errada"),
        _avance("incidencia", "en_preparacion", 7),
    ]
    linea = _linea("en_preparacion", historial=historial)
    assert _estados(linea) == ["hecho", "hecho", "actual", "futuro", "futuro", "futuro"]
    assert linea["pasos"][2]["fecha"] == _t(7).isoformat()
    assert linea["pasos"][3]["fecha"] is None
    assert linea["pasos"][3]["repartidor_nombre"] is None
    assert linea["especial"] is None


def test_despachar_otra_vez_toma_la_fecha_del_ultimo_despacho():
    historial = [
        *CAMINO[:2],
        _avance("despachado", "incidencia", 6, "otro"),
        _avance("incidencia", "en_preparacion", 7),
        _avance("en_preparacion", "despachado", 8),
    ]
    linea = _linea("despachado", historial=historial)
    assert linea["pasos"][3]["fecha"] == _t(8).isoformat()


def test_cancelado_tras_incidencia_queda_donde_estaba_sin_paso_en_curso():
    historial = [
        *CAMINO[:2],
        _avance("despachado", "incidencia", 6, "rechazado"),
        _avance("incidencia", "cancelado", 7),
    ]
    linea = _linea("cancelado", historial=historial)
    assert _estados(linea) == ["hecho"] * 4 + ["futuro"] * 2
    assert "actual" not in _estados(linea)
    assert linea["especial"] == {"tipo": "cancelado", "fecha": _t(7).isoformat()}


def test_cancelado_sin_historial_y_sin_pago_es_un_pendiente_que_vencio():
    linea = _linea("cancelado", pagos=(PagoVisto("rechazado", _t(1)),), envio=None)
    assert _estados(linea) == ["hecho"] + ["futuro"] * 5
    assert linea["especial"] == {"tipo": "cancelado", "fecha": None}
    assert linea["pago_pendiente"] is None


def test_cancelado_sin_historial_tras_un_retracto_llega_hasta_pagado_sin_inventar_la_fecha():
    linea = _linea("cancelado", pagos=(PagoVisto("reembolsado", _t(30)),))
    assert _estados(linea) == ["hecho", "hecho"] + ["futuro"] * 4
    assert linea["pasos"][1]["fecha"] is None


def test_sin_historial_los_pasos_alcanzados_quedan_sin_fecha():
    linea = _linea("en_reparto", pagos=(PagoVisto("aprobado", None),), envio=None)
    assert _estados(linea) == ["hecho"] * 4 + ["actual", "futuro"]
    assert [p["fecha"] for p in linea["pasos"]] == [T0.isoformat(), None, None, None, None, None]
    assert linea["entrega_estimada"] is None


def test_entregado_sin_fila_cae_a_la_fecha_del_envio():
    envio = EnvioVisto(repartidor_nombre="Luis Gomez", entrega_estimada=None, entregado_en=_t(9))
    linea = _linea("entregado", historial=CAMINO[:3], envio=envio)
    assert linea["pasos"][5]["fecha"] == _t(9).isoformat()


def test_el_despacho_solo_trae_el_nombre_del_repartidor():
    linea = _linea("despachado", historial=CAMINO[:2])
    despacho = linea["pasos"][3]
    assert despacho["repartidor_nombre"] == "Luis Gomez"
    assert set(despacho) == {"paso", "estado", "fecha", "repartidor_nombre"}
    assert linea["entrega_estimada"] == _t(48).isoformat()


def test_las_fechas_sin_zona_se_leen_como_utc():
    sin_zona = T0.replace(tzinfo=None)
    linea = linea_de_tiempo(
        estado="pendiente_pago", creado_en=sin_zona, pagos=[], historial=[], envio=None, ahora=_t(1)
    )
    assert linea["pasos"][0]["fecha"] == T0.isoformat()
    assert linea["pago_pendiente"]["vence_en"] == _t(24).isoformat()
