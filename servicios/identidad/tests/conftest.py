"""Banco de pruebas de Identidad: SQLite en memoria, sin base externa.

Los modelos usan tipos portables a proposito, asi que el mismo esquema corre
aqui y en Postgres. Los indices parciales se declaran con `postgresql_where` y
`sqlite_where` a la vez: si en SQLite degradaran a indices totales, la prueba
del historial de asignaciones pasaria por el motivo equivocado.
"""

from __future__ import annotations

import socket
import uuid
from collections.abc import AsyncIterator, Iterator

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from tukit_identidad.modelos import (
    AcudienteMatricula,
    AmbitoTipo,
    AsignacionRol,
    Base,
    Colegio,
    Estudiante,
    Matricula,
    Permiso,
    Rol,
    RolPermiso,
    Sede,
    Usuario,
)


@pytest_asyncio.fixture
async def db() -> AsyncIterator[AsyncSession]:
    motor = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with motor.begin() as conexion:
        await conexion.run_sync(Base.metadata.create_all)
    fabrica = async_sessionmaker(motor, expire_on_commit=False)
    async with fabrica() as sesion:
        yield sesion
    await motor.dispose()


@pytest.fixture
def id_nuevo():
    return lambda: uuid.uuid4()


async def crear_usuario(db: AsyncSession, correo: str) -> Usuario:
    u = Usuario(correo=correo, clave_hash="x")
    db.add(u)
    await db.flush()
    return u


async def crear_colegio_con_sede(db: AsyncSession, nombre: str) -> tuple[Colegio, Sede]:
    colegio = Colegio(nombre=nombre)
    db.add(colegio)
    await db.flush()
    sede = Sede(colegio_id=colegio.id, nombre=f"{nombre} - sede principal")
    db.add(sede)
    await db.flush()
    return colegio, sede


async def crear_matricula(db: AsyncSession, sede: Sede, grado: str = "5", anio: int = 2026) -> Matricula:
    estudiante = Estudiante(nombre_cifrado=b"cifrado")
    db.add(estudiante)
    await db.flush()
    matricula = Matricula(
        estudiante_id=estudiante.id,
        sede_id=sede.id,
        colegio_id=sede.colegio_id,
        grado=grado,
        anio_lectivo=anio,
    )
    db.add(matricula)
    await db.flush()
    return matricula


async def vincular_acudiente(db: AsyncSession, usuario: Usuario, matricula: Matricula) -> None:
    db.add(AcudienteMatricula(usuario_id=usuario.id, matricula_id=matricula.id))
    await db.flush()


async def asignar(
    db: AsyncSession,
    usuario: Usuario,
    rol_codigo: str,
    tipo: AmbitoTipo,
    ambito_id: uuid.UUID | None = None,
    **extra,
) -> AsignacionRol:
    a = AsignacionRol(
        usuario_id=usuario.id, rol_codigo=rol_codigo, ambito_tipo=tipo.value, ambito_id=ambito_id, **extra
    )
    db.add(a)
    await db.flush()
    return a


async def crear_rol_con_permisos(db: AsyncSession, codigo: str, permisos: list[Permiso]) -> Rol:
    rol = Rol(codigo=codigo, nombre=codigo)
    db.add(rol)
    for p in permisos:
        db.add(p)
    await db.flush()
    for p in permisos:
        db.add(RolPermiso(rol_codigo=codigo, permiso_codigo=p.codigo))
    await db.flush()
    return rol


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
