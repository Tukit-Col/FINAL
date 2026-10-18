"""El override de la rama `qa`: `GEMINI_BASE_URL` manda la percepcion al fake-gemini.

Solo existe en `qa` (Tukit-QA, H-C-17) y nunca va a `main`. Las pruebas no tocan
la red (`urlopen` esta parcheado) ni definen `GEMINI_API_KEY`: la borran del
entorno sin leerla, igual que la guardia de 0 USD de las pruebas de A.
"""

from __future__ import annotations

import io
import json
import urllib.parse

import pytest
from tukit_inteligencia import gemini
from tukit_inteligencia.percepcion import PercepcionFallida

PAGINA = {"grados": ["Cuarto"], "completa": True, "items": [{"descripcion": "Cuaderno", "cantidad": 2}]}


class _Respuesta(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False


@pytest.fixture
def pedidos(monkeypatch):
    """Entorno sin clave ni override, y la red sustituida por un registro de pedidos."""
    for variable in ("GEMINI_API_KEY", "GEMINI_MODELO", "GEMINI_BASE_URL"):
        monkeypatch.delenv(variable, raising=False)
    registro: list[object] = []

    def urlopen(pedido, timeout):  # noqa: ARG001
        registro.append(pedido)
        cuerpo = {"candidates": [{"content": {"parts": [{"text": json.dumps(PAGINA)}]}}]}
        return _Respuesta(json.dumps(cuerpo).encode())

    monkeypatch.setattr(gemini.urllib.request, "urlopen", urlopen)
    return registro


@pytest.mark.parametrize(
    ("base", "esperada"),
    [
        (
            "http://fake-gemini:8090/",
            "http://fake-gemini:8090/v1beta/models/gemini-3.5-flash-lite:generateContent?key=qa",
        ),
        (
            "https://fake.qa.local//",
            "https://fake.qa.local/v1beta/models/gemini-3.5-flash-lite:generateContent?key=qa",
        ),
    ],
)
def test_con_base_url_va_al_fake_con_la_clave_qa(pedidos, monkeypatch, base, esperada):
    monkeypatch.setenv("GEMINI_BASE_URL", base)

    pagina = gemini.pedir_pagina(b"png", 1)

    assert len(pedidos) == 1
    assert pedidos[0].full_url == esperada
    assert urllib.parse.parse_qs(urllib.parse.urlsplit(pedidos[0].full_url).query) == {"key": ["qa"]}
    assert pagina.items[0].descripcion == "Cuaderno"


@pytest.mark.parametrize("base", [None, "", "   "])
def test_sin_base_url_ni_clave_falla_igual_que_main(pedidos, monkeypatch, base):
    """Vacia cuenta como ausente: el camino es el de `main`, que exige la clave."""
    if base is not None:
        monkeypatch.setenv("GEMINI_BASE_URL", base)

    with pytest.raises(PercepcionFallida, match="Falta GEMINI_API_KEY"):
        gemini.pedir_pagina(b"png", 1)
    assert pedidos == []


@pytest.mark.parametrize("base", ["ftp://fake-gemini:8090", "file:///tmp/fake", "fake-gemini:8090"])
def test_un_esquema_no_admitido_se_rechaza_sin_llamar(pedidos, monkeypatch, base):
    monkeypatch.setenv("GEMINI_BASE_URL", base)

    with pytest.raises(PercepcionFallida, match="GEMINI_BASE_URL"):
        gemini.pedir_pagina(b"png", 1)
    assert pedidos == []
