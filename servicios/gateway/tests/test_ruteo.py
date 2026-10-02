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
from tukit_gateway import api
from tukit_gateway.api import CABECERAS_SALTADAS, RUTAS, app, bloqueada, destino


class TestElPrefijoMasLargoGana:
    @pytest.mark.parametrize(
        ("ruta", "esperado"),
        [
            ("/v1/catalogo/conceptos", "catalogo"),
            ("/v1/catalogo", "catalogo"),
            ("/v1/listas/abc", "catalogo"),
            # La subida de listas la sirve inteligencia (percepcion + version
            # pendiente), no catalogo: su prefijo mas largo gana a `/v1/listas`.
            # Un `/v1/listas/<id>` cualquiera sigue en catalogo (la linea de arriba).
            ("/v1/listas/subir", "inteligencia"),
            ("/v1/colegios", "identidad"),
            ("/v1/contactos", "identidad"),
            ("/v1/trabajos/abc", "inteligencia"),
            # "Mis solicitudes" del acudiente: prefijo propio para no chocar con
            # `/v1/trabajos/{trabajo_id}`; la sirve inteligencia.
            ("/v1/mis-solicitudes", "inteligencia"),
            # `/v1/admin` esta declarado aparte y no cae en `/v1/trabajos`
            # por parecido: si un dia admin vive en otro servicio, cambia una
            # linea del mapa y nada mas.
            ("/v1/admin/cola", "inteligencia"),
            # La revision de listas la sirve catalogo; la ingesta de PDF,
            # inteligencia. Ambas bajo `/v1/admin`, distinguidas por el prefijo
            # mas largo: `/v1/admin/listas` gana a `/v1/admin`.
            ("/v1/admin/listas", "catalogo"),
            ("/v1/admin/listas/abc/revision", "catalogo"),
            ("/v1/admin/propuestas/abc/rechazar", "catalogo"),
            # La curaduria proactiva del catalogo (cola, alta de util/libro,
            # buscar en tienda, aprobar) cuelga de `/v1/admin/catalogo`: su
            # prefijo mas largo gana a `/v1/admin` -> inteligencia. `rechazar`
            # sigue yendo a catalogo por su propio prefijo `/v1/admin/propuestas`.
            ("/v1/admin/catalogo/propuestas", "catalogo"),
            ("/v1/admin/catalogo/tiendas/exito/buscar", "catalogo"),
            ("/v1/admin/onboarding", "inteligencia"),
            # Importar una lista, su documento y su percepcion cuelgan de
            # `/v1/admin/listas`, asi que van a catalogo por el prefijo mas
            # largo; el onboarding no tiene ese prefijo y cae en `/v1/admin`.
            ("/v1/admin/listas/importar", "catalogo"),
            ("/v1/admin/listas/abc/documento", "catalogo"),
            ("/v1/admin/listas/abc/percepcion", "catalogo"),
            # El backlog de sugerencias de padres cuelga de `/v1/admin` pero lo
            # sirve catalogo: su prefijo mas largo gana a `/v1/admin` y evita
            # que caiga en inteligencia.
            ("/v1/admin/sugerencias", "catalogo"),
            # El padron de acudientes lo sirve identidad (es su dato personal),
            # no inteligencia: su prefijo mas largo gana a `/v1/admin`.
            ("/v1/admin/acudientes", "identidad"),
            ("/v1/admin/acudientes/abc", "identidad"),
            # El tablero de logistica y la bandeja de casos, que ahora si tienen
            # servicio detras (comercio y operacion).
            ("/v1/comercio/pedidos", "comercio"),
            ("/v1/comercio/pedidos/abc", "comercio"),
            ("/v1/comercio/mis-pedidos", "comercio"),
            # "Mi cuenta" del acudiente y su libreta de direcciones: identidad.
            ("/v1/cuenta", "identidad"),
            ("/v1/cuenta/direcciones", "identidad"),
            ("/v1/cuenta/direcciones/abc", "identidad"),
            # El panel del colegio (kits, cobertura, ahorro) lo calcula
            # inteligencia; cuelga de `/v1/metricas`, no de `/v1/colegios`.
            ("/v1/metricas/colegios/abc", "inteligencia"),
            ("/v1/operacion/casos", "operacion"),
            ("/v1/operacion/casos/abc", "operacion"),
            # El checkout y el webhook de la pasarela, ahora servidos por
            # comercio (§9): salieron de PENDIENTES cuando existio la escritura.
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
        """`/v1/admin/sugerencias` NO debe sombrearse a `/v1/admin` (inteligencia).

        Sin el prefijo propio la sugerencia iria al servicio equivocado y el
        backlog nunca se escribiria; el fallo saldria capas mas abajo.
        """
        assert destino("/v1/admin/sugerencias") == "catalogo"
        assert destino("/v1/admin/sugerencias/abc") == "catalogo"

    def test_acudientes_no_cae_en_inteligencia(self):
        """`/v1/admin/acudientes` NO debe sombrearse a `/v1/admin` (inteligencia).

        Sin el prefijo propio el padron iria al servicio equivocado y nunca
        llegaria a identidad, que es quien tiene el dato del acudiente.
        """
        assert destino("/v1/admin/acudientes") == "identidad"
        assert destino("/v1/admin/acudientes/abc") == "identidad"

    def test_un_prefijo_parecido_pero_distinto_no_cuela(self):
        """`/v1/listasbla` no es `/v1/listas`. Sin la comprobacion del
        separador, un endpoint nuevo mal escrito se reenviaria en silencio."""
        assert destino("/v1/listasbla") is None

    @pytest.mark.parametrize("ruta", ["/", "/v1", "/v2/catalogo", "/v1/inventado"])
    def test_lo_que_no_esta_declarado_no_se_rutea(self, ruta):
        assert destino(ruta) is None


class TestYaNoHayPagoPendiente:
    """El §9 (checkout y webhook) ya no responde 501: tiene a comercio detras.

    Cuando el pago vivia en PENDIENTES, la puerta respondia 501 con la seccion
    del contrato. Ahora que la escritura de comercio existe, esas rutas rutean
    como cualquier otra y PENDIENTES queda vacio; esta prueba fija que no quedo
    ningun 501 residual anunciando algo que ya se sirve.
    """

    def test_el_checkout_ya_no_esta_pendiente(self):
        from tukit_gateway.api import PENDIENTES, pendiente

        assert PENDIENTES == {}
        assert pendiente("/v1/ordenes") is None
        assert pendiente("/v1/webhooks/wompi") is None


class TestLasRutasInternasNoSeExponen:
    """`/v1/comercio/pedidos-pagados` es servicio-a-servicio (inteligencia le
    pega directo a comercio por `TUKIT_COMERCIO_URL`), y desde fuera debe verse
    como INEXISTENTE, no como prohibida: revelar que hay una superficie interna
    es informacion que no le hace falta a nadie de fuera.
    """

    def test_pedidos_pagados_esta_bloqueada(self):
        assert bloqueada("/v1/comercio/pedidos-pagados") is True

    def test_el_resto_de_comercio_no_esta_bloqueado(self):
        # El bloqueo es exacto sobre pedidos-pagados: el tablero de pedidos y lo
        # demas de comercio siguen ruteando.
        assert bloqueada("/v1/comercio/pedidos") is False
        assert bloqueada("/v1/comercio/mis-pedidos") is False
        assert destino("/v1/comercio/pedidos") == "comercio"

    async def test_responde_404_indistinguible_de_ruta_desconocida(self):
        """El 404 de la ruta interna es identico al de una ruta que no existe, y
        la ruta bloqueada NO aparece en la lista de rutas: desde fuera no hay
        forma de saber que existe una superficie interna detras."""
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://prueba"
        ) as cliente:
            respuesta = await cliente.get("/v1/comercio/pedidos-pagados")

        assert respuesta.status_code == 404
        cuerpo = respuesta.json()
        assert cuerpo["error"] == "ruta_desconocida"
        assert cuerpo["rutas"] == sorted(RUTAS)
        assert "/v1/comercio/pedidos-pagados" not in cuerpo["rutas"]


class TestElEndpointInternoDeCatalogoNoSeExpone:
    """`/interno/listas-por-contacto/{usuario_id}` es servicio-a-servicio
    (inteligencia le pega directo a catalogo por `TUKIT_CATALOGO_URL`) y, como no
    esta en `RUTAS`, la puerta ni siquiera lo conoce: `destino` es `None` y la
    peticion recibe el mismo 404 de "ruta desconocida" que cualquier otra. Asi la
    superficie interna del catalogo no existe hacia el navegador."""

    RUTA = "/interno/listas-por-contacto/aaaaaaaa-aaaa-5aaa-8aaa-aaaaaaaaaaaa"

    def test_destino_es_none(self):
        assert destino(self.RUTA) is None

    async def test_responde_404_ruta_desconocida(self):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://prueba"
        ) as cliente:
            respuesta = await cliente.get(self.RUTA)

        assert respuesta.status_code == 404
        cuerpo = respuesta.json()
        assert cuerpo["error"] == "ruta_desconocida"
        # El prefijo interno no aparece en la lista de rutas que si existen.
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


