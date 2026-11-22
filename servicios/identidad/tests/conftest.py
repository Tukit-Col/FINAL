from __future__ import annotations

import socket
import uuid
from collections.abc import AsyncIterator, Iterator

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from tukit_comun.bd import MotorServicio
from tukit_comun.identificadores import derivar
from tukit_identidad.modelos import Base, Colegio, Sede

from tests._ayudas_identidad import cliente_api, motor_sqlite


@pytest.fixture(autouse=True)
def _sin_broker(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("RABBITMQ_URL", raising=False)


@pytest_asyncio.fixture
async def db() -> AsyncIterator[AsyncSession]:
    motor = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with motor.begin() as conexion:
        await conexion.run_sync(Base.metadata.create_all)
    fabrica = async_sessionmaker(motor, expire_on_commit=False)
    async with fabrica() as sesion:
        yield sesion
    await motor.dispose()


@pytest_asyncio.fixture
async def motor() -> AsyncIterator[MotorServicio]:
    async with motor_sqlite() as m:
        yield m


async def _sembrar_colegios(sesion) -> None:
    colegio = Colegio(
        id=derivar("colegio", "2.4"),
        nombre="Colegio San Pedro",
        dane="311001093652",
        logo_url="https://cdn.tukit.co/colegios/san-pedro.png",
        sitio_web="https://sanpedro.edu.co",
        contacto_nombre="Secretaria academica",
        contacto_email="secretaria@sanpedro.edu.co",
        contacto_telefono="+57 1 2345678",
        direccion="Calle 1 # 2-3, Bogota",
    )
    sesion.add(colegio)
    await sesion.flush()
    sesion.add(Sede(id=derivar("sede", "2.4", "Sede unica"), colegio_id=colegio.id, nombre="Sede unica"))
    sesion.add(Colegio(id=derivar("colegio", "9.9"), nombre="Colegio Sin Perfil"))


@pytest.fixture()
async def cliente():
    async with cliente_api(_sembrar_colegios) as http:
        yield http


@pytest.fixture
def id_nuevo():
    return lambda: uuid.uuid4()


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
