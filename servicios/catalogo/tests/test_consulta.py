from __future__ import annotations

import inspect
import uuid
from pathlib import Path

from tukit_catalogo.consulta import Emparejamiento, emparejar

BLOCK = uuid.UUID("00000000-0000-0000-0000-0000000000b1")
COLORES = uuid.UUID("00000000-0000-0000-0000-0000000000c4")
ORIGAMI = uuid.UUID("00000000-0000-0000-0000-0000000000b9")


CONCEPTOS = [
    {
        "id": BLOCK,
        "codigo": "C003",
        "nombre": "block",
        "sinonimos": ["bloc", "block carta", "block oficio"],
        "discriminantes": ("tamano", "rayado"),
    },
    {
        "id": COLORES,
        "codigo": "C004",
        "nombre": "colores",
        "sinonimos": ["lapiz colores", "lapices de colores"],
        "discriminantes": (),
    },
    {
        "id": ORIGAMI,
        "codigo": "C090",
        "nombre": "origami",
        "sinonimos": ["papel origami"],
        "discriminantes": ("tamano",),
    },
]


def _producto(concepto, sku, nombre, nivel, atributos, personaje=None):
    return {
        "concepto_id": concepto,
        "sku": sku,
        "nombre": nombre,
        "nivel": nivel,
        "personaje": personaje,
        "atributos": atributos,
        "precio_cop": 1000,
    }


PRODUCTOS = [
    _producto(
        BLOCK,
        "TK-C003-ECO",
        "Block cuadriculado carta",
        "economico",
        {"tamano": "carta", "rayado": "cuadriculado"},
    ),
    _producto(BLOCK, "TK-C003-CON", "Block iris oficio", "confiable", {"tamano": "oficio"}),
    _producto(BLOCK, "TK-C003-PRE", "Block premium carta", "premium", {"tamano": "carta"}),
    _producto(BLOCK, "TK-C003-ECO-BLUEY", "Block carta Bluey", "economico", {"tamano": "carta"}, "bluey"),
    _producto(ORIGAMI, "TK-ORIGAMI", "Bloc origami 15 x 15", "economico", {"tamano": "15 x 15 cm"}),
    _producto(COLORES, "TK-C004-ECO", "Colores x12 economico", "economico", {}),
    _producto(COLORES, "TK-C004-CON", "Colores x12 confiable", "confiable", {}),
    _producto(COLORES, "TK-C004-PRE", "Colores x24 premium", "premium", {}),
]


class TestSeAbstieneEnVezDeInventar:
    def test_block_oficio_no_devuelve_el_de_carta_ni_el_origami(self):
        resultado = emparejar("block oficio", CONCEPTOS, PRODUCTOS)

        assert resultado.estado == "reconocido"
        assert resultado.concepto_codigo == "C003"
        assert resultado.atributos_impuestos["tamano"] == "oficio"
        assert [o.sku for o in resultado.opciones] == ["TK-C003-CON"]
        assert all("origami" not in o.nombre.lower() for o in resultado.opciones)

    def test_si_nadie_declara_el_atributo_no_hay_opcion(self):
        sin_oficio = [p for p in PRODUCTOS if p["atributos"].get("tamano") != "oficio"]

        resultado = emparejar("block oficio", CONCEPTOS, sin_oficio)

        assert resultado.estado == "abstencion"
        assert resultado.opciones == ()
        assert "oficio" in resultado.motivo

    def test_sin_atributo_impuesto_hay_una_opcion_por_nivel(self):
        resultado = emparejar("lapices de colores x 12", CONCEPTOS, PRODUCTOS)

        assert resultado.estado == "reconocido"
        assert resultado.concepto_codigo == "C004"
        assert [o.nivel for o in resultado.opciones] == ["economico", "confiable", "premium"]

    def test_un_concepto_ya_asignado_no_se_vuelve_a_adivinar(self):
        sin_pista = emparejar("material de trabajo opciones varias", CONCEPTOS, PRODUCTOS)
        asignado = emparejar(
            "material de trabajo opciones varias", CONCEPTOS, PRODUCTOS, concepto_forzado="C004"
        )

        assert sin_pista.estado == "sin_match"
        assert asignado.estado == "reconocido" and asignado.concepto_codigo == "C004"
        assert [o.nivel for o in asignado.opciones] == ["economico", "confiable", "premium"]

    def test_escolar_no_se_le_exige_a_un_producto(self):
        maleta = uuid.UUID("00000000-0000-0000-0000-0000000000a8")
        conceptos = [
            {"id": maleta, "codigo": "C086", "nombre": "maleta", "sinonimos": [], "discriminantes": ("tipo",)}
        ]
        productos = [_producto(maleta, "TK-C086-CON", "Morral azul", "confiable", {"tipo": "morral"})]

        escolar = emparejar("Maleta escolar", conceptos, productos)
        morral = emparejar("Maleta tipo morral", conceptos, productos)

        assert escolar.estado == "reconocido" and escolar.atributos_impuestos == {}
        assert [o.sku for o in escolar.opciones] == ["TK-C086-CON"]
        assert morral.atributos_impuestos == {"tipo": "morral"}

    def test_en_un_nivel_gana_el_de_marca_y_no_el_personaje(self):
        resultado = emparejar("block carta", CONCEPTOS, PRODUCTOS)

        economicos = [o for o in resultado.opciones if o.nivel == "economico"]
        assert len(economicos) == 1
        assert economicos[0].sku == "TK-C003-ECO"
        assert economicos[0].personaje is None


