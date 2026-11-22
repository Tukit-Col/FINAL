"""El techo del benchmark tiene que ser de verdad el techo."""

from __future__ import annotations

import random
import sys
from itertools import product
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

import comun  # noqa: E402
from tukit_inteligencia.optimizador import Candidato, Renglon  # noqa: E402

NIVELES = ("economico", "confiable", "premium")


def _lista(rng: random.Random, n: int) -> list[Renglon]:
    renglones = []
    for orden in range(1, n + 1):
        candidatos = tuple(
            Candidato(
                sku=f"s{orden}-{k}",
                nombre=f"producto {orden}-{k}",
                nivel=rng.choice(NIVELES),
                precio_cop=rng.randrange(1000, 20000, 500),
                personaje=rng.choice([None, None, "bluey", "cars"]),
                unidades_por_empaque=rng.choice([1, 1, 2, 12]),
            )
            for k in range(rng.randint(1, 3))
        )
        renglones.append(
            Renglon(
                hijo=comun.HIJO,
                orden=orden,
                texto=f"renglon {orden}",
                tipo_item="util",
                modo_adquisicion="mercado_abierto",
                cantidad=rng.randint(1, 6),
                estado_resolucion="resuelto_auto",
                candidatos=candidatos,
            )
        )
    return renglones


def _todas(dec: list[Renglon]):
    for combo in product(*(r.candidatos for r in dec)):
        yield {str(r.orden): c.sku for r, c in zip(dec, combo, strict=True)}


@pytest.mark.parametrize("semilla", range(25))
def test_los_optimos_igualan_a_la_fuerza_bruta(semilla):
    rng = random.Random(semilla)
    dec = comun.decidibles(_lista(rng, rng.randint(2, 6)))
    todas = [(a, comun.objetivos(dec, a, {})) for a in _todas(dec)]

    oa = comun.objetivos(dec, comun.optimo_ahorrador(dec), {})
    assert oa["costo"] == min(o["costo"] for _, o in todas)

    op = comun.objetivos(dec, comun.optimo_premium(dec), {})
    fid_max = max(o["fidelidad"] for _, o in todas)
    assert op["fidelidad"] == fid_max
    assert op["costo"] == min(o["costo"] for _, o in todas if o["fidelidad"] == fid_max)

    prefs = {"personaje_por_hijo": {comun.HIJO: ["bluey"]}}
    of = comun.objetivos(dec, comun.optimo_fan(dec, {"bluey"}), prefs)
    con_pers = [comun.objetivos(dec, a, prefs) for a, _ in todas]
    pers_max = max(o["personaje"] for o in con_pers)
    assert of["personaje"] == pers_max
    assert of["costo"] == min(o["costo"] for o in con_pers if o["personaje"] == pers_max)

    tope = int((oa["costo"] + op["costo"]) / 2)
    ob = comun.objetivos(dec, comun.optimo_presupuesto(dec, tope), {})
    caben = [o for _, o in todas if o["costo"] <= tope]
    assert ob["costo"] <= tope
    assert ob["fidelidad"] == max(o["fidelidad"] for o in caben)


def test_presupuesto_imposible_devuelve_none():
    rng = random.Random(99)
    dec = comun.decidibles(_lista(rng, 4))
    assert comun.optimo_presupuesto(dec, 0) is None


def test_domina_respeta_los_sentidos_de_cada_eje():
    base = {"costo": 100, "fidelidad": 0.5, "disponibilidad": 1.0, "personaje": 0.0}
    assert comun.domina({**base, "costo": 90}, base)
    assert comun.domina({**base, "fidelidad": 0.6}, base)
    assert not comun.domina(base, base)
    assert not comun.domina({**base, "costo": 90, "fidelidad": 0.4}, base)
