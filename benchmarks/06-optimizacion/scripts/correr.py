"""Corre los constructores del frente sobre las instancias del benchmark Laya.

Pasadas (cada una escribe un archivo en `resultados/`):

    python correr.py tiempo     # tiempo de pared, frentes y ternas de la DP
    python correr.py memoria    # pico de memoria con tracemalloc (pasada aparte)
    python correr.py semillas   # NSGA-II con semillas 1-4 (variabilidad de calidad)
    python correr.py hogares    # hogares sinteticos de 2-8 hijos (n hasta ~300)

Las pasadas de tiempo y memoria van separadas porque tracemalloc encarece cada
asignacion de memoria y distorsionaria los tiempos. Todo corre en un solo
proceso salvo `semillas`, que no mide tiempo.

Instancias: `datos/instancias.json.gz` (175 listas, foto del catalogo
d60ef70e9428f7e6, la misma del benchmark Laya). Preferencias: sin preferencias
(las de Ahorrador, Premium y Presupuesto) y, para las 157 listas del escenario
Fan, el personaje pedido.
"""

from __future__ import annotations

import argparse
import gc
import math
import os
import platform
import sys
import time
import tracemalloc
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor

import numpy as np

import algoritmos as alg
from tukit_final import RESULTADOS, decidibles, escenarios, guardar_json, instancias, opt, renglones_de

TOPE_ENUMERACION = 60_000  # |E| maximo para la fuerza bruta (a ~5e4 ya tarda hasta 30 s)


def _entorno() -> dict:
    import subprocess

    import pymoo

    from tukit_final import FINAL

    # Una copia exportada con `git archive` no tiene `.git`: el commit se pasa en TUKIT_FINAL_COMMIT.
    commit = os.environ.get("TUKIT_FINAL_COMMIT", "")
    try:
        commit = commit or subprocess.run(
            ["git", "-C", str(FINAL), "rev-parse", "HEAD"], capture_output=True, text=True, check=True
        ).stdout.strip()
    except Exception:  # noqa: BLE001
        commit = "desconocido"
    try:
        cpu = subprocess.run(["sysctl", "-n", "machdep.cpu.brand_string"], capture_output=True, text=True).stdout.strip()
    except Exception:  # noqa: BLE001
        cpu = platform.processor()
    return {
        "python": sys.version.split()[0],
        "numpy": np.__version__,
        "pymoo": pymoo.__version__,
        "plataforma": platform.platform(),
        "cpu": cpu,
        "final_commit": commit,
    }


def _vec(frente) -> list[list[float]]:
    return [[s.costo, s.fidelidad, s.disponibilidad, s.personaje] for s in frente]


def _tareas(con_fan: bool = True) -> list[dict]:
    """(instancia, etiqueta de preferencias, preferencias) para cada corrida."""
    insts = {i["id"]: i for i in instancias()}
    fan = {e["instancia"]: e["preferencias"] for e in escenarios() if e["escenario"] == "fan"}
    tareas = []
    for iid in sorted(insts):
        tareas.append({"instancia": iid, "prefs_tag": "sin_preferencias", "prefs": {}})
        if con_fan and iid in fan:
            tareas.append({"instancia": iid, "prefs_tag": "fan", "prefs": fan[iid]})
    return tareas


def _medir(fn, dec, opciones, prefs, memoria: bool, **kw):
    gc.collect()
    if memoria:
        tracemalloc.reset_peak()
        base = tracemalloc.get_traced_memory()[0]
        frente = fn(dec, opciones, prefs, **kw)
        pico = tracemalloc.get_traced_memory()[1] - base
        return frente, None, pico
    t0 = time.perf_counter()
    frente = fn(dec, opciones, prefs, **kw)
    return frente, time.perf_counter() - t0, None


