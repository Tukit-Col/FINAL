"""NFR-MAN-01: el arranque, el apagado y los puntos de entrada de la API de Identidad.

`api.py` solo ensambla (router + motor), pero ese ensamblado es donde un
servicio se cae en silencio o se expone de mas. Las pruebas de rutas montan su
propio motor y nunca pasan por el ciclo de vida real, asi que aqui se fija:

- el arranque ata `app.state.motor` al servicio `identidad` y a la URL del
  entorno (`TUKIT_IDENTIDAD_DB_URL`), instrumenta ese mismo motor y el apagado
  lo cierra, incluso si el cuerpo de la aplicacion falla;
- `/health/ready` prueba la base que el arranque abrio: 200 si responde, 503 con
  el detalle si no (un orquestador no debe mandar trafico a una API sin base);
- `main` levanta `uvicorn` con la app de Identidad, en `127.0.0.1:8011` por
  omision (NO expuesta a la red salvo que se pida con `--host`), y respeta
  `--puerto` y `--host`; `uvicorn.run` se sustituye: no se abre ningun puerto;
- `python -m tukit_identidad` provisiona el esquema completo y lo reporta;
- una llave de sesion de desarrollo debe avisar AL ARRANCAR (H-C-06): hoy el
  aviso solo sale la primera vez que se firma o se lee un token.

Las bases son archivos SQLite temporales; no hay Postgres ni red. Datos ficticios.
"""

from __future__ import annotations

import runpy
import sys
import uuid
from pathlib import Path
from typing import Any

import httpx
import pytest
import uvicorn
from fastapi import FastAPI
from sqlalchemy import create_engine, insert, inspect
from tukit_comun.bd import MotorServicio
from tukit_identidad import api as modulo_api
from tukit_identidad.api import PUERTO_POR_OMISION, app, main
from tukit_identidad.dominio import sesiones
from tukit_identidad.modelos import Base, Colegio

pytestmark = pytest.mark.nfr("NFR-MAN-01")


