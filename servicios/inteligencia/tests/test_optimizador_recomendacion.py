from __future__ import annotations

import pytest
from _ayudas_inteligencia import candidato, renglon_optimizador
from tukit_inteligencia.optimizador import (
    armar_los_tres,
)


class TestQueKitsSeArman:
    RENGLONES = [
        renglon_optimizador(
            orden,
            texto,
            (
                candidato(f"{prefijo}-ECO", "economico", 3000),
                candidato(f"{prefijo}-CON", "confiable", 6000),
                candidato(f"{prefijo}-PRE", "premium", 12000),
                candidato(f"{prefijo}-FAN", "economico", 4000, personaje="spiderman"),
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
        renglon_optimizador(
            1,
            "Cuaderno",
            (
                candidato("ECO", "economico", 5000),
                candidato("PRE", "premium", 40000),
                candidato("FAN", "economico", 9000, personaje="spiderman"),
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
    RENGLONES = [
        renglon_optimizador(
            orden,
            texto,
            (
                candidato(f"{prefijo}-ECO", "economico", 3000),
                candidato(f"{prefijo}-CON", "confiable", 6000),
                candidato(f"{prefijo}-PRE", "premium", 12000),
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
        assert medida.objetivos["fidelidad"] == pytest.approx(0.5)
        assert medida.recomendado is True
        assert medida.dentro_de_presupuesto is True
        assert "$12.000" in medida.razon
        assert kits["Premium"].total_cop == 24000

    def test_sin_tope_va_hasta_la_mitad_de_camino(self):
        medida = self._kits({"prioridad": "equilibrio"})["A tu Medida"]
        assert medida.total_cop <= 15000
        assert medida.objetivos["fidelidad"] == pytest.approx(0.5)
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
            renglon_optimizador(
                1,
                "Cuaderno",
                (
                    candidato("ECO", "economico", 3000),
                    candidato("PRE", "premium", 12000),
                    candidato("FAN", "economico", 5000, personaje="spiderman"),
                ),
            )
        ]
        kits = armar_los_tres(
            renglones, {"presupuesto_por_hijo": 6000, "personaje_por_hijo": {"hijo-1": ["spiderman"]}}
        )
        assert next(k for k in kits if k.recomendado).perfil == "Fan"

    def test_si_lo_pedido_no_cabe_cae_a_la_mejor_marca_que_cabe_y_no_al_mas_barato(self):
        renglones = [
            renglon_optimizador(
                1,
                "Cuaderno",
                (
                    candidato("ECO", "economico", 3000),
                    candidato("CON", "confiable", 5000),
                    candidato("FAN", "economico", 20000, personaje="spiderman"),
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


class TestSeleccionMAUT:
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
        assert elegir_recomendado_maut(frente, solo_calidad).costo == 20000
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
        assert esperados == PESOS_POR_OMISION
        assert sum(PESOS_POR_OMISION.values()) == pytest.approx(1.0)
