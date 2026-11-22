"""NFR-MAN-01: el arranque de Comercio: ciclo de vida de la app, CLI de la API y provision del esquema.

Los demas tests inyectan `app.state` a mano y nunca disparan el `lifespan`; por eso nadie ejercia
el ensamblado real. Aqui se ejerce lo que ocurre en el despliegue y, si se rompe, deja el servicio
caido o a medio cablear sin que ninguna prueba de rutas lo note:

- `_arrancar`/`_apagar`: el motor sale del entorno, la pasarela de `WOMPI_MODO` (falsa por omision:
  nunca cobra de verdad sin querer), el cliente de Catalogo cuelga de un pool acotado, y al apagar
  se cierra el pool y se libera el motor.
- `main`: uvicorn escucha en 127.0.0.1:8014 por omision (no se expone a la red sin pedirlo).
- `python -m tukit_comercio`: provisiona el esquema completo en la base del entorno.

Sin red ni procesos: `uvicorn.run` se reemplaza por un espia, la base es SQLite en memoria o en un
archivo de `tmp_path`, y el estado de la app compartida se restaura al terminar cada prueba.
"""

from __future__ import annotations

import runpy
import sys

import httpx
import pytest
import uvicorn
from sqlalchemy import inspect
from sqlalchemy.ext.asyncio import create_async_engine
from tukit_comercio import api
from tukit_comercio.api import PUERTO_POR_OMISION, app
from tukit_comercio.modelos import Base
from tukit_comercio.pasarela import PasarelaFalsa
from tukit_comercio.remoto import ESPERA_SEGUNDOS, ClienteCatalogo
from tukit_comun.bd import MotorServicio

pytestmark = pytest.mark.nfr("NFR-MAN-01")


@pytest.fixture(autouse=True)
def estado_de_la_app_restaurado(monkeypatch) -> None:
    """El `app` es un singleton de modulo que otras pruebas pueblan: se devuelve como estaba."""
    for nombre in ("motor", "pasarela", "catalogo", "pool_catalogo"):
        monkeypatch.setattr(app.state, nombre, getattr(app.state, nombre, None), raising=False)


@pytest.fixture
def entorno_de_arranque(monkeypatch) -> None:
    monkeypatch.setenv("TUKIT_COMERCIO_DB_URL", "sqlite+aiosqlite:///:memory:")
    monkeypatch.delenv("WOMPI_MODO", raising=False)
    monkeypatch.delenv("OTEL_EXPORTER_OTLP_ENDPOINT", raising=False)


# --- el ciclo de vida ---------------------------------------------------------------------------


async def test_el_arranque_cablea_motor_pasarela_falsa_y_catalogo_con_pool(monkeypatch, entorno_de_arranque):
    """Al arrancar, la app cuelga motor, pasarela y cliente de Catalogo; sin `WOMPI_MODO` la pasarela
    es la falsa (jamas Wompi por accidente) y el cliente de Catalogo usa el pool con la espera acotada."""
    instrumentados: list[object] = []
    monkeypatch.setattr(api, "instrumentar_motor", instrumentados.append)

    async with app.router.lifespan_context(app):
        motor = app.state.motor
        assert isinstance(motor, MotorServicio)
        assert motor.servicio == "comercio"
        assert instrumentados == [motor.engine]  # el motor se instrumenta para trazas
        assert isinstance(app.state.pasarela, PasarelaFalsa)
        assert isinstance(app.state.catalogo, ClienteCatalogo)
        assert app.state.catalogo.cliente is app.state.pool_catalogo
        assert app.state.pool_catalogo.timeout.read == ESPERA_SEGUNDOS
        assert app.state.pool_catalogo.is_closed is False

        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://prueba"
        ) as http:
            listo = await http.get("/health/ready")
        assert listo.status_code == 200
        assert listo.json() == {"estado": "listo", "servicio": "Tukit Comercio"}


async def test_el_apagado_cierra_el_pool_y_libera_el_motor(monkeypatch, entorno_de_arranque):
    """Sin esto cada reinicio filtra conexiones: el pool hacia Catalogo se cierra y el motor se libera."""
    cerrados: list[str] = []
    crear_motor_real = api.crear_motor

    def _crear_motor_espiado(servicio: str) -> MotorServicio:
        motor = crear_motor_real(servicio)
        cerrar_real = motor.cerrar

        async def _cerrar() -> None:
            cerrados.append(servicio)
            await cerrar_real()

        motor.cerrar = _cerrar  # type: ignore[method-assign]
        return motor

    monkeypatch.setattr(api, "crear_motor", _crear_motor_espiado)

    async with app.router.lifespan_context(app):
        pool = app.state.pool_catalogo
        assert cerrados == []

    assert pool.is_closed is True
    assert cerrados == ["comercio"]