class TestLoQueNoSeReconoceOQueNoTieneProducto:
    def test_lo_que_no_reconocemos_no_trae_producto(self):
        resultado = emparejar("chaquiras surtidas", CONCEPTOS, PRODUCTOS)

        assert resultado.estado == "sin_match"
        assert resultado.opciones == ()

    def test_el_concepto_sin_producto_es_un_hueco(self):
        resultado = emparejar("block oficio", CONCEPTOS, [p for p in PRODUCTOS if p["concepto_id"] != BLOCK])

        assert isinstance(resultado, Emparejamiento)
        assert resultado.estado == "hueco_catalogo"


class TestLaFaltaDeOrtografiaSeAcercaAlCatalogo:

    def test_una_sola_palabra_cercana_se_corrige(self):
        from tukit_catalogo.transcripcion import corregir

        lexico = {"sharpie", "marcador", "toalla", "toallas", "carpeta", "carpetas"}

        assert corregir("SHSRPIE DE COLOR ROJO", lexico) == "SHARPIE DE COLOR ROJO"
        assert corregir("PAQUETES TAOLLA PARA MANOS", lexico | {"talla"}) == "PAQUETES TOALLA PARA MANOS"

    def test_nacho_no_se_vuelve_ancho_ni_el_plural_se_reescribe(self):
        from tukit_catalogo.transcripcion import corregir

        assert corregir("CARTILLA NACHO", {"ancho", "cartilla"}) == "CARTILLA NACHO"
        assert corregir("PAQUETES de toalla", {"paquete", "toalla"}) == "PAQUETES de toalla"

    def test_dos_candidatas_dejan_la_palabra_quieta(self):
        from tukit_catalogo.transcripcion import corregir

        assert corregir("plata", {"plato", "playa"}) == "plata"

    def test_lo_que_ya_esta_en_el_catalogo_no_se_toca(self):
        from tukit_catalogo.transcripcion import corregir

        assert corregir("block oficio", {"block", "oficio", "origami"}) == "block oficio"

    def test_el_vinilo_fluorescente_no_son_seis_colores(self):
        from tukit_catalogo.extraccion import extraer_atributos

        attrs = extraer_atributos("ESTUCHE DE VINILO X 6 UNIDADES ESCOLAR FLUORESCENTE", ("colores",))

        assert "colores" not in attrs

    def test_sharpie_y_toalla_como_los_imprimio_osito_encuentran_concepto(self):
        sharpie = uuid.UUID("00000000-0000-0000-0000-0000000000a1")
        toalla = uuid.UUID("00000000-0000-0000-0000-0000000000a2")
        conceptos = [
            {
                "id": sharpie,
                "codigo": "C006",
                "nombre": "marcador",
                "sinonimos": ["marcador sharpie", "sharpie"],
                "discriminantes": (),
            },
            {
                "id": toalla,
                "codigo": "C040",
                "nombre": "toallas y panitos",
                "sinonimos": ["toalla", "toalla mano"],
                "discriminantes": (),
            },
        ]
        productos = [
            _producto(sharpie, "TK-SHA", "Marcador Sharpie rojo", "economico", {}),
            _producto(toalla, "TK-TOA", "Paquete toalla para manos", "economico", {}),
        ]

        rojo = emparejar("SHSRPIE DE COLOR ROJO", conceptos, productos)
        manos = emparejar("PAQUETES TAOLLA PARA MANOS", conceptos, productos)

        assert rojo.texto_corregido == "SHARPIE DE COLOR ROJO"
        assert rojo.estado == "reconocido"
        assert rojo.concepto_codigo == "C006"
        assert manos.estado == "reconocido"
        assert manos.concepto_codigo == "C040"


