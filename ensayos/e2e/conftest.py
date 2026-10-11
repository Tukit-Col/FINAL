"""Fixtures de los E2E de la fase 4: el flujo del acudiente y el del colegio, contra el stack vivo.

Como las de `ensayos/integracion`, no corren con `make prueba`: necesitan los
seis procesos de `make backend` y las bases migradas y sembradas, y
`ensayos/conftest.py` deja esta carpeta fuera de la recoleccion salvo que se
pida (`-m e2e`, la ruta explicita o `TUKIT_QA_STACK=1`).

    make backend
    .venv/bin/pytest ensayos/e2e -m e2e

La percepcion es lo unico que no es el stack: la subida pasa por una copia de
inteligencia que sirve las respuestas grabadas de `datos/golden/fixtures-modelo/`
en lugar de Gemini (`inteligencia_lector_fixtures.py`), y por una copia del
gateway que apunta a ella. Todo lo demas es el stack compartido: el catalogo, el
poller que arma el kit del acudiente, el trabajador, comercio y la pasarela
falsa. Si el stack no responde, la sesion FALLA en vez de saltarse (H-C-03).
"""

from __future__ import annotations

import asyncio
import socket
import sys
import uuid
from collections.abc import Awaitable, Callable, Iterator
from pathlib import Path
from typing import Any

import httpx
import pytest
from sqlalchemy import text

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "integracion"))

sys.path.insert(0, str(Path(__file__).resolve().parent))

from e2e_flujo import catalogo_vivo  # noqa: E402
from stack_vivo import CLAVE_DEMO, GATEWAY, RAIZ, USUARIOS_DEMO, conexion_a, instancia  # noqa: E402
from tukit_comun.http import CABECERA_CORRELACION  # noqa: E402


@pytest.fixture(scope="session")
def stack() -> dict[str, Any]:
    """El estado del stack segun el gateway. Falla la sesion si no esta arriba."""
    try:
        respuesta = httpx.get(f"{GATEWAY}/v1/servicios", timeout=10.0)
    except httpx.HTTPError as error:
        pytest.fail(f"el stack no responde en {GATEWAY} ({error}); levantarlo con `make backend`")
    estado = respuesta.json()
    if not estado.get("todos_arriba"):
        caidos = [n for n, s in estado.get("servicios", {}).items() if not s.get("arriba")]
        pytest.fail(f"servicios caidos detras del gateway: {caidos}")
    return estado


@pytest.fixture(scope="session")
def puerta(stack: dict[str, Any], tmp_path_factory: pytest.TempPathFactory) -> Iterator[dict[str, Any]]:
    """El gateway por el que entran los E2E: el del stack, con la inteligencia de los dorados.

    Devuelve la URL de la copia del gateway y los dos registros de la copia de
    inteligencia: las paginas que leyo (`lecturas`) y los intentos de resolver
    el dominio de Gemini (`guardia`, que tiene que quedar vacio).
    """
    carpeta = tmp_path_factory.mktemp("inteligencia-dorada")
    guardia = carpeta / "guardia-gemini.log"
    lecturas = carpeta / "lecturas.log"
    with (
        instancia(
            "inteligencia_lector_fixtures",
            carpeta / "inteligencia.log",
            PYTHONPATH=str(Path(__file__).resolve().parent),
            TUKIT_QA_GUARDIA=str(guardia),
            TUKIT_QA_LECTURAS=str(lecturas),
        ) as inteligencia,
        instancia("tukit_gateway.api", carpeta / "gateway.log", TUKIT_INTELIGENCIA_URL=inteligencia) as base,
    ):
        yield {"base": base, "guardia": guardia, "lecturas": lecturas, "carpeta": carpeta, "raiz": RAIZ}


