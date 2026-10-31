"""El vector de cada renglon se guarda y se reaprovecha (ADR 0047).

Se fija que un lote con renglones guardados y sin guardar le pide al proveedor
solo los que faltan, en orden, y devuelve el resultado en el orden original;
que un fallo del proveedor no guarda nada y baja la tanda entera a lexico; que
con Redis caido se calcula como hoy; la duracion de la clave; y que un embeder
sin modelo declarado no se cachea.
"""

from __future__ import annotations

from collections.abc import Sequence

import httpx
import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool
from tukit_catalogo import cache_vectores, consulta
from tukit_catalogo.api import app
from tukit_catalogo.consulta import calcular_vectores
from tukit_catalogo.embeddings import (
    DIMENSION_EMBEDDING,
    MODELO_FALSO,
    MODELO_GEMINI,
    embeder_falso,
    embeder_gemini,
    modelo_de,
)
from tukit_catalogo.modelos import Base
from tukit_comun.bd import MotorServicio
from tukit_comun.cache import usar_cliente
from tukit_comun.pruebas_redis import RedisEnMemoria, cliente_en_memoria


class Proveedor:
    """Un embeder con modelo declarado que anota cada lote que recibe."""

    modelo = MODELO_FALSO

    def __init__(self, *, falla: bool = False) -> None:
        self.lotes: list[list[str]] = []
        self.falla = falla

    def __call__(self, textos: Sequence[str]) -> list[list[float]]:
        self.lotes.append(list(textos))
        if self.falla:
            raise RuntimeError("el proveedor no responde")
        return embeder_falso(textos)


@pytest.fixture()
def redis() -> RedisEnMemoria:
    motor = RedisEnMemoria()
    usar_cliente(cliente_en_memoria(motor))
    return motor


async def _guardar(redis: RedisEnMemoria, *textos: str) -> None:
    await redis.guardar_varias(
        {
            "tukit:" + cache_vectores.clave(MODELO_FALSO, texto): cache_vectores.a_bytes(vector)
            for texto, vector in zip(textos, embeder_falso(textos), strict=True)
        },
        60,
    )


RENGLONES = ["2 cuadernos cuadriculados", "1 caja de colores", "pegante en barra", "block iris"]


async def test_un_lote_mixto_pide_solo_los_que_faltan_en_orden(redis):
    await _guardar(redis, RENGLONES[1], RENGLONES[3])
    proveedor = Proveedor()

    vectores = await calcular_vectores(RENGLONES, proveedor)

    assert proveedor.lotes == [[RENGLONES[0], RENGLONES[2]]]
    assert vectores == embeder_falso(RENGLONES)
    assert len(redis.operaciones("leer")) == 1


async def test_lo_que_falto_queda_guardado_para_el_siguiente_lote(redis):
    await calcular_vectores(RENGLONES[:2], Proveedor())
    proveedor = Proveedor()

    vectores = await calcular_vectores(RENGLONES, proveedor)

    assert proveedor.lotes == [RENGLONES[2:]]
    assert vectores == embeder_falso(RENGLONES)


async def test_con_todo_guardado_no_se_llama_al_proveedor(redis):
    await _guardar(redis, *RENGLONES)
    proveedor = Proveedor()

    assert await calcular_vectores(RENGLONES, proveedor) == embeder_falso(RENGLONES)
    assert proveedor.lotes == []


async def test_el_vector_guardado_es_identico_al_calculado(redis):
    (calculado,) = await calcular_vectores(["regla de 30 cm"], Proveedor())
    (guardado,) = await calcular_vectores(["regla de 30 cm"], Proveedor())

    assert guardado == calculado
    assert all(type(x) is float for x in guardado)


async def test_un_fallo_del_proveedor_no_guarda_nada(redis):
    vectores = await calcular_vectores(RENGLONES, Proveedor(falla=True))

    assert vectores == [None] * len(RENGLONES)
    assert redis.operaciones("guardar") == []


async def test_un_fallo_del_proveedor_baja_la_tanda_entera_aunque_haya_guardados(redis):
    await _guardar(redis, RENGLONES[0])

    vectores = await calcular_vectores(RENGLONES, Proveedor(falla=True))

    assert vectores == [None] * len(RENGLONES)


async def test_con_redis_caido_calcula_como_hoy(redis):
    await _guardar(redis, RENGLONES[0])
    redis.caido = True
    proveedor = Proveedor()

    vectores = await calcular_vectores(RENGLONES, proveedor)

    assert proveedor.lotes == [RENGLONES]
    assert vectores == embeder_falso(RENGLONES)


async def test_con_redis_lento_calcula_como_hoy(redis):
    redis.demora = 1.0
    proveedor = Proveedor()

    assert await calcular_vectores(RENGLONES, proveedor) == embeder_falso(RENGLONES)
    assert proveedor.lotes == [RENGLONES]


async def test_sin_redis_el_proveedor_recibe_el_lote_entero_cada_vez():
    proveedor = Proveedor()

    await calcular_vectores(RENGLONES, proveedor)
    await calcular_vectores(RENGLONES, proveedor)

    assert proveedor.lotes == [RENGLONES, RENGLONES]


