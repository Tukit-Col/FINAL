"""El grafo de sustituibilidad entre conceptos, ya como tabla consultable.

Responde la pregunta que hoy no tiene respuesta util: que ofrecer cuando el
catalogo no tiene lo que la lista pide. 102 de las 297 celdas (concepto x
nivel) estan vacias y 17 conceptos no tienen ni un producto, asi que "no lo
tengo" es la salida mas frecuente del pipeline y tambien la menos util.

Lo que se prueba aqui no es que la tabla exista, sino las tres propiedades sin
las cuales no sirve de nada:

  1. Que la relacion sea DIRIGIDA. Que un block de dibujo sirva en lugar de
     uno de origami no implica lo contrario, y un grafo simetrico tendria que
     elegir un solo numero para dos preguntas distintas.
  2. Que este CURADA. Cada arista dice por que existe y quien la puso; si no,
     es una similitud calculada con otro nombre.
  3. Que responder sea una CONSULTA y no una reconstruccion. Es la razon de
     ser del cambio: el grafo en memoria se rearmaba entero por cada item y
     costaba el 95,3 % de la latencia del pipeline, 1.673 ms construirlo
     contra 0,137 ms consultarlo.
"""

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
        """La arista reflexiva no aporta ninguna alternativa y ademas ensucia
        el orden de los sustitutos con el concepto que justamente no se tiene."""
        block = crear_concepto(sesion, "block")
        with pytest.raises(IntegrityError):
            _sustituir(sesion, block, block)

    def test_el_mismo_par_no_se_declara_dos_veces(self, sesion):
        """Dos filas para el mismo par son dos grados distintos para la misma
        pregunta, o sea ninguna respuesta."""
        oficio = crear_concepto(sesion, "block_oficio")
        carta = crear_concepto(sesion, "block_carta")
        _sustituir(sesion, oficio, carta)

        with pytest.raises(IntegrityError):
            _sustituir(sesion, oficio, carta, 0.500)

    # Los dos extremos del rango van en pruebas separadas y no en un bucle a
    # proposito: despues de un flush fallido la sesion queda sucia, y al
    # deshacerla los conceptos recien creados se van con ella. Un segundo
    # intento dentro de la misma prueba fallaria por llave foranea y pasaria
    # igual, o sea que se estaria probando otra cosa sin enterarse.

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
        """Grado cero significa "no sirve como reemplazo", que es lo mismo que
        no tener la fila. Admitirlo llenaria la tabla de aristas que solo
        cuestan de leer y que nunca se pueden ofrecer."""
        oficio = crear_concepto(sesion, "block_oficio")
        carta = crear_concepto(sesion, "block_carta")
        with pytest.raises(IntegrityError):
            _sustituir(sesion, oficio, carta, 0.0)

    def test_toda_arista_dice_por_que_existe(self, sesion):
        """Curada y no inducida: una sustitucion sin motivo no se puede
        revisar, y poder revisarla es lo unico que la distingue de una
        similitud calculada por un modelo."""
        oficio = crear_concepto(sesion, "block_oficio")
        carta = crear_concepto(sesion, "block_carta")
        with pytest.raises(IntegrityError):
            _sustituir(sesion, oficio, carta, motivo=None)

    def test_toda_arista_sabe_quien_la_puso(self, sesion):
        """La misma regla del catalogo curado que ya rige en
        `producto_canonico`: lo que nadie curo no existe."""
        oficio = crear_concepto(sesion, "block_oficio")
        carta = crear_concepto(sesion, "block_carta")
        with pytest.raises(IntegrityError):
            _sustituir(sesion, oficio, carta, curado_por=None)


class TestRelacionDirigida:
    def test_que_a_sirva_por_b_no_implica_que_b_sirva_por_a(self, sesion):
        """Un block de dibujo pasa por uno de origami a medias; el de origami
        casi nunca pasa por uno de dibujo. Son dos preguntas con dos
        respuestas, y por eso son dos filas."""
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
        """El punto entero del cambio. El pipeline pregunta "que ofrezco en
        lugar de esto" una vez por item; si responder implica rearmar el grafo
        se pagan 1.673 ms por item en vez de 0,137 ms. El orden va en SQL,
        que es como corre en produccion y es lo que usa el indice."""
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
        """Sin indice la tabla no arregla nada: cambia un recorrido en memoria
        por un recorrido secuencial en disco, y el 95,3 % sigue ahi."""
        indices = {i.name for i in SustituibilidadConcepto.__table__.indexes}
        assert "ix_sustituibilidad_origen" in indices

    def test_un_hueco_de_catalogo_se_puede_responder_con_algo(self, sesion):
        """`HUECO_CATALOGO` es "te entendi y no lo tengo", y solo se gana algo
        frente a `SIN_MATCH` si se puede acompanar de una alternativa. Esta es
        la consulta que convierte una disculpa en una oferta."""
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
        """CASCADE aqui y RESTRICT en `producto_canonico`, y la asimetria es
        deliberada: un producto es un dato curado que sobrevive a la
        reorganizacion de su concepto, pero una arista a la que le falta un
        extremo no es nada que se pueda ofrecer."""
        oficio = crear_concepto(sesion, "block_oficio")
        carta = crear_concepto(sesion, "block_carta")
        _sustituir(sesion, oficio, carta)
        sesion.flush()

        sesion.delete(carta)
        sesion.flush()

        assert sesion.query(SustituibilidadConcepto).count() == 0
        assert sesion.query(Concepto).count() == 1
