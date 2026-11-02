"""Tickets del back-office: puerta de staff, transiciones de estado y respuesta.

Se prueba por HTTP contra la app real con SQLite en memoria y un doble de
Identidad que mapea token -> sesion. Lo que se defiende:

- **Acceso.** Bandeja, detalle, responder, estado y vinculo son de operador/admin:
  401 sin sesion, 403 con otro rol, 503 si Identidad no responde (falla cerrada).
- **Transiciones.** Solo las de `TRANSICIONES_CASO`; `cerrado` es terminal.
- **Responder.** Guarda la respuesta, encola el aviso SIN el texto y no deja el
  contacto en ningun lado; un ticket cerrado no admite respuestas.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator

import httpx
import pytest
import pytest_asyncio
from conftest import TOKEN_ACUDIENTE, TOKEN_ADMIN, TOKEN_OPERADOR, IdentidadFalsa, bearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from tukit_comun.bd import MotorServicio
from tukit_operacion.api import app
from tukit_operacion.dominio.casos import TRANSICIONES_CASO, validar_cambio_estado, validar_respuesta
from tukit_operacion.modelos import Base, EstadoCaso

BANDEJA = Base.metadata.tables["bandeja_salida"]
AUDITORIA = Base.metadata.tables["registro_auditoria"]
STAFF = bearer(TOKEN_OPERADOR)
USUARIO = str(uuid.uuid4())


@pytest_asyncio.fixture
async def cliente() -> AsyncIterator[httpx.AsyncClient]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conexion:
        await conexion.run_sync(Base.metadata.create_all)
    fabrica = async_sessionmaker(engine, expire_on_commit=False)
    app.state.motor = MotorServicio(servicio="prueba", engine=engine, _fabrica=fabrica)
    app.state.identidad = IdentidadFalsa(USUARIO)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://prueba") as http:
        yield http
    await engine.dispose()


async def _abrir(cliente, **kw) -> str:
    cuerpo = {
        "categoria": "reclamo",
        "asunto": "Llego incompleto",
        "descripcion": "Faltan dos cuadernos.",
        "contacto": {"correo": "papa@ejemplo.com", "celular": "3001234567"},
        **kw,
    }
    return (await cliente.post("/v1/operacion/casos", json=cuerpo)).json()["caso_id"]


async def _filas(tabla):
    async with app.state.motor.sesion() as db:
        return list(await (await db.connection()).execute(select(tabla)))


# ---------------------------------------------------------------------------
# Acceso
# ---------------------------------------------------------------------------

CASOS_DE_ACCESO = [
    ({}, 401),
    (bearer("token-que-no-existe"), 401),
    (bearer(TOKEN_ACUDIENTE), 403),
    (bearer(TOKEN_OPERADOR), 200),
    (bearer(TOKEN_ADMIN), 200),
]


@pytest.mark.parametrize(("headers", "esperado"), CASOS_DE_ACCESO)
async def test_bandeja_solo_para_staff(cliente, headers, esperado):
    assert (await cliente.get("/v1/operacion/casos", headers=headers)).status_code == esperado


@pytest.mark.parametrize(("headers", "esperado"), CASOS_DE_ACCESO)
async def test_detalle_solo_para_staff(cliente, headers, esperado):
    caso = await _abrir(cliente)
    assert (await cliente.get(f"/v1/operacion/casos/{caso}", headers=headers)).status_code == esperado


@pytest.mark.parametrize(("headers", "esperado"), CASOS_DE_ACCESO)
async def test_responder_solo_para_staff_y_un_rechazo_no_escribe(cliente, headers, esperado):
    caso = await _abrir(cliente)
    respuesta = await cliente.post(
        f"/v1/operacion/casos/{caso}/responder", headers=headers, json={"texto": "Ya lo revisamos."}
    )
    assert respuesta.status_code == esperado
    if esperado != 200:
        assert [f for f in await _filas(BANDEJA) if f.tipo == "caso_respuesta"] == []
        assert await _filas(AUDITORIA) == []


@pytest.mark.parametrize("headers", [{}, bearer(TOKEN_ACUDIENTE)])
async def test_estado_y_vinculo_rechazan_a_quien_no_es_staff(cliente, headers):
    caso = await _abrir(cliente)
    estado = await cliente.post(f"/v1/operacion/casos/{caso}/estado", headers=headers, json={"destino": "resuelto"})
    vinculo = await cliente.post(
        f"/v1/operacion/casos/{caso}/pedido", headers=headers, json={"pedido_id": str(uuid.uuid4())}
    )
    assert estado.status_code in (401, 403)
    assert vinculo.status_code in (401, 403)
    assert (await cliente.get(f"/v1/operacion/casos/{caso}", headers=STAFF)).json()["estado"] == "abierto"


@pytest.mark.parametrize("ruta", ["/v1/operacion/casos", f"/v1/operacion/casos/{uuid.uuid4()}"])
async def test_identidad_caida_falla_cerrada_con_503(cliente, ruta):
    app.state.identidad = IdentidadFalsa(caida=True)
    assert (await cliente.get(ruta, headers=STAFF)).status_code == 503


async def test_el_alta_del_acudiente_sigue_sin_sesion(cliente):
    # La puerta de staff no toca el alta: el acudiente abre su PQRS sin token.
    assert await _abrir(cliente)


# ---------------------------------------------------------------------------
# Transiciones de estado
# ---------------------------------------------------------------------------


def test_cerrado_es_terminal_y_resuelto_se_puede_reabrir():
    assert TRANSICIONES_CASO[EstadoCaso.CERRADO] == frozenset()
    assert validar_cambio_estado("resuelto", "en_gestion") is None
    assert validar_cambio_estado("cerrado", "abierto").razon == "transicion_invalida"


def test_no_se_vuelve_a_abierto_ni_se_inventa_un_estado():
    assert validar_cambio_estado("en_gestion", "abierto").estado == 409
    rechazo = validar_cambio_estado("abierto", "inventado")
    assert (rechazo.razon, rechazo.estado) == ("estado_invalido", 422)


def test_respuesta_vacia_larga_o_a_ticket_cerrado_se_rechaza():
    assert validar_respuesta("abierto", "   ")[1].razon == "respuesta_vacia"
    assert validar_respuesta("abierto", "x" * 2001)[1].razon == "respuesta_larga"
    assert validar_respuesta("cerrado", "hola")[1].razon == "caso_cerrado"
    assert validar_respuesta("abierto", "  hola  ") == ("hola", None)


async def test_cambiar_estado_deja_evento_y_auditoria_y_marca_resuelto(cliente):
    caso = await _abrir(cliente)
    respuesta = await cliente.post(f"/v1/operacion/casos/{caso}/estado", headers=STAFF, json={"destino": "resuelto"})
    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo["estado"] == "resuelto"
    assert cuerpo["resuelto_en"] is not None
    assert cuerpo["eventos"][-1]["datos"] == {"desde": "abierto", "hacia": "resuelto"}
    assert [f.accion for f in await _filas(AUDITORIA)] == ["caso_estado"]


async def test_transicion_ilegal_da_409_y_no_escribe(cliente):
    caso = await _abrir(cliente)
    await cliente.post(f"/v1/operacion/casos/{caso}/estado", headers=STAFF, json={"destino": "resuelto"})
    await cliente.post(f"/v1/operacion/casos/{caso}/estado", headers=STAFF, json={"destino": "cerrado"})
    respuesta = await cliente.post(f"/v1/operacion/casos/{caso}/estado", headers=STAFF, json={"destino": "en_gestion"})
    assert respuesta.status_code == 409
    assert respuesta.json()["error"] == "transicion_invalida"
    assert len(await _filas(AUDITORIA)) == 2


async def test_reabrir_un_resuelto_limpia_resuelto_en(cliente):
    caso = await _abrir(cliente)
    await cliente.post(f"/v1/operacion/casos/{caso}/estado", headers=STAFF, json={"destino": "resuelto"})
    reabierto = await cliente.post(f"/v1/operacion/casos/{caso}/estado", headers=STAFF, json={"destino": "en_gestion"})
    assert reabierto.json()["resuelto_en"] is None


# ---------------------------------------------------------------------------
# Responder
# ---------------------------------------------------------------------------


async def test_responder_guarda_la_respuesta_avisa_y_pasa_a_gestion(cliente):
    caso = await _abrir(cliente)
    respuesta = await cliente.post(
        f"/v1/operacion/casos/{caso}/responder", headers=STAFF, json={"texto": "  Te enviamos los dos cuadernos.  "}
    )
    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo["estado"] == "en_gestion"
    textos = [e["datos"]["texto"] for e in cuerpo["eventos"] if e["tipo"] == "respuesta"]
    assert textos == ["Te enviamos los dos cuadernos."]

    avisos = [f for f in await _filas(BANDEJA) if f.tipo == "caso_respuesta"]
    assert len(avisos) == 1
    assert str(avisos[0].agregado_id) == caso
    # El aviso no lleva ni el texto ni el contacto del acudiente.
    carga = str(avisos[0].carga)
    assert "cuadernos" not in carga
    assert "papa@ejemplo.com" not in carga
    assert USUARIO in carga


async def test_responder_a_un_ticket_cerrado_da_409_y_no_avisa(cliente):
    caso = await _abrir(cliente)
    for destino in ("resuelto", "cerrado"):
        await cliente.post(f"/v1/operacion/casos/{caso}/estado", headers=STAFF, json={"destino": destino})
    respuesta = await cliente.post(f"/v1/operacion/casos/{caso}/responder", headers=STAFF, json={"texto": "Hola"})
    assert respuesta.status_code == 409
    assert [f for f in await _filas(BANDEJA) if f.tipo == "caso_respuesta"] == []


async def test_responder_con_texto_vacio_da_422(cliente):
    caso = await _abrir(cliente)
    respuesta = await cliente.post(f"/v1/operacion/casos/{caso}/responder", headers=STAFF, json={"texto": "  "})
    assert respuesta.status_code == 422
    assert respuesta.json()["campo"] == "texto"


async def test_detalle_trae_descripcion_y_titular_para_el_back_office(cliente):
    caso = await _abrir(cliente)
    detalle = (await cliente.get(f"/v1/operacion/casos/{caso}", headers=STAFF)).json()
    assert detalle["descripcion"] == "Faltan dos cuadernos."
    assert detalle["usuario_id"] == USUARIO
    assert detalle["eventos"] == []


async def test_vincular_pedido(cliente):
    caso = await _abrir(cliente)
    pedido = str(uuid.uuid4())
    respuesta = await cliente.post(f"/v1/operacion/casos/{caso}/pedido", headers=STAFF, json={"pedido_id": pedido})
    assert respuesta.status_code == 200
    assert respuesta.json()["pedido_id"] == pedido
    malo = await cliente.post(f"/v1/operacion/casos/{caso}/pedido", headers=STAFF, json={"pedido_id": "no-es-uuid"})
    assert malo.status_code == 422
