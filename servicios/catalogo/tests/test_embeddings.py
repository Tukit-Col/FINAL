"""El canal semantico de la busqueda hibrida (OE3).

Dos cosas se fijan aqui. La primera es el puerto: el embeder falso no sale a la
red, es determinista y da vectores unitarios, que es lo que el CI necesita para
correr sin clave y sin que el resultado cambie entre corridas. La segunda es la
FUSION en `clasificar`: que sumar el coseno nunca hunda un match que lo lexico
ya acertaba (hibrido >= lexico), y que sin cabeza anclada el coseno no baste
para reabrir el error de `chaquiras de colores`, que la cabeza anclada cerro.
"""

from __future__ import annotations

import math

from tukit_catalogo.descubrir import clasificar
from tukit_catalogo.embeddings import (
    DIMENSION_EMBEDDING,
    coseno,
    embeder_falso,
    promedio,
    texto_de_producto,
)


class TestElEmbederFalsoSirveParaProbar:
    def test_es_determinista(self):
        una = embeder_falso(["cuaderno cosido 100 hojas"])
        otra = embeder_falso(["cuaderno cosido 100 hojas"])
        assert una == otra

    def test_da_un_vector_de_la_dimension_declarada(self):
        (vector,) = embeder_falso(["block oficio"])
        assert len(vector) == DIMENSION_EMBEDDING

    def test_el_vector_es_unitario(self):
        (vector,) = embeder_falso(["marcador borrable"])
        assert math.isclose(math.sqrt(sum(x * x for x in vector)), 1.0, rel_tol=1e-9)

    def test_lo_parecido_en_letras_queda_cerca_y_lo_distinto_lejos(self):
        bloc, block, pegante = embeder_falso(["bloc oficio", "block oficio", "pegante en barra"])
        assert coseno(bloc, block) > coseno(bloc, pegante)

    def test_no_sale_a_la_red(self):
        # Se lee el archivo, como en `test_consulta`: un camino a la red que
        # nadie llama hoy es uno que alguien llama manana. El embeder de las
        # pruebas no puede tener por donde salir.
        import inspect

        fuente = inspect.getsource(embeder_falso)
        assert "urllib" not in fuente
        assert "urlopen" not in fuente


class TestElCoseno:
    def test_iguales_da_uno(self):
        (v,) = embeder_falso(["colores x 12"])
        assert math.isclose(coseno(v, v), 1.0, rel_tol=1e-9)

    def test_vacios_o_disparejos_dan_cero_sin_reventar(self):
        assert coseno([], [1.0]) == 0.0
        assert coseno([1.0, 0.0], [1.0]) == 0.0

    def test_el_promedio_es_el_centro_normalizado(self):
        a, b = embeder_falso(["cuaderno cosido", "cuaderno argollado"])
        centro = promedio([a, b])
        assert centro is not None
        assert math.isclose(math.sqrt(sum(x * x for x in centro)), 1.0, rel_tol=1e-9)
        # El centro de dos cuadernos esta mas cerca de un cuaderno que de un
        # pegante: el vector del concepto se deriva del de sus productos.
        (pegante,) = embeder_falso(["pegante en barra"])
        assert coseno(centro, a) > coseno(centro, pegante)

    def test_promedio_sin_vectores_es_none(self):
        assert promedio([]) is None


def _texto(nombre: str, concepto: str = "", **attrs) -> str:
    return texto_de_producto(nombre, concepto or None, attrs or None)


# Conceptos con embedding poblado, como los serviria `cargar_indice`. El
# embedding del concepto es el centro de los textos de sus productos.
def _concepto(nombre, sinonimos, textos):
    return {
        "id": nombre,
        "nombre": nombre,
        "sinonimos": sinonimos,
        "embedding": promedio(embeder_falso(textos)),
    }


