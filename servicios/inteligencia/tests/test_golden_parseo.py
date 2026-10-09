"""NFR-PRE-02: el parseo de cada renglon de los dorados, y la cantidad de punta a punta.

Cada renglon que sobrevive a la percepcion tiene en `datos/golden/esperado/`
el tipo de item, el modo de adquisicion, la cantidad en unidad base y el
empaque que el parseo tiene que sacar del texto. Entre ellos estan los casos
que la skill pide por nombre: `0` para "disponible en casa", la cantidad que
viene dentro del texto cuando la lista no tiene columna (G06), el empaque
"x 12" y la medida "30 cm" que no es una cantidad.

La segunda clase sigue la cantidad por el camino real del acudiente: la
percepcion aceptada pasa por `_items_desde_percepcion` (lo que la subida le
manda al catalogo) y luego por `_normalizar` (lo que el pipeline arma con la
lista). Lo que se exige es que el kit pida lo que dice la lista.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from tukit_inteligencia import api  # noqa: F401  el router solo se importa despues de `api` (ciclo)
from tukit_inteligencia.dominio.pipeline import _normalizar
from tukit_inteligencia.parseo import parsear_renglon
from tukit_inteligencia.percepcion import ItemExtraido, Percepcion
from tukit_inteligencia.routers import inteligencia as router_inteligencia

pytestmark = pytest.mark.nfr("NFR-PRE-02")

GOLDEN = Path(__file__).resolve().parents[3] / "datos" / "golden"
ESPERADOS = {
    ruta.stem: json.loads(ruta.read_text()) for ruta in sorted((GOLDEN / "esperado").glob("G*.json"))
}
ACEPTADAS = sorted(v for v, e in ESPERADOS.items() if e["aceptada"])
RENGLONES = [
    pytest.param(variante, item, fila, id=f"{variante}#{fila['orden']}")
    for variante in ACEPTADAS
    for item, fila in zip(ESPERADOS[variante]["items"], ESPERADOS[variante]["renglones"], strict=True)
]


class TestParseoPorRenglon:
    @pytest.mark.parametrize(("variante", "item", "fila"), RENGLONES)
    def test_el_parseo_da_lo_que_el_dorado_espera(self, variante, item, fila):
        demanda = parsear_renglon(item["descripcion"], cantidad=item["cantidad"])

        obtenido = {
            "tipo_item": demanda.tipo_item,
            "modo_adquisicion": demanda.modo_adquisicion,
            "cantidad": demanda.cantidad,
            "unidades_por_empaque": demanda.unidades_por_empaque,
        }
        assert obtenido == fila["parseo"]

    def test_las_seis_variantes_aceptadas_tienen_dieciocho_renglones(self):
        assert ACEPTADAS == ["G01", "G03", "G05", "G06", "G07", "G09"]
        assert {len(ESPERADOS[v]["renglones"]) for v in ACEPTADAS} == {18}

    def test_lo_disponible_en_casa_pide_cero_aunque_el_modelo_no_diga_cantidad(self):
        demanda = parsear_renglon("Diccionario de inglés: el disponible en casa", cantidad=None)

        assert (demanda.tipo_item, demanda.cantidad) == ("no_comprar", 0)
        assert demanda.nota

    def test_la_medida_no_se_confunde_con_la_cantidad(self):
        assert parsear_renglon("Regla de 30 cm", cantidad=None).cantidad == 1


def _percepcion(variante: str) -> Percepcion:
    esperado = ESPERADOS[variante]
    return Percepcion(
        aceptada=True,
        grados=tuple(esperado["grados"]),
        paginas=1,
        items=tuple(ItemExtraido(**i) for i in esperado["items"]),
    )


def _cantidades_del_pipeline(variante: str) -> list[int]:
    items, _ = router_inteligencia._items_desde_percepcion(_percepcion(variante))
    crudos = [
        {"hijo": "hijo-1", "orden": n, "texto": i["texto_original"], "cantidad": i["cantidad"]}
        for n, i in enumerate(items, start=1)
    ]
    return [r["cantidad"] for r in _normalizar(crudos)]


class TestLaCantidadLlegaAlKit:
    @pytest.mark.parametrize("variante", [v for v in ACEPTADAS if v != "G06"])
    def test_con_columna_de_cantidad_el_pipeline_pide_lo_que_dice_la_lista(self, variante, record_property):
        esperadas = [f["parseo"]["cantidad"] for f in ESPERADOS[variante]["renglones"]]

        obtenidas = _cantidades_del_pipeline(variante)

        record_property(
            "renglones_con_otra_cantidad", sum(a != b for a, b in zip(obtenidas, esperadas, strict=True))
        )
        assert obtenidas == esperadas

    @pytest.mark.xfail(
        strict=True,
        reason=(
            "H-A-38: la subida convierte la cantidad nula en 1 (`_items_desde_percepcion`) antes de que el "
            "parseo lea el numero del texto, y una lista sin columna de cantidad pide 1 de todo"
        ),
    )
    def test_sin_columna_de_cantidad_el_pipeline_lee_la_cantidad_del_texto(self, record_property):
        esperadas = [f["parseo"]["cantidad"] for f in ESPERADOS["G06"]["renglones"]]

        obtenidas = _cantidades_del_pipeline("G06")

        record_property(
            "renglones_con_otra_cantidad", sum(a != b for a, b in zip(obtenidas, esperadas, strict=True))
        )
        assert obtenidas == esperadas

    def test_el_parseo_solo_si_lee_la_cantidad_del_texto(self):
        """El control del xfail de arriba: el defecto esta en la subida, no en el parseo."""
        esperadas = [f["parseo"]["cantidad"] for f in ESPERADOS["G06"]["renglones"]]
        crudos = [
            {"hijo": "hijo-1", "orden": n, "texto": i["descripcion"], "cantidad": i["cantidad"]}
            for n, i in enumerate(ESPERADOS["G06"]["items"], start=1)
        ]

        assert [r["cantidad"] for r in _normalizar(crudos)] == esperadas
