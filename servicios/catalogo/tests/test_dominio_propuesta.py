from __future__ import annotations

import uuid

import pytest
from tukit_catalogo import descubrir, tiendas
from tukit_catalogo.dominio.propuesta import (
    _ean_valido,
    construir_propuesta_libro,
    construir_propuesta_util,
)


def test_util_conserva_precio_en_centavos_y_puntaje_de_propuesta():
    cid = uuid.uuid4()
    tid = uuid.uuid4()
    o = tiendas.Oferta(
        tienda="exito",
        nombre="Cuaderno 100h",
        precio_cop=5000,
        disponible=True,
        imagen_url=None,
        url="http://x",
        sku="SKU1",
        ean=None,
        marca="Norma",
        especificaciones={},
    )
    d = construir_propuesta_util(cid, "Cuaderno", "exito", tid, o, "confiable")
    assert d["precio_centavos"] == o.precio_cop * 100
    assert 0 < d["puntaje"] < 1
    assert d["origen"] == "manual" and d["version_lista_id"] is None
    assert d["concepto_id"] == cid and d["referencia_externa"] == "SKU1"


def test_libro_usa_isbn_como_referencia():
    cid = uuid.uuid4()
    tid = uuid.uuid4()
    d = construir_propuesta_libro(
        cid, "Libro", "panamericana", tid, "9781234567897", "El Principito", 30000, "confiable"
    )
    assert d["referencia_externa"] == "9781234567897"
    assert d["especificaciones"] == {"isbn": "9781234567897"} and d["precio_centavos"] == 30000 * 100


def test_un_libro_por_isbn_puntua_mas_que_un_util_buscado_en_tienda():
    o = tiendas.Oferta(
        tienda="exito",
        nombre="Cuaderno 100h",
        precio_cop=5000,
        disponible=True,
        imagen_url=None,
        url="http://x",
        sku="SKU1",
        ean=None,
        marca="Norma",
        especificaciones={},
    )
    util = construir_propuesta_util(uuid.uuid4(), "Cuaderno", "exito", uuid.uuid4(), o, "confiable")
    libro = construir_propuesta_libro(
        uuid.uuid4(),
        "Libro",
        "panamericana",
        uuid.uuid4(),
        "9781234567897",
        "El Principito",
        30000,
        "confiable",
    )
    assert 0 < util["puntaje"] < libro["puntaje"] < 1


_FILTROS_EAN = pytest.mark.parametrize(
    "ean_valido", [_ean_valido, descubrir._ean_valido], ids=["propuesta", "descubrir"]
)


class TestElEanQueTraeLaTiendaSoloEntraSiEsUno:

    @_FILTROS_EAN
    @pytest.mark.parametrize("bueno", ["12345678", "123456789012", "1234567890123", "9781234567897"])
    def test_acepta_8_12_o_13_digitos(self, ean_valido, bueno):
        assert ean_valido(bueno) == bueno

    @_FILTROS_EAN
    def test_recorta_los_espacios_de_alrededor(self, ean_valido):
        assert ean_valido("  40012349  ") == "40012349"

    @_FILTROS_EAN
    @pytest.mark.parametrize(
        "malo", [None, "", "  ", "123", "SKU-4451", "12a45678", "abc12345", "12345678901234"]
    )
    def test_descarta_lo_que_no_parece_un_ean(self, ean_valido, malo):
        assert ean_valido(malo) is None


def test_id_estable_no_duplica_al_reencolar_el_mismo_candidato():
    cid, tid = uuid.uuid4(), uuid.uuid4()
    o = tiendas.Oferta(
        tienda="exito",
        nombre="Cuaderno",
        precio_cop=5000,
        disponible=True,
        imagen_url=None,
        url=None,
        sku="SKU1",
        ean=None,
        marca=None,
        especificaciones={},
    )
    a = construir_propuesta_util(cid, "Cuaderno", "exito", tid, o, "confiable")
    b = construir_propuesta_util(cid, "Cuaderno", "exito", tid, o, "confiable")
    assert a["id"] == b["id"]
