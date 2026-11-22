from __future__ import annotations

import pytest
from tukit_catalogo.enriquecer import (
    extraer_empaque,
)


class TestEmpaqueContraContenido:

    @pytest.mark.parametrize(
        ("nombre", "esperado"),
        [
            ("Lápices Kiut x 10 unidades", 10),
            ("Marcador delgado neón x12 unidades", 12),
            ("Paquete Esponja x2 Unds Arte", 2),
            ("Paquete Cartulina Octavos x25 Unds Negra", 25),
            ("Paquete Sobre Manila Amarillo X100 Gigante 27x37cm", 100),
            ("Paquete Carton Cartulina Octavo x25 Unds", 25),
            ("Paquete Forro Acetato Cuaderno Cosido X10 Azul", 10),
            ("Crayones Kores Jumbo x 12 Uds", 12),
        ],
    )
    def test_cuenta_los_empaques_de_verdad(self, nombre, esperado):
        assert extraer_empaque(nombre).unidades == esperado

    @pytest.mark.parametrize(
        ("nombre", "porque"),
        [
            ("Tarro Vinilo Payasito x1000 Gramos Azul", "1000 gramos es contenido, no mil tarros"),
            ("Rollo Plastico Burbuja X50 Metros 25 Centimetros", "50 metros es largo, no 50 rollos"),
            ("Pegamento líquido Glukids x 250 g", "250 gramos es contenido"),
            ("Óleo N.° 37 de 37 ml verde", "el 37 es el numero de color y los ml son contenido"),
            ("Portaminas 2Mm FINLANDEK", "2 mm es el grosor de la mina"),
            ("Lienzo con bastidor con grapa posterior 20 x 30 cm", "20 x 30 es una medida"),
            ("Acetato para stencil 30,5 x 30,5 cm", "medida con coma decimal"),
            ("Pegante en Barra  Avengers 40 Grs", "40 gramos es contenido"),
        ],
    )
    def test_no_confunde_una_medida_con_un_empaque(self, nombre, porque):
        assert extraer_empaque(nombre).unidades == 1, porque

    def test_el_caso_de_los_dos_doces(self):
        empaque = extraer_empaque("Témpera gouache de colores de 12 ml x 12 unidades")
        assert empaque.unidades == 12
        assert empaque.unidad_base == "unidad"

    def test_toma_el_conteo_y_no_la_longitud_cuando_vienen_los_dos(self):
        assert extraer_empaque("Taco De Cinta Aislante Cellux 18mm X5 Metros X10 Unds Negra").unidades == 10


class TestHojasSegunElConcepto:

    def test_las_hojas_de_un_cuaderno_no_son_cien_cuadernos(self):
        empaque = extraer_empaque(
            "Cuaderno cosido doble línea de 100 hojas (surtido)",
            atributos_del_concepto=("hojas", "rayado", "materias"),
        )
        assert empaque.unidades == 1
        assert empaque.unidad_base == "unidad"

    def test_las_hojas_de_un_acetato_si_son_el_paquete(self):
        empaque = extraer_empaque(
            "Acetato calibre 10 por 5 hojas", atributos_del_concepto=("calibre", "tamano")
        )
        assert empaque.unidades == 5
        assert empaque.unidad_base == "hoja"

    def test_el_cuaderno_argollado_tampoco_son_cien(self):
        empaque = extraer_empaque(
            "Cuaderno De Arte Bond Tapa Dura Surtido Media Carta X 40 Hj",
            atributos_del_concepto=("hojas", "rayado", "materias"),
        )
        assert empaque.unidades == 1

    def test_sin_saber_el_concepto_las_hojas_cuentan(self):
        assert extraer_empaque("Block cuadriculado por 50 hojas").unidades == 50


class TestColoresComoConteo:
    def test_una_caja_de_doce_colores_trae_doce(self):
        assert extraer_empaque("Colores Faber Castell x 12 colores").unidades == 12

    def test_lentejuelas_de_nueve_colores(self):
        assert extraer_empaque("Paquete Lentejuelas x9 Colores (Metro por Color) Surtido").unidades == 9


class TestEmpaqueEscritoDeOtroModo:
    def test_la_x_pegada_a_un_punto_es_empaque(self):
        assert extraer_empaque("Resaltadores..neon.x5 KIUT").unidades == 5

    def test_paquete_de_doce_sin_la_x(self):
        assert extraer_empaque("Lápices De Colores Lego Con Topper, Paquete De 12").unidades == 12
        assert extraer_empaque("Caja de 24 crayones").unidades == 24

    def test_una_caja_que_no_dice_cuantos_es_una(self):
        assert extraer_empaque("Caja matemática: 1 compas, reglas, 1 tajalápiz (surtido)").unidades == 1
