"""El cliente de tiendas, con Shopify al lado de VTEX.

Grancentral no corre sobre VTEX sino sobre Shopify, y eso no es un detalle de
transporte: cambia la forma del dato. VTEX devuelve un producto con articulos;
Shopify devuelve un producto con variantes, y en un mayorista de San Victorino
la variante es la diferencia entre venderle al papa una unidad o una docena.
"""

from tukit_catalogo.tiendas import Oferta, _a_oferta_shopify, _coincide


def producto(titulo: str, variantes: list[dict], **extra) -> dict:
    """Un producto de Shopify con lo minimo que trae `/products.json`."""
    return {
        "title": titulo,
        "handle": "un-producto",
        "vendor": extra.get("vendor", "Grancentral"),
        "images": extra.get("images", [{"src": "https://cdn/foto.png"}]),
        "variants": variantes,
    }


def variante(precio: str, opcion: str = "Default Title", **extra) -> dict:
    return {
        "option1": opcion,
        "price": precio,
        "available": extra.get("available", True),
        "sku": extra.get("sku"),
        "id": extra.get("id", 111),
    }


class TestLaVarianteQueSeLeCobraAlPapa:
    def test_entre_unidad_y_docena_se_cobra_la_unidad(self):
        """La razon por la que este modulo existe con prueba propia.

        Grancentral vende cada cosa en dos presentaciones y las publica como
        variantes del mismo producto: 'Unidad' y 'Docena'. La tabla de picado
        vale $9.500 suelta y $94.200 por docena. Quien arma un kit escolar
        necesita una, y tomar la primera variante que venga es una moneda al
        aire que diez veces de cada cien le cobra el paquete del mayorista.

        No hay umbral de precio que salve esto, porque los dos precios son
        correctos: son del mismo producto y de la misma tienda. Lo que decide
        es la palabra en la opcion.
        """
        crudo = producto(
            "Tabla Picado Con Tablero Acrilico",
            [variante("94200.00", "Docena"), variante("9500.00", "Unidad")],
        )
        oferta = _a_oferta_shopify("grancentral", "pgrancentral.com", crudo)

        assert oferta is not None
        assert oferta.precio_cop == 9500

    def test_un_producto_de_una_sola_variante_se_lee_igual(self):
        """Casi todo el catalogo no ofrece docena y Shopify lo marca asi.

        Cuando el vendedor no define opciones, Shopify inventa una variante
        llamada 'Default Title'. No es una presentacion: es la ausencia de
        presentaciones, y hay que tomarla sin buscarle la palabra 'Unidad'.
        """
        crudo = producto("Paquete Esponja x2 Unds Arte", [variante("7700.00")])
        oferta = _a_oferta_shopify("grancentral", "pgrancentral.com", crudo)

        assert oferta is not None
        assert oferta.precio_cop == 7700

    def test_si_la_unidad_esta_agotada_no_se_cae_a_la_docena(self):
        """Agotado es agotado, y ofrecer la docena seria cambiarle el pedido.

        Se responde con la unidad marcada no disponible para que el que decide
        vea el hueco. Devolver la docena disponible lo taparia con un producto
        que el papa no pidio y cuesta diez veces mas.
        """
        crudo = producto(
            "Paquete Lentejuelas x9 Colores",
            [
                variante("5750.00", "Unidad", available=False),
                variante("56550.00", "Docena", available=True),
            ],
        )
        oferta = _a_oferta_shopify("grancentral", "pgrancentral.com", crudo)

        assert oferta is not None
        assert oferta.precio_cop == 5750
        assert oferta.disponible is False


