"""NFR-MAN-01: el ensamblaje de Operacion: arranque, apagado, ciclo de vida, `main` y provision del esquema.

`api.py` solo ensambla: al arrancar crea el motor de SU base y un pool HTTP de
vida larga hacia Identidad, los cuelga de `app.state`, y al apagar los cierra;
`main` levanta uvicorn y `__main__.py` crea el esquema. Las pruebas de rutas
(`test_api_operacion.py`) inyectan el motor a mano y se saltan todo esto; aqui se
ensaya justo lo que ellas esquivan, con un motor de SQLite en memoria y un
`uvicorn.run` de mentira (ningun puerto, ninguna base real, ninguna red).

Importa porque un `_apagar` que no cierra el pool o el motor deja conexiones
abiertas en cada reinicio (la base compartida las agota), y un `__main__` que
tocara la base al importarse rompe cualquier herramienta que inspeccione el
paquete. Se comprueba tambien que la app monta el router y atiende una peticion
real durante el ciclo de vida, no solo que las funciones existan.
"""

from __future__ import annotations

import runpy
import sys
from collections.abc import AsyncIterator
from typing import Any

import httpx
import pytest
import pytest_asyncio
import uvicorn
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from tukit_comun import esquema
from tukit_comun.bd import MotorServicio
from tukit_operacion import api
from tukit_operacion.modelos import Base
from tukit_operacion.remoto import ESPERA_SEGUNDOS, ClienteIdentidad

pytestmark = pytest.mark.nfr("NFR-MAN-01")


class MotorFalso:
    """Hace de `MotorServicio`: anota como se creo, se instrumento y se cerro, en orden."""

    def __init__(self, eventos: list[str]) -> None:
        self.engine = object()
        self.eventos = eventos

    async def cerrar(self) -> None:
        self.eventos.append("motor.cerrar")


@pytest.fixture
def eventos() -> list[str]:
    return []


@pytest.fixture
def motor_falso(monkeypatch: pytest.MonkeyPatch, eventos: list[str]) -> MotorFalso:
    """Sustituye `crear_motor` e `instrumentar_motor` de `api`; deja registro de como se llamaron."""
    motor = MotorFalso(eventos)

    def crear(servicio: str) -> MotorFalso:
        eventos.append(f"crear_motor:{servicio}")
        return motor

    monkeypatch.setattr(api, "crear_motor", crear)
    monkeypatch.setattr(
        api, "instrumentar_motor", lambda engine: eventos.append(f"instrumentar:{engine is motor.engine}")
    )
    return motor


@pytest.fixture
def estado_restaurado(monkeypatch: pytest.MonkeyPatch) -> None:
    """`api.app` es un singleton: lo que el arranque cuelga de `app.state` no se queda para otras pruebas."""
    for nombre in ("motor", "pool_identidad", "identidad"):
        monkeypatch.setattr(api.app.state, nombre, None, raising=False)


class TestElArranque:
    async def test_crea_el_motor_de_operacion_lo_instrumenta_y_cuelga_los_singletons(
        self, motor_falso, eventos
    ):
        """El motor sale de `crear_motor("operacion")` (su propia base) y su engine pasa a la
        telemetria ANTES de atender; el cliente de Identidad usa el pool de vida larga."""
        aplicacion = FastAPI()

        await api._arrancar(aplicacion)
        pool = aplicacion.state.pool_identidad
        try:
            assert eventos == ["crear_motor:operacion", "instrumentar:True"]
            assert aplicacion.state.motor is motor_falso
            assert isinstance(pool, httpx.AsyncClient)
            assert pool.is_closed is False
            assert pool.timeout.read == ESPERA_SEGUNDOS
            assert isinstance(aplicacion.state.identidad, ClienteIdentidad)
            assert aplicacion.state.identidad.cliente is pool  # reutiliza conexiones, no abre una por llamada
        finally:
            await pool.aclose()

    async def test_cada_arranque_crea_su_propio_pool(self, motor_falso):
        uno, otro = FastAPI(), FastAPI()

        await api._arrancar(uno)
        await api._arrancar(otro)
        try:
            assert uno.state.pool_identidad is not otro.state.pool_identidad
        finally:
            await uno.state.pool_identidad.aclose()
            await otro.state.pool_identidad.aclose()


class TestElApagado:
    async def test_cierra_el_pool_de_identidad_y_luego_el_motor(self, motor_falso, eventos):
        """Sin esto cada reinicio deja conexiones abiertas contra Identidad y contra la base."""
        aplicacion = FastAPI()
        await api._arrancar(aplicacion)
        pool = aplicacion.state.pool_identidad
        eventos.clear()

        await api._apagar(aplicacion)

        assert pool.is_closed is True
        assert eventos == ["motor.cerrar"]


