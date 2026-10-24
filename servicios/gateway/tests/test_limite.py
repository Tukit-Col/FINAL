"""La puerta limita la tasa por token y por IP, en dos niveles (ADR 0047).

Se fija el 429 con su `Retry-After` y su cuerpo, que las dos claves tienen que
pasar, que el nivel estricto cuenta por ruta, de donde sale la IP del cliente
(solo se cree `X-Forwarded-For` si la conexion viene de un proxy de confianza),
las rutas que no cuentan, que con Redis caido cuenta en memoria, la
configuracion por entorno, y que ni el token ni la IP quedan en claro.
"""

from __future__ import annotations

import hashlib
import ipaddress
import logging
import sys

import httpx
import pytest
from tukit_comun.cache import usar_cliente
from tukit_comun.pruebas_redis import RedisEnMemoria, cliente_en_memoria
from tukit_gateway import api, limite
from tukit_gateway.api import app

CONFIANZA = (ipaddress.ip_network("127.0.0.1/32"), ipaddress.ip_network("::1/128"))


class Atras:
    """Los servicios de atras: responden 200 a todo y cuentan lo que les llega."""

    def __init__(self) -> None:
        self.peticiones: list[tuple[str, str]] = []
        atras = self

        class Cliente:
            def __init__(self, *args, **kwargs) -> None:
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, *args) -> bool:
                return False

            async def request(self, metodo, url, **_kwargs) -> httpx.Response:
                atras.peticiones.append((metodo, url))
                return httpx.Response(200, json={"ok": True})

        self.AsyncClient = Cliente
        self.HTTPError = httpx.HTTPError


@pytest.fixture()
def atras(monkeypatch) -> Atras:
    # Se cambia el `httpx` que ve `api`, no el de verdad, que usa el cliente de
    # la prueba (comparten el modulo).
    falso = Atras()
    monkeypatch.setattr(api, "httpx", falso)
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


async def _estados(http: httpx.AsyncClient, veces: int, metodo: str, ruta: str, **kwargs) -> list[int]:
    return [(await http.request(metodo, ruta, **kwargs)).status_code for _ in range(veces)]


# --- Por debajo y por encima ------------------------------------------------


async def test_por_debajo_del_limite_pasa_y_por_encima_da_429(atras, redis, monkeypatch):
    monkeypatch.setenv("TUKIT_LIMITE_GENERAL_IP", "3")
    async with _http() as http:
        estados = await _estados(http, 3, "GET", "/v1/catalogo/conceptos")
        respuesta = await http.get("/v1/catalogo/conceptos")

    assert estados == [200, 200, 200]
    assert len(atras.peticiones) == 3
    assert respuesta.status_code == 429
    cuerpo = respuesta.json()
    assert cuerpo["error"] == "demasiadas_peticiones"
    assert 1 <= cuerpo["reintentar_en_segundos"] <= 60
    assert respuesta.headers["Retry-After"] == str(cuerpo["reintentar_en_segundos"])
    assert cuerpo["mensaje"] == limite.mensaje(cuerpo["reintentar_en_segundos"])


async def test_el_429_no_llega_a_los_servicios(atras, redis, monkeypatch):
    monkeypatch.setenv("TUKIT_LIMITE_GENERAL_IP", "1")
    async with _http() as http:
        await _estados(http, 5, "POST", "/v1/catalogo/emparejar", json={"renglones": ["a"]})

    assert len(atras.peticiones) == 1


async def test_el_429_del_nivel_estricto_dice_la_espera_en_minutos(atras, redis, monkeypatch):
    monkeypatch.setenv("TUKIT_LIMITE_ESTRICTO_IP", "1")
    async with _http() as http:
        await http.post("/v1/sesiones", json={})
        respuesta = await http.post("/v1/sesiones", json={})

    assert respuesta.status_code == 429
    segundos = respuesta.json()["reintentar_en_segundos"]
    assert 540 < segundos <= 600
    assert respuesta.headers["Retry-After"] == str(segundos)
    assert "10 minutos" in respuesta.json()["mensaje"]


