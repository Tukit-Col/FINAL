"""La consola interna (`/v1/admin/*`) no se abre sin una sesion del equipo.

El defecto que esto fija: por la puerta, sin token, `GET /v1/admin/cola`
respondia 200 y `POST /v1/admin/trabajos/{id}/revision` aprobaba y publicaba
un kit. Solo `/v1/admin/acudientes` cerraba, porque identidad lo revisa por su
cuenta; catalogo e inteligencia confiaban en que nadie de fuera llegara.

La puerta es el unico punto por el que pasa todo el trafico de fuera, asi que
el chequeo vive aqui: 401 sin token o con uno que identidad no reconoce, 403
con un token valido sin rol de equipo (admin u operador), y el reenvio normal
con uno que si lo tiene. Identidad se simula con un transporte de httpx: la
prueba no necesita ningun proceso levantado.
"""

from __future__ import annotations

import httpx
import pytest
from tukit_gateway.api import app

# token -> roles que identidad devolveria en `GET /v1/sesiones/actual`.
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
]


class Atras:
    """Identidad y los servicios de atras en un solo transporte falso.

    Anota cada peticion que llega a un servicio que no es la validacion de la
    sesion, para que la prueba pueda decir que un 401/403 NO se reenvio."""

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
    """Cuelga un cliente compartido falso en `app.state` y lo retira al final."""
    doble = Atras()
    app.state.cliente = httpx.AsyncClient(transport=httpx.MockTransport(doble))
    yield doble
    del app.state.cliente


async def _llamar(metodo: str, ruta: str, token: str | None = None) -> httpx.Response:
    cabeceras = {"Authorization": f"Bearer {token}"} if token else {}
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://prueba") as cliente:
        return await cliente.request(metodo, ruta, headers=cabeceras, json={} if metodo == "POST" else None)


class TestLaConsolaExigeSesionDelEquipo:
    @pytest.mark.parametrize(("metodo", "ruta"), RUTAS_DE_CONSOLA)
    async def test_sin_token_es_401_y_no_se_reenvia(self, atras, metodo, ruta):
        respuesta = await _llamar(metodo, ruta)
        assert respuesta.status_code == 401
        assert respuesta.json()["error"] == "sesion_invalida"
        assert atras.reenviadas == []

    @pytest.mark.parametrize(("metodo", "ruta"), RUTAS_DE_CONSOLA)
    async def test_token_que_identidad_no_reconoce_es_401(self, atras, metodo, ruta):
        respuesta = await _llamar(metodo, ruta, "tok-inventado")
        assert respuesta.status_code == 401
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
        """Falla CERRADA: no poder preguntar no es razon para abrir."""
        doble = Atras(identidad_caida=True)
        app.state.cliente = httpx.AsyncClient(transport=httpx.MockTransport(doble))
        try:
            respuesta = await _llamar("GET", "/v1/admin/cola", "tok-admin")
        finally:
            del app.state.cliente
        assert respuesta.status_code == 503
        assert respuesta.json()["error"] == "identidad_no_disponible"
        assert doble.reenviadas == []


class TestLoQueNoEsConsolaNoCambia:
    async def test_la_sugerencia_del_acudiente_sigue_abierta(self, atras):
        """`POST /v1/admin/sugerencias` lo llama la web publica, sin sesion: un
        acudiente sugiere su (colegio, grado). Leer el backlog si es del equipo."""
        respuesta = await _llamar("POST", "/v1/admin/sugerencias")
        assert respuesta.status_code == 200
        assert atras.reenviadas == ["POST /v1/admin/sugerencias"]

    async def test_una_ruta_publica_no_pide_token(self, atras):
        respuesta = await _llamar("GET", "/v1/catalogo/conceptos")
        assert respuesta.status_code == 200
        assert atras.reenviadas == ["GET /v1/catalogo/conceptos"]

    async def test_un_prefijo_parecido_no_es_consola(self, atras):
        """`/v1/administrar` no es `/v1/admin`: la puerta ni lo rutea (404)."""
        respuesta = await _llamar("GET", "/v1/administrar")
        assert respuesta.status_code == 404
