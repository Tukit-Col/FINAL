from __future__ import annotations

import pytest
from conftest import CURADOR, crear_concepto, crear_producto
from sqlalchemy.exc import IntegrityError
from tukit_catalogo.modelos import Concepto, ProductoCanonico, SustituibilidadConcepto


def _sustituir(sesion, origen, sustituto, grado: float = 0.800, **kw):
    s = SustituibilidadConcepto(
        concepto_origen_id=origen.id,
        concepto_sustituto_id=sustituto.id,
        grado=grado,
        motivo=kw.pop("motivo", "Mismo uso en clase."),
        curado_por=kw.pop("curado_por", CURADOR),
        **kw,
    )
    sesion.add(s)
    sesion.flush()
    return s


class TestRelacionCurada:
    def test_un_concepto_no_se_sustituye_a_si_mismo(self, sesion):
        block = crear_concepto(sesion, "block")
        with pytest.raises(IntegrityError):
            _sustituir(sesion, block, block)

    def test_el_mismo_par_no_se_declara_dos_veces(self, sesion):
        oficio = crear_concepto(sesion, "block_oficio")
        carta = crear_concepto(sesion, "block_carta")
        _sustituir(sesion, oficio, carta)

        with pytest.raises(IntegrityError):
            _sustituir(sesion, oficio, carta, 0.500)

    def test_un_grado_mayor_que_uno_se_rechaza(self, sesion):
        oficio = crear_concepto(sesion, "block_oficio")
        carta = crear_concepto(sesion, "block_carta")
        with pytest.raises(IntegrityError):
            _sustituir(sesion, oficio, carta, 1.5)

    def test_un_grado_negativo_se_rechaza(self, sesion):
        oficio = crear_concepto(sesion, "block_oficio")
        carta = crear_concepto(sesion, "block_carta")
        with pytest.raises(IntegrityError):
            _sustituir(sesion, oficio, carta, -0.2)

    def test_una_arista_que_no_sustituye_nada_no_entra(self, sesion):
        oficio = crear_concepto(sesion, "block_oficio")
        carta = crear_concepto(sesion, "block_carta")
        with pytest.raises(IntegrityError):
            _sustituir(sesion, oficio, carta, 0.0)

    def test_toda_arista_dice_por_que_existe(self, sesion):
        oficio = crear_concepto(sesion, "block_oficio")
        carta = crear_concepto(sesion, "block_carta")
        with pytest.raises(IntegrityError):
            _sustituir(sesion, oficio, carta, motivo=None)

    def test_toda_arista_sabe_quien_la_puso(self, sesion):
        oficio = crear_concepto(sesion, "block_oficio")
        carta = crear_concepto(sesion, "block_carta")
        with pytest.raises(IntegrityError):
            _sustituir(sesion, oficio, carta, curado_por=None)


class TestRelacionDirigida:
    def test_que_a_sirva_por_b_no_implica_que_b_sirva_por_a(self, sesion):
        origami = crear_concepto(sesion, "block_origami")
        dibujo = crear_concepto(sesion, "block_dibujo")
        _sustituir(sesion, origami, dibujo, 0.700, motivo="Sirve para plegar, con desperdicio.")
        _sustituir(sesion, dibujo, origami, 0.200, motivo="El gramaje del origami no aguanta.")
        sesion.flush()

        grados = {
            (s.concepto_origen_id, s.concepto_sustituto_id): float(s.grado)
            for s in sesion.query(SustituibilidadConcepto)
        }
        assert grados[(origami.id, dibujo.id)] == pytest.approx(0.700)
        assert grados[(dibujo.id, origami.id)] == pytest.approx(0.200)


class TestConsultaYNoReconstruccion:
    def test_los_sustitutos_salen_ordenados_de_una_sola_consulta(self, sesion):
        oficio = crear_concepto(sesion, "block_oficio")
        carta = crear_concepto(sesion, "block_carta")
        media = crear_concepto(sesion, "block_media_carta")
        _sustituir(sesion, oficio, media, 0.400, motivo="Se queda corto para planos.")
        _sustituir(sesion, oficio, carta, 0.850, motivo="Mismo papel, un tamano menos.")
        sesion.flush()

        mejores = (
            sesion.query(SustituibilidadConcepto)
            .filter(SustituibilidadConcepto.concepto_origen_id == oficio.id)
            .order_by(SustituibilidadConcepto.grado.desc())
            .all()
        )
        assert [s.concepto_sustituto_id for s in mejores] == [carta.id, media.id]

    def test_la_consulta_por_concepto_de_origen_tiene_indice(self, sesion):
        indices = {i.name for i in SustituibilidadConcepto.__table__.indexes}
        assert "ix_sustituibilidad_origen" in indices

    def test_un_hueco_de_catalogo_se_puede_responder_con_algo(self, sesion):
        oficio = crear_concepto(sesion, "block_oficio")
        carta = crear_concepto(sesion, "block_carta")
        crear_producto(sesion, carta)
        _sustituir(sesion, oficio, carta, 0.850, motivo="Mismo papel, un tamano menos.")
        sesion.flush()

        con_producto = {p.concepto_id for p in sesion.query(ProductoCanonico)}
        assert oficio.id not in con_producto

        ofrecibles = [
            s
            for s in sesion.query(SustituibilidadConcepto)
            .filter(SustituibilidadConcepto.concepto_origen_id == oficio.id)
            .order_by(SustituibilidadConcepto.grado.desc())
            if s.concepto_sustituto_id in con_producto
        ]
        assert [s.concepto_sustituto_id for s in ofrecibles] == [carta.id]
        assert ofrecibles[0].motivo


class TestCicloDeVida:
    def test_borrar_un_concepto_se_lleva_sus_aristas(self, sesion):
        oficio = crear_concepto(sesion, "block_oficio")
        carta = crear_concepto(sesion, "block_carta")
        _sustituir(sesion, oficio, carta)
        sesion.flush()

        sesion.delete(carta)
        sesion.flush()

        assert sesion.query(SustituibilidadConcepto).count() == 0
        assert sesion.query(Concepto).count() == 1
