"""NFR-PRE-01: dada la respuesta grabada del modelo, `percibir` devuelve la lista exacta.

Los dorados de `datos/golden/` (G01...G10) cambian el formato de la misma lista:
foto borrosa, manuscrito, sin columna de cantidad, fila partida, pagina
cortada, mayusculas, varios grados, un .docx y un PDF que pasa el tope. El
modelo no se llama: un `leer` falso busca la pagina por su sha256 en
`fixtures-modelo/indice.json` y devuelve la respuesta grabada, con el mismo
manejo de errores del adaptador (`gemini.py:97-110`).

Lo que se exige es igualdad fila por fila con `esperado/Gnn.json` y cero filas
inventadas: ninguna fila sale de `percibir` sin estar en la respuesta del
modelo. No se mide al modelo (eso pide llamarlo); se mide lo que el sistema
hace con lo que el modelo dijo.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from tukit_inteligencia import paginas
from tukit_inteligencia.percepcion import TOPE_PAGINAS, PaginaLeida, PercepcionFallida, percibir

pytestmark = pytest.mark.nfr("NFR-PRE-01")

RAIZ = Path(__file__).resolve().parents[3]
GOLDEN = RAIZ / "datos" / "golden"
INDICE: dict[str, str] = json.loads((GOLDEN / "fixtures-modelo" / "indice.json").read_text())
ESPERADOS = {
    ruta.stem: json.loads(ruta.read_text()) for ruta in sorted((GOLDEN / "esperado").glob("G*.json"))
}
CON_FIXTURE = sorted(v for v in ESPERADOS if v != "G02")


def _lector():
    """El `leer` de los dorados: responde lo grabado y cuenta las paginas que le llegan."""
    llamadas: list[str] = []

    def leer(png: bytes, numero: int) -> PaginaLeida:
        huella = hashlib.sha256(png).hexdigest()
        llamadas.append(huella)
        ruta = INDICE.get(huella)
        if ruta is None:
            raise AssertionError(f"la pagina {numero} no tiene fixture: el dorado no puede llamar al modelo")
        respuesta = json.loads((RAIZ / ruta).read_text())["respuesta_http"]
        if respuesta["status"] != 200:
            raise PercepcionFallida(
                f"Gemini respondio {respuesta['status']}: {str(respuesta['cuerpo'])[:300]}"
            )
        texto = respuesta["cuerpo"]["candidates"][0]["content"]["parts"][0]["text"]
        return PaginaLeida.model_validate_json(texto)

    leer.llamadas = llamadas
    return leer


def _contenido(variante: str) -> bytes:
    return (GOLDEN / ESPERADOS[variante]["archivo"]).read_bytes()


def _fixture(variante: str) -> dict:
    return json.loads((GOLDEN / "fixtures-modelo" / f"{variante}-p1.json").read_text())


def _filas(items) -> list[tuple[str, int | None, float | None]]:
    return [(i.descripcion, i.cantidad, i.confianza) for i in items]


class TestElDoradoEsCoherente:
    """Antes de medir nada: cada fixture apunta a su archivo y el indice los cubre todos."""

    @pytest.mark.parametrize("variante", CON_FIXTURE)
    def test_el_sha256_del_fixture_es_el_del_archivo_que_llega_a_leer(self, variante):
        fixture = _fixture(variante)
        assert fixture["sha256_pagina"] == hashlib.sha256(_contenido(variante)).hexdigest()
        assert INDICE[fixture["sha256_pagina"]] == f"datos/golden/fixtures-modelo/{variante}-p1.json"

    @pytest.mark.parametrize("variante", [v for v in CON_FIXTURE if v != "G04"])
    def test_la_respuesta_trae_explicitos_los_tres_campos_del_esquema(self, variante):
        texto = _fixture(variante)["respuesta_http"]["cuerpo"]["candidates"][0]["content"]["parts"][0]["text"]
        assert set(json.loads(texto)) == {"grados", "completa", "items"}

    def test_el_indice_no_tiene_entradas_huerfanas(self):
        assert sorted(INDICE.values()) == sorted(
            f"datos/golden/fixtures-modelo/{v}-p1.json" for v in CON_FIXTURE
        )


class TestFilaPorFila:
    @pytest.mark.parametrize("variante", CON_FIXTURE)
    def test_percibir_devuelve_exactamente_lo_esperado(self, variante, record_property):
        esperado = ESPERADOS[variante]
        leer = _lector()

        percepcion = percibir(_contenido(variante), renderizar=paginas.renderizar, leer=leer)

        assert percepcion.aceptada is esperado["aceptada"]
        assert percepcion.error == esperado["error"]
        assert list(percepcion.grados) == esperado["grados"]
        assert percepcion.paginas == esperado["paginas"]
        assert list(percepcion.degradaciones) == esperado["degradaciones"]
        obtenidas = _filas(percepcion.items)
        esperadas = [(i["descripcion"], i["cantidad"], i["confianza"]) for i in esperado["items"]]
        record_property("variante", variante)
        record_property("filas_esperadas", len(esperadas))
        record_property("filas_obtenidas", len(obtenidas))
        record_property(
            "filas_distintas", sum(1 for a, b in zip(obtenidas, esperadas, strict=False) if a != b)
        )
        assert obtenidas == esperadas
        assert len(leer.llamadas) == 1

    @pytest.mark.parametrize("variante", CON_FIXTURE)
    def test_ninguna_fila_sale_sin_estar_en_la_respuesta_del_modelo(self, variante, record_property):
        fixture = _fixture(variante)
        if fixture["respuesta_http"]["status"] == 200:
            texto = fixture["respuesta_http"]["cuerpo"]["candidates"][0]["content"]["parts"][0]["text"]
            leidas = _filas(PaginaLeida.model_validate_json(texto).items)
        else:
            leidas = []

        percepcion = percibir(_contenido(variante), renderizar=paginas.renderizar, leer=_lector())

        inventadas = [fila for fila in _filas(percepcion.items) if fila not in leidas]
        record_property("filas_inventadas", len(inventadas))
        assert inventadas == []

    def test_el_renglon_en_blanco_de_la_fila_partida_se_descarta(self):
        texto = _fixture("G07")["respuesta_http"]["cuerpo"]["candidates"][0]["content"]["parts"][0]["text"]
        assert any(not i["descripcion"].strip() for i in json.loads(texto)["items"])

        percepcion = percibir(_contenido("G07"), renderizar=paginas.renderizar, leer=_lector())

        assert all(i.descripcion.strip() for i in percepcion.items)
        assert percepcion.items[0].descripcion == "Cuaderno cuadriculado grande cosido de 100 hojas"

    def test_la_pagina_cortada_no_se_arma_con_lo_que_alcanzo_a_verse(self):
        percepcion = percibir(_contenido("G08"), renderizar=paginas.renderizar, leer=_lector())

        assert percepcion.aceptada is False
        assert percepcion.error == "pagina_incompleta"
        assert percepcion.degradaciones == ("pagina_1_incompleta",)

    def test_varios_grados_escritos_de_cuatro_formas_son_tres_grados(self):
        percepcion = percibir(_contenido("G10"), renderizar=paginas.renderizar, leer=_lector())

        assert percepcion.error == "lista_de_varios_grados"
        assert percepcion.grados == ("Cuarto", "Prejardin", "Tercero")
        assert "3 grados" in percepcion.mensaje

    def test_el_word_que_el_proveedor_rechaza_termina_en_percepcion_fallida(self):
        percepcion = percibir(_contenido("G04"), renderizar=paginas.renderizar, leer=_lector())

        assert percepcion.error == "percepcion_fallida"
        assert percepcion.degradaciones == ("gemini",)
        assert "Gemini respondio 400" in percepcion.mensaje
        assert percepcion.items == ()


class TestTopeDePaginas:
    """G02 tiene una pagina mas que el tope: se rechaza antes de llamar al modelo."""

    def test_con_el_render_inyectado_se_rechaza_sin_llamar_al_modelo(self, record_property):
        contenido = _contenido("G02")
        cuantas = contenido.count(b"/Type /Page ")
        leer = _lector()

        percepcion = percibir(
            contenido, renderizar=lambda _c: [f"pagina-{n}".encode() for n in range(cuantas)], leer=leer
        )

        record_property("paginas", cuantas)
        record_property("llamadas_al_modelo", len(leer.llamadas))
        assert cuantas == TOPE_PAGINAS + 1 == ESPERADOS["G02"]["paginas"]
        assert percepcion.error == ESPERADOS["G02"]["error"] == "archivo_demasiado_largo"
        assert leer.llamadas == []

    @pytest.mark.xfail(
        strict=True,
        reason=(
            "H-A-36: sin el extra `pdf` de inteligencia (pypdfium2), que ni `make preparar` ni el CI "
            "instalan, el render real devuelve pdf_ilegible y el tope no llega a evaluarse"
        ),
    )
    def test_con_el_render_real_el_pdf_largo_da_archivo_demasiado_largo(self):
        leer = _lector()

        percepcion = percibir(_contenido("G02"), renderizar=paginas.renderizar, leer=leer)

        assert percepcion.error == "archivo_demasiado_largo"
        assert leer.llamadas == []
