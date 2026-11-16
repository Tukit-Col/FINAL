"""El panel de correos enviados: solo staff, sin contacto, con filtros y resumen.

Contra la app real con SQLite en memoria, como `test_admin_tickets`."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta

import httpx
import pytest_asyncio
from conftest import TOKEN_ACUDIENTE, TOKEN_OPERADOR, IdentidadFalsa, bearer
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from tukit_comun.bd import MotorServicio
from tukit_operacion.api import app
from tukit_operacion.modelos import Base
from tukit_operacion.repositorios import RepoNotificaciones

STAFF = bearer(TOKEN_OPERADOR)
USUARIO = str(uuid.uuid4())
AHORA = datetime(2026, 11, 16, 15, 0, tzinfo=UTC)


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


async def _aviso(plantilla: str, *, exito: bool = True, omitida: bool = False, minutos: int = 0, **datos) -> None:
    async with app.state.motor.sesion() as db:
        await RepoNotificaciones(await db.connection()).registrar(
            usuario_id=USUARIO,
            canal="correo",
            plantilla=plantilla,
            datos=datos,
            exito=exito,
            ahora=AHORA + timedelta(minutes=minutos),
            asunto=f"Asunto de {plantilla}",
            detalle="destino_no_enviable" if omitida else ("smtp" if exito else "smtp_error: OSError"),
            destino_dominio="tukit.co" if omitida else "gmail.com",
            omitida=omitida,
        )


async def test_solo_staff_ve_los_correos(cliente):
    assert (await cliente.get("/v1/operacion/correos")).status_code == 401
    assert (await cliente.get("/v1/operacion/correos", headers=bearer(TOKEN_ACUDIENTE))).status_code == 403
    assert (await cliente.get("/v1/operacion/correos", headers=STAFF)).status_code == 200


async def test_lista_lo_mas_reciente_primero_con_resumen_y_sin_direccion(cliente):
    await _aviso("pedido_pagado", pedido="AB12CD34", minutos=0)
    await _aviso("pedido_despachado", exito=False, pedido="AB12CD34", minutos=5)
    await _aviso("kits_publicados", omitida=True, exito=False, minutos=9)

    cuerpo = (await cliente.get("/v1/operacion/correos", headers=STAFF)).json()

    assert [c["plantilla"] for c in cuerpo["correos"]] == ["kits_publicados", "pedido_despachado", "pedido_pagado"]
    assert cuerpo["resumen"] == {"enviada": 1, "fallida": 1, "omitida": 1}
    omitido = cuerpo["correos"][0]
    assert (omitido["estado"], omitido["detalle"], omitido["destino_dominio"]) == (
        "omitida",
        "destino_no_enviable",
        "tukit.co",
    )
    assert not any("@" in str(valor) for correo in cuerpo["correos"] for valor in correo.values())


async def test_filtra_por_estado_plantilla_pedido_y_caso(cliente):
    await _aviso("pedido_pagado", pedido="AB12CD34", minutos=0)
    await _aviso("pedido_despachado", exito=False, pedido="ZZ99ZZ99", minutos=1)
    await _aviso("caso_respuesta", caso="CA5E0001", minutos=2)

    async def plantillas(**filtros) -> list[str]:
        r = await cliente.get("/v1/operacion/correos", params=filtros, headers=STAFF)
        return [c["plantilla"] for c in r.json()["correos"]]

    assert await plantillas(estado="fallida") == ["pedido_despachado"]
    assert await plantillas(plantilla="caso_respuesta") == ["caso_respuesta"]
    assert await plantillas(pedido="ab12cd34") == ["pedido_pagado"]
    assert await plantillas(caso="CA5E0001") == ["caso_respuesta"]
    assert await plantillas(limite=2) == ["caso_respuesta", "pedido_despachado"]
