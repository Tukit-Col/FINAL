from __future__ import annotations

import uuid
from datetime import timedelta

import pytest
from conftest import ahora, crear_edicion, en_dias
from sqlalchemy.exc import IntegrityError
from tukit_catalogo.modelos import (
    ConfiguracionColegioEditorial,
    PropuestaVersion,
    VersionVigente,
)

COLEGIO = uuid.UUID("00000000-0000-0000-0000-00000000c01e")
RECTOR = uuid.UUID("00000000-0000-0000-0000-00000000000r".replace("r", "9"))


def _propuesta(sesion, edicion, **kw) -> PropuestaVersion:
    p = PropuestaVersion(
        colegio_id=kw.pop("colegio_id", COLEGIO),
        edicion_propuesta_id=edicion.id,
        area=kw.pop("area", "matematicas"),
        grado=kw.pop("grado", "5"),
        anio_lectivo=kw.pop("anio_lectivo", 2026),
        vence_en=kw.pop("vence_en", en_dias(3)),
        **kw,
    )
    sesion.add(p)
    sesion.flush()
    return p


class TestVentanaDeDecision:
    def test_el_colegio_fija_su_ventana_una_vez_en_vez_de_decidir_bajo_presion(self, sesion):
        config = ConfiguracionColegioEditorial(colegio_id=COLEGIO)
        sesion.add(config)
        sesion.flush()

        assert config.dias_ventana_decision == 3

    def test_el_silencio_conserva_la_edicion_vigente_y_no_acepta_la_nueva(self, sesion):
        config = ConfiguracionColegioEditorial(colegio_id=COLEGIO)
        sesion.add(config)
        sesion.flush()
        assert config.politica_silencio == "conservar_vigente"

    def test_una_ventana_que_vence_antes_de_empezar_se_rechaza(self, sesion):
        edicion = crear_edicion(sesion, "9789580000001")
        with pytest.raises(IntegrityError):
            _propuesta(sesion, edicion, vence_en=ahora() - timedelta(days=1))

    def test_las_propuestas_por_vencer_se_pueden_consultar(self, sesion):
        manana = crear_edicion(sesion, "9789580000002")
        lejana = crear_edicion(sesion, "9789580000003")
        _propuesta(sesion, manana, vence_en=en_dias(1))
        _propuesta(sesion, lejana, vence_en=en_dias(20), grado="7")

        urgentes = (
            sesion.query(PropuestaVersion)
            .filter(PropuestaVersion.estado == "pendiente", PropuestaVersion.vence_en <= en_dias(2))
            .all()
        )
        assert len(urgentes) == 1
        assert urgentes[0].edicion_propuesta_id == manana.id


class TestCostoDeEvaluar:
    def test_la_propuesta_llega_con_la_comparacion_hecha(self, sesion):
        actual = crear_edicion(sesion, "9789580000010", anio_edicion=2023)
        nueva = crear_edicion(sesion, "9789580000011", anio_edicion=2026)
        p = _propuesta(
            sesion,
            nueva,
            edicion_actual_id=actual.id,
            justificacion="Actualiza el capitulo de estadistica",
            delta_precio_centavos=12_000,
        )

        assert p.edicion_actual_id == actual.id
        assert p.delta_precio_centavos == 12_000

    def test_una_propuesta_que_no_cambia_de_edicion_se_rechaza(self, sesion):
        misma = crear_edicion(sesion, "9789580000012")
        with pytest.raises(IntegrityError):
            _propuesta(sesion, misma, edicion_actual_id=misma.id)

    def test_no_se_puede_proponer_dos_veces_la_misma_edicion(self, sesion):
        nueva = crear_edicion(sesion, "9789580000013")
        _propuesta(sesion, nueva)
        with pytest.raises(IntegrityError):
            _propuesta(sesion, nueva)

    def test_una_propuesta_resuelta_sabe_quien_la_resolvio(self, sesion):
        nueva = crear_edicion(sesion, "9789580000014")
        p = _propuesta(sesion, nueva)
        p.estado = "aceptada"
        p.resuelta_en = ahora()

        with pytest.raises(IntegrityError):
            sesion.flush()

    def test_una_propuesta_vencida_es_el_unico_desenlace_sin_persona_detras(self, sesion):
        nueva = crear_edicion(sesion, "9789580000015")
        p = _propuesta(sesion, nueva)
        p.estado = "vencida"
        sesion.flush()
        assert p.resuelta_por is None


