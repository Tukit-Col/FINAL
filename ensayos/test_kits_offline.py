"""Los renglones de la auditoria de huecos del Agustiniano, con lo que deben recibir.

Corre sobre `datos/` tal como esta, sin base de datos (`kits_offline.py`). Si
una curaduria o un cambio de codigo vuelve a romper uno de estos renglones, se
sabe aqui y no en la siguiente auditoria. La referencia de cada caso es la
seccion de `docs/informes/nuevo-reporte-huecos-agustiniano.md` que lo trata.
"""

from __future__ import annotations

import pytest

from ensayos.kits_offline import armar_colegio, por_clave


@pytest.fixture(scope="module")
def renglon():
    lineas = por_clave(armar_colegio())
    return lineas.__getitem__


def _sku(eleccion) -> str | None:
    return eleccion.sku if eleccion else None


class TestLoQueNoSeVendeLlegaComoLinea:
    """3.1: con el tipo del concepto, ya no se muestra "No lo tenemos"."""

    @pytest.mark.parametrize("clave", ["J#86", "1#2", "J#1", "1#7", "J#68"])
    def test_uniforme_cartilla_licencia_audifonos_y_muda(self, renglon, clave):
        linea = renglon(clave)
        assert linea.estado != "HUECO_CATALOGO"
        assert linea.informativa

    def test_un_texto_con_titulo_es_por_su_cuenta(self, renglon):
        assert renglon("T#1").estado == "SIN_MATCH"

    @pytest.mark.parametrize("clave", ["4#65", "6#27", "1#3", "8#10", "J#25", "J#87"])
    def test_lo_que_el_colegio_no_pide_comprar_no_se_cobra(self, renglon, clave):
        linea = renglon(clave)
        assert linea.ahorrador is None and linea.premium is None


class TestHuecosReales:
    @pytest.mark.parametrize(
        "clave",
        [
            "J#3",
            "2#10",
            "3#16",
            "J#40",
            "1#39",
            "J#38",
            "10#59",
            "T#40",
            "7#12",
            "8#63",
            "T#67",
            "3#41",
            "1#11",
        ],
    )
    def test_no_se_cobra_un_sustituto(self, renglon, clave):
        assert renglon(clave).estado == "HUECO_CATALOGO"


class TestFalsosHuecosQueYaSeResuelven:
    def test_la_biblia(self, renglon):
        assert _sku(renglon("1#1").ahorrador) == "TK-LIB-9788471512635"

    def test_el_diccionario_ingles_espanol(self, renglon):
        assert renglon("2#11").candidatos

    def test_el_sketchbook_carta_con_el_block_a4(self, renglon):
        assert _sku(renglon("3#44").ahorrador) == "TK-C003-PRE"

    def test_el_archivador_de_fuelle(self, renglon):
        assert _sku(renglon("1#47").ahorrador) == "TK-C011-CON"

    def test_los_jumpers_con_el_kit_de_cuarenta(self, renglon):
        linea = renglon("8#62")
        assert _sku(linea.ahorrador) == "TK-REV-102561087"
        assert linea.ahorrador.unidades == 1

    def test_la_caja_de_marcadores_gruesos(self, renglon):
        assert _sku(renglon("J#14").ahorrador) == "TK-REV-632443"

    def test_la_escuadra_de_veinte_con_la_de_veintiseis(self, renglon):
        assert _sku(renglon("4#32").ahorrador) == "TK-C019-ECO"


class TestMalElegidosQueYaCumplen:
    def test_el_kit_de_pinceles(self, renglon):
        assert _sku(renglon("7#39").ahorrador) == "TK-C021-CON"

    def test_la_caja_de_plumones_no_es_un_marcador_suelto(self, renglon):
        assert renglon("3#62").ahorrador.empaque >= 10

    def test_el_tajalapiz_con_portabasura(self, renglon):
        assert _sku(renglon("T#64").ahorrador) == "TK-C007-PRE"

    def test_los_lapices_gruesos(self, renglon):
        assert _sku(renglon("J#59").ahorrador) == "TK-C002-PRE"

    def test_los_colores_triangulares_gruesos(self, renglon):
        assert _sku(renglon("J#61").ahorrador) == "TK-REV-100717597"

    def test_la_protoboard_de_830(self, renglon):
        assert renglon("9#63").ahorrador.sku == "TK-REV-104905872"

    def test_la_protoboard_de_400(self, renglon):
        assert _sku(renglon("6#47").ahorrador) == "TK-REV-101119299"

    def test_el_premium_no_cobra_el_pincel_de_agua(self, renglon):
        assert _sku(renglon("J#73").premium) != "TK-REV-517439"

    def test_el_premium_no_cobra_el_diccionario_aleman(self, renglon):
        assert _sku(renglon("8#6").premium) != "TK-C034-PRE"

    def test_la_cartuchera_no_es_de_personaje(self, renglon):
        assert renglon("J#58").ahorrador.personaje is None


class TestEmpaqueYCantidad:
    """3.4: el kit compra los paquetes que cubren lo pedido, no uno por unidad."""

    @pytest.mark.parametrize("clave", ["6#40", "7#57", "8#57", "J#39", "2#52", "T#78"])
    def test_un_paquete_alcanza(self, renglon, clave):
        assert renglon(clave).ahorrador.unidades == 1

    def test_tres_paquetes_de_octavos_son_tres_paquetes(self, renglon):
        assert renglon("J#33").ahorrador.unidades == 3

    def test_la_caja_de_colores_no_compra_doce(self, renglon):
        assert renglon("1#20").ahorrador.unidades == 1


class TestHerramientasPedidasEnVariasMaterias:
    def test_compas_y_compas_de_precision_son_un_solo_compas(self, renglon):
        # 3.5: el Ahorrador compraba dos compases.
        uno, otro = renglon("3#35").ahorrador, renglon("3#47").ahorrador
        assert uno.sku == otro.sku
        assert sorted([uno.unidades, otro.unidades]) == [0, 1]
