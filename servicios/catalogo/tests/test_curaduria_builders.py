"""Los builders puros de propuesta que HTTP y el CLI comparten.

`agregar_util`/`agregar_libro` construian su dict inline y lo encadenaban con
`_encolar` + `resolver`. La SPA necesita ese MISMO dict para encolar sin
aprobar (dos pasos), asi que el dict se extrae a una funcion pura --sin I/O, sin
motor-- que las dos superficies llaman. Aqui se prueba que el dict que sale
conserva lo que importa: precio en centavos, puntaje, origen y referencia.
"""

from __future__ import annotations

import uuid

from tukit_catalogo import tiendas
from tukit_catalogo.dominio.propuesta import (
    _ean_valido,
    construir_propuesta_libro,
    construir_propuesta_util,
)


def test_util_conserva_precio_en_centavos_y_puntaje():
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
    assert d["precio_centavos"] == 500000 and d["puntaje"] == 0.6
    assert d["origen"] == "manual" and d["version_lista_id"] is None
    assert d["concepto_id"] == cid and d["referencia_externa"] == "SKU1"


def test_libro_usa_isbn_como_referencia_y_puntaje_0_9():
    cid = uuid.uuid4()
    tid = uuid.uuid4()
    d = construir_propuesta_libro(
        cid, "Libro", "panamericana", tid, "9781234567897", "El Principito", 30000, "confiable"
    )
    assert d["referencia_externa"] == "9781234567897" and d["puntaje"] == 0.9
    assert d["especificaciones"] == {"isbn": "9781234567897"} and d["precio_centavos"] == 3000000


def test_ean_valido_solo_pasa_longitudes_de_codigo_de_barras():
    assert _ean_valido("9781234567897") == "9781234567897"  # 13
    assert _ean_valido("12345678") == "12345678"  # 8
    assert _ean_valido("  40012349  ") == "40012349"  # recorta
    assert _ean_valido("123") is None  # muy corto
    assert _ean_valido("abc12345") is None  # no digito
    assert _ean_valido(None) is None


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
    assert a["id"] == b["id"]  # derivado de (slug, sku), no aleatorio
