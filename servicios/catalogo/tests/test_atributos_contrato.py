"""Los atributos se parten en dos porque cumplen dos papeles distintos.

Medido contra las 4.719 lineas de lista del corpus, de los 155 pares
concepto-atributo declarados obligatorios solo 81 los pide alguna lista. Los
otros 74 describen el producto pero nadie los usa para pedirlo: la talla de
una bata de laboratorio depende del nino, no del colegio.

Tenerlos todos en un solo campo obligaba a elegir entre dos males. Usados
como restriccion dura, un atributo que ninguna lista pide y que casi ningun
producto declara descarta candidatos validos: pedir `bata de laboratorio` no
resolveria nada porque ninguna bata del catalogo dice su talla. Ignorados
todos, se pierde `rayado`, que 353 lineas especifican y que distingue un
cuaderno que sirve de uno que no.

De ahi los dos campos. `atributos_discriminantes` filtra; `atributos_
descriptivos` se le muestra al acudiente y no descarta a nadie.
"""

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
        # Vacio quiere decir "este concepto no discrimina por nada", que es
        # una afirmacion. Nulo obligaria a cada lector a decidir que significa.
        c = crear_concepto(sesion, "aserrin")
        assert c.atributos_discriminantes == []
        assert c.atributos_descriptivos == []

    def test_un_atributo_no_puede_filtrar_y_no_filtrar_a_la_vez(self, sesion):
        # Si `rayado` estuviera en los dos, el comportamiento dependeria de
        # cual lea primero el resolutor, y eso no es una regla sino un azar.
        with pytest.raises(ValueError, match="rayado"):
            crear_concepto(
                sesion,
                "cuaderno",
                atributos_discriminantes=["rayado"],
                atributos_descriptivos=["rayado"],
            )

    def test_el_error_nombra_el_atributo_culpable(self, sesion):
        # Un concepto curado a mano puede traer quince atributos. Decir solo
        # "hay solapamiento" obliga a compararlos a ojo.
        with pytest.raises(ValueError, match="hojas"):
            crear_concepto(
                sesion,
                "cuaderno",
                atributos_discriminantes=["rayado", "hojas"],
                atributos_descriptivos=["hojas", "materias"],
            )


class TestQueLaBaseTambienLoImpone:
    """El validador del ORM no alcanza: el cargador escribe con Core.

    Quien llena este catalogo es el cargador de CSV, que inserta con
    `insert()` y no pasa por los validadores del ORM. Si el invariante
    viviera solo en el modelo, la unica via que de verdad escribe datos
    seria justo la que no lo comprueba.
    """

    def test_hay_un_check_en_postgres(self):
        from tukit_catalogo.modelos import Concepto as C

        oyentes = [
            ddl
            for ddl in C.__table__.dispatch.after_create
            if "atributos_sin_solapar" in str(getattr(ddl, "element", ddl))
        ]
        assert oyentes, "falta el CHECK de solapamiento para postgresql"
        # Condicionada al dialecto: sin el `execute_if`, el operador `&&` de
        # Postgres llegaria a SQLite y ni la tabla se podria crear. Que esta
        # prueba y las de arriba corran es la evidencia de que SQLite si pudo:
        # comparten el `create_all` del conftest.
        assert oyentes[0]._should_execute is not None


class TestUnSoloLugarParaLosAtributos:
    """El campo unico se renombro, no se dejo al lado.

    Dejar `atributos_requeridos` conviviendo con los dos nuevos garantiza que
    algun lector siga consultando el viejo y se comporte distinto al resto sin
    que nada lo delate.
    """

    def test_el_concepto_no_tiene_atributos_requeridos(self):
        assert not hasattr(Concepto, "atributos_requeridos")
