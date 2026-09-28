"""Los guards e shapers puros de la revision de listas (dominio/listas.py).

`_exigir_sin_revisar` y `_cuidar_invariantes` son las puertas del gate de
revision: preservan las condiciones de `raise` exactas (404/409/422) que fijan
el contrato. `_item_publico` y `_pagina_percepcion` son shapers puros. Aqui se
prueban sin motor ni HTTP, con `assert`.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from tukit_catalogo.dominio.listas import (
    _cuidar_invariantes,
    _exigir_sin_revisar,
    _item_publico,
    _pagina_percepcion,
)
from tukit_comun.http import ErrorDominio


def test_exigir_sin_revisar_inexistente_es_404():
    with pytest.raises(ErrorDominio) as e:
        _exigir_sin_revisar(None)
    assert e.value.estado == 404 and e.value.error == "version_no_existe"


def test_exigir_sin_revisar_ya_revisada_es_409():
    fila = SimpleNamespace(revisada_en="2026-01-01")
    with pytest.raises(ErrorDominio) as e:
        _exigir_sin_revisar(fila)
    assert e.value.estado == 409 and e.value.error == "lista_ya_revisada"


def test_exigir_sin_revisar_abierta_pasa():
    _exigir_sin_revisar(SimpleNamespace(revisada_en=None))  # no alza


def test_invariante_sin_concepto_exige_revision():
    with pytest.raises(ErrorDominio) as e:
        _cuidar_invariantes(None, False, "mercado_abierto", None)
    assert e.value.error == "renglon_sin_concepto_va_a_revision" and e.value.estado == 422


def test_invariante_no_surtible_sin_instruccion():
    with pytest.raises(ErrorDominio) as e:
        _cuidar_invariantes("cid", True, "colegio_directo", None)
    assert e.value.error == "no_surtible_sin_instruccion" and e.value.estado == 422


def test_invariante_no_surtible_con_instruccion_pasa():
    _cuidar_invariantes("cid", True, "colegio_directo", "Se compra en el colegio")


def test_invariante_surtible_sin_instruccion_pasa():
    _cuidar_invariantes("cid", True, "mercado_abierto", None)


def test_pagina_percepcion_lista_de_items_se_aplana_a_texto():
    p = {"pagina": 2, "crudo": [{"descripcion": "Cuaderno", "cantidad": 3}, {"descripcion": "Lapiz"}]}
    r = _pagina_percepcion(p)
    assert r["pagina"] == 2 and r["crudo"] == "3 Cuaderno\nLapiz"


def test_pagina_percepcion_crudo_ya_texto_se_respeta():
    assert _pagina_percepcion({"pagina": 1, "crudo": "hola"})["crudo"] == "hola"


def test_pagina_percepcion_no_dict_se_coacciona():
    assert _pagina_percepcion("x")["crudo"] == "x"


def test_item_publico_arma_concepto_solo_si_hay_codigo():
    base = dict(
        id="i1", orden=1, texto_original="t", cantidad=2, unidad="unidad",
        tipo_item="util", modo_adquisicion="mercado_abierto", instruccion_colegio=None,
        url_externa=None, atributos={"x": 1}, requiere_revision=False,
        concepto_codigo="C001", concepto_nombre="Cuaderno",
    )
    r = _item_publico(SimpleNamespace(**base))
    assert r["concepto"] == {"codigo": "C001", "nombre": "Cuaderno"}
    base["concepto_codigo"] = None
    assert _item_publico(SimpleNamespace(**base))["concepto"] is None