async def test_el_apagado_ocurre_aunque_la_aplicacion_falle_en_marcha(monkeypatch, entorno_de_arranque):
    """El `finally` del ciclo de vida: una excepcion en marcha no deja el pool abierto."""

    class FalloEnMarcha(Exception):
        pass

    pools: list[httpx.AsyncClient] = []
    with pytest.raises(FalloEnMarcha):
        async with app.router.lifespan_context(app):
            pools.append(app.state.pool_catalogo)
            raise FalloEnMarcha

    assert pools[0].is_closed is True


# --- la CLI de la API ---------------------------------------------------------------------------


def _espiar_uvicorn(monkeypatch) -> list[tuple[tuple, dict]]:
    llamadas: list[tuple[tuple, dict]] = []
    monkeypatch.setattr(uvicorn, "run", lambda *args, **kwargs: llamadas.append((args, kwargs)))
    return llamadas


def test_main_sin_argumentos_escucha_solo_en_localhost_en_el_puerto_8014(monkeypatch):
    llamadas = _espiar_uvicorn(monkeypatch)

    assert api.main([]) == 0

    assert PUERTO_POR_OMISION == 8014
    assert llamadas == [((app,), {"host": "127.0.0.1", "port": 8014, "log_level": "info"})]


def test_main_respeta_host_y_puerto_pedidos(monkeypatch):
    llamadas = _espiar_uvicorn(monkeypatch)

    assert api.main(["--puerto", "9100", "--host", "0.0.0.0"]) == 0

    assert llamadas == [((app,), {"host": "0.0.0.0", "port": 9100, "log_level": "info"})]


def test_main_rechaza_un_puerto_que_no_es_numero_sin_levantar_nada(monkeypatch):
    llamadas = _espiar_uvicorn(monkeypatch)

    with pytest.raises(SystemExit) as salida:
        api.main(["--puerto", "ocho-mil"])

    assert salida.value.code == 2
    assert llamadas == []


@pytest.mark.filterwarnings("ignore:.*found in sys.modules.*:RuntimeWarning")
def test_python_m_api_sale_con_el_codigo_de_main(monkeypatch):
    """`python -m tukit_comercio.api`: el punto de entrada levanta uvicorn y termina con `SystemExit(0)`."""
    llamadas = _espiar_uvicorn(monkeypatch)
    monkeypatch.setattr(sys, "argv", ["tukit_comercio.api", "--puerto", "9200"])

    with pytest.raises(SystemExit) as salida:
        runpy.run_module("tukit_comercio.api", run_name="__main__")

    assert salida.value.code == 0
    assert len(llamadas) == 1
    assert llamadas[0][1] == {"host": "127.0.0.1", "port": 9200, "log_level": "info"}


# --- la provision del esquema (`python -m tukit_comercio`) --------------------------------------


@pytest.mark.filterwarnings("ignore:.*found in sys.modules.*:RuntimeWarning")
async def test_python_m_comercio_materializa_todas_las_tablas_en_la_base_del_entorno(
    tmp_path, monkeypatch, capsys
):
    """La provision crea cada tabla del modelo en la base de `TUKIT_COMERCIO_DB_URL` y reporta cuantas.

    Se corre en un hilo aparte porque `materializar` abre su propio bucle de eventos."""
    import asyncio

    url = f"sqlite+aiosqlite:///{tmp_path / 'comercio.db'}"
    monkeypatch.setenv("TUKIT_COMERCIO_DB_URL", url)

    await asyncio.to_thread(runpy.run_module, "tukit_comercio", run_name="__main__")

    esperadas = set(Base.metadata.tables)
    assert {"pedido", "linea_pedido", "pago", "envio", "devolucion", "reserva_inventario"} <= esperadas
    assert capsys.readouterr().out == (
        f"[comercio] esquema materializado: {len(esperadas)} tablas en tukit_comercio\n"
    )
    engine = create_async_engine(url)
    try:
        async with engine.connect() as conexion:
            creadas = await conexion.run_sync(lambda c: set(inspect(c).get_table_names()))
    finally:
        await engine.dispose()
    assert creadas == esperadas
