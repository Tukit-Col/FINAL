from __future__ import annotations

import socket
import uuid
from collections.abc import AsyncIterator, Iterator

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from tukit_operacion.modelos import Base


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


OPERADOR = "44444444-4444-5444-8444-444444444444"
ADMIN = "55555555-5555-5555-8555-555555555555"
ACUDIENTE = "22222222-2222-5222-8222-222222222222"
TOKEN_OPERADOR = "token-operador"
TOKEN_ADMIN = "token-admin"
TOKEN_ACUDIENTE = "token-acudiente"


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _sesion(usuario: str, rol: str) -> dict:
    return {"usuario_id": usuario, "correo": f"{rol}@tukit.test", "roles": [{"rol": rol, "ambito": None}]}


class IdentidadFalsa:
    def __init__(self, usuario_id: str | None = None, *, caida: bool = False) -> None:
        self.usuario_id = usuario_id or str(uuid.uuid4())
        self.llamadas: list[tuple[str, str | None]] = []
        self.caida = caida
        self.sesiones = {
            TOKEN_OPERADOR: _sesion(OPERADOR, "operador"),
            TOKEN_ADMIN: _sesion(ADMIN, "admin"),
            TOKEN_ACUDIENTE: _sesion(ACUDIENTE, "acudiente"),
        }

    async def sesion(self, token: str):
        if self.caida:
            from tukit_operacion.remoto import IdentidadCaida

            raise IdentidadCaida("identidad no responde")
        return self.sesiones.get(token)

    async def resolver_contacto(self, correo: str, celular: str | None = None) -> str | None:
        self.llamadas.append((correo, celular))
        return self.usuario_id


ACUDIENTE = "22222222-2222-5222-8222-222222222222"
OTRO_ACUDIENTE = "33333333-3333-5333-8333-333333333333"
TOKEN_ACUDIENTE = "token-acudiente"
TOKEN_OTRO = "token-otro"


class IdentidadConSesiones(IdentidadFalsa):
    def __init__(self, caida: bool = False) -> None:
        super().__init__()
        self.caida = caida
        self.sesiones = {
            **self.sesiones,
            TOKEN_ACUDIENTE: {"usuario_id": ACUDIENTE, "correo": "a@x.com", "roles": []},
            TOKEN_OTRO: {"usuario_id": OTRO_ACUDIENTE, "correo": "b@x.com", "roles": []},
        }

    async def sesion(self, token: str):
        from tukit_operacion.remoto import IdentidadCaida

        if self.caida:
            raise IdentidadCaida("no responde")
        return self.sesiones.get(token)


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
