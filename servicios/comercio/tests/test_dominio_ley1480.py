"""Plazos del retracto (Ley 1480, art. 47): cinco dias habiles desde la entrega
y treinta dias calendario para reembolsar. Dominio puro, sin base."""

from __future__ import annotations

from datetime import UTC, date, datetime

from tukit_comercio.dominio.ley1480 import (
    es_dia_habil,
    evaluar_devolucion,
    festivos_colombia,
    limite_reembolso,
    plazo_retracto,
    sumar_dias_habiles,
)


def _utc(anio, mes, dia, hora=15):
    return datetime(anio, mes, dia, hora, 0, tzinfo=UTC)


def test_festivos_2026_conocidos():
    f = festivos_colombia(2026)
    assert date(2026, 4, 2) in f  # jueves santo
    assert date(2026, 4, 3) in f  # viernes santo
    assert date(2026, 10, 12) in f  # Dia de la Raza (ya es lunes)
    assert date(2026, 11, 2) in f  # Todos los Santos, trasladado al lunes
    assert date(2026, 11, 16) in f  # Independencia de Cartagena, trasladado
    assert date(2026, 5, 18) in f  # Ascension, trasladada al lunes
    assert date(2026, 12, 25) in f


def test_fin_de_semana_y_festivo_no_son_habiles():
    assert not es_dia_habil(date(2026, 10, 31))  # sabado
    assert not es_dia_habil(date(2026, 11, 2))  # festivo
    assert es_dia_habil(date(2026, 11, 3))


def test_cinco_dias_habiles_saltan_fin_de_semana_y_festivo():
    # Entrega viernes 30-oct-2026: habiles 3, 4, 5, 6 y 9 de noviembre (el 2 es festivo).
    assert sumar_dias_habiles(date(2026, 10, 30), 5) == date(2026, 11, 9)


def test_plazo_corre_desde_la_entrega_no_desde_la_compra():
    assert plazo_retracto(None) is None
    # 21:00 en Bogota del viernes 30 es ya sabado en UTC: el dia que cuenta es el de Bogota.
    assert plazo_retracto(datetime(2026, 10, 31, 2, 0, tzinfo=UTC)) == date(2026, 11, 9)


def test_reembolso_treinta_dias_calendario():
    assert limite_reembolso(_utc(2026, 10, 1)) == date(2026, 10, 31)


def test_devolucion_a_tiempo_y_fuera_de_plazo():
    entregado = _utc(2026, 10, 30)
    a_tiempo = evaluar_devolucion(_utc(2026, 11, 9), entregado)
    assert a_tiempo["dentro_de_plazo"] is True
    assert a_tiempo["plazo_retracto"] == "2026-11-09"
    tarde = evaluar_devolucion(_utc(2026, 11, 10), entregado)
    assert tarde["dentro_de_plazo"] is False


def test_sin_entrega_el_plazo_no_corre():
    r = evaluar_devolucion(_utc(2026, 10, 1), None)
    assert r["plazo_retracto"] is None
    assert r["dentro_de_plazo"] is True
    assert r["limite_reembolso"] == "2026-10-31"
