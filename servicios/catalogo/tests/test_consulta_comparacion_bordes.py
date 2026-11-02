"""NFR-PRE-02: los bordes de la comparacion por atributo del ADR 0043, con el ADR como oraculo.

`test_afinamiento_kits.py` (del equipo) fija un caso por regla, casi siempre lejos del borde: 100
hojas donde piden 80, 26 cm donde piden 20, el lienzo de 30 x 25 frente al de 30 x 40. Aqui se
mira cada borde que el ADR escribe con numeros y los atributos de la lista que no tienen caso:

- `hojas`: «al menos lo pedido, a lo sumo el doble». El doble exacto cumple y uno mas no.
- `puntos`: «entre lo pedido y 2,2 veces». 2,2 veces exacto cumple.
- `longitud`: «entre 0,85 y 1,35 veces». Los dos extremos cumplen, en cualquier unidad de
  `_A_CM` (mm, cm, m, in), y lo que queda fuera por poco no.
- Medidas `a x b cm`: «menos de un 25 % por lado». El 25 % exacto ya no cumple, hacia arriba
  igual que hacia abajo, y la orientacion no importa.
- `colores`, `piezas`, `notas`, `gramaje`, `capacidad`: «al menos lo pedido», sin tope.
- Las equivalencias van en los dos sentidos, no se encadenan y no pasan de un atributo a otro.
- Lo que no es un numero no cumple un «al menos»: ni un booleano ni un `null`.

El ADR no dice nada de cambiar de unidad en un «al menos» (`1 kg` donde piden `500 g`). La prueba
de `TestLaUnidadDeLoQueSeMide` toma el texto del ADR («al menos lo pedido») como oraculo, igual
que `longitud` ya convierte; si el producto compara la unidad como texto, falla y queda como
candidato a hallazgo para la corrida.

Funciones puras, sin base ni red. Productos ficticios.
"""

from __future__ import annotations

import pytest
from tukit_catalogo.consulta import _cumple, _valor_cumple

pytestmark = pytest.mark.nfr("NFR-PRE-02")


def _p(atributos: dict) -> dict:
    return {"id": "qa-1", "sku": "QA-1", "nombre": "producto ficticio de QA", "atributos": atributos}


class TestLosBordesConNumero:
    @pytest.mark.parametrize(
        ("declarado", "cumple"),
        [(80, True), (160, True), (161, False), (79, False)],
        ids=["igual", "el-doble", "el-doble-mas-uno", "uno-menos"],
    )
    def test_hojas_hasta_el_doble_exacto(self, declarado, cumple):
        assert _cumple(_p({"hojas": declarado}), {"hojas": 80}) is cumple

    @pytest.mark.parametrize(
        ("declarado", "cumple"),
        [(400, True), (880, True), (881, False), (399, False)],
        ids=["igual", "2-2-veces", "2-2-veces-mas-uno", "uno-menos"],
    )
    def test_puntos_hasta_dos_coma_dos_veces(self, declarado, cumple):
        assert _cumple(_p({"puntos": declarado}), {"puntos": 400}) is cumple

    @pytest.mark.parametrize(
        ("declarado", "pedido", "cumple"),
        [
            ("17 cm", "20 cm", True),
            ("27 cm", "20 cm", True),
            ("16.9 cm", "20 cm", False),
            ("27.1 cm", "20 cm", False),
            ("170 mm", "20 cm", True),
            ("270 mm", "20 cm", True),
            ("0.3 m", "30 cm", True),
            ("12 in", "30 cm", True),
            ("6.5 in", "15 cm", True),
            ("3 m", "30 cm", False),
        ],
        ids=[
            "0-85",
            "1-35",
            "bajo-0-85",
            "sobre-1-35",
            "mm-0-85",
            "mm-1-35",
            "m-a-cm",
            "in-a-cm",
            "in-del-catalogo",
            "m-diez-veces",
        ],
    )
    def test_longitud_entre_0_85_y_1_35_en_cualquier_unidad(self, declarado, pedido, cumple):
        assert _cumple(_p({"longitud": declarado}), {"longitud": pedido}) is cumple

    @pytest.mark.parametrize(
        ("declarado", "cumple"),
        [
            ("20 x 25 cm", False),
            ("20 x 15 cm", False),
            ("20 x 24.9 cm", True),
            ("16 x 24 cm", True),
        ],
        ids=["25-por-ciento-arriba", "25-por-ciento-abajo", "bajo-el-25", "los-dos-lados-cerca"],
    )
    def test_medidas_menos_de_un_cuarto_por_lado(self, declarado, cumple):
        assert _cumple(_p({"tamano": declarado}), {"tamano": "20 x 20 cm"}) is cumple

    def test_la_orientacion_no_importa(self):
        assert _cumple(_p({"tamano": "30 x 20 cm"}), {"tamano": "20 x 30 cm"})
        assert _cumple(_p({"tamano": "32 x 22 cm"}), {"tamano": "20 x 30 cm"})