def _correr_instancia(renglones, prefs, algos: list[str], memoria: bool, semilla: int = 0) -> dict:
    dec = decidibles(renglones)
    opciones = [opt._admisibles(r) for r in dec]
    tamanos = [len(o) for o in opciones]
    espacio = math.prod(tamanos) if dec else 0
    fila = {
        "n": len(dec),
        "k_medio": round(float(np.mean(tamanos)), 4) if dec else 0.0,
        "k_max": max(tamanos) if dec else 0,
        "log10_espacio": round(math.log10(espacio), 4) if espacio > 0 else None,
        "espacio": espacio if espacio < 10**15 else None,
        "N": opt._poblacion(len(dec)) if dec else None,
        "G": opt._generaciones(espacio) if dec else None,
        "metodo_produccion": "nsga2" if espacio > opt.LIMITE_ENUMERACION else ("exacto" if espacio > 1 else "sin_frente"),
        "corridas": {},
    }
    if espacio <= 1:
        return fila
    for nombre in algos:
        if nombre == "enumeracion" and espacio > TOPE_ENUMERACION:
            continue
        kw = {"semilla": semilla} if nombre.startswith("nsga2") else {}
        info: dict = {}
        if nombre == "dp":
            kw["info"] = info
        frente, seg, pico = _medir(alg.ALGORITMOS[nombre], dec, opciones, prefs, memoria, **kw)
        fila["corridas"][nombre] = {
            "segundos": None if seg is None else round(seg, 6),
            "pico_bytes": pico,
            "frente": _vec(frente),
            **info,
        }
    return fila


def _muestra_por_n(ids_y_n: list[tuple[str, int]], cada: int) -> set[str]:
    """Una de cada `cada` instancias en orden de n: cubre todo el rango de tamanos."""
    orden = sorted(ids_y_n, key=lambda t: (t[1], t[0]))
    return {iid for k, (iid, _n) in enumerate(orden) if k % cada == 0 or k == len(orden) - 1}


def pasada(memoria: bool, algos: list[str], limite: int = 0, nsga_cada: int = 5) -> dict:
    """Con `memoria`, solo sin preferencias y el NSGA-II en una muestra por n.

    Con tracemalloc cada asignacion de pymoo se registra y el NSGA-II tarda unas
    15 veces mas; su memoria la acota la poblacion (N <= 200), asi que una de
    cada `nsga_cada` listas basta para ver la tendencia. DP, voraz y
    enumeracion se miden en todas.
    """
    insts = {i["id"]: i for i in instancias()}
    tareas = _tareas(con_fan=not memoria)
    if limite:
        ids = sorted(insts)[:limite]
        tareas = [t for t in tareas if t["instancia"] in ids]
    muestra_nsga = None
    if memoria:
        tamanos = [(iid, len(decidibles(renglones_de(i)))) for iid, i in insts.items()]
        muestra_nsga = _muestra_por_n(tamanos, nsga_cada)
        tracemalloc.start()
    # Calentamiento: importa pymoo y compila lo que haga falta fuera de la medicion.
    _correr_instancia(renglones_de(insts["2.14|Jardin"]), {}, ["nsga2", "dp", "voraz"], memoria=False)
    filas = []
    t0 = time.perf_counter()
    for k, t in enumerate(tareas, 1):
        algos_t = algos
        if muestra_nsga is not None and t["instancia"] not in muestra_nsga:
            algos_t = [a for a in algos if not a.startswith("nsga2")]
        fila = _correr_instancia(renglones_de(insts[t["instancia"]]), t["prefs"], algos_t, memoria)
        filas.append({"instancia": t["instancia"], "prefs_tag": t["prefs_tag"], **fila})
        if k % 20 == 0:
            print(f"  {k}/{len(tareas)} en {time.perf_counter() - t0:.0f} s", flush=True)
    if memoria:
        tracemalloc.stop()
    return {"entorno": _entorno(), "memoria": memoria, "tope_enumeracion": TOPE_ENUMERACION, "filas": filas}


# --------------------------------------------------------------------- semillas


def _trabajo_semilla(args):
    iid, semilla = args
    insts = {i["id"]: i for i in instancias()}
    fila = _correr_instancia(renglones_de(insts[iid]), {}, ["nsga2", "nsga2_sin_siembra"], False, semilla=semilla)
    return {"instancia": iid, "semilla": semilla, **fila}


def pasada_semillas(procesos: int) -> dict:
    ids = sorted(i["id"] for i in instancias())
    trabajos = [(iid, s) for iid in ids for s in (1, 2, 3, 4)]
    with ProcessPoolExecutor(max_workers=procesos) as ex:
        filas = list(ex.map(_trabajo_semilla, trabajos, chunksize=4))
    return {"entorno": _entorno(), "filas": filas}


