"""Pruebas del enriquecedor: sacar empaque y atributos del nombre.

Todos los nombres de estas pruebas son reales, copiados del catalogo cargado.
No son ejemplos inventados para que el codigo pase: son las formas concretas
en que las tiendas colombianas escriben sus productos, con sus mayusculas
irregulares, sus abreviaturas y sus cifras pegadas.

Lo que se fija aqui es la distincion que rompio el carrito: separar el numero
que cuenta EMPAQUES del numero que mide CONTENIDO. `Tempera de 12 ml x 12
unidades` tiene dos doces y solo uno de ellos multiplica lo que el papa paga.
"""

from __future__ import annotations

import pytest
from tukit_catalogo.embeddings import MODELO_FALSO, embeder_falso
from tukit_catalogo.enriquecer import (
    atributos_ambiguos,
    atributos_combinados,
    atributos_de_ficha,
    embeddings_a_actualizar,
    extraer_atributos,
    extraer_empaque,
    extraer_personaje,
)


class TestPoblarEmbeddings:
    """El canal semantico se puebla una vez y no se recalcula sin necesidad
    (OE3). La fuente del vector es un puerto: aqui, el embeder falso, sin red."""

    PRODUCTOS = [
        {
            "id": "p1",
            "nombre": "Cuaderno cosido 100 hojas Norma",
            "concepto": "cuaderno",
            "atributos": {"rayado": "cuadriculado"},
            "texto_embedding": None,
            "embedding_model": None,
        },
        {
            "id": "p2",
            "nombre": "Block iris oficio",
            "concepto": "block",
            "atributos": {"tamano": "oficio"},
            "texto_embedding": None,
            "embedding_model": None,
        },
    ]

    def test_calcula_un_vector_por_producto_sin_repetir_llamadas(self):
        vistos: list[str] = []

        def espia(textos):
            vistos.extend(textos)
            return embeder_falso(textos)

        espia.modelo = MODELO_FALSO  # un espia refleja el contrato del puerto

        cambios = embeddings_a_actualizar(self.PRODUCTOS, espia)

        assert {c["pid"] for c in cambios} == {"p1", "p2"}
        assert all(len(c["embedding"]) == 1024 for c in cambios)
        assert all(c["embedding_model"] == MODELO_FALSO for c in cambios)
        # El texto guardado deja ver de que se calculo: nombre + concepto + attrs.
        p1 = next(c for c in cambios if c["pid"] == "p1")
        assert "cuaderno" in p1["texto_embedding"].lower()
        assert "cuadriculado" in p1["texto_embedding"].lower()
        # Una sola llamada por producto, no una por atributo.
        assert len(vistos) == 2

    def test_es_idempotente_no_recalcula_lo_que_no_cambio(self):
        # Primera pasada: se calcula todo.
        cambios = embeddings_a_actualizar(self.PRODUCTOS, embeder_falso)
        # La base ya tiene el vector y el texto con el que se calculo.
        ya_poblados = [
            {
                **p,
                "texto_embedding": next(c for c in cambios if c["pid"] == p["id"])["texto_embedding"],
                "embedding_model": MODELO_FALSO,
            }
            for p in self.PRODUCTOS
        ]

        def no_debe_llamarse(textos):
            raise AssertionError("no se debe recalcular un embedding que no cambio")

        no_debe_llamarse.modelo = MODELO_FALSO

        assert embeddings_a_actualizar(ya_poblados, no_debe_llamarse) == []

    def test_recalcula_cuando_el_texto_cambia(self):
        cambios = embeddings_a_actualizar(self.PRODUCTOS, embeder_falso)
        poblados = [
            {
                **p,
                "texto_embedding": next(c for c in cambios if c["pid"] == p["id"])["texto_embedding"],
                "embedding_model": MODELO_FALSO,
            }
            for p in self.PRODUCTOS
        ]
        # Al primero le cambia el nombre: su texto ya no coincide, se recalcula;
        # el segundo, intacto, no.
        poblados[0]["nombre"] = "Cuaderno argollado 80 hojas"
        rehechos = embeddings_a_actualizar(poblados, embeder_falso)
        assert [c["pid"] for c in rehechos] == ["p1"]


class TestEmpaqueContraContenido:
    """El corazon del asunto: cual de los numeros del nombre es el empaque."""

    @pytest.mark.parametrize(
        ("nombre", "esperado"),
        [
            ("Lápices Kiut x 10 unidades", 10),
            ("Marcador delgado neón x12 unidades", 12),
            ("Paquete Esponja x2 Unds Arte", 2),
            ("Paquete Cartulina Octavos x25 Unds Negra", 25),
            ("Paquete Sobre Manila Amarillo X100 Gigante 27x37cm", 100),
            ("Paquete Carton Cartulina Octavo x25 Unds", 25),
            ("Paquete Forro Acetato Cuaderno Cosido X10 Azul", 10),
            ("Crayones Kores Jumbo x 12 Uds", 12),
        ],
    )
    def test_cuenta_los_empaques_de_verdad(self, nombre, esperado):
        assert extraer_empaque(nombre).unidades == esperado

    @pytest.mark.parametrize(
        ("nombre", "porque"),
        [
            ("Tarro Vinilo Payasito x1000 Gramos Azul", "1000 gramos es contenido, no mil tarros"),
            ("Rollo Plastico Burbuja X50 Metros 25 Centimetros", "50 metros es largo, no 50 rollos"),
            ("Pegamento líquido Glukids x 250 g", "250 gramos es contenido"),
            ("Óleo N.° 37 de 37 ml verde", "el 37 es el numero de color y los ml son contenido"),
            ("Portaminas 2Mm FINLANDEK", "2 mm es el grosor de la mina"),
            ("Lienzo con bastidor con grapa posterior 20 x 30 cm", "20 x 30 es una medida"),
            ("Acetato para stencil 30,5 x 30,5 cm", "medida con coma decimal"),
            ("Pegante en Barra  Avengers 40 Grs", "40 gramos es contenido"),
        ],
    )
    def test_no_confunde_una_medida_con_un_empaque(self, nombre, porque):
        assert extraer_empaque(nombre).unidades == 1, porque

    def test_el_caso_de_los_dos_doces(self):
        """`Tempera gouache de colores de 12 ml x 12 unidades`.

        El primer 12 es cuanta pintura trae cada tarrito y el segundo es
        cuantos tarritos vienen. Si se toma el primero, el kit cobra doce
        veces de mas por algo que ya venia junto.
        """
        empaque = extraer_empaque("Témpera gouache de colores de 12 ml x 12 unidades")
        assert empaque.unidades == 12
        assert empaque.unidad_base == "unidad"

    def test_toma_el_conteo_y_no_la_longitud_cuando_vienen_los_dos(self):
        """`Cinta Cellux 18mm X5 Metros X10 Unds`: tres numeros, uno solo cuenta.

        18 mm es el ancho, 5 metros es lo que mide cada rollo y 10 es cuantos
        rollos trae el taco. Es el nombre mas hostil del catalogo y por eso
        esta aqui.
        """
        assert extraer_empaque("Taco De Cinta Aislante Cellux 18mm X5 Metros X10 Unds Negra").unidades == 10


