"""Vuelve a correr solo el NSGA-II (con y sin siembra) y lo fusiona con las corridas existentes.

    python actualizar_nsga.py tiempo|memoria|hogares|hogares_memoria

Sirve cuando cambia el presupuesto de busqueda del NSGA-II (poblacion N y
generaciones G) pero no cambian los objetivos ni los candidatos admisibles: la
enumeracion, la programacion dinamica y el voraz dan el mismo frente, asi que
se conservan sus corridas y solo se reemplazan las de `nsga2` y
`nsga2_sin_siembra`. Antes de fusionar se comprueba que n y |E| de cada fila
coinciden con los de la corrida guardada. La pasada de semillas solo tiene
NSGA-II y se corre entera con `correr.py semillas`.

La entrada `entorno` registra el commit del optimizador con que se corrio el
NSGA-II (ver `correr._entorno`), el de las corridas que se conservan y la carga
de la maquina al empezar y al terminar.
"""

from __future__ import annotations

import argparse
import subprocess
import time
import tracemalloc

import correr
from tukit_final import RESULTADOS, cargar_json, decidibles, guardar_json, instancias, renglones_de

NSGA = ["nsga2", "nsga2_sin_siembra"]
ARCHIVOS = {
    "tiempo": "corridas_tiempo.json.gz",
    "memoria": "corridas_memoria.json.gz",
    "hogares": "hogares_tiempo.json.gz",
    "hogares_memoria": "hogares_memoria.json.gz",
}


def _carga() -> str:
    return subprocess.run(["uptime"], capture_output=True, text=True).stdout.strip()


def _entorno(previo: dict, carga_inicio: str) -> dict:
    e = correr._entorno()
    e["final_commit_conservadas"] = previo.get("final_commit_conservadas", previo.get("final_commit"))
    e["algoritmos_actualizados"] = NSGA
    e["carga_inicio"] = carga_inicio
    e["carga_fin"] = _carga()
    return e


def _fusionar(fila_vieja: dict, nueva: dict) -> None:
    for k in ("n", "espacio", "log10_espacio"):
        if fila_vieja[k] != nueva[k]:
            raise SystemExit(f"{fila_vieja['instancia']}: {k} cambio ({fila_vieja[k]} -> {nueva[k]})")
    fila_vieja["N"], fila_vieja["G"] = nueva["N"], nueva["G"]
    for a in NSGA:
        fila_vieja["corridas"].pop(a, None)
        if a in nueva["corridas"]:
            fila_vieja["corridas"][a] = nueva["corridas"][a]


def listas(memoria: bool, datos: dict) -> None:
    insts = {i["id"]: i for i in instancias()}
    muestra = None
    if memoria:
        tamanos = [(iid, len(decidibles(renglones_de(i)))) for iid, i in insts.items()]
        muestra = correr._muestra_por_n(tamanos, 5)
        tracemalloc.start()
    correr._correr_instancia(renglones_de(insts["2.14|Jardin"]), {}, ["nsga2", "dp", "voraz"], memoria=False)
    prefs = {(t["instancia"], t["prefs_tag"]): t["prefs"] for t in correr._tareas(con_fan=True)}
    t0 = time.perf_counter()
    for k, f in enumerate(datos["filas"], 1):
        algos = NSGA if muestra is None or f["instancia"] in muestra else []
        nueva = correr._correr_instancia(
            renglones_de(insts[f["instancia"]]), prefs[(f["instancia"], f["prefs_tag"])], algos, memoria
        )
        _fusionar(f, nueva)
        if k % 20 == 0:
            print(f"  {k}/{len(datos['filas'])} en {time.perf_counter() - t0:.0f} s", flush=True)
    if memoria:
        tracemalloc.stop()


def hogares(memoria: bool, datos: dict) -> None:
    hs = {h["id"]: h for h in correr.hogares()}
    muestra = None
    if memoria:
        muestra = correr._muestra_por_n([(h["id"], h["n"]) for h in hs.values()], 3)
        tracemalloc.start()
    t0 = time.perf_counter()
    for k, f in enumerate(datos["filas"], 1):
        algos = NSGA if muestra is None or f["instancia"] in muestra else []
        nueva = correr._correr_instancia(renglones_de({"renglones": hs[f["instancia"]]["renglones"]}), {}, algos, memoria)
        _fusionar(f, nueva)
        print(f"  hogar {k}/{len(datos['filas'])} n={f['n']} en {time.perf_counter() - t0:.0f} s", flush=True)
    if memoria:
        tracemalloc.stop()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("pasada", choices=list(ARCHIVOS))
    args = ap.parse_args()
    ruta = RESULTADOS / ARCHIVOS[args.pasada]
    datos = cargar_json(ruta)
    carga = _carga()
    t0 = time.perf_counter()
    memoria = args.pasada.endswith("memoria")
    (hogares if args.pasada.startswith("hogares") else listas)(memoria, datos)
    datos["entorno"] = _entorno(datos["entorno"], carga)
    guardar_json(ruta, datos)
    print(f"{ruta.name}: {len(datos['filas'])} filas en {time.perf_counter() - t0:.0f} s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
