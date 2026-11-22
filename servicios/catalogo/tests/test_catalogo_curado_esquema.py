# ruff: noqa: F811

from __future__ import annotations

import uuid

import pytest
from _ayudas_catalogo_curado import (  # noqa: F401  (los fixtures se reusan tal cual)
    cargado,
    catalogo,
    del_corpus,
)
from tukit_catalogo.cargador import CONCEPTOS_LIBRO
from tukit_catalogo.modelos import (
    CALIDAD_POR_NIVEL,
    Concepto,
    Nivel,
    OfertaTienda,
    PrecioOferta,
    ProductoCanonico,
)

CONCEPTOS_CON_PERSONAJE_ESPERADOS = 18


class TestCargaEnElEsquema:
    def test_los_cuatro_csv_entran_en_las_tablas_reales(self, cargado, catalogo):
        assert cargado.query(Concepto).count() == len(catalogo["conceptos"])
        assert cargado.query(ProductoCanonico).count() == len(catalogo["productos_canonicos"])
        assert cargado.query(OfertaTienda).count() == len(catalogo["ofertas_tienda"])
        assert cargado.query(PrecioOferta).count() == len(catalogo["precios_oferta"])

    def test_el_catalogo_no_esta_vacio(self, cargado):
        assert cargado.query(ProductoCanonico).count() >= 200
        assert sum(1 for c in cargado.query(Concepto) if del_corpus(c.codigo)) == 99


class TestConceptoValido:
    def test_todo_producto_cuelga_de_un_concepto_del_corpus(self, cargado, catalogo):
        del catalogo
        codigos = {c.codigo for c in cargado.query(Concepto)}
        assert sum(1 for codigo in codigos if del_corpus(codigo)) == 99
        assert all(del_corpus(c) or c.startswith("C1") or c in CONCEPTOS_LIBRO for c in codigos)
        for producto in cargado.query(ProductoCanonico):
            concepto = cargado.get(Concepto, producto.concepto_id)
            assert concepto is not None
            assert concepto.codigo in codigos

    def test_el_sku_nombra_al_concepto_y_al_nivel_que_dice_la_fila(self, cargado):
        for producto in cargado.query(ProductoCanonico):
            if producto.sku_interno.startswith(("TK-REV-", "TK-LIB-")):
                continue
            concepto = cargado.get(Concepto, producto.concepto_id)
            partes = producto.sku_interno.split("-")
            assert partes[0] == "TK"
            assert partes[1] == concepto.codigo
            assert partes[2] == producto.nivel[:3].upper()


class TestCuradoPor:
    def test_ningun_producto_se_queda_sin_curador(self, cargado):
        for producto in cargado.query(ProductoCanonico):
            assert producto.curado_por is not None
            assert producto.curado_por != uuid.UUID(int=0)
        assert len({p.curado_por for p in cargado.query(ProductoCanonico)}) <= 2

    def test_todo_producto_dice_de_que_fichero_salio(self, catalogo):
        procedencia = {f["producto_id"]: f for f in catalogo["productos_procedencia"]}
        assert len(procedencia) == len(catalogo["productos_canonicos"])
        for producto in catalogo["productos_canonicos"]:
            origen = procedencia[producto["id"]]
            assert origen["fichero_fuente"]
            assert origen["url_origen"].startswith("http")
            assert origen["sku_interno"] == producto["sku_interno"]
            if origen["fichero_fuente"] == "cola_revision":
                assert not origen["sha256_fichero"]
                assert origen["tienda_origen"]
            else:
                assert len(origen["sha256_fichero"]) == 64
                assert origen["indice_en_fichero"].isdigit()

    def test_todas_las_fuentes_estan_fijadas_por_hash(self, catalogo):
        entradas = catalogo["metricas"]["entradas"]
        assert set(entradas) == {"feed_scraper", "grancentral"}
        for fuente in entradas.values():
            assert len(fuente["sha256"]) == 64
            assert fuente["filas"] > 0


class TestNiveles:
    def test_solo_existen_los_tres_niveles(self, cargado):
        niveles = {p.nivel for p in cargado.query(ProductoCanonico)}
        assert niveles <= {n.value for n in Nivel}
        assert niveles == {"economico", "confiable", "premium"}

    def test_la_puntuacion_de_calidad_se_deriva_del_nivel(self, cargado):
        for producto in cargado.query(ProductoCanonico):
            if producto.sku_interno.startswith("TK-REV-"):
                assert float(producto.quality_score) == pytest.approx(0.85, abs=1e-3)
                continue
            esperada = CALIDAD_POR_NIVEL[Nivel(producto.nivel)]
            assert float(producto.quality_score) == pytest.approx(esperada, abs=1e-3)

    def test_solo_lleva_personaje_el_concepto_que_lo_admite(self, cargado):
        admiten = {c.id for c in cargado.query(Concepto) if c.admite_personaje}
        del_corpus_que_admiten = [
            c for c in cargado.query(Concepto) if c.admite_personaje and del_corpus(c.codigo)
        ]
        assert len(del_corpus_que_admiten) == CONCEPTOS_CON_PERSONAJE_ESPERADOS
        for producto in cargado.query(ProductoCanonico):
            if producto.personaje:
                assert producto.concepto_id in admiten

    def test_hay_productos_con_personaje_de_verdad(self, cargado):
        con_personaje = [p for p in cargado.query(ProductoCanonico) if p.personaje]
        assert len(con_personaje) >= 20
        assert {p.nivel for p in con_personaje} <= {n.value for n in Nivel}
