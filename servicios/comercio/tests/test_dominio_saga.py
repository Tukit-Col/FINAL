from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

from tukit_comercio.dominio.saga import PASOS, reservas_vencidas


def _reserva(estado: str, edad_min: float, pedido_estado: str):
    corte = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
    return SimpleNamespace(
        id="r",
        estado=estado,
        creado_en=corte - timedelta(minutes=edad_min),
        pedido_estado=pedido_estado,
    )


AHORA = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
TTL = timedelta(minutes=30)


def test_libera_una_reserva_activa_de_un_pedido_sin_pagar_y_vieja():
    filas = [_reserva("activa", edad_min=31, pedido_estado="pendiente_pago")]
    assert [r.id for r in reservas_vencidas(filas, ahora=AHORA, ttl=TTL)] == ["r"]


def test_no_libera_una_reserva_reciente():
    filas = [_reserva("activa", edad_min=29, pedido_estado="pendiente_pago")]
    assert reservas_vencidas(filas, ahora=AHORA, ttl=TTL) == []


def test_no_libera_si_el_pedido_ya_se_pago():
    filas = [_reserva("activa", edad_min=31, pedido_estado="pagado")]
    assert reservas_vencidas(filas, ahora=AHORA, ttl=TTL) == []


def test_no_libera_una_reserva_ya_liberada_o_consumida():
    filas = [
        _reserva("liberada", edad_min=99, pedido_estado="pendiente_pago"),
        _reserva("consumida", edad_min=99, pedido_estado="pendiente_pago"),
    ]
    assert reservas_vencidas(filas, ahora=AHORA, ttl=TTL) == []


def test_los_pasos_de_la_saga_estan_nombrados():
    claves = {p.paso for p in PASOS}
    assert claves == {"T1", "T2", "T3", "T4"}
    t4 = next(p for p in PASOS if p.paso == "T4")
    assert t4.compensacion is None
