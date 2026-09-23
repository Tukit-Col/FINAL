"""El canal semantico de la busqueda hibrida (OE3).

Dos cosas se fijan aqui. La primera es el puerto: el embeder falso no sale a la
red, es determinista y da vectores unitarios, que es lo que el CI necesita para
correr sin clave y sin que el resultado cambie entre corridas. La segunda es la
FUSION en `clasificar`: que sumar el coseno nunca hunda un match que lo lexico
ya acertaba (hibrido >= lexico), y que el rescate semantico este lo bastante
alto como para no reabrir el error de `chaquiras de colores`, que la cabeza
anclada cerro.

El rescate de un sinonimo que el lexico no tiene se prueba con vectores puestos
a mano, no con el embeder falso: el falso es de trigramas y dos sinonimos de
verdad (`estuche`/`cartuchera`) no comparten letras, asi que no podria
demostrar lo que un modelo real si hace. Fingir esa capacidad con el falso
seria una prueba que miente. Se inyecta el vector y se prueba el MECANISMO.
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
        # coseno no-trivial con `colores`. El rescate semantico esta guardado
        # justamente para que ese parecido de letras no reabra el error que la
        # cabeza anclada cerro: la cosa pedida no esta nombrada, y un coseno
        # mediano no basta para colarla.
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


class TestElRescateSemanticoLevantaLoQueElLexicoNoVe:
    """Un sinonimo que no esta en la lista de sinonimos. El lexico da 0 porque
    la cabeza no aparece nombrada; el coseno alto lo rescata. Se prueba con un
    vector puesto a mano porque el embeder de trigramas no modela sinonimos."""

    def test_un_coseno_alto_rescata_un_head_que_el_lexico_no_nombra(self):
        # Un concepto cuyo embedding es identico al del renglon (coseno 1.0)
        # pero cuyo nombre/sinonimos NO contienen la cabeza del renglon.
        (vector,) = embeder_falso(["cartuchera escolar"])
        estuche = {
            "id": "estuche",
            "nombre": "estuche",
            "sinonimos": ["cartuchera"],
            "embedding": vector,
        }
        # Cabeza 'lonchera': no aparece en 'estuche'/'cartuchera' -> lexico 0.
        _id, nombre, puntaje = clasificar(
            "lonchera termica", [estuche], embedding_renglon=vector
        )
        assert nombre == "estuche"
        assert puntaje >= 0.5

    def test_un_coseno_mediano_no_rescata(self):
        # Vector ortogonal-ish: sin senal semantica fuerte, un head no nombrado
        # sigue sin match, igual que en el lexico puro.
        (vector,) = embeder_falso(["cartuchera escolar"])
        (otro,) = embeder_falso(["balon de futbol de salon"])
        estuche = {"id": "estuche", "nombre": "estuche", "sinonimos": [], "embedding": vector}
        _id, _nombre, puntaje = clasificar("lonchera termica", [estuche], embedding_renglon=otro)
        assert puntaje < 0.5
