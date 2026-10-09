"""NFR-MAN-01: el arranque HTTP compartido por los servicios (`http.py`, `crear_app`).

`test_http.py` fija el sobre de error, la correlacion basica y las sondas. Aqui
se cierran los bordes que quedaban: el ciclo de vida (`al_arrancar` antes de
atender, `al_apagar` siempre), la sonda de readiness con una base viva, el CORS
frente a un origen NO permitido y frente a la lista de produccion, las formas de
error de validacion sin campo identificable, y la propagacion de la correlacion
hacia las llamadas salientes.

Importa porque este modulo es lo unico que los cinco servicios y el gateway
comparten en su borde: un `al_apagar` que no corre deja conexiones colgadas, un
CORS abierto de mas expone la API a cualquier sitio, y un id de correlacion que
se acepta sin validar termina en cada linea de log y en cada llamada saliente.
Se caracteriza ademas un defecto conocido (H-C-09): la cabecera
`x-correlation-id` entrante no se sanea.
"""

from __future__ import annotations

import re

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy.orm import DeclarativeBase
from tukit_comun.bd import sesion_de_prueba
from tukit_comun.http import (
    CABECERA_CORRELACION,
    ErrorDominio,
    _sellar_correlacion,
    cliente_efimero,
    crear_app,
    crear_pool,
    fijar_correlacion,
    id_de_correlacion,
    reset_correlacion,
)

pytestmark = pytest.mark.nfr("NFR-MAN-01")


class _Base(DeclarativeBase):
    pass


async def _pedir(app: FastAPI, metodo: str, ruta: str, **kw) -> httpx.Response:
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://prueba") as cliente:
        return await cliente.request(metodo, ruta, **kw)


class TestElCicloDeVida:
    async def test_arrancar_corre_antes_de_atender_y_apagar_al_final_con_la_misma_app(self):
        eventos: list[tuple[str, FastAPI]] = []

        async def arrancar(app: FastAPI) -> None:
            eventos.append(("arrancar", app))

        async def apagar(app: FastAPI) -> None:
            eventos.append(("apagar", app))

        app = crear_app(titulo="Prueba", descripcion="banco", al_arrancar=arrancar, al_apagar=apagar)

        async with app.router.lifespan_context(app):
            assert [nombre for nombre, _ in eventos] == ["arrancar"]  # antes de la primera peticion
            assert (await _pedir(app, "GET", "/salud")).status_code == 200

        assert [nombre for nombre, _ in eventos] == ["arrancar", "apagar"]
        assert all(app_recibida is app for _, app_recibida in eventos)

    async def test_el_motor_colgado_en_el_arranque_es_visible_para_la_sonda_de_readiness(self):
        """El `al_arrancar` de cada servicio cuelga el motor en `app.state`; la
        sonda lo encuentra ahi y prueba la base real."""
        motor = sesion_de_prueba(_Base)

        async def arrancar(app: FastAPI) -> None:
            app.state.motor = motor

        async def apagar(app: FastAPI) -> None:
            await app.state.motor.cerrar()

        app = crear_app(
            titulo="Servicio Ficticio", descripcion="banco", al_arrancar=arrancar, al_apagar=apagar
        )

        async with app.router.lifespan_context(app):
            respuesta = await _pedir(app, "GET", "/health/ready")

        assert respuesta.status_code == 200
        assert respuesta.json() == {"estado": "listo", "servicio": "Servicio Ficticio"}

    async def test_el_apagado_corre_aunque_el_servicio_termine_con_error(self):
        apagado: list[str] = []

        async def apagar(app: FastAPI) -> None:
            apagado.append("cerrado")

        app = crear_app(titulo="Prueba", descripcion="banco", al_apagar=apagar)

        with pytest.raises(RuntimeError, match="se cae el proceso"):
            async with app.router.lifespan_context(app):
                raise RuntimeError("se cae el proceso")

        assert apagado == ["cerrado"]

    async def test_sin_ganchos_el_ciclo_de_vida_no_hace_nada(self):
        app = crear_app(titulo="Prueba", descripcion="banco")

        async with app.router.lifespan_context(app):
            assert (await _pedir(app, "GET", "/salud")).json()["estado"] == "ok"