# ---------------------------------------------------------------------- hogares


def hogares(por_tramo: int = 3) -> list[dict]:
    """Hogares sinteticos: listas de grados consecutivos de un mismo colegio, un hijo por lista.

    Es el caso que el benchmark Laya no cubrio (un solo hijo por lista) y el que
    hace crecer n: un hogar de m hijos tiene la suma de sus lineas decidibles.
    Se eligen `por_tramo` hogares por tramo de n para cubrir de ~25 a ~300 lineas.
    """
    insts = instancias()
    por_colegio = defaultdict(list)
    for i in insts:
        por_colegio[i["colegio"]].append(i)
    candidatos = []
    for col, lst in sorted(por_colegio.items()):
        for m in range(2, 9):
            for ini in range(0, len(lst) - m + 1, m):
                grupo = lst[ini : ini + m]
                renglones = []
                for h, inst in enumerate(grupo, 1):
                    for r in inst["renglones"]:
                        renglones.append({**r, "hijo": f"hijo-{h}"})
                n = len(decidibles(renglones_de({"renglones": renglones})))
                candidatos.append({"id": f"{col}|{m}h|{grupo[0]['grado']}", "hijos": m, "n": n, "renglones": renglones})
    tramos = [(20, 40), (40, 60), (60, 80), (80, 110), (110, 140), (140, 180), (180, 230), (230, 320)]
    elegidos = []
    for lo, hi in tramos:
        en = sorted((c for c in candidatos if lo <= c["n"] < hi), key=lambda c: (c["n"], c["id"]))
        if not en:
            continue
        pasos = np.linspace(0, len(en) - 1, min(por_tramo, len(en))).round().astype(int)
        elegidos.extend(en[p] for p in dict.fromkeys(pasos.tolist()))
    return elegidos


def pasada_hogares(memoria: bool, nsga_cada: int = 3) -> dict:
    hs = hogares()
    muestra_nsga = None
    if memoria:
        muestra_nsga = _muestra_por_n([(h["id"], h["n"]) for h in hs], nsga_cada)
        tracemalloc.start()
    filas = []
    t0 = time.perf_counter()
    for k, h in enumerate(hs, 1):
        algos = ["dp", "nsga2", "nsga2_sin_siembra", "voraz"]
        if muestra_nsga is not None and h["id"] not in muestra_nsga:
            algos = ["dp", "voraz"]
        fila = _correr_instancia(renglones_de({"renglones": h["renglones"]}), {}, algos, memoria)
        filas.append({"instancia": h["id"], "hijos": h["hijos"], "prefs_tag": "sin_preferencias", **fila})
        print(f"  hogar {k}/{len(hs)} n={fila['n']} en {time.perf_counter() - t0:.0f} s", flush=True)
    if memoria:
        tracemalloc.stop()
    return {"entorno": _entorno(), "memoria": memoria, "filas": filas}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("pasada", choices=["tiempo", "memoria", "semillas", "hogares", "hogares_memoria"])
    ap.add_argument("--limite", type=int, default=0)
    ap.add_argument("--procesos", type=int, default=6)
    args = ap.parse_args()
    todos = ["enumeracion", "dp", "nsga2", "nsga2_sin_siembra", "voraz"]
    t0 = time.perf_counter()
    if args.pasada == "tiempo":
        datos, nombre = pasada(False, todos, args.limite), "corridas_tiempo.json.gz"
    elif args.pasada == "memoria":
        datos, nombre = pasada(True, todos, args.limite), "corridas_memoria.json.gz"
    elif args.pasada == "semillas":
        datos, nombre = pasada_semillas(args.procesos), "corridas_semillas.json.gz"
    elif args.pasada == "hogares":
        datos, nombre = pasada_hogares(False), "hogares_tiempo.json.gz"
    else:
        datos, nombre = pasada_hogares(True), "hogares_memoria.json.gz"
    if args.limite:
        nombre = nombre.replace(".json", f"_prueba{args.limite}.json")
    guardar_json(RESULTADOS / nombre, datos)
    print(f"{nombre}: {len(datos['filas'])} filas en {time.perf_counter() - t0:.0f} s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