class TestHojasSegunElConcepto:
    """`N hojas` es empaque o atributo segun QUE cosa sea, no segun como se escriba.

    Cien hojas de un cuaderno son una propiedad de ese cuaderno: sigue siendo
    un cuaderno. Cinco hojas de acetato son cinco hojas: el paquete trae cinco.
    La misma palabra y dos significados opuestos para el carrito.

    Lo que decide no es una lista de excepciones a mano sino el concepto: si
    declara `hojas` entre sus `atributos_discriminantes`, entonces las hojas
    describen la cosa; si no, la cuentan.
    """

    def test_las_hojas_de_un_cuaderno_no_son_cien_cuadernos(self):
        empaque = extraer_empaque(
            "Cuaderno cosido doble línea de 100 hojas (surtido)",
            atributos_del_concepto=("hojas", "rayado", "materias"),
        )
        assert empaque.unidades == 1
        assert empaque.unidad_base == "unidad"

    def test_las_hojas_de_un_acetato_si_son_el_paquete(self):
        empaque = extraer_empaque(
            "Acetato calibre 10 por 5 hojas", atributos_del_concepto=("calibre", "tamano")
        )
        assert empaque.unidades == 5
        assert empaque.unidad_base == "hoja"

    def test_el_cuaderno_argollado_tampoco_son_cien(self):
        empaque = extraer_empaque(
            "Cuaderno De Arte Bond Tapa Dura Surtido Media Carta X 40 Hj",
            atributos_del_concepto=("hojas", "rayado", "materias"),
        )
        assert empaque.unidades == 1

    def test_sin_saber_el_concepto_las_hojas_cuentan(self):
        """Por omision se cuenta, porque es el caso mas comun fuera del cuaderno."""
        assert extraer_empaque("Block cuadriculado por 50 hojas").unidades == 50


class TestColoresComoConteo:
    def test_una_caja_de_doce_colores_trae_doce(self):
        assert extraer_empaque("Colores Faber Castell x 12 colores").unidades == 12

    def test_lentejuelas_de_nueve_colores(self):
        assert extraer_empaque("Paquete Lentejuelas x9 Colores (Metro por Color) Surtido").unidades == 9


