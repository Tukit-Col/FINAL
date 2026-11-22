from __future__ import annotations

import pytest
from conftest import crear_concepto
from tukit_catalogo.modelos import Concepto


class TestLosDosPapelesDeUnAtributo:
    def test_un_concepto_puede_declarar_los_dos(self, sesion):
        c = crear_concepto(
            sesion,
            "cuaderno",
            atributos_discriminantes=["rayado", "hojas"],
            atributos_descriptivos=["materias"],
        )
        assert c.atributos_discriminantes == ["rayado", "hojas"]
        assert c.atributos_descriptivos == ["materias"]

    def test_los_dos_campos_empiezan_vacios_y_no_en_nulo(self, sesion):
        c = crear_concepto(sesion, "aserrin")
        assert c.atributos_discriminantes == []
        assert c.atributos_descriptivos == []

    def test_un_atributo_no_puede_filtrar_y_no_filtrar_a_la_vez(self, sesion):
        with pytest.raises(ValueError, match="rayado"):
            crear_concepto(
                sesion,
                "cuaderno",
                atributos_discriminantes=["rayado"],
                atributos_descriptivos=["rayado"],
            )

    def test_el_error_nombra_el_atributo_culpable(self, sesion):
        with pytest.raises(ValueError, match="hojas"):
            crear_concepto(
                sesion,
                "cuaderno",
                atributos_discriminantes=["rayado", "hojas"],
                atributos_descriptivos=["hojas", "materias"],
            )


class TestQueLaBaseTambienLoImpone:
    def test_hay_un_check_en_postgres(self):
        from tukit_catalogo.modelos import Concepto as C

        oyentes = [
            ddl
            for ddl in C.__table__.dispatch.after_create
            if "atributos_sin_solapar" in str(getattr(ddl, "element", ddl))
        ]
        assert oyentes, "falta el CHECK de solapamiento para postgresql"
        assert oyentes[0]._should_execute is not None


class TestUnSoloLugarParaLosAtributos:
    def test_el_concepto_no_tiene_atributos_requeridos(self):
        assert not hasattr(Concepto, "atributos_requeridos")
