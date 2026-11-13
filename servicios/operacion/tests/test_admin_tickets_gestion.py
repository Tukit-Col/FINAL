"""Gestión de tickets del back-office: asignar, prioridad, nota interna y conteos.

Se prueba por HTTP contra la app real con SQLite en memoria. Se defiende:

- **Acceso.** Solo staff (401 sin sesión, 403 con rol de acudiente).
- **Asignar.** "yo" fija el dueño, "nadie" lo suelta (solo el dueño o un admin);
  cada cambio deja su evento y su fila de auditoría.
- **Prioridad.** Solo valores conocidos; un ticket cerrado no se repriorizan.
- **Nota interna.** Nunca llega al acudiente (`mis-casos`).
"""

from __future__ import annotations

import json
import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta

import httpx
import pytest_asyncio
from conftest import (
    ADMIN,
    OPERADOR,
    TOKEN_ACUDIENTE,
    TOKEN_ADMIN,
    TOKEN_OPERADOR,
    IdentidadConSesiones,
    bearer,
)
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from tukit_comun.bd import MotorServicio
from tukit_operacion.api import app
from tukit_operacion.dominio.casos import validar_asignacion, validar_nota, validar_prioridad
from tukit_operacion.modelos import Base

CASO = Base.metadata.tables["caso"]
AUDITORIA = Base.metadata.tables["registro_auditoria"]
OP = bearer(TOKEN_OPERADOR)
ADM = bearer(TOKEN_ADMIN)
TEXTO_SECRETO = "nota-solo-para-el-equipo-xyz"


@pytest_asyncio.fixture
async def cliente() -> AsyncIterator[httpx.AsyncClient]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conexion:
        await conexion.run_sync(Base.metadata.create_all)
    fabrica = async_sessionmaker(engine, expire_on_commit=False)
    app.state.motor = MotorServicio(servicio="prueba", engine=engine, _fabrica=fabrica)
    app.state.identidad = IdentidadConSesiones()
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://prueba") as http:
        yield http
    await engine.dispose()


async def _abrir(cliente, token=TOKEN_ACUDIENTE, **kw) -> str:
    cuerpo = {"categoria": "reclamo", "asunto": "Llego incompleto", "descripcion": "Faltan dos cuadernos.", **kw}
    r = await cliente.post("/v1/operacion/mis-casos", json=cuerpo, headers=bearer(token))
    assert r.status_code == 201, r.text
    return r.json()["caso_id"]


async def _post(cliente, caso, accion, cuerpo, headers=OP):
    return await cliente.post(f"/v1/operacion/casos/{caso}/{accion}", json=cuerpo, headers=headers)


async def _poner(caso, **valores):
    async with app.state.motor.sesion() as db:
        await (await db.connection()).execute(update(CASO).where(CASO.c.id == uuid.UUID(caso)).values(**valores))


# --- dominio puro ----------------------------------------------------------


def test_reglas_puras():
    assert validar_prioridad("abierto", "alta") is None
    assert validar_prioridad("abierto", "critica").razon == "prioridad_invalida"
    assert validar_prioridad("cerrado", "alta").razon == "caso_cerrado"
    assert validar_asignacion("yo", None, OPERADOR, es_admin=False) is None
    assert validar_asignacion("nadie", OPERADOR, OPERADOR, es_admin=False) is None
    assert validar_asignacion("nadie", ADMIN, OPERADOR, es_admin=False).estado == 403
    assert validar_asignacion("nadie", ADMIN, OPERADOR, es_admin=True) is None
    assert validar_asignacion("otro", None, OPERADOR, es_admin=True).razon == "asignacion_invalida"
    assert validar_nota("  hola ")[0] == "hola"
    assert validar_nota("   ")[1].razon == "nota_vacia"
    assert validar_nota("x" * 2001)[1].razon == "nota_larga"


# --- asignar ---------------------------------------------------------------


async def test_asignar_yo_y_soltar(cliente):
    caso = await _abrir(cliente)
    r = await _post(cliente, caso, "asignar", {"asignar": "yo"})
    assert r.status_code == 200, r.text
    assert r.json()["asignado_a"] == OPERADOR
    eventos = [e for e in r.json()["eventos"] if e["tipo"] == "asignacion"]
    assert eventos[0]["datos"] == {"desde": None, "hacia": OPERADOR}
    assert eventos[0]["actor_id"] == OPERADOR

    r = await _post(cliente, caso, "asignar", {"asignar": "nadie"})
    assert r.json()["asignado_a"] is None
    acciones = [f.accion for f in await _filas(AUDITORIA)]
    assert acciones.count("caso_asignado") == 2


async def _filas(tabla):
    async with app.state.motor.sesion() as db:
        return list((await (await db.connection()).execute(select(tabla))))


