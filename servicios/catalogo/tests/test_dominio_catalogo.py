from __future__ import annotations

from types import SimpleNamespace

import pytest
from tukit_catalogo.dominio.catalogo import (
    _concepto_publico,
    _oferta_publica,
    _ordenar_ofertas,
    _producto_publico,
    _sobre,
    _validar_edicion,
    pesos,
)
from tukit_comun.http import ErrorDominio


def test_pesos_divide_por_cien_y_trunca():
    assert pesos(450000) == 4500
    assert pesos(499) == 4


def test_pesos_none_es_desconocido_no_cero():
    assert pesos(None) is None


def test_concepto_publico_normaliza_colecciones_nulas():
    fila = SimpleNamespace(
        codigo="cuaderno",
        nombre_canonico="Cuaderno",
        categoria="escritura",
        tipo_item="util",
        sinonimos=None,
        admite_personaje=1,
        atributos_discriminantes=("tamano",),
        atributos_descriptivos=None,
        frecuencia_demanda=None,
    )
    out = _concepto_publico(fila)
    assert out["nombre"] == "Cuaderno"
    assert out["sinonimos"] == []
    assert out["admite_personaje"] is True
    assert out["atributos_discriminantes"] == ["tamano"]
    assert out["atributos_descriptivos"] == []
    assert out["frecuencia_demanda"] == 0


def _fila_producto(**kw) -> SimpleNamespace:
    base = dict(
        sku_interno="TK-C001-ECO",
        ean=None,
        nombre="Cuaderno 100h",
        marca="Norma",
        nivel="economico",
        personaje=None,
        imagen_url=None,
        descripcion=None,
        es_propio=0,
        unidad_base="unidad",
        unidades_por_empaque=None,
        atributos=None,
        quality_score=0.8,
        concepto_codigo="cuaderno",
        concepto_nombre="Cuaderno",
        centavos=450000,
        tiendas=3,
    )
    base.update(kw)
    return SimpleNamespace(**base)


def test_producto_publico_expone_sku_y_precio_en_pesos():
    out = _producto_publico(_fila_producto())
    assert out["sku"] == "TK-C001-ECO"
    assert out["precio_desde"] == 4500
    assert out["tiendas"] == 3
    assert out["unidades_por_empaque"] == 1
    assert out["atributos"] == {}


def test_producto_publico_sin_precio_ni_tiendas():
    out = _producto_publico(_fila_producto(centavos=None, tiendas=None))
    assert out["precio_desde"] is None
    assert out["tiendas"] == 0


def test_oferta_publica_precio_en_pesos_y_disponible_tri_estado():
    fila = SimpleNamespace(
        slug="exito",
        tienda_nombre="Exito",
        tipo="minorista",
        url="http://x",
        disponible=None,
        valor_centavos=500000,
        vigente_desde=None,
        vigente_hasta=None,
        fuente="scraper",
        metodo_vinculacion="ean",
        confianza_vinculacion=0.9,
    )
    out = _oferta_publica(fila)
    assert out["precio"] == 5000
    assert out["disponible"] is None


def test_ordenar_ofertas_precio_primero_nulos_al_final():
    ofertas = [
        {"precio": None},
        {"precio": 3000},
        {"precio": 1000},
    ]
    assert [o["precio"] for o in _ordenar_ofertas(ofertas)] == [1000, 3000, None]


def test_sobre_lleva_total_pagina_y_la_clave_pedida():
    assert _sobre(2, 50, 130, "productos", [1, 2]) == {
        "total": 130,
        "pagina": 2,
        "por_pagina": 50,
        "productos": [1, 2],
    }


def test_validar_edicion_acepta_campos_editables_sin_tocarlos():
    cambios = {"nombre": "x", "nivel": "premium", "atributos": {"color": "rojo"}}
    assert _validar_edicion(cambios) is None
    assert cambios == {"nombre": "x", "nivel": "premium", "atributos": {"color": "rojo"}}


def test_validar_edicion_rechaza_campo_no_editable():
    with pytest.raises(ErrorDominio) as e:
        _validar_edicion({"sku": "otro"})
    assert e.value.error == "campo_no_editable"


def test_validar_edicion_rechaza_nivel_invalido():
    with pytest.raises(ErrorDominio) as e:
        _validar_edicion({"nivel": "carisimo"})
    assert e.value.error == "nivel_invalido"


def test_validar_edicion_rechaza_atributo_anidado():
    with pytest.raises(ErrorDominio) as e:
        _validar_edicion({"atributos": {"malo": ["lista"]}})
    assert e.value.error == "atributos_invalido"


def test_validar_edicion_empaque_minimo_uno():
    with pytest.raises(ErrorDominio) as e:
        _validar_edicion({"unidades_por_empaque": 0})
    assert e.value.error == "empaque_invalido"
