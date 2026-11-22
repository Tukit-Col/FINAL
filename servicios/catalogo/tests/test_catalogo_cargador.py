from __future__ import annotations

import pytest
from tukit_catalogo.cargador import (
    COLUMNAS_ENRIQUECIDAS,
    Problema,
    atributos_de_csv,
    isbn13_valido,
    normalizar_isbn,
    pesos_a_centavos,
    validar_referencias,
)


class TestIsbn:

    @pytest.mark.parametrize(
        "isbn",
        [
            "9788428536523",
            "9789585189232",
            "9789580714729",
            "9791370400521",
        ],
    )
    def test_acepta_los_isbn_que_se_observaron_en_las_tiendas(self, isbn):
        assert isbn13_valido(isbn)

    @pytest.mark.parametrize(
        "isbn",
        [
            "9788428536524",
            "978842853652",
            "97884285365233",
            "1234567890123",
            "",
            "732461",
        ],
    )
    def test_rechaza_lo_que_no_es_un_isbn13(self, isbn):
        assert not isbn13_valido(isbn)

    def test_el_sku_de_una_tienda_no_pasa_por_isbn(self):
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

    def test_convierte_pesos_enteros_a_centavos(self):
        assert pesos_a_centavos(34200) == 3420000
        assert pesos_a_centavos("42000") == 4200000

    def test_tolera_el_formato_con_puntos_de_miles(self):
        assert pesos_a_centavos("132.000") == 13200000
        assert pesos_a_centavos("$ 105.000") == 10500000

    def test_rechaza_un_precio_que_no_es_un_precio(self):
        for malo in ("", "gratis", "0", None, "-5000"):
            with pytest.raises(ValueError):
                pesos_a_centavos(malo)


class TestReferencias:

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

    def test_las_columnas_enriquecidas_estan_declaradas(self):
        assert {
            "imagen_url",
            "atributos",
            "unidades_por_empaque",
            "unidad_base",
            "personaje",
        } == COLUMNAS_ENRIQUECIDAS

    def test_ninguna_columna_enriquecida_entra_en_el_set_de_actualizacion(self):
        from tukit_catalogo.modelos import Base

        producto = Base.metadata.tables["producto_canonico"]
        claves = {c.name for c in producto.primary_key.columns}
        columnas_csv = {c.name for c in producto.columns}

        actualizables = {c for c in columnas_csv if c not in claves and c not in COLUMNAS_ENRIQUECIDAS}
        assert not (actualizables & COLUMNAS_ENRIQUECIDAS)
        assert {"nombre", "nivel", "concepto_id", "activo"} <= actualizables


class TestLosAtributosViajanEnElCsv:

    def test_lee_los_atributos_exportados(self):
        assert atributos_de_csv('{"tamano": "grande"}') == {"tamano": "grande"}

    def test_descarta_las_claves_de_legado(self):
        crudo = '{"cantidades_declaradas": ["20:cm"], "frase_ancla": "tabla periodica", "color": "azul"}'
        assert atributos_de_csv(crudo) == {"color": "azul"}

    def test_lo_vacio_o_roto_es_un_diccionario_vacio(self):
        assert atributos_de_csv("") == {}
        assert atributos_de_csv(None) == {}
        assert atributos_de_csv("{no es json") == {}
        assert atributos_de_csv('["lista"]') == {}