COLORES = _concepto(
    "colores",
    ["lapices de colores", "colores de madera"],
    ["colores de madera x 12", "lapices de colores x 12"],
)
POMPONES = _concepto("pompones", [], ["pompones de colores surtidos"])
CUADERNO = _concepto(
    "cuaderno",
    ["cuaderno cosido"],
    ["cuaderno cosido 100 hojas", "cuaderno argollado 80 hojas"],
)
CATALOGO = [COLORES, POMPONES, CUADERNO]


class TestLaFusionNoRompeLaCabezaAnclada:
    def test_sin_embedding_del_renglon_se_comporta_como_antes(self):
        # La ruta de las pruebas existentes y de los callers viejos: sin vector
        # de consulta, `clasificar` es exactamente el lexico de siempre.
        _id, nombre, puntaje = clasificar("pompones de colores para manualidades", CATALOGO)
        assert nombre == "pompones"
        assert puntaje > 0.5

    def test_chaquiras_de_colores_sigue_fuera_aunque_comparta_letras(self):
        # El embeder falso es de trigramas, asi que `chaquiras de colores` tiene
        # coseno no-trivial con `colores`. Ese parecido de letras no reabre el
        # error que la cabeza anclada cerro: la cosa pedida no esta nombrada, y
        # sin cabeza anclada el puntaje es 0.
        (consulta,) = embeder_falso(["chaquiras de colores"])
        _id, _nombre, puntaje = clasificar("chaquiras de colores", CATALOGO, embedding_renglon=consulta)
        assert puntaje < 0.5

    def test_el_coseno_no_hunde_un_match_que_el_lexico_acertaba(self):
        # Hibrido >= lexico, por construccion: para el mismo renglon, el puntaje
        # con embedding no puede ser menor que sin el.
        renglon = "pompones de colores para manualidades"
        (consulta,) = embeder_falso([renglon])
        _i, _n, solo_lexico = clasificar(renglon, CATALOGO)
        _i, _n, hibrido = clasificar(renglon, CATALOGO, embedding_renglon=consulta)
        assert hibrido >= solo_lexico

    def test_un_match_lexico_perfecto_mas_coseno_no_pasa_de_uno(self):
        # El puntaje ES la confianza que `inteligencia` guarda en
        # `candidato_item.confianza`, una columna NUMERIC(4,3) con el check
        # `candidato_confianza_en_rango` (0..1). Cuando el lexico acierta la
        # cabeza y la frase entera (parecido 1.0), la base ya vale 1.0, y el
        # aporte del coseno la empujaba por encima -> viola el check y el
        # pipeline muere en la insercion. La fusion debe tener techo en 1.0.
        renglon = "cuaderno cosido"
        (consulta,) = embeder_falso([renglon])
        # Concepto cuyo nombre ES el renglon (parecido lexico 1.0) y cuyo
        # embedding es el del renglon (coseno 1.0): el caso extremo que dispara
        # el desborde. Sin techo, 0.6 + 0.4 + 0.15 = 1.15.
        exacto = {"id": "x", "nombre": renglon, "sinonimos": [], "embedding": consulta}
        _i, _n, hibrido = clasificar(renglon, [exacto], embedding_renglon=consulta)
        assert hibrido <= 1.0

    def test_un_coseno_negativo_no_resta(self):
        # Hibrido >= lexico tiene que valer sin suponer nada del modelo. Con el
        # de produccion los cosenos medidos nunca bajan de 0.43, pero un modelo
        # distinto puede dar negativos, y entonces `0.15 * cos` restaba: el
        # canal semantico hundia un match que el lexico acertaba.
        renglon = "pompones de colores para manualidades"
        (consulta,) = embeder_falso([renglon])
        opuestos = [{**c, "embedding": [-x for x in consulta]} for c in CATALOGO]
        _i, nombre_lexico, solo_lexico = clasificar(renglon, opuestos)
        _i, nombre, hibrido = clasificar(renglon, opuestos, embedding_renglon=consulta)
        assert nombre == nombre_lexico
        assert hibrido >= solo_lexico
