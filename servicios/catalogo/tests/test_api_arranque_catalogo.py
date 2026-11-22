"""NFR-MAN-01: el ensamblado de `api.py`: ciclo de vida del motor, rutas montadas y arranque por CLI.

`api.py` casi no tiene logica, pero es donde se cablea lo que, si falla, tumba el
servicio entero sin que ninguna prueba de ruta lo note: un motor que no se crea
al arrancar (todas las rutas darian 500 al primer pedido), uno que no se cierra
al apagar (conexiones colgadas) o una CLI que arranca la `app` equivocada.

Lo que se ata:

  - el arranque crea el motor DEL SERVICIO `catalogo`, lo cuelga de `app.state` y
    lo instrumenta; el apagado lo cierra;
  - la misma `app` monta la lectura (`/v1/catalogo`, `/v1/listas`) y la revision
    (`/v1/admin`), y `admin_http` (el puente historico) ve el mismo motor y el
    mismo router;
  - `main` levanta uvicorn con la CADENA de importacion `tukit_catalogo.api:app`
    (no el objeto): con `python -m` el modulo seria `__main__` y habria dos
    `app`, una sin lifespan (de ahi el 500 en `/v1/admin/*`).

Nada abre un puerto ni una base real: `crear_motor` y `uvicorn.run` son dobles.
"""

from __future__ import annotations

import importlib
import runpy

import pytest
import uvicorn
from fastapi import FastAPI
from tukit_catalogo import admin_http, api
from tukit_catalogo.routers import admin as routers_admin

pytestmark = pytest.mark.nfr("NFR-MAN-01")


class _MotorFalso:
    """Un motor de mentira que solo recuerda si se le pidio cerrar."""

    def __init__(self) -> None:
        self.engine = object()
        self.cerrado = False

    async def cerrar(self) -> None:
        self.cerrado = True


@pytest.fixture()
def motor_falso(monkeypatch):
    """Sustituye `crear_motor` e `instrumentar_motor` de `api` y deja un registro de como se llamaron."""
    motor = _MotorFalso()
    motor.pedidos: list[str] = []
    motor.instrumentados: list[object] = []

    def crear(servicio):
        motor.pedidos.append(servicio)
        return motor

    monkeypatch.setattr(api, "crear_motor", crear)
    monkeypatch.setattr(api, "instrumentar_motor", motor.instrumentados.append)
    return motor


async def test_el_arranque_crea_el_motor_del_servicio_catalogo_y_lo_instrumenta(motor_falso):
    """El motor sale de `crear_motor("catalogo")` (su propia base) y su engine se entrega a la telemetria."""
    aplicacion = FastAPI()

    await api._arrancar(aplicacion)

    assert aplicacion.state.motor is motor_falso
    assert motor_falso.pedidos == ["catalogo"]
    assert motor_falso.instrumentados == [motor_falso.engine]
    assert motor_falso.cerrado is False


async def test_el_apagado_cierra_el_motor_que_dejo_el_arranque(motor_falso):
    """Apagar libera el pool: sin esto cada reinicio deja conexiones abiertas contra la base."""
    aplicacion = FastAPI()
    await api._arrancar(aplicacion)

    await api._apagar(aplicacion)

    assert motor_falso.cerrado is True


async def test_el_lifespan_de_la_app_arranca_y_apaga_el_motor(motor_falso, monkeypatch):
    """Por el ciclo de vida real de la `app`: durante el servicio hay motor y al salir queda cerrado."""
    monkeypatch.setattr(api.app.state, "motor", None, raising=False)

    async with api.app.router.lifespan_context(api.app):
        assert api.app.state.motor is motor_falso
        assert motor_falso.cerrado is False

    assert motor_falso.cerrado is True
    assert motor_falso.pedidos == ["catalogo"]


def test_la_app_monta_la_lectura_y_la_revision_sobre_el_mismo_motor():
    """Lectura, listas, revision (`/v1/admin`) e internas viven en la misma `app`, la que atiende."""
    publicas = set(api.app.openapi()["paths"])
    assert {"/v1/catalogo/conceptos", "/v1/listas"} <= publicas
    assert {"/v1/admin/listas", "/v1/admin/catalogo/propuestas"} <= publicas
    # Las rutas internas no figuran en el esquema publico, pero la app las sirve.
    assert not any(ruta.startswith("/interno") for ruta in publicas)
    assert api.app.url_path_for("resolver_sku", sku="TK-C001-ECO") == "/interno/resolver-sku/TK-C001-ECO"
    # El puente historico expone el mismo router y la misma funcion de motor que las rutas montadas.
    assert admin_http.router is routers_admin.router
    assert admin_http._motor is routers_admin._motor


def test_el_motor_de_la_revision_es_el_de_la_app_canonica(monkeypatch):
    """`/v1/admin` busca su motor en `tukit_catalogo.api.app`: si el motor se cuelga de otra `app`, da 500."""
    sentinela = _MotorFalso()
    monkeypatch.setattr(api.app.state, "motor", sentinela, raising=False)
    assert routers_admin._motor() is sentinela


def test_main_arranca_uvicorn_por_cadena_de_importacion_y_con_los_valores_por_omision(monkeypatch):
    """Sin argumentos: `127.0.0.1:8012`, y el objetivo es el TEXTO `tukit_catalogo.api:app`, no el objeto."""
    llamadas: list[tuple[tuple, dict]] = []
    monkeypatch.setattr(uvicorn, "run", lambda *a, **k: llamadas.append((a, k)))

    assert api.main([]) == 0

    assert llamadas == [
        (("tukit_catalogo.api:app",), {"host": "127.0.0.1", "port": 8012, "log_level": "info"})
    ]
    modulo, _, atributo = llamadas[0][0][0].partition(":")
    assert getattr(importlib.import_module(modulo), atributo) is api.app
    assert api.PUERTO_POR_OMISION == 8012


def test_main_respeta_el_puerto_y_el_host_pedidos(monkeypatch):
    llamadas: list[dict] = []
    monkeypatch.setattr(uvicorn, "run", lambda *a, **k: llamadas.append(k))

    assert api.main(["--puerto", "9100", "--host", "0.0.0.0"]) == 0

    assert (llamadas[0]["host"], llamadas[0]["port"]) == ("0.0.0.0", 9100)


def test_main_con_un_puerto_que_no_es_numero_falla_sin_levantar_nada(monkeypatch, capsys):
    """argparse rechaza `--puerto abc` con salida 2 y mensaje; uvicorn no se llega a invocar."""
    llamadas: list[object] = []
    monkeypatch.setattr(uvicorn, "run", lambda *a, **k: llamadas.append(a))

    with pytest.raises(SystemExit) as salida:
        api.main(["--puerto", "abc"])

    assert salida.value.code == 2
    assert "--puerto" in capsys.readouterr().err
    assert llamadas == []


def test_ejecutar_el_modulo_como_programa_sale_con_el_codigo_de_main(monkeypatch):
    """`python -m tukit_catalogo.api` termina con `SystemExit(0)` tras pedirle a uvicorn que sirva la app."""
    llamadas: list[tuple] = []
    monkeypatch.setattr(uvicorn, "run", lambda *a, **k: llamadas.append(a))
    monkeypatch.setattr("sys.argv", ["tukit_catalogo.api"])

    # runpy avisa que el modulo ya estaba importado: es justo lo que se esta ensayando.
    with pytest.warns(RuntimeWarning), pytest.raises(SystemExit) as salida:
        runpy.run_module("tukit_catalogo.api", run_name="__main__")

    assert salida.value.code == 0
    assert llamadas == [("tukit_catalogo.api:app",)]
