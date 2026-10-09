"""NFR-MAN-01: el cliente de tiendas no se fia de lo que no puede distinguir.

`test_tiendas` fija la traduccion de Shopify y el filtro de palabras. Aqui se
caracteriza el resto del cliente, sin una sola peticion real (`urlopen` se
sustituye por un guion de respuestas inventadas y el cache apunta a `tmp_path`):

- **El cache en disco** hace reproducible el catalogo: una respuesta fresca no
  vuelve a la red, una vencida o corrupta si, y solo se guarda lo que trae datos.
- **El reintento** existe porque una tienda que limita el ritmo responde vacio,
  y un vacio por prisa se lee igual que un hueco real del catalogo. Se afirma el
  numero de intentos y la espera creciente (inyectada, sin dormir).
- **La ficha es exacta o nada.** Una respuesta con dos productos no es una ficha:
  ponerle a un producto la foto o el precio de otro es peor que dejarlo vacio.
- **La traduccion de VTEX** a `Oferta`: precio entero, disponibilidad por
  existencias, EAN solo si tiene un largo valido, especificaciones sin vacios.
- **La busqueda** pide el rango correcto a VTEX; en Shopify baja el catalogo
  paginado, corta en la primera pagina vacia y respeta el tope de candidatos.

Los datos (tiendas, dominios, productos) son inventados.
"""

from __future__ import annotations

import json
import os
import urllib.error
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from tukit_catalogo import tiendas
from tukit_catalogo.tiendas import (
    Oferta,
    _a_oferta,
    _a_oferta_shopify,
    _catalogo_shopify,
    _clave,
    _pedir,
    _sin_tildes,
    buscar,
    ficha,
    slug_de_url,
)

pytestmark = pytest.mark.nfr("NFR-MAN-01")

URL_FICHA = "https://www.exito.com/cuaderno-ficticio-100-hojas/p"
API_FICHA = "https://www.exito.com/api/catalog_system/pub/products/search/cuaderno-ficticio-100-hojas/p"


class _Respuesta:
    """Lo que devuelve `urlopen`: un gestor de contexto con `read()`."""

    def __init__(self, cuerpo: bytes) -> None:
        self._cuerpo = cuerpo

    def __enter__(self) -> _Respuesta:
        return self

    def __exit__(self, *_a: object) -> None:
        return None

    def read(self) -> bytes:
        return self._cuerpo


class Red:
    """Un guion de respuestas para `urlopen`. Cada entrada es un objeto JSON, bytes o una excepcion."""

    def __init__(self, guion: list[object]) -> None:
        self.guion = list(guion)
        self.llamadas: list[tuple[str, dict[str, str], float | None]] = []
        self.esperas: list[float] = []

    def urlopen(self, peticion, timeout=None):  # noqa: ANN001
        self.llamadas.append((peticion.full_url, dict(peticion.header_items()), timeout))
        if not self.guion:
            raise AssertionError(f"peticion no prevista: {peticion.full_url}")
        siguiente = self.guion.pop(0)
        if isinstance(siguiente, BaseException):
            raise siguiente
        if isinstance(siguiente, bytes):
            return _Respuesta(siguiente)
        return _Respuesta(json.dumps(siguiente).encode())

    @property
    def urls(self) -> list[str]:
        return [u for u, _h, _t in self.llamadas]


