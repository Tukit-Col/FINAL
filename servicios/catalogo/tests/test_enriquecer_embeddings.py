from __future__ import annotations

from tukit_catalogo.embeddings import DIMENSION_EMBEDDING, MODELO_FALSO, embeder_falso
from tukit_catalogo.enriquecer import (
    embeddings_a_actualizar,
)


class TestPoblarEmbeddings:

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

        espia.modelo = MODELO_FALSO

        cambios = embeddings_a_actualizar(self.PRODUCTOS, espia)

        assert {c["pid"] for c in cambios} == {"p1", "p2"}
        assert all(len(c["embedding"]) == DIMENSION_EMBEDDING for c in cambios)
        assert all(c["embedding_model"] == MODELO_FALSO for c in cambios)
        p1 = next(c for c in cambios if c["pid"] == "p1")
        assert "cuaderno" in p1["texto_embedding"].lower()
        assert "cuadriculado" in p1["texto_embedding"].lower()
        assert len(vistos) == 2

    def test_es_idempotente_no_recalcula_lo_que_no_cambio(self):
        cambios = embeddings_a_actualizar(self.PRODUCTOS, embeder_falso)
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
        poblados[0]["nombre"] = "Cuaderno argollado 80 hojas"
        rehechos = embeddings_a_actualizar(poblados, embeder_falso)
        assert [c["pid"] for c in rehechos] == ["p1"]
