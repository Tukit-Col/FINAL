from __future__ import annotations

from tukit_inteligencia.parseo import mensaje_para_papa, parsear_renglon


class TestLoQueNoSeCompraNoSeBusca:
    def test_el_disponible_en_casa_es_no_comprar(self):
        demanda = parsear_renglon("Diccionario: el disponible en casa")

        assert demanda.tipo_item == "no_comprar"
        assert demanda.cantidad == 0
        assert demanda.busca_en_catalogo is False

    def test_lo_que_se_pedira_despues_queda_diferido(self):
        demanda = parsear_renglon(
            "Durante el ano se incluiran algunos textos. Seran solicitados con anterioridad."
        )

        assert demanda.tipo_item == "diferido"
        assert demanda.busca_en_catalogo is False

    def test_la_licencia_con_link_no_entra_al_carrito(self):
        demanda = parsear_renglon(
            "Plan lector virtual RAZ-PLUS, administrada por QUOVIX. Link de pago: https://pagoslearning.com/"
        )

        assert demanda.tipo_item == "licencia_digital"
        assert demanda.url_externa == "https://pagoslearning.com/"
        assert demanda.busca_en_catalogo is False

    def test_el_libro_para_colorear_es_papeleria(self):
        for renglon in (
            "Libro para colorear",
            "Libro pasatiempo",
            "libro de recortes",
            "Libro didactico para colorear",
            "revista didactica para recortar",
        ):
            demanda = parsear_renglon(renglon)
            assert demanda.tipo_item == "util", renglon
            assert demanda.busca_en_catalogo is True

    def test_cualquier_editorial_si_se_busca(self):
        demanda = parsear_renglon("La casa de los espiritus. Autor: Isabella Allende. Cualquier editorial")

        assert demanda.tipo_item == "libro_libre"
        assert demanda.busca_en_catalogo is True

    def test_la_edicion_que_manda_el_colegio_no_se_empareja(self):
        demanda = parsear_renglon("Filo. Mi amigo imaginario. Mapi y Fabio Sardo. Editorial Enlace.")

        assert demanda.tipo_item == "texto"
        assert demanda.busca_en_catalogo is False


class TestLaCantidadNoSeConfundeConElEmpaque:
    def test_doce_lapices_son_doce_unidades(self):
        demanda = parsear_renglon("12 lapices")

        assert demanda.cantidad == 12
        assert demanda.unidades_por_empaque is None

    def test_la_caja_se_anota_aparte_de_la_cantidad(self):
        demanda = parsear_renglon("1 caja de lapices x 12")

        assert demanda.cantidad == 1
        assert demanda.unidades_por_empaque == 12

    def test_la_cantidad_que_viene_en_columna_aparte_no_se_duplica(self):
        demanda = parsear_renglon("Cuaderno cuadriculado", cantidad=2)

        assert demanda.cantidad == 2

    def test_los_metros_no_son_un_empaque(self):
        demanda = parsear_renglon("1 metro de lentejuelas")

        assert demanda.unidades_por_empaque is None
        assert demanda.cantidad == 1


class TestLoQueElJardinVendeNoSeBusca:
    def test_el_arroba_del_margen_no_hace_parte_del_pedido(self):
        demanda = parsear_renglon("@EXPEDICION MATEMATICA / EDITORIAL ENCUENTRO.")

        assert demanda.texto.startswith("EXPEDICION")
        assert demanda.tipo_item == "texto"

    def test_lo_que_se_compra_en_el_jardin_no_entra_al_catalogo(self):
        demanda = parsear_renglon(
            "CARPETA IDEAS CREATIVAS, la puede adquirir directamente en el jardin con un 10% de descuento"
        )

        assert demanda.tipo_item == "util"
        assert demanda.modo_adquisicion == "venta_directa_editorial"
        assert demanda.busca_en_catalogo is False
        assert mensaje_para_papa(demanda) == (
            "Se adquiere directamente en el colegio. Tukit no lo incluye en la compra."
        )

    def test_el_texto_de_venta_directa_no_lo_surte_tukit(self):
        demanda = parsear_renglon(
            "EXPEDICION MATEMATICA / EDITORIAL ENCUENTRO. "
            "Este texto se debe adquirir directamente con la editorial."
        )

        assert demanda.tipo_item == "texto"
        assert demanda.modo_adquisicion == "venta_directa_editorial"
        assert demanda.busca_en_catalogo is False
        assert mensaje_para_papa(demanda) == (
            "Se compra directamente con la editorial. Tukit no lo incluye en la compra."
        )

    def test_lo_que_no_se_busca_lleva_mensaje_para_el_papa(self):
        casos = (
            (
                "Diccionario: el disponible en casa",
                "No hay que comprarlo. Ya se tiene en casa.",
            ),
            (
                "Durante el ano se incluiran algunos textos. Seran solicitados con anterioridad.",
                "Se compra más adelante. Todavía no entra en este kit.",
            ),
            (
                "Plan lector virtual RAZ-PLUS. Link de pago: https://pagoslearning.com/",
                "Es una licencia digital. No se busca en la tienda de útiles.",
            ),
            (
                "Uniforme diario segun modelo del colegio",
                "Aún no lo proveemos. El colegio indica cómo conseguirlo.",
            ),
        )
        for renglon, esperado in casos:
            demanda = parsear_renglon(renglon)
            assert demanda.busca_en_catalogo is False, renglon
            assert mensaje_para_papa(demanda) == esperado, renglon

    def test_lo_que_si_se_busca_no_lleva_mensaje_de_estado(self):
        demanda = parsear_renglon("2 lapices negros")

        assert demanda.busca_en_catalogo is True
        assert mensaje_para_papa(demanda) == ""
