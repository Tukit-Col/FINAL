"""Corre el benchmark de optimización y guarda resultados en resultados/."""
import itertools
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from benchmarks.optimizer import (
    DEFAULT_WEIGHTS,
    PERFILES,
    generar_instancia,
    optimizar_exhaustivo,
    optimizar_greedy,
    optimizar_nsga2,
    optimizar_random,
    puntaje_global,
)

RAIZ = Path(__file__).resolve().parents[1]
RESULTADOS = RAIZ / "resultados"
RESULTADOS.mkdir(exist_ok=True)

INSTANCIAS = [
    {"nombre": "pequeña", "n_items": 4, "n_cand": 2, "semilla": 1},
    {"nombre": "mediana", "n_items": 6, "n_cand": 3, "semilla": 2},
    {"nombre": "grande", "n_items": 8, "n_cand": 3, "semilla": 3},
]


def main():
    filas = []
    for inst in INSTANCIAS:
        items = generar_instancia(inst["n_items"], inst["n_cand"], inst["semilla"])
        for perfil in PERFILES:
            f = DEFAULT_WEIGHTS[perfil]
            ex = optimizar_exhaustivo(items, perfil, inst["semilla"])
            greedy = optimizar_greedy(items, perfil, inst["semilla"])
            nsga = optimizar_nsga2(items, perfil, inst["semilla"])
            rnd = optimizar_random(items, perfil, semilla=inst["semilla"])

            # puntaje global (misma normalización = enumeración completa)
            p_ex = puntaje_global(items, ex, f)
            p_greedy = puntaje_global(items, greedy, f)
            p_nsga = puntaje_global(items, nsga, f)
            p_rnd = puntaje_global(items, rnd, f)

            def fila(sol, p):
                gap = round((p - p_ex) / p_ex * 100, 2) if p_ex else 0.0
                return {
                    "instancia": inst["nombre"], "perfil": perfil,
                    "metodo": sol["metodo"], "puntaje": round(p, 4),
                    "gap_vs_optimo_%": gap, "costo": round(sol["costo"], 2),
                    "fan": round(sol["fan"], 4), "quality": round(sol["quality"], 4),
                    "tiempo_s": sol["tiempo_s"],
                }

            for sol, p in [(ex, p_ex), (greedy, p_greedy), (nsga, p_nsga), (rnd, p_rnd)]:
                filas.append(fila(sol, p))
                print(fila(sol, p))

    with open(RESULTADOS / "optimizer.json", "w", encoding="utf-8") as fh:
        json.dump(filas, fh, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