class TestAtributos:
    """Los atributos son lo que el resolutor compara contra lo que pidio el colegio.

    Solo se extrae lo que se puede leer sin adivinar. Un atributo inventado es
    peor que uno ausente: si el catalogo dice `tamano: oficio` sobre algo que
    es carta, el resolutor lo elige con confianza y el papa recibe el tamano
    equivocado. Ausente al menos manda el renglon a revision.
    """

    def test_lee_el_tamano_escolar(self):
        assert (
            extraer_atributos("Paquete Cartulina Octavos x25 Unds Negra", ("tamano",))["tamano"] == "octavo"
        )
        assert (
            extraer_atributos("Cartulina Espejo Medio Pliego Verde", ("tamano",))["tamano"] == "medio pliego"
        )
        assert extraer_atributos("Cuaderno Bond Media Carta X 40 Hj", ("tamano",))["tamano"] == "media carta"
        assert extraer_atributos("Sobre de Manila tamaño oficio", ("tamano",))["tamano"] == "oficio"

    def test_no_confunde_carta_con_media_carta(self):
        """`media carta` contiene `carta`: si se busca la corta primero, todo
        lo de media carta queda marcado como carta y es el doble de grande."""
        assert extraer_atributos("Cuaderno Media Carta", ("tamano",))["tamano"] == "media carta"
        assert extraer_atributos("Cuaderno tamaño carta", ("tamano",))["tamano"] == "carta"

    def test_lee_el_color(self):
        assert extraer_atributos("Cartulina Espejo Medio Pliego Verde", ("color",))["color"] == "verde"
        assert extraer_atributos("Tarro Vinilo Payasito x1000 Gramos Azul", ("color",))["color"] == "azul"

    def test_surtido_es_un_color_valido_y_significa_algo(self):
        """`surtido` no es ausencia de color: es la promesa de que el colegio
        acepta cualquiera, y el optimizador puede usarlo para abaratar."""
        assert extraer_atributos("Cuaderno cosido doble línea (surtido)", ("color",))["color"] == "surtido"

    def test_lee_las_hojas_cuando_el_concepto_las_pide(self):
        assert extraer_atributos("Cuaderno cosido de 100 hojas", ("hojas",))["hojas"] == 100
        assert extraer_atributos("Cuaderno Bond Media Carta X 40 Hj", ("hojas",))["hojas"] == 40

    def test_lee_capacidad_y_gramaje(self):
        assert extraer_atributos("Pegamento líquido Glukids x 250 g", ("gramaje",))["gramaje"] == "250 g"
        assert (
            extraer_atributos("Témpera gouache de 12 ml x 12 unidades", ("capacidad",))["capacidad"]
            == "12 ml"
        )

    def test_solo_devuelve_lo_que_el_concepto_pide(self):
        """No se llena el JSON con todo lo que se pueda leer. Los atributos son
        un contrato con el resolutor: lo que sobra es ruido que pesa en cada
        comparacion."""
        attrs = extraer_atributos("Cartulina Espejo Medio Pliego Verde", ("tamano",))
        assert set(attrs) == {"tamano"}

    def test_lee_la_presentacion_que_el_colegio_si_distingue(self):
        """Pegante en barra y pegante liquido pegan igual y no son lo mismo:
        la lista suele pedir uno de los dos a proposito."""
        assert (
            extraer_atributos("Pegamento líquido Glukids x 250 g", ("presentacion",))["presentacion"]
            == "liquido"
        )
        assert (
            extraer_atributos("Barra Silicona Transparente Delgada X 10 Unidades", ("presentacion",))[
                "presentacion"
            ]
            == "barra"
        )
        assert (
            extraer_atributos("Témpera dactilar Little Creatives de 30 g", ("presentacion",))["presentacion"]
            == "dactilar"
        )

    def test_lee_el_material(self):
        assert extraer_atributos("Caja Guantes de Nitrilo x100 Unds", ("material",))["material"] == "nitrilo"
        assert extraer_atributos("Abaco Plastico Vertical 10 Filas", ("material",))["material"] == "plastico"

    def test_lee_el_tipo_cuando_el_termino_es_inequivoco(self):
        assert (
            extraer_atributos("Cinta Adhesiva Transparente X 255 Metros", ("tipo",))["tipo"] == "transparente"
        )
        assert extraer_atributos("Bloc origami x 50 unidades (15 x 15 cm)", ("tipo",))["tipo"] == "origami"
        assert extraer_atributos("Crayón Eterna X 12 Jumbo Largo Redondo", ("tipo",))["tipo"] == "jumbo"
        assert extraer_atributos("Paquete De Hojas Examen X100 Unds Cuadros", ("tipo",))["tipo"] == "examen"

    def test_prefiere_el_tipo_mas_especifico(self):
        """`punta pincel` contiene `punta`: gana el termino largo. Es una punta,
        no un tipo: el tipo de un marcador es su tinta."""
        assert extraer_atributos("Plumones Punta Pincel Marcadores Faber Castell X10", ("tipo", "punta")) == {
            "punta": "punta pincel"
        }

    def test_calla_cuando_no_puede_leer(self):
        """Si el nombre no dice el tamano, la clave no aparece. No se rellena
        con `desconocido` ni con el valor mas comun."""
        assert extraer_atributos("Portaminas FINLANDEK", ("tamano", "color")) == {}

    def test_el_color_en_femenino_tambien_es_un_color(self):
        """`Cartulina Negra` y `Marcador Negro` son el mismo color. Buscar solo
        el masculino dejaba sin color a medio catalogo."""
        assert extraer_atributos("Paquete Cartulina Octavos x25 Unds Negra", ("color",))["color"] == "negro"
        assert extraer_atributos("Tempera Roja", ("color",))["color"] == "rojo"
        assert extraer_atributos("Cinta Blanca", ("color",))["color"] == "blanco"

    def test_el_tamano_en_centimetros_cuando_no_hay_tamano_escolar(self):
        attrs = extraer_atributos("Bloc origami x 50 unidades (15 x 15 cm)", ("tamano",))
        assert attrs["tamano"] == "15 x 15 cm"

    def test_el_tamano_escolar_gana_sobre_los_centimetros(self):
        attrs = extraer_atributos("Cartulina Octavo 25 x 35 cm", ("tamano",))
        assert attrs["tamano"] == "octavo"

    def test_cuenta_los_colores_de_un_surtido(self):
        """`Marcador neon x12 unidades`: doce marcadores surtidos son doce
        colores. Sin la palabra que promete surtido no se infiere nada."""
        assert extraer_atributos("Marcador delgado neón x12 unidades", ("colores",))["colores"] == 12
        assert extraer_atributos("Colores Faber x 12 colores", ("colores",))["colores"] == 12

    def test_no_inventa_colores_cuando_el_empaque_puede_ser_de_uno_solo(self):
        assert extraer_atributos("Marcador permanente negro x12 unidades", ("colores",)) == {}

    def test_lee_multimaterias(self):
        attrs = extraer_atributos("Cuaderno Argollado Multimaterias Spiderman", ("materias",))
        assert attrs["materias"] == "multiple"
        assert extraer_atributos("Cuaderno argollado 5 materias", ("materias",))["materias"] == 5


class TestEmpaqueEscritoDeOtroModo:
    def test_la_x_pegada_a_un_punto_sigue_siendo_empaque(self):
        """`Resaltadores..neon.x5 KIUT` es como lo escribio la tienda. Exigir
        un espacio antes de la x contaba ese paquete de cinco como uno."""
        assert extraer_empaque("Resaltadores..neon.x5 KIUT").unidades == 5

    def test_paquete_de_doce_sin_la_x(self):
        assert extraer_empaque("Lápices De Colores Lego Con Topper, Paquete De 12").unidades == 12
        assert extraer_empaque("Caja de 24 crayones").unidades == 24

    def test_una_caja_que_no_dice_cuantos_sigue_siendo_una(self):
        assert extraer_empaque("Caja matemática: 1 compas, reglas, 1 tajalápiz (surtido)").unidades == 1


class TestPersonaje:
    """El personaje va en su propia columna, no entre los atributos.

    Es ortogonal al nivel: un cuaderno de Spiderman no es un cuaderno mejor,
    es el mismo con otra portada. Tenerlo aparte deja medir cuanto cuesta ese
    gusto, que es justo lo que el kit necesita para decidir si lo recomienda.
    """

    def test_reconoce_los_personajes_del_catalogo(self):
        assert extraer_personaje("Regla  Barbie Love") == "Barbie"
        assert extraer_personaje("Vaso de 530 ml plástico con pitillo Spiderman") == "Spiderman"
        assert extraer_personaje("Cuaderno Paw Patrol Rayado 50 hojas") == "Paw Patrol"
        assert extraer_personaje("Estuche para lápices Lego Mandaloriano") == "Star Wars"

    def test_un_producto_liso_no_tiene_personaje(self):
        assert extraer_personaje("Cuaderno cosido doble línea de 100 hojas") is None
        assert extraer_personaje("Resma de papel natural carta de 72 g x 500 hojas") is None

    def test_no_lo_dispara_una_palabra_contenida_en_otra(self):
        """`cars` esta dentro de `descarsable` y `lego` dentro de `legosa`:
        sin frontera de palabra medio catalogo quedaria licenciado."""
        assert extraer_personaje("Carpeta plástica legajadora") is None


