"""Experimento B: poblacion y generaciones del NSGA-II, con particion por colegio.
Uso: uv run python ensayos/calibracion/calibrar_nsga.py [--rapido]
Salida: ensayos/calibracion/salidas/calibracion_nsga.json"""

from __future__ import annotations

import argparse
import math
import random
import time
from concurrent.futures import ProcessPoolExecutor
from itertools import product

import nucleo as n
import numpy as np
from scipy import stats
from tukit_inteligencia import optimizador as opt

FACTORES = (0.25, 0.5, 1.0, 2.0)
UMBRAL_HV = 0.001


PARTIDA = {
    "pob_por_linea": 12,
    "pob_min": 40,
    "pob_max": 200,
    "gen_por_decada": 20,
    "gen_min": 30,
    "gen_max": 120,
}


def poblacion_con(a: float):
    def f(nlineas: int) -> int:
        p = PARTIDA
        cruda = min(a * p["pob_max"], max(a * p["pob_min"], a * p["pob_por_linea"] * nlineas))
        cruda = max(4, int(round(cruda)))
        return cruda + (cruda & 1)

    return f


def generaciones_con(b: float):
    def f(espacio: int) -> int:
        p = PARTIDA
        crudas = b * p["gen_por_decada"] * math.log10(max(10, espacio))
        return max(2, int(min(b * p["gen_max"], max(b * p["gen_min"], crudas))))

    return f


def _colegios(insts: list[dict]) -> dict[str, list[str]]:
    por_colegio: dict[str, list[str]] = {}
    for i in insts:
        por_colegio.setdefault(i["colegio"], []).append(i["id"])
    return por_colegio


def particion(insts: list[dict], pliegues: int) -> dict:
    por_colegio = _colegios(insts)
    colegios = sorted(por_colegio)
    random.Random(n.SEMILLA_BASE).shuffle(colegios)
    total = sum(len(v) for v in por_colegio.values())
    prueba: list[str] = []
    resto: list[str] = []
    for c in colegios:
        if sum(len(por_colegio[x]) for x in prueba) < 0.2 * total:
            prueba.append(c)
        else:
            resto.append(c)
    grupos: list[list[str]] = [[] for _ in range(pliegues)]
    for c in sorted(resto, key=lambda c: -len(por_colegio[c])):
        k = min(range(pliegues), key=lambda j: (sum(len(por_colegio[x]) for x in grupos[j]), j))
        grupos[k].append(c)
    return {
        "prueba": [i for c in prueba for i in por_colegio[c]],
        "colegios_prueba": prueba,
        "pliegues": [[i for c in g for i in por_colegio[c]] for g in grupos],
        "colegios_pliegues": grupos,
    }


def cargar(id_lista: str):
    inst = next(i for i in n.instancias() if i["id"] == id_lista)
    dec = n.decidibles(n.renglones_de(inst))
    return dec, n.opciones_de(dec)


def _referencia(id_lista: str):
    dec, ops = cargar(id_lista)
    lo, hi = n.limites_costo(dec, ops)
    return dec, ops, lo, hi, n.hipervolumen(n.frente_exacto_por_podas(dec, ops, {}), lo, hi)


def _trabajo(args):
    id_lista, a, b, semillas = args
    opt._poblacion = poblacion_con(a)
    opt._generaciones = generaciones_con(b)
    dec, ops, lo, hi, hv_ref = _referencia(id_lista)
    razones, tiempos = [], []
    for s in semillas:
        t0 = time.perf_counter()
        f = opt._frente_nsga(dec, ops, {}, semilla=s)
        tiempos.append(time.perf_counter() - t0)
        razones.append(n.hipervolumen(f, lo, hi) / hv_ref if hv_ref > 0 else 1.0)
    evals = opt._poblacion(len(dec)) * opt._generaciones(n.espacio_de(ops))
    return {"lista": id_lista, "a": a, "b": b, "razon": razones, "t": tiempos, "evals": evals}


def correr_rejilla(ids: list[str], semillas, procesos: int) -> list[dict]:
    trabajos = [(i, a, b, semillas) for i in ids for a, b in product(FACTORES, FACTORES)]
    with ProcessPoolExecutor(max_workers=procesos) as ex:
        return list(ex.map(_trabajo, trabajos, chunksize=8))


def resumen_por_config(filas: list[dict]) -> list[dict]:
    out = []
    for a, b in product(FACTORES, FACTORES):
        fs = [f for f in filas if f["a"] == a and f["b"] == b]
        por_lista = [float(np.mean(f["razon"])) for f in fs]
        out.append(
            {
                "a": a,
                "b": b,
                "listas": len(fs),
                "hv_medio": float(np.mean(por_lista)),
                "hv_min_lista": float(np.min(por_lista)),
                "t_medio_s": float(np.mean([np.mean(f["t"]) for f in fs])),
                "evals_medios": float(np.mean([f["evals"] for f in fs])),
            }
        )
    return out


def elegir(res_val: list[dict]) -> dict:
    mejor = max(r["hv_medio"] for r in res_val)
    admisibles = [r for r in res_val if r["hv_medio"] >= mejor - UMBRAL_HV]
    return min(admisibles, key=lambda r: (r["evals_medios"], -r["hv_medio"]))


def ic_bootstrap(x: np.ndarray, rng: np.random.Generator, k: int = 10_000) -> list[float]:
    medias = [x[rng.integers(0, len(x), len(x))].mean() for _ in range(k)]
    return [float(v) for v in np.percentile(medias, [2.5, 97.5])]


