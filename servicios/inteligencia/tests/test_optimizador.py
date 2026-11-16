"""El armado de los kits por perfil: unidades, total honesto y consolidacion.

Las pruebas de aqui fijan lo que NO depende del algoritmo de seleccion: la
aritmetica de unidades, la regla de que lo informativo no se cobra, que cada
perfil elige lo que dice, que un candidato sin precio no gana por barato y que
lo que piden varios hermanos o varias materias se compra una vez. Lo que si
depende del algoritmo (el frente NSGA-II) vive en `test_optimizador_frente.py`;
que kits se arman y cual se recomienda, en `test_optimizador_recomendacion.py`.
"""

from __future__ import annotations

import pytest
from _ayudas_inteligencia import candidato, renglon_optimizador
from tukit_inteligencia.optimizador import (
    Candidato,
    armar_los_tres,
    consolidar,
    elegir_por_perfil,
    unidades_a_comprar,
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
        caja = candidato("TK-CAJA", "confiable", 18900, unidades_por_empaque=12)
        kits = armar_los_tres([renglon_optimizador(1, "12 lapices", (caja,), cantidad=12)])

        linea = kits[0].lineas[0]
        assert linea.cantidad_pedida == 12
        assert linea.unidades_por_empaque == 12
        assert linea.unidades_a_comprar == 1
        assert linea.subtotal_cop == 18900


class TestCadaPerfilEligeLoQueDice:
    CANDIDATOS = (
        candidato("ECO", "economico", 5000),
        candidato("CON", "confiable", 9000),
        candidato("PRE", "premium", 15000),
        candidato("FAN", "economico", 7000, personaje="spiderman"),
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
            candidato("CON", "confiable", 9000),
            candidato("PRE", "premium", 4000),
        )
        assert elegir_por_perfil(barato_premium, "Ahorrador").sku == "PRE"

    def test_el_que_no_cumple_el_atributo_solo_entra_si_no_hay_otro(self):
        candidatos = (
            candidato("NO-CUMPLE", "economico", 1000, cumple=False),
            candidato("CUMPLE", "premium", 30000, cumple=True),
        )
        assert elegir_por_perfil(candidatos, "Ahorrador").sku == "CUMPLE"

    def test_sin_precio_no_gana_una_comparacion_de_precio_pero_tampoco_se_descarta(self):
        candidatos = (candidato("SIN", "economico", None), candidato("CON", "premium", 8000))
        assert elegir_por_perfil(candidatos, "Ahorrador").sku == "CON"
        assert elegir_por_perfil((candidatos[0],), "Ahorrador").sku == "SIN"

    def test_ahorrador_compara_lo_que_cuesta_la_linea_y_no_el_precio_unitario(self):
        """Doce lapices: sueltos a $1.000 cuestan $12.000; la caja de doce a
        $9.000 sale mas barata aunque su precio unitario sea mayor. Ordenar por
        precio unitario hacia fallar el Ahorrador en el 20 % del benchmark."""
        candidatos = (
            candidato("SUELTO", "economico", 1000),
            candidato("CAJA", "economico", 9000, unidades_por_empaque=12),
        )
        assert elegir_por_perfil(candidatos, "Ahorrador", cantidad=12).sku == "CAJA"
        assert elegir_por_perfil(candidatos, "Ahorrador", cantidad=1).sku == "SUELTO"

    def test_premium_desempata_el_nivel_por_lo_que_cuesta_la_linea(self):
        candidatos = (
            candidato("PRE-SUELTO", "premium", 2000),
            candidato("PRE-CAJA", "premium", 15000, unidades_por_empaque=12),
        )
        assert elegir_por_perfil(candidatos, "Premium", cantidad=12).sku == "PRE-CAJA"

    def test_el_kit_usa_la_cantidad_de_la_linea(self):
        candidatos = (
            candidato("SUELTO", "economico", 1000),
            candidato("CAJA", "economico", 9000, unidades_por_empaque=12),
        )
        unica = [renglon_optimizador(1, "12 lapices", candidatos, cantidad=12)]
        kits = armar_los_tres(unica)
        ahorrador = next(k for k in kits if k.perfil == "Ahorrador")
        assert ahorrador.lineas[0].elegido.sku == "CAJA"
        assert ahorrador.total_cop == 9000


class TestLoInformativoSeMuestraYNoSeCobra:
    def test_una_licencia_digital_no_entra_al_total(self):
        util = candidato("TK-UTIL", "confiable", 10000)
        kits = armar_los_tres(
            [
                renglon_optimizador(1, "Cuaderno", (util,)),
                renglon_optimizador(
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
                renglon_optimizador(
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
        util = candidato("TK-UTIL", "confiable", 10000)
        kits = armar_los_tres(
            [
                renglon_optimizador(1, "Cuaderno", (util,)),
                renglon_optimizador(2, "Uniforme", tipo_item="uniforme", modo_adquisicion="mercado_abierto"),
            ]
        )
        # Una sola linea comprable y esta resuelta: resolucion_auto 1.0. Contando
        # la informativa daria 0.5 y el kit se veria peor por vender menos. La
        # fidelidad es el nivel de marca (confiable = 0.5 sobre el tope premium),
        # que es un eje distinto y ya no se confunde con la resolucion.
        assert kits[0].objetivos["resolucion_auto"] == 1.0
        assert kits[0].objetivos["fidelidad"] == pytest.approx(0.5)


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
                renglon_optimizador(1, "2 borradores", (caja,), cantidad=2, hijo="hijo-1"),
                renglon_optimizador(1, "2 borradores", (caja,), cantidad=2, hijo="hijo-2"),
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

    CAJA = Candidato(
        sku="TK-CART-X25", nombre="Block x25", nivel="economico", precio_cop=9000, unidades_por_empaque=25
    )

    def test_el_mensaje_no_usa_la_referencia_interna_del_hijo(self):
        # H-C-04: decia "Se compra junto con el de hijo-1", el id interno.
        lineas, _ = consolidar(
            armar_los_tres(
                [
                    renglon_optimizador(7, "2 cartulinas", (self.CAJA,), cantidad=2, hijo="hijo-0"),
                    renglon_optimizador(4, "2 cartulinas", (self.CAJA,), cantidad=2, hijo="hijo-1"),
                ]
            )[0].lineas
        )
        mensaje = next(linea.mensaje for linea in lineas if linea.unidades_a_comprar == 0)
        assert "hijo-" not in mensaje
        assert (
            mensaje
            == "Se compra junto con la línea 7 de tu otro hijo: un empaque de 25 alcanza para los dos."
        )

    def test_el_mensaje_de_una_linea_del_mismo_hijo_no_lo_llama_otro(self):
        # Dos renglones del mismo hijo con el mismo producto, mas el hermano.
        lineas, _ = consolidar(
            armar_los_tres(
                [
                    renglon_optimizador(49, "2 cartulinas", (self.CAJA,), cantidad=2, hijo="hijo-1"),
                    renglon_optimizador(50, "2 cartulinas pastel", (self.CAJA,), cantidad=2, hijo="hijo-1"),
                    renglon_optimizador(3, "2 cartulinas", (self.CAJA,), cantidad=2, hijo="hijo-0"),
                ]
            )[0].lineas
        )
        por_orden = {linea.orden: linea for linea in lineas}
        primera = next(linea for linea in lineas if linea.unidades_a_comprar > 0)
        for linea in lineas:
            if linea is primera:
                continue
            assert "hijo-" not in (linea.mensaje or "")
            if linea.hijo == primera.hijo:
                assert linea.mensaje == (
                    f"Se compra junto con la línea {primera.orden}: un empaque de 25 alcanza para todos."
                )
            else:
                assert "de tu otro hijo" in (linea.mensaje or "")
        assert len(por_orden) == 3

    def test_los_textos_nunca_se_consolidan_y_el_kit_dice_por_que(self):
        libro = Candidato(sku="TK-LIB", nombre="Don Quijote", nivel="confiable", precio_cop=50000)
        lineas = armar_los_tres(
            [
                renglon_optimizador(1, "Don Quijote", (libro,), tipo_item="texto", hijo="hijo-1"),
                renglon_optimizador(1, "Don Quijote", (libro,), tipo_item="texto", hijo="hijo-2"),
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
                    renglon_optimizador(1, "1 borrador", (suelto,), hijo="hijo-1"),
                    renglon_optimizador(1, "1 borrador", (suelto,), hijo="hijo-2"),
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
                renglon_optimizador(59, "Tijeras", (self.TIJERAS,), uno_por_estudiante=True),
                renglon_optimizador(91, "tijeras", (self.TIJERAS,), uno_por_estudiante=True),
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
                renglon_optimizador(1, "2 reglas", (self.TIJERAS,), cantidad=2, uno_por_estudiante=True),
                renglon_optimizador(2, "regla", (self.TIJERAS,), cantidad=1, uno_por_estudiante=True),
            ]
        )[0]
        assert [linea.unidades_a_comprar for linea in kit.lineas] == [2, 0]

    def test_lo_que_se_gasta_no_se_junta(self):
        pegante = Candidato(sku="TK-PEG", nombre="Pegante", nivel="economico", precio_cop=4900)
        kit = armar_los_tres(
            [
                renglon_optimizador(65, "Pegante en barra", (pegante,)),
                renglon_optimizador(89, "pegante en barra", (pegante,)),
            ]
        )[0]
        assert [linea.unidades_a_comprar for linea in kit.lineas] == [1, 1]

    def test_dos_productos_distintos_no_se_juntan(self):
        acero = Candidato(sku="TK-ACERO", nombre="Regla de acero", nivel="premium", precio_cop=12000)
        kit = armar_los_tres(
            [
                renglon_optimizador(21, "regla 30 cm", (self.TIJERAS,), uno_por_estudiante=True),
                renglon_optimizador(31, "regla de acero", (acero,), uno_por_estudiante=True),
            ]
        )[0]
        assert [linea.unidades_a_comprar for linea in kit.lineas] == [1, 1]

    def test_los_hermanos_no_se_juntan_aqui_cada_uno_necesita_las_suyas(self):
        kit = armar_los_tres(
            [
                renglon_optimizador(1, "tijeras", (self.TIJERAS,), uno_por_estudiante=True, hijo="hijo-1"),
                renglon_optimizador(1, "tijeras", (self.TIJERAS,), uno_por_estudiante=True, hijo="hijo-2"),
            ]
        )[0]
        assert [linea.unidades_a_comprar for linea in kit.lineas] == [1, 1]


class TestUnCandidatoSinPrecioNoGanaPorBarato:
    """El costo del frente no suma lo que no tiene precio (su falta la mide la
    disponibilidad), asi que un candidato sin precio parecia gratis: el
    Ahorrador lo elegia y mostraba un total que no incluia esa linea, y el
    Premium y A tu Medida lo tomaban como una marca que no costaba nada. Lo
    que Tukit no puede surtir no gana una comparacion de precio, igual que en
    la heuristica."""

    RENGLONES = [
        renglon_optimizador(
            1, "Cuaderno", (candidato("A-ECO", "economico", 3000), candidato("A-SIN", "premium", None))
        ),
        renglon_optimizador(
            2, "Colores", (candidato("B-ECO", "economico", 2000), candidato("B-PRE", "premium", 9000))
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
            renglon_optimizador(1, "Cuaderno", (candidato("A-SIN", "premium", None),)),
            renglon_optimizador(
                2, "Colores", (candidato("B-ECO", "economico", 2000), candidato("B-PRE", "premium", 9000))
            ),
        ]
        ahorrador = next(k for k in armar_los_tres(renglones) if k.perfil == "Ahorrador")
        assert self._skus(ahorrador) == ["A-SIN", "B-ECO"]