class TestElPrecioComoNumero:
    def test_los_centavos_del_peso_no_entran_al_catalogo(self):
        """Shopify manda '5750.00' y el catalogo guarda enteros.

        El peso colombiano no tiene centavos en la practica, y los dos ceros
        son de formato. Truncar en vez de redondear evita que un '.99' de
        alguna tienda suba el precio un peso sin que nadie lo haya decidido.
        """
        crudo = producto("Cualquiera", [variante("6200.00")])
        oferta = _a_oferta_shopify("grancentral", "pgrancentral.com", crudo)

        assert oferta is not None
        assert oferta.precio_cop == 6200
        assert isinstance(oferta.precio_cop, int)

    def test_un_producto_sin_variantes_no_produce_oferta(self):
        """Sin variante no hay precio, y sin precio no hay nada que ofrecer.

        Un cero se propagaria al total del kit como si el producto fuera
        gratis, que es la misma trampa que ya tenia VTEX con los articulos que
        no se venden en linea.
        """
        assert _a_oferta_shopify("grancentral", "pgrancentral.com", producto("X", [])) is None


class TestLaBusquedaQueNoTieneBuscador:
    def test_pide_todas_las_palabras_y_no_una_cualquiera(self):
        """Shopify no ordena por relevancia, asi que el filtro es nuestro.

        Eso resulta ser una ventaja. Preguntarle 'lentejuelas' al buscador de
        Panamericana devuelve veinticuatro renos y cascanueces con traje de
        lentejuelas, porque su ranking premia la palabra suelta. Aqui el
        catalogo se baja entero y se filtra en casa: exigir TODAS las palabras
        deja fuera al reno y deja pasar el paquete.
        """
        assert _coincide("Paquete Lentejuelas x9 Colores Metro por Color", "lentejuelas")
        assert _coincide("Tabla Picado Con Tablero Acrilico", "tabla picado")
        assert not _coincide("Reno de 52 cm blanco con bufanda de lentejuelas", "tabla picado")

    def test_ignora_tildes_y_mayusculas(self):
        """Los titulos del mayorista vienen sin tildar y las consultas no.

        'Punzon Metalico' en la tienda contra 'punzón metálico' en el corpus
        es la misma cosa escrita por dos personas distintas.
        """
        assert _coincide("Punzon Metalico Para Tabla Picado", "punzón metálico")

    def test_la_palabra_va_completa_y_no_como_pedazo(self):
        """'pino' no puede traer 'pinocho', ni 'cola' traer 'colageno'.

        Buscar por pedazo de palabra es como quedo antes el sondeo de
        'esponja', que trajo tubos de espuma para piscina. El limite de
        palabra corta esa clase de parecido de pura letra.
        """
        assert not _coincide("Arbol Pinocho Decorativo", "pino")
        assert _coincide("Arbol de Pino Navideno", "pino")


class TestLaFormaDelDato:
    def test_una_oferta_de_shopify_es_una_oferta_como_la_de_vtex(self):
        """Todo lo de arriba de este modulo trata las dos tiendas igual.

        `a_candidatos`, el enriquecedor y el cargador no deberian enterarse de
        que una tienda corre sobre otra plataforma. Por eso Shopify se traduce
        a la misma `Oferta` y la diferencia muere dentro de este archivo.
        """
        crudo = producto("Paquete De Refuerzo Para Hojas Perforadas X350", [variante("4500.00")])
        oferta = _a_oferta_shopify("grancentral", "pgrancentral.com", crudo)

        assert isinstance(oferta, Oferta)
        assert oferta.tienda == "grancentral"
        assert oferta.url == "https://pgrancentral.com/products/un-producto"
        assert oferta.imagen_url == "https://cdn/foto.png"
        assert oferta.marca == "Grancentral"

    def test_sin_sku_propio_se_usa_el_id_de_la_variante(self):
        """Grancentral deja el sku vacio en casi todo su catalogo.

        La oferta necesita una referencia estable porque la base la usa para
        no duplicar (`uq_oferta_referencia`). El id de la variante cumple: es
        de la tienda, no cambia y distingue unidad de docena.
        """
        crudo = producto("Cualquiera", [variante("100.00", sku=None, id=42)])
        oferta = _a_oferta_shopify("grancentral", "pgrancentral.com", crudo)

        assert oferta is not None
        assert oferta.sku == "42"