class TestLaVersionYElTituloLlegaAlaSonda:
    async def test_una_version_propia_sale_en_la_sonda_y_en_el_esquema(self):
        app = crear_app(titulo="Servicio Ficticio", descripcion="banco", version="2.7")

        assert (await _pedir(app, "GET", "/salud")).json() == {
            "estado": "ok",
            "servicio": "Servicio Ficticio",
            "version": "2.7",
        }
        assert app.version == "2.7"
        assert app.title == "Servicio Ficticio"

    async def test_liveness_nombra_al_servicio_sin_tocar_base(self):
        app = crear_app(titulo="Servicio Ficticio", descripcion="banco")

        assert (await _pedir(app, "GET", "/health/live")).json() == {
            "estado": "vivo",
            "servicio": "Servicio Ficticio",
        }


class TestElSobreDeErrorEnLosBordes:
    async def test_un_error_de_dominio_con_otro_estado_conserva_el_codigo_y_omite_el_campo_ausente(self):
        app = crear_app(titulo="Prueba", descripcion="banco")

        @app.get("/conflicto")
        async def conflicto() -> dict:
            raise ErrorDominio("lista_ya_publicada", "Ya estaba publicada.", estado=409)

        respuesta = await _pedir(app, "GET", "/conflicto")

        assert respuesta.status_code == 409
        assert respuesta.json() == {"error": "lista_ya_publicada", "mensaje": "Ya estaba publicada."}

    async def test_un_parametro_de_consulta_invalido_nombra_el_campo_y_no_devuelve_el_valor(self):
        app = crear_app(titulo="Prueba", descripcion="banco")

        @app.get("/pagina")
        async def pagina(n: int) -> dict:
            return {"n": n}

        respuesta = await _pedir(app, "GET", "/pagina", params={"n": "valor-secreto"})

        assert respuesta.status_code == 400
        assert respuesta.json()["campo"] == "n"
        assert "valor-secreto" not in respuesta.text

    async def test_sin_cuerpo_el_error_sigue_siendo_400_y_no_inventa_un_campo(self):
        """Cuando falta el cuerpo entero no hay un campo que senalar: se omite la
        clave en vez de mandar una cadena vacia."""
        app = crear_app(titulo="Prueba", descripcion="banco")

        @app.post("/eco")
        async def eco(datos: dict) -> dict:
            return datos

        respuesta = await _pedir(app, "POST", "/eco")

        assert respuesta.status_code == 400
        cuerpo = respuesta.json()
        assert cuerpo["error"] == "entrada_invalida"
        assert "campo" not in cuerpo


class TestElCorsNoSeAbreDeMas:
    async def test_un_origen_no_listado_no_recibe_permiso(self):
        app = crear_app(titulo="Prueba", descripcion="banco")

        respuesta = await _pedir(app, "GET", "/salud", headers={"Origin": "https://sitio-ajeno.example.test"})

        assert respuesta.status_code == 200  # el servidor responde; el NAVEGADOR no entrega el cuerpo
        assert "access-control-allow-origin" not in respuesta.headers

    async def test_la_lista_de_produccion_reemplaza_la_de_desarrollo(self, monkeypatch):
        monkeypatch.setenv("TUKIT_CORS_ORIGENES", "https://tukit.example.test")
        app = crear_app(titulo="Prueba", descripcion="banco")

        propio = await _pedir(app, "GET", "/salud", headers={"Origin": "https://tukit.example.test"})
        desarrollo = await _pedir(app, "GET", "/salud", headers={"Origin": "http://localhost:3000"})

        assert propio.headers["access-control-allow-origin"] == "https://tukit.example.test"
        assert "access-control-allow-origin" not in desarrollo.headers

    async def test_la_precarga_de_un_origen_permitido_autoriza_metodo_y_credenciales(self):
        app = crear_app(titulo="Prueba", descripcion="banco")

        respuesta = await _pedir(
            app,
            "OPTIONS",
            "/salud",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "x-correlation-id",
            },
        )

        assert respuesta.status_code == 200
        assert respuesta.headers["access-control-allow-origin"] == "http://localhost:3000"
        assert respuesta.headers["access-control-allow-credentials"] == "true"
        assert "POST" in respuesta.headers["access-control-allow-methods"]


