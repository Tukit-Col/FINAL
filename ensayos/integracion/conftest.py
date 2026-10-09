"""Fixtures de las pruebas de integracion: el stack vivo, no SQLite.

Estas pruebas no corren con `make prueba` (que recoge `arquitectura libs
servicios`): necesitan los seis procesos levantados con `make backend` y las
bases de Postgres migradas. Se corren aparte:

    make backend
    .venv/bin/pytest ensayos/integracion -m integracion

Si el stack no responde, la sesion FALLA en vez de saltarse: una suite de
integracion que se salta en silencio es el verde fantasma que ya se le reprocha
al CI (Tukit-QA, H-C-03).

Todo pasa por el gateway, que es la unica puerta del frontend. Las bases se
consultan solo para comprobar lo que la API no muestra (la bandeja de salida,
lo que queda persistido); la URL de cada base sale de `url_desde_entorno`, la
misma que usan los servicios. Las constantes y los flujos compartidos viven en
`stack_vivo.py`.
"""

from __future__ import annotations

import socket
import uuid
from collections.abc import Awaitable, Callable, Iterator
from typing import Any

import httpx
import pytest
from sqlalchemy import text
from stack_vivo import CLAVE_DEMO, GATEWAY, USUARIOS_DEMO, conexion_a
from tukit_comun.http import CABECERA_CORRELACION


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


@pytest.fixture
def cliente(stack: dict[str, Any], correlacion_id: str) -> Iterator[httpx.Client]:
    """Cliente contra el gateway que manda el `correlacion_id` de la prueba."""
    with httpx.Client(base_url=GATEWAY, timeout=30.0, headers={CABECERA_CORRELACION: correlacion_id}) as http:
        yield http


@pytest.fixture(scope="session")
def sesiones(stack: dict[str, Any]) -> dict[str, dict[str, str]]:
    """Token y `usuario_id` de cada usuario de demostracion, por rol."""
    resultado: dict[str, dict[str, str]] = {}
    with httpx.Client(base_url=GATEWAY, timeout=30.0) as http:
        for rol, correo in USUARIOS_DEMO.items():
            respuesta = http.post("/v1/sesiones", json={"correo": correo, "clave": CLAVE_DEMO})
            if respuesta.status_code != 200:
                pytest.fail(
                    f"no se pudo entrar como {correo} ({respuesta.status_code}): falta sembrar_acceso"
                )
            cuerpo = respuesta.json()
            resultado[rol] = {"token": cuerpo["token"], "usuario_id": cuerpo["sesion"]["usuario_id"]}
    return resultado


@pytest.fixture(scope="session")
def producto(stack: dict[str, Any]) -> dict[str, Any]:
    """Un producto real del catalogo sembrado, con precio vigente."""
    respuesta = httpx.get(f"{GATEWAY}/v1/catalogo/productos", params={"por_pagina": 50}, timeout=30.0)
    con_precio = [p for p in respuesta.json()["productos"] if p.get("precio_desde")]
    if not con_precio:
        pytest.fail("el catalogo no tiene productos con precio; falta `make bd-sembrar`")
    return con_precio[0]


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
