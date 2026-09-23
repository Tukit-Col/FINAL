"""Pruebas del cargador de datos curados.

El cargador es la primera pieza que mete datos de verdad en la base, y el
riesgo no es que falle: es que **funcione a medias en silencio**. Un producto
sin imagen se carga igual de bien que uno con imagen, y el papa se entera al
ver un hueco gris donde deberia haber un cuaderno. Un empaque mal contado se
carga igual de bien, y el papa se entera cuando le llegan doce lapices en vez
de una caja.

De ahi la forma de estas pruebas: casi todas son sobre las funciones PURAS de
validacion y normalizacion, no sobre la escritura. Lo que hay que fijar no es
que el INSERT corra, es que los datos malos se vean.
"""

from __future__ import annotations

import pytest
from tukit_catalogo.cargador import (
    COLUMNAS_ENRIQUECIDAS,
    Problema,
    isbn13_valido,
    normalizar_isbn,
    pesos_a_centavos,
    validar_referencias,
)


class TestIsbn:
    """El ISBN es la llave con la que un libro se compara entre tiendas.

    Sin el, dos fichas de la misma biblia en dos librerias son dos productos
    distintos y no se puede decir cual esta mas barata, que es justo lo que
    Tukit tiene que responder. Un ISBN mal transcrito es peor que ninguno:
    fabrica un producto que no existe.
    """

    @pytest.mark.parametrize(
        "isbn",
        [
            "9788428536523",  # Biblia Latinoamerica, vista en dos tiendas
            "9789585189232",  # Constitucion Politica, Solar
            "9789580714729",  # Diccionario Nacho
            "9791370400521",  # prefijo 979, tambien legitimo
        ],
    )
    def test_acepta_los_isbn_que_se_observaron_en_las_tiendas(self, isbn):
        assert isbn13_valido(isbn)

    @pytest.mark.parametrize(
        "isbn",
        [
            "9788428536524",  # ultimo digito cambiado: la suma ya no cuadra
            "978842853652",  # 12 digitos
            "97884285365233",  # 14
            "1234567890123",  # no empieza por 978 ni 979
            "",
            "732461",  # un SKU de tienda, que es el error que de verdad paso
        ],
    )
    def test_rechaza_lo_que_no_es_un_isbn13(self, isbn):
        assert not isbn13_valido(isbn)

    def test_el_sku_de_una_tienda_no_pasa_por_isbn(self):
        """Caso real y no hipotetico: al raspar una pagina de categoria en vez
        de una ficha de producto, lo que vuelve como 'ISBN' es el codigo
        interno de la tienda. Si eso entrara al catalogo, dos libros distintos
        podrian colisionar en la misma llave."""
        assert not isbn13_valido("732461")

    def test_normalizar_quita_guiones_y_espacios(self):
        assert normalizar_isbn("978-84-285-3652-3") == "9788428536523"
        assert normalizar_isbn(" 9788428536523 ") == "9788428536523"
        assert normalizar_isbn("978 84 285 3652 3") == "9788428536523"

    def test_normalizar_no_inventa_cuando_no_hay_nada(self):
        assert normalizar_isbn("") is None
        assert normalizar_isbn("   ") is None
        assert normalizar_isbn(None) is None


class TestPrecios:
    """El precio se guarda en centavos y entero, nunca en coma flotante.

    Un peso colombiano no tiene centavos en la practica, pero la columna es
    `valor_centavos` y mezclar unidades es como se pierde un factor de cien
    sin que nadie lo note hasta la factura.
    """

    def test_convierte_pesos_enteros_a_centavos(self):
        assert pesos_a_centavos(34200) == 3420000
        assert pesos_a_centavos("42000") == 4200000

    def test_tolera_el_formato_con_puntos_de_miles(self):
        """Las tiendas colombianas escriben 132.000 y eso no es un decimal."""
        assert pesos_a_centavos("132.000") == 13200000
        assert pesos_a_centavos("$ 105.000") == 10500000

    def test_rechaza_un_precio_que_no_es_un_precio(self):
        for malo in ("", "gratis", "0", None, "-5000"):
            with pytest.raises(ValueError):
                pesos_a_centavos(malo)