@pytest_asyncio.fixture
async def motor_sqlite(monkeypatch: pytest.MonkeyPatch) -> AsyncIterator[MotorServicio]:
    """Un `MotorServicio` real sobre SQLite en memoria, entregado por `crear_motor("operacion")`."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conexion:
        await conexion.run_sync(Base.metadata.create_all)
    motor = MotorServicio(
        servicio="operacion", engine=engine, _fabrica=async_sessionmaker(engine, expire_on_commit=False)
    )
    monkeypatch.setattr(api, "crear_motor", lambda servicio: motor)
    monkeypatch.setattr(api, "instrumentar_motor", lambda engine: None)
    yield motor
    await engine.dispose()


class TestElCicloDeVida:
    async def test_la_app_arranca_atiende_una_peticion_y_apaga_sin_dejar_nada_abierto(
        self, motor_sqlite, estado_restaurado
    ):
        async with api.app.router.lifespan_context(api.app):
            pool = api.app.state.pool_identidad
            assert api.app.state.motor is motor_sqlite
            assert pool.is_closed is False
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=api.app), base_url="http://prueba"
            ) as http:
                bandeja = await http.get("/v1/operacion/casos")

        assert bandeja.status_code == 200
        assert bandeja.json()["casos"] == []
        assert pool.is_closed is True

    def test_la_app_monta_la_lectura_y_la_escritura_de_casos(self):
        operaciones = {
            (metodo.upper(), ruta)
            for ruta, definicion in api.app.openapi()["paths"].items()
            for metodo in definicion
        }

        assert {
            ("GET", "/v1/operacion/casos"),
            ("GET", "/v1/operacion/casos/{caso_id}"),
            ("GET", "/v1/operacion/metricas"),
            ("POST", "/v1/operacion/casos"),
        } <= operaciones
        assert api.app.title == "Tukit Operacion"


class TestMain:
    @pytest.fixture
    def uvicorn_falso(self, monkeypatch: pytest.MonkeyPatch) -> list[tuple[tuple[Any, ...], dict[str, Any]]]:
        llamadas: list[tuple[tuple[Any, ...], dict[str, Any]]] = []
        monkeypatch.setattr(uvicorn, "run", lambda *a, **k: llamadas.append((a, k)))
        return llamadas

    def test_sin_argumentos_sirve_la_app_en_loopback_y_el_puerto_8015(self, uvicorn_falso):
        """El valor por omision es loopback: abrirlo a toda la red es una decision explicita."""
        assert api.main([]) == 0

        assert uvicorn_falso == [((api.app,), {"host": "127.0.0.1", "port": 8015, "log_level": "info"})]
        assert api.PUERTO_POR_OMISION == 8015

    def test_respeta_el_puerto_y_el_host_pedidos(self, uvicorn_falso):
        assert api.main(["--puerto", "9100", "--host", "0.0.0.0"]) == 0  # noqa: S104

        (_, parametros) = uvicorn_falso[0]
        assert (parametros["host"], parametros["port"]) == ("0.0.0.0", 9100)  # noqa: S104

    def test_un_puerto_que_no_es_numero_se_rechaza_sin_levantar_nada(self, uvicorn_falso, capsys):
        with pytest.raises(SystemExit) as salida:
            api.main(["--puerto", "abc"])

        assert salida.value.code == 2
        assert "--puerto" in capsys.readouterr().err
        assert uvicorn_falso == []

    def test_ejecutado_como_modulo_sale_con_el_codigo_de_main(self, uvicorn_falso, monkeypatch):
        """`python -m tukit_operacion.api`: sirve la app y termina con `SystemExit(0)`."""
        monkeypatch.setattr(sys, "argv", ["tukit_operacion.api"])

        # runpy avisa que el modulo ya estaba importado: es justo lo que se esta ensayando.
        with pytest.warns(RuntimeWarning), pytest.raises(SystemExit) as salida:
            runpy.run_module("tukit_operacion.api", run_name="__main__")

        assert salida.value.code == 0
        ((posicionales, parametros),) = uvicorn_falso
        assert parametros == {"host": "127.0.0.1", "port": 8015, "log_level": "info"}
        assert posicionales[0].title == "Tukit Operacion"


class TestLaProvisionDelEsquema:
    @pytest.fixture
    def materializar_falso(self, monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, Any]]:
        llamadas: list[tuple[str, Any]] = []
        monkeypatch.setattr(esquema, "materializar", lambda servicio, base: llamadas.append((servicio, base)))
        return llamadas

    def test_python_m_tukit_operacion_crea_el_esquema_del_servicio_operacion(self, materializar_falso):
        runpy.run_module("tukit_operacion.__main__", run_name="__main__")

        assert materializar_falso == [("operacion", Base)]

    def test_importar_el_modulo_no_toca_la_base(self, materializar_falso):
        """Sin la guarda `__main__`, cualquier herramienta que importe el paquete crearia tablas."""
        runpy.run_module("tukit_operacion.__main__", run_name="tukit_operacion.importado")

        assert materializar_falso == []
