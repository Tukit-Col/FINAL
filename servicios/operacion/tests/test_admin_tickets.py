from __future__ import annotations

import json
import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta

import httpx
import pytest
import pytest_asyncio
from conftest import ADMIN, OPERADOR, TOKEN_ACUDIENTE, TOKEN_ADMIN, TOKEN_OPERADOR, IdentidadFalsa, bearer
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from tukit_comun.bd import MotorServicio
from tukit_operacion.api import app
from tukit_operacion.dominio.casos import (
    TRANSICIONES_CASO,
    validar_asignacion,
    validar_cambio_estado,
    validar_nota,
    validar_prioridad,
    validar_respuesta,
)
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
    estado = await cliente.post(
        f"/v1/operacion/casos/{caso}/estado", headers=headers, json={"destino": "resuelto"}
    )
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
    assert await _abrir(cliente)


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
    respuesta = await cliente.post(
        f"/v1/operacion/casos/{caso}/estado", headers=STAFF, json={"destino": "resuelto"}
    )
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
    respuesta = await cliente.post(
        f"/v1/operacion/casos/{caso}/estado", headers=STAFF, json={"destino": "en_gestion"}
    )
    assert respuesta.status_code == 409
    assert respuesta.json()["error"] == "transicion_invalida"
    assert len(await _filas(AUDITORIA)) == 2


async def test_reabrir_un_resuelto_limpia_resuelto_en(cliente):
    caso = await _abrir(cliente)
    await cliente.post(f"/v1/operacion/casos/{caso}/estado", headers=STAFF, json={"destino": "resuelto"})
    reabierto = await cliente.post(
        f"/v1/operacion/casos/{caso}/estado", headers=STAFF, json={"destino": "en_gestion"}
    )
    assert reabierto.json()["resuelto_en"] is None


async def test_responder_guarda_la_respuesta_avisa_y_pasa_a_gestion(cliente):
    caso = await _abrir(cliente)
    respuesta = await cliente.post(
        f"/v1/operacion/casos/{caso}/responder",
        headers=STAFF,
        json={"texto": "  Te enviamos los dos cuadernos.  "},
    )
    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo["estado"] == "en_gestion"
    textos = [e["datos"]["texto"] for e in cuerpo["eventos"] if e["tipo"] == "respuesta"]
    assert textos == ["Te enviamos los dos cuadernos."]

    avisos = [f for f in await _filas(BANDEJA) if f.tipo == "caso_respuesta"]
    assert len(avisos) == 1
    assert str(avisos[0].agregado_id) == caso
    carga = str(avisos[0].carga)
    assert "cuadernos" not in carga
    assert "papa@ejemplo.com" not in carga
    assert USUARIO in carga


async def test_responder_a_un_ticket_cerrado_da_409_y_no_avisa(cliente):
    caso = await _abrir(cliente)
    for destino in ("resuelto", "cerrado"):
        await cliente.post(f"/v1/operacion/casos/{caso}/estado", headers=STAFF, json={"destino": destino})
    respuesta = await cliente.post(
        f"/v1/operacion/casos/{caso}/responder", headers=STAFF, json={"texto": "Hola"}
    )
    assert respuesta.status_code == 409
    assert [f for f in await _filas(BANDEJA) if f.tipo == "caso_respuesta"] == []


async def test_responder_con_texto_vacio_da_422(cliente):
    caso = await _abrir(cliente)
    respuesta = await cliente.post(
        f"/v1/operacion/casos/{caso}/responder", headers=STAFF, json={"texto": "  "}
    )
    assert respuesta.status_code == 422
    assert respuesta.json()["campo"] == "texto"


async def test_detalle_trae_descripcion_y_titular_para_el_back_office(cliente):
    caso = await _abrir(cliente)
    detalle = (await cliente.get(f"/v1/operacion/casos/{caso}", headers=STAFF)).json()
    assert detalle["descripcion"] == "Faltan dos cuadernos."
    assert detalle["usuario_id"] == USUARIO
    assert detalle["eventos"] == []


async def test_vincular_un_pedido_a_un_caso_responde_200_y_un_id_invalido_422(cliente):
    caso = await _abrir(cliente)
    pedido = str(uuid.uuid4())
    respuesta = await cliente.post(
        f"/v1/operacion/casos/{caso}/pedido", headers=STAFF, json={"pedido_id": pedido}
    )
    assert respuesta.status_code == 200
    assert respuesta.json()["pedido_id"] == pedido
    malo = await cliente.post(
        f"/v1/operacion/casos/{caso}/pedido", headers=STAFF, json={"pedido_id": "no-es-uuid"}
    )
    assert malo.status_code == 422


async def test_bandeja_filtra_por_titular(cliente):
    mio = await _abrir(cliente, asunto="Del titular")
    r = await cliente.get(f"/v1/operacion/casos?usuario_id={USUARIO}", headers=STAFF)
    assert r.status_code == 200
    assert mio in [c["caso_id"] for c in r.json()["casos"]]
    r = await cliente.get(f"/v1/operacion/casos?usuario_id={uuid.uuid4()}", headers=STAFF)
    assert r.json()["casos"] == []
    assert (await cliente.get("/v1/operacion/casos?usuario_id=no-es-uuid", headers=STAFF)).status_code == 422
    assert (await cliente.get(f"/v1/operacion/casos?usuario_id={USUARIO}")).status_code == 401


CASO = Base.metadata.tables["caso"]
OP = STAFF
ADM = bearer(TOKEN_ADMIN)
TEXTO_SECRETO = "nota-solo-para-el-equipo-xyz"


