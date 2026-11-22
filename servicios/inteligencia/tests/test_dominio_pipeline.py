from __future__ import annotations

from dataclasses import replace

from tukit_inteligencia.dominio.pipeline import (
    _anclar_kits,
    _personaje_pedido,
    clave_de_hijo,
    estado_desde_emparejamiento,
    inyectar_personaje_fan,
    personajes_de_los_hijos,
    personajes_por_hijo,
)
from tukit_inteligencia.modelos import EstadoResolucion, PerfilKit
from tukit_inteligencia.optimizador import Candidato, KitArmado, LineaKit, consolidar


class TestEstadoDesdeEmparejamiento:
    def test_reconocido_sin_opciones_es_hueco_no_sin_match(self):
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
    return KitArmado(
        perfil=perfil,
        total_cop=2000,
        objetivos={},
        lineas=(_linea("C001", 1000), _linea("C086", 1000)),
    )


PREFS_FAN = {"personaje_por_hijo": {"hijo-1": ["spiderman"]}, "pesos": {"personaje": 1}}


class TestInyectarPersonajeFan:
    def test_solo_toca_el_fan_y_pone_el_producto_de_personaje(self):
        swaps = {"C086": {"sku": "SPIDEY-MALETA", "personaje": "spiderman", "precio_desde": 5000}}
        kits = [_kit(PerfilKit.AHORRADOR.value), _kit(PerfilKit.FAN.value)]
        r = inyectar_personaje_fan(kits, {"hijo-1": swaps}, PREFS_FAN)

        ahorrador = next(k for k in r if k.perfil == PerfilKit.AHORRADOR.value)
        fan = next(k for k in r if k.perfil == PerfilKit.FAN.value)
        assert ahorrador.lineas[1].elegido.sku == "NEUTRAL-C086"
        maleta = next(li for li in fan.lineas if li.concepto_codigo == "C086")
        assert maleta.elegido.sku == "SPIDEY-MALETA"
        assert maleta.elegido.personaje == "spiderman"
        assert maleta.subtotal_cop == 5000
        assert fan.total_cop == 6000
        assert fan.objetivos["costo"] == 6000

    def test_veredicto_de_presupuesto_usa_el_precio_verdadero(self):
        swaps = {"C086": {"sku": "SPIDEY-MALETA", "personaje": "spiderman", "precio_desde": 5000}}
        prefs = {**PREFS_FAN, "presupuesto_por_hijo": 3000}
        r = inyectar_personaje_fan([_kit(PerfilKit.FAN.value)], {"hijo-1": swaps}, prefs)
        fan = next(k for k in r if k.perfil == PerfilKit.FAN.value)
        assert fan.total_cop == 6000
        assert fan.recomendado is True
        assert fan.dentro_de_presupuesto is False

    def test_no_duplica_el_cobro_cuando_dos_hermanos_comparten_un_ancla(self):
        fan = KitArmado(
            perfil=PerfilKit.FAN.value,
            total_cop=5000,
            objetivos={},
            lineas=(
                _linea("C086", 5000, hijo="ana", orden=1, empaque=2, unidades=1, subtotal=5000),
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
        r = inyectar_personaje_fan([fan], {"ana": swaps, "leo": swaps}, PREFS_FAN)
        fan2 = next(k for k in r if k.perfil == PerfilKit.FAN.value)

        assert fan2.total_cop == 5000
        comprables = [li for li in fan2.lineas if not li.informativa]
        assert sum(li.unidades_a_comprar for li in comprables) == 1
        assert all(li.elegido.sku == "SPIDEY-MALETA" for li in comprables)

    def test_sin_swaps_devuelve_los_kits_intactos(self):
        kits = [_kit(PerfilKit.FAN.value)]
        assert inyectar_personaje_fan(kits, {}, PREFS_FAN) is kits


def _linea_cuaderno(orden: int, texto: str, impuestos: dict, *, hijo: str = "hijo-1") -> LineaKit:
    base = _linea("C001", 8000, hijo=hijo, orden=orden)
    return replace(base, descripcion=texto, atributos_impuestos=impuestos)


SPIDEY_CUADERNO = {
    "sku": "TK-C001-CON-SPIDERMAN",
    "nombre": "Cuaderno Argollado Multimaterias Spiderman",
    "personaje": "spiderman",
    "precio_desde": 36900,
    "atributos": {"encuadernacion": "argollado", "materias": "multiple", "rayado": "cuadriculado"},
}


class TestElFanNoRepiteElMismoPersonaje:
    def _fan_con_cuadernos(self, renglones):
        lineas = tuple(_linea_cuaderno(i + 1, t, imp) for i, (t, imp) in enumerate(renglones))
        kit = KitArmado(perfil=PerfilKit.FAN.value, total_cop=0, objetivos={}, lineas=lineas)
        r = inyectar_personaje_fan([kit], {"hijo-1": {"C001": SPIDEY_CUADERNO}}, PREFS_FAN)
        return next(k for k in r if k.perfil == PerfilKit.FAN.value)

    def test_el_mismo_producto_va_en_un_solo_renglon_de_cuaderno(self):
        fan = self._fan_con_cuadernos(
            [
                ("cuaderno cuadriculado 100 hojas", {"rayado": "cuadriculado"}),
                ("cuaderno cuadriculado grande", {"rayado": "cuadriculado"}),
                ("cuaderno argollado grande", {"encuadernacion": "argollado"}),
                ("cuaderno cuadriculado 50 hojas", {"rayado": "cuadriculado"}),
            ]
        )
        con_personaje = [li for li in fan.lineas if li.elegido.sku == SPIDEY_CUADERNO["sku"]]
        assert len(con_personaje) == 1
        assert sum(1 for li in fan.lineas if li.elegido.sku == "NEUTRAL-C001") == 3

    def test_un_argollado_no_se_pone_donde_el_colegio_pidio_cosido(self):
        fan = self._fan_con_cuadernos(
            [
                ("cuaderno cosido 100 hojas", {"encuadernacion": "cosido"}),
                ("cuaderno argollado 100 hojas", {"encuadernacion": "argollado"}),
            ]
        )
        por_texto = {li.descripcion: li.elegido.sku for li in fan.lineas}
        assert por_texto["cuaderno cosido 100 hojas"] == "NEUTRAL-C001"
        assert por_texto["cuaderno argollado 100 hojas"] == SPIDEY_CUADERNO["sku"]

    def test_si_todos_piden_cosido_el_fan_no_mete_el_argollado(self):
        fan = self._fan_con_cuadernos(
            [
                ("cuaderno cosido 100 hojas", {"encuadernacion": "cosido"}),
                ("cuaderno cosido grande", {"encuadernacion": "cosido"}),
            ]
        )
        assert all(li.elegido.sku == "NEUTRAL-C001" for li in fan.lineas)

    def test_un_renglon_que_pide_surtido_puede_repetir(self):
        fan = self._fan_con_cuadernos(
            [
                ("cuaderno cuadriculado", {"rayado": "cuadriculado"}),
                ("cuadernos surtidos", {}),
            ]
        )
        assert all(li.elegido.sku == SPIDEY_CUADERNO["sku"] for li in fan.lineas)

    def test_cada_hermano_conserva_su_propio_personaje(self):
        lineas = (
            _linea_cuaderno(1, "cuaderno", {}, hijo="ana"),
            _linea_cuaderno(2, "cuaderno 2", {}, hijo="ana"),
            _linea_cuaderno(1, "cuaderno", {}, hijo="leo"),
        )
        kit = KitArmado(perfil=PerfilKit.FAN.value, total_cop=0, objetivos={}, lineas=lineas)
        swaps = {"C001": SPIDEY_CUADERNO}
        fan = inyectar_personaje_fan([kit], {"ana": swaps, "leo": swaps}, PREFS_FAN)[0]
        con = [(li.hijo, li.orden) for li in fan.lineas if li.elegido.sku == SPIDEY_CUADERNO["sku"]]
        assert sorted(con) == [("ana", 1), ("leo", 1)]


def _producto(personaje: str, *, empaque: int = 1) -> dict:
    return {
        "sku": f"TK-C001-{personaje.upper()}",
        "nombre": f"Cuaderno {personaje}",
        "personaje": personaje,
        "precio_desde": 9000,
        "unidades_por_empaque": empaque,
    }


def _fan_dos_hijos(*, empaque: int = 1) -> KitArmado:
    lineas = (
        replace(_linea("C001", 4000, hijo="hijo-1", orden=1, empaque=empaque), cantidad_pedida=1),
        replace(_linea("C001", 4000, hijo="hijo-2", orden=1, empaque=empaque), cantidad_pedida=1),
    )
    return KitArmado(perfil=PerfilKit.FAN.value, total_cop=8000, objetivos={}, lineas=lineas)


PREFS_DOS = {"personaje_por_hijo": {"hijo-1": ["spiderman"], "hijo-2": ["frozen"]}}


class TestSwapsPorHijo:
    def test_dos_hijos_cada_uno_recibe_su_personaje(self):
        swaps = {"hijo-1": {"C001": _producto("spiderman")}, "hijo-2": {"C001": _producto("frozen")}}
        fan = inyectar_personaje_fan([_fan_dos_hijos()], swaps, PREFS_DOS)[0]
        por_hijo = {li.hijo: li.elegido.sku for li in fan.lineas}
        assert por_hijo == {"hijo-1": "TK-C001-SPIDERMAN", "hijo-2": "TK-C001-FROZEN"}

    def test_mismo_personaje_consolida_una_compra(self):
        producto = _producto("spiderman", empaque=2)
        swaps = {"hijo-1": {"C001": producto}, "hijo-2": {"C001": producto}}
        prefs = {"personaje_por_hijo": {"hijo-1": ["spiderman"], "hijo-2": ["spiderman"]}}
        fan = inyectar_personaje_fan([_fan_dos_hijos(empaque=2)], swaps, prefs)[0]
        assert [li.unidades_a_comprar for li in fan.lineas] == [1, 0]
        assert fan.total_cop == 9000
        assert len(fan.consolidaciones) == 1
        assert fan.consolidaciones[0]["sku"] == "TK-C001-SPIDERMAN"

    def test_personajes_distintos_no_se_consolidan(self):
        swaps = {
            "hijo-1": {"C001": _producto("spiderman", empaque=2)},
            "hijo-2": {"C001": _producto("frozen", empaque=2)},
        }
        fan = inyectar_personaje_fan([_fan_dos_hijos(empaque=2)], swaps, PREFS_DOS)[0]
        assert fan.consolidaciones == ()
        assert [li.unidades_a_comprar for li in fan.lineas] == [1, 1]
        assert fan.total_cop == 18000

    def test_hijo_sin_personaje_queda_neutro(self):
        swaps = {"hijo-1": {"C001": _producto("spiderman")}}
        prefs = {"personaje_por_hijo": {"hijo-1": ["spiderman"]}}
        fan = inyectar_personaje_fan([_fan_dos_hijos()], swaps, prefs)[0]
        por_hijo = {li.hijo: li.elegido.sku for li in fan.lineas}
        assert por_hijo == {"hijo-1": "TK-C001-SPIDERMAN", "hijo-2": "NEUTRAL-C001"}


class TestPersonajesPorHijo:
    def test_primer_personaje_de_cada_hijo_y_omite_vacios(self):
        prefs = {"personaje_por_hijo": {"hijo-1": ["Spiderman", "cars"], "hijo-2": [], "hijo-3": ["frozen"]}}
        assert personajes_por_hijo(prefs) == {"hijo-1": "Spiderman", "hijo-3": "frozen"}
        assert personajes_por_hijo({}) == {}

    def test_clave_exacta_gana(self):
        assert personajes_de_los_hijos(PREFS_DOS, ["hijo-1", "hijo-2"]) == {
            "hijo-1": "spiderman",
            "hijo-2": "frozen",
        }

    def test_sin_clave_que_case_se_une_por_orden_si_cuadra(self):
        assert personajes_de_los_hijos(PREFS_DOS, ["a", "b"]) == {"a": "spiderman", "b": "frozen"}

    def test_preferencias_dispersas_dejan_neutral(self):
        prefs = {"personaje_por_hijo": {"hijo-2": ["frozen"]}}
        assert clave_de_hijo(prefs, "hijo-1", ["hijo-1"]) is None
        assert personajes_de_los_hijos(prefs, ["hijo-1"]) == {}
        assert personajes_de_los_hijos({"personaje_por_hijo": {"hijo-1": ["x"]}}, ["hijo-0"]) == {}
        assert personajes_de_los_hijos(prefs, ["a", "b"]) == {}

    def test_con_alguna_clave_exacta_no_se_adivina_por_orden(self):
        assert clave_de_hijo(PREFS_DOS, "otro", ["hijo-1", "otro"]) is None


class TestHermanoNeutralConEmpaque:
    def test_el_neutral_conserva_su_sku_y_la_compra_se_rehace(self):
        armado = _fan_dos_hijos(empaque=2)
        lineas, consolidaciones = consolidar(armado.lineas)
        assert [li.unidades_a_comprar for li in lineas] == [1, 0]
        fan = replace(armado, lineas=lineas, consolidaciones=consolidaciones)

        swaps = {"hijo-1": {"C001": _producto("spiderman", empaque=2)}}
        prefs = {"personaje_por_hijo": {"hijo-1": ["spiderman"]}}
        r = inyectar_personaje_fan([fan], swaps, prefs)[0]

        por_hijo = {li.hijo: li for li in r.lineas}
        assert por_hijo["hijo-1"].elegido.sku == "TK-C001-SPIDERMAN"
        assert por_hijo["hijo-2"].elegido.sku == "NEUTRAL-C001"
        assert [li.unidades_a_comprar for li in r.lineas] == [1, 1]
        assert r.consolidaciones == ()
        assert por_hijo["hijo-2"].mensaje is None
        assert r.total_cop == 9000 + 4000


SPIDEY_MULTI = {
    "sku": "TK-C001-CON-SPIDERMAN",
    "nombre": "Cuaderno Argollado Multimaterias Spiderman",
    "personaje": "spiderman",
    "precio_desde": 36900,
    "atributos": {"materias": "multiple", "encuadernacion": "argollado"},
}
SPIDEY_COSIDO = {
    "sku": "TK-C001-COS-SPIDERMAN",
    "nombre": "Cuaderno Cosido 100 hojas Spiderman",
    "personaje": "spiderman",
    "precio_desde": 41000,
    "atributos": {"materias": "1", "encuadernacion": "cosido", "hojas": "100"},
}
PIDE_COSIDO = {"materias": "1", "encuadernacion": "cosido", "hojas": "100"}


def _cartuchera(personaje: str) -> dict:
    return {
        "sku": f"TK-C009-ECO-{personaje.upper()}",
        "nombre": f"Cartuchera {personaje}",
        "personaje": personaje,
        "precio_desde": 15000,
    }


def _fan(lineas) -> KitArmado:
    return KitArmado(perfil=PerfilKit.FAN.value, total_cop=0, objetivos={}, lineas=tuple(lineas))


PREFS_HERMANOS = {"personaje_por_hijo": {"hijo-1": ["spiderman"], "hijo-2": ["minnie"]}}


class TestHermanosConVariantes:
    def test_hermanos_cada_uno_su_personaje_con_variantes(self):
        lineas = [
            _linea_cuaderno(1, "cuaderno cosido 100 hojas", PIDE_COSIDO, hijo="hijo-1"),
            _linea_cuaderno(2, "cuaderno cosido 100 hojas", PIDE_COSIDO, hijo="hijo-1"),
            _linea("C009", 9000, hijo="hijo-2", orden=1),
        ]
        swaps = {
            "hijo-1": {"C001": [SPIDEY_MULTI, SPIDEY_COSIDO]},
            "hijo-2": {"C009": [_cartuchera("minnie")]},
        }
        fan = inyectar_personaje_fan([_fan(lineas)], swaps, PREFS_HERMANOS)[0]
        skus_h1 = [li.elegido.sku for li in fan.lineas if li.hijo == "hijo-1"]
        assert SPIDEY_COSIDO["sku"] in skus_h1
        assert SPIDEY_MULTI["sku"] not in skus_h1
        h2 = [li for li in fan.lineas if li.hijo == "hijo-2"]
        assert [li.elegido.sku for li in h2] == ["TK-C009-ECO-MINNIE"]
        assert all(li.elegido.personaje != "spiderman" for li in h2)
        assert "personaje_sin_encaje" not in fan.objetivos

    def test_mismo_personaje_dos_hijos_sigue_consolidando(self):
        cartuchera = {**_cartuchera("spiderman"), "unidades_por_empaque": 2}
        lineas = [
            _linea("C009", 9000, hijo="hijo-1", orden=1, empaque=2),
            _linea("C009", 9000, hijo="hijo-2", orden=1, empaque=2),
        ]
        swaps = {"hijo-1": {"C009": [cartuchera]}, "hijo-2": {"C009": [cartuchera]}}
        prefs = {"personaje_por_hijo": {"hijo-1": ["spiderman"], "hijo-2": ["spiderman"]}}
        fan = inyectar_personaje_fan([_fan(lineas)], swaps, prefs)[0]
        grupo = next(c for c in fan.consolidaciones if c["sku"] == cartuchera["sku"])
        assert grupo["hijos"] == ["hijo-1", "hijo-2"]

    def test_hijo_sin_personaje_queda_neutral(self):
        lineas = [
            _linea("C009", 9000, hijo="hijo-1", orden=1),
            _linea("C009", 9000, hijo="hijo-2", orden=1),
            _linea_cuaderno(2, "cuaderno", {}, hijo="hijo-2"),
        ]
        swaps = {"hijo-1": {"C009": [_cartuchera("spiderman")]}}
        prefs = {"personaje_por_hijo": {"hijo-1": ["spiderman"]}}
        fan = inyectar_personaje_fan([_fan(lineas)], swaps, prefs)[0]
        assert all(
            li.elegido is None or li.elegido.personaje is None for li in fan.lineas if li.hijo == "hijo-2"
        )

    def test_ancla_sin_encaje_queda_registrada(self):
        lineas = [
            _linea_cuaderno(1, "cuaderno cosido 100 hojas", PIDE_COSIDO, hijo="hijo-1"),
            _linea_cuaderno(2, "cuaderno cosido 100 hojas", PIDE_COSIDO, hijo="hijo-1"),
            _linea("C009", 9000, hijo="hijo-1", orden=3),
        ]
        swaps = {"hijo-1": {"C001": [SPIDEY_MULTI], "C009": [_cartuchera("spiderman")]}}
        fan = inyectar_personaje_fan([_fan(lineas)], swaps, PREFS_FAN)[0]
        assert fan.objetivos["personaje_sin_encaje"] == [
            {"hijo": "hijo-1", "concepto": "C001", "personaje": "spiderman"}
        ]
        assert all(li.elegido.sku == "NEUTRAL-C001" for li in fan.lineas if li.concepto_codigo == "C001")
