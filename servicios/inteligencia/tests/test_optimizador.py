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

    def test_ahorrador_compara_lo_que_cuesta_la_linea_y_no_el_precio_unitario(self):
        """Doce lapices: sueltos a $1.000 cuestan $12.000; la caja de doce a
        $9.000 sale mas barata aunque su precio unitario sea mayor. Ordenar por
        precio unitario hacia fallar el Ahorrador en el 20 % del benchmark."""
        candidatos = (
            _candidato("SUELTO", "economico", 1000),
            _candidato("CAJA", "economico", 9000, unidades_por_empaque=12),
        )
        assert elegir_por_perfil(candidatos, "Ahorrador", cantidad=12).sku == "CAJA"
        assert elegir_por_perfil(candidatos, "Ahorrador", cantidad=1).sku == "SUELTO"

    def test_premium_desempata_el_nivel_por_lo_que_cuesta_la_linea(self):
        candidatos = (
            _candidato("PRE-SUELTO", "premium", 2000),
            _candidato("PRE-CAJA", "premium", 15000, unidades_por_empaque=12),
        )
        assert elegir_por_perfil(candidatos, "Premium", cantidad=12).sku == "PRE-CAJA"

    def test_el_kit_usa_la_cantidad_de_la_linea(self):
        candidatos = (
            _candidato("SUELTO", "economico", 1000),
            _candidato("CAJA", "economico", 9000, unidades_por_empaque=12),
        )
        unica = [_renglon(1, "12 lapices", candidatos, cantidad=12)]
        kits = armar_los_tres(unica)
        ahorrador = next(k for k in kits if k.perfil == "Ahorrador")
        assert ahorrador.lineas[0].elegido.sku == "CAJA"
        assert ahorrador.total_cop == 9000


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


class TestUnaHerramientaSePideEnVariasMateriasYSeCompraUnaVez:
    """Tijeras en artes, en tecnologia y en la cartuchera son las mismas
    tijeras. El kit cobraba tres. Solo aplica a lo que dura todo el ano
    (`uno_por_estudiante`); lo que se gasta (pegante, cinta) se respeta."""

    TIJERAS = Candidato(sku="TK-TIJ", nombre="Tijeras Eterna", nivel="economico", precio_cop=5800)

    def test_dos_renglones_de_la_misma_herramienta_se_compran_una_vez(self):
        kit = armar_los_tres(
            [
                _renglon(59, "Tijeras", (self.TIJERAS,), uno_por_estudiante=True),
                _renglon(91, "tijeras", (self.TIJERAS,), uno_por_estudiante=True),
            ]
        )[0]
        primera, segunda = kit.lineas
        assert primera.unidades_a_comprar == 1
        assert segunda.unidades_a_comprar == 0
        assert segunda.subtotal_cop == 0
        assert "linea 59" in (segunda.mensaje or "")
        assert kit.total_cop == 5800

    def test_se_compra_la_cantidad_mayor_y_no_la_suma(self):
        kit = armar_los_tres(
            [
                _renglon(1, "2 reglas", (self.TIJERAS,), cantidad=2, uno_por_estudiante=True),
                _renglon(2, "regla", (self.TIJERAS,), cantidad=1, uno_por_estudiante=True),
            ]
        )[0]
        assert [linea.unidades_a_comprar for linea in kit.lineas] == [2, 0]

    def test_lo_que_se_gasta_no_se_junta(self):
        pegante = Candidato(sku="TK-PEG", nombre="Pegante", nivel="economico", precio_cop=4900)
        kit = armar_los_tres(
            [_renglon(65, "Pegante en barra", (pegante,)), _renglon(89, "pegante en barra", (pegante,))]
        )[0]
        assert [linea.unidades_a_comprar for linea in kit.lineas] == [1, 1]

    def test_dos_productos_distintos_no_se_juntan(self):
        acero = Candidato(sku="TK-ACERO", nombre="Regla de acero", nivel="premium", precio_cop=12000)
        kit = armar_los_tres(
            [
                _renglon(21, "regla 30 cm", (self.TIJERAS,), uno_por_estudiante=True),
                _renglon(31, "regla de acero", (acero,), uno_por_estudiante=True),
            ]
        )[0]
        assert [linea.unidades_a_comprar for linea in kit.lineas] == [1, 1]

    def test_los_hermanos_no_se_juntan_aqui_cada_uno_necesita_las_suyas(self):
        kit = armar_los_tres(
            [
                _renglon(1, "tijeras", (self.TIJERAS,), uno_por_estudiante=True, hijo="hijo-1"),
                _renglon(1, "tijeras", (self.TIJERAS,), uno_por_estudiante=True, hijo="hijo-2"),
            ]
        )[0]
        assert [linea.unidades_a_comprar for linea in kit.lineas] == [1, 1]


