"""El armado de los tres kits: unidades, total honesto y recomendacion.

Las pruebas de aqui fijan lo que NO depende del algoritmo. La heuristica de
seleccion se reemplazo por NSGA-II (OE4); la aritmetica de unidades, la regla de
que lo informativo no se cobra y la regla de recomendacion salida de la encuesta
siguen valiendo despues del reemplazo —eso es lo que la mayoria de estas pruebas
defiende—. El ultimo bloque (`TestElFrenteDePareto`) es lo que si depende del
algoritmo: que el frente no lo haga peor que la heuristica y que sea
reproducible.
"""

from __future__ import annotations

import pytest
from tukit_inteligencia.optimizador import (
    Candidato,
    Renglon,
    armar_los_tres,
    consolidar,
    elegir_por_perfil,
    optimizar_frente,
    unidades_a_comprar,
)


def _candidato(sku: str, nivel: str, precio: int | None, **kw) -> Candidato:
    return Candidato(sku=sku, nombre=f"Producto {sku}", nivel=nivel, precio_cop=precio, **kw)


def _renglon(orden: int, texto: str, candidatos: tuple[Candidato, ...] = (), **kw) -> Renglon:
    return Renglon(
        hijo=kw.pop("hijo", "hijo-1"),
        orden=orden,
        texto=texto,
        tipo_item=kw.pop("tipo_item", "util"),
        modo_adquisicion=kw.pop("modo_adquisicion", "mercado_abierto"),
        cantidad=kw.pop("cantidad", 1),
        estado_resolucion=kw.pop("estado_resolucion", "RESUELTO_AUTO"),
        candidatos=candidatos,
        **kw,
    )


class TestLaCuentaDeUnidadesNoVuelveASumarCajas:
    """El defecto original: la lista pedia 12 lapices y el carrito sumaba 12
    cajas de 12. Es la razon de que `cantidad_pedida`, `unidades_por_empaque`
    y `unidades_a_comprar` sean tres numeros distintos."""

    @pytest.mark.parametrize(
        ("pedida", "empaque", "esperado"),
        [(12, 12, 1), (13, 12, 2), (1, 12, 1), (24, 12, 2), (3, 1, 3), (0, 12, 0)],
    )
    def test_es_el_techo_de_la_division(self, pedida, empaque, esperado):
        assert unidades_a_comprar(pedida, empaque) == esperado

    def test_doce_lapices_en_caja_de_doce_es_una_caja(self):
        caja = _candidato("TK-CAJA", "confiable", 18900, unidades_por_empaque=12)
        kits = armar_los_tres([_renglon(1, "12 lapices", (caja,), cantidad=12)])

        linea = kits[0].lineas[0]
        assert linea.cantidad_pedida == 12
        assert linea.unidades_por_empaque == 12
        assert linea.unidades_a_comprar == 1
        assert linea.subtotal_cop == 18900


