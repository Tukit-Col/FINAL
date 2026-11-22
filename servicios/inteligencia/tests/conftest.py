from __future__ import annotations

import socket
import uuid
from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Any

import pytest
from sqlalchemy import event
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool
from tukit_comun.bd import MotorServicio
from tukit_comun.cache import usar_cliente
from tukit_inteligencia.modelos import Base

COLEGIO = "11111111-1111-5111-8111-111111111111"


@pytest.fixture(autouse=True)
def _sin_broker(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("RABBITMQ_URL", raising=False)


@pytest.fixture(autouse=True)
def _limitador_limpio() -> None:
    from tukit_inteligencia import nl2c

    nl2c.LIMITADOR.reiniciar()


@pytest.fixture(autouse=True)
def _sin_dobles_que_sobrevivan() -> Iterator[None]:
    yield
    from tukit_inteligencia import nl2c
    from tukit_inteligencia.api import app

    nl2c.usar_llamador(None)
    for puerto in ("renderizar", "leer"):
        if hasattr(app.state, puerto):
            delattr(app.state, puerto)


@pytest.fixture(autouse=True)
def _sin_redis(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.delenv("REDIS_URL", raising=False)
    usar_cliente(None)
    yield
    usar_cliente(None)


@pytest.fixture()
async def motor():
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )

    @event.listens_for(engine.sync_engine, "connect")
    def _activar_fk(conexion, _registro):  # noqa: ANN001
        cursor = conexion.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    async with engine.begin() as conexion:
        await conexion.run_sync(Base.metadata.create_all)
    fabrica = async_sessionmaker(engine, expire_on_commit=False)
    motor = MotorServicio(servicio="prueba", engine=engine, _fabrica=fabrica)
    yield motor
    await motor.cerrar()


def opcion(sku: str, nivel: str, precio: int | None, **kw: Any) -> dict[str, Any]:
    return {
        "sku": sku,
        "nombre": kw.pop("nombre", f"Producto {sku}"),
        "nivel": nivel,
        "precio_cop": precio,
        "personaje": kw.pop("personaje", None),
        "marca": kw.pop("marca", "Generica"),
        "imagen_url": kw.pop("imagen_url", None),
        "unidad_base": kw.pop("unidad_base", "unidad"),
        "unidades_por_empaque": kw.pop("unidades_por_empaque", 1),
        "atributos": kw.pop("atributos", {}),
        "cumple": kw.pop("cumple", True),
        "producto_id": kw.pop("producto_id", None),
    }


@dataclass
class CatalogoFalso:
    renglones: list[dict[str, Any]] = field(default_factory=list)
    respuestas: dict[str, dict[str, Any]] = field(default_factory=dict)
    grado: str = "Cuarto"
    llamadas: list[str] = field(default_factory=list)

    async def listas(self, *, colegio_id: str, grado: str, anio_lectivo: int | None = None) -> list[dict]:
        self.llamadas.append("listas")
        if grado != self.grado:
            return []
        return [{"lista_id": "lista-1", "grado": grado, "anio_lectivo": anio_lectivo or 2026}]

    async def lista(self, lista_id: str) -> dict[str, Any]:
        self.llamadas.append("lista")
        return {
            "lista_id": lista_id,
            "grado": self.grado,
            "total_items": len(self.renglones),
            "items": self.renglones,
        }

    async def producto(self, sku: str) -> dict[str, Any]:
        self.llamadas.append("producto")
        for respuesta in self.respuestas.values():
            for op in respuesta.get("opciones", []):
                if op["sku"] == sku:
                    return {
                        "sku": op["sku"],
                        "nombre": op["nombre"],
                        "marca": op.get("marca"),
                        "nivel": op["nivel"],
                        "personaje": op.get("personaje"),
                        "imagen_url": op.get("imagen_url"),
                        "unidad_base": op.get("unidad_base", "unidad"),
                        "unidades_por_empaque": op.get("unidades_por_empaque", 1),
                        "precio_desde": op.get("precio_cop"),
                        "concepto": {"codigo": respuesta.get("concepto_codigo"), "nombre": ""},
                    }
        raise KeyError(sku)

    async def productos_del_concepto(self, concepto: str, *, maximo: int = 40) -> list[dict[str, Any]]:
        self.llamadas.append("productos_del_concepto")
        salida: list[dict[str, Any]] = []
        for respuesta in self.respuestas.values():
            if respuesta.get("concepto_codigo") != concepto:
                continue
            for op in respuesta.get("opciones", []):
                if op.get("precio_cop") is None:
                    continue
                salida.append(
                    {
                        "sku": op["sku"],
                        "nombre": op["nombre"],
                        "marca": op.get("marca"),
                        "nivel": op["nivel"],
                        "personaje": op.get("personaje"),
                        "imagen_url": op.get("imagen_url"),
                        "unidad_base": op.get("unidad_base", "unidad"),
                        "unidades_por_empaque": op.get("unidades_por_empaque", 1),
                        "precio_desde": op.get("precio_cop"),
                        "concepto": {"codigo": concepto, "nombre": ""},
                    }
                )
        return salida[:maximo]

    async def productos_de_personaje(
        self, concepto: str, personaje: str, *, limite: int = 8
    ) -> list[dict[str, Any]]:
        producto = await self.producto_de_personaje(concepto, personaje)
        return [producto] if producto else []

    async def producto_de_personaje(self, concepto: str, personaje: str) -> dict[str, Any] | None:
        self.llamadas.append("producto_de_personaje")
        respuesta = next((r for r in self.respuestas.values() if r.get("concepto_codigo") == concepto), None)
        for op in (respuesta or {}).get("opciones", []):
            if str(op.get("personaje") or "").lower() == personaje.lower():
                return {
                    "sku": op["sku"],
                    "nombre": op["nombre"],
                    "marca": op.get("marca"),
                    "nivel": op["nivel"],
                    "personaje": op.get("personaje"),
                    "imagen_url": op.get("imagen_url"),
                    "unidad_base": op.get("unidad_base", "unidad"),
                    "unidades_por_empaque": op.get("unidades_por_empaque", 1),
                    "precio_desde": op.get("precio_cop"),
                }
        return None

    async def emparejar(
        self, renglones: list[str], conceptos: list[str | None] | None = None
    ) -> list[dict[str, Any]]:
        self.llamadas.append("emparejar")
        self.conceptos_asignados = conceptos
        return [
            self.respuestas.get(
                texto,
                {
                    "texto": texto,
                    "estado": "sin_match",
                    "concepto_codigo": None,
                    "concepto_nombre": None,
                    "parecido": 0.0,
                    "atributos_impuestos": {},
                    "motivo": "No reconocemos que pide este renglon.",
                    "opciones": [],
                },
            )
            for texto in renglones
        ]


def renglon(orden: int, texto: str, **kw: Any) -> dict[str, Any]:
    return {
        "orden": orden,
        "texto_original": texto,
        "cantidad": kw.pop("cantidad", 1),
        "tipo_item": kw.pop("tipo_item", "util"),
        "modo_adquisicion": kw.pop("modo_adquisicion", "mercado_abierto"),
        "instruccion_colegio": kw.pop("instruccion_colegio", None),
        "url_externa": kw.pop("url_externa", None),
    }


def reconocido(texto: str, codigo: str, opciones: list[dict[str, Any]], parecido: float = 0.95) -> dict:
    return {
        "texto": texto,
        "estado": "reconocido",
        "concepto_codigo": codigo,
        "concepto_nombre": codigo.lower(),
        "parecido": parecido,
        "atributos_impuestos": {},
        "motivo": "",
        "opciones": opciones,
    }


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
