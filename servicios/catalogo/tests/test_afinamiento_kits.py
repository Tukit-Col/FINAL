"""Lo que la auditoria de huecos del Agustiniano (2026-10-11) encontro mal elegido.

Cada prueba nombra el renglon de la auditoria que la motivo (`grado#orden`,
ver `docs/informes/nuevo-reporte-huecos-agustiniano.md`). Los textos son los
de la lista oficial, copiados tal cual, con sus erratas.
"""

from __future__ import annotations

from types import SimpleNamespace

from tukit_catalogo.consulta import _cumple
from tukit_catalogo.enriquecer import Empaque, empaque_combinado, extraer_atributos, extraer_empaque
from tukit_catalogo.routers.admin import _renglon_resuelto, armar_items


def _p(sku: str, atributos: dict, nivel: str = "confiable", precio: int = 1000, **extra) -> dict:
    return {
        "id": sku,
        "sku": sku,
        "nombre": sku,
        "nivel": nivel,
        "personaje": None,
        "atributos": atributos,
        "precio_cop": precio,
        "unidades_por_empaque": 1,
        **extra,
    }


class TestComoSeComparaCadaAtributo:
    """Respuesta a 5.1: exacto lo que cambia que cosa es, flexible lo que se mide."""

    def test_las_hojas_valen_si_son_al_menos_las_pedidas(self):
        # 1#15: ferrocarril cosido de 80 hojas; el unico ferrocarril es de 100.
        assert _cumple(_p("a", {"hojas": 100}), {"hojas": 80})
        assert not _cumple(_p("a", {"hojas": 50}), {"hojas": 80})

    def test_las_hojas_no_valen_si_son_mas_del_doble(self):
        assert not _cumple(_p("a", {"hojas": 200}), {"hojas": 80})

    def test_las_materias_son_exactas(self):
        assert not _cumple(_p("a", {"materias": 5}), {"materias": 3})
        assert not _cumple(_p("a", {"materias": "multiple"}), {"materias": 3})

    def test_la_longitud_admite_un_poco_mas_y_casi_nada_menos(self):
        # 4#32: escuadra de 20 cm; la de 45 grados del catalogo es de 26 cm.
        assert _cumple(_p("a", {"longitud": "26 cm"}), {"longitud": "20 cm"})
        assert _cumple(_p("a", {"longitud": "300 mm"}), {"longitud": "30 cm"})
        assert not _cumple(_p("a", {"longitud": "20 cm"}), {"longitud": "30 cm"})

    def test_carta_y_a4_son_equivalentes(self):
        # 3#44: sketch book carta; el block de bocetos es A4.
        assert _cumple(_p("a", {"tamano": "a4"}), {"tamano": "carta"})
        assert not _cumple(_p("a", {"tamano": "oficio"}), {"tamano": "carta"})

    def test_las_medidas_admiten_una_cuarta_parte_por_lado(self):
        # 1#25: lienzo de 25x25; hay uno de 20 x 30 y otro de 50 x 70.
        assert _cumple(_p("a", {"tamano": "20 x 30 cm"}), {"tamano": "25 x 25 cm"})
        assert not _cumple(_p("a", {"tamano": "50 x 70 cm"}), {"tamano": "25 x 25 cm"})

    def test_frasco_y_tarro_son_lo_mismo(self):
        assert _cumple(_p("a", {"presentacion": "tarro"}), {"presentacion": "frasco"})

    def test_antifluido_cumple_lo_que_pide_plastico(self):
        # 3#52: protector para ropa (delantal plastico); el delantal es antifluido.
        assert _cumple(_p("a", {"material": "antifluido"}), {"material": "plastico"})
        assert not _cumple(_p("a", {"material": "tela"}), {"material": "antifluido"})

    def test_las_unidades_valen_si_son_al_menos_las_pedidas(self):
        assert _cumple(_p("a", {"unidades": 15}), {"unidades": 12})
        assert not _cumple(_p("a", {"unidades": 10}), {"unidades": 12})
        assert not _cumple(_p("a", {}), {"unidades": 2})

    def test_el_peso_vale_si_es_al_menos_el_pedido(self):
        # T#67: pegante en barra de 125 g; la mayor del catalogo es de 40 g.
        assert not _cumple(_p("a", {"peso": "40 g"}), {"peso": "125 g"})

    def test_las_protoboards_valen_si_tienen_al_menos_los_puntos_y_no_demasiados(self):
        # 9#63: protoboard de 830 puntos; se cobraba la de 400.
        assert _cumple(_p("a", {"puntos": 840}), {"puntos": 830})
        assert not _cumple(_p("a", {"puntos": 400}), {"puntos": 830})
        assert not _cumple(_p("a", {"puntos": 2200}), {"puntos": 400})

    def test_de_ingles_acepta_el_bilingue_y_ingles_ingles_solo_el_monolingue(self):
        assert _cumple(_p("a", {"idioma": "espanol-ingles"}), {"idioma": "ingles"})
        assert not _cumple(_p("a", {"idioma": "espanol-ingles"}), {"idioma": "ingles-ingles"})
        assert not _cumple(_p("a", {"idioma": "espanol-ingles"}), {"idioma": "espanol"})
        assert _cumple(_p("a", {"idioma": "espanol"}), {"idioma": "espanol"})

    def test_lo_que_no_se_declara_no_cumple(self):
        assert not _cumple(_p("a", {}), {"tamano": "oficio"})


