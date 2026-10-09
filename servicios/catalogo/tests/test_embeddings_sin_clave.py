"""NFR-MAN-01: los bordes del canal semantico que se alcanzan SIN clave de Gemini.

`test_embeddings` fija el camino feliz del embeder falso y de la fusion. Aqui se
ata lo que un vector degenerado o una configuracion sin clave pueden romper en
silencio:

  - un vector nulo (norma cero) no debe producir `NaN` ni una division por cero,
    sino un coseno 0: asi un concepto sin embeddings utiles no gana por accidente;
  - el centro de varios vectores ignora los de otra dimension en vez de mezclar
    columnas que no son comparables;
  - `embeder_gemini` sin `GEMINI_API_KEY` se niega con un error claro y NO sale
    a la red: la alternativa seria inventar un vector que ponga cerca cosas que
    no lo estan, que es peor que no tener canal semantico;
  - cada embeder declara el modelo que marca sus vectores.

La clave no se lee ni se define en este archivo: el `conftest` la borra antes de
cada prueba. Lo que SI exige la clave (armar y enviar el lote a Gemini, el
analisis de su respuesta) queda sin cubrir a proposito; ver el informe.
"""

from __future__ import annotations

import math
import urllib.request

import pytest
from tukit_catalogo.embeddings import (
    DIMENSION_EMBEDDING,
    MODELO_FALSO,
    MODELO_GEMINI,
    EmbeddingFallido,
    coseno,
    embeder_falso,
    embeder_gemini,
    promedio,
    texto_de_concepto,
    texto_de_producto,
)

pytestmark = pytest.mark.nfr("NFR-MAN-01")


def test_el_texto_de_un_concepto_junta_su_nombre_y_sus_sinonimos():
    """El vector de un concepto se calcula de su nombre mas como mas lo llama la gente, en ese orden."""
    assert texto_de_concepto("cartuchera", ["estuche", "lapicera"]) == "cartuchera estuche lapicera"
    assert texto_de_concepto("cartuchera") == "cartuchera"


def test_el_texto_de_un_producto_lleva_nombre_concepto_y_atributos_en_orden():
    """Es lo que se guarda en `texto_embedding`: se lee para depurar por que dos cosas quedaron cerca."""
    texto = texto_de_producto("Cosido 100 hojas Norma", "cuaderno", {"rayado": "cuadriculado", "hojas": 100})
    assert texto == "Cosido 100 hojas Norma cuaderno rayado cuadriculado hojas 100"
    assert texto_de_producto("Colores x12") == "Colores x12"


def test_el_coseno_con_un_vector_nulo_es_cero_y_no_nan():
    """Un vector de ceros del mismo largo no tiene direccion: el coseno es 0.0, sin dividir por cero."""
    assert coseno([0.0, 0.0, 0.0], [1.0, 2.0, 3.0]) == 0.0
    assert coseno([1.0, 2.0, 3.0], [0.0, 0.0, 0.0]) == 0.0
    resultado = coseno([0.0, 0.0], [0.0, 0.0])
    assert resultado == 0.0
    assert not math.isnan(resultado)


def test_el_coseno_de_vectores_no_unitarios_se_normaliza():
    """Aunque los vectores no lleguen unitarios (pudieron venir de otra fuente) el coseno queda en [-1, 1]."""
    assert math.isclose(coseno([3.0, 4.0], [6.0, 8.0]), 1.0, rel_tol=1e-12)
    assert math.isclose(coseno([1.0, 0.0], [0.0, 5.0]), 0.0, abs_tol=1e-12)
    assert math.isclose(coseno([2.0, 0.0], [-7.0, 0.0]), -1.0, rel_tol=1e-12)


def test_el_promedio_descarta_los_vectores_de_otra_dimension():
    """La dimension la fija el primer vector util; uno de otro largo no se mezcla ni descuadra la suma."""
    centro = promedio([[3.0, 4.0], [1.0, 2.0, 3.0], [3.0, 4.0]])
    assert centro is not None
    assert len(centro) == 2
    assert math.isclose(centro[0], 0.6, rel_tol=1e-12)
    assert math.isclose(centro[1], 0.8, rel_tol=1e-12)


def test_el_promedio_ignora_los_vectores_vacios_y_sin_ninguno_es_none():
    """Un embedding vacio (producto sin vector) no cuenta; si ninguno sirve el concepto queda sin vector."""
    assert promedio([[], [1.0, 0.0]]) == [1.0, 0.0]
    assert promedio([[], []]) is None


def test_el_promedio_de_vectores_opuestos_es_nulo_y_no_revienta():
    """Si los vectores se cancelan, el centro es el vector cero sin normalizar (ni NaN), y su coseno es 0."""
    centro = promedio([[1.0, 0.0], [-1.0, 0.0]])
    assert centro == [0.0, 0.0]
    assert coseno(centro, [1.0, 0.0]) == 0.0


def test_el_embeder_falso_no_mezcla_los_textos_de_un_mismo_lote():
    """El vector de un texto es el mismo solo o en lote, y un lote vacio da una lista vacia."""
    solo = embeder_falso(["bloc oficio"])[0]
    en_lote = embeder_falso(["pegante en barra", "bloc oficio", "colores"])[1]
    assert solo == en_lote
    assert embeder_falso([]) == []


def test_el_embeder_falso_ignora_tildes_mayusculas_y_espacios_repetidos():
    """`LÁPIZ  Negro` y `lapiz negro` son el mismo texto para el vector: la tilde no separa cosas iguales."""
    a, b = embeder_falso(["LÁPIZ  Negro", "lapiz negro"])
    assert a == b
    assert len(a) == DIMENSION_EMBEDDING


def test_cada_embeder_declara_con_que_modelo_marca_sus_vectores():
    """Quien puebla la base lee `.modelo` para escribir `embedding_model` y recalcular si el modelo cambia."""
    assert embeder_falso.modelo == MODELO_FALSO == "falso-trigramas-1024"
    assert embeder_gemini.modelo == MODELO_GEMINI == "gemini-embedding-001"


@pytest.fixture()
def sin_red(monkeypatch):
    """Cualquier intento de abrir una URL falla la prueba: sin clave no debe haber ni un intento."""
    intentos: list[str] = []

    def prohibido(pedido, *args, **kwargs):
        intentos.append(getattr(pedido, "full_url", str(pedido)))
        raise AssertionError("se intento abrir una URL")

    monkeypatch.setattr(urllib.request, "urlopen", prohibido)
    return intentos


@pytest.mark.parametrize("textos", [["cuaderno rayado"], ["uno", "dos", "tres"], []])
def test_gemini_sin_clave_se_niega_con_un_error_claro_y_no_sale_a_la_red(sin_red, textos):
    """Sin `GEMINI_API_KEY` el embeder alza `EmbeddingFallido` ANTES de armar la peticion (tambien en vacio).

    El mensaje nombra la variable que falta, para que quien lo lee en un log
    sepa que configurar. No hay reintento ni vector inventado.
    """
    with pytest.raises(EmbeddingFallido, match="GEMINI_API_KEY"):
        embeder_gemini(textos)
    assert sin_red == []
