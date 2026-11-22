from __future__ import annotations

import httpx
import pytest
from tukit_gateway.api import CABECERAS_SALTADAS, RUTAS, app, bloqueada, destino


class TestElPrefijoMasLargoGana:
    @pytest.mark.parametrize(
        ("ruta", "esperado"),
        [
            ("/v1/catalogo/conceptos", "catalogo"),
            ("/v1/catalogo", "catalogo"),
            ("/v1/listas/abc", "catalogo"),
            ("/v1/listas/subir", "inteligencia"),
            ("/v1/colegios", "identidad"),
            ("/v1/contactos", "identidad"),
            ("/v1/trabajos/abc", "inteligencia"),
            ("/v1/mis-solicitudes", "inteligencia"),
            ("/v1/admin/cola", "inteligencia"),
            ("/v1/admin/listas", "catalogo"),
            ("/v1/admin/listas/abc/revision", "catalogo"),
            ("/v1/admin/propuestas/abc/rechazar", "catalogo"),
            ("/v1/admin/catalogo/propuestas", "catalogo"),
            ("/v1/admin/catalogo/tiendas/exito/buscar", "catalogo"),
            ("/v1/admin/onboarding", "inteligencia"),
            ("/v1/admin/listas/importar", "catalogo"),
            ("/v1/admin/listas/abc/documento", "catalogo"),
            ("/v1/admin/listas/abc/percepcion", "catalogo"),
            ("/v1/admin/sugerencias", "catalogo"),
            ("/v1/admin/acudientes", "identidad"),
            ("/v1/admin/acudientes/abc", "identidad"),
            ("/v1/comercio/pedidos", "comercio"),
            ("/v1/comercio/pedidos/abc", "comercio"),
            ("/v1/comercio/mis-pedidos", "comercio"),
            ("/v1/cuenta", "identidad"),
            ("/v1/cuenta/direcciones", "identidad"),
            ("/v1/cuenta/direcciones/abc", "identidad"),
            ("/v1/metricas/colegios/abc", "inteligencia"),
            ("/v1/operacion/casos", "operacion"),
            ("/v1/operacion/casos/abc", "operacion"),
            ("/v1/ordenes", "comercio"),
            ("/v1/ordenes/abc/pago", "comercio"),
            ("/v1/ordenes/abc/retracto", "comercio"),
            ("/v1/pagos/abc/sincronizar", "comercio"),
            ("/v1/webhooks/wompi", "comercio"),
        ],
    )
    def test_cada_prefijo_va_a_su_servicio(self, ruta, esperado):
        assert destino(ruta) == esperado

    def test_sugerencias_no_cae_en_inteligencia(self):
        assert destino("/v1/admin/sugerencias") == "catalogo"
        assert destino("/v1/admin/sugerencias/abc") == "catalogo"

    def test_acudientes_no_cae_en_inteligencia(self):
        assert destino("/v1/admin/acudientes") == "identidad"
        assert destino("/v1/admin/acudientes/abc") == "identidad"

    def test_un_prefijo_parecido_pero_distinto_no_cuela(self):
        assert destino("/v1/listasbla") is None

    @pytest.mark.parametrize("ruta", ["/", "/v1", "/v2/catalogo", "/v1/inventado"])
    def test_lo_que_no_esta_declarado_no_se_rutea(self, ruta):
        assert destino(ruta) is None


class TestNingunaRutaSeAnunciaComoPendiente:
    def test_el_checkout_y_el_webhook_no_estan_pendientes(self):
        from tukit_gateway.api import PENDIENTES, pendiente

        assert PENDIENTES == {}
        assert pendiente("/v1/ordenes") is None
        assert pendiente("/v1/webhooks/wompi") is None