class TestCadaPerfilEligeLoQueDice:
    CANDIDATOS = (
        _candidato("ECO", "economico", 5000),
        _candidato("CON", "confiable", 9000),
        _candidato("PRE", "premium", 15000),
        _candidato("FAN", "economico", 7000, personaje="spiderman"),
    )

    def test_ahorrador_toma_el_mas_barato(self):
        assert elegir_por_perfil(self.CANDIDATOS, "Ahorrador").sku == "ECO"

    def test_premium_toma_el_mejor_nivel_y_no_el_mas_caro_de_cualquier_nivel(self):
        assert elegir_por_perfil(self.CANDIDATOS, "Premium").sku == "PRE"

    def test_fan_toma_el_personaje_que_se_pidio(self):
        elegido = elegir_por_perfil(self.CANDIDATOS, "Fan", personajes=("spiderman",))
        assert elegido.sku == "FAN"

    def test_fan_sin_personaje_disponible_no_se_lo_inventa(self):
        sin_personaje = tuple(c for c in self.CANDIDATOS if c.personaje is None)
        assert elegir_por_perfil(sin_personaje, "Fan", personajes=("bluey",)).sku == "ECO"

    def test_el_ahorrador_puede_llevar_un_premium_si_salio_mas_barato(self):
        """No es un defecto. El nivel describe un producto y el perfil una
        ponderacion sobre el kit; comparten la palabra y nada mas."""
        barato_premium = (
            _candidato("CON", "confiable", 9000),
            _candidato("PRE", "premium", 4000),
        )
        assert elegir_por_perfil(barato_premium, "Ahorrador").sku == "PRE"

    def test_el_que_no_cumple_el_atributo_solo_entra_si_no_hay_otro(self):
        candidatos = (
            _candidato("NO-CUMPLE", "economico", 1000, cumple=False),
            _candidato("CUMPLE", "premium", 30000, cumple=True),
        )
        assert elegir_por_perfil(candidatos, "Ahorrador").sku == "CUMPLE"

    def test_sin_precio_no_gana_una_comparacion_de_precio_pero_tampoco_se_descarta(self):
        candidatos = (_candidato("SIN", "economico", None), _candidato("CON", "premium", 8000))
        assert elegir_por_perfil(candidatos, "Ahorrador").sku == "CON"
        assert elegir_por_perfil((candidatos[0],), "Ahorrador").sku == "SIN"


class TestLoInformativoSeMuestraYNoSeCobra:
    def test_una_licencia_digital_no_entra_al_total(self):
        util = _candidato("TK-UTIL", "confiable", 10000)
        kits = armar_los_tres(
            [
                _renglon(1, "Cuaderno", (util,)),
                _renglon(
                    2,
                    "Plan lector virtual RAZ-PLUS",
                    tipo_item="licencia_digital",
                    modo_adquisicion="plataforma",
                    instruccion_colegio="Se adquiere con QUOVIX.",
                ),
            ]
        )
        kit = kits[0]
        informativa = next(linea for linea in kit.lineas if linea.informativa)

        assert informativa.subtotal_cop is None
        assert informativa.precio_unitario_cop is None
        assert informativa.instruccion_colegio == "Se adquiere con QUOVIX."
        assert kit.total_cop == 10000

    def test_una_edicion_exclusiva_es_papel_comprable_y_aun_asi_informativa(self):
        """El tipo dice que se puede comprar y el modo dice que no a Tukit.
        Colapsar los dos ejes perderia justo este caso."""
        kits = armar_los_tres(
            [
                _renglon(
                    1,
                    "Sistema Flex TAC-Lenguaje 1",
                    tipo_item="texto",
                    modo_adquisicion="edicion_exclusiva",
                    instruccion_colegio="Edicion exclusiva para la institucion.",
                )
            ]
        )
        assert kits[0].lineas[0].informativa is True
        assert kits[0].total_cop == 0

    def test_los_objetivos_no_cuentan_lo_que_nunca_se_iba_a_vender(self):
        util = _candidato("TK-UTIL", "confiable", 10000)
        kits = armar_los_tres(
            [
                _renglon(1, "Cuaderno", (util,)),
                _renglon(2, "Uniforme", tipo_item="uniforme", modo_adquisicion="mercado_abierto"),
            ]
        )
        # Una sola linea comprable y esta resuelta: resolucion_auto 1.0. Contando
        # la informativa daria 0.5 y el kit se veria peor por vender menos. La
        # fidelidad es el nivel de marca (confiable = 0.5 sobre el tope premium),
        # que es un eje distinto y ya no se confunde con la resolucion.
        assert kits[0].objetivos["resolucion_auto"] == 1.0
        assert kits[0].objetivos["fidelidad"] == 0.5