class TestAtributosDeLaFicha:
    """Lo que la tienda publica en su ficha tecnica, traducido al catalogo.

    La ficha trae mucho mas de lo que sirve. `Factor Neto PUM`, `Dividendo
    PUM`, `IVA` y `Prime` son contabilidad de la tienda, no descripciones del
    producto, y meterlos al catalogo solo le da ruido al resolutor.
    """

    def test_traduce_los_campos_utiles(self):
        attrs = atributos_de_ficha(
            {"Número de hojas": "50", "Tipo de linea": "Rayado", "Formato": "Cosido"},
            ("hojas", "rayado", "tipo"),
        )
        assert attrs == {"hojas": 50, "rayado": "rayado", "tipo": "cosido"}

    def test_ignora_la_contabilidad_de_la_tienda(self):
        attrs = atributos_de_ficha(
            {"Factor Neto PUM": "1,0", "IVA": "19", "Prime": "Si", "Número de hojas": "80"},
            ("hojas", "tipo", "material"),
        )
        assert attrs == {"hojas": 80}

    def test_solo_devuelve_lo_que_el_concepto_pide(self):
        attrs = atributos_de_ficha({"Número de hojas": "50", "Peso": "112 gr."}, ("hojas",))
        assert set(attrs) == {"hojas"}

    def test_limpia_la_composicion_textil(self):
        """La tienda escribe la ficha de composicion entera. Guardarla tal
        cual hace que el resolutor compare `algodon` contra `Exterior:
        Poliester=100%, Forro: Nylon=100%` y no encuentre nada."""
        attrs = atributos_de_ficha({"Material": "Exterior: Poliester=100%"}, ("material",))
        assert attrs["material"] == "poliester"
        limpio = atributos_de_ficha({"Material": "Plástico resistente"}, ("material",))
        assert limpio["material"] == "plastico"

    def test_descarta_las_casillas_que_la_tienda_lleno_por_llenar(self):
        """`N/A` y `Normal` no dicen nada del producto, pero parecen dato: si
        entran al catalogo, el resolutor filtra por ellos."""
        assert atributos_de_ficha({"Tipo": "N/A"}, ("tipo",)) == {}
        assert atributos_de_ficha({"Tipo": "Normal"}, ("tipo",)) == {}
        assert atributos_de_ficha({"Material": "-"}, ("material",)) == {}

    def test_un_cero_declarado_no_es_una_pieza(self):
        assert atributos_de_ficha({"Número de Piezas": "0"}, ("piezas",)) == {}
        assert atributos_de_ficha({"Número de Piezas": "6"}, ("piezas",))["piezas"] == 6

    def test_lee_el_color_de_la_ficha(self):
        assert atributos_de_ficha({"Color": "Azul Rey"}, ("color",))["color"] == "azul"


class TestLosConceptosQueNadieLograbaCumplir:
    """Doce conceptos tenian productos y NINGUNO cumplia su atributo exigido.

    No era que faltaran productos: era que el nombre decia el dato y nadie lo
    leia. Estas pruebas cubren los que si se podian leer. El que no, queda
    documentado como exigencia imposible, que es un defecto del concepto y no
    del catalogo.
    """

    def test_la_agenda_escolar_cubre_dos_anos(self):
        assert extraer_atributos("Agenda Chica Kawai 2026 2027", ("ano",))["ano"] == "2026-2027"
        assert extraer_atributos("Agenda ejecutiva permanente con solapa", ("ano",))["ano"] == "permanente"

    def test_el_tipo_de_calculadora_decide_si_sirve_para_la_clase(self):
        assert (
            extraer_atributos("Calculadora Científica Casio Fx 82La Plus", ("tipo",))["tipo"] == "cientifica"
        )
        assert extraer_atributos("Calculadora básica 12 dígitos Eterna", ("tipo",))["tipo"] == "basica"

    def test_el_balon_de_salon_no_es_el_de_futbol(self):
        cancha = extraer_atributos("Balon Futbol De Salón #4 Tiki Taka", ("tipo",))
        assert cancha["tipo"] == "futbol de salon"
        assert extraer_atributos("Balón De Fútbol Nro 4 Game", ("tipo",))["tipo"] == "futbol"

    def test_la_flauta_dulce_soprano_es_dulce(self):
        """Dulce es el instrumento y soprano la voz. Como `soprano` la lista que
        pide "flauta dulce" (la escolar de siempre) no encontraba ninguna."""
        assert extraer_atributos("Flauta Dulce Hohner Soprano 9508", ("tipo",))["tipo"] == "dulce"
        assert extraer_atributos("Flauta soprano germana", ("tipo",))["tipo"] == "soprano"

    def test_un_rango_de_durezas_no_exige_ninguna(self):
        assert extraer_atributos("Lápiz 2H-6B", ("dureza",)).get("dureza") is None
        assert extraer_atributos("Lápiz negro 2B", ("dureza",))["dureza"] == "2b"
        assert extraer_atributos("Lápiz 8B", ("dureza",))["dureza"] == "8b"

    def test_para_un_morral_grande_si_es_un_tamano(self):
        assert extraer_atributos("Morral Escolar Frozen Grande", ("tamano",))["tamano"] == "grande"
        assert extraer_atributos("Morral Escolar Bluey Mediano Azul", ("tamano",))["tamano"] == "mediano"

    def test_el_tamano_de_papel_le_gana_al_relativo(self):
        """`Agenda Design Argollada Grande` es grande, pero un `Cuaderno
        Grande Media Carta` es de media carta: el tamano escolar es el que
        el colegio escribio y el relativo es como lo llama la tienda."""
        assert extraer_atributos("Cuaderno Grande Media Carta", ("tamano",))["tamano"] == "media carta"

    def test_escolar_solo_gana_cuando_no_hay_nada_mejor(self):
        """`escolar` aparece en medio catalogo y como tipo dice poquisimo."""
        assert extraer_atributos("Flauta Fina Escolar", ("tipo",))["tipo"] == "escolar"
        assert extraer_atributos("Compas escolar keyroad (surtido)", ("tipo",))["tipo"] == "escolar"
        assert extraer_atributos("Compas Precision Faber Castell", ("tipo",))["tipo"] == "precision"

    def test_la_presentacion_del_aserrin(self):
        attrs = extraer_atributos("Aserrin Escolar De Colores Bolsa X 12 Unidades", ("presentacion",))
        assert attrs["presentacion"] == "bolsa"