class TestLasRutasInternasNoSeExponen:
    def test_pedidos_pagados_esta_bloqueada(self):
        assert bloqueada("/v1/comercio/pedidos-pagados") is True

    def test_leer_un_contacto_esta_bloqueado(self):
        assert bloqueada("/v1/contactos/e1b0fb96-a9ee-5bb0-b0be-c2c88ace6b62") is True
        assert bloqueada("/v1/contactos") is False

    def test_el_resto_de_comercio_no_esta_bloqueado(self):
        assert bloqueada("/v1/comercio/pedidos") is False
        assert bloqueada("/v1/comercio/mis-pedidos") is False
        assert destino("/v1/comercio/pedidos") == "comercio"

    @pytest.mark.parametrize(
        ("ruta", "servicio"),
        [
            ("/v1/comercio/mis-pedidos/abc/retracto", "comercio"),
            ("/v1/operacion/mis-casos", "operacion"),
            ("/v1/cuenta/mis-datos", "identidad"),
            ("/v1/cuenta/mis-datos/exportar", "identidad"),
            ("/v1/cuenta/supresion", "identidad"),
            ("/v1/cuenta/consentimientos/revocar", "identidad"),
            ("/v1/operacion/mis-casos/abc/comentarios", "operacion"),
            ("/v1/trabajos/abc/kits/Fan/lineas/xyz/descarte", "inteligencia"),
            ("/v1/trabajos/abc/kits/Fan/lineas/xyz/opciones", "inteligencia"),
        ],
    )
    def test_las_rutas_del_acudiente_pasan_por_la_puerta(self, ruta, servicio):
        assert bloqueada(ruta) is False
        assert destino(ruta) == servicio

    async def test_responde_404_indistinguible_de_ruta_desconocida(self):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://prueba"
        ) as cliente:
            respuesta = await cliente.get("/v1/comercio/pedidos-pagados")

        assert respuesta.status_code == 404
        cuerpo = respuesta.json()
        assert cuerpo["error"] == "ruta_desconocida"
        assert cuerpo["rutas"] == sorted(RUTAS)
        assert "/v1/comercio/pedidos-pagados" not in cuerpo["rutas"]


async def _respuesta_cruda(ruta: str) -> tuple[int, bytes]:
    from urllib.parse import unquote

    mensajes: list[dict] = []
    alcance = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "GET",
        "scheme": "http",
        "path": unquote(ruta),
        "raw_path": ruta.encode(),
        "query_string": b"",
        "root_path": "",
        "headers": [(b"host", b"prueba")],
        "server": ("prueba", 80),
        "client": ("127.0.0.1", 1),
    }

    async def recibir() -> dict:
        return {"type": "http.request", "body": b"", "more_body": False}

    async def enviar(mensaje: dict) -> None:
        mensajes.append(mensaje)

    await app(alcance, recibir, enviar)
    estado = next(m["status"] for m in mensajes if m["type"] == "http.response.start")
    cuerpo = b"".join(m.get("body", b"") for m in mensajes if m["type"] == "http.response.body")
    return estado, cuerpo


class TestLosSegmentosPuntoNoSaltanElBloqueo:
    @pytest.mark.parametrize(
        "ruta",
        [
            "/v1/comercio/x/../pedidos-pagados",
            "/v1/comercio/./pedidos-pagados",
            "/v1/ordenes/../ordenes",
            "/v1/catalogo/..",
            "/v1/comercio\\pedidos-pagados",
        ],
    )
    def test_una_ruta_ambigua_esta_bloqueada(self, ruta):
        assert bloqueada(ruta) is True

    def test_un_punto_dentro_de_un_segmento_no_es_ambiguo(self):
        assert bloqueada("/v1/catalogo/imagen.png") is False
        assert bloqueada("/v1/catalogo/v1..2") is False

    @pytest.mark.parametrize(
        "ruta",
        [
            "/v1/comercio/x/../pedidos-pagados",
            "/v1/comercio/x/%2e%2e/pedidos-pagados",
            "/v1/comercio/x/%2E%2E/pedidos-pagados",
            "/v1/comercio/x%2f..%2fpedidos-pagados",
            "/v1/comercio/x/../../v1/ordenes/abc/pago",
        ],
    )
    async def test_la_ruta_cruda_responde_el_404_de_ruta_desconocida(self, ruta):
        estado, cuerpo = await _respuesta_cruda(ruta)
        assert estado == 404
        assert b'"ruta_desconocida"' in cuerpo


class TestElEndpointInternoDeCatalogoNoSeExpone:
    RUTA = "/interno/listas-por-contacto/aaaaaaaa-aaaa-5aaa-8aaa-aaaaaaaaaaaa"

    def test_una_ruta_interna_no_tiene_destino_en_la_puerta(self):
        assert destino(self.RUTA) is None

    async def test_responde_404_ruta_desconocida(self):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://prueba"
        ) as cliente:
            respuesta = await cliente.get(self.RUTA)

        assert respuesta.status_code == 404
        cuerpo = respuesta.json()
        assert cuerpo["error"] == "ruta_desconocida"
        assert not any(r.startswith("/interno") for r in cuerpo["rutas"])


