"""Los renglones de la auditoria de huecos del Agustiniano, con lo que deben recibir."""

from __future__ import annotations

import pytest
from kits_offline import armar_colegio, por_clave


@pytest.fixture(scope="module")
def renglon():
    lineas = por_clave(armar_colegio())
    return lineas.__getitem__


def _sku(eleccion) -> str | None:
    return eleccion.sku if eleccion else None


class TestLoQueNoSeVendeLlegaComoLinea:
    @pytest.mark.parametrize("clave", ["J#86", "1#2", "J#1", "1#7", "J#68"])
    def test_uniforme_cartilla_licencia_audifonos_y_muda(self, renglon, clave):
        linea = renglon(clave)
        assert linea.estado != "HUECO_CATALOGO"
        assert linea.informativa

    def test_un_texto_con_titulo_es_por_su_cuenta(self, renglon):
        linea = renglon("T#1")
        assert linea.tipo == "otro" and linea.informativa
        assert linea.ahorrador is None and linea.premium is None

    @pytest.mark.parametrize("clave", ["4#65", "6#27", "1#3", "8#10", "J#25", "J#87"])
    def test_lo_que_el_colegio_no_pide_comprar_no_se_cobra(self, renglon, clave):
        linea = renglon(clave)
        assert linea.ahorrador is None and linea.premium is None


def test_el_colegio_no_tiene_huecos():
    huecos = [k for k, linea in por_clave(armar_colegio()).items() if linea.estado == "HUECO_CATALOGO"]
    assert huecos == []


class TestLasFichasBlancasSonBlancas:
    def test_cada_perfil_lleva_fichas_blancas(self, renglon):
        linea = renglon("2#52")
        assert (_sku(linea.ahorrador), _sku(linea.premium)) == (
            "TK-REV-47365750194347",
            "TK-REV-44702942134443",
        )

    def test_ninguna_candidata_es_de_otro_color(self, renglon):
        colores = {(c.get("atributos") or {}).get("color") for c in renglon("2#52").candidatos}
        assert colores == {"blanco"}


class TestLasPiedrasDeTexturaSonUnSoloSet:
    def test_la_bisuteria_lleva_el_set(self, renglon):
        linea = renglon("2#71")
        assert (_sku(linea.ahorrador), _sku(linea.premium)) == ("TK-REV-603855", "TK-REV-603851")

    def test_la_jardineria_no_compra_otro(self, renglon):
        linea = renglon("2#91")
        assert linea.ahorrador is None and linea.premium is None


class TestElCuadernoDeTresMateriasEsElDeCinco:
    @pytest.mark.parametrize("clave", ["10#17", "10#24", "10#27", "11#21", "11#24"])
    def test_cada_perfil_tiene_su_cuaderno(self, renglon, clave):
        linea = renglon(clave)
        assert (_sku(linea.ahorrador), _sku(linea.premium)) == ("TK-REV-648753", "TK-REV-546276")


class TestElectronicaBatasYArtesTienenProducto:
    @pytest.mark.parametrize(
        "clave, sku",
        [
            ("6#48", "TK-REV-J01"),
            ("6#49", "TK-REV-J02"),
            ("8#63", "TK-REV-J05"),
            ("8#64", "TK-REV-J06"),
            ("1#44", "TK-REV-91c2c31c08ae"),
            ("1#45", "TK-REV-6cc17be10276"),
            ("6#50", "TK-REV-6cc17be10276"),
            ("1#46", "TK-REV-81893789"),
            ("6#51", "TK-REV-37e32267c9f2"),
            ("1#41", "TK-REV-SW06"),
            ("6#52", "TK-REV-SW35"),
            ("2#79", "TK-REV-MJUG"),
            ("6#53", "TK-REV-L37A"),
            ("8#61", "TK-REV-87e29b56aab5"),
            ("9#69", "TK-REV-SG90"),
            ("5#76", "TK-REV-APP"),
            ("7#43", "TK-REV-790637358"),
        ],
    )
    def test_el_ahorrador_cobra_el_sku_curado(self, renglon, clave, sku):
        assert _sku(renglon(clave).ahorrador) == sku

    @pytest.mark.parametrize(
        "clave, ahorrador, premium",
        [
            ("3#41", "TK-REV-7018", "TK-REV-8014"),
            ("9#46", "TK-REV-777576887", "TK-REV-790642236"),
            ("9#47", "TK-REV-790635002", "TK-REV-790635380"),
        ],
    )
    def test_cada_perfil_tiene_su_opcion(self, renglon, clave, ahorrador, premium):
        linea = renglon(clave)
        assert (_sku(linea.ahorrador), _sku(linea.premium)) == (ahorrador, premium)

    @pytest.mark.parametrize("clave", ["J#63", "6#59", "11#64"])
    def test_el_borrador_sigue_siendo_de_nata(self, renglon, clave):
        linea = renglon(clave)
        assert "nata" in linea.ahorrador.nombre.lower()
        assert "nata" in linea.premium.nombre.lower()

    def test_septimo_compra_las_dos_cintas_y_un_pegante(self, renglon):
        assert renglon("7#61").ahorrador.unidades == 1
        assert renglon("7#66").ahorrador.unidades == 1
        assert renglon("7#89").ahorrador is None


