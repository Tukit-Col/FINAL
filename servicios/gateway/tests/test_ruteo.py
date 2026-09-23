"""La puerta rutea por prefijo y no adivina.

El caso que estas pruebas fijan es el de una ruta desconocida. Un proxy con
comodin la reenviaria a algun servicio y el error saldria seis capas mas
abajo, con el mensaje del servicio equivocado; aqui se responde 404 con la
lista de prefijos que si existen, que es lo que le sirve a quien esta
integrando.
"""

from __future__ import annotations

import httpx
import pytest
from tukit_gateway.api import RUTAS, app, destino


class TestElPrefijoMasLargoGana:
    @pytest.mark.parametrize(
        ("ruta", "esperado"),
        [
            ("/v1/catalogo/conceptos", "catalogo"),
            ("/v1/catalogo", "catalogo"),
            ("/v1/listas/abc", "catalogo"),
            ("/v1/colegios", "identidad"),
            ("/v1/contactos", "identidad"),
            ("/v1/trabajos/abc", "inteligencia"),
            # `/v1/admin` esta declarado aparte y no cae en `/v1/trabajos`
            # por parecido: si un dia admin vive en otro servicio, cambia una
            # linea del mapa y nada mas.
            ("/v1/admin/cola", "inteligencia"),
        ],
    )
    def test_cada_prefijo_va_a_su_servicio(self, ruta, esperado):
        assert destino(ruta) == esperado

    def test_un_prefijo_parecido_pero_distinto_no_cuela(self):
        """`/v1/listasbla` no es `/v1/listas`. Sin la comprobacion del
        separador, un endpoint nuevo mal escrito se reenviaria en silencio."""
        assert destino("/v1/listasbla") is None

    @pytest.mark.parametrize("ruta", ["/", "/v1", "/v2/catalogo", "/v1/ordenes"])
    def test_lo_que_no_esta_declarado_no_se_rutea(self, ruta):
        assert destino(ruta) is None


class TestLoQueElContratoDefineYNadieSirve:
    """501 y no 404, y la diferencia le importa a quien integra.

    Un 404 dice "te equivocaste de URL" y manda a revisar el cliente; un 501
    dice "la URL es correcta y el backend todavia no la sirve" y manda a
    esperar. Confundirlas cuesta una tarde buscando un error que no esta.
    """

    @pytest.mark.parametrize("ruta", ["/v1/ordenes", "/v1/ordenes/abc/pago", "/v1/webhooks/wompi"])
    async def test_el_pago_responde_501_con_la_seccion_del_contrato(self, ruta):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://prueba"
        ) as cliente:
            respuesta = await cliente.post(ruta, json={})

        assert respuesta.status_code == 501
        cuerpo = respuesta.json()
        assert cuerpo["error"] == "no_implementado"
        assert cuerpo["seccion_contrato"] == "9"


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
        """El de atras no fallo, no esta. La distincion le dice a quien opera
        si hay que mirar un log o levantar un proceso.

        El destino se fija a un puerto cerrado en vez de confiar en que el
        servicio real no este levantado: si alguien corre la suite con el
        backend arriba, la prueba pasaria por la razon equivocada.
        """
        monkeypatch.setenv("TUKIT_CATALOGO_URL", "http://127.0.0.1:1")
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://prueba"
        ) as cliente:
            respuesta = await cliente.get("/v1/catalogo/conceptos")

        assert respuesta.status_code == 503
        assert respuesta.json()["error"] == "servicio_no_disponible"


class TestLaSondaDiceLaVerdadSobreLosTres:
    async def test_no_responde_ok_con_los_tres_caidos(self, monkeypatch):
        """`GET /salud` en la puerta responde `ok` aunque no haya nada
        detras. Sin `/v1/servicios`, eso hace perder una tarde."""
        for variable in ("TUKIT_CATALOGO_URL", "TUKIT_IDENTIDAD_URL", "TUKIT_INTELIGENCIA_URL"):
            monkeypatch.setenv(variable, "http://127.0.0.1:1")
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://prueba"
        ) as cliente:
            assert (await cliente.get("/salud")).json()["estado"] == "ok"
            cuerpo = (await cliente.get("/v1/servicios")).json()

        assert cuerpo["todos_arriba"] is False
        assert set(cuerpo["servicios"]) == {"catalogo", "identidad", "inteligencia"}
