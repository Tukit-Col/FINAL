from __future__ import annotations

import logging
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest
from tukit_comun import cache
from tukit_comun.cache import ClienteRedis, MotorEnMemoria, cliente_desde_entorno, entero_de_entorno
from tukit_comun.pruebas_redis import RedisEnMemoria, cliente_en_memoria


class Reloj:
    def __init__(self) -> None:
        self.ahora = 1000.0

    def __call__(self) -> float:
        return self.ahora

    def avanzar(self, segundos: float) -> None:
        self.ahora += segundos


@pytest.fixture
def reloj() -> Reloj:
    return Reloj()


@pytest.fixture
def motor(reloj: Reloj) -> RedisEnMemoria:
    return RedisEnMemoria(reloj=reloj)


@pytest.fixture
def cliente(motor: RedisEnMemoria, reloj: Reloj) -> ClienteRedis:
    return cliente_en_memoria(motor, reloj=reloj)


async def test_lo_guardado_se_lee_con_el_prefijo(cliente, motor):
    await cliente.guardar("percepcion", "v1:abc", b"valor", 60)

    assert await cliente.leer("percepcion", "v1:abc") == b"valor"
    assert motor.guardado("tukit:v1:abc") == b"valor"


async def test_leer_varias_respeta_el_orden_y_marca_lo_que_falta(cliente):
    await cliente.guardar_varias("vector", {"b": b"2", "d": b"4"}, 60)

    assert await cliente.leer_varias("vector", ["a", "b", "c", "d"]) == [None, b"2", None, b"4"]


async def test_leer_varias_va_en_una_sola_llamada(cliente, motor):
    await cliente.leer_varias("vector", ["a", "b", "c"])

    assert motor.operaciones("leer") == [("tukit:a", "tukit:b", "tukit:c")]


async def test_sin_claves_no_llama_al_motor(cliente, motor):
    assert await cliente.leer_varias("vector", []) == []
    await cliente.guardar_varias("vector", {}, 60)
    assert await cliente.contar([]) == []

    assert motor.llamadas == []


async def test_lo_guardado_vence_al_cumplirse_su_ttl(cliente, reloj):
    await cliente.guardar("vector", "a", b"1", 60)

    reloj.avanzar(59)
    assert await cliente.leer("vector", "a") == b"1"
    reloj.avanzar(1)
    assert await cliente.leer("vector", "a") is None


async def test_ttl_cero_apaga_el_guardado(cliente, motor):
    await cliente.guardar("vector", "a", b"1", 0)

    assert motor.operaciones("guardar") == []
    assert await cliente.leer("vector", "a") is None


async def test_el_vencimiento_es_el_pedido(cliente, motor):
    await cliente.guardar("percepcion", "a", b"1", 2_592_000)

    assert motor.vence_en("tukit:a") == pytest.approx(2_592_000)


async def test_contar_suma_y_dice_lo_que_falta_de_la_ventana(cliente, reloj):
    assert await cliente.contar([("token:x", 60), ("ip:y", 600)]) == [(1, 60_000), (1, 600_000)]

    reloj.avanzar(10)
    assert await cliente.contar([("token:x", 60), ("ip:y", 600)]) == [(2, 50_000), (2, 590_000)]


async def test_la_ventana_vencida_vuelve_a_empezar(cliente, reloj):
    for _ in range(3):
        await cliente.contar([("token:x", 60)])

    reloj.avanzar(60)
    assert await cliente.contar([("token:x", 60)]) == [(1, 60_000)]


async def test_el_motor_en_memoria_poda_sin_pasar_del_tope(reloj):
    motor = MotorEnMemoria(reloj=reloj, tope=3)
    for i in range(5):
        await motor.contar([(f"c{i}", 60 + i)])

    assert len(motor._cuentas) == 3
    assert set(motor._cuentas) == {"c2", "c3", "c4"}


async def test_caido_lee_como_si_no_estuviera(cliente, motor):
    await cliente.guardar("vector", "a", b"1", 60)
    motor.caido = True

    assert await cliente.leer_varias("vector", ["a", "b"]) == [None, None]
    assert cliente.degradado


