"""La percepcion lee todo o dice que no pudo. Nunca recorta callada.

El tope de cinco paginas que hubo antes devolvia un kit incompleto con la
misma forma que uno completo. Estas pruebas existen para que eso no tenga
por donde volver: el doble de paginas se leen todas, y un archivo con dos
grados se rechaza con los grados en la mano.
"""

from __future__ import annotations

import pytest
from tukit_inteligencia.percepcion import (
    TOPE_PAGINAS,
    ItemExtraido,
    PaginaLeida,
    PercepcionFallida,
    grados_distintos,
    normalizar_grado,
    percibir,
)


def _lector(paginas: dict[int, PaginaLeida]):
    llamadas: list[int] = []

    def leer(_png: bytes, numero: int) -> PaginaLeida:
        llamadas.append(numero)
        return paginas[numero]

    leer.llamadas = llamadas
    return leer


def _paginas(cuantas: int) -> list[bytes]:
    return [f"pagina-{n}".encode() for n in range(cuantas)]


class TestNoSeRecorta:
    def test_lee_todas_las_paginas_aunque_pasen_de_cinco(self):
        paginas = {
            n: PaginaLeida(grados=["Cuarto"], items=[ItemExtraido(descripcion=f"item {n}")])
            for n in range(1, 7)
        }
        lector = _lector(paginas)

        resultado = percibir(b"pdf", renderizar=lambda _c: _paginas(6), leer=lector)

        assert resultado.aceptada is True
        assert lector.llamadas == [1, 2, 3, 4, 5, 6]
        assert len(resultado.items) == 6

    def test_un_archivo_mas_largo_que_el_tope_no_llama_al_modelo(self):
        lector = _lector({})

        resultado = percibir(b"pdf", renderizar=lambda _c: _paginas(TOPE_PAGINAS + 1), leer=lector)

        assert resultado.aceptada is False
        assert resultado.error == "archivo_demasiado_largo"
        assert lector.llamadas == []

    def test_una_pagina_incompleta_no_se_hace_pasar_por_lista(self):
        lector = _lector(
            {1: PaginaLeida(grados=["Cuarto"], completa=False, items=[ItemExtraido(descripcion="lapiz")])}
        )

        resultado = percibir(b"pdf", renderizar=lambda _c: _paginas(1), leer=lector)

        assert resultado.aceptada is False
        assert resultado.error == "pagina_incompleta"
        assert resultado.items[0].descripcion == "lapiz"

    def test_si_el_modelo_falla_el_trabajo_falla(self):
        def leer(_png: bytes, _numero: int) -> PaginaLeida:
            raise PercepcionFallida("sin red")

        resultado = percibir(b"pdf", renderizar=lambda _c: _paginas(1), leer=leer)

        assert resultado.aceptada is False
        assert resultado.error == "percepcion_fallida"
        assert resultado.degradaciones == ("gemini",)


class TestUnArchivoEsUnGrado:
    def test_cuatro_y_cuarto_son_el_mismo_grado(self):
        assert normalizar_grado("4°") == normalizar_grado("Cuarto") == "Cuarto"

    def test_pre_jardin_es_un_solo_grado(self):
        assert normalizar_grado("PRE-JARDIN") == normalizar_grado("Prejardin") == "Prejardin"

    @pytest.mark.parametrize(
        "nombres",
        [["Cuarto", "4°", "cuarto de primaria"], ["Jardin"], []],
    )
    def test_un_solo_grado_se_acepta(self, nombres: list[str]):
        assert len(grados_distintos(nombres)) <= 1

    def test_dos_grados_se_rechazan_y_se_dicen(self):
        lector = _lector(
            {
                1: PaginaLeida(grados=["Cuarto"], items=[ItemExtraido(descripcion="lapiz")]),
                2: PaginaLeida(grados=["Quinto"], items=[ItemExtraido(descripcion="borrador")]),
            }
        )

        resultado = percibir(b"pdf", renderizar=lambda _c: _paginas(2), leer=lector)

        assert resultado.aceptada is False
        assert resultado.error == "lista_de_varios_grados"
        assert resultado.grados == ("Cuarto", "Quinto")
        assert "2 grados" in resultado.mensaje
