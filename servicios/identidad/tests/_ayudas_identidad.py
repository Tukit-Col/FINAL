"""Ayudas compartidas por las pruebas de Identidad.

Aqui viven las piezas que mas de un archivo de prueba necesita: sembrar filas
del modelo, montar un `MotorServicio` sobre SQLite en memoria y abrir un
cliente HTTP contra la app real. Ningun archivo de prueba importa de otro: lo
comun se importa de este modulo y las fixtures viven en `conftest.py`.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager

import httpx
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool
from tukit_comun.bd import MotorServicio
from tukit_comun.identificadores import derivar
from tukit_identidad.api import app
from tukit_identidad.dominio.sesiones import emitir_token, hashear_clave
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

Sembrador = Callable[[AsyncSession], Awaitable[None]]


# ------------------------------------------------------------------ motores


@asynccontextmanager
async def motor_sqlite() -> AsyncIterator[MotorServicio]:
    """Un `MotorServicio` sobre SQLite en memoria con el esquema de Identidad,
    con el mismo API que el runtime (`motor.sesion()`, `motor.engine`)."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conexion:
        await conexion.run_sync(Base.metadata.create_all)
    fabrica = async_sessionmaker(engine, expire_on_commit=False)
    try:
        yield MotorServicio(servicio="identidad", engine=engine, _fabrica=fabrica)
    finally:
        await engine.dispose()


@asynccontextmanager
async def cliente_api(sembrar: Sembrador | None = None) -> AsyncIterator[httpx.AsyncClient]:
    """Un cliente HTTP contra la app real, sobre una base SQLite en memoria.

    `StaticPool` comparte la unica conexion entre la siembra y las peticiones,
    asi que lo sembrado por `sembrar` (que recibe una sesion y hace commit al
    salir) lo ve la app. La base queda en `app.state.motor`."""
    engine = create_async_engine(
        "sqlite+aiosqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False}
    )
    async with engine.begin() as conexion:
        await conexion.run_sync(Base.metadata.create_all)
    fabrica = async_sessionmaker(engine, expire_on_commit=False)
    if sembrar is not None:
        async with fabrica() as sesion:
            await sembrar(sesion)
            await sesion.commit()
    app.state.motor = MotorServicio(servicio="prueba", engine=engine, _fabrica=fabrica)
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://prueba"
        ) as http:
            yield http
    finally:
        await engine.dispose()


async def sembrar_rol_acudiente_y_colegio(sesion: AsyncSession) -> None:
    """El rol `acudiente` (la cuenta lo asigna al crearse) y San Pedro ("2.4")
    con la sede `derivar("sede", "2.4", "u")`, donde se registran los hijos."""
    sesion.add(Rol(codigo="acudiente", nombre="Acudiente", del_sistema=True))
    colegio = Colegio(id=derivar("colegio", "2.4"), nombre="Colegio San Pedro")
    sesion.add(colegio)
    await sesion.flush()
    sesion.add(Sede(id=derivar("sede", "2.4", "u"), colegio_id=colegio.id, nombre="Sede unica"))


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def sembrar_usuario_con_rol(correo: str, rol: str) -> tuple[uuid.UUID, str]:
    """Usuario con credencial real + un rol GLOBAL vigente en `app.state.motor`;
    devuelve (id, token).

    Siembra directo (no por /v1/registro) porque el registro no asigna roles. El
    ambito va global/`ambito_id=None` para satisfacer el CHECK
    `asignacion_ambito_coherente` que SQLite si aplica (las FK no, por eso no hace
    falta sembrar la tabla `rol`).
    """
    async with app.state.motor.sesion() as sesion:
        u = Usuario(correo=correo, clave_hash=hashear_clave("demo1234"))
        sesion.add(u)
        await sesion.flush()
        sesion.add(AsignacionRol(usuario_id=u.id, rol_codigo=rol, ambito_tipo="global", ambito_id=None))
        uid = u.id
    return uid, emitir_token(uid, version_permisos=1)


# ------------------------------------------------------------------ siembra


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
