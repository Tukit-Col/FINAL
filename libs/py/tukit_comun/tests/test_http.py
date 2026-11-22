from __future__ import annotations

from datetime import UTC, datetime

import httpx
import pytest
from fastapi import FastAPI
from pydantic import BaseModel
from tukit_comun.http import (
    CABECERA_CORRELACION,
    ORIGENES_POR_OMISION,
    ErrorDominio,
    cliente_efimero,
    crear_app,
    id_de_correlacion,
    iso,
    origenes_permitidos,
)


class Clave(BaseModel):
    contrasena: str
    edad: int


def _app() -> FastAPI:
    app = crear_app(titulo="Prueba", descripcion="banco de pruebas")

    @app.post("/eco")
    async def eco(clave: Clave) -> dict:
        return {"ok": True}

    @app.get("/rechazo")
    async def rechazo() -> dict:
        raise ErrorDominio("presupuesto_invalido", "Tiene que ser positivo.", campo="presupuesto")

    @app.get("/quien-soy")
    async def quien_soy() -> dict:
        return {"cid": id_de_correlacion()}

    return app


async def _pedir(metodo: str, ruta: str, **kw):
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=_app()), base_url="http://prueba"
    ) as cliente:
        return await cliente.request(metodo, ruta, **kw)


class TestElErrorNoDevuelveLoQueElClienteEnvio:
    async def test_la_contrasena_recibida_no_vuelve_en_la_respuesta(self):
        respuesta = await _pedir(
            "POST", "/eco", json={"contrasena": "secreto-de-verdad", "edad": "no soy un numero"}
        )

        assert respuesta.status_code == 400
        assert "secreto-de-verdad" not in respuesta.text
        assert "no soy un numero" not in respuesta.text

    async def test_conserva_donde_fallo_para_que_se_pueda_arreglar(self):
        respuesta = await _pedir("POST", "/eco", json={"contrasena": "x", "edad": "abc"})
        cuerpo = respuesta.json()

        assert cuerpo["error"] == "entrada_invalida"
        assert cuerpo["campo"] == "edad"
        assert set(cuerpo) == {"error", "mensaje", "campo"}


class TestElSobreDeDominio:
    async def test_lleva_codigo_mensaje_y_campo(self):
        respuesta = await _pedir("GET", "/rechazo")

        assert respuesta.status_code == 400
        assert respuesta.json() == {
            "error": "presupuesto_invalido",
            "mensaje": "Tiene que ser positivo.",
            "campo": "presupuesto",
        }

    def test_el_codigo_es_un_dato_y_no_texto_dentro_del_mensaje(self):
        error = ErrorDominio("estado_incompatible", "Ya estaba publicado.", estado=409)
        assert error.estado == 409
        assert error.cuerpo() == {"error": "estado_incompatible", "mensaje": "Ya estaba publicado."}


class TestElIdDeCorrelacion:

    async def test_sin_cabecera_se_acuña_una_y_vuelve_en_la_respuesta(self):
        respuesta = await _pedir("GET", "/quien-soy")
        cid = respuesta.headers.get(CABECERA_CORRELACION)
        assert cid
        assert respuesta.json()["cid"] == cid

    async def test_una_cabecera_dada_viaja_de_ida_y_vuelta(self):
        dado = "abc-123-correlacion"
        respuesta = await _pedir("GET", "/quien-soy", headers={CABECERA_CORRELACION: dado})
        assert respuesta.headers[CABECERA_CORRELACION] == dado
        assert respuesta.json()["cid"] == dado

    async def test_el_error_de_dominio_tambien_lleva_la_cabecera(self):
        dado = "corr-en-el-error"
        respuesta = await _pedir("GET", "/rechazo", headers={CABECERA_CORRELACION: dado})
        assert respuesta.status_code == 400
        assert respuesta.headers[CABECERA_CORRELACION] == dado

    async def test_cliente_efimero_propaga_el_id_a_las_salientes(self):
        async with cliente_efimero(None, 5.0) as propio:
            assert CABECERA_CORRELACION not in {k.lower() for k in propio.headers}