class TestQueKitsSeArman:
    """Solo se arman los kits que el acudiente pidio (ADR 0030).

    Siempre Ahorrador y Premium; Fan solo con personaje y `A tu Medida` solo con
    el punto medio o un tope. Por eso los canonicos de una lista son dos.
    """

    RENGLONES = [
        _renglon(
            orden,
            texto,
            (
                _candidato(f"{prefijo}-ECO", "economico", 3000),
                _candidato(f"{prefijo}-CON", "confiable", 6000),
                _candidato(f"{prefijo}-PRE", "premium", 12000),
                _candidato(f"{prefijo}-FAN", "economico", 4000, personaje="spiderman"),
            ),
        )
        for orden, texto, prefijo in ((1, "Cuaderno", "C"), (2, "Colores", "K"))
    ]

    def _perfiles(self, preferencias):
        return [k.perfil for k in armar_los_tres(self.RENGLONES, preferencias)]

    def test_sin_preferencias_solo_ahorrador_y_premium(self):
        assert self._perfiles({}) == ["Ahorrador", "Premium"]

    def test_el_fan_solo_si_pidio_un_personaje(self):
        assert self._perfiles({"personaje_por_hijo": {"hijo-1": ["spiderman"]}}) == [
            "Ahorrador",
            "Fan",
            "Premium",
        ]

    def test_a_tu_medida_solo_con_el_punto_medio_o_un_tope(self):
        assert self._perfiles({"prioridad": "equilibrio"}) == ["Ahorrador", "A tu Medida", "Premium"]
        assert self._perfiles({"presupuesto_por_hijo": 12000}) == ["Ahorrador", "A tu Medida", "Premium"]
        assert self._perfiles({"prioridad": "precio"}) == ["Ahorrador", "Premium"]

    def test_se_marca_uno_solo(self):
        kits = armar_los_tres(self.RENGLONES, {"prioridad": "equilibrio"})
        assert sum(1 for kit in kits if kit.recomendado) == 1


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

    def _recomendado(self, preferencias=None):
        return next(k for k in armar_los_tres(self.RENGLONES, preferencias) if k.recomendado)

    def test_por_omision_es_el_ahorrador(self):
        assert self._recomendado().perfil == "Ahorrador"

    def test_premium_solo_con_calidad_primero_y_diez_por_ciento_declarado(self):
        pesos = {"precio": 0.2, "marca_exigida": 0.2, "calidad": 0.5, "personaje": 0.1}
        assert self._recomendado({"pesos": pesos, "disposicion_sobreprecio": 0.10}).perfil == "Premium"
        assert self._recomendado({"pesos": pesos, "disposicion_sobreprecio": 0.0}).perfil == "Ahorrador"

    def test_fan_con_personaje_explicito(self):
        assert self._recomendado({"personaje_por_hijo": {"hijo-1": ["spiderman"]}}).perfil == "Fan"

    def test_con_diez_por_ciento_decide_la_utilidad_aditiva_de_los_pesos(self):
        """Entre Ahorrador y Premium la utilidad normalizada es w_precio contra
        w_marca_exigida + w_calidad: con los pesos P21 (0,285 contra 0,528) gana
        el Premium; si el precio pesa mas que marca y calidad juntas, el Ahorrador."""
        assert self._recomendado({"disposicion_sobreprecio": 0.10}).perfil == "Premium"
        precio_primero = {"precio": 0.6, "marca_exigida": 0.1, "calidad": 0.1, "personaje": 0.2}
        recomendado = self._recomendado({"pesos": precio_primero, "disposicion_sobreprecio": 0.10})
        assert recomendado.perfil == "Ahorrador"

    def test_sin_diez_por_ciento_los_pesos_no_suben_al_premium(self):
        calidad_primero = {"precio": 0.1, "marca_exigida": 0.3, "calidad": 0.6, "personaje": 0.0}
        recomendado = self._recomendado({"pesos": calidad_primero, "disposicion_sobreprecio": 0.05})
        assert recomendado.perfil == "Ahorrador"

    def test_si_ninguno_cabe_dice_cuanto_cuesta_el_mas_barato(self):
        recomendado = self._recomendado({"presupuesto_por_hijo": 100})
        assert recomendado.perfil == "Ahorrador"
        assert recomendado.dentro_de_presupuesto is False
        assert "Ningún kit cabe en tu tope de $100" in recomendado.razon
        assert "$5.000" in recomendado.razon