class TestElCuerpoMultipartViajaIntacto:
    """La ingesta de PDF sube un multipart; si la puerta tocara el cuerpo o
    perdiera el `content-type` con su boundary, el de atras no podria parsear
    los campos. La puerta lee `body()` crudo y lo pasa tal cual con el
    `content-type` original —que no esta en CABECERAS_SALTADAS—.
    """

    def test_content_type_no_se_salta(self):
        assert "content-type" not in CABECERAS_SALTADAS

    async def test_reenvia_el_multipart_sin_alterarlo(self, monkeypatch):
        capturado: dict[str, object] = {}

        class ClienteEspia:
            def __init__(self, *args, **kwargs):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                return False

            async def request(self, metodo, url, *, params, headers, content):
                capturado["metodo"] = metodo
                capturado["url"] = url
                capturado["headers"] = headers
                capturado["content"] = content
                return httpx.Response(200, content=b"ok")

        # Se reemplaza el modulo `httpx` que ve `api` por un envoltorio que
        # solo cambia `AsyncClient`, para no tocar el `httpx` real que usa el
        # cliente de prueba de esta misma suite (comparten el modulo).
        class HttpxEnvuelto:
            AsyncClient = ClienteEspia
            HTTPError = httpx.HTTPError

        monkeypatch.setattr(api, "httpx", HttpxEnvuelto)

        # Un multipart armado a mano con un boundary explicito, para poder
        # verificar byte a byte que llega igual y que el boundary sobrevive.
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
                "/v1/admin/listas/importar", content=cuerpo, headers={"content-type": tipo}
            )

        assert respuesta.status_code == 200
        assert capturado["content"] == cuerpo
        assert capturado["url"].endswith("/v1/admin/listas/importar")
        assert capturado["headers"]["content-type"] == tipo


class TestLaSondaDiceLaVerdadSobreLosTres:
    async def test_no_responde_ok_con_los_tres_caidos(self, monkeypatch):
        """`GET /salud` en la puerta responde `ok` aunque no haya nada
        detras. Sin `/v1/servicios`, eso hace perder una tarde."""
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
