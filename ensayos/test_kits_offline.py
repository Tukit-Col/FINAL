"""Los renglones de la auditoria de huecos del Agustiniano, con lo que deben recibir.

Corre sobre `datos/` tal como esta, sin base de datos (`kits_offline.py`). Si
una curaduria o un cambio de codigo vuelve a romper uno de estos renglones, se
sabe aqui y no en la siguiente auditoria. La referencia de cada caso es la
seccion de `docs/informes/auditoria-huecos-agustiniano/v2-d4ea7cb.md` que lo trata.
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
    """Lo que ninguna tienda registrada vende: sigue siendo hueco, no un sustituto."""

    @pytest.mark.parametrize(
        "clave",
        ["3#41", "8#63", "1#44", "1#45", "9#46", "2#71", "6#53", "7#43", "8#61"],
    )
    def test_no_se_cobra_un_sustituto(self, renglon, clave):
        # Bata antifluido, jumpers macho-hembra, caimanes, LED, ecoline, piedras,
        # motorreductor, acrilico cian y Arduino.
        assert renglon(clave).estado == "HUECO_CATALOGO"


class TestLoQueTrajoElSurtidoDelDoceDeOctubre:
    """Huecos de la auditoria v2 que se cerraron con productos aprobados en la cola."""

    @pytest.mark.parametrize(
        "clave, sku",
        [
            ("J#3", "TK-REV-45938454560939"),  # cuaderno de cuadros de 1 cm
            ("2#10", "TK-REV-47148563103915"),  # block rayado carta
            ("J#17", "TK-REV-44702907465899"),  # vinilo amarillo de 125 g
            ("T#40", "TK-REV-124275171"),  # pincel plano #10
            ("7#12", "TK-REV-37779"),  # diccionario ingles-ingles
            ("1#11", "TK-REV-47124879278251"),  # sobre de acetato grueso oficio
            ("2#19", "TK-REV-45126710231211"),  # metro de costura
            # «de 12 o 18 unidades»: el renglon extrae 18 y la curaduria lo deja en 12.
            ("4#54", "TK-REV-124326044"),
            # Block de cartulina multicolor A4 en vez del paquete iris x100 de $63.800.
            ("5#66", "TK-REV-628655"),
            ("T#55", "TK-REV-355583"),  # libro para colorear
            # «papel iris octavos»: no hay papel iris en octavos; se cura a carta.
            ("10#61", "TK-REV-3630108"),
        ],
    )
    def test_el_ahorrador_cobra_el_producto_nuevo(self, renglon, clave, sku):
        assert _sku(renglon(clave).ahorrador) == sku

    def test_un_renglon_generico_no_recibe_la_variante(self, renglon):
        # «paquete de cartulina arte por octavos» no es la fluorescente, y
        # «lapices» a secas no es el lapiz rojo.
        assert renglon("J#75").ahorrador.sku != "TK-REV-124001157"
        assert "rojo" not in renglon("6#58").ahorrador.nombre.lower()

    def test_el_premium_tampoco_cobra_cartulina_de_un_color_por_iris(self, renglon):
        assert _sku(renglon("5#66").premium) == "TK-REV-628655"


class TestFalsosHuecosQueYaSeResuelven:
    def test_la_biblia(self, renglon):
        assert _sku(renglon("1#1").ahorrador) == "TK-LIB-9788471512635"

    def test_el_diccionario_ingles_espanol(self, renglon):
        assert renglon("2#11").candidatos

    def test_el_sketchbook_carta_con_el_block_a4(self, renglon):
        assert _sku(renglon("3#44").ahorrador) == "TK-C003-PRE"

    def test_el_archivador_de_fuelle(self, renglon):
        # Por el nombre: `nivelar` le cambia el sku semilla cuando cambia su nivel.
        assert "Fuelle" in renglon("1#47").ahorrador.nombre

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


class TestDesempateComoElOptimizador:
    """Dos productos con el mismo costo de linea: gana el de mejor nivel.

    En el frente de Pareto, a igual costo, la solucion de mejor nivel domina a la
    otra, asi que el Ahorrador del optimizador no puede tomar la de nivel menor.
    Las tijeras punta roma Milan (confiable) y Nessan (premium) cuestan lo mismo.
    """

    @pytest.mark.parametrize("clave", ["J#62", "T#66", "1#21", "2#43"])
    def test_las_tijeras_punta_roma_del_ahorrador_son_las_de_mejor_nivel(self, renglon, clave):
        assert _sku(renglon(clave).ahorrador) == "TK-C013-PRE"


def test_con_todo_igual_gana_el_primero_de_la_ruta_rapida():
    from ensayos.kits_offline import _clave_ahorrador, _clave_premium, _mejor

    def producto(sku, nivel, precio, personaje=None):
        return {
            "sku": sku,
            "nivel": nivel,
            "precio_cop": precio,
            "unidades_por_empaque": 1,
            "personaje": personaje,
        }

    candidatos = [producto("B", "confiable", 5000), producto("A", "confiable", 5000)]
    assert _mejor(candidatos, _clave_ahorrador, 1)["sku"] == "B"
    assert _mejor(candidatos, _clave_premium, 1)["sku"] == "B"

    # El Premium no toma un producto sin precio aunque sea de mejor nivel (`_surtibles`).
    sin_precio = [producto("P", "premium", None), producto("C", "confiable", 9000)]
    assert _mejor(sin_precio, _clave_premium, 1)["sku"] == "C"
