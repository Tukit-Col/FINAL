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


def _linea(
    concepto: str,
    precio: int | None,
    *,
    hijo: str = "hijo-1",
    orden: int = 1,
    empaque: int = 1,
    unidades: int | None = None,
    subtotal: int | None = None,
) -> LineaKit:
    elegido = (
        None
        if precio is None
        else Candidato(
            sku=f"NEUTRAL-{concepto}",
            nombre="neutral",
            nivel="confiable",
            precio_cop=precio,
            unidades_por_empaque=empaque,
        )
    )
    comprar = unidades if unidades is not None else (1 if precio is not None else 0)
    sub = subtotal if subtotal is not None else (precio if precio is not None else None)
    return LineaKit(
        hijo=hijo,
        orden=orden,
        descripcion=concepto,
        tipo="util",
        estado_resolucion=EstadoResolucion.RESUELTO_AUTO.value,
        cantidad_pedida=1,
        unidad_base="unidad",
        unidades_por_empaque=empaque,
        unidades_a_comprar=comprar,
        informativa=False,
        elegido=elegido,
        precio_unitario_cop=precio,
        subtotal_cop=sub,
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


PREFS_FAN = {"personaje_por_hijo": {"hijo-1": ["spiderman"]}, "pesos": {"personaje": 1}}


class TestInyectarPersonajeFan:
    def test_solo_toca_el_fan_y_pone_el_producto_de_personaje(self):
        # El catalogo surte la maleta spiderman a 5000 (via `precio_desde`);
        # el cuaderno spiderman no lo surte, asi que su ancla queda neutral.
        swaps = {"C086": {"sku": "SPIDEY-MALETA", "personaje": "spiderman", "precio_desde": 5000}}
        kits = [_kit(PerfilKit.AHORRADOR.value), _kit(PerfilKit.FAN.value)]
        r = inyectar_personaje_fan(kits, swaps, PREFS_FAN)

        ahorrador = next(k for k in r if k.perfil == PerfilKit.AHORRADOR.value)
        fan = next(k for k in r if k.perfil == PerfilKit.FAN.value)
        # El ahorrador no se toca.
        assert ahorrador.lineas[1].elegido.sku == "NEUTRAL-C086"
        # El Fan trae el producto de personaje en la maleta, con su precio.
        maleta = next(li for li in fan.lineas if li.concepto_codigo == "C086")
        assert maleta.elegido.sku == "SPIDEY-MALETA"
        assert maleta.elegido.personaje == "spiderman"
        assert maleta.subtotal_cop == 5000
        # El total se rehace: cuaderno 1000 + maleta 5000.
        assert fan.total_cop == 6000
        # Y los objetivos tambien: `costo` no puede quedar en el viejo 2000.
        assert fan.objetivos["costo"] == 6000

    def test_veredicto_de_presupuesto_usa_el_precio_verdadero(self):
        # Presupuesto 3000: el Fan neutral (2000) cabria, pero con spiderman
        # (6000) NO. El swap ocurre despues de recomendar, asi que el veredicto
        # se tiene que recomputar o mentiria diciendo que cabe.
        swaps = {"C086": {"sku": "SPIDEY-MALETA", "personaje": "spiderman", "precio_desde": 5000}}
        prefs = {**PREFS_FAN, "presupuesto_por_hijo": 3000}
        r = inyectar_personaje_fan([_kit(PerfilKit.FAN.value)], swaps, prefs)
        fan = next(k for k in r if k.perfil == PerfilKit.FAN.value)
        assert fan.total_cop == 6000
        # El unico kit no cabe: recomendar lo marca fuera de presupuesto.
        assert fan.recomendado is True
        assert fan.dentro_de_presupuesto is False

    def test_no_duplica_el_cobro_cuando_dos_hermanos_comparten_un_ancla(self):
        # Dos hermanos piden la misma maleta (C086), empaque de 2: un solo
        # empaque alcanza para los dos. `armar_los_tres` ya consolido sobre el
        # sku neutral (una linea con 1 unidad, la otra en 0). Al meter spiderman
        # (empaque 2, 5000) el kit debe seguir cobrando UN empaque, no dos.
        fan = KitArmado(
            perfil=PerfilKit.FAN.value,
            total_cop=5000,
            objetivos={},
            lineas=(
                # ana: absorbe el empaque conjunto (1 unidad de empaque=2).
                _linea("C086", 5000, hijo="ana", orden=1, empaque=2, unidades=1, subtotal=5000),
                # leo: consolidado, en cero.
                _linea("C086", 5000, hijo="leo", orden=1, empaque=2, unidades=0, subtotal=0),
            ),
            consolidaciones=({"sku": "NEUTRAL-C086", "hijos": ["ana", "leo"]},),
        )
        swaps = {
            "C086": {
                "sku": "SPIDEY-MALETA",
                "personaje": "spiderman",
                "precio_desde": 5000,
                "unidades_por_empaque": 2,
            }
        }
        r = inyectar_personaje_fan([fan], swaps, PREFS_FAN)
        fan2 = next(k for k in r if k.perfil == PerfilKit.FAN.value)

        # Un solo empaque de spiderman cubre a los dos: total = 5000, no 10000.
        assert fan2.total_cop == 5000
        comprables = [li for li in fan2.lineas if not li.informativa]
        assert sum(li.unidades_a_comprar for li in comprables) == 1
        # Y las dos lineas ya traen el producto de personaje.
        assert all(li.elegido.sku == "SPIDEY-MALETA" for li in comprables)

    def test_sin_swaps_devuelve_los_kits_intactos(self):
        kits = [_kit(PerfilKit.FAN.value)]
        assert inyectar_personaje_fan(kits, {}, PREFS_FAN) is kits