async def _abrir_como_acudiente(cliente, **kw) -> str:
    cuerpo = {
        "categoria": "reclamo",
        "asunto": "Llego incompleto",
        "descripcion": "Faltan dos cuadernos.",
        **kw,
    }
    r = await cliente.post("/v1/operacion/mis-casos", json=cuerpo, headers=bearer(TOKEN_ACUDIENTE))
    assert r.status_code == 201, r.text
    return r.json()["caso_id"]


async def _post(cliente, caso, accion, cuerpo, headers=STAFF):
    return await cliente.post(f"/v1/operacion/casos/{caso}/{accion}", json=cuerpo, headers=headers)


async def _poner(caso, **valores):
    async with app.state.motor.sesion() as db:
        await (await db.connection()).execute(
            update(CASO).where(CASO.c.id == uuid.UUID(caso)).values(**valores)
        )


def test_reglas_de_prioridad_asignacion_y_nota():
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


@pytest.mark.parametrize(
    ("accion", "cuerpo"),
    [("asignar", {"asignar": "yo"}), ("prioridad", {"prioridad": "alta"}), ("nota", {"texto": "ok"})],
    ids=["asignar", "prioridad", "nota"],
)
@pytest.mark.parametrize(
    ("headers", "esperado"), [({}, 401), (bearer(TOKEN_ACUDIENTE), 403)], ids=["sin_sesion", "acudiente"]
)
async def test_la_gestion_rechaza_a_quien_no_es_staff_y_no_escribe(
    cliente, accion, cuerpo, headers, esperado
):
    caso = await _abrir_como_acudiente(cliente)
    assert (await _post(cliente, caso, accion, cuerpo, headers=headers)).status_code == esperado
    assert await _filas(AUDITORIA) == []


async def test_asignar_yo_y_soltar(cliente):
    caso = await _abrir_como_acudiente(cliente)
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


async def test_relevo_a_otro_staff_y_soltar_ajeno(cliente):
    caso = await _abrir_como_acudiente(cliente)
    await _post(cliente, caso, "asignar", {"asignar": "yo"}, headers=ADM)
    r = await _post(cliente, caso, "asignar", {"asignar": "yo"})
    assert r.json()["asignado_a"] == OPERADOR
    await _post(cliente, caso, "asignar", {"asignar": "yo"}, headers=ADM)
    denegado = await _post(cliente, caso, "asignar", {"asignar": "nadie"})
    assert denegado.status_code == 403
    assert (await _post(cliente, caso, "asignar", {"asignar": "nadie"}, headers=ADM)).json()[
        "asignado_a"
    ] is None


async def test_asignar_a_otro_es_422_y_a_un_caso_inexistente_404(cliente):
    caso = await _abrir_como_acudiente(cliente)
    assert (await _post(cliente, caso, "asignar", {"asignar": "otro"})).status_code == 422
    assert (await _post(cliente, str(uuid.uuid4()), "asignar", {"asignar": "yo"})).status_code == 404


async def test_prioridad_reordena_la_bandeja(cliente):
    a = await _abrir_como_acudiente(cliente, asunto="primero")
    b = await _abrir_como_acudiente(cliente, asunto="segundo")
    await _poner(a, prioridad="media")
    await _poner(b, prioridad="media")
    r = await _post(cliente, b, "prioridad", {"prioridad": "urgente"})
    assert r.status_code == 200
    assert r.json()["prioridad"] == "urgente"
    ev = [e for e in r.json()["eventos"] if e["tipo"] == "prioridad"][0]
    assert ev["datos"] == {"desde": "media", "hacia": "urgente"}
    bandeja = (await cliente.get("/v1/operacion/casos", headers=OP)).json()
    assert bandeja["casos"][0]["caso_id"] == b


async def test_prioridad_invalida_o_de_un_caso_cerrado_es_422(cliente):
    caso = await _abrir_como_acudiente(cliente)
    r = await _post(cliente, caso, "prioridad", {"prioridad": "critica"})
    assert r.status_code == 422
    await _poner(caso, estado="cerrado")
    r = await _post(cliente, caso, "prioridad", {"prioridad": "alta"})
    assert r.status_code == 422
    assert r.json()["error"] == "caso_cerrado"


async def test_nota_interna_es_de_staff_y_no_llega_al_acudiente(cliente):
    caso = await _abrir_como_acudiente(cliente)
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


@pytest.mark.parametrize("texto", ["   ", "x" * 2001], ids=["vacia", "larga"])
async def test_nota_vacia_o_larga_es_422(cliente, texto):
    caso = await _abrir_como_acudiente(cliente)
    assert (await _post(cliente, caso, "nota", {"texto": texto})).status_code == 422


async def test_resumen_cuenta_sin_asignar_y_vencidos(cliente):
    ayer = datetime.now(UTC) - timedelta(days=1)
    vencido_sin_dueno = await _abrir_como_acudiente(cliente, asunto="a")
    vencido_asignado = await _abrir_como_acudiente(cliente, asunto="b")
    resuelto_vencido = await _abrir_como_acudiente(cliente, asunto="c")
    await _abrir_como_acudiente(cliente, asunto="d")
    await _poner(vencido_sin_dueno, vence_en=ayer)
    await _poner(vencido_asignado, vence_en=ayer)
    await _poner(resuelto_vencido, vence_en=ayer, estado="resuelto", resuelto_en=datetime.now(UTC))
    await _post(cliente, vencido_asignado, "asignar", {"asignar": "yo"})
    resumen = (await cliente.get("/v1/operacion/casos", headers=OP)).json()["resumen"]
    assert resumen["sin_asignar"] == 2
    assert resumen["vencidos"] == 2
