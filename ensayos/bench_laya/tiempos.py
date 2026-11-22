"""Tiempos medidos con la maquina sola (las corridas principales compartian CPU/GPU).

Lado NSGA-II (venv del proyecto):   python tiempos.py nsga
Lado Laya    (.venv-laya):          python tiempos.py laya [--cpu]

Toma 30 listas fijas (cada sexta por id), un proceso, y mide el tiempo de pared
de armar los kits de un papa sin preferencias (NSGA-II: los tres kits de una
corrida; Laya: cada modalidad, escenario ahorrador). Escribe `tiempos_<lado>.json`
en `ensayos/bench_laya/salidas/`.
"""

from __future__ import annotations

import gzip
import json
import statistics as st
import sys
import time
from pathlib import Path

CARPETA = Path(__file__).resolve().parent
# Los tiempos son resultados del informe: van junto a el, no junto al codigo.
SALIDA = CARPETA.parents[1] / "ensayos" / "bench_laya" / "salidas"


def _muestra():
    with gzip.open(CARPETA / "instancias.json.gz", "rt", encoding="utf-8") as f:
        inst = json.load(f)["instancias"]
    escs = json.loads((CARPETA / "escenarios.json").read_text(encoding="utf-8"))["escenarios"]
    ids = sorted({e["instancia"] for e in escs})[::6][:30]
    por_id = {i["id"]: i for i in inst}
    return [por_id[i] for i in ids], [
        e for e in escs if e["instancia"] in ids and e["escenario"] == "ahorrador"
    ]


def _resumen(xs):
    return {
        "n": len(xs),
        "media_s": round(st.mean(xs), 3),
        "mediana_s": round(st.median(xs), 3),
        "max_s": round(max(xs), 3),
    }


def nsga():
    from comun import renglones_de
    from tukit_inteligencia.optimizador import armar_los_tres

    instancias, _ = _muestra()
    armar_los_tres(renglones_de(instancias[0]), {})
    xs = []
    for inst in instancias:
        t = time.perf_counter()
        armar_los_tres(renglones_de(inst), {}, semilla=0)
        xs.append(time.perf_counter() - t)
    return {"nsga2_tres_kits": _resumen(xs)}


def laya(cpu: bool):
    import laya as lib
    from correr_laya import MODALIDADES

    instancias, escs = _muestra()
    por_id = {i["id"]: i for i in instancias}
    agente = lib.load("typed-decisions", device="cpu" if cpu else None)
    agente.predict("calentamiento", {"q": {"type": "noul", "instructions": "¿si?"}})
    salida = {}
    for m, fn in MODALIDADES.items():
        if cpu and m == "B":
            continue  # estados de miles de tokens: en CPU tarda minutos por lista
        xs = []
        for esc in escs:
            t = time.perf_counter()
            fn(agente, por_id[esc["instancia"]], esc)
            xs.append(time.perf_counter() - t)
        salida[f"laya_{m}_un_kit"] = _resumen(xs)
        print(m, salida[f"laya_{m}_un_kit"], flush=True)
    return salida


def main() -> int:
    lado = sys.argv[1]
    if lado == "nsga":
        datos = nsga()
        nombre = "tiempos_nsga.json"
    else:
        cpu = "--cpu" in sys.argv
        datos = laya(cpu)
        nombre = f"tiempos_laya{'_cpu' if cpu else '_gpu'}.json"
    (SALIDA / nombre).write_text(json.dumps(datos, indent=1), encoding="utf-8")
    print(datos)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
