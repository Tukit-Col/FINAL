"""Fase 5 de QA, ADV-19 en la puerta: el limite estricto como freno al consumo del asistente NL2C.

Cada peticion al asistente que llega a inteligencia cuesta una llamada a un modelo de pago
(OWASP LLM10). oe5 puso sus rutas en el nivel estricto (`limite.py`, «Cada llamada del asistente
cuesta una llamada a un modelo de pago»); `test_limite.py` y `test_gateway_limite_patron.py` no
las tocan. Aqui se mira con los topes por omision lo que dice el fixture
`ensayos/adversariales/fixtures/nl2c/ADV-19-*.json`:

- la peticion 31 del mismo token a `/v1/nl2c/interpretar` y la 61 de la misma IP reciben 429 y no
  llegan a inteligencia; sin token (el flujo de empezar no pide sesion) solo cuenta la IP;
- `/v1/nl2c/decision` comparte la cuenta de `nl2c` y `/v1/kits/{id}/asistente/proponer` tiene la
  suya (`nl2c-kit`);
- la barra final no abre otra cuenta y un GET no cuenta en el estricto.

Nada sale del proceso: inteligencia es el cliente falso de `test_gateway_limite_patron.py`, el
Redis es el doble en memoria y las IP son de 198.18.0.0/15 (RFC 2544).
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path

import pytest
from test_gateway_limite_patron import Atras, _bearer, _estados, _http
from tukit_comun.cache import usar_cliente
from tukit_comun.pruebas_redis import RedisEnMemoria, cliente_en_memoria
from tukit_gateway.api import app
from tukit_gateway.limite import _VARIABLES, ruta_estricta

pytestmark = pytest.mark.nfr("NFR-SEG-03")

RAIZ = Path(__file__).resolve().parents[3]
(FIXTURE,) = sorted((RAIZ / "ensayos" / "adversariales" / "fixtures" / "nl2c").glob("ADV-19-*.json"))
CASO = json.loads(FIXTURE.read_text(encoding="utf-8"))
INTENTOS = {intento["id"]: intento["condicion_exito"] for intento in CASO["intentos"]}

INTERPRETAR = "/v1/nl2c/interpretar"
DECISION = "/v1/nl2c/decision"
CLIENTE = ("198.18.0.40", 50_000)


@pytest.fixture(autouse=True)
def _caso(record_property, monkeypatch: pytest.MonkeyPatch) -> None:
    record_property("caso_adv", CASO["caso"])
    # Los topes por omision son los del codigo, como en `test_gateway_limite_patron.py`.
    for variable in (*_VARIABLES, "TUKIT_PROXIES_CONFIANZA"):
        monkeypatch.delenv(variable, raising=False)


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


def _proponer(trabajo_id: str | None = None) -> str:
    return f"/v1/kits/{trabajo_id or uuid.uuid4()}/asistente/proponer"


def _texto(token: str | None = "tok-familia-nl2c") -> dict:
    """Lo que manda la web al asistente: un texto corto del acudiente y, si hay sesion, su token."""
    return {"headers": _bearer(token) if token else {}, "json": {"texto": "Cambiame el cuaderno."}}


def _llegaron(atras, sufijo: str) -> int:
    return sum(1 for _metodo, url in atras.peticiones if url.rstrip("/").endswith(sufijo))


class TestADV19ElLimiteEstrictoDelAsistente:
    def test_el_fixture_es_el_del_caso(self):
        assert CASO["caso"] == "ADV-19" and CASO["owasp"] == ["LLM10"]
        assert CASO["ensayo_ids"] == ["NFR-SEG-03"]
        assert set(INTENTOS) == {
            "interpretar_31",
            "decision_comparte",
            "proponer_aparte",
            "ip_61",
            "interpretar_sin_token",
            "barra_final_y_get",
        }

    @pytest.mark.parametrize(
        ("metodo", "camino", "nombre"),
        [
            ("POST", INTERPRETAR, "nl2c"),
            ("POST", INTERPRETAR + "/", "nl2c"),
            ("POST", DECISION, "nl2c"),
            ("POST", "/v1/kits/7d0c2b8e-0000-4000-8000-000000000001/asistente/proponer", "nl2c-kit"),
            ("POST", "/v1/kits/7d0c2b8e-0000-4000-8000-000000000001/asistente/proponer/", "nl2c-kit"),
            ("GET", INTERPRETAR, None),
            ("GET", "/v1/kits/7d0c2b8e-0000-4000-8000-000000000001/asistente/proponer", None),
        ],
    )
    def test_las_rutas_del_asistente_son_estrictas_solo_en_post(self, metodo, camino, nombre):
        assert ruta_estricta(metodo, camino) == nombre

    async def test_la_31_del_mismo_token_a_interpretar_recibe_429_y_no_llega_a_inteligencia(
        self, atras, redis, record_property
    ):
        esperado = INTENTOS["interpretar_31"]
        async with _http(CLIENTE) as http:
            estados = await _estados(http, 31, "POST", INTERPRETAR, **_texto())
            ultima = await http.post(INTERPRETAR, **_texto())

        record_property("peticiones_que_llegaron_atras", _llegaron(atras, INTERPRETAR))
        assert estados == [200] * 30 + [429]
        assert _llegaron(atras, INTERPRETAR) == esperado["llegan_atras"]
        assert ultima.status_code == 429
        minimo, maximo = esperado["retry_after"]
        assert minimo <= int(ultima.headers["Retry-After"]) <= maximo
        assert ultima.json()["error"] == "demasiadas_peticiones"

    async def test_decision_comparte_la_cuenta_de_interpretar(self, atras, redis):
        esperado = INTENTOS["decision_comparte"]
        async with _http(CLIENTE) as http:
            mitad = await _estados(http, 15, "POST", INTERPRETAR, **_texto())
            otra_mitad = await _estados(http, 15, "POST", DECISION, **_texto())
            la_31 = await http.post(DECISION, **_texto())

        assert mitad + otra_mitad == [200] * 30
        assert la_31.status_code == 429
        assert _llegaron(atras, INTERPRETAR) + _llegaron(atras, DECISION) == esperado["llegan_atras"]

    async def test_proponer_sobre_el_kit_tiene_su_propia_cuenta(self, atras, redis):
        esperado = INTENTOS["proponer_aparte"]
        kit = str(uuid.uuid4())
        async with _http(CLIENTE) as http:
            topado = await _estados(http, 31, "POST", INTERPRETAR, **_texto())
            sobre_el_kit = await _estados(http, 31, "POST", _proponer(kit), **_texto())

        assert topado[-1] == 429
        assert sobre_el_kit == [200] * 30 + [429]
        assert _llegaron(atras, "/asistente/proponer") == esperado["llegan_atras"]

    async def test_la_61_de_la_misma_ip_recibe_429_aunque_cada_una_lleve_otro_token(
        self, atras, redis, record_property
    ):
        esperado = INTENTOS["ip_61"]
        async with _http(CLIENTE) as http:
            estados = [
                (await http.post(INTERPRETAR, **_texto(f"tok-{i // 20}"))).status_code for i in range(60)
            ]
            otra_familia = await http.post(INTERPRETAR, **_texto("tok-nueva"))

        record_property("peticiones_que_llegaron_atras", _llegaron(atras, INTERPRETAR))
        assert estados == [200] * 60
        assert otra_familia.status_code == 429
        assert _llegaron(atras, INTERPRETAR) == esperado["llegan_atras"]

    async def test_sin_token_interpretar_cuenta_solo_por_ip(self, atras, redis):
        esperado = INTENTOS["interpretar_sin_token"]
        async with _http(CLIENTE) as http:
            estados = await _estados(http, 61, "POST", INTERPRETAR, **_texto(None))

        assert estados == [200] * 60 + [429]
        assert _llegaron(atras, INTERPRETAR) == esperado["llegan_atras"]
        assert not any(c.split(":")[2:5] == ["estricto", "nl2c", "token"] for c in redis.claves())

    async def test_la_barra_final_suma_en_la_misma_cuenta_y_el_get_no_suma(self, atras, redis):
        async with _http(CLIENTE) as http:
            con_barra = await _estados(http, 15, "POST", INTERPRETAR + "/", **_texto())
            leidas = await _estados(http, 40, "GET", INTERPRETAR, headers=_bearer("tok-familia-nl2c"))
            sin_barra = await _estados(http, 16, "POST", INTERPRETAR, **_texto())

        assert con_barra == [200] * 15
        assert leidas == [200] * 40
        assert sin_barra == [200] * 15 + [429]

    async def test_las_claves_del_asistente_llevan_su_ruta_y_solo_huellas(self, atras, redis):
        token = "tok-secreto-de-la-familia-nl2c"
        async with _http(CLIENTE) as http:
            await http.post(INTERPRETAR, **_texto(token))
            await http.post(_proponer(), **_texto(token))

        claves = redis.claves()
        estrictas = sorted(c.split(":")[2:5] for c in claves if c.split(":")[2] == "estricto")
        assert estrictas == [
            ["estricto", "nl2c", "ip"],
            ["estricto", "nl2c", "token"],
            ["estricto", "nl2c-kit", "ip"],
            ["estricto", "nl2c-kit", "token"],
        ]
        assert not any(token in c or CLIENTE[0] in c for c in claves)
