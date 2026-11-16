"""Barrido de hogares (2 a 8 hijos): PD con consolidacion vs NSGA-II vs linea base.

uv run python ensayos/acoplado/correr_hermanos.py [--procesos 6] [--limite N]
Escribe hermanos.json.
"""

from __future__ import annotations

import argparse
import json
import random
import statistics as st
import time
import tracemalloc
from concurrent.futures import ProcessPoolExecutor

LIMITE_PD_S = 20.0
TOPE_CAPA = 2_000_000
SEMILLAS = (0, 1, 2)
TAMANOS_SINT = {2: 4, 3: 4, 4: 4, 5: 3, 6: 3, 7: 3, 8: 3}  # 24 hogares
SEMILLA_HOGARES = 20261113


def hogares(instancias):
    rng = random.Random(SEMILLA_HOGARES)
    out = []
    for k, cuantos in TAMANOS_SINT.items():
        for m in range(cuantos):
            ids = rng.sample(range(len(instancias)), k)
            out.append({"id": f"sint-{k}-{m}", "tipo": "sintetico", "hijos": k, "indices": ids})
    por_col: dict[str, list[int]] = {}
    for i, inst in enumerate(instancias):
        por_col.setdefault(inst["colegio"], []).append(i)
    grandes = sorted(c for c, v in por_col.items() if len(v) >= 8)
    for k in range(2, 9):
        for m in range(2):
            col = grandes[(k * 2 + m) % len(grandes)]
            ids = rng.sample(por_col[col], k)  # grados distintos del mismo colegio
            out.append({"id": f"col-{k}-{m}", "tipo": "mismo_colegio", "colegio": col, "hijos": k, "indices": ids})
    return out


def _memoria(fn):
    tracemalloc.start()
    try:
        fn()
    except Exception:  # noqa: BLE001
        pass
    pico = tracemalloc.get_traced_memory()[1]
    tracemalloc.stop()
    return pico / 2**20


def trabajo(args):
    desc, con_memoria = args
    from comun import cargar_json
    from hermanos import Hogar, Tiempo, armar_hogar, base_hogar, nsga_hogar, pd_hogar

    ins = cargar_json("instancias.json.gz")["instancias"]
    h = Hogar(armar_hogar([ins[i] for i in desc["indices"]]))
    A0 = h.costo(h.heuristica("ahorrador"))
    P0 = h.costo(h.heuristica("premium"))
    B = (A0 + P0) // 2  # mitad de camino, como `_tope_de_a_tu_medida`
    fila = dict(desc, lineas=h.n, compartidos=h.K, A0=A0, P0=P0, presupuesto=B, cota_inf=round(h.cota_inferior_ahorrador()))
    rng = random.Random(1)
    mal = 0
    for _ in range(5):
        idx = [rng.randrange(len(f)) for f in h.cand]
        mal += h.costo(idx) != h.total_armar_kit(idx)
    fila["valid_desajustes_de_5"] = mal

    def pd(modo, tope):
        t = time.perf_counter()
        try:
            r, est = pd_hogar(h, modo, tope, limite_s=LIMITE_PD_S, tope_capa=TOPE_CAPA)
            return {"estado": "ok" if r else "infactible", "s": time.perf_counter() - t, "estados": est,
                    "fid": None if not r or modo == "costo" else r[0] / (h.n * 2), "costo": r[1] if r else None}
        except Tiempo as e:
            return {"estado": e.args[1], "s": time.perf_counter() - t, "estados": int(e.args[0]), "fid": None, "costo": None}

    fila["pd_costo"] = pd("costo", A0)
    fila["pd_pres"] = pd("presupuesto", B)
    fila["ns"], fila["base"] = [], []
    for sem in SEMILLAS:
        t = time.perf_counter()
        a, b, ev = nsga_hogar(h, B, sem)
        fila["ns"].append({"semilla": sem, "s": time.perf_counter() - t, "evals": ev,
                           "ah_costo": a[1], "ah_fid": a[0], "pr_fid": b and b[0], "pr_costo": b and b[1]})
        t = time.perf_counter()
        a, b = base_hogar(h, B, sem)
        fila["base"].append({"semilla": sem, "s": time.perf_counter() - t,
                             "ah_costo": a[1], "ah_fid": a[0], "pr_fid": b and b[0], "pr_costo": b and b[1],
                             "pr_sin_consolidar": b and h.costo_sin_consolidar(b[2])})
    if con_memoria:
        fila["mem_pd_pico_mib"] = _memoria(lambda: pd_hogar(h, "presupuesto", B, limite_s=LIMITE_PD_S, tope_capa=TOPE_CAPA))
        fila["mem_ns_pico_mib"] = _memoria(lambda: nsga_hogar(h, B, 0))
    return fila


def main():
    from acoplado import AQUI
    from comun import cargar_json, guardar_json

    ap = argparse.ArgumentParser()
    ap.add_argument("--procesos", type=int, default=6)
    ap.add_argument("--limite", type=int, default=None)
    a = ap.parse_args()
    ins = cargar_json("instancias.json.gz")["instancias"]
    hs = hogares(ins)
    if a.limite:
        hs = hs[: a.limite]
    vistos = set()
    trabajos = []
    for d in hs:
        mem = d["tipo"] == "sintetico" and d["hijos"] not in vistos
        vistos.add(d["hijos"]) if d["tipo"] == "sintetico" else None
        trabajos.append((d, mem))
    t0 = time.perf_counter()
    with ProcessPoolExecutor(a.procesos) as ex:
        filas = list(ex.map(trabajo, trabajos))
    total = time.perf_counter() - t0
    guardar_json("hermanos.json", {"config": {"limite_pd_s": LIMITE_PD_S, "tope_capa_estados": TOPE_CAPA,
                                              "semillas": list(SEMILLAS), "hogares": len(filas), "segundos_totales": total,
                                              "presupuesto": "(Ahorrador + Premium)/2 de la heuristica, ya consolidados"},
                                   "filas": filas}, AQUI)
    print(f"{len(filas)} hogares en {total:.0f} s")


if __name__ == "__main__":
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parent))
    main()