class TestLaConsolidacionEntreHermanos:
    def test_dos_hermanos_con_el_mismo_borrador_comparten_la_caja(self):
        caja = Candidato(
            sku="TK-BORRADOR-X10",
            nombre="Caja de borradores x10",
            nivel="economico",
            precio_cop=8000,
            unidades_por_empaque=10,
        )
        kits = armar_los_tres(
            [
                _renglon(1, "2 borradores", (caja,), cantidad=2, hijo="hijo-1"),
                _renglon(1, "2 borradores", (caja,), cantidad=2, hijo="hijo-2"),
            ]
        )
        kit = kits[0]

        assert len(kit.consolidaciones) == 1
        nota = kit.consolidaciones[0]
        assert nota["hijos"] == ["hijo-1", "hijo-2"]
        assert nota["demanda_base"] == 4
        assert nota["unidades_a_comprar"] == 1
        assert nota["ahorro"] == 8000
        assert kit.total_cop == 8000

    def test_los_textos_nunca_se_consolidan_y_el_kit_dice_por_que(self):
        libro = Candidato(sku="TK-LIB", nombre="Don Quijote", nivel="confiable", precio_cop=50000)
        lineas = armar_los_tres(
            [
                _renglon(1, "Don Quijote", (libro,), tipo_item="texto", hijo="hijo-1"),
                _renglon(1, "Don Quijote", (libro,), tipo_item="texto", hijo="hijo-2"),
            ]
        )[0].lineas

        assert all(linea.no_consolidable for linea in lineas)
        assert all("no son sustituibles" in (linea.motivo_no_consolidable or "") for linea in lineas)
        assert all(linea.unidades_a_comprar == 1 for linea in lineas)

    def test_sin_ahorro_no_se_toca_nada(self):
        """Consolidar por consolidar mueve unidades entre hermanos sin
        beneficio y vuelve la explicacion mas dificil de leer que la lista."""
        suelto = Candidato(sku="TK-UNO", nombre="Borrador", nivel="economico", precio_cop=1000)
        lineas, notas = consolidar(
            armar_los_tres(
                [
                    _renglon(1, "1 borrador", (suelto,), hijo="hijo-1"),
                    _renglon(1, "1 borrador", (suelto,), hijo="hijo-2"),
                ]
            )[0].lineas
        )
        assert notas == ()
        assert all(linea.unidades_a_comprar == 1 for linea in lineas)


class TestLaRecomendacion:
    RENGLONES = [
        _renglon(
            1,
            "Cuaderno",
            (
                _candidato("ECO", "economico", 5000),
                _candidato("PRE", "premium", 40000),
                _candidato("FAN", "economico", 9000, personaje="spiderman"),
            ),
        )
    ]

    def test_se_marca_uno_y_se_devuelven_los_tres(self):
        kits = armar_los_tres(self.RENGLONES)
        assert len(kits) == 3
        assert sum(1 for kit in kits if kit.recomendado) == 1

    def test_por_omision_es_el_ahorrador(self):
        kits = armar_los_tres(self.RENGLONES)
        assert next(kit for kit in kits if kit.recomendado).perfil == "Ahorrador"

    def test_premium_solo_con_calidad_primero_y_diez_por_ciento_declarado(self):
        kits = armar_los_tres(
            self.RENGLONES,
            {
                "pesos": {"precio": 0.2, "marca_exigida": 0.2, "calidad": 0.5, "personaje": 0.1},
                "disposicion_sobreprecio": 0.10,
            },
        )
        assert next(kit for kit in kits if kit.recomendado).perfil == "Premium"

    def test_calidad_primero_sin_disposicion_sigue_siendo_ahorrador(self):
        kits = armar_los_tres(
            self.RENGLONES,
            {
                "pesos": {"precio": 0.2, "marca_exigida": 0.2, "calidad": 0.5, "personaje": 0.1},
                "disposicion_sobreprecio": 0.0,
            },
        )
        assert next(kit for kit in kits if kit.recomendado).perfil == "Ahorrador"

    def test_fan_solo_con_personaje_explicito(self):
        kits = armar_los_tres(self.RENGLONES, {"personaje_por_hijo": {"hijo-1": ["spiderman"]}})
        assert next(kit for kit in kits if kit.recomendado).perfil == "Fan"

    def test_el_presupuesto_es_una_cota_dura_y_se_cae_al_que_si_cabe(self):
        kits = armar_los_tres(
            self.RENGLONES,
            {
                "pesos": {"precio": 0.2, "marca_exigida": 0.2, "calidad": 0.5, "personaje": 0.1},
                "disposicion_sobreprecio": 0.10,
                "presupuesto_por_hijo": 10000,
            },
        )
        recomendado = next(kit for kit in kits if kit.recomendado)
        assert recomendado.perfil == "Ahorrador"
        assert recomendado.dentro_de_presupuesto is True
        assert "se pasa de tu presupuesto" in recomendado.razon

    def test_si_ninguno_cabe_lo_dice_en_vez_de_callarlo(self):
        kits = armar_los_tres(self.RENGLONES, {"presupuesto_por_hijo": 100})
        recomendado = next(kit for kit in kits if kit.recomendado)
        assert recomendado.dentro_de_presupuesto is False
        assert "Ningun kit cabe" in recomendado.razon


