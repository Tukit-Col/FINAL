"""La programacion dinamica da el mismo frente que la fuerza bruta.

Repite la verificacion de la Observacion "Verificacion empirica" del documento
de algoritmos (300 instancias aleatorias de 2 a 6 lineas, con nivel, precio
-incluido sin precio-, empaque y personaje aleatorios) y la extiende a 1.000
instancias de hasta 8 lineas y a preferencias con personaje pedido. Ademas
comprueba la mochila de presupuesto contra la fuerza bruta.

    python test_dp.py          (o: python -m pytest test_dp.py)
"""

from __future__ import annotations

import itertools
import random

from algoritmos import dp_presupuesto, enumeracion, programacion_dinamica
from tukit_final import opt

NIVELES = opt.ORDEN_NIVEL
PERSONAJES = (None, None, None, "Frozen", "Spiderman")


def _instancia(rng: random.Random, n: int):
    renglones = []
    for i in range(n):
        k = rng.randint(1, 3)
        cands = tuple(
            opt.Candidato(
                sku=f"S{i}-{j}",
                nombre=f"p{i}{j}",
                nivel=rng.choice(NIVELES),
                precio_cop=None if rng.random() < 0.1 else rng.randrange(500, 40000, 100),
                personaje=rng.choice(PERSONAJES),
                unidades_por_empaque=rng.choice((1, 1, 1, 6, 12)),
            )
            for j in range(k)
        )
        renglones.append(
            opt.Renglon(
                hijo=rng.choice(("hijo-1", "hijo-2")),
                orden=i + 1,
                texto=f"r{i}",
                tipo_item="util",
                modo_adquisicion="mercado_abierto",
                cantidad=rng.randint(1, 13),
                estado_resolucion="RESUELTO_AUTO",
                candidatos=cands,
            )
        )
    return renglones


def _vectores(frente):
    return sorted((s.costo, s.fidelidad, s.disponibilidad, s.personaje) for s in frente)


def test_dp_igual_a_fuerza_bruta(casos: int = 1000) -> int:
    rng = random.Random(20261102)
    for caso in range(casos):
        renglones = _instancia(rng, rng.randint(2, 8))
        dec = [r for r in renglones if opt._admisibles(r)]
        opciones = [opt._admisibles(r) for r in dec]
        prefs = rng.choice(({}, {"personaje_por_hijo": {"hijo-1": ["Frozen"]}}))
        exacto = enumeracion(dec, opciones, prefs)
        dp = programacion_dinamica(dec, opciones, prefs)
        assert _vectores(exacto) == _vectores(dp), f"caso {caso}: frentes distintos"
        # Cada asignacion de la DP reproduce su vector con la funcion de produccion.
        for s in dp:
            elegidos = [next(c for c in o if c.sku == s.asignacion[(r.hijo, r.orden)]) for r, o in zip(dec, opciones)]
            assert opt._objetivos_de_asignacion(dec, elegidos, prefs) == (
                s.costo,
                s.fidelidad,
                s.disponibilidad,
                s.personaje,
            )
    return casos


def test_mochila_presupuesto(casos: int = 500) -> int:
    rng = random.Random(7)
    for caso in range(casos):
        renglones = _instancia(rng, rng.randint(1, 7))
        dec = [r for r in renglones if opt._admisibles(r)]
        opciones = [opt._admisibles(r) for r in dec]
        todos = [opt._solucion(dec, list(combo), {}) for combo in itertools.product(*opciones)]
        tope = rng.choice([s.costo for s in todos])
        caben = [s for s in todos if s.costo <= tope]
        mejor = max(caben, key=lambda s: (s.fidelidad, -s.costo))
        js = dp_presupuesto(dec, opciones, tope)
        assert js is not None
        s = opt._solucion(dec, [opciones[i][j] for i, j in enumerate(js)], {})
        assert (s.fidelidad, s.costo) == (mejor.fidelidad, mejor.costo), f"caso {caso}"
    return casos


if __name__ == "__main__":
    print("frente DP == fuerza bruta en", test_dp_igual_a_fuerza_bruta(), "instancias aleatorias")
    print("mochila DP == fuerza bruta en", test_mochila_presupuesto(), "instancias aleatorias")