class TestLoQueElExtractorLeiaMal:
    def test_las_materias_escritas_en_letras(self):
        # 11#21: "cuaderno tres materias" se leia como de una materia.
        assert extraer_atributos("cuaderno tres materias cuadriculado grande", ("materias",)) == {
            "materias": 3
        }
        assert extraer_atributos("Cuaderno 5 materias", ("materias",)) == {"materias": 5}

    def test_el_tamano_en_plural(self):
        # 1#39 y J#40: "cuartos" y "pliegos" no se leian.
        assert extraer_atributos("cuartos de cartulina blanca", ("tamano",)) == {"tamano": "cuarto"}
        assert extraer_atributos("pliegos de papel Cartulina blanca", ("tamano",)) == {"tamano": "pliego"}

    def test_las_medidas_en_cms(self):
        assert extraer_atributos("Lienzo de 25x25cms", ("tamano",)) == {"tamano": "25 x 25 cm"}

    def test_el_numero_del_pincel_con_espacio(self):
        # T#40: "pincel plano # 10".
        assert extraer_atributos("pincel plano # 10", ("grosor",)) == {"grosor": "n10"}

    def test_la_longitud_en_pulgadas(self):
        # 10#59: tijeras de 8,5 pulgadas.
        assert extraer_atributos("Tijeras 8,5 pulgadas", ("longitud",)) == {"longitud": "8.5 in"}

    def test_lo_que_dice_el_tipo_de_block(self):
        # 2#10 y 3#16.
        assert extraer_atributos("Block tamaño carta a rayas", ("tipo",)) == {"tipo": "rayado"}
        assert extraer_atributos("blocks de hojas blancas tamano carta", ("tipo",)) == {"tipo": "blanco"}

    def test_el_acabado_de_la_cartulina(self):
        # J#38: cartulina fluorescente.
        texto = "paquetes de octavos de cartulina fluorescente colores surtidos"
        assert extraer_atributos(texto, ("acabado",)) == {"acabado": "fluorescente"}

    def test_palabras_de_las_listas_que_no_se_leian(self):
        assert extraer_atributos("tajalápiz con portabasura", ("deposito",)) == {"deposito": True}
        assert extraer_atributos("tijeras puntaroma", ("punta",)) == {"punta": "punta roma"}
        assert extraer_atributos("maleta de rodachines", ("tipo",)) == {"tipo": "con ruedas"}
        assert extraer_atributos("caja de pañuelos faciales", ("tipo",)) == {"tipo": "panuelo"}
        assert extraer_atributos("palos de pincho largos", ("tipo",)) == {"tipo": "pincho"}
        assert extraer_atributos("Pliegos de papel celofán", ("tipo",)) == {"tipo": "celofan"}
        assert extraer_atributos("caja de plastilina gigante larga x12", ("tipo",)) == {"tipo": "gigante"}

    def test_la_manga_de_la_bata(self):
        assert extraer_atributos("Bata para artes con mangas", ("manga",)) == {"manga": "larga"}
        assert extraer_atributos("Bata Unisex Manga Corta Talla Xl", ("manga",)) == {"manga": "corta"}

    def test_antifluido_es_un_material(self):
        assert extraer_atributos("Bata de laboratorio de material antifluido", ("material",)) == {
            "material": "antifluido"
        }

    def test_el_tarro_se_lee_como_frasco(self):
        assert extraer_atributos("Tarro Vinilo Payasito x1000 Gramos Azul", ("presentacion",)) == {
            "presentacion": "frasco"
        }

    def test_cuantas_notas_trae_el_xilofono(self):
        assert extraer_atributos("Xilófono de 8 placas con baquetas", ("notas",)) == {"notas": 8}
        assert extraer_atributos("Xilofono Marimba 8 Tonos Piano Gato", ("notas",)) == {"notas": 8}

    def test_el_jumbo_es_grueso(self):
        assert extraer_atributos("Lapiz Kores Jumbo x12", ("grosor",)) == {"grosor": "grueso"}

    def test_el_idioma_no_depende_del_orden(self):
        # 2#11 y 2#15: el mismo diccionario escrito en los dos ordenes.
        assert extraer_atributos("Diccionario Larousse Basico Ingles - español", ("idioma",)) == {
            "idioma": "espanol-ingles"
        }
        assert extraer_atributos("Diccionario Inglés – Inglés", ("idioma",)) == {"idioma": "ingles-ingles"}
        assert extraer_atributos("Diccionario de inglés", ("idioma",)) == {"idioma": "ingles"}

    def test_la_docena_es_un_empaque(self):
        # J#93: "Docena Barra Silicona Gruesa" se compraba de a una barra.
        assert extraer_empaque("Docena Barra Silicona Gruesa").unidades == 12