def _hipervolumen(kits, ref_costo: int) -> float:
    """Hipervolumen 2D (costo vs nivel) de un conjunto de kits.

    No se necesita pymoo: con dos ejes el hipervolumen es el area que domina el
    frente respecto a un punto de referencia. Se usa costo (minimizar, se
    normaliza a `ref_costo - costo`) contra fidelidad de nivel (maximizar). Es
    la magnitud que la tesis reporta; aqui solo se pide que NSGA-II no la
    empeore frente a la heuristica sobre el mismo corpus.
    """
    puntos = sorted({(k.total_cop, k.objetivos.get("fidelidad", 0.0)) for k in kits})
    # Frente: para cada costo, la mejor fidelidad; area bajo la escalera.
    mejor: dict[int, float] = {}
    for costo, fid in puntos:
        mejor[costo] = max(mejor.get(costo, 0.0), fid)
    area = 0.0
    for costo, fid in mejor.items():
        area += max(0, ref_costo - costo) * fid
    return area


class TestElFrenteDePareto:
    """Lo que SI depende del algoritmo: el frente NSGA-II (OE4).

    Un renglon con varios candidatos que se compensan (mas barato vs mejor
    nivel vs con personaje) es donde el frente tiene algo que decir. La
    heuristica es la referencia: el frente no puede hacerlo peor.
    """

    # Un kit con compromiso real: cada linea ofrece barato-flojo,
    # caro-premium y medio-con-personaje. La heuristica y el frente deberian
    # coincidir en los extremos y el frente debe dominar en area.
    RENGLONES = [
        _renglon(
            1,
            "Cuaderno",
            (
                _candidato("C-ECO", "economico", 3000),
                _candidato("C-PRE", "premium", 12000),
                _candidato("C-FAN", "confiable", 6000, personaje="spiderman"),
            ),
            hijo="hijo-1",
        ),
        _renglon(
            2,
            "Colores",
            (
                _candidato("K-ECO", "economico", 8000),
                _candidato("K-PRE", "premium", 25000),
                _candidato("K-FAN", "confiable", 15000, personaje="spiderman"),
            ),
            hijo="hijo-1",
        ),
    ]

    def test_el_frente_no_esta_vacio_cuando_hay_compromiso(self):
        frente = optimizar_frente(self.RENGLONES, {})
        assert len(frente) >= 2
        # Un frente de Pareto no tiene puntos dominados: si ordeno por costo, la
        # fidelidad no puede quedarse igual o subir sin que el costo suba.
        ordenado = sorted(frente, key=lambda s: s.costo)
        for anterior, siguiente in zip(ordenado, ordenado[1:], strict=False):
            assert siguiente.costo >= anterior.costo
            # Si el costo sube es porque compra fidelidad/disponibilidad; dos
            # puntos con el mismo costo no pueden estar ambos en el frente.
            if siguiente.costo == anterior.costo:
                assert (siguiente.fidelidad, siguiente.disponibilidad) != (
                    anterior.fidelidad,
                    anterior.disponibilidad,
                )

    def test_ahorrador_es_el_mas_barato_del_frente(self):
        kits = armar_los_tres(self.RENGLONES, {})
        ahorrador = next(k for k in kits if k.perfil == "Ahorrador")
        assert ahorrador.total_cop == min(k.total_cop for k in kits)
        # Los dos candidatos mas baratos: 3000 + 8000.
        assert ahorrador.total_cop == 11000

    def test_premium_maximiza_el_nivel_de_marca(self):
        kits = armar_los_tres(self.RENGLONES, {})
        premium = next(k for k in kits if k.perfil == "Premium")
        assert premium.objetivos["fidelidad"] >= max(k.objetivos["fidelidad"] for k in kits)
        # Los dos premium: 12000 + 25000.
        assert premium.total_cop == 37000

    def test_fan_toma_el_personaje_pedido_en_todo_el_kit(self):
        kits = armar_los_tres(self.RENGLONES, {"personaje_por_hijo": {"hijo-1": ["spiderman"]}})
        fan = next(k for k in kits if k.perfil == "Fan")
        elegidos = {linea.elegido.sku for linea in fan.lineas if linea.elegido}
        assert elegidos == {"C-FAN", "K-FAN"}

    def test_el_frente_domina_o_iguala_a_la_heuristica_en_hipervolumen(self):
        """La prueba de la tesis, en pequeno: el frente NSGA-II no puede tener
        menos hipervolumen que los tres puntos que daba la heuristica."""
        kits_frente = armar_los_tres(self.RENGLONES, {})
        # La heuristica pura: se fuerza reconstruyendo los kits con
        # `elegir_por_perfil` linea a linea (misma que la ruta degradada).
        from tukit_inteligencia.optimizador import armar_kit

        kits_heuristica = [
            armar_kit(self.RENGLONES, perfil, {}) for perfil in ("Ahorrador", "Premium", "Fan")
        ]
        ref = max(k.total_cop for k in kits_frente + kits_heuristica) + 1
        assert _hipervolumen(kits_frente, ref) >= _hipervolumen(kits_heuristica, ref)

    def test_es_reproducible_bajo_la_misma_semilla(self):
        una = optimizar_frente(self.RENGLONES, {}, semilla=7)
        otra = optimizar_frente(self.RENGLONES, {}, semilla=7)

        def clave(f):
            return sorted((s.costo, s.fidelidad, s.disponibilidad, s.personaje) for s in f)

        assert clave(una) == clave(otra)

    def test_una_sola_opcion_por_linea_no_gasta_el_algoritmo(self):
        """Sin compromiso multiobjetivo el frente es vacio y `armar_los_tres`
        cae a la heuristica, que da exactamente el mismo kit."""
        unica = [_renglon(1, "Cuaderno", (_candidato("SOLO", "confiable", 5000),))]
        assert optimizar_frente(unica, {}) == []
        kits = armar_los_tres(unica, {})
        assert all(k.lineas[0].elegido.sku == "SOLO" for k in kits)