def _resumen_prueba(hv: np.ndarray, t: np.ndarray, filas: list[dict]) -> dict:
    return {
        "hv_medio": float(hv.mean()),
        "hv_min": float(hv.min()),
        "t_medio_s": float(t.mean()),
        "t_max_s": float(t.max()),
        "evals_medios": float(np.mean([f["evals"] for f in filas])),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rapido", action="store_true")
    ap.add_argument("--procesos", type=int, default=8)
    ap.add_argument("--pliegues", type=int, default=5)
    ap.add_argument("--semillas-cv", type=int, default=3)
    ap.add_argument("--semillas-prueba", type=int, default=10)
    args = ap.parse_args()

    grandes = []
    for i in n.instancias():
        dec = n.decidibles(n.renglones_de(i))
        if dec and n.espacio_de(n.opciones_de(dec)) > opt.LIMITE_ENUMERACION:
            grandes.append(i)
    lados = particion(grandes, args.pliegues)
    if args.rapido:
        lados["prueba"] = lados["prueba"][:3]
        lados["pliegues"] = [p[:2] for p in lados["pliegues"]]
    sem_cv = (0,) if args.rapido else tuple(range(args.semillas_cv))
    sem_pru = tuple(range(3 if args.rapido else args.semillas_prueba))

    salida: dict = {
        "hardware": n.hardware(),
        "listas_grandes": len(grandes),
        "limite_enumeracion_usado": opt.LIMITE_ENUMERACION,
        "particion": {
            "prueba": len(lados["prueba"]),
            "pliegues": [len(p) for p in lados["pliegues"]],
            "colegios_prueba": lados["colegios_prueba"],
            "colegios_pliegues": lados["colegios_pliegues"],
        },
        "factores": list(FACTORES),
        "umbral_hv": UMBRAL_HV,
        "referencia_hv": n.REFERENCIA,
        "semillas_validacion": len(sem_cv),
        "semillas_prueba": len(sem_pru),
    }

    t0 = time.perf_counter()
    todas = [i for p in lados["pliegues"] for i in p]
    filas = correr_rejilla(todas, sem_cv, args.procesos)
    salida["t_rejilla_s"] = time.perf_counter() - t0
    salida["rejilla"] = resumen_por_config(filas)
    elegida = elegir(salida["rejilla"])
    salida["elegida"] = {"a": elegida["a"], "b": elegida["b"]}
    print("elegida", salida["elegida"], flush=True)

    por_pliegue = []
    for k, ids in enumerate(lados["pliegues"]):
        dentro = set(ids)
        ajuste = resumen_por_config([f for f in filas if f["lista"] not in dentro])
        apartado = resumen_por_config([f for f in filas if f["lista"] in dentro])
        e = elegir(ajuste)
        en_apartado = next(r for r in apartado if (r["a"], r["b"]) == (e["a"], e["b"]))
        mejor_apartado = max(r["hv_medio"] for r in apartado)
        por_pliegue.append(
            {
                "pliegue": k,
                "listas_apartadas": len(ids),
                "elegida": {"a": e["a"], "b": e["b"]},
                "hv_medio_apartado": en_apartado["hv_medio"],
                "hv_min_lista_apartado": en_apartado["hv_min_lista"],
                "mejor_hv_apartado": mejor_apartado,
                "dentro_del_umbral_en_apartado": en_apartado["hv_medio"] >= mejor_apartado - UMBRAL_HV,
            }
        )
    salida["validacion_cruzada"] = por_pliegue
    print("pliegues", [p["elegida"] for p in por_pliegue], flush=True)

    t0 = time.perf_counter()
    por_config: dict[str, list[dict]] = {}
    for nombre, (a, b) in (("actual", (1.0, 1.0)), ("elegida", (elegida["a"], elegida["b"]))):
        por_config[nombre] = [_trabajo((i, a, b, sem_pru)) for i in lados["prueba"]]
    salida["t_prueba_s"] = time.perf_counter() - t0
    hv_a = np.array([np.mean(f["razon"]) for f in por_config["actual"]])
    hv_e = np.array([np.mean(f["razon"]) for f in por_config["elegida"]])
    t_a = np.array([np.mean(f["t"]) for f in por_config["actual"]])
    t_e = np.array([np.mean(f["t"]) for f in por_config["elegida"]])
    rng = np.random.default_rng(n.SEMILLA_BASE)
    dif = hv_e - hv_a
    try:
        p_hv = float(stats.wilcoxon(hv_e, hv_a).pvalue) if np.any(dif != 0) else 1.0
    except ValueError:
        p_hv = 1.0
    p_t = float(stats.wilcoxon(t_e, t_a).pvalue) if np.any(t_e != t_a) else 1.0
    razones_e = np.array([r for f in por_config["elegida"] for r in f["razon"]])
    salida["prueba"] = {
        "listas": len(lados["prueba"]),
        "semillas": len(sem_pru),
        "actual": _resumen_prueba(hv_a, t_a, por_config["actual"]),
        "elegida": _resumen_prueba(hv_e, t_e, por_config["elegida"]),
        "dif_hv_elegida_menos_actual": {
            "media": float(dif.mean()),
            "ic95": ic_bootstrap(dif, rng),
            "wilcoxon_p": p_hv,
        },
        "dif_t_s_elegida_menos_actual": {
            "media": float((t_e - t_a).mean()),
            "ic95": ic_bootstrap(t_e - t_a, rng),
            "wilcoxon_p": p_t,
        },
        "fraccion_corridas_elegida_hv_ge_0999": float(np.mean(razones_e >= 0.999)),
        "razon_min_corrida_elegida": float(razones_e.min()),
        "razon_por_semilla_actual": [r for f in por_config["actual"] for r in f["razon"]],
        "razon_por_semilla_elegida": razones_e.tolist(),
    }
    n.guardar("calibracion_nsga.json" if not args.rapido else "calibracion_nsga_rapido.json", salida)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
