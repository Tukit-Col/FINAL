"""Experimento A: tiempo de la enumeracion exacta y del NSGA-II segun el tamano del espacio.
Uso: uv run python ensayos/calibracion/umbral.py [--rapido]
Salida: ensayos/calibracion/salidas/umbral.json"""

from __future__ import annotations

import argparse
import random
import time
from concurrent.futures import ProcessPoolExecutor
from itertools import product

import nucleo as n
from tukit_inteligencia.optimizador import _frente_exacto, _frente_nsga, _no_dominadas, _solucion

NIVELES = list(range(6, 19))
SEMILLAS_HV = tuple(range(30))
SEMILLAS_TIEMPO = (0, 1, 2)
TOPE_ENUMERACION_S = 150.0


def subproblemas(por_nivel: int) -> list[dict]:
    insts = n.instancias()
    out = []
    for b in NIVELES:
        rng = random.Random(n.SEMILLA_BASE + b)
        orden = list(range(len(insts)))
        rng.shuffle(orden)
        k = por_nivel if b <= 14 else max(2, por_nivel - 2)
        hechos = 0
        for i in orden:
            sp = n.subproblema(n.renglones_de(insts[i]), b, rng)
            if sp is None:
                continue
            dec, ops = sp
            out.append({"bits": b, "instancia": insts[i]["id"], "ordenes": [r.orden for r in dec]})
            hechos += 1
            if hechos == k:
                break
    return out


def reconstruir(desc: dict):
    inst = next(i for i in n.instancias() if i["id"] == desc["instancia"])
    dec = [r for r in n.decidibles(n.renglones_de(inst)) if r.orden in set(desc["ordenes"])]
    return dec, n.opciones_de(dec)


def medir_exacto(dec, ops, repeticiones: int) -> dict:
    mejores = None
    for _ in range(repeticiones):
        t0 = time.perf_counter()
        sol = [_solucion(dec, list(c), {}) for c in product(*ops)]
        t1 = time.perf_counter()
        frente = _no_dominadas(sol)
        t2 = time.perf_counter()
        u = len({(s.costo, s.fidelidad, s.disponibilidad, s.personaje) for s in sol})
        fila = {"t_eval": t1 - t0, "t_filtro": t2 - t1, "t_total": t2 - t0, "U": u, "frente": len(frente)}
        if mejores is None or fila["t_total"] < mejores["t_total"]:
            mejores = fila
    return mejores


def _hv_semilla(args):
    desc, semilla = args
    dec, ops = reconstruir(desc)
    lo, hi = n.limites_costo(dec, ops)
    f = _frente_nsga(dec, ops, {}, semilla=semilla)
    return semilla, n.hipervolumen(f, lo, hi), len(f)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rapido", action="store_true", help="prueba: 1 subproblema por nivel, 3 semillas")
    ap.add_argument("--procesos", type=int, default=8)
    args = ap.parse_args()
    descs = subproblemas(1 if args.rapido else 5)
    semillas_hv = SEMILLAS_HV[:3] if args.rapido else SEMILLAS_HV

    d0, o0 = reconstruir(descs[0])
    _frente_nsga(d0, o0, {}, semilla=0)

    filas = []
    ultimo_t_exacto: dict[int, float] = {}
    for desc in descs:
        dec, ops = reconstruir(desc)
        b = desc["bits"]
        S = n.espacio_de(ops)
        fila = {**desc, "S": S, "lineas": len(dec)}
        previo = ultimo_t_exacto.get(b - 1)
        if previo is not None and previo > TOPE_ENUMERACION_S:
            fila["exacto"] = None
        else:
            rep = 3 if S <= 2**12 else 1
            fila["exacto"] = medir_exacto(dec, ops, rep)
            ultimo_t_exacto[b] = max(ultimo_t_exacto.get(b, 0.0), fila["exacto"]["t_total"])
        t0 = time.perf_counter()
        t_poda_ref = n.frente_exacto_por_podas(dec, ops, {})
        fila["t_poda_s"] = time.perf_counter() - t0
        fila["frente_poda"] = len(t_poda_ref)
        if fila["exacto"] is not None and S <= 2**16:
            igual = {
                (s.costo, s.fidelidad, s.disponibilidad, s.personaje) for s in _frente_exacto(dec, ops, {})
            } == {(s.costo, s.fidelidad, s.disponibilidad, s.personaje) for s in t_poda_ref}
            fila["poda_igual_a_enumeracion"] = igual
        tiempos = []
        for sem in SEMILLAS_TIEMPO:
            t0 = time.perf_counter()
            _frente_nsga(dec, ops, {}, semilla=sem)
            tiempos.append(time.perf_counter() - t0)
        fila["t_nsga_s"] = tiempos
        lo, hi = n.limites_costo(dec, ops)
        fila["hv_exacto"] = n.hipervolumen(t_poda_ref, lo, hi)
        filas.append(fila)
        print(
            b,
            S,
            fila["exacto"] and round(fila["exacto"]["t_total"], 3),
            round(sum(tiempos) / 3, 3),
            flush=True,
        )

    trabajos = [(d, s) for d in descs for s in semillas_hv]
    with ProcessPoolExecutor(max_workers=args.procesos) as ex:
        resultados = list(ex.map(_hv_semilla, trabajos, chunksize=4))
    k = 0
    for fila in filas:
        porcion = resultados[k : k + len(semillas_hv)]
        k += len(semillas_hv)
        fila["hv_nsga"] = [r[1] for r in porcion]
        fila["razon_hv"] = [r[1] / fila["hv_exacto"] if fila["hv_exacto"] > 0 else 1.0 for r in porcion]

    n.guardar(
        "umbral.json" if not args.rapido else "umbral_rapido.json",
        {
            "hardware": n.hardware(),
            "semillas_hv": list(semillas_hv),
            "referencia_hv": n.REFERENCIA,
            "filas": filas,
        },
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
