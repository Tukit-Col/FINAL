from __future__ import annotations

import httpx
import pytest
from tukit_gateway.api import app

SESIONES = {
    "tok-admin": [{"rol": "admin", "ambito_tipo": "global"}],
    "tok-operador": [{"rol": "operador", "ambito_tipo": "global"}],
    "tok-acudiente": [{"rol": "acudiente", "ambito_tipo": "global"}],
}

RUTAS_DE_CONSOLA = [
    ("GET", "/v1/admin/cola"),
    ("GET", "/v1/admin/listas"),
    ("POST", "/v1/admin/trabajos/aaaa/revision"),
    ("POST", "/v1/admin/listas/bbbb/cerrar"),
    ("GET", "/v1/admin/catalogo/propuestas"),
    ("GET", "/v1/admin/sugerencias"),
    ("GET", "/v1/admin/acudientes"),
    ("PATCH", "/v1/catalogo/productos/TK-001"),
    ("DELETE", "/v1/catalogo/productos/TK-001"),
    ("POST", "/v1/catalogo/productos/TK-001/reclasificar"),
    ("PATCH", "/v1/colegios/cccc"),
]


class Atras:

    def __init__(self, *, identidad_caida: bool = False) -> None:
        self.identidad_caida = identidad_caida
        self.reenviadas: list[str] = []

    def __call__(self, peticion: httpx.Request) -> httpx.Response:
        if peticion.url.path == "/v1/sesiones/actual":
            if self.identidad_caida:
                raise httpx.ConnectError("identidad apagada", request=peticion)
            token = peticion.headers.get("authorization", "").removeprefix("Bearer ").strip()
            roles = SESIONES.get(token)
            if roles is None:
                return httpx.Response(401, json={"error": "sesion_invalida", "mensaje": "no"})
            return httpx.Response(200, json={"usuario_id": "u-1", "roles": roles})
        self.reenviadas.append(f"{peticion.method} {peticion.url.path}")
        return httpx.Response(200, json={"ok": True})


@pytest.fixture
def atras():
    doble = Atras()
    app.state.cliente = httpx.AsyncClient(transport=httpx.MockTransport(doble))
    yield doble
    del app.state.cliente


async def _llamar(metodo: str, ruta: str, token: str | None = None) -> httpx.Response:
    cabeceras = {"Authorization": f"Bearer {token}"} if token else {}
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://prueba") as cliente:
        return await cliente.request(metodo, ruta, headers=cabeceras, json={} if metodo == "POST" else None)


class TestLaConsolaExigeSesionDelEquipo:
    @pytest.mark.parametrize("token", [None, "tok-inventado"], ids=["sin_token", "token_desconocido"])
    @pytest.mark.parametrize(("metodo", "ruta"), RUTAS_DE_CONSOLA)
    async def test_sin_sesion_valida_es_401_y_no_se_reenvia(self, atras, metodo, ruta, token):
        respuesta = await _llamar(metodo, ruta, token)
        assert respuesta.status_code == 401
        assert respuesta.json()["error"] == "sesion_invalida"
        assert atras.reenviadas == []

    @pytest.mark.parametrize(("metodo", "ruta"), RUTAS_DE_CONSOLA)
    async def test_token_de_acudiente_es_403(self, atras, metodo, ruta):
        respuesta = await _llamar(metodo, ruta, "tok-acudiente")
        assert respuesta.status_code == 403
        assert respuesta.json()["error"] == "acceso_denegado"
        assert atras.reenviadas == []

    @pytest.mark.parametrize("token", ["tok-admin", "tok-operador"])
    @pytest.mark.parametrize(("metodo", "ruta"), RUTAS_DE_CONSOLA)
    async def test_admin_u_operador_pasan(self, atras, metodo, ruta, token):
        respuesta = await _llamar(metodo, ruta, token)
        assert respuesta.status_code == 200
        assert atras.reenviadas == [f"{metodo} {ruta}"]

    async def test_identidad_caida_cierra_con_503(self):
        doble = Atras(identidad_caida=True)
        app.state.cliente = httpx.AsyncClient(transport=httpx.MockTransport(doble))
        try:
            respuesta = await _llamar("GET", "/v1/admin/cola", "tok-admin")
        finally:
            del app.state.cliente
        assert respuesta.status_code == 503
        assert respuesta.json()["error"] == "identidad_no_disponible"
        assert doble.reenviadas == []


class TestLoQueNoEsConsolaQuedaAbierto:
    async def test_la_sugerencia_del_acudiente_es_abierta(self, atras):
        respuesta = await _llamar("POST", "/v1/admin/sugerencias")
        assert respuesta.status_code == 200
        assert atras.reenviadas == ["POST /v1/admin/sugerencias"]

    async def test_una_ruta_publica_no_pide_token(self, atras):
        respuesta = await _llamar("GET", "/v1/catalogo/conceptos")
        assert respuesta.status_code == 200
        assert atras.reenviadas == ["GET /v1/catalogo/conceptos"]

    @pytest.mark.parametrize("ruta", ["/v1/catalogo/productos/TK-001", "/v1/colegios/cccc"])
    async def test_leer_un_producto_o_un_colegio_es_abierto(self, atras, ruta):
        respuesta = await _llamar("GET", ruta)
        assert respuesta.status_code == 200
        assert atras.reenviadas == [f"GET {ruta}"]

    async def test_un_prefijo_parecido_no_es_consola(self, atras):
        respuesta = await _llamar("GET", "/v1/administrar")
        assert respuesta.status_code == 404
