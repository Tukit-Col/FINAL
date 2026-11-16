"""La decision de crear/promover/conflicto y la validacion de clave, puras."""

from __future__ import annotations

import pytest
from tukit_identidad.dominio.cuenta import (
    CLAVE_MINIMA,
    ClaveDebil,
    Decision,
    decide_creacion,
    validar_clave,
)


def test_correo_libre_se_crea():
    assert decide_creacion(None) is Decision.CREAR


def test_invitado_sin_credencial_se_promueve():
    assert decide_creacion("sin-credencial") is Decision.PROMOVER


def test_correo_con_credencial_real_es_conflicto():
    assert decide_creacion("pbkdf2_sha256$...$...") is Decision.CONFLICTO


def test_clave_corta_se_rechaza():
    with pytest.raises(ClaveDebil):
        validar_clave("x" * (CLAVE_MINIMA - 1))


@pytest.mark.parametrize("largo", [CLAVE_MINIMA, CLAVE_MINIMA + 24])
def test_una_clave_del_largo_minimo_o_mas_es_valida(largo):
    """El limite es inclusivo: `CLAVE_MINIMA` caracteres ya bastan."""
    assert validar_clave("x" * largo) is None