@pytest.fixture()
def red(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Cache en `tmp_path`, red guionada y reloj de espera inyectado."""

    def instalar(*guion: object) -> Red:
        falsa = Red(list(guion))
        monkeypatch.setattr(tiendas.urllib.request, "urlopen", falsa.urlopen)
        monkeypatch.setattr(tiendas.time, "sleep", falsa.esperas.append)
        return falsa

    monkeypatch.setattr(tiendas, "CACHE", tmp_path / "cache_tiendas")
    monkeypatch.setattr(tiendas.urllib.request, "urlopen", Red([]).urlopen)
    monkeypatch.setattr(tiendas.time, "sleep", lambda _s: None)
    return instalar


def _vtex(nombre: str = "Cuaderno Ficticio", precio: float = 5750, cantidad: int = 4, **kw) -> dict:
    crudo = {
        "productName": nombre,
        "brand": "Marca Ficticia",
        "link": "https://www.exito.com/cuaderno-ficticio/p",
        "allSpecifications": ["Hojas", "Vacia"],
        "Hojas": ["100 "],
        "Vacia": [""],
        "items": [
            {
                "itemId": 8801,
                "name": "Cuaderno Ficticio azul",
                "ean": "7701234567890",
                "images": [{"imageUrl": "https://img.example.test/c.jpg"}],
                "sellers": [{"commertialOffer": {"Price": precio, "AvailableQuantity": cantidad}}],
            },
            {"itemId": 8802, "name": "otra variante", "sellers": []},
        ],
    }
    crudo.update(kw)
    return crudo


# ---------------------------------------------------------------------------
# Piezas pequenas
# ---------------------------------------------------------------------------


class TestPiezasPequenas:
    @pytest.mark.parametrize(
        ("url", "esperado"),
        [
            ("https://www.exito.com/cuaderno-ficticio/p", ("www.exito.com", "cuaderno-ficticio")),
            ("https://www.exito.com/cuaderno-ficticio/p/", ("www.exito.com", "cuaderno-ficticio")),
            ("https://www.exito.com/cuaderno-ficticio/p?sku=1#x", ("www.exito.com", "cuaderno-ficticio")),
            (
                "https://www.exito.com/papeleria/cuadernos/cuaderno-ficticio/p",
                ("www.exito.com", "cuaderno-ficticio"),
            ),
            ("https://www.exito.com/cuaderno-ficticio", None),  # no es una ficha
            ("https://www.exito.com/p", None),  # sin slug
            ("https://www.exito.com/", None),
            ("cuaderno-ficticio/p", None),  # sin dominio
            ("http://[::1/p", None),  # direccion malformada
            ("", None),
        ],
    )
    def test_slug_de_url_solo_reconoce_fichas(self, url, esperado):
        assert slug_de_url(url) == esperado

    def test_la_clave_de_cache_es_un_nombre_de_fichero_seguro(self):
        assert _clave("Cuaderno Ficticio / 100 Hojas!") == "cuaderno-ficticio-100-hojas"
        assert _clave("--A--") == "a"
        assert len(_clave("x" * 500)) == 120

    def test_sin_tildes_normaliza_para_comparar(self):
        assert _sin_tildes("Lápiz CÓLOR Ñandú") == "lapiz color nandu"


# ---------------------------------------------------------------------------
# _pedir: cache y reintento
# ---------------------------------------------------------------------------


class TestPedirCache:
    def test_una_respuesta_con_datos_se_guarda_con_su_origen_y_su_fecha(self, red, tmp_path):
        falsa = red([{"a": 1}])

        assert _pedir("https://tienda.example.test/api", "mi-clave") == [{"a": 1}]

        guardado = json.loads((tmp_path / "cache_tiendas" / "mi-clave.json").read_text())
        assert guardado["url"] == "https://tienda.example.test/api"
        assert guardado["respuesta"] == [{"a": 1}]
        assert datetime.fromisoformat(guardado["leido_en"]).tzinfo is not None
        assert len(falsa.llamadas) == 1

    def test_la_peticion_parece_un_navegador_y_acepta_json(self, red):
        falsa = red([{"a": 1}])
        _pedir("https://tienda.example.test/api", "k")
        _url, cabeceras, tiempo = falsa.llamadas[0]
        assert cabeceras["User-agent"].startswith("Mozilla/5.0")
        assert cabeceras["Accept"] == "application/json"
        assert tiempo == 25

    def test_una_respuesta_fresca_no_vuelve_a_la_red(self, red):
        falsa = red([{"a": 1}])
        assert _pedir("https://tienda.example.test/api", "k") == [{"a": 1}]
        assert _pedir("https://tienda.example.test/api", "k") == [{"a": 1}]
        assert len(falsa.llamadas) == 1  # la segunda salio del cache

    def test_una_respuesta_vencida_se_pide_otra_vez_y_se_reescribe(self, red, tmp_path):
        red_ = red([{"v": 1}], [{"v": 2}])
        _pedir("https://tienda.example.test/api", "k", dias_frescura=3)
        archivo = tmp_path / "cache_tiendas" / "k.json"
        viejo = (datetime.now(UTC) - timedelta(days=4)).timestamp()
        os.utime(archivo, (viejo, viejo))

        assert _pedir("https://tienda.example.test/api", "k", dias_frescura=3) == [{"v": 2}]
        assert len(red_.llamadas) == 2
        assert json.loads(archivo.read_text())["respuesta"] == [{"v": 2}]

    def test_la_frescura_es_la_que_pide_quien_llama(self, red, tmp_path):
        red_ = red([{"v": 1}])
        _pedir("https://tienda.example.test/api", "k")
        archivo = tmp_path / "cache_tiendas" / "k.json"
        hace_cuatro = (datetime.now(UTC) - timedelta(days=4)).timestamp()
        os.utime(archivo, (hace_cuatro, hace_cuatro))

        # Con 7 dias de frescura (por omision) todavia vale.
        assert _pedir("https://tienda.example.test/api", "k") == [{"v": 1}]
        assert len(red_.llamadas) == 1

    @pytest.mark.parametrize("contenido", ["no es json {", '{"sin_respuesta": true}'])
    def test_un_cache_corrupto_se_ignora_y_se_vuelve_a_pedir(self, red, tmp_path, contenido):
        carpeta = tmp_path / "cache_tiendas"
        carpeta.mkdir()
        (carpeta / "k.json").write_text(contenido)
        falsa = red([{"bueno": 1}])

        assert _pedir("https://tienda.example.test/api", "k") == [{"bueno": 1}]
        assert len(falsa.llamadas) == 1
        assert json.loads((carpeta / "k.json").read_text())["respuesta"] == [{"bueno": 1}]


class TestPedirReintento:
    def test_una_respuesta_vacia_no_se_guarda_y_se_reintenta_con_espera_creciente(self, red, tmp_path):
        """Un vacio por exceso de prisa no se puede confundir con 'la tienda no lo tiene'."""
        falsa = red([], {}, [])

        assert _pedir("https://tienda.example.test/api", "k") is None

        assert len(falsa.llamadas) == 3
        assert falsa.esperas == [1.5, 3.0]  # no se espera despues del ultimo intento
        assert not (tmp_path / "cache_tiendas" / "k.json").exists()

    def test_un_error_de_red_se_reintenta_y_el_segundo_intento_basta(self, red):
        falsa = red(urllib.error.URLError("sin ruta"), [{"a": 1}])
        assert _pedir("https://tienda.example.test/api", "k") == [{"a": 1}]
        assert len(falsa.llamadas) == 2
        assert falsa.esperas == [1.5]

    @pytest.mark.parametrize(
        "fallo",
        [urllib.error.URLError("x"), TimeoutError("lento"), ConnectionResetError("corte"), b"<html>no json"],
        ids=["urlerror", "timeout", "oserror", "json-roto"],
    )
    def test_tres_fallos_seguidos_devuelven_none_y_no_lanzan(self, red, fallo):
        falsa = red(fallo, fallo, fallo)
        assert _pedir("https://tienda.example.test/api", "k") is None
        assert len(falsa.llamadas) == 3

    def test_un_json_que_no_es_lista_ni_objeto_no_cuenta_como_datos(self, red):
        falsa = red(b"5", b'"ok"', b"true")
        assert _pedir("https://tienda.example.test/api", "k") is None
        assert len(falsa.llamadas) == 3

    def test_un_objeto_tambien_es_una_respuesta_valida(self, red):
        """Shopify envuelve la lista en un objeto."""
        red({"products": [{"id": 1}]})
        assert _pedir("https://tienda.example.test/api", "k") == {"products": [{"id": 1}]}


# ---------------------------------------------------------------------------
# ficha
# ---------------------------------------------------------------------------


class TestFicha:
    def test_una_direccion_que_no_es_ficha_no_sale_a_la_red(self, red):
        falsa = red()
        assert ficha("https://www.exito.com/cuadernos") is None
        assert falsa.llamadas == []

    def test_un_producto_se_traduce_y_la_tienda_se_reconoce_por_dominio(self, red):
        falsa = red([_vtex()])

        oferta = ficha(URL_FICHA)

        assert falsa.urls == [API_FICHA]
        assert oferta is not None
        assert oferta.tienda == "exito"
        assert oferta.nombre == "Cuaderno Ficticio"
        assert oferta.precio_cop == 5750

    def test_un_dominio_desconocido_se_usa_tal_cual_como_tienda(self, red):
        red([_vtex()])
        oferta = ficha("https://tienda.example.test/cuaderno-ficticio/p")
        assert oferta is not None
        assert oferta.tienda == "tienda.example.test"

    def test_el_slug_se_escapa_en_la_direccion_de_la_api(self, red):
        falsa = red([_vtex()])
        ficha("https://www.exito.com/cuaderno ficticio/p")
        assert falsa.urls == [
            "https://www.exito.com/api/catalog_system/pub/products/search/cuaderno%20ficticio/p"
        ]

    def test_dos_productos_no_son_una_ficha(self, red):
        """Si la respuesta trae varios, no hay forma de saber cual era: mejor vacio que equivocado."""
        red([_vtex("Uno Ficticio"), _vtex("Dos Ficticio")])
        assert ficha(URL_FICHA) is None

    def test_sin_respuesta_no_hay_ficha(self, red):
        falsa = red([], [], [])
        assert ficha(URL_FICHA) is None
        assert len(falsa.llamadas) == 3

    def test_la_segunda_lectura_sale_del_cache(self, red):
        falsa = red([_vtex()])
        primera = ficha(URL_FICHA)
        segunda = ficha(URL_FICHA)
        assert primera == segunda
        assert len(falsa.llamadas) == 1


# ---------------------------------------------------------------------------
# _a_oferta (VTEX)
# ---------------------------------------------------------------------------


class TestTraduccionVtex:
    def test_un_producto_completo(self):
        oferta = _a_oferta("exito", _vtex())
        assert oferta == Oferta(
            tienda="exito",
            nombre="Cuaderno Ficticio",
            precio_cop=5750,
            disponible=True,
            imagen_url="https://img.example.test/c.jpg",
            url="https://www.exito.com/cuaderno-ficticio/p",
            sku="8801",
            ean="7701234567890",
            marca="Marca Ficticia",
            especificaciones={"Hojas": "100"},  # recortada; la vacia no entra
        )

    def test_solo_se_lee_el_primer_articulo(self):
        """Las variantes de color de un cuaderno son el mismo cuaderno para el kit."""
        assert _a_oferta("exito", _vtex()).sku == "8801"

    def test_el_precio_decimal_se_trunca_a_entero(self):
        assert _a_oferta("exito", _vtex(precio=5750.9)).precio_cop == 5750

    @pytest.mark.parametrize(("cantidad", "disponible"), [(0, False), (1, True), (None, False)])
    def test_disponible_es_tener_existencias(self, cantidad, disponible):
        assert _a_oferta("exito", _vtex(cantidad=cantidad)).disponible is disponible

    def test_sin_articulos_no_hay_oferta(self):
        assert _a_oferta("exito", {"productName": "Sin items", "items": []}) is None
        assert _a_oferta("exito", {"productName": "Sin items"}) is None

    def test_sin_vendedor_el_precio_es_cero_y_no_esta_disponible(self):
        """VTEX devuelve cero cuando no se vende en linea; los consumidores filtran precio <= 0."""
        crudo = {"productName": "Sin Venta Ficticia", "items": [{"itemId": 5, "sellers": []}]}
        oferta = _a_oferta("exito", crudo)
        assert oferta.precio_cop == 0
        assert oferta.disponible is False
        assert oferta.imagen_url is None
        assert oferta.url == ""

    def test_el_nombre_cae_al_del_articulo_si_el_producto_no_lo_trae(self):
        crudo = _vtex()
        del crudo["productName"]
        assert _a_oferta("exito", crudo).nombre == "Cuaderno Ficticio azul"

    @pytest.mark.parametrize(
        ("ean", "valido"),
        [
            ("12345670", True),  # EAN-8
            ("123456789012", True),  # UPC-A
            ("7701234567890", True),  # EAN-13
            ("1234567890", False),  # largo que no es de codigo de barras
            ("77012345678901", False),
            ("77012345678AB", False),
            ("", False),
            (None, False),
            ("  7701234567890 ", True),  # se recorta antes de validar
        ],
    )
    def test_el_ean_solo_se_acepta_con_un_largo_de_codigo_de_barras(self, ean, valido):
        crudo = _vtex()
        crudo["items"][0]["ean"] = ean
        resultado = _a_oferta("exito", crudo).ean
        assert (resultado is not None) is valido
        if valido:
            assert resultado == ean.strip()

    def test_sin_marca_queda_none_y_no_texto_vacio(self):
        assert _a_oferta("exito", _vtex(brand="   ")).marca is None


class TestTraduccionShopifyBordes:
    def test_un_precio_ilegible_no_produce_oferta(self):
        crudo = {"title": "Algo", "variants": [{"price": "gratis", "option1": "Unidad"}]}
        assert _a_oferta_shopify("grancentral", "pgrancentral.com", crudo) is None

    def test_sin_imagenes_ni_proveedor_ni_handle_quedan_vacios(self):
        crudo = {"title": "  Tabla de Picado Ficticia ", "variants": [{"id": 9, "price": "9500.00"}]}
        oferta = _a_oferta_shopify("grancentral", "pgrancentral.com", crudo)
        assert oferta.nombre == "Tabla de Picado Ficticia"
        assert oferta.imagen_url is None
        assert oferta.marca is None
        assert oferta.url == "https://pgrancentral.com/products/"
        assert oferta.sku == "9"
        assert oferta.disponible is False


# ---------------------------------------------------------------------------
# buscar
# ---------------------------------------------------------------------------


def _shopify(titulo: str, precio: str = "5750.00", *, con_variante: bool = True) -> dict:
    return {
        "title": titulo,
        "handle": titulo.lower().replace(" ", "-"),
        "vendor": "Proveedor Ficticio",
        "images": [{"src": "https://img.example.test/s.jpg"}],
        "variants": [{"id": 1, "sku": "S1", "price": precio, "option1": "Unidad", "available": True}]
        if con_variante
        else [],
    }


class TestBuscarVtex:
    def test_una_tienda_que_no_conoce_devuelve_vacio_sin_red(self, red):
        falsa = red()
        assert buscar("tienda-inventada", "cuaderno") == []
        assert falsa.llamadas == []

    def test_pide_el_rango_y_el_texto_escapado(self, red):
        falsa = red([_vtex()])
        buscar("exito", "cuaderno rayado", cuantos=10)
        assert falsa.urls == [
            "https://www.exito.com/api/catalog_system/pub/products/search?ft=cuaderno%20rayado&_from=0&_to=9"
        ]

    def test_devuelve_las_ofertas_y_salta_los_productos_sin_articulos(self, red):
        red([_vtex("Uno Ficticio"), {"productName": "Sin Items", "items": []}, _vtex("Dos Ficticio")])
        assert [o.nombre for o in buscar("panamericana", "cuaderno")] == ["Uno Ficticio", "Dos Ficticio"]

    def test_sin_resultados_es_una_lista_vacia(self, red):
        red([], [], [])
        assert buscar("exito", "cuaderno inexistente") == []

    def test_la_busqueda_se_cachea_por_tienda_y_consulta(self, red):
        falsa = red([_vtex()])
        buscar("exito", "Cuaderno Rayado!")
        buscar("exito", "Cuaderno Rayado!")
        assert len(falsa.llamadas) == 1
        assert (tiendas.CACHE / "busca-exito-cuaderno-rayado.json").exists()


class TestBuscarShopify:
    def test_baja_el_catalogo_por_paginas_y_corta_en_la_primera_vacia(self, red):
        falsa = red({"products": [_shopify("Tabla Picado Ficticia")]}, {"products": []})

        resultado = buscar("grancentral", "tabla picado")

        assert [o.nombre for o in resultado] == ["Tabla Picado Ficticia"]
        assert falsa.urls == [
            "https://pgrancentral.com/products.json?limit=250&page=1",
            "https://pgrancentral.com/products.json?limit=250&page=2",
        ]

    def test_filtra_por_todas_las_palabras_de_la_consulta(self, red):
        red(
            {
                "products": [
                    _shopify("Lentejuelas Doradas Ficticias"),
                    _shopify("Reno Con Traje De Lentejuelas"),
                    _shopify("Lentejuelas Plateadas Ficticias"),
                ]
            },
            {"products": []},
        )
        nombres = [o.nombre for o in buscar("grancentral", "lentejuelas ficticias")]
        assert nombres == ["Lentejuelas Doradas Ficticias", "Lentejuelas Plateadas Ficticias"]

    def test_respeta_el_tope_de_candidatos(self, red):
        red({"products": [_shopify(f"Boligrafo Ficticio {i}") for i in range(6)]}, {"products": []})
        assert len(buscar("grancentral", "boligrafo", cuantos=3)) == 3

    def test_un_producto_sin_variantes_se_salta_y_no_cuenta_para_el_tope(self, red):
        red(
            {
                "products": [
                    _shopify("Boligrafo Sin Precio", con_variante=False),
                    _shopify("Boligrafo Con Precio Uno"),
                    _shopify("Boligrafo Con Precio Dos"),
                ]
            },
            {"products": []},
        )
        assert [o.nombre for o in buscar("grancentral", "boligrafo", cuantos=2)] == [
            "Boligrafo Con Precio Uno",
            "Boligrafo Con Precio Dos",
        ]

    def test_un_catalogo_que_no_responde_da_vacio(self, red):
        red([], [], [])
        assert buscar("grancentral", "boligrafo") == []


class TestCatalogoShopify:
    def test_no_pide_mas_paginas_que_el_tope(self, red):
        falsa = red(*[{"products": [_shopify(f"Producto Ficticio {n}")]} for n in range(5)])
        todo = _catalogo_shopify("grancentral", "pgrancentral.com", paginas=3)
        assert len(todo) == 3
        assert len(falsa.llamadas) == 3

    def test_una_respuesta_que_no_es_objeto_corta_la_descarga(self, red):
        """Si la tienda contesta una lista donde espera un objeto, no se inventa un catalogo."""
        falsa = red([{"products": [1]}])
        assert _catalogo_shopify("grancentral", "pgrancentral.com") == []
        assert len(falsa.llamadas) == 1

    def test_las_paginas_quedan_en_cache_por_tienda_y_numero(self, red):
        red({"products": [_shopify("Uno Ficticio")]}, {"products": []})
        _catalogo_shopify("grancentral", "pgrancentral.com")
        assert (tiendas.CACHE / "shopify-grancentral-p1.json").exists()
        # La pagina final es un objeto con lista vacia: no es una respuesta vacia
        # (`{}`), y guardarla permite reconstruir el catalogo sin red.
        assert (tiendas.CACHE / "shopify-grancentral-p2.json").exists()
        assert not (tiendas.CACHE / "shopify-grancentral-p3.json").exists()
