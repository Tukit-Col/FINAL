from __future__ import annotations

import itertools

import pytest
from tukit_inteligencia.dominio.maquina import TRANSICIONES, puede_pasar
from tukit_inteligencia.modelos import EstadoTrabajo

_PERMITIDAS = {
    ("encolado", "procesando"),
    ("encolado", "fallido"),
    ("procesando", "espera_revision"),
    ("procesando", "fallido"),
    ("procesando", "publicado"),
    ("espera_revision", "publicado"),
    ("espera_revision", "procesando"),
    ("espera_revision", "encolado"),
    ("fallido", "encolado"),
    ("encolado", "cancelado"),
    ("espera_revision", "cancelado"),
    ("publicado", "cancelado"),
    ("fallido", "cancelado"),
}

_ESTADOS = [e.value for e in EstadoTrabajo]


@pytest.mark.parametrize("desde,hacia", list(itertools.product(_ESTADOS, _ESTADOS)))
def test_cada_celda_de_la_maquina(desde: str, hacia: str):
    assert puede_pasar(desde, hacia) is ((desde, hacia) in _PERMITIDAS)


def test_publicado_solo_se_cancela():
    assert TRANSICIONES[EstadoTrabajo.PUBLICADO] == frozenset({EstadoTrabajo.CANCELADO})


def test_cancelado_es_terminal():
    assert TRANSICIONES[EstadoTrabajo.CANCELADO] == frozenset()


def test_fallido_reintenta_a_encolado():
    assert EstadoTrabajo.ENCOLADO in TRANSICIONES[EstadoTrabajo.FALLIDO]


def test_un_estado_inventado_no_pasa():
    assert puede_pasar("inventado", "publicado") is False
    assert puede_pasar("encolado", "inventado") is False
