"""Banco de pruebas de Identidad: SQLite en memoria, sin base externa.

Los modelos usan tipos portables a proposito, asi que el mismo esquema corre
aqui y en Postgres. Los indices parciales se declaran con `postgresql_where` y
`sqlite_where` a la vez: si en SQLite degradaran a indices totales, la prueba
del historial de asignaciones pasaria por el motivo equivocado.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator

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


@pytest.fixture(autouse=True)
def _sin_broker(monkeypatch: pytest.MonkeyPatch) -> None:
    """Las pruebas corren sin RabbitMQ aunque quien las lance tenga `RABBITMQ_URL`.

    La variable cambia el modo del sondeador de colegios (ADR 0046): con ella
    consume su cola en vez de sondear. Las que prueban el modo con broker la
    ponen ellas.
    """
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