class TestLaRespuestaCuandoNoSabe:
    async def test_dice_que_rutas_si_existen(self):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://prueba"
        ) as cliente:
            respuesta = await cliente.get("/v1/inventado")

        assert respuesta.status_code == 404
        cuerpo = respuesta.json()
        assert cuerpo["error"] == "ruta_desconocida"
        assert cuerpo["rutas"] == sorted(RUTAS)

    async def test_un_servicio_apagado_da_503_y_no_502(self, monkeypatch):
        monkeypatch.setenv("TUKIT_CATALOGO_URL", "http://127.0.0.1:1")
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://prueba"
        ) as cliente:
            respuesta = await cliente.get("/v1/catalogo/conceptos")

        assert respuesta.status_code == 503
        assert respuesta.json()["error"] == "servicio_no_disponible"


class TestElCuerpoMultipartViajaIntacto:
    def test_content_type_no_se_salta(self):
        assert "content-type" not in CABECERAS_SALTADAS

    async def test_reenvia_el_multipart_sin_alterarlo(self):
        capturado: dict[str, object] = {}

        class ClienteEspia:
            async def aclose(self):
                return None

            async def get(self, url, **_kwargs):
                return httpx.Response(200, json={"usuario_id": "u", "roles": [{"rol": "operador"}]})

            async def request(self, metodo, url, *, params, headers, content):
                capturado["metodo"] = metodo
                capturado["url"] = url
                capturado["headers"] = headers
                capturado["content"] = content
                return httpx.Response(200, content=b"ok")

        app.state.cliente = ClienteEspia()

        boundary = "----tukitBoundary123"
        cuerpo = (
            f"--{boundary}\r\n"
            'Content-Disposition: form-data; name="archivo"; filename="lista.pdf"\r\n'
            "Content-Type: application/pdf\r\n\r\n"
            "%PDF-1.4 binario\x00\x01\x02\r\n"
            f"--{boundary}--\r\n"
        ).encode("latin-1")
        tipo = f"multipart/form-data; boundary={boundary}"

        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://prueba"
        ) as cliente:
            respuesta = await cliente.post(
                "/v1/admin/listas/importar",
                content=cuerpo,
                headers={"content-type": tipo, "authorization": "Bearer tok-operador"},
            )

        assert respuesta.status_code == 200
        assert capturado["content"] == cuerpo
        assert capturado["url"].endswith("/v1/admin/listas/importar")
        assert capturado["headers"]["content-type"] == tipo


class TestLaSondaDiceLaVerdadSobreLosTres:
    async def test_no_responde_ok_con_los_tres_caidos(self, monkeypatch):
        for variable in (
            "TUKIT_CATALOGO_URL",
            "TUKIT_IDENTIDAD_URL",
            "TUKIT_INTELIGENCIA_URL",
            "TUKIT_COMERCIO_URL",
            "TUKIT_OPERACION_URL",
        ):
            monkeypatch.setenv(variable, "http://127.0.0.1:1")
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://prueba"
        ) as cliente:
            assert (await cliente.get("/salud")).json()["estado"] == "ok"
            cuerpo = (await cliente.get("/v1/servicios")).json()

        assert cuerpo["todos_arriba"] is False
        assert set(cuerpo["servicios"]) == {
            "catalogo",
            "identidad",
            "inteligencia",
            "comercio",
            "operacion",
        }

    @pytest.mark.parametrize(
        "ruta",
        [
            "/v1/ordenes",
            "/v1/ordenes/abc",
            "/v1/ordenes/abc/pago",
            "/v1/ordenes/abc/retracto",
            "/v1/ordenes/abc/avanzar/x",
        ],
    )
    def test_ordenes_internas_estan_bloqueadas(self, ruta):
        assert bloqueada(ruta) is True

    def test_el_avance_de_ordenes_si_pasa(self):
        assert bloqueada("/v1/ordenes/abc/avanzar") is False
        assert destino("/v1/ordenes/abc/avanzar") == "comercio"

    async def test_crear_orden_responde_el_mismo_404(self):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://prueba"
        ) as cliente:
            respuesta = await cliente.post("/v1/ordenes", json={})

        assert respuesta.status_code == 404
        assert respuesta.json()["error"] == "ruta_desconocida"