@pytest.fixture(scope="session", autouse=True)
def _guardia_de_los_flujos(_guardia_sesion: dict) -> Iterator[None]:
    """La guardia de §4.2 tambien mientras corren los flujos de modulo.

    Los flujos que comparten las pruebas de un modulo se arman antes que las
    fixtures de cada prueba, y con ellas la guardia por prueba. Esta cubre ese
    tramo con la misma cuenta.
    """
    original = socket.getaddrinfo

    def vigilada(host, *args, **kwargs):  # noqa: ANN001, ANN002, ANN003
        nombre = host.decode() if isinstance(host, bytes) else str(host or "")
        if _DOMINIO_GEMINI in nombre.lower():
            _guardia_sesion["intentos"] += 1
            raise OSError("guardia: intento de llamada real a Gemini")
        return original(host, *args, **kwargs)

    socket.getaddrinfo = vigilada
    yield
    socket.getaddrinfo = original


@pytest.fixture(scope="session")
def colegio_aliado(stack: dict[str, Any]) -> str:
    """Un colegio del directorio, para el registro del acudiente (el registro lo pide)."""
    colegios = httpx.get(f"{GATEWAY}/v1/colegios", timeout=30.0).json()["colegios"]
    assert colegios, "el directorio de colegios esta vacio: falta `make bd-sembrar`"
    return colegios[0]["colegio_id"]


@pytest.fixture(scope="session")
def catalogo(stack: dict[str, Any]) -> dict[str, Any]:
    """Los SKU e id del catalogo vivo y los conceptos que no tienen producto activo."""
    return asyncio.run(catalogo_vivo())


@pytest.fixture(scope="module")
def http_flujo(puerta: dict[str, Any]) -> Iterator[httpx.Client]:
    """El cliente de los flujos que comparten las pruebas de un modulo, con su propio `correlacion_id`."""
    with httpx.Client(
        base_url=puerta["base"], timeout=60.0, headers={CABECERA_CORRELACION: uuid.uuid4().hex}
    ) as http:
        yield http


@pytest.fixture(autouse=True)
def _correlacion_del_flujo(request: pytest.FixtureRequest, record_property) -> None:
    """Deja en el JUnit el `correlacion_id` del flujo de modulo, si la prueba usa uno."""
    if "http_flujo" in request.fixturenames:
        record_property(
            "correlacion_flujo", request.getfixturevalue("http_flujo").headers[CABECERA_CORRELACION]
        )


@pytest.fixture
def cliente(puerta: dict[str, Any], correlacion_id: str) -> Iterator[httpx.Client]:
    """Cliente contra la puerta de los E2E que manda el `correlacion_id` de la prueba."""
    with httpx.Client(
        base_url=puerta["base"], timeout=60.0, headers={CABECERA_CORRELACION: correlacion_id}
    ) as http:
        yield http


@pytest.fixture(scope="session")
def admin(stack: dict[str, Any]) -> dict[str, str]:
    """La cabecera del administrador de demostracion (revisa y aprueba las listas)."""
    respuesta = httpx.post(
        f"{GATEWAY}/v1/sesiones", json={"correo": USUARIOS_DEMO["admin"], "clave": CLAVE_DEMO}, timeout=30.0
    )
    if respuesta.status_code != 200:
        pytest.fail(f"no se pudo entrar como administrador ({respuesta.status_code}): falta sembrar_acceso")
    return {"authorization": f"Bearer {respuesta.json()['token']}"}


@pytest.fixture
def consultar() -> Callable[..., Awaitable[list[Any]]]:
    """`await consultar(servicio, sql, **parametros)` contra la base del servicio."""

    async def _consultar(servicio: str, sql: str, **parametros: Any) -> list[Any]:
        async with conexion_a(servicio) as conexion:
            resultado = await conexion.execute(text(sql), parametros)
            filas = list(resultado) if resultado.returns_rows else []
            await conexion.commit()
            return filas

    return _consultar


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


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    carpeta = Path(__file__).resolve().parent
    for item in items:
        if carpeta in Path(str(item.fspath)).resolve().parents:
            item.add_marker(pytest.mark.e2e)


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
