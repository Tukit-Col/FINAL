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
    inyectar_personaje_fan,
)
from tukit_inteligencia.modelos import EstadoResolucion
from tukit_inteligencia.optimizador import Candidato, KitArmado, LineaKit, PerfilKit


class TestEstadoDesdeEmparejamiento:
    def test_reconocido_sin_opciones_es_hueco_no_sin_match(self):
        # El catalogo entendio el concepto pero no tiene producto: es "te
        # entendi y no lo tengo", no "no te entendi". El contrato los separa.
        r = estado_desde_emparejamiento({"estado": "reconocido", "opciones": []}, 0.75)
        assert r == EstadoResolucion.HUECO_CATALOGO.value

    def test_reconocido_por_encima_del_umbral_es_auto(self):
        r = estado_desde_emparejamiento({"estado": "reconocido", "opciones": [{}], "parecido": 0.9}, 0.75)
        assert r == EstadoResolucion.RESUELTO_AUTO.value

    def test_reconocido_por_debajo_del_umbral_es_ambiguo(self):
        r = estado_desde_emparejamiento({"estado": "reconocido", "opciones": [{}], "parecido": 0.5}, 0.75)
        assert r == EstadoResolucion.AMBIGUO.value

    def test_abstencion_es_hueco_catalogo(self):
        r = estado_desde_emparejamiento({"estado": "abstencion", "opciones": [{}]}, 0.75)
        assert r == EstadoResolucion.HUECO_CATALOGO.value

    def test_desconocido_es_sin_match(self):
        assert estado_desde_emparejamiento({"estado": "otra_cosa"}, 0.75) == EstadoResolucion.SIN_MATCH.value


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


def _linea(concepto: str, precio: int | None) -> LineaKit:
    elegido = (
        None
        if precio is None
        else Candidato(sku=f"NEUTRAL-{concepto}", nombre="neutral", nivel="confiable", precio_cop=precio)
    )
    return LineaKit(
        hijo="hijo-1",
        orden=1,
        descripcion=concepto,
        tipo="util",
        estado_resolucion=EstadoResolucion.RESUELTO_AUTO.value,
        cantidad_pedida=1,
        unidad_base="unidad",
        unidades_por_empaque=1,
        unidades_a_comprar=1 if precio is not None else 0,
        informativa=False,
        elegido=elegido,
        precio_unitario_cop=precio,
        subtotal_cop=precio,
        concepto_codigo=concepto,
    )


def _kit(perfil: str) -> KitArmado:
    # C001 cuaderno + C086 maleta, ambos con producto neutral de 1000.
    return KitArmado(
        perfil=perfil,
        total_cop=2000,
        objetivos={},
        lineas=(_linea("C001", 1000), _linea("C086", 1000)),
    )


class TestInyectarPersonajeFan:
    def test_solo_toca_el_fan_y_pone_el_producto_de_personaje(self):
        # El catalogo surte la maleta spiderman a 5000 (via `precio_desde`);
        # el cuaderno spiderman no lo surte, asi que su ancla queda neutral.
        swaps = {"C086": {"sku": "SPIDEY-MALETA", "personaje": "spiderman", "precio_desde": 5000}}
        kits = [_kit(PerfilKit.AHORRADOR.value), _kit(PerfilKit.FAN.value)]
        r = inyectar_personaje_fan(kits, swaps)

        ahorrador, fan = r
        # El ahorrador no se toca.
        assert ahorrador.lineas[1].elegido.sku == "NEUTRAL-C086"
        # El Fan trae el producto de personaje en la maleta, con su precio.
        maleta = next(li for li in fan.lineas if li.concepto_codigo == "C086")
        assert maleta.elegido.sku == "SPIDEY-MALETA"
        assert maleta.elegido.personaje == "spiderman"
        assert maleta.subtotal_cop == 5000
        # Y el total se rehace: cuaderno 1000 + maleta 5000.
        assert fan.total_cop == 6000

    def test_sin_swaps_devuelve_los_kits_intactos(self):
        kits = [_kit(PerfilKit.FAN.value)]
        assert inyectar_personaje_fan(kits, {}) is kits
