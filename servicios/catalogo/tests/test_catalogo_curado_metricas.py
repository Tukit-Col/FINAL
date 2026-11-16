"""Las metricas medidas del catalogo curado: cobertura del corpus y basura del universo cerrado."""

# Los fixtures `catalogo` y `cargado` llegan de `_ayudas_catalogo_curado`.
# ruff: noqa: F811

from __future__ import annotations

import pytest
from _ayudas_catalogo_curado import (  # noqa: F401  (los fixtures se reusan tal cual)
    UMBRAL_ACEPTACION,
    catalogo,
)


class TestCoberturaDelCorpus:
    def test_resuelve_la_mayor_parte_de_los_renglones_reales(self, catalogo):
        """La medida que importa para la tesis no es cuantos productos hay sino
        que fraccion de una lista escolar de verdad queda resuelta."""
        cobertura = catalogo["metricas"]["cobertura_corpus"]
        assert cobertura["lineas_corpus"] == 3610
        assert cobertura["cobertura_lineas"] >= 0.95
        assert cobertura["cobertura_unidades"] >= 0.95

    def test_el_corpus_tiene_diecisiete_colegios_distintos(self, catalogo):
        """`colegio_id` leido como numero hace que `2.1` y `2.10` colapsen y el
        corpus pase de 17 a 16 sin que nada falle. Es un defecto que ya se
        cometio una vez."""
        por_colegio = catalogo["metricas"]["cobertura_corpus"]["cobertura_por_colegio"]
        assert len(por_colegio) == 17

    def test_ningun_colegio_queda_desatendido(self, catalogo):
        """El promedio puede tapar un colegio entero mal cubierto."""
        por_colegio = catalogo["metricas"]["cobertura_corpus"]["cobertura_por_colegio"]
        peor = min(por_colegio.items(), key=lambda kv: kv[1]["cobertura"])
        assert peor[1]["cobertura"] >= 0.80, f"colegio {peor[0]}: {peor[1]}"


class TestCuradoNoFiltrado:
    def test_el_universo_cerrado_deja_pasar_menos_basura_que_el_filtrado(self, catalogo):
        """El hallazgo central del perfilado: filtrar por palabra sobre un
        universo abierto concentro la basura en vez de quitarla, 10,41 % en la
        semilla contra 5,53 % del crudo. Construir por inclusion tiene que
        medir por debajo de los dos o el cambio de enfoque no sirvio de nada.
        """
        rn = catalogo["metricas"]["rn_p12_sobre_el_universo_cerrado"]
        referencia = rn["referencia_perfilado"]
        assert rn["tasa"] < referencia["crudo_del_scraper"]
        assert rn["tasa"] < referencia["semilla_de_la_bd"]

    def test_el_emparejamiento_esta_medido_y_no_declarado(self, catalogo):
        """Un umbral sin muestra anotada es una opinion."""
        emparejamiento = catalogo["metricas"]["emparejamiento"]
        assert emparejamiento is not None
        assert emparejamiento["pares_anotados"] >= 100
        assert emparejamiento["positivos"] > 0 and emparejamiento["negativos"] > 0
        operativo = emparejamiento["punto_operativo"]
        assert operativo["umbral"] == pytest.approx(UMBRAL_ACEPTACION, abs=0.011)
        assert operativo["precision"] >= 0.80
