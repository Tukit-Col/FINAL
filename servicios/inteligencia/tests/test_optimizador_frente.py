"""El frente de Pareto (OE4): lo que si depende del algoritmo NSGA-II.

Que el frente no lo haga peor que la heuristica en hipervolumen, que sea
reproducible bajo la misma semilla, que el camino metaheuristico corra de
verdad cuando el espacio pasa `LIMITE_ENUMERACION`, que el Fan no repita el
mismo producto y que los bordes (sin lineas, todo informativo, sin admisibles)
den un resultado bien definido en vez de una excepcion.
"""

from __future__ import annotations

from _ayudas_inteligencia import candidato, renglon_optimizador
from tukit_inteligencia.optimizador import (
    armar_los_tres,
    optimizar_frente,
)


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
        renglon_optimizador(
            1,
            "Cuaderno",
            (
                candidato("C-ECO", "economico", 3000),
                candidato("C-PRE", "premium", 12000),
                candidato("C-FAN", "confiable", 6000, personaje="spiderman"),
            ),
            hijo="hijo-1",
        ),
        renglon_optimizador(
            2,
            "Colores",
            (
                candidato("K-ECO", "economico", 8000),
                candidato("K-PRE", "premium", 25000),
                candidato("K-FAN", "confiable", 15000, personaje="spiderman"),
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
        menos hipervolumen que los puntos que daba la heuristica."""
        kits_frente = armar_los_tres(self.RENGLONES, {})
        # La heuristica pura: se fuerza reconstruyendo los kits con
        # `elegir_por_perfil` linea a linea (misma que la ruta degradada).
        from tukit_inteligencia.optimizador import armar_kit

        kits_heuristica = [armar_kit(self.RENGLONES, perfil, {}) for perfil in ("Ahorrador", "Premium")]
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
        unica = [renglon_optimizador(1, "Cuaderno", (candidato("SOLO", "confiable", 5000),))]
        assert optimizar_frente(unica, {}) == []
        kits = armar_los_tres(unica, {})
        assert all(k.lineas[0].elegido.sku == "SOLO" for k in kits)


class TestElFanNoRepiteElMismoProducto:
    """Regresion: el Fan ponia el mismo cuaderno de personaje en cada renglon."""

    SPIDEY = candidato("SPIDEY", "confiable", 36900, personaje="spiderman")
    OTRO_DISENO = candidato("SPIDEY-2", "confiable", 12000, personaje="spiderman")
    NEUTRO = candidato("NEUTRO", "economico", 7990)

    def _renglones(self, textos, candidatos):
        return [renglon_optimizador(i + 1, t, candidatos) for i, t in enumerate(textos)]

    def test_el_mismo_producto_de_personaje_sale_una_vez(self):
        renglones = self._renglones(
            ["cuaderno cuadriculado 100 hojas", "cuaderno cosido 100 hojas", "cuaderno grande"],
            (self.SPIDEY, self.NEUTRO),
        )
        fan = next(
            k
            for k in armar_los_tres(renglones, {"personaje_por_hijo": {"hijo-1": ["spiderman"]}})
            if k.perfil == "Fan"
        )
        skus = [li.elegido.sku for li in fan.lineas]
        assert skus.count("SPIDEY") == 1
        assert skus.count("NEUTRO") == 2

    def test_otro_diseno_del_personaje_es_preferido_al_neutro(self):
        renglones = self._renglones(
            ["cuaderno a", "cuaderno b"], (self.SPIDEY, self.OTRO_DISENO, self.NEUTRO)
        )
        fan = next(
            k
            for k in armar_los_tres(renglones, {"personaje_por_hijo": {"hijo-1": ["spiderman"]}})
            if k.perfil == "Fan"
        )
        # Los dos renglones llevan personaje, pero no el mismo producto.
        assert {li.elegido.sku for li in fan.lineas} == {"SPIDEY-2", "SPIDEY"}

    def test_el_renglon_surtido_puede_repetir(self):
        renglones = self._renglones(
            ["cuaderno cuadriculado", "cuadernos surtidos"], (self.SPIDEY, self.NEUTRO)
        )
        fan = next(
            k
            for k in armar_los_tres(renglones, {"personaje_por_hijo": {"hijo-1": ["spiderman"]}})
            if k.perfil == "Fan"
        )
        assert [li.elegido.sku for li in fan.lineas] == ["SPIDEY", "SPIDEY"]

    def test_ahorrador_y_premium_no_cambian(self):
        renglones = self._renglones(["cuaderno a", "cuaderno b"], (self.SPIDEY, self.NEUTRO))
        sin = armar_los_tres(renglones, {})
        con = armar_los_tres(renglones, {"personaje_por_hijo": {"hijo-1": ["spiderman"]}})
        for perfil in ("Ahorrador", "Premium"):
            a = next(k for k in sin if k.perfil == perfil)
            b = next(k for k in con if k.perfil == perfil)
            assert [li.elegido.sku for li in a.lineas] == [li.elegido.sku for li in b.lineas]


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
            renglon_optimizador(
                i,
                f"Item {i}",
                tuple(
                    candidato(f"L{i}-{j}", niveles[j], precios[j], personaje=personajes[j]) for j in range(4)
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

    def _renglones_dispares(self):
        """Doce lineas con precios distintos por linea: subir de marca cuesta
        distinto en cada una, que es donde la escalera de costo marginal encuentra
        kits que el cruce SBX no ve (benchmark: 68 % de las listas)."""
        return [
            renglon_optimizador(
                i,
                f"Item {i}",
                (
                    candidato(f"D{i}-E", "economico", 1000 * i),
                    candidato(f"D{i}-C", "confiable", 1000 * i + 300 * (13 - i)),
                    candidato(f"D{i}-P", "premium", 1000 * i + 900 * (13 - i) + 50 * i * i),
                ),
                hijo="hijo-1",
            )
            for i in range(1, 13)
        ]

    def test_la_escalera_sube_de_marca_donde_cuesta_menos(self):
        from tukit_inteligencia.optimizador import _admisibles, _escalera_costo_marginal

        renglones = self._renglones_dispares()
        opciones = [_admisibles(r) for r in renglones]
        escalera = _escalera_costo_marginal(renglones, opciones)
        # Arranca en el kit mas barato y termina en el de mejor marca.
        assert all(opciones[i][j].nivel == "economico" for i, j in enumerate(escalera[0]))
        assert all(opciones[i][j].nivel == "premium" for i, j in enumerate(escalera[-1]))
        # Cada peldano sube la marca y no baja el costo.
        costos = [sum(opciones[i][j].precio_cop for i, j in enumerate(p)) for p in escalera]
        niveles = [sum(opciones[i][j].rango_nivel for i, j in enumerate(p)) for p in escalera]
        assert costos == sorted(costos)
        assert all(b > a for a, b in zip(niveles, niveles[1:], strict=False))
        # El primer peldano sube la linea donde subir cuesta menos: la 12.
        cambio = [i for i, (a, b) in enumerate(zip(escalera[0], escalera[1], strict=True)) if a != b]
        assert cambio == [11]

    def test_ningun_kit_de_la_escalera_domina_al_frente(self):
        from tukit_inteligencia.optimizador import (
            _admisibles,
            _domina,
            _escalera_costo_marginal,
            _objetivos_de_asignacion,
        )

        renglones = self._renglones_dispares()
        opciones = [_admisibles(r) for r in renglones]
        frente = optimizar_frente(renglones, {}, semilla=0)
        puntos = [(s.costo, s.fidelidad, s.disponibilidad, s.personaje) for s in frente]
        for peldano in _escalera_costo_marginal(renglones, opciones):
            elegidos = [opciones[i][j] for i, j in enumerate(peldano)]
            kit = _objetivos_de_asignacion(renglones, elegidos, {})
            assert not any(_domina(kit, p) for p in puntos), "la escalera domina un punto del frente"


class TestBordesDelOptimizador:
    """Casos limite que antes no tenian prueba: sin lineas, todo informativo,
    sin candidatos admisibles. El contrato es un resultado bien definido, no una
    excepcion."""

    def test_sin_renglones_el_frente_es_vacio(self):
        assert optimizar_frente([], {}) == []

    def test_todo_informativo_el_frente_es_vacio(self):
        informativas = [
            renglon_optimizador(1, "Licencia", tipo_item="licencia_digital"),
            renglon_optimizador(2, "Uniforme", tipo_item="uniforme"),
        ]
        assert optimizar_frente(informativas, {}) == []

    def test_sin_candidatos_no_hay_frente_y_el_kit_marca_la_linea(self):
        sin_cand = [renglon_optimizador(1, "Cuaderno", ())]
        assert optimizar_frente(sin_cand, {}) == []
        kits = armar_los_tres(sin_cand)
        # Se arman los kits igual; la linea queda sin elegido, no revienta.
        assert [k.perfil for k in kits] == ["Ahorrador", "Premium"]
        assert all(kit.lineas[0].elegido is None for kit in kits)

    def test_un_kit_grande_corre_por_nsga_y_respeta_las_unidades(self):
        """Un espacio de busqueda grande fuerza la ruta NSGA-II; la aritmetica
        de unidades y la exclusion de lo informativo siguen valiendo."""
        renglones = [
            renglon_optimizador(
                orden,
                f"Item {orden}",
                (
                    candidato(f"A{orden}", "economico", 1000 + orden),
                    candidato(f"B{orden}", "confiable", 2000 + orden),
                    candidato(f"C{orden}", "premium", 3000 + orden, personaje="bluey"),
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
