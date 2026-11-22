"""Recoleccion de `ensayos/`: las pruebas que necesitan el stack vivo se piden aparte.

`make prueba` corre `pytest libs servicios ensayos`, y `ensayos` esta en
`testpaths`. Sin este archivo recogeria `ensayos/integracion` y `ensayos/e2e`,
que necesitan los seis procesos de `make backend` y las bases migradas, y la
suite unitaria quedaria roja cada vez que el stack no esta arriba.

Esas dos carpetas quedan fuera de la recoleccion por defecto y entran solo si se
piden de forma explicita, como lo hacen los jobs `integracion` y `e2e-api` del CI:

    .venv/bin/pytest -m integracion                # o: pytest ensayos/integracion -m integracion
    .venv/bin/pytest -m e2e                        # o: pytest ensayos/e2e -m e2e
    TUKIT_QA_STACK=1 .venv/bin/pytest ensayos      # las dos, con cualquier otro filtro

Tambien entran si la ruta se pasa en la linea de comandos (pytest nunca ignora
una ruta inicial). Pedidas con el stack apagado, la sesion FALLA en vez de
saltarse: la fixture `stack` de cada carpeta hace `pytest.fail` (H-C-03).

Las demas pruebas de `ensayos/` (las del equipo) se recogen igual que antes.
"""

from __future__ import annotations

import itertools
import os
import re
import socket
import uuid
from collections.abc import Iterator
from pathlib import Path

import pytest
from _pytest.mark.expression import Expression

# Carpeta con stack -> marcador que la pide con `-m`.
_CON_STACK = {"integracion": "integracion", "e2e": "e2e"}
_PALABRAS = {"and", "or", "not", "True", "False"}


def _selecciona(expresion: str, marcador: str) -> bool:
    """Si la expresion de `-m` deja entrar pruebas por llevar `marcador`.

    Es asi cuando hay alguna combinacion de los demas marcadores de la expresion
    con la que una prueba entra con `marcador` y no entra sin el. `-m integracion`
    y `-m "integracion and nfr"` la piden; `-m "not integracion"` y `-m nfr`, no.
    """
    compilada = Expression.compile(expresion)
    otros = sorted(set(re.findall(r"(?:\w|[:+\-.\[\]\\/])+", expresion)) - _PALABRAS - {marcador})
    for valores in itertools.product((False, True), repeat=len(otros)):
        puestos = frozenset(nombre for nombre, valor in zip(otros, valores, strict=True) if valor)
        con = compilada.evaluate(lambda nombre, _p=puestos, **_: nombre == marcador or nombre in _p)
        sin = compilada.evaluate(lambda nombre, _p=puestos, **_: nombre in _p)
        if con and not sin:
            return True
    return False


def pytest_ignore_collect(collection_path: Path, config: pytest.Config) -> bool | None:
    marcador = _CON_STACK.get(collection_path.name)
    if marcador is None or collection_path.parent != Path(__file__).resolve().parent:
        return None
    if os.environ.get("TUKIT_QA_STACK") == "1":
        return None
    expresion = config.getoption("markexpr", default="")
    if expresion and _selecciona(expresion, marcador):
        return None
    return True


# --- Bloque de QA (Tukit-QA, acuerdos §2.4 y §4.2) ---------------------------
# Guardia de 0 USD, marcadores y `correlacion_id` por prueba. Va repetido en
# cada `conftest.py` donde QA agrega pruebas, porque `pyproject.toml` no esta
# entre las rutas que QA puede tocar. La cuenta de intentos vive en `config`
# para que todos los conftest sumen sobre la misma.

_DOMINIO_GEMINI = "generativelanguage.googleapis.com"


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line("markers", "nfr(id): ensayo de la matriz NFR de Tukit-QA")
    config.addinivalue_line("markers", "integracion: necesita el stack vivo (make backend)")
    config.addinivalue_line("markers", "e2e: flujo de punta a punta contra el stack vivo (make backend)")


@pytest.fixture(scope="session", autouse=True)
def _guardia_sesion(request: pytest.FixtureRequest, record_testsuite_property) -> Iterator[dict]:
    cuenta = request.config.__dict__.setdefault("_qa_guardia_gemini", {"intentos": 0, "anotada": False})
    yield cuenta
    if not cuenta["anotada"]:
        cuenta["anotada"] = True
        record_testsuite_property("llamadas_reales", cuenta["intentos"])


@pytest.fixture
def correlacion_id(request: pytest.FixtureRequest, record_property) -> str:
    marca = request.node.get_closest_marker("nfr")
    cid = uuid.uuid4().hex
    record_property("correlacion_id", cid)
    record_property("ensayo_id", marca.args[0] if marca else "suite")
    return cid


@pytest.fixture(autouse=True)
def _guardia_gemini(monkeypatch: pytest.MonkeyPatch, _guardia_sesion: dict, correlacion_id: str) -> None:
    # Se borran sin leerlas: el valor nunca pasa por la prueba.
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_MODELO", raising=False)
    original = socket.getaddrinfo

    def vigilada(host, *args, **kwargs):  # noqa: ANN001, ANN002, ANN003
        nombre = host.decode() if isinstance(host, bytes) else str(host or "")
        if _DOMINIO_GEMINI in nombre.lower():
            _guardia_sesion["intentos"] += 1
            pytest.fail("guardia: intento de llamada real a Gemini")
        return original(host, *args, **kwargs)

    monkeypatch.setattr(socket, "getaddrinfo", vigilada)