class TestElEmpaqueCurado:
    def test_lo_guardado_gana_sobre_lo_leido(self):
        # Una correccion a mano en la UI de admin no la deshace `enriquecer`.
        assert empaque_combinado(25, "hoja", Empaque(1, "unidad")) == Empaque(25, "hoja")

    def test_el_uno_por_omision_lo_reemplaza_lo_leido(self):
        assert empaque_combinado(1, "unidad", Empaque(12, "unidad")) == Empaque(12, "unidad")


class TestElRenglonDeLaRutaRapida:
    def test_un_valor_curado_asterisco_quita_lo_leido(self):
        # T#69: la receta para armar la bitacora ponia `hojas=15`.
        texto = "bitacora tamaño octavo. 15 hojas de cartulina blanca"
        productos = [_p("dibujo", {"rayado": "blanco"})]
        candidatos, impuestos, _ = _renglon_resuelto(texto, {"hojas": "*"}, productos, ("hojas", "rayado"))
        assert "hojas" not in impuestos
        assert [c["sku"] for c in candidatos] == ["dibujo"]

    def test_un_kit_de_pinceles_pide_varios_y_no_el_grosor_de_cada_uno(self):
        # 7#39: el kit de 12 pinceles se resolvia con un solo pincel delgado.
        texto = "Kit de 12 pinceles sintéticos. delgados, planos redondos y abanico"
        productos = [
            _p("suelto", {"grosor": "delgado", "forma": "redondo"}, precio=500),
            _p("set", {"unidades": 15}, precio=26900),
        ]
        candidatos, impuestos, _ = _renglon_resuelto(texto, {}, productos, ("grosor", "forma", "unidades"))
        assert impuestos == {"unidades": 12}
        assert [c["sku"] for c in candidatos] == ["set"]

    def test_una_caja_sin_numero_pide_mas_de_uno(self):
        # 3#62: "caja de plumones" se resolvia con un marcador suelto.
        productos = [_p("suelto", {}, precio=4400), _p("caja", {"unidades": 12}, precio=10900)]
        candidatos, _, _ = _renglon_resuelto("caja de plumones", {}, productos, ("punta", "unidades"))
        assert [c["sku"] for c in candidatos] == ["caja"]

    def test_un_plural_con_cantidad_uno_pide_mas_de_uno(self):
        # 7#87: "marcadores", cantidad 1.
        productos = [_p("suelto", {}, precio=4400), _p("caja", {"unidades": 12}, precio=10900)]
        candidatos, _, _ = _renglon_resuelto("marcadores", {}, productos, ("punta", "unidades"), cantidad=1)
        assert [c["sku"] for c in candidatos] == ["caja"]
        candidatos, _, _ = _renglon_resuelto(
            "marcadores permanentes negros", {}, productos, ("punta", "unidades"), cantidad=2
        )
        assert {c["sku"] for c in candidatos} == {"suelto", "caja"}

    def test_si_ningun_juego_cumple_vale_la_pieza_suelta(self):
        # 3#88: "Pinceles de punta redonda". No hay juego de pinceles redondos.
        productos = [_p("redondo", {"forma": "redondo"}), _p("planos", {"forma": "plano", "unidades": 4})]
        candidatos, impuestos, _ = _renglon_resuelto(
            "Pinceles de punta redonda", {}, productos, ("forma", "unidades"), cantidad=1
        )
        assert [c["sku"] for c in candidatos] == ["redondo"]
        assert "unidades" not in impuestos

    def test_un_juego_de_piezas_iguales_si_exige_como_es_cada_una(self):
        # J#61: "cajas de colores x 12 triangulares gruesos".
        productos = [
            _p("delgados", {"unidades": 12, "grosor": "delgado"}, precio=6100),
            _p("gruesos", {"unidades": 12, "grosor": "grueso", "forma": "triangular"}, precio=24890),
        ]
        candidatos, impuestos, _ = _renglon_resuelto(
            "cajas de colores x 12 triangulares gruesos", {}, productos, ("unidades", "forma", "grosor"), 24
        )
        assert impuestos == {"unidades": 12, "forma": "triangular", "grosor": "grueso"}
        assert [c["sku"] for c in candidatos] == ["gruesos"]