class TestLoQueLasListasSiPidenYNoSabiamosLeer:
    """Los 84 atributos "que ninguna lista pide" casi todos si se piden.

    Al medir contra las 4.719 lineas del corpus, 84 pares concepto-atributo
    salian con cero demanda, y la lectura facil era quitarlos del contrato.
    Mirando las lineas de verdad, la mayoria se piden y con insistencia: lo
    que faltaba era vocabulario para leerlas. Un cero puede querer decir "no
    lo piden" o "no lo sabemos leer", y solo el primero justifica relajar el
    requisito.

    Cada cadena de aqui esta copiada del corpus, no inventada.
    """

    def test_el_idioma_del_diccionario(self):
        assert extraer_atributos("diccionario en español", ("idioma",)) == {"idioma": "espanol"}
        assert extraer_atributos("diccionario de inglés", ("idioma",)) == {"idioma": "ingles"}

    def test_un_diccionario_de_dos_idiomas_no_es_de_uno(self):
        # `diccionario de inglés y francés` aparece en el corpus, y darlo por
        # ingles a secas haria que un diccionario bilingue pasara por uno
        # monolingue, que es otro libro y otro precio. Los idiomas van en orden
        # alfabetico, para que el orden en que se escribieron no los separe.
        assert extraer_atributos("diccionario de inglés y francés", ("idioma",)) == {
            "idioma": "frances-ingles"
        }

    def test_el_deposito_del_tajalapiz(self):
        # `Tajalapiz con deposito` es la linea mas repetida de ese concepto.
        assert extraer_atributos("Tajalapiz con deposito", ("deposito",)) == {"deposito": True}
        assert extraer_atributos("Tajalapiz sin deposito", ("deposito",)) == {"deposito": False}

    def test_un_tajalapiz_que_no_dice_nada_no_afirma_que_no_tenga(self):
        assert extraer_atributos("Tajalapiz grueso", ("deposito",)) == {}

    @pytest.mark.parametrize(
        ("texto", "cuantos"),
        [("Tajalapiz doble", 2), ("Tajalapiz de dos orificios", 2), ("Tajalapiz sencillo", 1)],
    )
    def test_los_orificios_del_tajalapiz(self, texto, cuantos):
        assert extraer_atributos(texto, ("orificios",)) == {"orificios": cuantos}

    @pytest.mark.parametrize(
        ("texto", "esperado"),
        [
            ("Pincel Grueso", "grueso"),
            ("Pincel Delgado", "delgado"),
            ("Pincel mediano", "mediano"),
            # Sin palabra, el numero de la serie es lo que gradua el pincel.
            ("Pincel redondo N° 8", "n8"),
            ("Pincel #11", "n11"),
        ],
    )
    def test_el_grosor_del_pincel(self, texto, esperado):
        assert extraer_atributos(texto, ("grosor",)) == {"grosor": esperado}

    def test_cuando_el_pincel_dice_las_dos_cosas_manda_la_palabra(self):
        # `Pincel #11 pequeño` trae numero y palabra. La palabra se compara
        # entre marcas; la serie numerica no significa lo mismo en todas.
        assert extraer_atributos("Pincel #11 pequeño", ("grosor",)) == {"grosor": "pequeno"}

    def test_la_forma_del_pincel(self):
        assert extraer_atributos("Pincel Delgado Plano", ("forma",)) == {"forma": "plano"}
        assert extraer_atributos("Pincel redondo N° 4", ("forma",)) == {"forma": "redondo"}

    @pytest.mark.parametrize("texto,dureza", [("Lapiz negro 2B", "2b"), ("Lapiz HB", "hb")])
    def test_la_dureza_del_lapiz(self, texto, dureza):
        assert extraer_atributos(texto, ("dureza",)) == {"dureza": dureza}

    def test_el_numero_de_un_lapiz_no_es_su_dureza(self):
        # `Lapiz n 2` es la escala comercial, no la escala de grafito. Darla
        # por `2b` seria afirmar una mina blanda que nadie pidio.
        assert extraer_atributos("Lapiz n 2 negro", ("dureza",)) == {}

    def test_el_color_de_un_esfero_es_su_tinta(self):
        # `Lapicero Negro` no habla del plastico del tubo.
        assert extraer_atributos("Lapicero Negro", ("tinta",)) == {"tinta": "negro"}
        assert extraer_atributos("esferos rojos y negros", ("tinta",)) == {"tinta": "surtido"}

    @pytest.mark.parametrize(
        ("texto", "cuantos"),
        [
            ("Cartuchera doble servicio", 2),
            ("Cartuchera Premium 2 Bolsillos Cars Mc Queen", 2),
            ("Cartuchera Súper 2 Bolsillos Minnie Hi!", 2),
            ("Cartuchera sencilla", 1),
        ],
    )
    def test_los_compartimentos_de_la_cartuchera(self, texto, cuantos):
        assert extraer_atributos(texto, ("compartimentos",)) == {"compartimentos": cuantos}

    def test_una_cartuchera_mediana_no_declara_compartimentos(self):
        assert extraer_atributos("Cartuchera mediana", ("compartimentos",)) == {}


class TestElRayadoYLaFormaQueSeNosEscapaban:
    """Dos atributos de mucha demanda que el nombre si trae.

    `rayado` es lo que un colegio escribe de un cuaderno casi siempre, y
    C001 es el concepto mas pedido del corpus con 416 renglones. No habia
    rama que lo leyera, asi que el atributo mas discriminante del producto
    mas pedido salia vacio.

    `forma` es una regresion que me hice al darle a `forma` su propio
    vocabulario: `triangular` vivia en TIPOS y se quedo fuera, con lo que
    `Lapiz triangular` dejo de leerse. El corpus lo pide 17 veces.
    """

    @pytest.mark.parametrize(
        ("texto", "esperado"),
        [
            ("Cuaderno cuadriculado 100 hojas", "cuadriculado"),
            ("Cuaderno ferrocarril", "ferrocarril"),
            ("Cuaderno doble linea", "doble linea"),
            ("Cuaderno rayado", "rayado"),
            ("Cuaderno cuadricula grande", "cuadricula grande"),
            ("Cuaderno milimetrado", "milimetrado"),
            ("Cuaderno de hojas blancas", "blanco"),
            ("Cuaderno cuadriculado 1 cm", "cuadriculado 1 cm"),
        ],
    )
    def test_el_rayado_del_cuaderno(self, texto, esperado):
        assert extraer_atributos(texto, ("rayado",)) == {"rayado": esperado}

    def test_un_cuaderno_que_no_dice_su_rayado_no_lo_inventa(self):
        assert extraer_atributos("Cuaderno cosido 100 hojas", ("rayado",)) == {}

    @pytest.mark.parametrize(
        ("texto", "esperado"),
        [
            ("Lapiz triangular grueso", "triangular"),
            ("Lapiz hexagonal", "hexagonal"),
            ("Pincel redondo N° 4", "redondo"),
            ("Pincel Delgado Plano", "plano"),
        ],
    )
    def test_la_forma_sigue_leyendo_lo_de_antes_y_lo_nuevo(self, texto, esperado):
        assert extraer_atributos(texto, ("forma",)) == {"forma": esperado}


