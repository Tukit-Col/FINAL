"""El armado de los tres kits: unidades, total honesto y recomendacion.

Las pruebas de aqui fijan lo que NO depende del algoritmo. La heuristica de
seleccion se va a reemplazar por NSGA-II; la aritmetica de unidades, la regla
de que lo informativo no se cobra y la regla de recomendacion salida de la
encuesta tienen que seguir valiendo despues del reemplazo.
"""

from __future__ import annotations

import pytest
from tukit_inteligencia.optimizador import (
    Candidato,
    Renglon,
    armar_los_tres,
    consolidar,
    elegir_por_perfil,
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

    def test_la_fidelidad_no_cuenta_lo_que_nunca_se_iba_a_vender(self):
        util = _candidato("TK-UTIL", "confiable", 10000)
        kits = armar_los_tres(
            [
                _renglon(1, "Cuaderno", (util,)),
                _renglon(2, "Uniforme", tipo_item="uniforme", modo_adquisicion="mercado_abierto"),
            ]
        )
        # Una sola linea comprable y esta resuelta: fidelidad 1.0. Contando la
        # informativa daria 0.5 y el kit se veria peor por vender menos.
        assert kits[0].objetivos["fidelidad"] == 1.0


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