class TestReferencias:
    """Una oferta que apunta a un producto que no existe rompe el kit.

    Estas son las que SI bloquean la carga. El resto de problemas de calidad se
    reportan y dejan pasar, porque un catalogo incompleto sigue sirviendo; una
    referencia roto, no.
    """

    def test_no_reporta_nada_cuando_todo_cuadra(self):
        problemas = validar_referencias(
            conceptos={"c1"},
            productos={"p1": "c1"},
            tiendas={"t1"},
            ofertas={"o1": ("p1", "t1")},
            precios={"pr1": "o1"},
        )
        assert problemas == []

    def test_detecta_un_producto_sin_concepto(self):
        problemas = validar_referencias(
            conceptos={"c1"},
            productos={"p1": "FANTASMA"},
            tiendas={"t1"},
            ofertas={},
            precios={},
        )
        assert len(problemas) == 1
        assert problemas[0].bloqueante
        assert "FANTASMA" in problemas[0].detalle

    def test_detecta_una_oferta_sin_producto_y_otra_sin_tienda(self):
        problemas = validar_referencias(
            conceptos={"c1"},
            productos={"p1": "c1"},
            tiendas={"t1"},
            ofertas={"o1": ("FANTASMA", "t1"), "o2": ("p1", "TIENDA_FANTASMA")},
            precios={},
        )
        assert len(problemas) == 2
        assert all(p.bloqueante for p in problemas)

    def test_detecta_un_precio_huerfano(self):
        problemas = validar_referencias(
            conceptos={"c1"},
            productos={"p1": "c1"},
            tiendas={"t1"},
            ofertas={"o1": ("p1", "t1")},
            precios={"pr1": "OFERTA_FANTASMA"},
        )
        assert len(problemas) == 1
        assert problemas[0].bloqueante


class TestProblema:
    def test_un_problema_se_lee_sin_tener_que_abrir_el_codigo(self):
        p = Problema(bloqueante=True, clase="referencia", detalle="producto p1 -> concepto FANTASMA")
        texto = str(p)
        assert "referencia" in texto
        assert "FANTASMA" in texto


class TestElCargadorNoDeshaceElEnriquecimiento:
    """El upsert no puede pisar lo que el CSV no sabe.

    `enriquecer` escribe empaque, portada y personaje directamente en la base.
    El cargador actualizaba toda columna presente en la fila del CSV, asi que
    volver a correrlo devolvia el catalogo al estado anterior: portadas en
    nulo y empaques de vuelta en uno. Y lo hacia en silencio, informando que
    habia escrito 330 productos, que era cierto.
    """

    def test_las_columnas_enriquecidas_estan_declaradas(self):
        assert {
            "imagen_url",
            "atributos",
            "unidades_por_empaque",
            "unidad_base",
            "personaje",
        } == COLUMNAS_ENRIQUECIDAS

    def test_ninguna_columna_enriquecida_entra_en_el_set_de_actualizacion(self):
        """Se comprueba sobre el modelo real, no sobre una copia: si alguien
        agrega una columna enriquecida nueva y olvida declararla, la prueba
        que importa es esta."""
        from tukit_catalogo.modelos import Base

        producto = Base.metadata.tables["producto_canonico"]
        claves = {c.name for c in producto.primary_key.columns}
        columnas_csv = {c.name for c in producto.columns}

        actualizables = {c for c in columnas_csv if c not in claves and c not in COLUMNAS_ENRIQUECIDAS}
        assert not (actualizables & COLUMNAS_ENRIQUECIDAS)
        # Y lo que si debe seguir actualizandose desde el CSV, que es la razon
        # de que el upsert exista.
        assert {"nombre", "nivel", "concepto_id", "activo"} <= actualizables
