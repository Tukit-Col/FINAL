"""El vector guardado con la app de catalogo y un Redis de verdad (ADR 0047).

Es la prueba de punta a punta de la cache de vectores: la API que arranca
`make arriba` no tiene embeder sin la clave de Gemini, asi que se corre la app
aqui, en el proceso de la prueba, con el embeder falso y contra el Redis de
`TUKIT_PRUEBAS_REDIS_URL`. La segunda lista solo le pide al proveedor el renglon
nuevo, y lo que queda en Redis son los vectores, con su vencimiento, y nada mas.
"""

from __future__ import annotations

from collections.abc import Sequence

import httpx
import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool
from tukit_catalogo import cache_vectores, consulta
from tukit_catalogo.api import app
from tukit_catalogo.embeddings import DIMENSION_EMBEDDING, MODELO_FALSO, embeder_falso
from tukit_catalogo.modelos import Base
from tukit_comun.bd import MotorServicio
from tukit_comun.cache import usar_cliente
from tukit_comun.pruebas_redis import clientes_de_prueba, lo_guardado

pytestmark = pytest.mark.redis

RENGLONES = ["2 cuadernos cuadriculados", "1 caja de colores", "pegante en barra"]


async def test_la_segunda_lista_solo_calcula_el_renglon_nuevo_contra_redis(monkeypatch):
    lotes: list[list[str]] = []

    def proveedor(textos: Sequence[str]) -> list[list[float]]:
        lotes.append(list(textos))
        return embeder_falso(textos)

    proveedor.modelo = MODELO_FALSO  # type: ignore[attr-defined]
    monkeypatch.setattr(consulta, "_embeder_por_entorno", lambda: proveedor)
    engine = create_async_engine(
        "sqlite+aiosqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False}
    )
    async with engine.begin() as conexion:
        await conexion.run_sync(Base.metadata.create_all)
    app.state.motor = MotorServicio(
        servicio="prueba", engine=engine, _fabrica=async_sessionmaker(engine, expire_on_commit=False)
    )

    try:
        async with clientes_de_prueba() as (cliente,):
            usar_cliente(cliente)
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app), base_url="http://prueba"
            ) as http:
                primera = await http.post("/v1/catalogo/emparejar", json={"renglones": RENGLONES[:2]})
                segunda = await http.post("/v1/catalogo/emparejar", json={"renglones": RENGLONES})

            assert primera.status_code == segunda.status_code == 200
            assert lotes == [RENGLONES[:2], RENGLONES[2:]]
            assert not cliente.degradado
            guardado = await lo_guardado(cliente.prefijo)
    finally:
        await engine.dispose()

    esperados = {
        cliente.prefijo + cache_vectores.clave(MODELO_FALSO, texto): vector
        for texto, vector in zip(RENGLONES, embeder_falso(RENGLONES), strict=True)
    }
    assert {c: cache_vectores.de_bytes(g.valor) for c, g in guardado.items()} == esperados
    assert all(len(g.valor) == 8 * DIMENSION_EMBEDDING for g in guardado.values())
    assert all((24 * 3600 - 60) * 1000 < g.vence_en_ms <= 24 * 3600 * 1000 for g in guardado.values())
    assert not any(b"cuaderno" in g.valor or "cuaderno" in c for c, g in guardado.items())