async def test_la_clave_dura_un_dia_y_se_configura(redis, monkeypatch):
    await calcular_vectores(["a"], Proveedor())
    monkeypatch.setenv("TUKIT_CACHE_VECTORES_SEGUNDOS", "600")
    await calcular_vectores(["b"], Proveedor())

    assert redis.vence_en("tukit:" + cache_vectores.clave(MODELO_FALSO, "a")) == pytest.approx(86_400, abs=5)
    assert redis.vence_en("tukit:" + cache_vectores.clave(MODELO_FALSO, "b")) == pytest.approx(600, abs=5)


async def test_con_duracion_cero_no_hay_cache(redis, monkeypatch):
    monkeypatch.setenv("TUKIT_CACHE_VECTORES_SEGUNDOS", "0")
    proveedor = Proveedor()

    await calcular_vectores(RENGLONES, proveedor)
    await calcular_vectores(RENGLONES, proveedor)

    assert proveedor.lotes == [RENGLONES, RENGLONES]
    assert redis.llamadas == []


async def test_un_embeder_sin_modelo_no_se_cachea(redis):
    lotes: list[list[str]] = []

    def suelto(textos: Sequence[str]) -> list[list[float]]:
        lotes.append(list(textos))
        return embeder_falso(textos)

    await calcular_vectores(RENGLONES, suelto)
    await calcular_vectores(RENGLONES, suelto)

    assert lotes == [RENGLONES, RENGLONES]
    assert redis.llamadas == []


async def test_un_vector_de_otra_dimension_no_se_guarda(redis):
    class Corto(Proveedor):
        def __call__(self, textos: Sequence[str]) -> list[list[float]]:
            return [[1.0, 0.0, 0.0] for _ in textos]

    assert await calcular_vectores(["a"], Corto()) == [[1.0, 0.0, 0.0]]
    assert redis.claves() == []


async def test_un_valor_de_otro_largo_cuenta_como_no_guardado(redis):
    await redis.guardar_varias({"tukit:" + cache_vectores.clave(MODELO_FALSO, "a"): b"\x00" * 16}, 60)
    proveedor = Proveedor()

    assert await calcular_vectores(["a"], proveedor) == embeder_falso(["a"])
    assert proveedor.lotes == [["a"]]


async def test_la_clave_lleva_el_modelo_la_dimension_y_la_huella_del_texto(redis):
    await calcular_vectores(["2 cuadernos cuadriculados"], Proveedor())

    (llave,) = redis.claves()
    prefijo, uso, modelo, dimension, huella = llave.split(":")
    assert (prefijo, uso, modelo, dimension) == ("tukit", "vector", MODELO_FALSO, str(DIMENSION_EMBEDDING))
    assert len(huella) == 64
    assert "cuaderno" not in llave


def test_el_modelo_de_gemini_es_el_efectivo(monkeypatch):
    monkeypatch.delenv("GEMINI_MODELO_EMBEDDING", raising=False)
    assert modelo_de(embeder_gemini) == MODELO_GEMINI
    monkeypatch.setenv("GEMINI_MODELO_EMBEDDING", "gemini-embedding-002")
    assert modelo_de(embeder_gemini) == "gemini-embedding-002"
    assert modelo_de(embeder_falso) == MODELO_FALSO
    assert modelo_de(lambda textos: []) is None


def test_otro_modelo_es_otra_clave():
    assert cache_vectores.clave("gemini-embedding-001", "a") != cache_vectores.clave(
        "gemini-embedding-002", "a"
    )


# --- Por la ruta -----------------------------------------------------------


@pytest.fixture()
async def http(monkeypatch):
    engine = create_async_engine(
        "sqlite+aiosqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False}
    )
    async with engine.begin() as conexion:
        await conexion.run_sync(Base.metadata.create_all)
    app.state.motor = MotorServicio(
        servicio="prueba", engine=engine, _fabrica=async_sessionmaker(engine, expire_on_commit=False)
    )
    proveedor = Proveedor()
    monkeypatch.setattr(consulta, "_embeder_por_entorno", lambda: proveedor)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://prueba") as cliente:
        yield cliente, proveedor
    await engine.dispose()


async def test_dos_familias_con_la_misma_lista_calculan_cada_renglon_una_vez(http, redis):
    cliente, proveedor = http

    primera = await cliente.post("/v1/catalogo/emparejar", json={"renglones": RENGLONES[:3]})
    segunda = await cliente.post("/v1/catalogo/emparejar", json={"renglones": RENGLONES})

    assert primera.status_code == segunda.status_code == 200
    assert proveedor.lotes == [RENGLONES[:3], RENGLONES[3:]]
    assert segunda.json()["total"] == len(RENGLONES)


async def test_por_la_ruta_con_redis_caido_responde_igual(http, redis):
    cliente, proveedor = http
    sin_cache = (await cliente.post("/v1/catalogo/emparejar", json={"renglones": RENGLONES})).json()
    redis.caido = True

    con_redis_caido = (await cliente.post("/v1/catalogo/emparejar", json={"renglones": RENGLONES})).json()

    assert con_redis_caido == sin_cache
    assert proveedor.lotes == [RENGLONES, RENGLONES]
