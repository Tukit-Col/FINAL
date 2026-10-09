"""NFR-MAN-01: Los clientes remotos de Inteligencia (catalogo, identidad, comercio) y su disyuntor.

`remoto.py` es la unica puerta por la que el pipeline ve a los otros servicios
(invariantes 1 y 3), y su decision interesante es COMO DEGRADAR: sin catalogo no
hay pipeline (`RemotoCaido`, trabajo fallido y reintentable), sin identidad si
(el kit se arma sin destinatario), y un rechazo de negocio de Comercio es una
respuesta, no un fallo. Estas pruebas fijan esas reglas contra un destino falso
en memoria (`httpx.MockTransport`): ni sockets ni servicios levantados.

Lo que se caracteriza, por orden de importancia:

- el disyuntor por-destino (ADR 0020): tras `umbral` fallos el destino deja de
  recibir llamadas y el cliente degrada a `RemotoCaido` sin tocarlo; pasado el
  `ttl` deja pasar UNA prueba, y un exito lo cierra mientras un fallo lo reabre;
- el reintento SOLO en GET: reintentar un POST (crear orden, iniciar pago,
  importar una lista) es un doble efecto; los GET insisten tres veces con backoff;
- cada metodo pide la ruta, el verbo y los parametros del contrato;
- los errores 4xx/5xx, el timeout y la caida de red se traducen a la excepcion de
  dominio que cada cliente promete (`RemotoCaido`, `None` o `(estado, cuerpo)`).

El disyuntor es un registro global por proceso: cada prueba arranca con uno vacio
(`_disyuntores` sustituido) y el `asyncio.sleep` del backoff de tenacity se
registra sin esperar, asi que ninguna prueba duerme.

Cuatro defectos reales quedan marcados `xfail` estricto (ver cada prueba): el
catalogo trata un 4xx como caida, Comercio no cuenta los 5xx en su disyuntor,
Identidad no tiene disyuntor y `registrar_contacto` devuelve la cadena "None".
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import Callable
from typing import Any

import httpx
import pytest
from tukit_comun import resiliencia
from tukit_comun.resiliencia import Disyuntor
from tukit_inteligencia.remoto import (
    ESPERA_SEGUNDOS,
    ClienteCatalogo,
    ClienteComercio,
    ClienteIdentidad,
    RemotoCaido,
    url_catalogo,
    url_comercio,
    url_identidad,
)

pytestmark = pytest.mark.nfr("NFR-MAN-01")

BASE = "http://destino.prueba"
USUARIO = "22222222-2222-5222-8222-222222222222"


# --- Utilidades --------------------------------------------------------------


class Destino:
    """Un destino falso: responde segun un guion y anota cada peticion que recibe.

    Cada elemento del guion es una `httpx.Response`, una excepcion (que se
    levanta, como lo haria la red) o un callable `peticion -> respuesta`. Cuando
    el guion se agota se repite el ultimo elemento: un destino "caido" es un
    guion de un solo `503`.
    """

    def __init__(self, *guion: httpx.Response | Exception | Callable[[httpx.Request], httpx.Response]):
        self._guion = list(guion)
        self.peticiones: list[httpx.Request] = []

    def __call__(self, peticion: httpx.Request) -> httpx.Response:
        self.peticiones.append(peticion)
        paso = self._guion.pop(0) if len(self._guion) > 1 else self._guion[0]
        if isinstance(paso, Exception):
            raise paso
        if callable(paso):
            return paso(peticion)
        return paso

    @property
    def llamadas(self) -> int:
        return len(self.peticiones)

    @property
    def ultima(self) -> httpx.Request:
        return self.peticiones[-1]

    def cuerpo_enviado(self) -> Any:
        return json.loads(self.ultima.content)


def ok(cuerpo: Any = None, estado: int = 200) -> httpx.Response:
    return httpx.Response(estado, json={} if cuerpo is None else cuerpo)


def caido(estado: int = 503) -> httpx.Response:
    return httpx.Response(estado, json={"detail": "caido"})


@pytest.fixture(autouse=True)
def disyuntores_vacios(monkeypatch):
    """Cada prueba parte con el registro de disyuntores vacio.

    `disyuntor_de` consulta el diccionario del modulo en cada llamada, asi que
    sustituirlo aisla la prueba sin tocar el codigo del producto y sin que el
    estado de un circuito abierto se filtre a la siguiente.
    """
    registro: dict[str, Disyuntor] = {}
    monkeypatch.setattr(resiliencia, "_disyuntores", registro)
    return registro


@pytest.fixture(autouse=True)
def pausas(monkeypatch):
    """El backoff de tenacity duerme con `asyncio.sleep`: aqui solo se anota."""
    dormidas: list[float] = []

    async def _sin_espera(segundos: float, *_a: Any, **_k: Any) -> None:
        dormidas.append(segundos)

    monkeypatch.setattr(asyncio, "sleep", _sin_espera)
    return dormidas


@pytest.fixture()
async def fabrica():
    """Construye un cliente httpx sobre un `Destino` y lo cierra al terminar."""
    abiertos: list[httpx.AsyncClient] = []

    def _construir(destino: Destino) -> httpx.AsyncClient:
        http = httpx.AsyncClient(transport=httpx.MockTransport(destino))
        abiertos.append(http)
        return http

    yield _construir
    for http in abiertos:
        await http.aclose()


class Reloj:
    """Reloj inyectado al disyuntor: el TTL se cruza sin esperar."""

    def __init__(self) -> None:
        self.ahora = 0.0

    def __call__(self) -> float:
        return self.ahora


def circuito(registro: dict[str, Disyuntor], destino: str, *, umbral: int = 5, reloj: Reloj | None = None):
    """Siembra en el registro un disyuntor con umbral y reloj controlados."""
    d = Disyuntor(destino, umbral=umbral, ttl=30.0, reloj=reloj or Reloj())
    registro[destino] = d
    return d


def catalogo_sobre(fabrica, destino: Destino) -> ClienteCatalogo:
    return ClienteCatalogo(base=BASE, cliente=fabrica(destino))


def identidad_sobre(fabrica, destino: Destino) -> ClienteIdentidad:
    return ClienteIdentidad(base=BASE, cliente=fabrica(destino))


def comercio_sobre(fabrica, destino: Destino) -> ClienteComercio:
    return ClienteComercio(base=BASE, cliente=fabrica(destino))


# --- Direcciones por omision y por entorno -----------------------------------


class TestDireccionesDeLosServicios:
    def test_sin_entorno_son_los_puertos_del_arranque_local(self, monkeypatch):
        """El contrato fija catalogo en 8012 e identidad en 8011; comercio va en 8014."""
        for variable in ("TUKIT_CATALOGO_URL", "TUKIT_IDENTIDAD_URL", "TUKIT_COMERCIO_URL"):
            monkeypatch.delenv(variable, raising=False)

        assert url_catalogo() == "http://127.0.0.1:8012"
        assert url_identidad() == "http://127.0.0.1:8011"
        assert url_comercio() == "http://127.0.0.1:8014"

    def test_el_entorno_manda_y_se_quita_la_barra_final(self, monkeypatch):
        """Una barra final en la variable duplicaria la barra de la ruta (`//v1/...`)."""
        monkeypatch.setenv("TUKIT_CATALOGO_URL", "http://catalogo.interno:9000/")
        monkeypatch.setenv("TUKIT_IDENTIDAD_URL", "http://identidad.interna:9001//")
        monkeypatch.setenv("TUKIT_COMERCIO_URL", "http://comercio.interno:9002/")

        assert url_catalogo() == "http://catalogo.interno:9000"
        assert url_identidad() == "http://identidad.interna:9001"
        assert url_comercio() == "http://comercio.interno:9002"

    async def test_un_cliente_sin_base_pide_a_la_url_del_entorno(self, monkeypatch, fabrica):
        monkeypatch.setenv("TUKIT_CATALOGO_URL", "http://catalogo.interno:9000/")
        destino = Destino(ok({"lista_id": "abc"}))
        cliente = ClienteCatalogo(cliente=fabrica(destino))

        await cliente.lista("abc")

        assert destino.ultima.url.host == "catalogo.interno"
        assert destino.ultima.url.port == 9000
        assert destino.ultima.url.path == "/v1/listas/abc"


# --- ClienteCatalogo: rutas, verbos y cuerpos --------------------------------


class TestCatalogoPideLoQueElContratoDice:
    async def test_listas_pide_la_primera_pagina_del_colegio_y_grado(self, fabrica):
        destino = Destino(ok({"listas": [{"lista_id": "l-1"}, {"lista_id": "l-2"}]}))

        listas = await catalogo_sobre(fabrica, destino).listas(colegio_id="col-1", grado="Cuarto")

        assert listas == [{"lista_id": "l-1"}, {"lista_id": "l-2"}]
        assert destino.ultima.method == "GET"
        assert destino.ultima.url.path == "/v1/listas"
        # Sin anio lectivo el parametro NO viaja: el catalogo elige el vigente.
        assert dict(destino.ultima.url.params) == {
            "colegio_id": "col-1",
            "grado": "Cuarto",
            "por_pagina": "5",
        }

    async def test_listas_con_anio_lo_envia_y_sin_clave_devuelve_vacio(self, fabrica):
        destino = Destino(ok({}))

        listas = await catalogo_sobre(fabrica, destino).listas(
            colegio_id="col-1", grado="Cuarto", anio_lectivo=2026
        )

        assert listas == []
        assert destino.ultima.url.params["anio_lectivo"] == "2026"

    @pytest.mark.parametrize(
        ("metodo", "argumentos", "ruta"),
        [
            ("lista", ("lista-9",), "/v1/listas/lista-9"),
            ("revision", ("ver-3",), "/v1/admin/listas/ver-3/revision"),
            ("producto", ("SKU-77",), "/v1/catalogo/productos/SKU-77"),
            ("resueltos", ("ver-3",), "/v1/admin/listas/ver-3/resueltos"),
        ],
    )
    async def test_las_lecturas_por_id_son_get_a_su_ruta_y_devuelven_el_cuerpo(
        self, fabrica, metodo, argumentos, ruta
    ):
        cuerpo = {"clave": "valor", "items": [1, 2]}
        destino = Destino(ok(cuerpo))

        recibido = await getattr(catalogo_sobre(fabrica, destino), metodo)(*argumentos)

        assert recibido == cuerpo
        assert (destino.ultima.method, destino.ultima.url.path) == ("GET", ruta)

    async def test_producto_de_personaje_devuelve_el_primero_o_none(self, fabrica):
        con_producto = Destino(ok({"productos": [{"sku": "A"}, {"sku": "B"}]}))
        sin_producto = Destino(ok({"productos": []}))

        primero = await catalogo_sobre(fabrica, con_producto).producto_de_personaje("C001", "Estrella")
        ninguno = await catalogo_sobre(fabrica, sin_producto).producto_de_personaje("C001", "Estrella")

        assert primero == {"sku": "A"}
        assert ninguno is None
        assert con_producto.ultima.url.path == "/v1/catalogo/productos"
        assert dict(con_producto.ultima.url.params) == {
            "concepto": "C001",
            "personaje": "Estrella",
            "por_pagina": "1",
        }

    async def test_listas_por_contacto_cuelga_de_interno_y_tolera_cuerpo_sin_listas(self, fabrica):
        destino = Destino(ok({"listas": [{"version_id": "v-1"}]}), ok({}))
        cliente = catalogo_sobre(fabrica, destino)

        con_listas = await cliente.listas_por_contacto(USUARIO)
        sin_clave = await cliente.listas_por_contacto(USUARIO)

        assert con_listas == [{"version_id": "v-1"}]
        assert sin_clave == []
        assert destino.ultima.url.path == f"/interno/listas-por-contacto/{USUARIO}"

    async def test_emparejar_es_post_con_los_renglones_y_devuelve_los_emparejamientos(self, fabrica):
        destino = Destino(ok({"emparejamientos": [{"texto": "lapiz", "estado": "reconocido"}]}))

        resultado = await catalogo_sobre(fabrica, destino).emparejar(["lapiz", "borrador"])

        assert resultado == [{"texto": "lapiz", "estado": "reconocido"}]
        assert (destino.ultima.method, destino.ultima.url.path) == ("POST", "/v1/catalogo/emparejar")
        assert destino.cuerpo_enviado() == {"renglones": ["lapiz", "borrador"]}

    async def test_emparejar_sin_clave_devuelve_lista_vacia(self, fabrica):
        destino = Destino(ok({}))
        assert await catalogo_sobre(fabrica, destino).emparejar(["lapiz"]) == []


class TestImportarListaArmaElCuerpo:
    async def test_minimo_lleva_la_evidencia_y_omite_lo_opcional(self, fabrica):
        destino = Destino(ok({"version_id": "ver-1"}, 201))

        respuesta = await catalogo_sobre(fabrica, destino).importar_lista(
            colegio_id="col-1",
            grado="Cuarto",
            anio_lectivo=2026,
            items=[{"texto_original": "lapiz", "cantidad": 2}],
            documento_base64="UERG",
            percepcion_cruda=[{"pagina": 1, "crudo": "2 lapiz"}],
        )

        assert respuesta == {"version_id": "ver-1"}
        assert (destino.ultima.method, destino.ultima.url.path) == ("POST", "/v1/admin/listas/importar")
        assert destino.cuerpo_enviado() == {
            "colegio_id": "col-1",
            "grado": "Cuarto",
            "anio_lectivo": 2026,
            "items": [{"texto_original": "lapiz", "cantidad": 2}],
            "origen": "onboarding",
            "evidencia": {
                "documento_base64": "UERG",
                "percepcion_cruda": [{"pagina": 1, "crudo": "2 lapiz"}],
            },
        }

    async def test_los_opcionales_viajan_solo_si_traen_algo(self, fabrica):
        destino = Destino(ok({"version_id": "ver-1"}, 201))
        cliente = catalogo_sobre(fabrica, destino)
        base = {
            "colegio_id": "col-1",
            "grado": "Cuarto",
            "anio_lectivo": 2026,
            "items": [],
            "documento_base64": "",
            "percepcion_cruda": [],
        }

        # Vacios o None: no viajan (el catalogo no debe ver llaves en blanco).
        await cliente.importar_lista(**base, contacto_referencia=None, preferencias={}, colegio_datos={})
        vacio = destino.cuerpo_enviado()
        assert not {"contacto_referencia", "preferencias", "colegio_datos"} & set(vacio)

        await cliente.importar_lista(
            **base,
            contacto_referencia=USUARIO,
            preferencias={"disposicion_sobreprecio": 0.1},
            colegio_datos={"dane": "111001", "nombre": "Colegio Ficticio Uno"},
            origen="sugerencia_padre",
        )
        lleno = destino.cuerpo_enviado()
        assert lleno["contacto_referencia"] == USUARIO
        assert lleno["preferencias"] == {"disposicion_sobreprecio": 0.1}
        assert lleno["colegio_datos"] == {"dane": "111001", "nombre": "Colegio Ficticio Uno"}
        assert lleno["origen"] == "sugerencia_padre"


# --- ClienteCatalogo: errores traducidos a RemotoCaido -----------------------


class TestCatalogoTraduceLosFalloAUnaCaida:
    @pytest.mark.parametrize("estado", [404, 422, 500, 503])
    async def test_un_estado_de_error_es_remoto_caido_con_el_codigo_y_la_ruta(self, fabrica, estado):
        destino = Destino(caido(estado))

        with pytest.raises(RemotoCaido) as info:
            await catalogo_sobre(fabrica, destino).lista("lista-9")

        assert info.value.servicio == "catalogo"
        assert info.value.detalle == f"/v1/listas/lista-9 respondio {estado}"

    async def test_un_timeout_es_remoto_caido_no_respondio(self, fabrica):
        destino = Destino(httpx.ReadTimeout("lento"))

        with pytest.raises(RemotoCaido) as info:
            await catalogo_sobre(fabrica, destino).emparejar(["lapiz"])

        assert info.value.servicio == "catalogo"
        assert "no respondio" in info.value.detalle
        assert "/v1/catalogo/emparejar" in info.value.detalle

    async def test_una_caida_de_red_es_remoto_caido(self, fabrica):
        destino = Destino(httpx.ConnectError("conexion rechazada"))

        with pytest.raises(RemotoCaido) as info:
            await catalogo_sobre(fabrica, destino).producto("SKU-1")

        assert info.value.servicio == "catalogo"
        assert "conexion rechazada" in info.value.detalle

    def test_remoto_caido_expone_servicio_y_detalle_y_los_junta_en_el_mensaje(self):
        error = RemotoCaido("catalogo", "circuito abierto")

        assert (error.servicio, error.detalle) == ("catalogo", "circuito abierto")
        assert str(error) == "catalogo: circuito abierto"


# --- Reintento: solo GET -----------------------------------------------------


class TestElReintentoEsSoloParaLecturas:
    async def test_un_get_que_falla_se_intenta_tres_veces_con_backoff(self, fabrica, pausas):
        destino = Destino(caido(503))

        with pytest.raises(RemotoCaido) as info:
            await catalogo_sobre(fabrica, destino).lista("lista-9")

        assert destino.llamadas == 3
        assert info.value.detalle.endswith("respondio 503")
        # Backoff exponencial (0.2 s, luego 0.4 s) sin dormir de verdad.
        assert pausas == [0.2, 0.4]

    async def test_un_get_se_recupera_si_un_reintento_responde(self, fabrica, pausas):
        destino = Destino(caido(503), httpx.ConnectError("blip"), ok({"lista_id": "lista-9"}))

        cuerpo = await catalogo_sobre(fabrica, destino).lista("lista-9")

        assert cuerpo == {"lista_id": "lista-9"}
        assert destino.llamadas == 3
        assert len(pausas) == 2

    @pytest.mark.parametrize("fallo", [caido(503), httpx.ReadTimeout("lento"), httpx.ConnectError("caido")])
    async def test_un_post_jamas_se_reintenta(self, fabrica, pausas, fallo):
        """Reintentar el POST de `emparejar`/`importar` duplicaria la importacion."""
        destino = Destino(fallo)
        cliente = catalogo_sobre(fabrica, destino)

        with pytest.raises(RemotoCaido):
            await cliente.emparejar(["lapiz"])
        assert destino.llamadas == 1

        with pytest.raises(RemotoCaido):
            await cliente.importar_lista(
                colegio_id="c",
                grado="g",
                anio_lectivo=2026,
                items=[],
                documento_base64="",
                percepcion_cruda=[],
            )
        assert destino.llamadas == 2  # una por llamada, ninguna repetida
        assert pausas == []

    @pytest.mark.xfail(
        strict=True,
        reason=(
            "H-A-02: el reintento de GET insiste ante un 4xx (404/422), que no es una caida; "
            "resiliencia.py:117-120 documenta 'reintenta timeouts y 5xx/red'"
        ),
    )
    async def test_un_get_con_4xx_no_se_reintenta(self, fabrica, pausas):
        """Un 404 es la respuesta de un catalogo sano: repetirla solo suma latencia."""
        destino = Destino(caido(404))

        with pytest.raises(RemotoCaido):
            await catalogo_sobre(fabrica, destino).producto("SKU-que-no-existe")

        assert destino.llamadas == 1
        assert pausas == []


# --- Disyuntor del catalogo ---------------------------------------------------


class TestDisyuntorDelCatalogo:
    async def test_tras_el_umbral_el_destino_deja_de_recibir_llamadas(self, fabrica):
        """Cinco POST caidos abren el circuito: el sexto se rechaza sin tocar al destino."""
        destino = Destino(caido(503))
        cliente = catalogo_sobre(fabrica, destino)

        for _ in range(5):
            with pytest.raises(RemotoCaido) as info:
                await cliente.emparejar(["lapiz"])
            assert info.value.detalle.endswith("respondio 503")
        assert destino.llamadas == 5

        with pytest.raises(RemotoCaido) as info:
            await cliente.emparejar(["lapiz"])

        assert info.value.servicio == "catalogo"
        assert info.value.detalle.startswith("circuito abierto")
        assert destino.llamadas == 5  # el sexto intento NO salio de la casa

    async def test_con_el_circuito_abierto_un_get_ni_toca_al_destino_ni_reintenta(self, fabrica, pausas):
        destino = Destino(ok({"lista_id": "x"}))
        d = circuito(resiliencia._disyuntores, "catalogo", umbral=1)
        d._estado = resiliencia._Estado.ABIERTO  # el circuito ya estaba abierto

        with pytest.raises(RemotoCaido) as info:
            await catalogo_sobre(fabrica, destino).lista("x")

        assert info.value.detalle.startswith("circuito abierto")
        assert destino.llamadas == 0
        assert pausas == []

    async def test_si_el_circuito_abre_en_pleno_reintento_el_siguiente_intento_se_corta(self, fabrica):
        """Con umbral 2, el GET falla dos veces, abre el circuito y NO hace el tercer intento."""
        destino = Destino(caido(503))
        circuito(resiliencia._disyuntores, "catalogo", umbral=2)

        with pytest.raises(RemotoCaido) as info:
            await catalogo_sobre(fabrica, destino).lista("x")

        assert destino.llamadas == 2
        assert info.value.detalle.startswith("circuito abierto")

    async def test_pasado_el_ttl_deja_pasar_una_prueba_y_un_exito_lo_cierra(self, fabrica):
        reloj = Reloj()
        d = circuito(resiliencia._disyuntores, "catalogo", umbral=2, reloj=reloj)
        destino = Destino(caido(503), caido(503), ok({"emparejamientos": []}))
        cliente = catalogo_sobre(fabrica, destino)

        for _ in range(2):
            with pytest.raises(RemotoCaido):
                await cliente.emparejar(["a"])
        assert d.abierto
        with pytest.raises(RemotoCaido):
            await cliente.emparejar(["a"])  # dentro del TTL: rechazada
        assert destino.llamadas == 2

        reloj.ahora = 31.0  # cruzado el TTL de 30 s: medio-abierto
        assert await cliente.emparejar(["a"]) == []
        assert destino.llamadas == 3
        assert not d.abierto

        # Cerrado de nuevo: el trafico normal vuelve a pasar.
        assert await cliente.emparejar(["a"]) == []
        assert destino.llamadas == 4

    async def test_si_la_prueba_del_medio_abierto_falla_el_circuito_se_reabre(self, fabrica):
        reloj = Reloj()
        d = circuito(resiliencia._disyuntores, "catalogo", umbral=1, reloj=reloj)
        destino = Destino(caido(503))
        cliente = catalogo_sobre(fabrica, destino)

        with pytest.raises(RemotoCaido):
            await cliente.emparejar(["a"])
        assert d.abierto

        reloj.ahora = 31.0
        with pytest.raises(RemotoCaido) as info:
            await cliente.emparejar(["a"])  # la prueba sale y falla
        assert info.value.detalle.endswith("respondio 503")
        assert destino.llamadas == 2

        reloj.ahora = 40.0  # 9 s despues de reabrir: dentro del nuevo TTL
        with pytest.raises(RemotoCaido) as info:
            await cliente.emparejar(["a"])
        assert info.value.detalle.startswith("circuito abierto")
        assert destino.llamadas == 2

    async def test_los_fallos_tienen_que_ser_consecutivos_un_exito_reinicia_la_cuenta(self, fabrica):
        guion = [caido(503)] * 4 + [ok({"emparejamientos": []})] + [caido(503)] * 4
        destino = Destino(*guion)
        d = circuito(resiliencia._disyuntores, "catalogo", umbral=5)
        cliente = catalogo_sobre(fabrica, destino)

        for paso in guion:
            if paso.status_code == 200:
                await cliente.emparejar(["a"])
            else:
                with pytest.raises(RemotoCaido):
                    await cliente.emparejar(["a"])

        assert not d.abierto  # 4 + 4 fallos separados por un exito no suman 5
        assert destino.llamadas == len(guion)

    async def test_un_catalogo_caido_no_cierra_la_puerta_de_comercio(self, fabrica):
        """El disyuntor es por destino: es la frontera del bulkhead."""
        catalogo_caido = Destino(caido(503))
        comercio_sano = Destino(ok({"pedido_id": "p-1"}, 201))
        cliente_catalogo = catalogo_sobre(fabrica, catalogo_caido)
        for _ in range(5):
            with pytest.raises(RemotoCaido):
                await cliente_catalogo.emparejar(["a"])
        assert resiliencia.disyuntor_de("catalogo").abierto

        estado, cuerpo = await comercio_sobre(fabrica, comercio_sano).crear_orden({"lineas": []})

        assert (estado, cuerpo) == (201, {"pedido_id": "p-1"})
        assert comercio_sano.llamadas == 1

    @pytest.mark.xfail(
        strict=True,
        reason=(
            "H-A-24: el disyuntor del catalogo cuenta un 4xx (respuesta de un destino sano) como "
            "fallo; remoto.py:98-104 deja raise_for_status dentro del `async with disyuntor`"
        ),
    )
    async def test_los_4xx_de_un_catalogo_sano_no_abren_el_circuito(self, fabrica):
        """Cinco rechazos 422 de un catalogo sano no deben cortar la consulta valida siguiente.

        Se usa POST para que el reintento de GET no tape la cuenta del disyuntor.
        """
        destino = Destino(*[caido(422)] * 5, ok({"emparejamientos": []}))
        cliente = catalogo_sobre(fabrica, destino)

        for _ in range(5):
            with pytest.raises(RemotoCaido) as info:
                await cliente.emparejar(["renglon que el catalogo rechaza"])
            assert info.value.detalle.endswith("respondio 422")

        # El catalogo esta sano: una consulta valida tiene que llegar.
        assert await cliente.emparejar(["lapiz"]) == []


# --- ClienteIdentidad --------------------------------------------------------


class TestRegistrarContacto:
    async def test_envia_el_correo_y_el_celular_y_devuelve_el_usuario_id(self, fabrica):
        destino = Destino(ok({"usuario_id": USUARIO}, 201))

        usuario = await identidad_sobre(fabrica, destino).registrar_contacto(
            "acudiente@example.test", "3000000000"
        )

        assert usuario == USUARIO
        assert (destino.ultima.method, destino.ultima.url.path) == ("POST", "/v1/contactos")
        assert destino.cuerpo_enviado() == {"correo": "acudiente@example.test", "celular": "3000000000"}

    async def test_sin_celular_envia_null(self, fabrica):
        destino = Destino(ok({"usuario_id": USUARIO}, 201))

        await identidad_sobre(fabrica, destino).registrar_contacto("acudiente@example.test")

        assert destino.cuerpo_enviado() == {"correo": "acudiente@example.test", "celular": None}

    @pytest.mark.parametrize(
        "fallo",
        [caido(503), caido(422), httpx.ReadTimeout("lento"), httpx.ConnectError("caido")],
        ids=["5xx", "4xx", "timeout", "red"],
    )
    async def test_si_identidad_falla_devuelve_none_en_vez_de_levantar(self, fabrica, fallo):
        """Perder el aviso es malo; perder el kit por no poder avisar es peor."""
        destino = Destino(fallo)

        assert await identidad_sobre(fabrica, destino).registrar_contacto("acudiente@example.test") is None

    @pytest.mark.xfail(
        strict=True,
        reason=(
            "H-A-25: registrar_contacto devuelve la cadena 'None' (str(None)) si la respuesta 2xx "
            "no trae usuario_id; trabajos.py:157-158 y 1100 la pasan a uuid.UUID y revienta; remoto.py:268"
        ),
    )
    async def test_una_respuesta_sin_usuario_id_es_none_no_la_cadena_none(self, fabrica):
        destino = Destino(ok({"otro": "campo"}, 201))

        usuario = await identidad_sobre(fabrica, destino).registrar_contacto("acudiente@example.test")

        assert usuario is None

    @pytest.mark.xfail(
        strict=True,
        reason=(
            "H-A-26: ClienteIdentidad no usa disyuntor (remoto.py:255-269, 272-285, 287-307); "
            "REVISION_ARQUITECTURA.md:388-391 lo exige por destino ('catalogo','identidad','comercio')"
        ),
    )
    async def test_con_identidad_caida_el_sexto_intento_no_toca_el_destino(self, fabrica):
        destino = Destino(httpx.ConnectError("caido"))
        cliente = identidad_sobre(fabrica, destino)

        for _ in range(6):
            assert await cliente.registrar_contacto("acudiente@example.test") is None

        # Cinco fallos abren el circuito (umbral por omision): el sexto no sale.
        assert destino.llamadas == 5


class TestUsuarioDelToken:
    async def test_pregunta_a_identidad_con_el_bearer_y_devuelve_el_usuario_id(self, fabrica):
        destino = Destino(ok({"usuario_id": USUARIO, "roles": []}))

        usuario = await identidad_sobre(fabrica, destino).usuario_del_token("tok-1")

        assert usuario == USUARIO
        assert (destino.ultima.method, destino.ultima.url.path) == ("GET", "/v1/sesiones/actual")
        assert destino.ultima.headers["Authorization"] == "Bearer tok-1"

    @pytest.mark.parametrize(
        "respuesta",
        [caido(401), caido(500), ok({"sin": "usuario"}), httpx.ConnectError("caido")],
        ids=["token_invalido", "5xx", "sin_usuario_id", "red"],
    )
    async def test_cualquier_cosa_que_no_sea_un_usuario_degrada_a_none(self, fabrica, respuesta):
        """Un token que no vale o una identidad caida degradan al flujo por contacto."""
        destino = Destino(respuesta)

        assert await identidad_sobre(fabrica, destino).usuario_del_token("tok-1") is None


class TestSesionFallaCerrada:
    async def test_una_sesion_valida_devuelve_el_cuerpo_con_los_roles(self, fabrica):
        cuerpo = {"usuario_id": USUARIO, "roles": [{"rol": "operador", "ambito": None}]}
        destino = Destino(ok(cuerpo))

        sesion = await identidad_sobre(fabrica, destino).sesion("tok-op")

        assert sesion == cuerpo
        assert destino.ultima.headers["Authorization"] == "Bearer tok-op"

    async def test_un_401_es_un_token_que_no_vale_y_devuelve_none(self, fabrica):
        destino = Destino(caido(401))

        assert await identidad_sobre(fabrica, destino).sesion("tok-malo") is None

    @pytest.mark.parametrize(
        "fallo",
        [caido(500), caido(503), caido(403), httpx.ReadTimeout("lento"), httpx.ConnectError("caido")],
        ids=["500", "503", "403", "timeout", "red"],
    )
    async def test_cualquier_otro_fallo_es_remoto_caido_nunca_un_acceso_abierto(self, fabrica, fallo):
        """No poder preguntar NO es lo mismo que 'no vale': quien valida responde 503, no deja pasar."""
        destino = Destino(fallo)

        with pytest.raises(RemotoCaido) as info:
            await identidad_sobre(fabrica, destino).sesion("tok-op")

        assert info.value.servicio == "identidad"


class TestDatosDirectorio:
    async def test_devuelve_los_datos_dueb_del_colegio(self, fabrica):
        cuerpo = {"dane": "111001", "direccion": "Calle Ficticia 1", "sitio": "https://colegio.example.test"}
        destino = Destino(ok(cuerpo))

        datos = await identidad_sobre(fabrica, destino).datos_directorio("111001")

        assert datos == cuerpo
        assert (destino.ultima.method, destino.ultima.url.path) == ("GET", "/v1/directorio/111001")

    @pytest.mark.parametrize(
        "respuesta",
        [caido(404), caido(500), httpx.ReadTimeout("lento"), httpx.ConnectError("caido")],
        ids=["dane_desconocido", "5xx", "timeout", "red"],
    )
    async def test_sin_datos_la_subida_degrada_a_none(self, fabrica, respuesta):
        """El revisor completa a mano lo que falte: la subida no se cae."""
        destino = Destino(respuesta)

        assert await identidad_sobre(fabrica, destino).datos_directorio("111001") is None


# --- ClienteComercio ---------------------------------------------------------


class TestComercioDevuelveEstadoYCuerpo:
    async def test_crear_orden_es_post_a_ordenes_y_devuelve_estado_y_cuerpo(self, fabrica):
        destino = Destino(ok({"pedido_id": "p-1", "total": 12000}, 201))
        orden = {"usuario_id": USUARIO, "lineas": [{"sku": "A", "cantidad": 1}]}

        estado, cuerpo = await comercio_sobre(fabrica, destino).crear_orden(orden)

        assert (estado, cuerpo) == (201, {"pedido_id": "p-1", "total": 12000})
        assert (destino.ultima.method, destino.ultima.url.path) == ("POST", "/v1/ordenes")
        assert destino.cuerpo_enviado() == orden

    async def test_iniciar_pago_cuelga_del_pedido(self, fabrica):
        destino = Destino(ok({"url_redireccion": "https://pasarela.example.test/p"}, 201))

        estado, cuerpo = await comercio_sobre(fabrica, destino).iniciar_pago("p-1", {"metodo": "pse"})

        assert estado == 201
        assert cuerpo["url_redireccion"].startswith("https://pasarela.example.test")
        assert destino.ultima.url.path == "/v1/ordenes/p-1/pago"
        assert destino.cuerpo_enviado() == {"metodo": "pse"}

    @pytest.mark.parametrize("estado", [400, 409, 422])
    async def test_un_rechazo_de_negocio_es_una_respuesta_no_una_excepcion(self, fabrica, estado):
        """`422 precio_cambiado` lo tiene que ver el acudiente: no es una caida de Comercio."""
        rechazo = {"error": "precio_cambiado", "mensaje": "El precio cambio."}
        destino = Destino(httpx.Response(estado, json=rechazo))

        resultado = await comercio_sobre(fabrica, destino).crear_orden({"lineas": []})

        assert resultado == (estado, rechazo)

    @pytest.mark.parametrize("estado", [500, 502, 503])
    async def test_un_5xx_es_remoto_caido_y_el_post_no_se_reintenta(self, fabrica, pausas, estado):
        """Reintentar un checkout a ciegas es un doble cobro."""
        destino = Destino(caido(estado))

        with pytest.raises(RemotoCaido) as info:
            await comercio_sobre(fabrica, destino).crear_orden({"lineas": []})

        assert info.value.servicio == "comercio"
        assert info.value.detalle == f"{estado} en /v1/ordenes"
        assert destino.llamadas == 1
        assert pausas == []

    @pytest.mark.parametrize("fallo", [httpx.ReadTimeout("lento"), httpx.ConnectError("caido")])
    async def test_timeout_o_red_caida_es_remoto_caido(self, fabrica, fallo):
        destino = Destino(fallo)

        with pytest.raises(RemotoCaido) as info:
            await comercio_sobre(fabrica, destino).iniciar_pago("p-1", {})

        assert info.value.servicio == "comercio"
        assert destino.llamadas == 1


class TestDisyuntorDeComercio:
    async def test_cinco_caidas_de_red_abren_el_circuito_y_la_sexta_no_sale(self, fabrica):
        destino = Destino(httpx.ConnectError("caido"))
        cliente = comercio_sobre(fabrica, destino)

        for _ in range(5):
            with pytest.raises(RemotoCaido) as info:
                await cliente.crear_orden({"lineas": []})
            assert not info.value.detalle.startswith("circuito abierto")

        with pytest.raises(RemotoCaido) as info:
            await cliente.crear_orden({"lineas": []})

        assert info.value.servicio == "comercio"
        assert info.value.detalle.startswith("circuito abierto")
        assert destino.llamadas == 5

    async def test_pasado_el_ttl_la_prueba_exitosa_cierra_el_circuito(self, fabrica):
        reloj = Reloj()
        d = circuito(resiliencia._disyuntores, "comercio", umbral=1, reloj=reloj)
        destino = Destino(httpx.ConnectError("caido"), ok({"pedido_id": "p-1"}, 201))
        cliente = comercio_sobre(fabrica, destino)

        with pytest.raises(RemotoCaido):
            await cliente.crear_orden({"lineas": []})
        assert d.abierto

        reloj.ahora = 31.0
        estado, _ = await cliente.crear_orden({"lineas": []})

        assert estado == 201
        assert not d.abierto

    @pytest.mark.xfail(
        strict=True,
        reason=(
            "H-A-26: ClienteComercio._postear levanta RemotoCaido por 5xx FUERA del `async with "
            "disyuntor_de('comercio')` (remoto.py:379-380), asi que un Comercio que responde 503 jamas "
            "abre el circuito y recibe toda la tormenta"
        ),
    )
    async def test_cinco_respuestas_5xx_tambien_abren_el_circuito(self, fabrica):
        destino = Destino(caido(503))
        cliente = comercio_sobre(fabrica, destino)

        for _ in range(6):
            with pytest.raises(RemotoCaido):
                await cliente.crear_orden({"lineas": []})

        assert destino.llamadas == 5


class TestPedidosPagados:
    async def test_lee_la_lista_de_pedidos_confirmados(self, fabrica):
        pedidos = [{"trabajo_id": "t-1", "usuario_id": USUARIO, "estado": "confirmado"}]
        destino = Destino(ok({"pedidos": pedidos}))

        resultado = await comercio_sobre(fabrica, destino).pedidos_pagados()

        assert resultado == pedidos
        assert (destino.ultima.method, destino.ultima.url.path) == ("GET", "/v1/comercio/pedidos-pagados")

    async def test_sin_clave_pedidos_es_lista_vacia(self, fabrica):
        assert await comercio_sobre(fabrica, Destino(ok({}))).pedidos_pagados() == []

    @pytest.mark.parametrize(
        "fallo",
        [caido(500), caido(404), httpx.ReadTimeout("lento"), httpx.ConnectError("caido")],
        ids=["5xx", "4xx", "timeout", "red"],
    )
    async def test_cualquier_fallo_es_remoto_caido_no_un_cruce_a_medias(self, fabrica, fallo):
        destino = Destino(fallo)

        with pytest.raises(RemotoCaido) as info:
            await comercio_sobre(fabrica, destino).pedidos_pagados()

        assert info.value.servicio == "comercio"


def test_la_espera_generosa_cubre_un_emparejamiento_de_lista_entera():
    """Medio segundo convertiria una lista larga en un fallo intermitente (remoto.py:39-43)."""
    assert ESPERA_SEGUNDOS >= 30.0
