"""Los atributos que salen de la ficha de la tienda y como se combinan con lo leido y lo guardado.

Todos los nombres de estas pruebas son reales, copiados del catalogo cargado.
No son ejemplos inventados para que el codigo pase: son las formas concretas
en que las tiendas colombianas escriben sus productos, con sus mayusculas
irregulares, sus abreviaturas y sus cifras pegadas.
"""

from __future__ import annotations

from tukit_catalogo.enriquecer import (
    atributos_combinados,
    atributos_de_ficha,
)


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

    def test_devuelve_solo_lo_que_el_concepto_pide(self):
        # La ficha trae cincuenta y un campos, y casi todos son contabilidad
        # interna de la tienda: `Factor Neto PUM`, `IVA`, `Prime`.
        assert atributos_de_ficha({"Tamaño": "Grande", "IVA": "19", "Prime": "Si"}, ("tamano",)) == {
            "tamano": "grande"
        }


class TestLoGuardadoContraLoReleido:
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
