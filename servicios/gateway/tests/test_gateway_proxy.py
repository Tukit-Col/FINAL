"""NFR-MAN-01: la puerta reenvia con fidelidad, degrada con 503 y no expone lo interno (`api.py`).

`test_ruteo.py` fija la tabla de prefijos. Aqui se fija el comportamiento del
reenvio con destinos de mentira (`httpx.MockTransport`, ninguna red): que viaja
al servicio de atras y que vuelve al cliente, que un servicio caido es un 503
`servicio_no_disponible` y no un 502 ni un 500, que una ruta interna bloqueada
recibe EXACTAMENTE la misma respuesta que una desconocida y nunca toca al
destino, y que la sonda `/v1/servicios` dice la verdad de cada servicio.

Importa porque la puerta es el unico punto por el que pasa todo el trafico del
navegador: lo que reenvia mal (cabeceras de salto, correlacion) rompe a todos, y
lo que deja pasar de lo interno queda expuesto sin autenticacion. Una ruta con
segmentos `.` o `..` tampoco esquiva el bloqueo: era el defecto H-A-06, que
`173ee80` corrigio con `ambigua` (api.py:178-189).
"""

from __future__ import annotations

import json
import runpy
import sys
from collections.abc import Callable
from types import SimpleNamespace
from typing import Any

import httpx
import pytest
from tukit_gateway import api
from tukit_gateway.api import ESPERA_SEGUNDOS, PUERTO_POR_OMISION, RUTAS, app

pytestmark = pytest.mark.nfr("NFR-MAN-01")

SERVICIOS = ("catalogo", "identidad", "inteligencia", "comercio", "operacion")


class Atras:
    """Los servicios de atras de mentira: anota cada peticion que les llega y
    cuanto espera la puerta su respuesta (la espera de lectura de esa peticion)."""

    def __init__(self, responder: Callable[[httpx.Request], httpx.Response]) -> None:
        self.responder = responder
        self.peticiones: list[httpx.Request] = []
        self.esperas: list[Any] = []

    def __call__(self, peticion: httpx.Request) -> httpx.Response:
        self.peticiones.append(peticion)
        self.esperas.append(peticion.extensions.get("timeout", {}).get("read"))
        return self.responder(peticion)


@pytest.fixture(autouse=True)
def _destinos_ficticios(monkeypatch: pytest.MonkeyPatch) -> None:
    """Cada servicio vive en un host ficticio: nada depende de un backend real."""
    for nombre in SERVICIOS:
        monkeypatch.setenv(f"TUKIT_{nombre.upper()}_URL", f"http://{nombre}.example.test")


def _poner(monkeypatch: pytest.MonkeyPatch, responder: Callable[[httpx.Request], httpx.Response]) -> Atras:
    """Hace que la puerta hable con `responder` en vez de con la red.

    La puerta reenvia con UN cliente compartido que arma `crear_pool` en el
    primer uso (`api._cliente`, `60560b9`). Se cambia el `AsyncClient` que ese
    pool construye por uno con el transporte de mentira y las mismas opciones
    (espera, limites, el hook de la correlacion); un cliente que ya trae su
    transporte, como el de `_pedir`, no cambia. El `conftest` cierra y retira
    el pool al terminar cada prueba."""
    atras = Atras(responder)
    transporte = httpx.MockTransport(atras)

    class ClienteDeMentira(httpx.AsyncClient):
        def __init__(self, **opciones: Any) -> None:
            opciones.setdefault("transport", transporte)
            super().__init__(**opciones)

    monkeypatch.setattr(httpx, "AsyncClient", ClienteDeMentira)
    return atras


async def _pedir(metodo: str, ruta: str, **kw: Any) -> httpx.Response:
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://prueba") as cliente:
        return await cliente.request(metodo, ruta, **kw)


