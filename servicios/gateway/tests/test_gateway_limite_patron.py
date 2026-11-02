"""Fase 6 de QA, NFR-SEG-03: el limite de tasa de la puerta como patron (ADR 0047).

`test_limite.py` (del equipo) fija el limite pieza por pieza, casi siempre con topes de 1 a 3
puestos por entorno y en el nivel general; lo que ya prueba (el estricto por ruta, la cabecera
desde un cliente cualquiera, Redis caido o lento) no se repite. Aqui se mira como patron, con lo
que una familia o un atacante ven:

- **Los numeros por omision.** Sin tocar el entorno, la subida 31 del mismo token en 10 minutos
  recibe 429 y la 61 de la misma IP tambien, aunque cada una lleve otro token. El 429 llega antes
  que inteligencia: es el freno de LLM10 (consumo sin limite) delante del modelo.
- **Nada en claro en el nivel estricto.** Las cuatro claves de una subida llevan la huella del
  token y la de la IP, y el log del 429 nombra el nivel y la ruta, no la huella.
- **Lo que el ADR deja abierto (PEN-96).** Se caracteriza como «limitacion conocida (ADR 0047,
  PEN-96)», no como hallazgo: si el producto se porta distinto de lo que dice el ADR, la prueba
  falla y eso si seria un hallazgo.
  - La ventana fija deja pasar hasta el doble del tope en el cambio de ventana.
  - Sin Redis, cada puerta cuenta por su lado: dos puertas dejan pasar el doble.
  - Cuando empieza un episodio de degradacion, el contador en memoria arranca de cero.
  - Desde un proxy de confianza (la web, en 127.0.0.1), cada `X-Forwarded-For` inventada tiene su
    cupo; el del token sigue valiendo, y un proxy que agrega la IP real a la derecha la corrige.

Nada sale del proceso: los servicios de atras son un cliente falso que cuenta lo que le llega, el
Redis es el doble en memoria y las IP son de 198.18.0.0/15 (RFC 2544) o de documentacion.
"""

from __future__ import annotations

import hashlib
import logging

import httpx
import pytest
from tukit_comun.cache import ClienteRedis, usar_cliente
from tukit_comun.pruebas_redis import RedisEnMemoria, cliente_en_memoria
from tukit_gateway.api import app
from tukit_gateway.limite import _VARIABLES

pytestmark = pytest.mark.nfr("NFR-SEG-03")

LIMITACION = "limitacion conocida (ADR 0047, PEN-96)"


@pytest.fixture(autouse=True)
def _limites_por_omision(monkeypatch: pytest.MonkeyPatch) -> None:
    # Los numeros por omision son los del codigo: un tope exportado en la terminal no los cambia.
    for variable in (*_VARIABLES, "TUKIT_PROXIES_CONFIANZA"):
        monkeypatch.delenv(variable, raising=False)


class Atras:
    """Los servicios de atras: responden 200 a todo y cuentan lo que les llega."""

    def __init__(self) -> None:
        self.peticiones: list[tuple[str, str]] = []
        atras = self

        class Cliente:
            async def aclose(self) -> None:
                return None

            async def request(self, metodo, url, **_kwargs) -> httpx.Response:
                atras.peticiones.append((metodo, url))
                return httpx.Response(200, json={"ok": True})

        self.cliente = Cliente()


class Reloj:
    def __init__(self) -> None:
        self.ahora = 1000.0

    def __call__(self) -> float:
        return self.ahora


@pytest.fixture()
def atras() -> Atras:
    # Se cambia el cliente compartido de la puerta; la limpieza del conftest lo retira al final.
    falso = Atras()
    app.state.cliente = falso.cliente
    return falso


@pytest.fixture()
def redis() -> RedisEnMemoria:
    motor = RedisEnMemoria()
    usar_cliente(cliente_en_memoria(motor))
    return motor


def _http(cliente: tuple[str, int] = ("127.0.0.1", 50_000)) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app, client=cliente), base_url="http://prueba")