class TestBachilleratoInternacional:
    def test_el_programa_es_columna_y_no_texto_suelto(self, sesion):
        bi = crear_edicion(sesion, "9789580000020", programa="bachillerato_internacional")
        assert bi.programa == "bachillerato_internacional"

    def test_se_puede_medir_la_cobertura_por_programa(self, sesion):
        for i, programa in enumerate(["nacional", "nacional", "bachillerato_internacional"]):
            crear_edicion(sesion, f"978958000003{i}", programa=programa)

        from tukit_catalogo.modelos import EdicionLibro

        por_programa: dict[str, int] = {}
        for e in sesion.query(EdicionLibro):
            por_programa[e.programa] = por_programa.get(e.programa, 0) + 1

        assert por_programa == {"nacional": 2, "bachillerato_internacional": 1}

    def test_un_programa_inventado_se_rechaza(self, sesion):
        with pytest.raises(IntegrityError):
            crear_edicion(sesion, "9789580000040", programa="montessori")


class TestEdicionVigente:
    def test_un_colegio_tiene_una_sola_edicion_vigente_por_area_grado_y_anio(self, sesion):
        a = crear_edicion(sesion, "9789580000050")
        b = crear_edicion(sesion, "9789580000051")
        for edicion in (a, b):
            sesion.add(
                VersionVigente(
                    colegio_id=COLEGIO,
                    edicion_id=edicion.id,
                    area="matematicas",
                    grado="5",
                    anio_lectivo=2026,
                )
            )
        with pytest.raises(IntegrityError):
            sesion.flush()

    def test_cerrar_la_vigencia_anterior_permite_la_nueva_y_conserva_el_historial(self, sesion):
        vieja = crear_edicion(sesion, "9789580000060", anio_edicion=2023)
        nueva = crear_edicion(sesion, "9789580000061", anio_edicion=2026)

        v1 = VersionVigente(
            colegio_id=COLEGIO, edicion_id=vieja.id, area="matematicas", grado="5", anio_lectivo=2026
        )
        sesion.add(v1)
        sesion.flush()

        v1.vigente_hasta = ahora()
        sesion.add(
            VersionVigente(
                colegio_id=COLEGIO, edicion_id=nueva.id, area="matematicas", grado="5", anio_lectivo=2026
            )
        )
        sesion.flush()

        assert sesion.query(VersionVigente).count() == 2
        vigentes = [v for v in sesion.query(VersionVigente) if v.vigente_hasta is None]
        assert len(vigentes) == 1
        assert vigentes[0].edicion_id == nueva.id

    def test_no_se_puede_borrar_una_edicion_que_algun_colegio_usa(self, sesion):
        edicion = crear_edicion(sesion, "9789580000070")
        sesion.add(
            VersionVigente(
                colegio_id=COLEGIO, edicion_id=edicion.id, area="matematicas", grado="5", anio_lectivo=2026
            )
        )
        sesion.flush()
        sesion.delete(edicion)
        with pytest.raises(IntegrityError):
            sesion.flush()

    def test_una_edicion_no_puede_reemplazarse_a_si_misma(self, sesion):
        edicion = crear_edicion(sesion, "9789580000080")
        edicion.reemplazada_por_id = edicion.id
        with pytest.raises(IntegrityError):
            sesion.flush()

    def test_una_edicion_descontinuada_apunta_a_su_reemplazo(self, sesion):
        vieja = crear_edicion(sesion, "9789580000090", anio_edicion=2023)
        nueva = crear_edicion(sesion, "9789580000091", anio_edicion=2026)
        vieja.descontinuada_en = ahora().date()
        vieja.reemplazada_por_id = nueva.id
        sesion.flush()

        assert vieja.reemplazada_por_id == nueva.id