async def _pedir_crudo(ruta: str) -> tuple[int, dict[str, Any]]:
    """Entrega al ASGI una ruta SIN normalizar, como la dejaria un cliente que
    no resuelve `..` (por ejemplo `curl --path-as-is`): uvicorn solo decodifica
    los `%xx`, no colapsa los segmentos de punto."""
    mensajes: list[dict[str, Any]] = []

    async def recibir() -> dict[str, Any]:
        return {"type": "http.request", "body": b"", "more_body": False}

    async def enviar(mensaje: dict[str, Any]) -> None:
        mensajes.append(mensaje)

    alcance = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "GET",
        "scheme": "http",
        "path": ruta,
        "raw_path": ruta.encode(),
        "query_string": b"",
        "headers": [(b"host", b"prueba")],
        "client": ("127.0.0.1", 1),
        "server": ("prueba", 80),
    }
    await app(alcance, recibir, enviar)
    cuerpo = b"".join(m.get("body", b"") for m in mensajes[1:])
    return mensajes[0]["status"], json.loads(cuerpo)


class TestUnServicioCaidoEsUn503:
    @pytest.mark.parametrize(
        "fallo",
        [
            httpx.ConnectError("conexion rechazada"),
            httpx.ConnectTimeout("sin respuesta al conectar"),
            httpx.ReadTimeout("el pipeline no contesto"),
            httpx.RemoteProtocolError("el servicio cerro la conexion"),
        ],
        ids=["rechazada", "timeout-al-conectar", "timeout-de-lectura", "cierre-abrupto"],
    )
    async def test_cualquier_error_de_transporte_da_503_servicio_no_disponible(self, monkeypatch, fallo):
        def caido(peticion: httpx.Request) -> httpx.Response:
            raise fallo

        _poner(monkeypatch, caido)

        respuesta = await _pedir("GET", "/v1/catalogo/conceptos")

        assert respuesta.status_code == 503  # no 502: el de atras no fallo, no esta
        assert respuesta.json() == {
            "error": "servicio_no_disponible",
            "mensaje": "El servicio de catalogo no respondio en http://catalogo.example.test.",
            "detalle": str(fallo),
        }

    async def test_el_mensaje_nombra_el_servicio_que_corresponde_a_la_ruta(self, monkeypatch):
        def caido(peticion: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("no esta")

        _poner(monkeypatch, caido)

        # Bajo /v1/ordenes la puerta solo expone el avance (173ee80, api.py:154-161).
        respuesta = await _pedir("POST", "/v1/ordenes/orden-ficticia/avanzar", json={})

        assert respuesta.status_code == 503
        assert "El servicio de comercio" in respuesta.json()["mensaje"]
        assert "http://comercio.example.test" in respuesta.json()["mensaje"]

    async def test_un_error_http_del_servicio_no_es_un_fallo_de_la_puerta(self, monkeypatch):
        """El 500 de atras es la respuesta de atras: se devuelve tal cual, no se
        maquilla como 503 (el servicio SI esta)."""
        _poner(monkeypatch, lambda p: httpx.Response(500, json={"error": "fallo_interno"}))

        respuesta = await _pedir("GET", "/v1/catalogo/conceptos")

        assert respuesta.status_code == 500
        assert respuesta.json() == {"error": "fallo_interno"}


class TestUnaRutaInternaSeVeComoInexistente:
    async def test_la_bloqueada_recibe_la_misma_respuesta_que_la_desconocida_y_no_toca_a_nadie(
        self, monkeypatch
    ):
        atras = _poner(monkeypatch, lambda p: httpx.Response(200, json={"interno": True}))

        bloqueada = await _pedir("GET", "/v1/comercio/pedidos-pagados")
        desconocida = await _pedir("GET", "/v1/comercio-inventado/pedidos-pagados")

        assert bloqueada.status_code == desconocida.status_code == 404
        cuerpo_bloqueada, cuerpo_desconocida = bloqueada.json(), desconocida.json()
        assert cuerpo_bloqueada["error"] == cuerpo_desconocida["error"] == "ruta_desconocida"
        assert cuerpo_bloqueada["rutas"] == cuerpo_desconocida["rutas"] == sorted(RUTAS)
        # El unico dato propio del mensaje es el camino que el cliente ya sabia.
        assert cuerpo_bloqueada["mensaje"] == "La puerta no atiende /v1/comercio/pedidos-pagados."
        assert cuerpo_desconocida["mensaje"] == "La puerta no atiende /v1/comercio-inventado/pedidos-pagados."
        assert set(cuerpo_bloqueada) == set(cuerpo_desconocida) == {"error", "mensaje", "rutas"}
        assert atras.peticiones == []  # ni la interna ni la desconocida llegaron al servicio

    @pytest.mark.parametrize("metodo", ["GET", "POST", "PUT", "PATCH", "DELETE"])
    async def test_el_bloqueo_no_depende_del_metodo(self, monkeypatch, metodo):
        atras = _poner(monkeypatch, lambda p: httpx.Response(200))

        respuesta = await _pedir(metodo, "/v1/comercio/pedidos-pagados")

        assert respuesta.status_code == 404
        assert atras.peticiones == []

    @pytest.mark.parametrize(
        "ruta",
        [
            "/v1/comercio/pedidos-pagados/",
            "/v1/comercio/pedidos-pagados/algo/mas",
            "/v1/comercio/pedidos%2Dpagados",  # el cliente codifica un guion
        ],
    )
    async def test_el_bloqueo_alcanza_a_los_subcaminos_y_a_la_codificacion_porcentual(
        self, monkeypatch, ruta
    ):
        atras = _poner(monkeypatch, lambda p: httpx.Response(200))

        respuesta = await _pedir("GET", ruta)

        assert respuesta.status_code == 404
        assert atras.peticiones == []

    async def test_el_resto_de_comercio_sigue_pasando(self, monkeypatch):
        atras = _poner(monkeypatch, lambda p: httpx.Response(200, json={"pedidos": []}))

        respuesta = await _pedir("GET", "/v1/comercio/pedidos")

        assert respuesta.status_code == 200
        assert [str(p.url) for p in atras.peticiones] == ["http://comercio.example.test/v1/comercio/pedidos"]

    @pytest.mark.parametrize(
        "ruta",
        ["/v1/comercio/pedidos/../pedidos-pagados", "/v1/comercio/./pedidos-pagados"],
        ids=["punto-punto", "punto"],
    )
    async def test_un_camino_con_segmentos_de_punto_no_esquiva_el_bloqueo(self, monkeypatch, ruta):
        """La ruta interna debe verse como inexistente desde fuera. Era H-A-06:
        `bloqueada` y `destino` miraban el camino sin normalizar, y httpx
        colapsaba los puntos al reenviar, asi que comercio recibia
        `/v1/comercio/pedidos-pagados`. Desde `173ee80`, `ambigua`
        (api.py:178-189) rechaza cualquier segmento `.`/`..` antes de rutear:
        queda como prueba de no regresion."""
        atras = _poner(monkeypatch, lambda p: httpx.Response(200, json={"interno": True}))

        estado, _ = await _pedir_crudo(ruta)

        assert estado == 404
        assert [str(p.url) for p in atras.peticiones] == []


class TestLoQueViajaHaciaAtras:
    async def test_metodo_url_consulta_y_cuerpo_llegan_intactos(self, monkeypatch):
        atras = _poner(monkeypatch, lambda p: httpx.Response(201, json={"ok": True}))

        respuesta = await _pedir(
            "POST",
            # El avance es la unica ruta de /v1/ordenes que la puerta expone (173ee80).
            "/v1/ordenes/orden-ficticia/avanzar?modo=falso&moneda=COP",
            content=b'{"referencia": "ref-ficticia"}',
            headers={"content-type": "application/json"},
        )

        (peticion,) = atras.peticiones
        assert respuesta.status_code == 201
        assert peticion.method == "POST"
        assert peticion.url.scheme == "http"
        assert peticion.url.host == "comercio.example.test"
        assert peticion.url.path == "/v1/ordenes/orden-ficticia/avanzar"
        assert dict(peticion.url.params) == {"modo": "falso", "moneda": "COP"}
        assert peticion.content == b'{"referencia": "ref-ficticia"}'
        assert peticion.headers["content-type"] == "application/json"

    @pytest.mark.parametrize("metodo", ["GET", "POST", "PUT", "PATCH", "DELETE"])
    async def test_cada_metodo_se_reenvia_como_llego(self, monkeypatch, metodo):
        atras = _poner(monkeypatch, lambda p: httpx.Response(200))

        await _pedir(metodo, "/v1/operacion/casos")

        assert [p.method for p in atras.peticiones] == [metodo]

    async def test_cada_prefijo_pega_en_el_host_de_su_servicio(self, monkeypatch):
        atras = _poner(monkeypatch, lambda p: httpx.Response(200))

        for ruta in (
            "/v1/catalogo/x",
            "/v1/colegios",
            "/v1/trabajos/x",
            "/v1/comercio/pedidos",
            "/v1/operacion/casos",
        ):
            await _pedir("GET", ruta)

        assert [p.url.host for p in atras.peticiones] == [
            "catalogo.example.test",
            "identidad.example.test",
            "inteligencia.example.test",
            "comercio.example.test",
            "operacion.example.test",
        ]

    async def test_la_url_de_un_servicio_sale_del_entorno_sin_barra_final(self, monkeypatch):
        monkeypatch.setenv("TUKIT_CATALOGO_URL", "http://otro-catalogo.example.test:9000/")
        atras = _poner(monkeypatch, lambda p: httpx.Response(200))

        await _pedir("GET", "/v1/catalogo/conceptos")

        assert str(atras.peticiones[0].url) == "http://otro-catalogo.example.test:9000/v1/catalogo/conceptos"

    async def test_el_token_viaja_intacto_y_las_cabeceras_de_salto_no(self, monkeypatch):
        atras = _poner(monkeypatch, lambda p: httpx.Response(200))

        await _pedir(
            "GET",
            "/v1/sesiones/actual",
            headers={
                "authorization": "Bearer token-ficticio",
                "connection": "close",
                "keep-alive": "timeout=5",
                "x-otra": "valor",
            },
        )

        cabeceras = atras.peticiones[0].headers
        assert cabeceras["authorization"] == "Bearer token-ficticio"  # la validacion es de identidad
        assert cabeceras["x-otra"] == "valor"
        assert cabeceras["host"] == "identidad.example.test"  # no el de la puerta
        assert "keep-alive" not in cabeceras
        # El `close` del cliente no se hereda: la conexion hacia atras es de la puerta
        # (httpx pone la suya, `keep-alive`).
        assert cabeceras["connection"] == "keep-alive"

    async def test_el_cliente_hacia_atras_espera_los_trescientos_segundos_del_pipeline(self, monkeypatch):
        atras = _poner(monkeypatch, lambda p: httpx.Response(200))

        await _pedir("GET", "/v1/trabajos/x")

        assert atras.esperas == [ESPERA_SEGUNDOS] == [300.0]


class TestLaCorrelacionSeAcunaEnElBorde:
    async def test_sin_id_la_puerta_acuna_uno_y_lo_comparte_con_atras_y_con_el_cliente(self, monkeypatch):
        atras = _poner(monkeypatch, lambda p: httpx.Response(200))

        respuesta = await _pedir("GET", "/v1/catalogo/conceptos")

        enviado = atras.peticiones[0].headers["x-correlation-id"]
        assert enviado
        assert respuesta.headers["x-correlation-id"] == enviado

    async def test_un_id_entrante_se_respeta_y_se_propaga(self, monkeypatch):
        atras = _poner(monkeypatch, lambda p: httpx.Response(200))

        respuesta = await _pedir(
            "GET", "/v1/catalogo/conceptos", headers={"x-correlation-id": "req-del-cliente"}
        )

        assert atras.peticiones[0].headers["x-correlation-id"] == "req-del-cliente"
        assert respuesta.headers["x-correlation-id"] == "req-del-cliente"

    async def test_dos_peticiones_sin_id_reciben_ids_distintos(self, monkeypatch):
        atras = _poner(monkeypatch, lambda p: httpx.Response(200))

        await _pedir("GET", "/v1/catalogo/a")
        await _pedir("GET", "/v1/catalogo/b")

        primero, segundo = (p.headers["x-correlation-id"] for p in atras.peticiones)
        assert primero != segundo

    async def test_el_503_tambien_lleva_la_correlacion_para_poder_rastrearlo(self, monkeypatch):
        def caido(peticion: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("no esta")

        _poner(monkeypatch, caido)

        respuesta = await _pedir("GET", "/v1/catalogo/x", headers={"x-correlation-id": "req-503"})

        assert respuesta.status_code == 503
        assert respuesta.headers["x-correlation-id"] == "req-503"


class TestLoQueVuelveAlCliente:
    async def test_estado_cuerpo_y_tipo_de_contenido_pasan_sin_tocarse(self, monkeypatch):
        _poner(
            monkeypatch,
            lambda p: httpx.Response(
                409,
                content=b'{"error": "estado_incompatible"}',
                headers={"content-type": "application/json", "x-propia": "del-servicio"},
            ),
        )

        # Una ruta publica: las de `/v1/admin` piden sesion del equipo (46a0c4a) y
        # aqui se mide el reenvio, no la puerta de la consola (test_admin_sesion.py).
        respuesta = await _pedir("PATCH", "/v1/listas/abc")

        assert respuesta.status_code == 409
        assert respuesta.content == b'{"error": "estado_incompatible"}'
        assert respuesta.headers["content-type"] == "application/json"
        assert respuesta.headers["x-propia"] == "del-servicio"

    async def test_un_cuerpo_binario_llega_byte_a_byte(self, monkeypatch):
        pdf = b"%PDF-1.4\x00\xff\xfe binario"
        _poner(
            monkeypatch,
            lambda p: httpx.Response(200, content=pdf, headers={"content-type": "application/pdf"}),
        )

        respuesta = await _pedir("GET", "/v1/listas/abc/documento")

        assert respuesta.content == pdf
        assert respuesta.headers["content-type"] == "application/pdf"

    async def test_las_cabeceras_de_salto_del_servicio_no_llegan_al_cliente(self, monkeypatch):
        _poner(monkeypatch, lambda p: httpx.Response(200, content=b"ok", headers={"keep-alive": "timeout=5"}))

        respuesta = await _pedir("GET", "/v1/catalogo/conceptos")

        assert "keep-alive" not in respuesta.headers
        assert respuesta.headers["content-length"] == "2"  # la recalcula la puerta, no la copia

    async def test_un_204_sin_cuerpo_se_devuelve_sin_cuerpo(self, monkeypatch):
        _poner(monkeypatch, lambda p: httpx.Response(204))

        respuesta = await _pedir("DELETE", "/v1/cuenta/direcciones/abc")

        assert respuesta.status_code == 204
        assert respuesta.content == b""


class TestLasRutasPendientesDan501:
    async def test_un_501_con_la_seccion_del_contrato_y_sin_tocar_al_servicio(self, monkeypatch):
        monkeypatch.setattr(api, "PENDIENTES", {"/v1/futuro": "9"})
        atras = _poner(monkeypatch, lambda p: httpx.Response(200))

        respuesta = await _pedir("GET", "/v1/futuro/cosa")

        assert respuesta.status_code == 501
        assert respuesta.json() == {
            "error": "no_implementado",
            "mensaje": (
                "/v1/futuro/cosa esta en el contrato (seccion 9) y todavia no hay servicio detras. "
                "No cambies el cliente: la URL es la correcta."
            ),
            "seccion_contrato": "9",
        }
        assert atras.peticiones == []

    async def test_un_501_no_se_confunde_con_el_404_de_ruta_desconocida(self, monkeypatch):
        monkeypatch.setattr(api, "PENDIENTES", {"/v1/futuro": "9"})
        _poner(monkeypatch, lambda p: httpx.Response(200))

        pendiente = await _pedir("GET", "/v1/futuro")
        inventada = await _pedir("GET", "/v1/inventado")

        assert (pendiente.status_code, inventada.status_code) == (501, 404)
        assert "rutas" not in pendiente.json()

    async def test_un_prefijo_solo_parecido_no_es_pendiente(self, monkeypatch):
        monkeypatch.setattr(api, "PENDIENTES", {"/v1/futuro": "9"})
        _poner(monkeypatch, lambda p: httpx.Response(200))

        respuesta = await _pedir("GET", "/v1/futuros")

        assert respuesta.status_code == 404


class TestLaSondaDeServicios:
    async def test_con_todos_listos_todos_arriba(self, monkeypatch):
        atras = _poner(monkeypatch, lambda p: httpx.Response(200, json={"estado": "listo"}))

        cuerpo = (await _pedir("GET", "/v1/servicios")).json()

        assert cuerpo["todos_arriba"] is True
        assert cuerpo["servicios"] == {
            nombre: {"url": f"http://{nombre}.example.test", "arriba": True} for nombre in SERVICIOS
        }
        # Se pregunta por READINESS (base incluida), no por liveness.
        assert sorted(str(p.url) for p in atras.peticiones) == sorted(
            f"http://{nombre}.example.test/health/ready" for nombre in SERVICIOS
        )
        # Cada sonda espera 5 s, no los 300 del pool.
        assert atras.esperas == [5.0] * len(SERVICIOS)

    async def test_un_servicio_caido_no_oculta_a_los_demas_y_dice_por_que(self, monkeypatch):
        def responder(peticion: httpx.Request) -> httpx.Response:
            if peticion.url.host == "comercio.example.test":
                raise httpx.ConnectError("conexion rechazada")
            return httpx.Response(200)

        _poner(monkeypatch, responder)

        cuerpo = (await _pedir("GET", "/v1/servicios")).json()

        assert cuerpo["todos_arriba"] is False
        assert cuerpo["servicios"]["comercio"] == {
            "url": "http://comercio.example.test",
            "arriba": False,
            "detalle": "conexion rechazada",
        }
        assert [n for n, s in cuerpo["servicios"].items() if s["arriba"]] == [
            "catalogo",
            "identidad",
            "inteligencia",
            "operacion",
        ]

    @pytest.mark.parametrize("estado", [500, 503, 404, 204])
    async def test_un_servicio_vivo_pero_no_listo_no_cuenta_como_arriba(self, monkeypatch, estado):
        """Un 503 de readiness (base caida) es la verdad que evita perder la
        tarde con un 502 rio abajo: solo el 200 cuenta."""
        _poner(
            monkeypatch,
            lambda p: httpx.Response(estado if p.url.host == "identidad.example.test" else 200),
        )

        cuerpo = (await _pedir("GET", "/v1/servicios")).json()

        assert cuerpo["servicios"]["identidad"] == {"url": "http://identidad.example.test", "arriba": False}
        assert cuerpo["todos_arriba"] is False

    async def test_con_los_cinco_caidos_el_detalle_de_cada_uno_se_conserva(self, monkeypatch):
        def caido(peticion: httpx.Request) -> httpx.Response:
            raise httpx.ConnectTimeout(f"sin respuesta de {peticion.url.host}")

        _poner(monkeypatch, caido)

        cuerpo = (await _pedir("GET", "/v1/servicios")).json()

        assert cuerpo["todos_arriba"] is False
        assert all(not s["arriba"] for s in cuerpo["servicios"].values())
        assert cuerpo["servicios"]["catalogo"]["detalle"] == "sin respuesta de catalogo.example.test"
        assert cuerpo["servicios"]["operacion"]["detalle"] == "sin respuesta de operacion.example.test"

    async def test_la_sonda_propia_de_la_puerta_no_depende_de_los_servicios(self, monkeypatch):
        def caido(peticion: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("no esta")

        _poner(monkeypatch, caido)

        assert (await _pedir("GET", "/salud")).json()["estado"] == "ok"
        assert (await _pedir("GET", "/health/ready")).json() == {
            "estado": "listo",
            "servicio": "Tukit Gateway",
        }


class TestLosServiciosPorOmision:
    def test_cada_servicio_tiene_su_puerto_de_desarrollo(self, monkeypatch):
        for nombre in SERVICIOS:
            monkeypatch.delenv(f"TUKIT_{nombre.upper()}_URL")

        assert api._servicios() == {
            "catalogo": "http://127.0.0.1:8012",
            "identidad": "http://127.0.0.1:8011",
            "inteligencia": "http://127.0.0.1:8013",
            "comercio": "http://127.0.0.1:8014",
            "operacion": "http://127.0.0.1:8015",
        }


class TestElPuntoDeEntrada:
    def test_main_levanta_uvicorn_en_el_puerto_de_la_puerta_por_omision(self, monkeypatch):
        llamadas: list[tuple[Any, dict[str, Any]]] = []
        monkeypatch.setitem(
            sys.modules,
            "uvicorn",
            SimpleNamespace(run=lambda aplicacion, **kw: llamadas.append((aplicacion, kw))),
        )

        assert api.main([]) == 0

        assert llamadas == [
            (
                app,
                {
                    "host": "127.0.0.1",
                    "port": PUERTO_POR_OMISION,
                    "log_level": "info",
                    "proxy_headers": False,
                },
            )
        ]
        assert PUERTO_POR_OMISION == 8010

    def test_main_respeta_host_y_puerto_pedidos(self, monkeypatch):
        llamadas: list[tuple[Any, dict[str, Any]]] = []
        monkeypatch.setitem(
            sys.modules,
            "uvicorn",
            SimpleNamespace(run=lambda aplicacion, **kw: llamadas.append((aplicacion, kw))),
        )

        assert api.main(["--puerto", "9100", "--host", "0.0.0.0"]) == 0

        assert llamadas[0][1] == {
            "host": "0.0.0.0",
            "port": 9100,
            "log_level": "info",
            "proxy_headers": False,
        }

    def test_un_puerto_que_no_es_numero_se_rechaza_antes_de_levantar_nada(self, monkeypatch):
        llamadas: list[Any] = []
        monkeypatch.setitem(sys.modules, "uvicorn", SimpleNamespace(run=lambda *a, **kw: llamadas.append(a)))

        with pytest.raises(SystemExit) as salida:
            api.main(["--puerto", "ocho-mil"])

        assert salida.value.code == 2
        assert llamadas == []

    def test_ejecutado_como_modulo_sale_con_el_codigo_que_devuelve_main(self, monkeypatch):
        """`python -m tukit_gateway.api` termina con `SystemExit(0)` tras servir."""
        llamadas: list[dict[str, Any]] = []
        monkeypatch.setitem(
            sys.modules, "uvicorn", SimpleNamespace(run=lambda aplicacion, **kw: llamadas.append(kw))
        )
        monkeypatch.setattr(sys, "argv", ["tukit_gateway.api", "--puerto", "9200"])

        with pytest.warns(RuntimeWarning), pytest.raises(SystemExit) as salida:
            runpy.run_module("tukit_gateway.api", run_name="__main__")

        assert salida.value.code == 0
        assert llamadas == [{"host": "127.0.0.1", "port": 9200, "log_level": "info", "proxy_headers": False}]
