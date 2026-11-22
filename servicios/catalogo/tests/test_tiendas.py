from tukit_catalogo.tiendas import Oferta, _a_oferta_shopify, _coincide


def producto(titulo: str, variantes: list[dict], **extra) -> dict:
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
        unidad, docena = 9500, 94200
        crudo = producto(
            "Tabla Picado Con Tablero Acrilico",
            [variante(f"{docena}.00", "Docena"), variante(f"{unidad}.00", "Unidad")],
        )
        oferta = _a_oferta_shopify("grancentral", "pgrancentral.com", crudo)

        assert oferta is not None
        assert oferta.precio_cop == unidad

    def test_un_producto_de_una_sola_variante_se_lee_igual(self):
        precio = 7700
        crudo = producto("Paquete Esponja x2 Unds Arte", [variante(f"{precio}.00")])
        oferta = _a_oferta_shopify("grancentral", "pgrancentral.com", crudo)

        assert oferta is not None
        assert oferta.precio_cop == precio

    def test_si_la_unidad_esta_agotada_no_se_cae_a_la_docena(self):
        unidad, docena = 5750, 56550
        crudo = producto(
            "Paquete Lentejuelas x9 Colores",
            [
                variante(f"{unidad}.00", "Unidad", available=False),
                variante(f"{docena}.00", "Docena", available=True),
            ],
        )
        oferta = _a_oferta_shopify("grancentral", "pgrancentral.com", crudo)

        assert oferta is not None
        assert oferta.precio_cop == unidad
        assert oferta.disponible is False


class TestElPrecioComoNumero:
    def test_los_centavos_del_peso_no_entran_al_catalogo(self):
        crudo = producto("Cualquiera", [variante("6200.99")])
        oferta = _a_oferta_shopify("grancentral", "pgrancentral.com", crudo)

        assert oferta is not None
        assert oferta.precio_cop == 6200
        assert isinstance(oferta.precio_cop, int)

    def test_un_producto_sin_variantes_no_produce_oferta(self):
        assert _a_oferta_shopify("grancentral", "pgrancentral.com", producto("X", [])) is None


class TestLaBusquedaQueNoTieneBuscador:
    def test_pide_todas_las_palabras_y_no_una_cualquiera(self):
        assert _coincide("Paquete Lentejuelas x9 Colores Metro por Color", "lentejuelas")
        assert _coincide("Tabla Picado Con Tablero Acrilico", "tabla picado")
        assert not _coincide("Reno de 52 cm blanco con bufanda de lentejuelas", "tabla picado")

    def test_ignora_tildes_y_mayusculas(self):
        assert _coincide("Punzon Metalico Para Tabla Picado", "punzón metálico")

    def test_la_palabra_va_completa_y_no_como_pedazo(self):
        assert not _coincide("Arbol Pinocho Decorativo", "pino")
        assert _coincide("Arbol de Pino Navideno", "pino")


class TestLaFormaDelDato:
    def test_una_oferta_de_shopify_es_una_oferta_como_la_de_vtex(self):
        crudo = producto("Paquete De Refuerzo Para Hojas Perforadas X350", [variante("4500.00")])
        oferta = _a_oferta_shopify("grancentral", "pgrancentral.com", crudo)

        assert isinstance(oferta, Oferta)
        assert oferta.tienda == "grancentral"
        assert oferta.url == "https://pgrancentral.com/products/un-producto"
        assert oferta.imagen_url == "https://cdn/foto.png"
        assert oferta.marca == "Grancentral"

    def test_sin_sku_propio_se_usa_el_id_de_la_variante(self):
        crudo = producto("Cualquiera", [variante("100.00", sku=None, id=42)])
        oferta = _a_oferta_shopify("grancentral", "pgrancentral.com", crudo)

        assert oferta is not None
        assert oferta.sku == "42"