class TestElFrenteNSGAEnEspacioGrande:
    """El camino que SOLO corre NSGA-II: espacio de busqueda > LIMITE_ENUMERACION.

    Las otras pruebas del frente usan kits chicos (espacio 9) que caen en la
    enumeracion exacta; ninguna ejercita el optimizador metaheuristico en si. Con
    8 lineas de 4 candidatos el espacio es 4**8 = 65536 > 4096, asi que aqui si
    corre NSGA-II con la codificacion entera.
    """

    def _renglones_grandes(self):
        niveles = ("economico", "confiable", "premium", "confiable")
        precios = (3000, 6000, 12000, 7000)
        personajes = (None, None, None, "spiderman")
        return [
            _renglon(
                i,
                f"Item {i}",
                tuple(
                    _candidato(f"L{i}-{j}", niveles[j], precios[j], personaje=personajes[j]) for j in range(4)
                ),
                hijo="hijo-1",
            )
            for i in range(1, 9)
        ]

    def test_el_frente_es_no_dominado(self):
        from tukit_inteligencia.optimizador import LIMITE_ENUMERACION

        renglones = self._renglones_grandes()
        assert LIMITE_ENUMERACION < 4**8  # confirma que corre NSGA, no enumeracion
        frente = optimizar_frente(renglones, {}, semilla=0)
        assert len(frente) >= 2
        # Ningun punto del frente domina a otro: si dos difieren, no puede uno
        # ser >= en todos los ejes (costo invertido) y > en alguno.
        for a in frente:
            for b in frente:
                if a is b:
                    continue
                mejor_o_igual = (
                    a.costo <= b.costo
                    and a.fidelidad >= b.fidelidad
                    and a.disponibilidad >= b.disponibilidad
                    and a.personaje >= b.personaje
                )
                estricto = (
                    a.costo < b.costo
                    or a.fidelidad > b.fidelidad
                    or a.disponibilidad > b.disponibilidad
                    or a.personaje > b.personaje
                )
                assert not (mejor_o_igual and estricto), "el frente trae un punto dominado"

    def test_es_reproducible_bajo_la_misma_semilla(self):
        renglones = self._renglones_grandes()

        def clave(f):
            return sorted((s.costo, s.fidelidad, s.disponibilidad, s.personaje) for s in f)

        assert clave(optimizar_frente(renglones, {}, semilla=13)) == clave(
            optimizar_frente(renglones, {}, semilla=13)
        )


