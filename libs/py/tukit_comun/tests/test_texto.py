"""La normalizacion de personajes que comparten Catalogo e Inteligencia."""

from __future__ import annotations

import pytest
from tukit_comun.texto import normalizar_personaje


@pytest.mark.parametrize("texto", ["Spider-Man", "spiderman", "SPIDER MAN", "spider_man", " Spider-man "])
def test_variantes_de_escritura_dan_la_misma_clave(texto):
    assert normalizar_personaje(texto) == "spiderman"


def test_quita_tildes_y_enie():
    assert normalizar_personaje("Pequeña Sirena") == normalizar_personaje("pequena sirena")
    assert normalizar_personaje("Frózen") == "frozen"