class TestLosHuecosDeLaAuditoriaV2TienenProducto:
    @pytest.mark.parametrize(
        "clave, sku",
        [
            ("J#3", "TK-REV-45938454560939"),
            ("2#10", "TK-REV-47148563103915"),
            ("J#17", "TK-REV-44702907465899"),
            ("T#40", "TK-REV-124275171"),
            ("7#12", "TK-REV-37779"),
            ("1#11", "TK-REV-47124879278251"),
            ("2#19", "TK-REV-45126710231211"),
            ("4#54", "TK-REV-124326044"),
            ("5#66", "TK-REV-628655"),
            ("T#55", "TK-REV-355583"),
            ("10#61", "TK-REV-3630108"),
        ],
    )
    def test_el_ahorrador_cobra_el_sku_curado(self, renglon, clave, sku):
        assert _sku(renglon(clave).ahorrador) == sku

    def test_un_renglon_generico_no_recibe_la_variante(self, renglon):
        assert renglon("J#75").ahorrador.sku != "TK-REV-124001157"
        assert "rojo" not in renglon("6#58").ahorrador.nombre.lower()

    def test_el_premium_tampoco_cobra_cartulina_de_un_color_por_iris(self, renglon):
        assert _sku(renglon("5#66").premium) in {"TK-REV-628655", "TK-REV-152926"}


class TestFalsosHuecosQueYaSeResuelven:
    def test_la_biblia_se_resuelve_al_libro_curado_en_el_ahorrador(self, renglon):
        assert _sku(renglon("1#1").ahorrador) == "TK-LIB-9788471512635"

    def test_el_diccionario_ingles_espanol(self, renglon):
        assert renglon("2#11").candidatos

    def test_el_sketchbook_carta_con_el_block_a4(self, renglon):
        assert _sku(renglon("3#44").ahorrador) == "TK-REV-694037"

    def test_el_archivador_de_fuelle(self, renglon):
        assert "Fuelle" in renglon("1#47").ahorrador.nombre

    def test_los_jumpers_con_el_kit_de_cuarenta(self, renglon):
        linea = renglon("8#62")
        assert _sku(linea.ahorrador) == "TK-REV-102561087"
        assert linea.ahorrador.unidades == 1

    def test_la_caja_de_marcadores_gruesos(self, renglon):
        assert _sku(renglon("J#14").ahorrador) == "TK-REV-44702849237163"

    def test_la_escuadra_de_veinte_con_la_de_veintiuno(self, renglon):
        assert _sku(renglon("4#32").ahorrador) == "TK-REV-3331144"


class TestMalElegidosQueYaCumplen:
    def test_el_kit_de_pinceles(self, renglon):
        assert "mixto" in renglon("7#39").ahorrador.nombre

    def test_la_caja_de_plumones_no_es_un_marcador_suelto(self, renglon):
        assert renglon("3#62").ahorrador.empaque >= 10

    def test_el_tajalapiz_con_portabasura(self, renglon):
        assert _sku(renglon("T#64").ahorrador) == "TK-REV-44702933385387"

    def test_los_lapices_gruesos(self, renglon):
        assert _sku(renglon("J#59").ahorrador) == "TK-REV-47663243165867"

    def test_los_colores_triangulares_gruesos(self, renglon):
        assert _sku(renglon("J#61").ahorrador) == "TK-REV-124275586"

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
    @pytest.mark.parametrize("clave", ["6#40", "8#57", "J#39", "2#52", "T#78"])
    def test_un_paquete_alcanza(self, renglon, clave):
        assert renglon(clave).ahorrador.unidades == 1

    def test_diez_hojas_son_dos_paquetes_de_cinco(self, renglon):
        linea = renglon("7#57").ahorrador
        assert linea.unidades * linea.empaque >= 10

    def test_tres_paquetes_de_octavos_son_tres_paquetes(self, renglon):
        assert renglon("J#33").ahorrador.unidades == 3

    def test_la_caja_de_colores_no_compra_doce(self, renglon):
        assert renglon("1#20").ahorrador.unidades == 1


class TestHerramientasPedidasEnVariasMaterias:
    def test_compas_y_compas_de_precision_son_un_solo_compas(self, renglon):
        uno, otro = renglon("3#35").ahorrador, renglon("3#47").ahorrador
        assert uno.sku == otro.sku
        assert sorted([uno.unidades, otro.unidades]) == [0, 1]


class TestDesempateComoElOptimizador:
    @pytest.mark.parametrize("clave", ["J#62", "T#66", "1#21", "2#43"])
    def test_las_tijeras_punta_roma_del_ahorrador_son_las_mas_baratas(self, renglon, clave):
        assert _sku(renglon(clave).ahorrador) == "TK-REV-124275363"


def test_con_todo_igual_gana_el_primero_de_la_ruta_rapida():
    from kits_offline import _clave_ahorrador, _clave_premium, _mejor

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

    sin_precio = [producto("P", "premium", None), producto("C", "confiable", 9000)]
    assert _mejor(sin_precio, _clave_premium, 1)["sku"] == "C"


class TestLaCajaNoReemplazaALaUnidad:
    @pytest.mark.parametrize("clave", ["1#58", "J#96"])
    def test_un_marcador_borrable_no_es_la_caja_de_diez(self, renglon, clave):
        linea = renglon(clave)
        assert linea.ahorrador.empaque == 1
        assert linea.premium.empaque == 1

    def test_un_pincel_redondo_no_es_un_set(self, renglon):
        assert renglon("T#41").premium.empaque == 1

    @pytest.mark.parametrize("clave", ["4#54", "6#34", "11#54"])
    def test_el_estuche_doble_punta_es_doble_punta(self, renglon, clave):
        assert "doble punta" in renglon(clave).ahorrador.nombre.lower()

    def test_el_cuaderno_kiut_cuenta_como_cinco_materias(self, renglon):
        assert "TK-REV-546276" in {c["sku"] for c in renglon("8#17").candidatos}