class TestCamposDeFichaQueLaTiendaSiPublica:
    """Traducciones que faltaban, medidas sobre las 147 fichas en cache.

    `Tamaño` aparece en 14 fichas y no estaba traducido, siendo `tamano` el
    atributo que mas falta en el catalogo. `Idioma` esta en 4 y es lo que
    distingue un diccionario de otro. Se anaden los que la tienda publica de
    verdad y no los que uno supondria: `Talla` no aparece en ninguna ficha,
    asi que mapearlo habria sido codigo muerto con pinta de cobertura.
    """

    def test_el_tamano_de_la_ficha(self):
        assert atributos_de_ficha({"Tamaño": "Grande"}, ("tamano",)) == {"tamano": "grande"}

    def test_el_idioma_de_la_ficha(self):
        assert atributos_de_ficha({"Idioma": "Español"}, ("idioma",)) == {"idioma": "espanol"}

    def test_las_dimensiones_de_la_ficha(self):
        assert atributos_de_ficha({"Dimensiones": "23.7 cm x 18.5 cm x 0.4 cm"}, ("dimensiones",)) == {
            "dimensiones": "23.7 cm x 18.5 cm x 0.4 cm"
        }

    def test_la_punta_y_la_presentacion(self):
        assert atributos_de_ficha({"Tipo de punta": "Una Punta"}, ("punta",)) == {"punta": "una punta"}
        assert atributos_de_ficha({"Presentación": "Paq. x 10 uds."}, ("presentacion",)) == {
            "presentacion": "paq. x 10 uds."
        }

    def test_sigue_devolviendo_solo_lo_pedido(self):
        # La ficha trae cincuenta y un campos, y casi todos son contabilidad
        # interna de la tienda: `Factor Neto PUM`, `IVA`, `Prime`.
        assert atributos_de_ficha({"Tamaño": "Grande", "IVA": "19", "Prime": "Si"}, ("tamano",)) == {
            "tamano": "grande"
        }


class TestCuandoElSilencioSignificaAlgo:
    """`materias` es el unico atributo con valor por omision, y por convencion.

    En la papeleria colombiana un cuaderno que no dice nada es de UNA materia:
    lo multiple siempre viene marcado ("multimaterias", "argollado 7
    materias"). Callarlo no es que no se sepa, es que es uno, igual que
    `unidades_por_empaque`.

    Importa porque C001 es el concepto mas pedido del corpus, con 410
    renglones, y sin esto 16 de sus 17 productos quedaban incompletos por un
    atributo que en realidad sabiamos.

    Lo que NO se hace es extender la idea a los demas. Un tajalapiz que no
    menciona deposito puede tenerlo perfectamente, y afirmar que no lo tiene
    seria inventarse una ausencia.
    """

    def test_un_cuaderno_que_no_dice_nada_es_de_una_materia(self):
        assert extraer_atributos("Cuaderno Stitch 100 Hojas", ("materias",)) == {"materias": 1}

    def test_lo_multiple_viene_marcado_y_se_respeta(self):
        assert extraer_atributos("Cuaderno Argollado Multimaterias Spiderman", ("materias",)) == {
            "materias": "multiple"
        }
        assert extraer_atributos("Cuaderno argollado 7 materias", ("materias",)) == {"materias": 7}

    def test_el_silencio_no_se_interpreta_en_los_demas_atributos(self):
        # Un tajalapiz sin mencion de deposito puede tenerlo.
        assert extraer_atributos("Tajalapiz grueso", ("deposito",)) == {}
        # Una cartuchera que no cuenta bolsillos no tiene uno.
        assert extraer_atributos("Cartuchera mediana", ("compartimentos",)) == {}
        # Un cuaderno que no dice su rayado no es de hojas blancas.
        assert extraer_atributos("Cuaderno cosido 100 hojas", ("rayado",)) == {}