@pytest.fixture
def base_sqlite(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Un archivo SQLite con el esquema y UN colegio ficticio, elegido por la
    variable de entorno que lee el arranque. `app.state.motor` se restaura al
    terminar, porque `app` es un objeto global compartido con otras pruebas."""
    ruta = tmp_path / "identidad.db"
    monkeypatch.setenv("TUKIT_IDENTIDAD_DB_URL", f"sqlite+aiosqlite:///{ruta}")
    monkeypatch.setattr(app.state, "motor", None, raising=False)
    motor = create_engine(f"sqlite:///{ruta}")
    Base.metadata.create_all(motor)
    with motor.begin() as conexion:
        conexion.execute(insert(Colegio.__table__).values(id=uuid.uuid4(), nombre="COLEGIO FICTICIO UNO"))
    motor.dispose()
    return ruta


@pytest.fixture
def cerrados(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Registra cada `MotorServicio.cerrar` (y lo ejecuta de verdad)."""
    registro: list[str] = []
    original = MotorServicio.cerrar

    async def espia(self: MotorServicio) -> None:
        registro.append(self.servicio)
        await original(self)

    monkeypatch.setattr(MotorServicio, "cerrar", espia)
    return registro


class TestEnsamblado:
    def test_la_app_monta_el_router_de_identidad_y_las_sondas(self):
        rutas = set(app.openapi()["paths"])

        assert app.title == "Tukit Identidad"
        assert {"/v1/colegios", "/v1/sesiones", "/v1/cuenta", "/v1/admin/acudientes"} <= rutas
        assert {"/health/live", "/health/ready"} <= rutas


class TestCicloDeVida:
    async def test_el_arranque_ata_el_motor_de_identidad_a_la_url_del_entorno_y_el_apagado_lo_cierra(
        self, base_sqlite: Path, cerrados: list[str]
    ):
        async with app.router.lifespan_context(app):
            motor = app.state.motor
            assert isinstance(motor, MotorServicio)
            assert motor.servicio == "identidad"
            assert motor.engine.url.database == str(base_sqlite)
            assert cerrados == []  # sigue abierto mientras la app atiende

        assert cerrados == ["identidad"]

    async def test_el_motor_del_arranque_sirve_la_base_del_entorno(self, base_sqlite: Path):
        async with (
            app.router.lifespan_context(app),
            httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://prueba") as http,
        ):
            respuesta = await http.get("/v1/colegios")

        assert respuesta.status_code == 200
        cuerpo = respuesta.json()
        assert cuerpo["total"] == 1
        assert cuerpo["colegios"][0]["nombre"] == "COLEGIO FICTICIO UNO"

    async def test_el_arranque_instrumenta_el_mismo_motor_que_deja_en_el_estado(
        self, base_sqlite: Path, monkeypatch: pytest.MonkeyPatch
    ):
        instrumentados: list[Any] = []
        monkeypatch.setattr(modulo_api, "instrumentar_motor", instrumentados.append)

        async with app.router.lifespan_context(app):
            assert instrumentados == [app.state.motor.engine]

    async def test_el_apagado_cierra_el_motor_aunque_la_aplicacion_falle(
        self, base_sqlite: Path, cerrados: list[str]
    ):
        with pytest.raises(RuntimeError, match="fallo de la aplicacion"):
            async with app.router.lifespan_context(app):
                raise RuntimeError("fallo de la aplicacion")

        assert cerrados == ["identidad"]

    async def test_ready_responde_200_si_la_base_del_arranque_contesta(self, base_sqlite: Path):
        async with (
            app.router.lifespan_context(app),
            httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://prueba") as http,
        ):
            respuesta = await http.get("/health/ready")

        assert respuesta.status_code == 200
        assert respuesta.json() == {"estado": "listo", "servicio": "Tukit Identidad"}

    async def test_ready_responde_503_con_el_detalle_si_la_base_no_se_puede_abrir(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        """La URL apunta a un directorio que no existe: el arranque no falla
        (el motor es perezoso), pero la sonda de readiness si lo nota."""
        monkeypatch.setattr(app.state, "motor", None, raising=False)
        monkeypatch.setenv(
            "TUKIT_IDENTIDAD_DB_URL", f"sqlite+aiosqlite:///{tmp_path / 'no_existe' / 'identidad.db'}"
        )

        async with (
            app.router.lifespan_context(app),
            httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://prueba") as http,
        ):
            respuesta = await http.get("/health/ready")
            viva = await http.get("/health/live")

        assert respuesta.status_code == 503
        cuerpo = respuesta.json()
        assert cuerpo["estado"] == "no_listo"
        assert cuerpo["detalle"]
        # Liveness no toca la base: un proceso sano no se reinicia por una base caida.
        assert viva.status_code == 200
        assert viva.json()["estado"] == "vivo"

    @pytest.mark.xfail(
        strict=True,
        reason=(
            "H-C-06: sin TUKIT_LLAVE_SESION el arranque no avisa que firma con la llave publica de "
            "desarrollo; el docstring promete 'SE AVISA en cada arranque' (sesiones.py:21-23, :40-41) "
            "pero api.py:27-29 no la consulta y el aviso solo sale al firmar/leer el primer token"
        ),
    )
    async def test_arrancar_sin_llave_de_sesion_avisa_en_el_arranque_no_al_primer_token(
        self,
        base_sqlite: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
        caplog: pytest.LogCaptureFixture,
    ):
        """Quien despliega sin `TUKIT_LLAVE_SESION` obtiene tokens firmables por
        cualquiera que lea el repositorio, y hoy no se entera hasta que alguien
        inicia sesion (si es que mira la salida estandar)."""
        monkeypatch.delenv(sesiones.VARIABLE_LLAVE, raising=False)

        async with app.router.lifespan_context(app):
            pass

        capturado = capsys.readouterr()
        avisos = capturado.out + capturado.err + caplog.text
        assert sesiones.VARIABLE_LLAVE in avisos


class TestMain:
    @pytest.fixture
    def uvicorn_falso(self, monkeypatch: pytest.MonkeyPatch) -> list[tuple[tuple, dict]]:
        llamadas: list[tuple[tuple, dict]] = []
        monkeypatch.setattr(uvicorn, "run", lambda *args, **kwargs: llamadas.append((args, kwargs)))
        return llamadas

    def test_por_omision_escucha_solo_en_localhost_en_el_8011(self, uvicorn_falso: list):
        assert main([]) == 0

        [(args, kwargs)] = uvicorn_falso
        assert args == (app,)
        assert kwargs == {"host": "127.0.0.1", "port": 8011, "log_level": "info"}
        assert PUERTO_POR_OMISION == 8011

    def test_puerto_y_host_se_pueden_cambiar(self, uvicorn_falso: list):
        assert main(["--puerto", "9100", "--host", "0.0.0.0"]) == 0

        [(_, kwargs)] = uvicorn_falso
        assert (kwargs["host"], kwargs["port"]) == ("0.0.0.0", 9100)

    def test_un_puerto_que_no_es_numero_lo_rechaza_el_analizador_sin_levantar_nada(self, uvicorn_falso: list):
        with pytest.raises(SystemExit) as salida:
            main(["--puerto", "abc"])

        assert salida.value.code == 2
        assert uvicorn_falso == []

    def test_ejecutado_como_script_levanta_uvicorn_y_sale_con_0(
        self, uvicorn_falso: list, monkeypatch: pytest.MonkeyPatch
    ):
        monkeypatch.delitem(sys.modules, "tukit_identidad.api")
        monkeypatch.setattr(sys, "argv", ["api", "--puerto", "9200"])

        with pytest.raises(SystemExit) as salida:
            runpy.run_module("tukit_identidad.api", run_name="__main__")

        assert salida.value.code == 0
        [(args, kwargs)] = uvicorn_falso
        assert isinstance(args[0], FastAPI)
        assert kwargs["port"] == 9200
        assert "/v1/colegios" in args[0].openapi()["paths"]


class TestProvisionDelEsquema:
    """`python -m tukit_identidad`: crea todas las tablas en la base del entorno."""

    def test_crea_el_esquema_completo_y_reporta_cuantas_tablas(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ):
        ruta = tmp_path / "vacia.db"
        monkeypatch.setenv("TUKIT_IDENTIDAD_DB_URL", f"sqlite+aiosqlite:///{ruta}")
        monkeypatch.delitem(sys.modules, "tukit_identidad.__main__", raising=False)

        runpy.run_module("tukit_identidad", run_name="__main__")

        motor = create_engine(f"sqlite:///{ruta}")
        try:
            tablas = set(inspect(motor).get_table_names())
        finally:
            motor.dispose()
        assert tablas == set(Base.metadata.tables)
        assert {"usuario", "colegio", "asignacion_rol", "acudiente_matricula"} <= tablas
        assert (
            f"[identidad] esquema materializado: {len(Base.metadata.tables)} tablas en tukit_identidad"
            in capsys.readouterr().out
        )

    def test_correrlo_dos_veces_es_inocuo(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        ruta = tmp_path / "dos_veces.db"
        monkeypatch.setenv("TUKIT_IDENTIDAD_DB_URL", f"sqlite+aiosqlite:///{ruta}")

        runpy.run_module("tukit_identidad", run_name="__main__")
        runpy.run_module("tukit_identidad", run_name="__main__")

        motor = create_engine(f"sqlite:///{ruta}")
        try:
            assert set(inspect(motor).get_table_names()) == set(Base.metadata.tables)
        finally:
            motor.dispose()

    def test_importar_el_paquete_sin_ejecutarlo_no_toca_ninguna_base(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        """La provision solo corre bajo `__main__`: importar el modulo no crea nada."""
        ruta = tmp_path / "no_debe_existir.db"
        monkeypatch.setenv("TUKIT_IDENTIDAD_DB_URL", f"sqlite+aiosqlite:///{ruta}")

        runpy.run_module("tukit_identidad", run_name="no_es_main")

        assert not ruta.exists()