class TestBordesDelOptimizador:
    """Casos limite que antes no tenian prueba: sin lineas, todo informativo,
    sin candidatos admisibles. El contrato es un resultado bien definido, no una
    excepcion."""

    def test_sin_renglones_el_frente_es_vacio(self):
        assert optimizar_frente([], {}) == []

    def test_todo_informativo_el_frente_es_vacio(self):
        informativas = [
            _renglon(1, "Licencia", tipo_item="licencia_digital"),
            _renglon(2, "Uniforme", tipo_item="uniforme"),
        ]
        assert optimizar_frente(informativas, {}) == []

    def test_sin_candidatos_no_hay_frente_y_el_kit_marca_la_linea(self):
        sin_cand = [_renglon(1, "Cuaderno", ())]
        assert optimizar_frente(sin_cand, {}) == []
        kits = armar_los_tres(sin_cand)
        # Se arman los tres kits igual; la linea queda sin elegido, no revienta.
        assert len(kits) == 3
        assert all(kit.lineas[0].elegido is None for kit in kits)

    def test_un_kit_grande_corre_por_nsga_y_respeta_las_unidades(self):
        """Un espacio de busqueda grande fuerza la ruta NSGA-II; la aritmetica
        de unidades y la exclusion de lo informativo siguen valiendo."""
        renglones = [
            _renglon(
                orden,
                f"Item {orden}",
                (
                    _candidato(f"A{orden}", "economico", 1000 + orden),
                    _candidato(f"B{orden}", "confiable", 2000 + orden),
                    _candidato(f"C{orden}", "premium", 3000 + orden, personaje="bluey"),
                ),
                hijo="hijo-1",
            )
            for orden in range(1, 9)  # 3**8 = 6561 > LIMITE_ENUMERACION
        ]
        frente = optimizar_frente(renglones, {}, semilla=3)
        assert len(frente) >= 2
        kits = armar_los_tres(renglones, {}, semilla=3)
        ahorrador = next(k for k in kits if k.perfil == "Ahorrador")
        # El mas barato posible: los ocho candidatos "A".
        assert ahorrador.total_cop == sum(1000 + o for o in range(1, 9))