class TestATuMedida:
    """El kit del punto medio sale del frente: la mejor marca que cabe.

    El benchmark Laya vs NSGA-II mostro que el kit recomendado con presupuesto
    lograba el 40 % de la calidad posible mientras el frente ya traia uno del
    94 % que cabia (ADR 0029). Cada linea ofrece tres niveles: el Ahorrador
    cuesta 6.000 y el Premium 24.000.
    """

    RENGLONES = [
        _renglon(
            orden,
            texto,
            (
                _candidato(f"{prefijo}-ECO", "economico", 3000),
                _candidato(f"{prefijo}-CON", "confiable", 6000),
                _candidato(f"{prefijo}-PRE", "premium", 12000),
            ),
        )
        for orden, texto, prefijo in ((1, "Cuaderno", "C"), (2, "Colores", "K"))
    ]

    def _kits(self, preferencias):
        return {k.perfil: k for k in armar_los_tres(self.RENGLONES, preferencias)}

    def test_con_tope_es_la_mejor_marca_que_cabe_y_se_recomienda(self):
        kits = self._kits({"prioridad": "equilibrio", "presupuesto_por_hijo": 12000})
        medida = kits["A tu Medida"]
        assert medida.total_cop == 12000
        assert medida.objetivos["fidelidad"] == 0.5
        assert medida.recomendado is True
        assert medida.dentro_de_presupuesto is True
        assert "$12.000" in medida.razon
        # El Premium sigue siendo el de mejor marca: ya no se ajusta.
        assert kits["Premium"].total_cop == 24000

    def test_sin_tope_va_hasta_la_mitad_de_camino(self):
        """Sin tope, el tope implicito es (6.000 + 24.000) / 2 = 15.000."""
        medida = self._kits({"prioridad": "equilibrio"})["A tu Medida"]
        assert medida.total_cop <= 15000
        assert medida.objetivos["fidelidad"] == 0.5
        assert "mitad de camino" in medida.razon
        assert "$15.000" in medida.razon

    def test_si_el_tope_alcanza_para_el_premium_se_recomienda_el_premium(self):
        kits = self._kits({"prioridad": "equilibrio", "presupuesto_por_hijo": 30000})
        assert "A tu Medida" not in kits
        assert kits["Premium"].recomendado is True
        assert "alcanza" in kits["Premium"].razon

    def test_si_no_alcanza_para_subir_de_marca_no_se_repite_el_ahorrador(self):
        kits = self._kits({"prioridad": "equilibrio", "presupuesto_por_hijo": 6000})
        assert "A tu Medida" not in kits
        assert kits["Ahorrador"].recomendado is True
        assert "no alcanza para subir de marca" in kits["Ahorrador"].razon

    def test_el_sobreprecio_declarado_no_estira_el_tope(self):
        """Con 10.000 y 20 % de sobreprecio el kit no pasa de 10.000 (ECO+CON =
        9.000). Quien escribe "maximo 10.000" no espera pagar 12.000."""
        kits = self._kits({"presupuesto_por_hijo": 10000, "disposicion_sobreprecio": 0.2})
        assert kits["A tu Medida"].total_cop == 9000

    def test_si_ninguno_cabe_lo_dice_con_el_precio_del_mas_barato(self):
        kits = self._kits({"prioridad": "equilibrio", "presupuesto_por_hijo": 5000})
        ahorrador = kits["Ahorrador"]
        assert ahorrador.recomendado is True
        assert ahorrador.dentro_de_presupuesto is False
        assert "$5.000" in ahorrador.razon and "$6.000" in ahorrador.razon

    def test_el_personaje_pedido_sigue_mandando_si_cabe(self):
        renglones = [
            _renglon(
                1,
                "Cuaderno",
                (
                    _candidato("ECO", "economico", 3000),
                    _candidato("PRE", "premium", 12000),
                    _candidato("FAN", "economico", 5000, personaje="spiderman"),
                ),
            )
        ]
        kits = armar_los_tres(
            renglones, {"presupuesto_por_hijo": 6000, "personaje_por_hijo": {"hijo-1": ["spiderman"]}}
        )
        assert next(k for k in kits if k.recomendado).perfil == "Fan"

    def test_si_lo_pedido_no_cabe_cae_a_la_mejor_marca_que_cabe_y_no_al_mas_barato(self):
        renglones = [
            _renglon(
                1,
                "Cuaderno",
                (
                    _candidato("ECO", "economico", 3000),
                    _candidato("CON", "confiable", 5000),
                    _candidato("FAN", "economico", 20000, personaje="spiderman"),
                ),
            )
        ]
        kits = armar_los_tres(
            renglones, {"presupuesto_por_hijo": 6000, "personaje_por_hijo": {"hijo-1": ["spiderman"]}}
        )
        recomendado = next(k for k in kits if k.recomendado)
        assert recomendado.lineas[0].elegido.sku == "CON"
        assert recomendado.dentro_de_presupuesto is True
        assert "se pasa de tu tope" in recomendado.razon