class TestLoQueSeptimoPediaYElNombreNoDecia:
    """Atributos que la auditoria de Septimo (Agustiniano Salitre) encontro
    sin leer, con renglones de esa lista y nombres reales del catalogo.

    El kit recomendaba un oleo para `Pinturas acrilicas tubo de 45 cc:
    blanco`, un cuaderno rayado para uno cuadriculado y argollado para uno
    cosido. Ninguno era un error del filtro: el catalogo no declaraba lo que
    habia que comparar, o el renglon lo escribia en plural y no se leia.
    """

    def test_rayas_es_rayado(self):
        nombre = "Cuaderno Argollado 105 Scribe Master Pasta Dura Hombre 80 Hojas Rayas Pasta Dura Grande"
        assert extraer_atributos(nombre, ("rayado",)) == {"rayado": "rayado"}

    @pytest.mark.parametrize(
        ("texto", "esperado"),
        [
            ("Cuaderno Cosido 100 Hojas Norma X-Presarte Cuadros Hombre", "cosido"),
            ("Cuaderno Argollado 105 Norma Xpresarte Cuadros 80 Hojas", "argollado"),
            ("cuaderno cuadriculado Cosido 50 hojas", "cosido"),
            ("cuadernos cosidos de 100 hojas", "cosido"),
            ("cuaderno cuadriculado cocido", "cosido"),
            ("cuaderno doble linea grande sin espiral", "cosido"),
            ("cuaderno argollado cuadriculado grande 100 hojas", "argollado"),
        ],
    )
    def test_la_encuadernacion_del_cuaderno(self, texto, esperado):
        assert extraer_atributos(texto, ("encuadernacion",)) == {"encuadernacion": esperado}

    def test_un_cuaderno_que_no_dice_su_encuadernacion_no_la_inventa(self):
        assert extraer_atributos("Cuaderno Stitch 100 Hojas", ("encuadernacion",)) == {}

    @pytest.mark.parametrize(
        ("texto", "esperado"),
        [
            ("Óleo franco magenta 50 ml", {"tipo": "oleo", "color": "magenta"}),
            ("Pintura al óleo de 75 ml, verde permanente", {"tipo": "oleo", "color": "verde"}),
            ("Pinturas acrílicas tubo de 45 cc: cian", {"tipo": "acrilico", "color": "cian"}),
            ("Pinturas acrílicas tubo de 45 cc: amarillo 900", {"tipo": "acrilico", "color": "amarillo"}),
            ("Pinturas acrílicas tubo de 45 cc: blanco", {"tipo": "acrilico", "color": "blanco"}),
        ],
    )
    def test_el_tipo_y_el_color_de_la_pintura(self, texto, esperado):
        assert extraer_atributos(texto, ("tipo", "color")) == esperado

    def test_marcadores_acrilicos_en_plural(self):
        assert extraer_atributos("estuche de marcadores acrílicos", ("tipo",)) == {"tipo": "acrilico"}

    @pytest.mark.parametrize(
        ("texto", "esperado"),
        [
            ("Micropunta negro", {"punta": "micropunta", "color": "negro"}),
            ("Marcador Sharpie Punta Fina Negro", {"punta": "punta fina", "color": "negro"}),
            ("Plumones Punta Pincel Marcadores Faber Castell X10", {"punta": "punta pincel"}),
            ("MARCADOR PERMANENTE NEGRO FABER CASTELL", {"tipo": "permanente", "color": "negro"}),
        ],
    )
    def test_la_tinta_y_la_punta_del_marcador_son_cosas_distintas(self, texto, esperado):
        # Antes `punta` leia la tabla de tipos: un marcador permanente quedaba
        # con `punta=permanente`, y uno de punta fina con `tipo=punta fina`.
        assert extraer_atributos(texto, ("tipo", "punta", "color")) == esperado

    def test_un_marcador_delgado_es_de_punta_fina(self):
        assert extraer_atributos("Plumones delgados Keyroad x 12 unidades", ("punta",)) == {
            "punta": "punta fina"
        }

    def test_la_punta_roma_de_las_tijeras_se_sigue_leyendo(self):
        assert extraer_atributos("Tijera punta roma  NESSAN", ("punta",)) == {"punta": "punta roma"}

    @pytest.mark.parametrize(
        ("texto", "esperado"),
        [
            ("octavos de cartón paja de colores", "surtido"),
            ("Paquete Carton Paja Octavos x10 Unds Colores", "surtido"),
            ("Cartón paja color crema por 10 uds.", "crema"),
        ],
    )
    def test_de_colores_es_surtido(self, texto, esperado):
        assert extraer_atributos(texto, ("color",)) == {"color": esperado}

    @pytest.mark.parametrize(
        ("texto", "esperado"),
        [
            ("Biblia católica", "completa"),
            ("La Biblia Latinoamericana Letra Grande", "completa"),
            ("Libro Lecturas De La Biblia Para Nios Y Nias", "infantil"),
            ("Biblia para niños", "infantil"),
        ],
    )
    def test_una_seleccion_infantil_no_es_la_biblia(self, texto, esperado):
        assert extraer_atributos(texto, ("edicion",)) == {"edicion": esperado}

    @pytest.mark.parametrize(
        ("texto", "esperado"),
        [
            ("Diccionario Inglés – Inglés", {"monolingue": True}),
            ("Nacho: diccionario escolar ingles - espanol", {"monolingue": False}),
            ("Diccionario School Larousse espanol-ingles/english-spanish", {"monolingue": False}),
            # "Diccionario de ingles" a secas no dice cual: en Colombia casi
            # siempre es el bilingue, y exigir uno u otro dejaria sin opcion
            # a la mayoria de las listas.
            ("Diccionario de inglés", {}),
            ("Diccionario Oxford Pocket para estudiantes latinoamericanos", {}),
        ],
    )
    def test_un_diccionario_ingles_ingles_es_monolingue(self, texto, esperado):
        assert extraer_atributos(texto, ("monolingue",)) == esperado

    @pytest.mark.parametrize(
        "texto",
        [
            "Transportador 360 Grados FABER CASTELL",
            "Transportador de 360° Eterna",
            "transportador 360 grados",
        ],
    )
    def test_los_grados_del_transportador(self, texto):
        assert extraer_atributos(texto, ("grados",)) == {"grados": 360}

    def test_la_regla_de_acero(self):
        assert extraer_atributos("regla de acero inoxidable de 30 cm", ("material",)) == {"material": "acero"}

    @pytest.mark.parametrize(
        ("texto", "esperado"),
        [
            ("Palos de paleta", "paleta"),
            ("Palos De Madera Para Paleta Color Natural X 500 Unidades", "paleta"),
            ("Palo De Balso Cuadrado 5 X 5 Mm X 90 Cm 10 Unidades", "balso"),
        ],
    )
    def test_el_tipo_de_palito(self, texto, esperado):
        assert extraer_atributos(texto, ("tipo",)) == {"tipo": esperado}

    @pytest.mark.parametrize(
        ("texto", "esperado"),
        [
            ("Toalla pequeña", "tela"),
            ("Pequeñin Toallitas Húmedas Original", "humeda"),
            ("Paquete Pañitos Humedos Grandulones Panda X100 Unds", "humeda"),
        ],
    )
    def test_una_toalla_no_es_un_panito_humedo(self, texto, esperado):
        assert extraer_atributos(texto, ("tipo",)) == {"tipo": esperado}

    @pytest.mark.parametrize(
        ("texto", "esperado"),
        [("vaso pequeño de plástico", "vaso"), ("Vaso plástico de 450 ml con pitillo unicornio", "vaso")],
    )
    def test_un_vaso_no_es_un_plato(self, texto, esperado):
        assert extraer_atributos(texto, ("tipo",)) == {"tipo": esperado}

    @pytest.mark.parametrize(
        ("texto", "esperado"),
        [
            ("hojas papel durex tamaño 1/8", "octavo"),
            ("Bloc de papel pergamino, 25 hojas de 1/8", "octavo"),
            ("Sketchbook de papel durex 50 hojas tamaño carta", "carta"),
        ],
    )
    def test_el_tamano_del_papel_de_dibujo(self, texto, esperado):
        assert extraer_atributos(texto, ("tamano",)) == {"tamano": esperado}