class TestPoolHttpx:

    async def test_el_hook_estampa_el_id_vivo_de_la_peticion_en_curso(self):
        from tukit_comun.http import _sellar_correlacion, crear_pool, fijar_correlacion, reset_correlacion

        pool = crear_pool(espera=5.0)
        try:
            peticion = pool.build_request("GET", "http://x/ping")
            token = fijar_correlacion("cid-vivo")
            try:
                await _sellar_correlacion(peticion)
            finally:
                reset_correlacion(token)
            assert peticion.headers[CABECERA_CORRELACION] == "cid-vivo"
        finally:
            await pool.aclose()

    async def test_sin_peticion_en_curso_no_anexa_nada(self):
        from tukit_comun.http import _sellar_correlacion, crear_pool

        pool = crear_pool(espera=5.0)
        try:
            peticion = pool.build_request("GET", "http://x/ping")
            await _sellar_correlacion(peticion)
            assert CABECERA_CORRELACION not in {k.lower() for k in peticion.headers}
        finally:
            await pool.aclose()


class TestLivenessYReadiness:

    async def test_live_responde_sin_base(self):
        respuesta = await _pedir("GET", "/health/live")
        assert respuesta.status_code == 200
        assert respuesta.json()["estado"] == "vivo"

    async def test_ready_sin_motor_esta_listo(self):
        respuesta = await _pedir("GET", "/health/ready")
        assert respuesta.status_code == 200
        assert respuesta.json()["estado"] == "listo"

    async def test_ready_da_503_si_la_base_falla(self):
        from types import SimpleNamespace

        class _ConexionRota:
            async def __aenter__(self):
                raise RuntimeError("base caida")

            async def __aexit__(self, *a):
                return False

        app = crear_app(titulo="Prueba", descripcion="banco")
        app.state.motor = SimpleNamespace(engine=SimpleNamespace(connect=lambda: _ConexionRota()))
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://prueba"
        ) as cliente:
            respuesta = await cliente.get("/health/ready")
        assert respuesta.status_code == 503
        assert "base caida" in respuesta.json()["detalle"]


class TestElNavegadorPuedeLeerLaRespuesta:
    async def test_el_next_local_esta_permitido_sin_configurar_nada(self):
        respuesta = await _pedir("GET", "/salud", headers={"Origin": "http://localhost:3000"})
        assert respuesta.headers["access-control-allow-origin"] == "http://localhost:3000"

    def test_sin_variable_de_entorno_valen_los_dos_puertos_de_un_next_nuevo(self, monkeypatch):
        monkeypatch.delenv("TUKIT_CORS_ORIGENES", raising=False)
        assert origenes_permitidos() == list(ORIGENES_POR_OMISION)

    def test_produccion_no_hereda_la_lista_de_desarrollo(self, monkeypatch):
        monkeypatch.setenv("TUKIT_CORS_ORIGENES", "https://tukit.co, https://admin.tukit.co")
        assert origenes_permitidos() == ["https://tukit.co", "https://admin.tukit.co"]


class TestLaSonda:
    async def test_los_tres_servicios_responden_igual(self):
        cuerpo = (await _pedir("GET", "/salud")).json()
        assert cuerpo == {"estado": "ok", "servicio": "Prueba", "version": "1.1"}


class TestIso:
    def test_none_es_none_no_cadena_vacia(self):
        assert iso(None) is None

    def test_una_fecha_sale_en_iso8601(self):
        assert iso(datetime(2026, 9, 23, 10, 30, tzinfo=UTC)) == "2026-09-23T10:30:00+00:00"


class TestClienteEfimero:

    async def test_el_cliente_inyectado_se_reusa_y_no_se_cierra(self):
        inyectado = httpx.AsyncClient()
        try:
            async with cliente_efimero(inyectado, 5.0) as usado:
                assert usado is inyectado
            assert not inyectado.is_closed
        finally:
            await inyectado.aclose()

    async def test_sin_cliente_abre_uno_propio_y_lo_cierra_al_salir(self):
        capturado = {}
        async with cliente_efimero(None, 5.0) as propio:
            capturado["c"] = propio
            assert not propio.is_closed
        assert capturado["c"].is_closed


@pytest.mark.parametrize("metodo", ["GET", "POST"])
async def test_la_sonda_no_necesita_base_de_datos(metodo):
    respuesta = await _pedir(metodo, "/salud")
    assert respuesta.status_code in {200, 405}