def _bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _subida(token: str, ip: str = "198.18.0.10") -> dict:
    """Lo que manda la web al subir una lista: el token de la familia, su IP y un PDF ficticio."""
    return {
        "headers": {**_bearer(token), "X-Forwarded-For": ip},
        "files": {"archivo": ("lista.pdf", b"%PDF-1.4 lista ficticia de QA\n", "application/pdf")},
    }


async def _estados(http: httpx.AsyncClient, veces: int, metodo: str, ruta: str, **kwargs) -> list[int]:
    return [(await http.request(metodo, ruta, **kwargs)).status_code for _ in range(veces)]


# --- Los numeros por omision: el freno delante del modelo (LLM10) -----------------


class TestElFrenoDeLasSubidas:
    async def test_la_subida_31_del_mismo_token_recibe_429_y_no_llega_a_inteligencia(
        self, atras, redis, record_property
    ):
        async with _http() as http:
            estados = await _estados(http, 31, "POST", "/v1/listas/subir", **_subida("tok-familia-qa"))
            ultima = await http.post("/v1/listas/subir", **_subida("tok-familia-qa"))

        subidas = [p for p in atras.peticiones if p[1].endswith("/v1/listas/subir")]
        record_property("subidas_aceptadas", estados.count(200))
        record_property("subidas_que_llegaron_atras", len(subidas))
        assert estados == [200] * 30 + [429]
        assert len(subidas) == 30
        assert ultima.status_code == 429
        # La ventana estricta es de 600 s; el redondeo hacia arriba puede dar 601.
        assert 540 < int(ultima.headers["Retry-After"]) <= 601
        assert ultima.json()["error"] == "demasiadas_peticiones"

    async def test_la_subida_61_de_la_misma_ip_recibe_429_aunque_cada_una_lleve_otro_token(
        self, atras, redis, record_property
    ):
        async with _http() as http:
            estados = [
                (await http.post("/v1/listas/subir", **_subida(f"tok-{i // 20}"))).status_code
                for i in range(60)
            ]
            otra_familia = await http.post("/v1/listas/subir", **_subida("tok-nueva"))

        record_property("subidas_aceptadas", estados.count(200))
        assert estados == [200] * 60
        assert otra_familia.status_code == 429
        assert len(atras.peticiones) == 60


# --- Nada en claro en el nivel estricto ------------------------------------------


async def test_las_claves_de_una_subida_llevan_solo_huellas_y_el_log_no_las_dice(atras, redis, caplog):
    token, ip = "tok-secreto-de-la-familia-qa", "198.18.7.21"
    with caplog.at_level(logging.DEBUG):
        async with _http() as http:
            await _estados(http, 31, "POST", "/v1/listas/subir", **_subida(token, ip))

    huellas = {hashlib.sha256(token.encode()).hexdigest(), hashlib.sha256(ip.encode()).hexdigest()}
    claves = redis.claves()
    assert sorted(c.split(":")[2:5] for c in claves) == sorted(
        [
            ["estricto", "listas-subir", "ip"],
            ["estricto", "listas-subir", "token"],
            ["general", "v1", "ip"],
            ["general", "v1", "token"],
        ]
    )
    assert {c.rsplit(":", 1)[1] for c in claves} == huellas
    assert not any(token in c or ip in c for c in claves)
    assert "429 por estricto:listas-subir:token" in caplog.text
    for dato in (token, ip, *huellas):
        assert dato not in caplog.text


# --- Lo que el ADR deja abierto (PEN-96) ------------------------------------------


