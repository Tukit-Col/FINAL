from __future__ import annotations

import math

from tukit_catalogo.clasificacion import clasificar
from tukit_catalogo.embeddings import (
    DIMENSION_EMBEDDING,
    coseno,
    embeder_falso,
    promedio,
    texto_de_producto,
)


class TestElEmbederFalsoSirveParaProbar:
    def test_el_mismo_texto_da_siempre_el_mismo_vector(self):
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

    def test_el_embeder_falso_no_usa_urllib_ni_abre_conexiones(self):
        import inspect

        fuente = inspect.getsource(embeder_falso)
        assert "urllib" not in fuente
        assert "urlopen" not in fuente


class TestElCoseno:
    def test_el_coseno_de_un_vector_consigo_mismo_es_uno(self):
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
        (pegante,) = embeder_falso(["pegante en barra"])
        assert coseno(centro, a) > coseno(centro, pegante)

    def test_promedio_sin_vectores_es_none(self):
        assert promedio([]) is None


def _texto(nombre: str, concepto: str = "", **attrs) -> str:
    return texto_de_producto(nombre, concepto or None, attrs or None)


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
    def test_sin_embedding_del_renglon_clasifica_solo_por_lexico(self):
        _id, nombre, puntaje = clasificar("pompones de colores para manualidades", CATALOGO)
        assert nombre == "pompones"
        assert puntaje > 0.5

    def test_chaquiras_de_colores_queda_fuera_aunque_comparta_letras(self):
        (consulta,) = embeder_falso(["chaquiras de colores"])
        _id, _nombre, puntaje = clasificar("chaquiras de colores", CATALOGO, embedding_renglon=consulta)
        assert puntaje < 0.5

    def test_el_coseno_no_hunde_un_match_que_el_lexico_acertaba(self):
        renglon = "pompones de colores para manualidades"
        (consulta,) = embeder_falso([renglon])
        _i, _n, solo_lexico = clasificar(renglon, CATALOGO)
        _i, _n, hibrido = clasificar(renglon, CATALOGO, embedding_renglon=consulta)
        assert hibrido >= solo_lexico

    def test_un_match_lexico_perfecto_mas_coseno_no_pasa_de_uno(self):
        renglon = "cuaderno cosido"
        (consulta,) = embeder_falso([renglon])
        exacto = {"id": "x", "nombre": renglon, "sinonimos": [], "embedding": consulta}
        _i, _n, hibrido = clasificar(renglon, [exacto], embedding_renglon=consulta)
        assert hibrido <= 1.0

    def test_un_coseno_negativo_no_resta(self):
        renglon = "pompones de colores para manualidades"
        (consulta,) = embeder_falso([renglon])
        opuestos = [{**c, "embedding": [-x for x in consulta]} for c in CATALOGO]
        _i, nombre_lexico, solo_lexico = clasificar(renglon, opuestos)
        _i, nombre, hibrido = clasificar(renglon, opuestos, embedding_renglon=consulta)
        assert nombre == nombre_lexico
        assert hibrido >= solo_lexico