async def test_caido_no_guarda_y_no_revienta(cliente, motor):
    motor.caido = True

    await cliente.guardar("vector", "a", b"1", 60)

    assert motor.guardado("tukit:a") is None


async def test_caido_cuenta_en_memoria(cliente, motor):
    motor.caido = True

    assert await cliente.contar([("token:x", 60)]) == [(1, 60_000)]
    assert await cliente.contar([("token:x", 60)]) == [(2, 60_000)]


async def test_lento_se_rinde_en_la_espera(motor, reloj):
    motor.demora = 2.0
    cliente = cliente_en_memoria(motor, espera=0.05, reloj=reloj)

    inicio = time.monotonic()
    assert await cliente.leer("vector", "a") is None
    assert await cliente.contar([("token:x", 60)]) == [(1, 60_000)]

    assert time.monotonic() - inicio < 1.0
    assert cliente.degradado


async def test_un_error_que_no_es_de_redis_sube(cliente, motor, monkeypatch):
    async def roto(claves):
        raise ValueError("un error de programacion")

    monkeypatch.setattr(motor, "leer_varias", roto)

    with pytest.raises(ValueError):
        await cliente.leer("vector", "a")


async def test_un_solo_warning_por_episodio_y_sin_claves(cliente, motor, reloj, caplog):
    motor.caido = True
    caplog.set_level(logging.INFO, logger="tukit_comun.cache")

    for _ in range(3):
        await cliente.leer("limite", "general:v1:token:huella-del-token")
        reloj.avanzar(6)

    avisos = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert len(avisos) == 1
    assert "RedisCaido" in avisos[0].getMessage()
    assert "huella-del-token" not in caplog.text


async def test_tras_un_fallo_no_pregunta_durante_la_pausa(cliente, motor, reloj):
    motor.caido = True
    await cliente.leer("vector", "a")
    motor.caido = False

    reloj.avanzar(4.9)
    await cliente.leer("vector", "a")
    await cliente.contar([("token:x", 60)])
    assert len(motor.llamadas) == 1

    reloj.avanzar(0.2)
    await cliente.leer("vector", "a")
    assert len(motor.llamadas) == 2


async def test_la_vuelta_deja_un_info_y_cierra_el_episodio(cliente, motor, reloj, caplog):
    caplog.set_level(logging.INFO, logger="tukit_comun.cache")
    motor.caido = True
    await cliente.guardar("vector", "a", b"1", 60)
    motor.caido = False
    reloj.avanzar(6)

    await cliente.guardar("vector", "a", b"1", 60)

    assert not cliente.degradado
    assert await cliente.leer("vector", "a") == b"1"
    vueltas = [r for r in caplog.records if r.levelno == logging.INFO and "volvio" in r.getMessage()]
    assert len(vueltas) == 1


async def test_un_episodio_nuevo_vuelve_a_avisar(cliente, motor, reloj, caplog):
    caplog.set_level(logging.WARNING, logger="tukit_comun.cache")
    for _ in range(2):
        motor.caido = True
        await cliente.leer("vector", "a")
        motor.caido = False
        reloj.avanzar(6)
        await cliente.leer("vector", "a")

    assert len([r for r in caplog.records if r.levelno == logging.WARNING]) == 2


async def test_el_conteo_en_memoria_no_se_mezcla_con_el_de_redis(cliente, motor, reloj):
    await cliente.contar([("token:x", 60)])
    motor.caido = True
    await cliente.contar([("token:x", 60)])
    motor.caido = False
    reloj.avanzar(6)

    assert await cliente.contar([("token:x", 60)]) == [(2, 54_000)]


async def test_sin_motor_lee_nada_y_cuenta_en_memoria(reloj):
    cliente = ClienteRedis(None, reloj=reloj)

    await cliente.guardar("vector", "a", b"1", 60)
    assert await cliente.leer("vector", "a") is None
    assert await cliente.contar([("ip:y", 60)]) == [(1, 60_000)]
    assert await cliente.contar([("ip:y", 60)]) == [(2, 60_000)]
    assert not cliente.con_redis
    assert not cliente.degradado