@pytest.mark.parametrize("con_redis", [True, False], ids=["redis", "memoria"])
async def test_la_ventana_fija_deja_pasar_casi_el_doble_en_el_cambio_de_ventana(
    atras, monkeypatch, con_redis, record_property
):
    reloj = Reloj()
    motor = RedisEnMemoria(reloj=reloj) if con_redis else None
    usar_cliente(ClienteRedis(motor, espera=0.05, reloj=reloj))
    monkeypatch.setenv("TUKIT_LIMITE_GENERAL_IP", "3")
    async with _http() as http:
        # La primera abre la ventana (60 s); las demas llegan justo antes de que cierre y justo despues.
        primera = await _estados(http, 1, "GET", "/v1/colegios")
        reloj.ahora = 1059.9
        antes = await _estados(http, 3, "GET", "/v1/colegios")
        reloj.ahora = 1060.1
        despues = await _estados(http, 3, "GET", "/v1/colegios")

    record_property("caracterizacion", LIMITACION)
    record_property("pasaron_en_0_2_s", antes.count(200) + despues.count(200))
    assert primera == [200]
    assert antes == [200, 200, 429]
    assert despues == [200, 200, 200]
    # Tope 3 por minuto: 5 pasan en 0,2 s y 6 en 60,1 s.
    assert antes.count(200) + despues.count(200) == 2 * 3 - 1


async def test_sin_redis_dos_puertas_dejan_pasar_el_doble(atras, monkeypatch, record_property):
    monkeypatch.setenv("TUKIT_LIMITE_GENERAL_IP", "4")
    una, otra = ClienteRedis(None), ClienteRedis(None)
    estados: list[int] = []
    async with _http() as http:
        for i in range(10):
            usar_cliente(una if i % 2 == 0 else otra)
            estados.append((await http.get("/v1/colegios")).status_code)

    record_property("caracterizacion", LIMITACION)
    record_property("pasaron_con_tope_4", estados.count(200))
    # Cada puerta vio cinco: las cuatro primeras de cada una pasan.
    assert estados == [200] * 8 + [429, 429]


async def test_al_empezar_un_episodio_el_contador_en_memoria_arranca_de_cero(
    atras, redis, monkeypatch, record_property
):
    monkeypatch.setenv("TUKIT_LIMITE_GENERAL_IP", "3")
    async with _http() as http:
        con_redis = await _estados(http, 4, "GET", "/v1/colegios")
        redis.caido = True
        en_el_episodio = await _estados(http, 4, "GET", "/v1/colegios")

    record_property("caracterizacion", LIMITACION)
    assert con_redis == [200, 200, 200, 429]
    assert en_el_episodio == [200, 200, 200, 429]


class TestLaIpDesdeUnProxyDeConfianza:
    async def test_cada_x_forwarded_for_inventada_tiene_su_cupo(
        self, atras, redis, monkeypatch, record_property
    ):
        monkeypatch.setenv("TUKIT_LIMITE_GENERAL_IP", "2")
        async with _http(("127.0.0.1", 50_000)) as http:
            estados = [
                (await http.get("/v1/colegios", headers={"X-Forwarded-For": f"198.18.1.{i}"})).status_code
                for i in range(10)
            ]

        record_property("caracterizacion", LIMITACION)
        assert estados == [200] * 10

    async def test_el_cupo_del_token_sigue_valiendo_aunque_la_ip_cambie(self, atras, redis, monkeypatch):
        monkeypatch.setenv("TUKIT_LIMITE_GENERAL_TOKEN", "2")
        async with _http(("127.0.0.1", 50_000)) as http:
            estados = [
                (
                    await http.get(
                        "/v1/cuenta", headers={**_bearer("tok-familia"), "X-Forwarded-For": f"198.18.2.{i}"}
                    )
                ).status_code
                for i in range(3)
            ]

        assert estados == [200, 200, 429]

    async def test_un_proxy_que_agrega_la_ip_real_a_la_derecha_la_corrige(self, atras, redis, monkeypatch):
        monkeypatch.setenv("TUKIT_LIMITE_GENERAL_IP", "2")
        async with _http(("127.0.0.1", 50_000)) as http:
            estados = [
                (
                    await http.get("/v1/colegios", headers={"X-Forwarded-For": f"198.18.3.{i}, 203.0.113.5"})
                ).status_code
                for i in range(3)
            ]

        assert estados == [200, 200, 429]
