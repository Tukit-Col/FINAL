from __future__ import annotations

import socket
import uuid
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session
from tukit_catalogo.modelos import (
    Base,
    Concepto,
    EdicionLibro,
    Nivel,
    OfertaTienda,
    ProductoCanonico,
    Tienda,
)
from tukit_comun.cache import usar_cliente

CURADOR = uuid.UUID("00000000-0000-0000-0000-0000000000c1")


@pytest.fixture(autouse=True)
def _sin_redis(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.delenv("REDIS_URL", raising=False)
    usar_cliente(None)
    yield
    usar_cliente(None)


@pytest.fixture()
def sesion() -> Session:
    motor = create_engine("sqlite://")

    @event.listens_for(motor, "connect")
    def _activar_fk(conexion, _registro):  # noqa: ANN001
        conexion.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(motor)
    with Session(motor) as s:
        yield s


def ahora() -> datetime:
    return datetime.now(UTC)


def crear_concepto(sesion: Session, codigo: str = "cuaderno", **kw) -> Concepto:
    c = Concepto(
        codigo=codigo,
        nombre_canonico=kw.pop("nombre", codigo),
        categoria=kw.pop("categoria", "escritura"),
        **kw,
    )
    sesion.add(c)
    sesion.flush()
    return c


def crear_producto(
    sesion: Session, concepto: Concepto, nivel: Nivel = Nivel.CONFIABLE, **kw
) -> ProductoCanonico:
    sufijo = uuid.uuid4().hex[:8]
    p = ProductoCanonico(
        concepto_id=concepto.id,
        sku_interno=kw.pop("sku", f"TK-{sufijo}"),
        nombre=kw.pop("nombre", f"{concepto.nombre_canonico} {nivel.value}"),
        nivel=nivel.value,
        curado_por=kw.pop("curado_por", CURADOR),
        **kw,
    )
    sesion.add(p)
    sesion.flush()
    return p


def crear_tienda(sesion: Session, slug: str = "exito", tipo: str = "minorista") -> Tienda:
    t = Tienda(slug=slug, nombre=slug.title(), tipo=tipo)
    sesion.add(t)
    sesion.flush()
    return t


def crear_oferta(
    sesion: Session,
    producto: ProductoCanonico,
    tienda: Tienda,
    metodo: str = "ean",
    confianza: float = 1.000,
    **kw,
) -> OfertaTienda:
    o = OfertaTienda(
        producto_canonico_id=producto.id,
        tienda_id=tienda.id,
        referencia_externa=kw.pop("referencia", uuid.uuid4().hex[:10]),
        metodo_vinculacion=metodo,
        confianza_vinculacion=confianza,
        **kw,
    )
    sesion.add(o)
    sesion.flush()
    return o


def crear_edicion(sesion: Session, isbn: str, programa: str = "nacional", **kw) -> EdicionLibro:
    e = EdicionLibro(
        isbn13=isbn,
        titulo=kw.pop("titulo", f"Texto {isbn[-4:]}"),
        editorial=kw.pop("editorial", "Norma"),
        anio_edicion=kw.pop("anio_edicion", 2025),
        area=kw.pop("area", "matematicas"),
        programa=programa,
        **kw,
    )
    sesion.add(e)
    sesion.flush()
    return e


def en_dias(n: int) -> datetime:
    return ahora() + timedelta(days=n)


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