async def test_sin_motor_no_registra_nada(reloj, caplog):
    caplog.set_level(logging.DEBUG, logger="tukit_comun.cache")
    cliente = ClienteRedis(None, reloj=reloj)

    await cliente.leer("vector", "a")
    await cliente.contar([("ip:y", 60)])

    assert caplog.records == []


def test_sin_redis_url_no_hay_motor(monkeypatch):
    monkeypatch.delenv("REDIS_URL", raising=False)
    assert not cliente_desde_entorno().con_redis
    monkeypatch.setenv("REDIS_URL", "  ")
    assert not cliente_desde_entorno().con_redis


def test_sin_redis_url_no_se_importa_redis():
    raiz = Path(__file__).resolve().parents[1]
    codigo = (
        "import asyncio, sys\n"
        "from tukit_comun import cache\n"
        "cliente = cache.cliente_redis()\n"
        "asyncio.run(cliente.leer('vector', 'a'))\n"
        "asyncio.run(cliente.contar([('ip:y', 60)]))\n"
        "print('redis' in sys.modules)\n"
    )
    entorno = {k: v for k, v in os.environ.items() if k != "REDIS_URL"}
    entorno["PYTHONPATH"] = str(raiz)
    salida = subprocess.run(
        [sys.executable, "-c", codigo], env=entorno, capture_output=True, text=True, check=True
    )
    assert salida.stdout.strip() == "False"


def test_con_redis_url_y_sin_el_paquete_sigue_sin_redis(monkeypatch, caplog):
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
    monkeypatch.setitem(sys.modules, "redis", None)
    caplog.set_level(logging.WARNING, logger="tukit_comun.cache")

    cliente = cliente_desde_entorno()

    assert not cliente.con_redis
    assert "falta el paquete redis" in caplog.text


def test_con_redis_url_hay_motor(monkeypatch):
    pytest.importorskip("redis")
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
    monkeypatch.setenv("TUKIT_REDIS_ESPERA_MS", "100")

    cliente = cliente_desde_entorno()

    assert cliente.con_redis
    assert cliente._espera == pytest.approx(0.1)


def test_un_entero_mal_escrito_usa_el_de_por_omision(monkeypatch, caplog):
    monkeypatch.setenv("TUKIT_CACHE_PRUEBA", "treinta")
    assert entero_de_entorno("TUKIT_CACHE_PRUEBA", 30) == 30
    assert "TUKIT_CACHE_PRUEBA" in caplog.text
    monkeypatch.setenv("TUKIT_CACHE_PRUEBA", " 12 ")
    assert entero_de_entorno("TUKIT_CACHE_PRUEBA", 30) == 12


async def test_el_cliente_del_proceso_se_puede_cambiar(monkeypatch):
    monkeypatch.delenv("REDIS_URL", raising=False)
    doble = cliente_en_memoria()
    cache.usar_cliente(doble)
    try:
        assert cache.cliente_redis() is doble
        await cache.cerrar_cliente()
        assert cache.cliente_redis() is doble
    finally:
        cache.usar_cliente(None)
    assert cache.cliente_redis() is not doble
    cache.usar_cliente(None)


def test_main_sin_url_devuelve_2(monkeypatch, capsys):
    monkeypatch.delenv("REDIS_URL", raising=False)

    assert cache.main() == 2
    assert "Sin REDIS_URL" in capsys.readouterr().err


def test_main_con_un_redis_que_no_responde_devuelve_1_sin_la_clave(monkeypatch, capsys):
    pytest.importorskip("redis")
    monkeypatch.setenv("REDIS_URL", "redis://:secreta@127.0.0.1:1/0")

    assert cache.main(espera=1.0) == 1
    error = capsys.readouterr().err
    assert "no responde" in error
    assert "secreta" not in error
