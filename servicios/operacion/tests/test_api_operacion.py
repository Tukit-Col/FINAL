"""La superficie HTTP de Operacion, contra el contrato.

Se prueba con `ASGITransport` y no levantando uvicorn: la app se llama en el
mismo proceso. El motor y el cliente de Identidad se inyectan a mano en
`app.state` porque el arranque normal abriria conexiones reales, y una suite
que las necesita se termina saltando.

Lo que se comprueba es lo que el contrato promete: el 422 para una categoria
que un acudiente no puede abrir, el `vence_en` calculado del SLA, que la
bandeja devuelva `resumen`+`casos`, y —lo que la deuda del manifiesto exige—
que el contacto NO quede guardado en ningun lado del caso.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import httpx
import pytest_asyncio
from conftest import TOKEN_OPERADOR, IdentidadFalsa, bearer
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from tukit_comun.bd import MotorServicio
from tukit_operacion.api import app
from tukit_operacion.modelos import Base


@pytest_asyncio.fixture
async def cliente() -> AsyncIterator[httpx.AsyncClient]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conexion:
        await conexion.run_sync(Base.metadata.create_all)
    fabrica = async_sessionmaker(engine, expire_on_commit=False)
    app.state.motor = MotorServicio(servicio="prueba", engine=engine, _fabrica=fabrica)
    app.state.identidad = IdentidadFalsa()
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://prueba") as http:
        yield http
    await engine.dispose()


STAFF = bearer(TOKEN_OPERADOR)


def _solicitud(**kw):
    cuerpo = {
        "categoria": "peticion",
        "asunto": "No me llego el correo del kit",
        "descripcion": "Hice el pedido ayer y no tengo confirmacion.",
        "contacto": {"correo": "papa@ejemplo.com", "celular": "3001234567"},
    }
    cuerpo.update(kw)
    return cuerpo


async def test_abrir_caso_devuelve_201_y_vence_en(cliente):
    respuesta = await cliente.post("/v1/operacion/casos", json=_solicitud())
    assert respuesta.status_code == 201
    cuerpo = respuesta.json()
    assert cuerpo["estado"] == "abierto"
    assert cuerpo["categoria"] == "peticion"
    # Una peticion tiene termino (Ley 1755): vence_en no es nulo.
    assert cuerpo["vence_en"] is not None
    assert cuerpo["caso_id"]


async def test_categoria_de_saga_se_rechaza_con_422(cliente):
    respuesta = await cliente.post("/v1/operacion/casos", json=_solicitud(categoria="mapeo_lista"))
    assert respuesta.status_code == 422
    assert respuesta.json()["error"] == "categoria_no_permitida"


async def test_categoria_inexistente_se_rechaza_con_422(cliente):
    respuesta = await cliente.post("/v1/operacion/casos", json=_solicitud(categoria="inventada"))
    assert respuesta.status_code == 422
    assert respuesta.json()["error"] == "categoria_invalida"


async def test_sugerencia_puede_no_vencer_nunca_pero_peticion_si(cliente):
    # Sugerencia tiene termino guia; una queja tambien. Lo que importa es que el
    # SLA se aplica por categoria y no es un valor unico.
    peticion = (await cliente.post("/v1/operacion/casos", json=_solicitud(categoria="peticion"))).json()
    pago = (await cliente.post("/v1/operacion/casos", json=_solicitud(categoria="pago"))).json()
    assert peticion["vence_en"] is not None
    assert pago["vence_en"] is not None
    # El de pago vence antes que el de peticion (24 h contra 15 dias).
    assert pago["vence_en"] < peticion["vence_en"]


async def test_bandeja_devuelve_resumen_y_casos(cliente):
    await cliente.post("/v1/operacion/casos", json=_solicitud(categoria="pago"))
    respuesta = await cliente.get("/v1/operacion/casos", headers=STAFF)
    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert set(cuerpo) == {"resumen", "casos"}
    assert set(cuerpo["resumen"]) == {"abiertos", "urgentes", "vencen_hoy", "resueltos_semana"}
    assert cuerpo["resumen"]["abiertos"] == 1
    # Un caso de pago nace urgente.
    assert cuerpo["resumen"]["urgentes"] == 1


async def test_contacto_no_queda_guardado_en_el_caso(cliente):
    correo = "secreto@ejemplo.com"
    celular = "3009998877"
    creado = (
        await cliente.post(
            "/v1/operacion/casos",
            json=_solicitud(contacto={"correo": correo, "celular": celular}),
        )
    ).json()
    # El caso se pudo abrir y quedo con el usuario_id resuelto por el doble.
    detalle = (await cliente.get(f"/v1/operacion/casos/{creado['caso_id']}", headers=STAFF)).json()
    assert detalle["caso_id"] == creado["caso_id"]
    texto = str(detalle)
    assert correo not in texto
    assert celular not in texto
    # Y el doble de Identidad SI recibio el contacto (se resolvio, no se guardo).
    assert app.state.identidad.llamadas == [(correo, celular)]


async def test_caso_inexistente_es_404(cliente):
    import uuid

    respuesta = await cliente.get(f"/v1/operacion/casos/{uuid.uuid4()}", headers=STAFF)
    assert respuesta.status_code == 404
    assert respuesta.json()["error"] == "caso_no_existe"