async def test_la_ventana_vencida_vuelve_a_dar_cupo(atras, monkeypatch):
    ahora = [1000.0]
    usar_cliente(cliente_en_memoria(RedisEnMemoria(reloj=lambda: ahora[0]), reloj=lambda: ahora[0]))
    monkeypatch.setenv("TUKIT_LIMITE_GENERAL_IP", "1")
    async with _http() as http:
        assert await _estados(http, 2, "GET", "/v1/colegios") == [200, 429]
        ahora[0] += 61
        assert await _estados(http, 1, "GET", "/v1/colegios") == [200]


def test_retry_after_es_lo_que_le_falta_a_la_clave_mas_lenta():
    assert limite.mensaje(1) == (
        "Hiciste demasiadas peticiones en poco tiempo. Vuelve a intentarlo en 1 segundo."
    )
    assert limite.mensaje(59).endswith("en 59 segundos.")
    assert limite.mensaje(60).endswith("en 1 minuto.")
    assert limite.mensaje(61).endswith("en 2 minutos.")


async def test_retry_after_toma_la_mayor_espera_de_las_claves_pasadas(atras, redis, monkeypatch):
    # El general de la IP y el estricto de la IP pasan a la vez: manda el de 600 s.
    monkeypatch.setenv("TUKIT_LIMITE_GENERAL_IP", "1")
    monkeypatch.setenv("TUKIT_LIMITE_ESTRICTO_IP", "1")
    async with _http() as http:
        await http.post("/v1/registro", json={})
        respuesta = await http.post("/v1/registro", json={})

    assert int(respuesta.headers["Retry-After"]) > 540


# --- Las dos claves ---------------------------------------------------------


async def test_el_token_tiene_su_cupo_y_otro_token_de_la_misma_ip_tiene_el_suyo(atras, redis, monkeypatch):
    monkeypatch.setenv("TUKIT_LIMITE_GENERAL_TOKEN", "2")
    async with _http() as http:
        de_ana = await _estados(http, 3, "GET", "/v1/cuenta", headers=_bearer("tok-ana"))
        de_luis = await _estados(http, 2, "GET", "/v1/cuenta", headers=_bearer("tok-luis"))

    assert de_ana == [200, 200, 429]
    assert de_luis == [200, 200]


async def test_inventar_un_token_por_peticion_no_da_cupo_porque_cuenta_la_ip(atras, redis, monkeypatch):
    monkeypatch.setenv("TUKIT_LIMITE_GENERAL_IP", "3")
    async with _http() as http:
        estados = [(await http.get("/v1/cuenta", headers=_bearer(f"tok-{i}"))).status_code for i in range(5)]

    assert estados == [200, 200, 200, 429, 429]


async def test_sin_token_solo_cuenta_la_ip(atras, redis):
    async with _http() as http:
        await http.get("/v1/colegios")
        await http.get("/v1/colegios", headers={"Authorization": "Basic dXN1YXJpbzpjbGF2ZQ=="})

    claves = [c for (c,) in redis.operaciones("contar")]
    assert len(claves) == 2
    assert all(":ip:" in c for c in claves)


async def test_con_token_cuentan_las_dos_en_una_sola_ida_a_redis(atras, redis):
    async with _http() as http:
        await http.get("/v1/colegios", headers=_bearer("tok-ana"))

    (claves,) = redis.operaciones("contar")
    assert [c.split(":")[1:5] for c in claves] == [
        ["limite", "general", "v1", "token"],
        ["limite", "general", "v1", "ip"],
    ]


# --- El nivel estricto ------------------------------------------------------