class TestHuecosDelVocabularioQueDejoVerElCatalogo:
    """Productos que seguian sin atributo despues de enriquecer, no por
    juicio sino porque la tabla no tenia la palabra (o la tenia escrita de
    una forma que nunca llegaba)."""

    def test_el_tamano_a4_se_lee_aunque_la_normalizacion_lo_despegue(self):
        assert extraer_atributos("Block para bocetos A4, x 60 hojas 110g", ("tamano", "tipo")) == {
            "tamano": "a4",
            "tipo": "dibujo",
        }

    def test_el_sketch_book_es_un_block_de_dibujo(self):
        assert extraer_atributos("Sketch Book  Snoopy Azul", ("tipo",)) == {"tipo": "dibujo"}

    def test_el_cuaderno_pentagramado(self):
        nombre = "Cuaderno Musical Pentagramado Profesional Grande Argollado Tamaño Oficio"
        assert extraer_atributos(nombre, ("rayado",)) == {"rayado": "pentagramado"}

    @pytest.mark.parametrize(
        ("texto", "esperado"),
        [("Óleo franco oro de 50 ml", "dorado"), ("Pintura al óleo de 75 ml, púrpura", "morado")],
    )
    def test_oro_y_purpura_son_colores(self, texto, esperado):
        assert extraer_atributos(texto, ("color",)) == {"color": esperado}

    def test_el_papel_fotografico_no_son_hojas_de_examen(self):
        nombre = "Papel fotográfico carta a prueba de agua x 20 unidades"
        assert extraer_atributos(nombre, ("tipo",)) == {"tipo": "fotografico"}


class TestReleerLoQueUnVocabularioViejoLeyoMal:
    """Lo guardado gana sobre lo leido, salvo en las claves que se piden releer.

    Sin esta salida, `tipo=permanente` en `Pintura al oleo de 75 ml, verde
    permanente` y `punta=permanente` en los marcadores no se iban nunca: el
    enriquecedor solo agregaba claves nuevas.
    """

    def test_lo_guardado_gana_por_omision(self):
        assert atributos_combinados({"tipo": "permanente"}, {"tipo": "oleo", "color": "verde"}) == {
            "tipo": "permanente",
            "color": "verde",
        }

    def test_releer_una_clave_deja_mandar_al_nombre(self):
        assert atributos_combinados(
            {"tipo": "permanente"}, {"tipo": "oleo", "color": "verde"}, frozenset({"tipo"})
        ) == {"tipo": "oleo", "color": "verde"}

    def test_si_al_releer_el_nombre_no_dice_nada_la_clave_se_va(self):
        # `Marcador Sharpie Punta Fina` tenia `tipo=punta fina`: no dice su tinta.
        assert atributos_combinados(
            {"tipo": "punta fina", "punta": "punta fina"},
            {"punta": "punta fina"},
            frozenset({"tipo", "punta"}),
        ) == {"punta": "punta fina"}

    def test_releer_no_toca_las_demas_claves(self):
        assert atributos_combinados({"tipo": "x", "colores": 12}, {"colores": 10}, frozenset({"tipo"})) == {
            "colores": 12
        }


class TestUnRenglonQueEnumeraVariosValoresNoExigeNinguno:
    """Si el renglon nombra varios valores del MISMO atributo, el colegio pide
    un surtido, no uno de ellos. Antes se tomaba el primero de la tabla:
    `Kit de 12 pinceles ... planos redondos y abanico` exigia pinceles planos,
    lo contrario de lo pedido.

    La regla vale para los atributos de una sola dimension (forma, color,
    rayado, material, punta, presentacion, encuadernacion, grosor). `tipo` no
    entra: su tabla mezcla dimensiones (`Block cuadriculado argollado` dice
    dos tipos y los dos son ciertos), y ahi sigue ganando el mas especifico.
    """

    def test_el_kit_de_pinceles_surtidos_no_exige_forma(self):
        renglon = "Kit de 12 pinceles sintéticos. delgados, planos redondos y abanico"
        assert "forma" not in extraer_atributos(renglon, ("forma", "grosor"))

    def test_pero_si_el_grosor_que_dice_una_sola_vez(self):
        renglon = "Kit de 12 pinceles sintéticos. delgados, planos redondos y abanico"
        assert extraer_atributos(renglon, ("forma", "grosor")) == {"grosor": "delgado"}

    def test_un_cuaderno_cosido_o_argollado_no_exige_ninguno(self):
        assert extraer_atributos("cuaderno cosido o argollado", ("encuadernacion",)) == {}

    def test_dos_colores_no_exigen_ninguno(self):
        assert extraer_atributos("cartulina blanca y negra", ("color",)) == {}

    def test_una_variante_contenida_en_otra_no_cuenta_como_dos(self):
        # `doble linea` contiene `linea`: es un solo rayado, no dos.
        assert extraer_atributos("Cuaderno doble linea", ("rayado",)) == {"rayado": "doble linea"}
        assert extraer_atributos("Cuaderno cuadricula grande", ("rayado",)) == {"rayado": "cuadricula grande"}

    def test_cuaderno_cuadriculado_grande_es_un_cuaderno_grande(self):
        # En las listas `grande` es el tamano del cuaderno, no el del cuadro:
        # `cuaderno argollado cuadriculado grande 100 hojas` (Septimo, #14).
        assert extraer_atributos("cuaderno cuadriculado grande", ("rayado",)) == {"rayado": "cuadriculado"}

    @pytest.mark.parametrize(
        ("texto", "esperado"),
        [
            ("cuaderno rayado o cuadriculado", ["rayado"]),
            ("Kit de 12 pinceles sintéticos. delgados, planos redondos y abanico", ["forma"]),
            ("cuaderno cuadriculado cosido", []),
            ("Cuaderno doble linea", []),
        ],
    )
    def test_lo_que_no_se_exige_por_ambiguo_queda_marcado(self, texto, esperado):
        assert atributos_ambiguos(texto, ("rayado", "forma", "grosor", "encuadernacion")) == esperado

    def test_el_tipo_sigue_tomando_el_mas_especifico(self):
        assert extraer_atributos("Block Repuesto Kiut Carta Cuadriculado KIUT", ("tipo",)) == {
            "tipo": "cuadriculado"
        }


def test_doble_punta_no_se_lee_como_punta_fina():
    # «doble punta fina y gruesa» es un marcador de dos puntas: si ganaba
    # `punta fina`, el estuche doble punta que pide el colegio no se distinguia
    # de un marcador delgado.
    estuche = extraer_atributos("estuche de marcadores acrilicos doble punta", ("punta",))
    assert estuche == {"punta": "doble punta"}
    assert extraer_atributos("marcador doble punta fina y gruesa", ("punta",)) == {"punta": "doble punta"}
