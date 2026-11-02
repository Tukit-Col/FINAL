"""NFR-MAN-01: los bordes de la cache de vectores (ADR 0047) que `test_cache_vectores.py` no mira.

Con el doble `RedisEnMemoria` y un proveedor que anota sus lotes, como alla (N-141):

- el mismo renglon dos veces en un lote sale con el mismo vector y queda guardado para el
  siguiente. El ADR no promete quitar los repetidos: se anota cuantos textos van al proveedor;
- la clave es la huella del texto exacto que va al proveedor: una mayuscula o un espacio de mas
  son otra clave y otra llamada;
- un lote vacio no toca ni a Redis ni al proveedor;
- un proveedor que devuelve menos vectores de los pedidos es un fallo: no se guarda nada y la
  tanda baja a lexico, como dice el ADR de cualquier fallo del proveedor.

Y una con el `MotorRedis` de verdad contra un puerto que acepta y nunca contesta, como en
`libs/py/tukit_comun/tests/test_comun_cache_episodio.py`: la consulta no espera mas que la espera
de 250 ms y calcula como sin Redis.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import AsyncIterator, Sequence

import pytest
from tukit_catalogo import cache_vectores
from tukit_catalogo.consulta import calcular_vectores
from tukit_catalogo.embeddings import MODELO_FALSO, embeder_falso
from tukit_comun.cache import ESPERA_POR_OMISION_MS, PAUSA_TRAS_FALLO, ClienteRedis, MotorRedis, usar_cliente
from tukit_comun.pruebas_redis import RedisEnMemoria, cliente_en_memoria

pytestmark = pytest.mark.nfr("NFR-MAN-01")

ESPERA = ESPERA_POR_OMISION_MS / 1000


class Proveedor:
    """Un embeder con modelo declarado que anota cada lote; `corto` devuelve un vector de menos."""

    modelo = MODELO_FALSO

    def __init__(self, *, corto: bool = False) -> None:
        self.lotes: list[list[str]] = []
        self.corto = corto

    def __call__(self, textos: Sequence[str]) -> list[list[float]]:
        self.lotes.append(list(textos))
        vectores = embeder_falso(textos)
        return vectores[:-1] if self.corto else vectores


@pytest.fixture()
def redis() -> RedisEnMemoria:
    motor = RedisEnMemoria()
    usar_cliente(cliente_en_memoria(motor))
    return motor


@pytest.fixture()
async def redis_colgado() -> AsyncIterator[ClienteRedis]:
    """El cliente de verdad contra un puerto de 127.0.0.1 que acepta y nunca escribe."""
    pytest.importorskip("redis")
    soltar = asyncio.Event()

    async def atender(_lector: asyncio.StreamReader, escritor: asyncio.StreamWriter) -> None:
        await soltar.wait()
        escritor.close()

    servidor = await asyncio.start_server(atender, "127.0.0.1", 0)
    puerto = servidor.sockets[0].getsockname()[1]
    cliente = ClienteRedis(
        MotorRedis(f"redis://127.0.0.1:{puerto}/0", espera=ESPERA), espera=ESPERA, pausa=PAUSA_TRAS_FALLO
    )
    usar_cliente(cliente)
    yield cliente
    await cliente.cerrar()
    soltar.set()
    servidor.close()
    await servidor.wait_closed()


async def test_un_renglon_repetido_en_el_lote_sale_igual_y_queda_guardado(redis, record_property):
    proveedor = Proveedor()
    lote = ["block iris", "2 cuadernos cuadriculados", "block iris"]

    vectores = await calcular_vectores(lote, proveedor)
    otra_vez = await calcular_vectores(["block iris"], proveedor)

    record_property("textos_al_proveedor", sum(len(enviado) for enviado in proveedor.lotes))
    assert vectores == embeder_falso(lote)
    assert vectores[0] == vectores[2]
    assert otra_vez == embeder_falso(["block iris"])
    assert len(proveedor.lotes) == 1


async def test_la_clave_es_el_texto_exacto_sin_normalizar(redis):
    proveedor = Proveedor()
    variantes = ["Block Iris", "block iris ", "block  iris"]

    await calcular_vectores(["block iris"], proveedor)
    await calcular_vectores(variantes, proveedor)

    assert proveedor.lotes == [["block iris"], variantes]
    claves = {cache_vectores.clave(MODELO_FALSO, texto) for texto in ["block iris", *variantes]}
    assert len(claves) == 4
    assert all(redis.guardado("tukit:" + clave) is not None for clave in claves)


async def test_un_lote_vacio_no_toca_redis_ni_al_proveedor(redis):
    proveedor = Proveedor()

    assert await cache_vectores.vectores_guardados([], proveedor) == []
    assert await calcular_vectores([], proveedor) == []
    assert proveedor.lotes == []
    assert redis.llamadas == []


async def test_un_proveedor_que_devuelve_de_menos_baja_a_lexico_sin_guardar(redis):
    proveedor = Proveedor(corto=True)
    renglones = ["block iris", "pegante en barra", "1 caja de colores"]

    vectores = await calcular_vectores(renglones, proveedor)

    assert vectores == [None] * len(renglones)
    assert redis.operaciones("guardar") == []
    assert redis.claves() == []


async def test_con_redis_colgado_la_consulta_no_espera_mas_que_la_espera(redis_colgado, record_property):
    proveedor = Proveedor()
    renglones = ["block iris", "pegante en barra"]

    inicio = time.monotonic()
    vectores = await calcular_vectores(renglones, proveedor)
    segundos = time.monotonic() - inicio

    record_property("segundos_con_redis_colgado", round(segundos, 3))
    assert vectores == embeder_falso(renglones)
    assert proveedor.lotes == [renglones]
    assert redis_colgado.degradado
    # La lectura se rinde en la espera y el guardado ya cae en la pausa del episodio.
    assert segundos < 1.0