async def test_una_ruta_estricta_cuenta_en_los_dos_niveles(atras, redis):
    async with _http() as http:
        await http.post("/v1/listas/subir", headers=_bearer("tok-ana"))

    (claves,) = redis.operaciones("contar")
    assert [c.split(":")[2:5] for c in claves] == [
        ["general", "v1", "token"],
        ["general", "v1", "ip"],
        ["estricto", "listas-subir", "token"],
        ["estricto", "listas-subir", "ip"],
    ]


async def test_el_nivel_estricto_cuenta_por_ruta(atras, redis, monkeypatch):
    monkeypatch.setenv("TUKIT_LIMITE_ESTRICTO_TOKEN", "2")
    async with _http() as http:
        entrar = await _estados(http, 3, "POST", "/v1/sesiones", headers=_bearer("tok-ana"))
        subir = await _estados(http, 2, "POST", "/v1/listas/subir", headers=_bearer("tok-ana"))
        leer = await _estados(http, 3, "GET", "/v1/sesiones/actual", headers=_bearer("tok-ana"))

    assert entrar == [200, 200, 429]
    assert subir == [200, 200]
    assert leer == [200, 200, 200]


@pytest.mark.parametrize(
    ("metodo", "ruta", "nombre"),
    [
        ("POST", "/v1/listas/subir", "listas-subir"),
        ("POST", "/v1/trabajos", "trabajos"),
        ("POST", "/v1/trabajos/8a1c/reintentar", "trabajos-reintentar"),
        ("POST", "/v1/trabajos/aplicar-canonico", "trabajos-aplicar-canonico"),
        ("POST", "/v1/admin/onboarding", "onboarding"),
        ("POST", "/v1/admin/onboarding/ver-1/preview", "onboarding-preview"),
        ("POST", "/v1/sesiones", "sesiones"),
        ("POST", "/v1/sesiones/", "sesiones"),
        ("POST", "/v1/cuenta", "cuenta"),
        ("POST", "/v1/registro", "registro"),
        ("POST", "/v1/catalogo/emparejar", "catalogo-emparejar"),
        ("GET", "/v1/trabajos", None),
        ("POST", "/v1/sesiones/cierre", None),
        ("POST", "/v1/trabajos/8a1c", None),
        ("PATCH", "/v1/cuenta", None),
        ("POST", "/v1/cuenta/direcciones", None),
        # El flujo de pagos queda en el general: lo decide Juan.
        ("POST", "/v1/ordenes", None),
        ("POST", "/v1/comercio/mis-pedidos/p-1/pago", None),
        ("POST", "/v1/pagos/p-1/sincronizar", None),
    ],
)
def test_las_rutas_estrictas(metodo, ruta, nombre):
    assert limite.ruta_estricta(metodo, ruta) == nombre


def test_cada_ruta_estricta_existe_en_el_mapa_de_la_puerta():
    for _, patron in limite.RUTAS_ESTRICTAS:
        ejemplo = patron.pattern.replace("[^/]+", "x")
        assert api.destino(ejemplo) is not None, ejemplo


# --- La IP del cliente ------------------------------------------------------


