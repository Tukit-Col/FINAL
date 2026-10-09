"""Utilidades de prueba del Gateway.

Las fixtures del equipo (sin Redis y sin el cliente compartido de la prueba
anterior) y, al final, el bloque de QA.
"""

from __future__ import annotations

import socket
import uuid
from collections.abc import AsyncIterator, Iterator

import pytest
from tukit_comun.cache import usar_cliente
from tukit_gateway.api import app


@pytest.fixture(autouse=True)
def _sin_redis(monkeypatch) -> Iterator[None]:
    """Cada prueba con un cliente nuevo y sin Redis: el limite cuenta en una
    memoria que no arrastra lo que conto la prueba anterior, y una `REDIS_URL`
    exportada en la terminal no mete Redis en las pruebas unitarias."""
    monkeypatch.delenv("REDIS_URL", raising=False)
    usar_cliente(None)
    yield
    usar_cliente(None)


@pytest.fixture(autouse=True)
async def _sin_cliente_compartido() -> AsyncIterator[None]:
    """El cliente httpx compartido de la puerta nace en el primer uso y se ata
    al bucle de esa prueba; se cierra y se retira al terminar, para que la
    siguiente no herede conexiones de un bucle que ya no existe."""
    yield
    cliente = getattr(app.state, "cliente", None)
    if cliente is not None:
        await cliente.aclose()
        del app.state.cliente


# --- Bloque de QA (Tukit-QA, acuerdos §2.4 y §4.2) ---------------------------
# Guardia de 0 USD, marcadores y `correlacion_id` por prueba. Va repetido en
# cada `conftest.py` donde QA agrega pruebas, porque `pyproject.toml` no esta
# entre las rutas que QA puede tocar. La cuenta de intentos vive en `config`
# para que todos los conftest sumen sobre la misma.

_DOMINIO_GEMINI = "generativelanguage.googleapis.com"


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line("markers", "nfr(id): ensayo de la matriz NFR de Tukit-QA")
    config.addinivalue_line("markers", "integracion: necesita el stack vivo (make backend)")


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