class TestElAcudienteNoSaleALaRed:
    def test_este_modulo_no_consulta_fuera_del_catalogo(self):
        fuente = Path(inspect.getfile(emparejar)).read_text(encoding="utf-8")
        assert "import tiendas" not in fuente
        assert "tiendas.buscar" not in fuente
        assert "completar" not in fuente
        assert "urllib" not in fuente


class TestUnLibroConTituloSoloSeSurteConEseTitulo:

    LIBRO = uuid.UUID("00000000-0000-0000-0000-000000000134")
    CONCEPTO = {
        "id": LIBRO,
        "codigo": "C134",
        "nombre": "Libro o texto con titulo",
        "sinonimos": ["plan lector"],
        "discriminantes": ("isbn13",),
        "tipo_item": "libro_libre",
    }

    def _productos(self):
        return [
            _producto(self.LIBRO, "VAL", "Valeria en el Reino de Malagana", "confiable", {}),
            _producto(
                self.LIBRO,
                "GW-B1",
                "Gateway to the World b1 Student'S Book With Student'S app and Digital Student'S Book (en Inglés)",
                "confiable",
                {},
            ),
            _producto(
                self.LIBRO,
                "GW-A2",
                "Gateway to the World a2 Student'S Book With Student'S app and Digital Student'S Book (en Inglés)",
                "confiable",
                {},
            ),
        ]

    def _emparejar(self, texto):
        return emparejar(texto, [self.CONCEPTO], self._productos(), concepto_forzado="C134")

    def test_el_titulo_que_no_tenemos_es_un_hueco_y_no_otro_libro(self):
        for texto in (
            "Los secretos de Hafiz Mustafá - Francisco Leal Quevedo. Editorial Norma.",
            "Sherlock, Lupin y yo. Último acto en el teatro de la Ópera. Irene Adler. Editorial Planeta.",
            "Lectura Multidimensional Método 84H",
        ):
            r = self._emparejar(texto)
            assert r.opciones == (), texto
            assert r.estado == "hueco_catalogo", texto

    def test_el_titulo_que_si_tenemos_se_surte_con_ese_libro(self):
        r = self._emparejar("Valeria. En el reino de Malagana. Albeiro Echeverria. Editorial Panamericana.")
        assert [o.sku for o in r.opciones] == ["VAL"]

    def test_el_nivel_del_texto_escoge_la_edicion(self):
        r = self._emparejar("GATEWAY TO THE WORLD B1 STUDENT'S BOOK. Editorial Macmillan Education.")
        assert [o.sku for o in r.opciones] == ["GW-B1"]

    def test_la_ruta_rapida_aplica_la_misma_regla(self):
        from tukit_catalogo.routers.admin import _renglon_resuelto

        candidatos, _, _ = _renglon_resuelto(
            "Los secretos de Hafiz Mustafá - Francisco Leal Quevedo. Editorial Norma.",
            {},
            self._productos(),
            ("isbn13",),
            concepto="C134",
        )
        assert candidatos == []
        candidatos, _, _ = _renglon_resuelto(
            "Valeria. En el reino de Malagana.", {}, self._productos(), ("isbn13",), concepto="C134"
        )
        assert [c["sku"] for c in candidatos] == ["VAL"]