class TestAlMenosSinTope:
    @pytest.mark.parametrize(
        ("atributo", "mas", "pedido", "menos"),
        [
            ("colores", 48, 12, 10),
            ("piezas", 1000, 10, 9),
            ("notas", 100, 12, 11),
            ("unidades", 144, 12, 11),
            ("gramaje", "500 g", "125 g", "120 g"),
            ("capacidad", "1000 ml", "250 ml", "240 ml"),
        ],
    )
    def test_cualquier_cantidad_mayor_cumple_y_una_menor_no(self, atributo, mas, pedido, menos):
        assert _cumple(_p({atributo: mas}), {atributo: pedido})
        assert _cumple(_p({atributo: pedido}), {atributo: pedido})
        assert not _cumple(_p({atributo: menos}), {atributo: pedido})


class TestLaUnidadDeLoQueSeMide:
    # Candidato a hallazgo si falla: el ADR dice «al menos lo pedido» y `longitud` si convierte.
    @pytest.mark.parametrize(
        ("atributo", "declarado", "pedido"),
        [("gramaje", "1 kg", "500 g"), ("capacidad", "1 l", "500 ml")],
    )
    def test_mas_en_otra_unidad_es_al_menos_lo_pedido(self, atributo, declarado, pedido):
        assert _cumple(_p({atributo: declarado}), {atributo: pedido})

    @pytest.mark.parametrize(
        ("atributo", "declarado", "pedido"),
        [("gramaje", "100 g", "1 kg"), ("capacidad", "250 ml", "1 l")],
    )
    def test_menos_en_otra_unidad_no_cumple(self, atributo, declarado, pedido):
        assert not _cumple(_p({atributo: declarado}), {atributo: pedido})

    def test_una_longitud_sin_unidad_no_se_compara(self):
        assert not _valor_cumple("longitud", "20", "20 cm")


class TestLasEquivalencias:
    @pytest.mark.parametrize(
        ("atributo", "uno", "otro"),
        [
            ("tamano", "carta", "a4"),
            ("presentacion", "frasco", "tarro"),
            ("material", "plastico", "antifluido"),
            ("material", "acero", "metal"),
            ("tipo", "gigante", "jumbo"),
        ],
    )
    def test_van_en_los_dos_sentidos(self, atributo, uno, otro):
        assert _valor_cumple(atributo, uno, otro)
        assert _valor_cumple(atributo, otro, uno)

    def test_no_distinguen_mayusculas(self):
        assert _valor_cumple("tamano", "A4", "Carta")

    def test_no_se_encadenan(self):
        assert not _valor_cumple("material", "plastico", "metal")
        assert not _valor_cumple("material", "antifluido", "acero")

    def test_no_pasan_de_un_atributo_a_otro(self):
        assert not _valor_cumple("tamano", "frasco", "tarro")
        assert not _valor_cumple("presentacion", "carta", "a4")
        assert not _valor_cumple("color", "gigante", "jumbo")


class TestLoQueNoEsUnNumero:
    def test_un_booleano_no_es_una_cantidad(self):
        assert not _cumple(_p({"unidades": True}), {"unidades": 1})
        assert not _cumple(_p({"hojas": True}), {"hojas": 1})

    def test_declarar_null_no_es_declarar(self):
        assert not _cumple(_p({"hojas": None}), {"hojas": 80})

    def test_un_texto_que_no_empieza_por_cifra_no_cumple_un_al_menos(self):
        assert not _cumple(_p({"colores": "muchos"}), {"colores": 12})


def test_con_varios_atributos_tienen_que_cumplir_todos():
    producto = _p({"hojas": 100, "rayado": "cuadriculado", "tamano": "a4"})

    assert _cumple(producto, {"hojas": 80, "rayado": "cuadriculado", "tamano": "carta"})
    assert not _cumple(producto, {"hojas": 80, "rayado": "rayado", "tamano": "carta"})
    assert not _cumple(producto, {"hojas": 80, "rayado": "cuadriculado", "materias": 3})
