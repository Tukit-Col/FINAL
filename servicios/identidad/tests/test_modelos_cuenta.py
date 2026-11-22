from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool
from tukit_identidad.modelos import (
    AcudienteMatricula,
    Base,
    Colegio,
    Estudiante,
    Matricula,
    Sede,
    Usuario,
)


@pytest.fixture()
async def sesion():
    engine = create_async_engine(
        "sqlite+aiosqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False}
    )
    async with engine.begin() as conexion:
        await conexion.run_sync(Base.metadata.create_all)
    fabrica = async_sessionmaker(engine, expire_on_commit=False)
    async with fabrica() as s:
        yield s
    await engine.dispose()


async def test_el_usuario_guarda_celular(sesion):
    u = Usuario(correo="mama@ejemplo.com", clave_hash="x", celular="+57 300 1234567")
    sesion.add(u)
    await sesion.commit()
    await sesion.refresh(u)
    assert u.celular == "+57 300 1234567"


async def test_el_vinculo_guarda_apodo_cifrado(sesion):
    colegio = Colegio(nombre="Colegio X")
    sesion.add(colegio)
    await sesion.flush()
    sede = Sede(colegio_id=colegio.id, nombre="Sede unica")
    estudiante = Estudiante(nombre_cifrado=b"cifrado")
    sesion.add_all([sede, estudiante])
    await sesion.flush()
    matricula = Matricula(
        estudiante_id=estudiante.id,
        sede_id=sede.id,
        colegio_id=colegio.id,
        grado="Tercero",
        anio_lectivo=2026,
    )
    usuario = Usuario(correo="papa@ejemplo.com", clave_hash="x")
    sesion.add_all([matricula, usuario])
    await sesion.flush()
    vinculo = AcudienteMatricula(
        usuario_id=usuario.id, matricula_id=matricula.id, apodo_cifrado=b"apodo-cifrado"
    )
    sesion.add(vinculo)
    await sesion.commit()
    await sesion.refresh(vinculo)
    assert vinculo.apodo_cifrado == b"apodo-cifrado"
