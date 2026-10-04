"""El reintento del adaptador de Gemini: solo de transporte, y solo uno.

Lo que se protege es la frontera. Un reintento que tambien repitiera una llave
invalida o una respuesta mal formada esconderia fallos que una persona tiene
que ver; uno que no existiera rechaza la lista entera por una pagina colgada.
"""

from __future__ import annotations

import io
import json
import urllib.error

import pytest
from tukit_inteligencia import gemini
from tukit_inteligencia.percepcion import PercepcionFallida

PAGINA = {"grados": ["Once"], "completa": True, "items": [{"descripcion": "Cuaderno", "cantidad": 1}]}


class _Respuesta(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False


def _ok() -> _Respuesta:
    cuerpo = {"candidates": [{"content": {"parts": [{"text": json.dumps(PAGINA)}]}}]}
    return _Respuesta(json.dumps(cuerpo).encode())


def _http(codigo: int) -> urllib.error.HTTPError:
    return urllib.error.HTTPError("https://x", codigo, "error", {}, io.BytesIO(b"detalle"))


@pytest.fixture
def llamadas(monkeypatch):
    """Sustituye la red por una secuencia de resultados y cuenta las llamadas."""
    monkeypatch.setenv("GEMINI_API_KEY", "llave-de-prueba")
    monkeypatch.setattr(gemini.time, "sleep", lambda _s: None)
    registro: list[object] = []

    def preparar(*resultados):
        cola = list(resultados)

        def urlopen(_pedido, timeout):  # noqa: ARG001
            registro.append(timeout)
            resultado = cola.pop(0)
            if isinstance(resultado, BaseException):
                raise resultado
            return resultado

        monkeypatch.setattr(gemini.urllib.request, "urlopen", urlopen)
        return registro

    return preparar


def test_una_pagina_colgada_se_pide_otra_vez(llamadas):
    registro = llamadas(TimeoutError("The read operation timed out"), _ok())

    pagina = gemini.pedir_pagina(b"png", 3)

    assert len(registro) == 2
    assert pagina.items[0].descripcion == "Cuaderno"


def test_un_error_pasajero_de_gemini_se_reintenta(llamadas):
    registro = llamadas(_http(503), _ok())

    gemini.pedir_pagina(b"png", 1)

    assert len(registro) == 2


def test_una_llave_invalida_no_se_reintenta(llamadas):
    """Repetir un 403 no lo arregla: solo retrasa el mensaje que dice por que."""
    registro = llamadas(_http(403))

    with pytest.raises(PercepcionFallida, match="403"):
        gemini.pedir_pagina(b"png", 1)
    assert len(registro) == 1


def test_dos_fallos_seguidos_se_rinden_con_la_causa(llamadas):
    registro = llamadas(TimeoutError("timed out"), TimeoutError("timed out"))

    with pytest.raises(PercepcionFallida, match="no respondio"):
        gemini.pedir_pagina(b"png", 3)
    assert len(registro) == 2
