"""Los helpers puros del pipeline de resolucion, sin motor ni fixtures.

Son las decisiones que no tocan la base: traducir el vocabulario del catalogo a
un `EstadoResolucion`, normalizar un renglon crudo a una demanda, anclar el
personaje pedido al tope del kit. Se prueban con `assert` porque no tienen I/O:
el que sean puras es justo lo que ADR 0019 pide para que vivan en `dominio/`.
"""

from __future__ import annotations

from tukit_inteligencia.dominio.pipeline import (
    _anclar_kits,
    _personaje_pedido,
    estado_desde_emparejamiento,
)
from tukit_inteligencia.modelos import EstadoResolucion


class TestEstadoDesdeEmparejamiento:
    def test_reconocido_sin_opciones_es_hueco_no_sin_match(self):
        # El catalogo entendio el concepto pero no tiene producto: es "te
        # entendi y no lo tengo", no "no te entendi". El contrato los separa.
        r = estado_desde_emparejamiento({"estado": "reconocido", "opciones": []}, 0.75)
        assert r == EstadoResolucion.HUECO_CATALOGO.value

    def test_reconocido_por_encima_del_umbral_es_auto(self):
        r = estado_desde_emparejamiento(
            {"estado": "reconocido", "opciones": [{}], "parecido": 0.9}, 0.75
        )
        assert r == EstadoResolucion.RESUELTO_AUTO.value

    def test_reconocido_por_debajo_del_umbral_es_ambiguo(self):
        r = estado_desde_emparejamiento(
            {"estado": "reconocido", "opciones": [{}], "parecido": 0.5}, 0.75
        )
        assert r == EstadoResolucion.AMBIGUO.value

    def test_abstencion_es_hueco_catalogo(self):
        r = estado_desde_emparejamiento({"estado": "abstencion", "opciones": [{}]}, 0.75)
        assert r == EstadoResolucion.HUECO_CATALOGO.value

    def test_desconocido_es_sin_match(self):
        assert (
            estado_desde_emparejamiento({"estado": "otra_cosa"}, 0.75)
            == EstadoResolucion.SIN_MATCH.value
        )


class TestPersonajePedido:
    def test_toma_el_primero_declarado(self):
        prefs = {"personaje_por_hijo": {"ana": ["bluey"], "leo": ["spiderman"]}}
        assert _personaje_pedido(prefs) in {"bluey", "spiderman"}

    def test_sin_personaje_es_none(self):
        assert _personaje_pedido({}) is None
        assert _personaje_pedido({"personaje_por_hijo": {"ana": []}}) is None


class TestAnclarKits:
    def test_sin_personaje_devuelve_los_mismos_kits(self):
        kits = [object(), object()]
        assert _anclar_kits(kits, {}) is kits