class TestLaCorrelacionHaciaLasSalientes:
    async def test_el_cliente_efimero_lleva_el_id_de_la_peticion_en_curso(self):
        token = fijar_correlacion("req-saliente")
        try:
            async with cliente_efimero(None, 5.0) as propio:
                assert propio.headers[CABECERA_CORRELACION] == "req-saliente"
        finally:
            reset_correlacion(token)

    async def test_el_cliente_inyectado_no_se_toca_aunque_haya_correlacion(self):
        """Las pruebas inyectan su propio cliente: el CM no le mete cabeceras."""
        inyectado = httpx.AsyncClient()
        token = fijar_correlacion("req-saliente")
        try:
            async with cliente_efimero(inyectado, 5.0) as usado:
                assert CABECERA_CORRELACION not in usado.headers
        finally:
            reset_correlacion(token)
            await inyectado.aclose()

    async def test_el_hook_del_pool_no_pisa_una_cabecera_que_el_llamante_ya_puso(self):
        pool = crear_pool(espera=5.0)
        try:
            peticion = pool.build_request("GET", "http://x/ping", headers={CABECERA_CORRELACION: "explicito"})
            token = fijar_correlacion("del-contexto")
            try:
                await _sellar_correlacion(peticion)
            finally:
                reset_correlacion(token)
            assert peticion.headers[CABECERA_CORRELACION] == "explicito"
        finally:
            await pool.aclose()

    async def test_el_pool_se_crea_con_su_hook_y_su_tiempo_de_espera(self):
        pool = crear_pool(espera=3.0)
        try:
            assert _sellar_correlacion in pool.event_hooks["request"]
            assert pool.timeout == httpx.Timeout(3.0)
        finally:
            await pool.aclose()

    async def test_el_id_no_se_filtra_a_la_siguiente_peticion(self):
        app = crear_app(titulo="Prueba", descripcion="banco")

        @app.get("/quien-soy")
        async def quien_soy() -> dict:
            return {"cid": id_de_correlacion()}

        primera = await _pedir(app, "GET", "/quien-soy", headers={CABECERA_CORRELACION: "req-primera"})
        segunda = await _pedir(app, "GET", "/quien-soy")

        assert primera.json()["cid"] == "req-primera"
        assert segunda.json()["cid"] != "req-primera"
        assert segunda.headers[CABECERA_CORRELACION] == segunda.json()["cid"]
        assert id_de_correlacion() is None  # tampoco quedo pegado al contexto del llamador

    @pytest.mark.xfail(
        strict=True,
        reason="H-C-09: la cabecera x-correlation-id entrante se acepta sin sanear (longitud ni caracteres)",
    )
    @pytest.mark.parametrize(
        "hostil",
        ["x" * 5000, "a] ERROR forged [b", "<script>alert(1)</script>"],
        ids=["gigante", "falsifica-log", "html"],
    )
    async def test_un_id_hostil_se_reemplaza_por_uno_propio(self, hostil):
        """El id entra por una cabecera que controla el cliente, se pega en CADA
        linea de log (`[%(correlacion)s]`), se reenvia a todos los servicios y se
        refleja en la respuesta. Evidencia: http.py:238 lo toma tal cual
        (`peticion.headers.get(CABECERA_CORRELACION) or uuid4().hex`) sin validar
        longitud ni alfabeto."""
        app = crear_app(titulo="Prueba", descripcion="banco")

        @app.get("/quien-soy")
        async def quien_soy() -> dict:
            return {"cid": id_de_correlacion()}

        respuesta = await _pedir(app, "GET", "/quien-soy", headers={CABECERA_CORRELACION: hostil})

        visto = respuesta.json()["cid"]
        assert visto != hostil
        assert re.fullmatch(r"[A-Za-z0-9._-]{1,128}", visto)
        assert respuesta.headers[CABECERA_CORRELACION] == visto