async def test_relevo_a_otro_staff_y_soltar_ajeno(cliente):
    caso = await _abrir(cliente)
    await _post(cliente, caso, "asignar", {"asignar": "yo"}, headers=ADM)
    # el operador toma el relevo explicitamente
    r = await _post(cliente, caso, "asignar", {"asignar": "yo"})
    assert r.json()["asignado_a"] == OPERADOR
    # el admin lo suelta aunque no sea suyo; el operador no suelta el de otro
    await _post(cliente, caso, "asignar", {"asignar": "yo"}, headers=ADM)
    denegado = await _post(cliente, caso, "asignar", {"asignar": "nadie"})
    assert denegado.status_code == 403
    assert (await _post(cliente, caso, "asignar", {"asignar": "nadie"}, headers=ADM)).json()["asignado_a"] is None


async def test_asignar_validaciones_y_acceso(cliente):
    caso = await _abrir(cliente)
    assert (await _post(cliente, caso, "asignar", {"asignar": "otro"})).status_code == 422
    assert (await _post(cliente, str(uuid.uuid4()), "asignar", {"asignar": "yo"})).status_code == 404
    assert (await _post(cliente, caso, "asignar", {"asignar": "yo"}, headers={})).status_code == 401
    assert (
        await _post(cliente, caso, "asignar", {"asignar": "yo"}, headers=bearer(TOKEN_ACUDIENTE))
    ).status_code == 403


# --- prioridad -------------------------------------------------------------


async def test_prioridad_reordena_la_bandeja(cliente):
    a = await _abrir(cliente, asunto="primero")
    b = await _abrir(cliente, asunto="segundo")
    await _poner(a, prioridad="media")
    await _poner(b, prioridad="media")
    r = await _post(cliente, b, "prioridad", {"prioridad": "urgente"})
    assert r.status_code == 200
    assert r.json()["prioridad"] == "urgente"
    ev = [e for e in r.json()["eventos"] if e["tipo"] == "prioridad"][0]
    assert ev["datos"] == {"desde": "media", "hacia": "urgente"}
    bandeja = (await cliente.get("/v1/operacion/casos", headers=OP)).json()
    assert bandeja["casos"][0]["caso_id"] == b


async def test_prioridad_invalida_cerrado_y_acceso(cliente):
    caso = await _abrir(cliente)
    r = await _post(cliente, caso, "prioridad", {"prioridad": "critica"})
    assert r.status_code == 422
    await _poner(caso, estado="cerrado")
    r = await _post(cliente, caso, "prioridad", {"prioridad": "alta"})
    assert r.status_code == 422
    assert r.json()["error"] == "caso_cerrado"
    assert (await _post(cliente, caso, "prioridad", {"prioridad": "alta"}, headers={})).status_code == 401
    assert (
        await _post(cliente, caso, "prioridad", {"prioridad": "alta"}, headers=bearer(TOKEN_ACUDIENTE))
    ).status_code == 403


# --- nota interna ----------------------------------------------------------


async def test_nota_interna_es_de_staff_y_no_llega_al_acudiente(cliente):
    caso = await _abrir(cliente)
    r = await _post(cliente, caso, "nota", {"texto": f"  {TEXTO_SECRETO}  "})
    assert r.status_code == 200, r.text
    nota = [e for e in r.json()["eventos"] if e["tipo"] == "nota_interna"]
    assert nota[0]["datos"]["texto"] == TEXTO_SECRETO
    assert nota[0]["actor_id"] == OPERADOR

    vista = await cliente.get(f"/v1/operacion/mis-casos/{caso}", headers=bearer(TOKEN_ACUDIENTE))
    assert vista.status_code == 200
    assert TEXTO_SECRETO not in json.dumps(vista.json())
    lista = await cliente.get("/v1/operacion/mis-casos", headers=bearer(TOKEN_ACUDIENTE))
    assert TEXTO_SECRETO not in json.dumps(lista.json())


async def test_nota_vacia_o_larga_y_acceso(cliente):
    caso = await _abrir(cliente)
    assert (await _post(cliente, caso, "nota", {"texto": "   "})).status_code == 422
    assert (await _post(cliente, caso, "nota", {"texto": "x" * 2001})).status_code == 422
    assert (await _post(cliente, caso, "nota", {"texto": "ok"}, headers={})).status_code == 401
    assert (await _post(cliente, caso, "nota", {"texto": "ok"}, headers=bearer(TOKEN_ACUDIENTE))).status_code == 403


# --- conteos ---------------------------------------------------------------


async def test_resumen_cuenta_sin_asignar_y_vencidos(cliente):
    ayer = datetime.now(UTC) - timedelta(days=1)
    vencido_sin_dueno = await _abrir(cliente, asunto="a")
    vencido_asignado = await _abrir(cliente, asunto="b")
    resuelto_vencido = await _abrir(cliente, asunto="c")
    await _abrir(cliente, asunto="d")  # reciente, sin dueno
    await _poner(vencido_sin_dueno, vence_en=ayer)
    await _poner(vencido_asignado, vence_en=ayer)
    await _poner(resuelto_vencido, vence_en=ayer, estado="resuelto", resuelto_en=datetime.now(UTC))
    await _post(cliente, vencido_asignado, "asignar", {"asignar": "yo"})
    resumen = (await cliente.get("/v1/operacion/casos", headers=OP)).json()["resumen"]
    # sin dueno activos: a, d (b asignado, c resuelto no cuenta). Vencidos activos: a, b.
    assert resumen["sin_asignar"] == 2
    assert resumen["vencidos"] == 2