class TestUnCandidatoSinPrecioNoGanaPorBarato:
    """El costo del frente no suma lo que no tiene precio (su falta la mide la
    disponibilidad), asi que un candidato sin precio parecia gratis: el
    Ahorrador lo elegia y mostraba un total que no incluia esa linea, y el
    Premium y A tu Medida lo tomaban como una marca que no costaba nada. Lo
    que Tukit no puede surtir no gana una comparacion de precio, igual que en
    la heuristica."""

    RENGLONES = [
        _renglon(
            1, "Cuaderno", (_candidato("A-ECO", "economico", 3000), _candidato("A-SIN", "premium", None))
        ),
        _renglon(
            2, "Colores", (_candidato("B-ECO", "economico", 2000), _candidato("B-PRE", "premium", 9000))
        ),
    ]

    def _kits(self, preferencias=None):
        return {k.perfil: k for k in armar_los_tres(self.RENGLONES, preferencias or {})}

    def _skus(self, kit):
        return [linea.elegido.sku for linea in kit.lineas]

    def test_el_ahorrador_no_elige_lo_que_no_tiene_precio(self):
        ahorrador = self._kits()["Ahorrador"]
        assert self._skus(ahorrador) == ["A-ECO", "B-ECO"]
        assert ahorrador.total_cop == 5000
        assert ahorrador.objetivos["disponibilidad"] == 1.0

    def test_el_premium_no_toma_una_marca_sin_precio_como_gratis(self):
        premium = self._kits()["Premium"]
        assert self._skus(premium) == ["A-ECO", "B-PRE"]
        assert premium.total_cop == 12000

    def test_a_tu_medida_no_cabe_gracias_a_lo_que_no_tiene_precio(self):
        medida = self._kits({"prioridad": "equilibrio", "presupuesto_por_hijo": 12000})
        assert all(linea.precio_unitario_cop is not None for k in medida.values() for linea in k.lineas)

    def test_si_solo_hay_candidato_sin_precio_la_linea_igual_sale(self):
        """Ofrecerlo diciendo "no conocemos el precio" es mejor que dejar la
        linea vacia: puede ser el unico que cumple lo que el colegio exige."""
        renglones = [
            _renglon(1, "Cuaderno", (_candidato("A-SIN", "premium", None),)),
            _renglon(
                2, "Colores", (_candidato("B-ECO", "economico", 2000), _candidato("B-PRE", "premium", 9000))
            ),
        ]
        ahorrador = next(k for k in armar_los_tres(renglones) if k.perfil == "Ahorrador")
        assert self._skus(ahorrador) == ["A-SIN", "B-ECO"]


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

    def _renglones_dispares(self):
        """Doce lineas con precios distintos por linea: subir de marca cuesta
        distinto en cada una, que es donde la escalera de costo marginal encuentra
        kits que el cruce SBX no ve (benchmark: 68 % de las listas)."""
        return [
            _renglon(
                i,
                f"Item {i}",
                (
                    _candidato(f"D{i}-E", "economico", 1000 * i),
                    _candidato(f"D{i}-C", "confiable", 1000 * i + 300 * (13 - i)),
                    _candidato(f"D{i}-P", "premium", 1000 * i + 900 * (13 - i) + 50 * i * i),
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
            _renglon(1, "Licencia", tipo_item="licencia_digital"),
            _renglon(2, "Uniforme", tipo_item="uniforme"),
        ]
        assert optimizar_frente(informativas, {}) == []

    def test_sin_candidatos_no_hay_frente_y_el_kit_marca_la_linea(self):
        sin_cand = [_renglon(1, "Cuaderno", ())]
        assert optimizar_frente(sin_cand, {}) == []
        kits = armar_los_tres(sin_cand)
        # Se arman los kits igual; la linea queda sin elegido, no revienta.
        assert [k.perfil for k in kits] == ["Ahorrador", "Premium"]
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


class TestSeleccionMAUT:
    """Seleccion a posteriori sobre el frente: utilidad aditiva normalizada.

    `elegir_recomendado_maut(frente, pesos, tope=None, sobreprecio=None)` toma el
    punto del frente con mayor utilidad `U = w_precio*u_costo + (w_calidad +
    w_marca_exigida)*u_fidelidad + w_personaje*u_personaje`, con los pesos
    renormalizados para que sumen 1 y cada `u` normalizada a [0, 1] sobre el
    rango observado en el frente. Restricciones duras: el tope de gasto y el
    sobreprecio maximo sobre el punto mas barato.
    """

    @staticmethod
    def _punto(costo, fidelidad, personaje=0.0, disponibilidad=1.0):
        from tukit_inteligencia.optimizador import SolucionFrente

        return SolucionFrente({}, costo, fidelidad, disponibilidad, personaje)

    def _frente(self):
        return [
            self._punto(10000, 0.0),
            self._punto(12000, 0.5),
            self._punto(20000, 1.0),
            self._punto(15000, 0.2, personaje=1.0),
        ]

    def test_frente_vacio_no_elige_nada(self):
        from tukit_inteligencia.optimizador import elegir_recomendado_maut

        assert elegir_recomendado_maut([], {"precio": 1.0}) is None

    def test_un_solo_punto_es_el_elegido(self):
        from tukit_inteligencia.optimizador import elegir_recomendado_maut

        unico = self._punto(5000, 0.3)
        assert elegir_recomendado_maut([unico], {"precio": 1.0}) is unico

    def test_solo_precio_elige_el_mas_barato_y_solo_calidad_el_de_mejor_marca(self):
        from tukit_inteligencia.optimizador import elegir_recomendado_maut

        frente = self._frente()
        assert elegir_recomendado_maut(frente, {"precio": 1.0}).costo == 10000
        assert elegir_recomendado_maut(frente, {"calidad": 1.0}).costo == 20000

    def test_solo_personaje_elige_el_de_mas_personaje(self):
        from tukit_inteligencia.optimizador import elegir_recomendado_maut

        assert elegir_recomendado_maut(self._frente(), {"personaje": 1.0}).personaje == 1.0

    def test_la_utilidad_se_normaliza_sobre_el_rango_del_frente(self):
        """Con pesos iguales precio/calidad gana (12000, 0.5): pierde 0.2 de
        utilidad de costo (2000/10000) y gana 0.5 de fidelidad."""
        from tukit_inteligencia.optimizador import elegir_recomendado_maut

        elegido = elegir_recomendado_maut(self._frente(), {"precio": 0.5, "calidad": 0.5})
        assert (elegido.costo, elegido.fidelidad) == (12000, 0.5)

    def test_marca_exigida_y_calidad_pesan_ambas_sobre_la_fidelidad(self):
        from tukit_inteligencia.optimizador import elegir_recomendado_maut

        frente = self._frente()
        assert elegir_recomendado_maut(frente, {"precio": 0.3, "calidad": 0.7}).costo == 20000
        assert elegir_recomendado_maut(frente, {"precio": 0.3, "marca_exigida": 0.7}).costo == 20000
        mixto = {"precio": 0.3, "marca_exigida": 0.4, "calidad": 0.3}
        assert elegir_recomendado_maut(frente, mixto).costo == 20000

    def test_los_pesos_se_renormalizan(self):
        from tukit_inteligencia.optimizador import elegir_recomendado_maut

        frente = self._frente()
        assert elegir_recomendado_maut(frente, {"precio": 0.1, "calidad": 0.9}).costo == 20000
        assert elegir_recomendado_maut(frente, {"precio": 1, "calidad": 9}).costo == 20000
        assert elegir_recomendado_maut(frente, {"precio": 0.4, "calidad": 0.3}).costo == 12000

    def test_el_sobreprecio_acota_sobre_el_punto_mas_barato(self):
        from tukit_inteligencia.optimizador import elegir_recomendado_maut

        frente = self._frente()
        solo_calidad = {"calidad": 1.0}
        assert elegir_recomendado_maut(frente, solo_calidad).costo == 20000  # sin cota
        assert elegir_recomendado_maut(frente, solo_calidad, sobreprecio=0.0).costo == 10000
        assert elegir_recomendado_maut(frente, solo_calidad, sobreprecio=0.20).costo == 12000
        assert elegir_recomendado_maut(frente, solo_calidad, sobreprecio=1.0).costo == 20000

    def test_el_tope_es_restriccion_dura_y_sin_punto_que_quepa_no_elige(self):
        from tukit_inteligencia.optimizador import elegir_recomendado_maut

        frente = self._frente()
        assert elegir_recomendado_maut(frente, {"calidad": 1.0}, tope=13000).costo == 12000
        assert elegir_recomendado_maut(frente, {"calidad": 1.0}, tope=5000) is None

    def test_pesos_vacios_desempatan_por_menor_costo(self):
        from tukit_inteligencia.optimizador import elegir_recomendado_maut

        assert elegir_recomendado_maut(self._frente(), {}).costo == 10000

    def test_no_depende_del_orden_del_frente(self):
        from tukit_inteligencia.optimizador import elegir_recomendado_maut

        frente = self._frente()
        pesos = {"precio": 0.3, "calidad": 0.5, "personaje": 0.2}
        assert elegir_recomendado_maut(frente, pesos) == elegir_recomendado_maut(frente[::-1], pesos)

    def test_solo_considera_los_puntos_de_maxima_disponibilidad(self):
        from tukit_inteligencia.optimizador import elegir_recomendado_maut

        sin_precio = self._punto(1000, 1.0, disponibilidad=0.5)
        surtible = self._punto(9000, 0.1)
        assert elegir_recomendado_maut([sin_precio, surtible], {"calidad": 1.0}) is surtible


class TestPesosPorOmision:
    def test_son_los_de_la_encuesta_p21_y_suman_uno(self):
        from tukit_inteligencia.modelos import PESOS_POR_OMISION

        esperados = {"precio": 0.285, "marca_exigida": 0.273, "calidad": 0.255, "personaje": 0.187}
        assert PESOS_POR_OMISION == esperados
        assert abs(sum(PESOS_POR_OMISION.values()) - 1.0) < 1e-9