def _fila(orden: int, texto: str, concepto: str | None, tipo: str | None = None, cantidad: int = 1, **extra):
    return SimpleNamespace(
        id=f"i{orden}",
        orden=orden,
        texto_original=texto,
        cantidad=cantidad,
        tipo_item=tipo,
        modo_adquisicion="mercado_abierto",
        concepto_codigo=concepto,
        concepto_nombre=concepto,
        instruccion_colegio=None,
        url_externa=None,
        atributos=extra.get("atributos", {}),
        avisos_descartados=[],
    )


class TestLosRenglonesDeUnaVersion:
    def test_sin_tipo_en_el_renglon_manda_el_del_concepto(self):
        # 3.1: la ruta rapida veia `util` en un uniforme y decia "No lo tenemos".
        reglas = {"C131": ((), False, "uniforme"), "C001": ((), False, "util")}
        items = armar_items(
            [_fila(1, "Uniforme de diario", "C131"), _fila(2, "cuaderno", "C001", tipo="no_comprar")],
            {},
            reglas,
        )
        assert [i["tipo_item"] for i in items] == ["uniforme", "no_comprar"]

    def test_una_herramienta_pedida_en_dos_materias_sale_del_mismo_producto(self):
        # 3#35 y 3#47: "compas" y "compas de precision". El Ahorrador compraba dos.
        reglas = {"C018": (("tipo",), True, "util")}
        productos = {
            "C018": [
                _p("escolar", {}, precio=14900),
                _p("precision", {"tipo": "precision"}, precio=22990),
            ]
        }
        items = armar_items(
            [_fila(1, "compas", "C018"), _fila(2, "compas de precision", "C018")], productos, reglas
        )
        assert [[c["sku"] for c in i["candidatos"]] for i in items] == [["precision"], ["precision"]]

    def test_si_no_hay_producto_comun_cada_renglon_conserva_los_suyos(self):
        reglas = {"C008": (("material",), True, "util")}
        productos = {"C008": [_p("plastica", {"material": "plastico"})]}
        items = armar_items(
            [_fila(1, "regla de 30 cm", "C008"), _fila(2, "regla de acero inoxidable", "C008")],
            productos,
            reglas,
        )
        assert [[c["sku"] for c in i["candidatos"]] for i in items] == [["plastica"], []]
