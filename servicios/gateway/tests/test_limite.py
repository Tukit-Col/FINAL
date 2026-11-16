"""La puerta limita la tasa por token y por IP, en dos niveles (ADR 0047), por HTTP.

Se fija el 429 con su `Retry-After` y su cuerpo, que las dos claves tienen que
pasar, que el nivel estricto cuenta por ruta, que las exentas no llegan a Redis,
que con Redis caido o lento cuenta en memoria, y que ni el token ni la IP quedan
en claro. De donde sale la IP esta en `test_limite_ip_cliente.py`; los topes y
las rutas, en `test_limite_configuracion.py`.
"""

from __future__ import annotations

import hashlib
import logging

import pytest
from _ayudas_gateway import bearer, codigos, http_de
from tukit_comun.cache import usar_cliente
from tukit_comun.pruebas_redis import RedisEnMemoria, cliente_en_memoria
from tukit_gateway import limite

# --- Por debajo y por encima ------------------------------------------------


async def test_por_debajo_del_limite_pasa_y_por_encima_da_429(atras, redis, monkeypatch):
    monkeypatch.setenv("TUKIT_LIMITE_GENERAL_IP", "3")
    async with http_de() as http:
        estados = await codigos(http, 3, "GET", "/v1/catalogo/conceptos")
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
    async with http_de() as http:
        await codigos(http, 5, "POST", "/v1/catalogo/emparejar", json={"renglones": ["a"]})

    assert len(atras.peticiones) == 1


async def test_el_429_del_nivel_estricto_dice_la_espera_en_minutos(atras, redis, monkeypatch):
    monkeypatch.setenv("TUKIT_LIMITE_ESTRICTO_IP", "1")
    async with http_de() as http:
        await http.post("/v1/sesiones", json={})
        respuesta = await http.post("/v1/sesiones", json={})

    assert respuesta.status_code == 429
    segundos = respuesta.json()["reintentar_en_segundos"]
    # Lo que falta de la ventana estricta: casi entera, porque recien empezo.
    ventana = limite.niveles()[1].ventana
    assert ventana * 0.9 < segundos <= ventana
    assert respuesta.headers["Retry-After"] == str(segundos)
    assert "10 minutos" in respuesta.json()["mensaje"]


async def test_la_ventana_vencida_vuelve_a_dar_cupo(atras, monkeypatch):
    ahora = [1000.0]
    usar_cliente(cliente_en_memoria(RedisEnMemoria(reloj=lambda: ahora[0]), reloj=lambda: ahora[0]))
    monkeypatch.setenv("TUKIT_LIMITE_GENERAL_IP", "1")
    async with http_de() as http:
        assert await codigos(http, 2, "GET", "/v1/colegios") == [200, 429]
        ahora[0] += 61
        assert await codigos(http, 1, "GET", "/v1/colegios") == [200]


def test_retry_after_es_lo_que_le_falta_a_la_clave_mas_lenta():
    assert limite.mensaje(1) == (
        "Hiciste demasiadas peticiones en poco tiempo. Vuelve a intentarlo en 1 segundo."
    )
    assert limite.mensaje(59).endswith("en 59 segundos.")
    assert limite.mensaje(60).endswith("en 1 minuto.")
    assert limite.mensaje(61).endswith("en 2 minutos.")


async def test_retry_after_toma_la_mayor_espera_de_las_claves_pasadas(atras, redis, monkeypatch):
    # El general de la IP y el estricto de la IP pasan a la vez: manda la ventana mas larga.
    monkeypatch.setenv("TUKIT_LIMITE_GENERAL_IP", "1")
    monkeypatch.setenv("TUKIT_LIMITE_ESTRICTO_IP", "1")
    async with http_de() as http:
        await http.post("/v1/registro", json={})
        respuesta = await http.post("/v1/registro", json={})

    general, estricto = limite.niveles()
    assert int(respuesta.headers["Retry-After"]) > general.ventana
    assert int(respuesta.headers["Retry-After"]) <= estricto.ventana


# --- Las dos claves ---------------------------------------------------------


async def test_el_token_tiene_su_cupo_y_otro_token_de_la_misma_ip_tiene_el_suyo(atras, redis, monkeypatch):
    monkeypatch.setenv("TUKIT_LIMITE_GENERAL_TOKEN", "2")
    async with http_de() as http:
        de_ana = await codigos(http, 3, "GET", "/v1/cuenta", headers=bearer("tok-ana"))
        de_luis = await codigos(http, 2, "GET", "/v1/cuenta", headers=bearer("tok-luis"))

    assert de_ana == [200, 200, 429]
    assert de_luis == [200, 200]


async def test_inventar_un_token_por_peticion_no_da_cupo_porque_cuenta_la_ip(atras, redis, monkeypatch):
    monkeypatch.setenv("TUKIT_LIMITE_GENERAL_IP", "3")
    async with http_de() as http:
        estados = [(await http.get("/v1/cuenta", headers=bearer(f"tok-{i}"))).status_code for i in range(5)]

    assert estados == [200, 200, 200, 429, 429]


async def test_sin_token_solo_cuenta_la_ip(atras, redis):
    async with http_de() as http:
        await http.get("/v1/colegios")
        await http.get("/v1/colegios", headers={"Authorization": "Basic dXN1YXJpbzpjbGF2ZQ=="})

    claves = [c for (c,) in redis.operaciones("contar")]
    assert len(claves) == 2
    assert all(":ip:" in c for c in claves)