@pytest.mark.parametrize(
    ("conexion", "reenviada", "esperada"),
    [
        # Sin cabecera, la de la conexion.
        ("127.0.0.1", None, "127.0.0.1"),
        ("203.0.113.9", None, "203.0.113.9"),
        # Desde un proxy de confianza: la primera sin confianza desde la derecha.
        ("127.0.0.1", "198.51.100.7", "198.51.100.7"),
        ("127.0.0.1", "10.9.9.9, 198.51.100.7", "198.51.100.7"),
        ("127.0.0.1", "198.51.100.7, 127.0.0.1", "198.51.100.7"),
        ("::1", "2001:db8::5", "2001:db8::5"),
        # Todas de confianza: la de mas a la izquierda.
        ("127.0.0.1", "127.0.0.1, ::1", "127.0.0.1"),
        # Algo que no es una IP corta el recorrido: vale la ultima de confianza.
        ("127.0.0.1", "198.51.100.7, basura, 127.0.0.1", "127.0.0.1"),
        ("127.0.0.1", "198.51.100.7, unknown", "127.0.0.1"),
        # Las entradas vacias no cortan nada.
        ("127.0.0.1", "198.51.100.7, ", "198.51.100.7"),
        # Desde una conexion sin confianza, la cabecera la escribio el cliente.
        ("203.0.113.9", "198.51.100.7", "203.0.113.9"),
        ("203.0.113.9", "127.0.0.1", "203.0.113.9"),
        # Una IPv4 escrita como IPv6 es la misma IPv4.
        ("::ffff:127.0.0.1", "198.51.100.7", "198.51.100.7"),
        ("127.0.0.1", "::ffff:198.51.100.7", "198.51.100.7"),
        # Sin conexion conocida.
        (None, "198.51.100.7", "desconocida"),
    ],
)
def test_la_ip_del_cliente(conexion, reenviada, esperada):
    assert limite.ip_del_cliente(conexion, reenviada, CONFIANZA) == esperada


def test_los_proxies_de_confianza_se_configuran_con_redes(monkeypatch, caplog):
    monkeypatch.setenv("TUKIT_PROXIES_CONFIANZA", "127.0.0.1, 172.16.0.0/12, no-es-una-red")
    with caplog.at_level(logging.WARNING):
        redes = limite.proxies_de_confianza()

    assert redes == (ipaddress.ip_network("127.0.0.1/32"), ipaddress.ip_network("172.16.0.0/12"))
    assert "no-es-una-red" in caplog.text
    assert limite.ip_del_cliente("172.18.0.1", "198.51.100.7", redes) == "198.51.100.7"


async def test_x_forwarded_for_desde_un_proxy_de_confianza_separa_a_los_clientes(atras, redis, monkeypatch):
    monkeypatch.setenv("TUKIT_LIMITE_GENERAL_IP", "2")
    async with _http(("127.0.0.1", 50_000)) as http:
        de_una = await _estados(http, 3, "GET", "/v1/colegios", headers={"X-Forwarded-For": "198.51.100.7"})
        de_otra = await _estados(http, 2, "GET", "/v1/colegios", headers={"X-Forwarded-For": "198.51.100.8"})

    assert de_una == [200, 200, 429]
    assert de_otra == [200, 200]


async def test_x_forwarded_for_desde_un_cliente_cualquiera_no_cambia_la_ip(atras, redis, monkeypatch):
    monkeypatch.setenv("TUKIT_LIMITE_GENERAL_IP", "2")
    async with _http(("203.0.113.9", 50_000)) as http:
        estados = [
            (await http.get("/v1/colegios", headers={"X-Forwarded-For": f"198.51.100.{i}"})).status_code
            for i in range(3)
        ]

    assert estados == [200, 200, 429]


def _como_se_lanza(monkeypatch) -> tuple[tuple, dict]:
    """Con que argumentos lanza `api.main` a uvicorn, sin lanzarlo."""
    lanzada: list[tuple[tuple, dict]] = []

    class Uvicorn:
        @staticmethod
        def run(*args, **kwargs) -> None:
            lanzada.append((args, kwargs))

    with monkeypatch.context() as m:
        m.setitem(sys.modules, "uvicorn", Uvicorn)
        assert api.main(["--puerto", "18999"]) == 0
    assert len(lanzada) == 1
    return lanzada[0]


def test_la_puerta_se_lanza_sin_que_uvicorn_lea_x_forwarded_for(monkeypatch):
    _, opciones = _como_se_lanza(monkeypatch)

    assert opciones["proxy_headers"] is False


