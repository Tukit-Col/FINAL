from __future__ import annotations

import httpx
import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool
from tukit_comun.bd import MotorServicio
from tukit_comun.cifrado import cifrador_desde_entorno
from tukit_identidad.api import app
from tukit_identidad.dominio.sesiones import emitir_token
from tukit_identidad.modelos import (
    AsignacionRol,
    Base,
    Clasificacion,
    Permiso,
    Rol,
    RolPermiso,
    Usuario,
)


@pytest.fixture()
async def entorno():
    engine = create_async_engine(
        "sqlite+aiosqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False}
    )
    async with engine.begin() as conexion:
        await conexion.run_sync(Base.metadata.create_all)

    cifrador = cifrador_desde_entorno()
    fabrica = async_sessionmaker(engine, expire_on_commit=False)
    async with fabrica() as s:
        s.add_all(
            [
                Rol(codigo="admin", nombre="Admin", del_sistema=True),
                Rol(codigo="acudiente", nombre="Acudiente", del_sistema=True),
                Permiso(
                    codigo="usuario:leer:nombre",
                    recurso="usuario",
                    accion="leer",
                    campo="nombre",
                    clasificacion_minima=Clasificacion.PERSONAL.value,
                ),
            ]
        )
        await s.flush()
        s.add(RolPermiso(rol_codigo="admin", permiso_codigo="usuario:leer:nombre"))

        admin = Usuario(correo="admin@tukit.co", clave_hash="x")
        acudiente = Usuario(correo="acu@ejemplo.com", clave_hash="x")
        papa = Usuario(
            correo="papa@ejemplo.com",
            clave_hash="x",
            nombre_cifrado=cifrador.cifrar(b"Pedro Perez"),
        )
        s.add_all([admin, acudiente, papa])
        await s.flush()
        s.add_all(
            [
                AsignacionRol(usuario_id=admin.id, rol_codigo="admin", ambito_tipo="global", ambito_id=None),
                AsignacionRol(
                    usuario_id=acudiente.id, rol_codigo="acudiente", ambito_tipo="global", ambito_id=None
                ),
            ]
        )
        await s.commit()
        ids = {"admin": admin.id, "acudiente": acudiente.id, "papa": papa.id}
        vps = {"admin": admin.version_permisos, "acudiente": acudiente.version_permisos}

    app.state.motor = MotorServicio(servicio="prueba", engine=engine, _fabrica=fabrica)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://prueba") as http:
        yield http, ids, vps
    await engine.dispose()


def _bearer(uid, vp) -> dict[str, str]:
    return {"Authorization": f"Bearer {emitir_token(uid, version_permisos=vp)}"}


async def test_admin_resuelve_el_nombre_del_papa(entorno):
    http, ids, vps = entorno
    r = await http.get(
        "/v1/usuarios/nombres",
        params={"ids": str(ids["papa"])},
        headers=_bearer(ids["admin"], vps["admin"]),
    )
    assert r.status_code == 200
    assert r.json()["nombres"] == {str(ids["papa"]): "Pedro Perez"}


async def test_acudiente_sin_permiso_es_403(entorno):
    http, ids, vps = entorno
    r = await http.get(
        "/v1/usuarios/nombres",
        params={"ids": str(ids["papa"])},
        headers=_bearer(ids["acudiente"], vps["acudiente"]),
    )
    assert r.status_code == 403


async def test_id_sin_nombre_no_aparece(entorno):
    http, ids, vps = entorno
    r = await http.get(
        "/v1/usuarios/nombres",
        params={"ids": str(ids["admin"])},
        headers=_bearer(ids["admin"], vps["admin"]),
    )
    assert r.status_code == 200
    assert r.json()["nombres"] == {}
