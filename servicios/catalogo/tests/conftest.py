"""Utilidades de prueba del servicio de Catalogo."""

from __future__ import annotations

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
    """Las pruebas corren sin Redis aunque quien las lance tenga `REDIS_URL`.

    Con la variable, el vector de un renglon se guardaria en Redis (ADR 0047) y
    una prueba dejaria de llamar a su embeder. Las que prueban la cache ponen su
    doble con `usar_cliente`.
    """
    monkeypatch.delenv("REDIS_URL", raising=False)
    usar_cliente(None)
    yield
    usar_cliente(None)


@pytest.fixture()
def sesion() -> Session:
    motor = create_engine("sqlite://")

    # SQLite no verifica llaves foraneas ni restricciones CHECK de tabla a
    # menos que se le pida. Sin esto las pruebas pasarian sin probar nada.
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