async def test_solo_la_puerta_decide_de_quien_es_x_forwarded_for(atras, redis, monkeypatch):
    # Con la pila que arma uvicorn al lanzar la puerta. Si uvicorn leyera la
    # cabecera, confiaria en 127.0.0.1 aunque `TUKIT_PROXIES_CONFIANZA` no, y
    # cada IP inventada tendria su cupo.
    uvicorn = pytest.importorskip("uvicorn")
    args, opciones = _como_se_lanza(monkeypatch)
    # Sin `log_config`, uvicorn reconfiguraria el registro de toda la corrida.
    configuracion = uvicorn.Config(*args, **{**opciones, "log_config": None})
    configuracion.load()
    monkeypatch.setenv("TUKIT_PROXIES_CONFIANZA", "192.0.2.1")
    monkeypatch.setenv("TUKIT_LIMITE_GENERAL_IP", "5")

    transporte = httpx.ASGITransport(app=configuracion.loaded_app, client=("127.0.0.1", 50_000))
    async with httpx.AsyncClient(transport=transporte, base_url="http://prueba") as http:
        estados = [
            (await http.get("/v1/colegios", headers={"X-Forwarded-For": f"198.51.100.{i}"})).status_code
            for i in range(6)
        ]

    assert estados == [200] * 5 + [429]


# --- Lo que no cuenta -------------------------------------------------------


@pytest.mark.parametrize(
    ("metodo", "ruta"),
    [
        ("GET", "/v1/servicios"),
        ("POST", "/v1/webhooks/wompi"),
        ("POST", "/v1/webhooks"),
        ("OPTIONS", "/v1/catalogo/conceptos"),
        ("GET", "/salud"),
        ("GET", "/health/ready"),
        ("GET", "/favicon.ico"),
    ],
)
def test_las_rutas_exentas(metodo, ruta):
    assert limite.cuentas(metodo, ruta, "tok-ana", "198.51.100.7") == []


async def test_las_exentas_no_llegan_a_redis_y_una_desconocida_si(atras, redis, monkeypatch):
    monkeypatch.setenv("TUKIT_LIMITE_GENERAL_IP", "1")
    async with _http() as http:
        webhooks = await _estados(http, 3, "POST", "/v1/webhooks/wompi", json={})
        salud = await _estados(http, 3, "GET", "/salud")
        desconocida = await _estados(http, 2, "GET", "/v1/inventado")

    assert webhooks == [200, 200, 200]
    assert salud == [200, 200, 200]
    assert desconocida == [404, 429]
    assert len(redis.operaciones("contar")) == 2


async def test_la_sonda_de_servicios_no_cuenta(redis, monkeypatch):
    for servicio in ("CATALOGO", "IDENTIDAD", "INTELIGENCIA", "COMERCIO", "OPERACION"):
        monkeypatch.setenv(f"TUKIT_{servicio}_URL", "http://127.0.0.1:1")
    monkeypatch.setenv("TUKIT_LIMITE_GENERAL_IP", "1")
    async with _http() as http:
        estados = await _estados(http, 2, "GET", "/v1/servicios")

    assert estados == [200, 200]
    assert redis.operaciones("contar") == []


# --- Sin Redis, o con Redis caido ------------------------------------------


async def test_sin_redis_cuenta_en_la_memoria_del_proceso(atras, monkeypatch):
    monkeypatch.setenv("TUKIT_LIMITE_GENERAL_IP", "2")
    async with _http() as http:
        assert await _estados(http, 3, "GET", "/v1/colegios") == [200, 200, 429]


async def test_con_redis_caido_cuenta_en_memoria_y_nunca_da_500(atras, redis, monkeypatch):
    redis.caido = True
    monkeypatch.setenv("TUKIT_LIMITE_GENERAL_IP", "2")
    async with _http() as http:
        estados = await _estados(http, 3, "GET", "/v1/colegios")

    assert estados == [200, 200, 429]
    # Tras el primer fallo deja de preguntarle durante la pausa.
    assert len(redis.operaciones("contar")) == 1