async def test_con_token_cuentan_las_dos_en_una_sola_ida_a_redis(atras, redis):
    async with http_de() as http:
        await http.get("/v1/colegios", headers=bearer("tok-ana"))

    (claves,) = redis.operaciones("contar")
    assert [c.split(":")[1:5] for c in claves] == [
        ["limite", "general", "v1", "token"],
        ["limite", "general", "v1", "ip"],
    ]


# --- El nivel estricto ------------------------------------------------------


async def test_una_ruta_estricta_cuenta_en_los_dos_niveles(atras, redis):
    async with http_de() as http:
        await http.post("/v1/listas/subir", headers=bearer("tok-ana"))

    (claves,) = redis.operaciones("contar")
    assert [c.split(":")[2:5] for c in claves] == [
        ["general", "v1", "token"],
        ["general", "v1", "ip"],
        ["estricto", "listas-subir", "token"],
        ["estricto", "listas-subir", "ip"],
    ]


async def test_el_nivel_estricto_cuenta_por_ruta(atras, redis, monkeypatch):
    monkeypatch.setenv("TUKIT_LIMITE_ESTRICTO_TOKEN", "2")
    async with http_de() as http:
        entrar = await codigos(http, 3, "POST", "/v1/sesiones", headers=bearer("tok-ana"))
        subir = await codigos(http, 2, "POST", "/v1/listas/subir", headers=bearer("tok-ana"))
        leer = await codigos(http, 3, "GET", "/v1/sesiones/actual", headers=bearer("tok-ana"))

    assert entrar == [200, 200, 429]
    assert subir == [200, 200]
    assert leer == [200, 200, 200]


async def test_el_sexto_intento_de_suprimir_es_429(atras, redis):
    async with http_de() as http:
        estados = await codigos(http, 6, "POST", "/v1/cuenta/supresion", headers=bearer("tok-ana"))
    assert estados == [200, 200, 200, 200, 200, 429]


# --- Lo que no cuenta -------------------------------------------------------


async def test_las_exentas_no_llegan_a_redis_y_una_desconocida_si(atras, redis, monkeypatch):
    monkeypatch.setenv("TUKIT_LIMITE_GENERAL_IP", "1")
    async with http_de() as http:
        webhooks = await codigos(http, 3, "POST", "/v1/webhooks/wompi", json={})
        salud = await codigos(http, 3, "GET", "/salud")
        desconocida = await codigos(http, 2, "GET", "/v1/inventado")

    assert webhooks == [200, 200, 200]
    assert salud == [200, 200, 200]
    assert desconocida == [404, 429]
    assert len(redis.operaciones("contar")) == 2


async def test_la_sonda_de_servicios_no_cuenta(redis, monkeypatch):
    for servicio in ("CATALOGO", "IDENTIDAD", "INTELIGENCIA", "COMERCIO", "OPERACION"):
        monkeypatch.setenv(f"TUKIT_{servicio}_URL", "http://127.0.0.1:1")
    monkeypatch.setenv("TUKIT_LIMITE_GENERAL_IP", "1")
    async with http_de() as http:
        estados = await codigos(http, 2, "GET", "/v1/servicios")

    assert estados == [200, 200]
    assert redis.operaciones("contar") == []


# --- Sin Redis, o con Redis caido ------------------------------------------


async def test_sin_redis_cuenta_en_la_memoria_del_proceso(atras, monkeypatch):
    monkeypatch.setenv("TUKIT_LIMITE_GENERAL_IP", "2")
    async with http_de() as http:
        assert await codigos(http, 3, "GET", "/v1/colegios") == [200, 200, 429]


async def test_con_redis_caido_cuenta_en_memoria_y_nunca_da_500(atras, redis, monkeypatch):
    redis.caido = True
    monkeypatch.setenv("TUKIT_LIMITE_GENERAL_IP", "2")
    async with http_de() as http:
        estados = await codigos(http, 3, "GET", "/v1/colegios")

    assert estados == [200, 200, 429]
    # Tras el primer fallo deja de preguntarle durante la pausa.
    assert len(redis.operaciones("contar")) == 1


async def test_con_redis_lento_cuenta_en_memoria(atras, redis, monkeypatch):
    redis.demora = 1.0
    monkeypatch.setenv("TUKIT_LIMITE_GENERAL_IP", "1")
    async with http_de() as http:
        assert await codigos(http, 2, "GET", "/v1/colegios") == [200, 429]


async def test_con_redis_cuenta_en_redis(atras, redis, monkeypatch):
    monkeypatch.setenv("TUKIT_LIMITE_GENERAL_IP", "2")
    async with http_de() as http:
        assert await codigos(http, 3, "GET", "/v1/colegios") == [200, 200, 429]

    assert len(redis.operaciones("contar")) == 3
    (clave,) = redis.claves()
    assert redis.vence_en(clave) == pytest.approx(60, abs=2)


# --- Nada en claro ----------------------------------------------------------


async def test_ni_el_token_ni_la_ip_quedan_en_claro_ni_en_el_log(atras, redis, monkeypatch, caplog):
    token = "tok-secreto-de-la-familia"
    monkeypatch.setenv("TUKIT_LIMITE_GENERAL_TOKEN", "1")
    with caplog.at_level(logging.DEBUG):
        async with http_de() as http:
            await codigos(
                http, 2, "GET", "/v1/cuenta", headers={**bearer(token), "X-Forwarded-For": "198.51.100.7"}
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
    async with http_de() as http:
        await codigos(http, 2, "POST", "/v1/sesiones", json={})
        await codigos(http, 1, "GET", "/v1/colegios")

    assert niveles == ["estricto", "general", "general"]
