"""La maquina de estados del trabajo, como tabla, exhaustiva.

`puede_pasar` decide si un `409` procede al revisar un trabajo ya publicado. La
regla vive como dato (`TRANSICIONES`), no como cadena de `if`; esta prueba fija
CADA par (estado, siguiente) de los 5 estados —25 celdas— para que ningun
cambio a la tabla pase inadvertido: el terminal PUBLICADO (nada sale), el retry
FALLIDO->ENCOLADO, y el reproceso ESPERA_REVISION->PROCESANDO que el rechazo de
una revision usa.

Se prueba sobre `dominio.maquina`, que es el nombre unico por el que ADR 0019
expone la maquina; ese modulo reexporta la fuente en `modelos`, no la duplica.
"""

from __future__ import annotations

import itertools

import pytest
from tukit_inteligencia.dominio.maquina import TRANSICIONES, puede_pasar
from tukit_inteligencia.modelos import EstadoTrabajo

# La verdad esperada, escrita a mano aparte de TRANSICIONES para que la prueba
# sea un testigo independiente y no un eco de la tabla que valida.
_PERMITIDAS = {
    ("encolado", "procesando"),
    ("encolado", "fallido"),
    ("procesando", "espera_revision"),
    ("procesando", "fallido"),
    ("procesando", "publicado"),
    ("espera_revision", "publicado"),
    ("espera_revision", "procesando"),
    ("espera_revision", "encolado"),  # devolver reencola (ADR 0024: worker durable)
    ("fallido", "encolado"),
}

_ESTADOS = [e.value for e in EstadoTrabajo]


@pytest.mark.parametrize("desde,hacia", list(itertools.product(_ESTADOS, _ESTADOS)))
def test_cada_celda_de_la_maquina(desde: str, hacia: str):
    assert puede_pasar(desde, hacia) is ((desde, hacia) in _PERMITIDAS)


def test_publicado_es_terminal():
    assert TRANSICIONES[EstadoTrabajo.PUBLICADO] == frozenset()


def test_fallido_reintenta_a_encolado():
    assert EstadoTrabajo.ENCOLADO in TRANSICIONES[EstadoTrabajo.FALLIDO]


def test_un_estado_inventado_no_pasa():
    assert puede_pasar("inventado", "publicado") is False
    assert puede_pasar("encolado", "inventado") is False