async def test_con_redis_lento_cuenta_en_memoria(atras, redis, monkeypatch):
    redis.demora = 1.0
    monkeypatch.setenv("TUKIT_LIMITE_GENERAL_IP", "1")
    async with _http() as http:
        assert await _estados(http, 2, "GET", "/v1/colegios") == [200, 429]


async def test_con_redis_cuenta_en_redis(atras, redis, monkeypatch):
    monkeypatch.setenv("TUKIT_LIMITE_GENERAL_IP", "2")
    async with _http() as http:
        assert await _estados(http, 3, "GET", "/v1/colegios") == [200, 200, 429]

    assert len(redis.operaciones("contar")) == 3
    (clave,) = redis.claves()
    assert redis.vence_en(clave) == pytest.approx(60, abs=2)


# --- La configuracion -------------------------------------------------------


def test_los_numeros_por_omision():
    general, estricto = limite.niveles()
    assert (general.ventana, general.por_token, general.por_ip) == (60, 300, 1200)
    assert (estricto.ventana, estricto.por_token, estricto.por_ip) == (600, 30, 60)


def test_se_configuran_por_entorno_y_un_valor_malo_deja_el_de_omision(monkeypatch, caplog):
    monkeypatch.setenv("TUKIT_LIMITE_GENERAL_VENTANA", "30")
    monkeypatch.setenv("TUKIT_LIMITE_ESTRICTO_TOKEN", "cinco")
    with caplog.at_level(logging.WARNING):
        general, estricto = limite.niveles()
        limite.niveles()

    assert general.ventana == 30
    assert estricto.por_token == 30
    assert caplog.text.count("TUKIT_LIMITE_ESTRICTO_TOKEN") == 1


def test_un_cero_apaga_un_tope_o_un_nivel(monkeypatch):
    monkeypatch.setenv("TUKIT_LIMITE_GENERAL_TOKEN", "0")
    assert [c.tipo for c in limite.cuentas("GET", "/v1/colegios", "tok", "198.51.100.7")] == ["ip"]
    monkeypatch.setenv("TUKIT_LIMITE_ESTRICTO_VENTANA", "0")
    assert [c.nivel for c in limite.cuentas("POST", "/v1/sesiones", "tok", "198.51.100.7")] == ["general"]


# --- Nada en claro ----------------------------------------------------------


async def test_ni_el_token_ni_la_ip_quedan_en_claro_ni_en_el_log(atras, redis, monkeypatch, caplog):
    token = "tok-secreto-de-la-familia"
    monkeypatch.setenv("TUKIT_LIMITE_GENERAL_TOKEN", "1")
    with caplog.at_level(logging.DEBUG):
        async with _http() as http:
            await _estados(
                http, 2, "GET", "/v1/cuenta", headers={**_bearer(token), "X-Forwarded-For": "198.51.100.7"}
            )

    huella_token = hashlib.sha256(token.encode()).hexdigest()
    huella_ip = hashlib.sha256(b"198.51.100.7").hexdigest()
    claves = redis.claves()
    assert sorted(c.rsplit(":", 1)[1] for c in claves) == sorted([huella_token, huella_ip])
    assert not any(token in c or "198.51.100.7" in c for c in claves)
    assert "429 por general:v1:token" in caplog.text
    for dato in (token, huella_token, huella_ip, "198.51.100.7"):
        assert dato not in caplog.text


async def test_cada_rechazo_se_cuenta_por_nivel(atras, redis, monkeypatch):
    niveles: list[str] = []
    monkeypatch.setattr(limite.metricas, "contar_limite_rechazado", niveles.append)
    monkeypatch.setenv("TUKIT_LIMITE_GENERAL_IP", "1")
    monkeypatch.setenv("TUKIT_LIMITE_ESTRICTO_IP", "1")
    async with _http() as http:
        await _estados(http, 2, "POST", "/v1/sesiones", json={})
        await _estados(http, 1, "GET", "/v1/colegios")

    assert niveles == ["estricto", "general", "general"]
