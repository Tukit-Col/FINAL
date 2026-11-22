"""`token_bearer`: lectura del encabezado `Authorization`."""

import pytest
from tukit_comun.autenticacion import token_bearer


@pytest.mark.parametrize(
    ("encabezado", "esperado"),
    [
        (None, None),
        ("", None),
        ("Bearer abc", "abc"),
        ("bearer  abc ", "abc"),
        ("abc", "abc"),
        ("  abc  ", "abc"),
    ],
)
def test_lee_el_token_con_o_sin_prefijo_bearer(encabezado, esperado):
    assert token_bearer(encabezado) == esperado
