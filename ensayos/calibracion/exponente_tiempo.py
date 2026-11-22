"""Exponente de crecimiento (ajuste log-log) del tiempo y la memoria de NSGA-II y de la PD frente al
numero de lineas n, recalculado desde las corridas crudas de benchmarks/06-optimizacion (rama
origin/benchmarks, commit 8d917ae). Solo lectura. Salida: ensayos/calibracion/salidas/exponente_tiempo.json.
Uso: python3 -I ensayos/calibracion/exponente_tiempo.py
Uso: python3 -I ensayos/calibracion/exponente_tiempo.py"""

import gzip
import io
import json
import math
import statistics as st
import subprocess
from pathlib import Path

RAMA = "origin/benchmarks"
BASE = "benchmarks/06-optimizacion/resultados"
OUT = Path(__file__).resolve().parents[2] / "ensayos/calibracion/salidas/exponente_tiempo.json"


def leer_crudo(nombre):
    return subprocess.run(["git", "show", f"{RAMA}:{BASE}/{nombre}"], check=True, capture_output=True).stdout


def leer(nombre):
    return json.load(gzip.open(io.BytesIO(leer_crudo(nombre)), "rt"))


def pendiente(xs, ys):
    lx, ly = [math.log(x) for x in xs], [math.log(y) for y in ys]
    mx, my = sum(lx) / len(lx), sum(ly) / len(ly)
    return sum((a - mx) * (c - my) for a, c in zip(lx, ly)) / sum((a - mx) ** 2 for a in lx)


def por_n(pares):
    d = {}
    for n, v in pares:
        d.setdefault(n, []).append(v)
    return sorted(d), [st.median(d[n]) for n in sorted(d)]


def main():
    sem = leer("corridas_semillas.json.gz")["filas"]
    mem = leer("corridas_memoria.json.gz")["filas"]
    hog = json.loads(leer_crudo("resumen.json"))["hogares"]["filas"]
    res = {
        "fuente": f"{RAMA}:{BASE}",
        "metodo": "pendiente del ajuste log-log de los puntos (n = lineas decidibles); conjunto = listas reales (mediana de semillas por lista) + hogares sinteticos",
    }
    inst = {}
    for r in sem:
        s = (r["corridas"].get("nsga2") or {}).get("segundos")
        if s:
            inst.setdefault((r["instancia"], r["n"]), []).append(s)
    t = [(n, st.median(v)) for (_, n), v in inst.items()]
    th = [(h["n"], h["nsga2"]["segundos"]) for h in hog]
    res["tiempo_nsga2"] = {
        "solo_listas_reales": {"puntos": len(t), "exponente": round(pendiente(*zip(*t)), 2)},
        "listas_y_hogares": {"puntos": len(t + th), "exponente": round(pendiente(*zip(*(t + th))), 2)},
    }
    for alg in ("nsga2", "dp"):
        m = [
            (r["n"], r["corridas"][alg]["pico_bytes"])
            for r in mem
            if (r["corridas"].get(alg) or {}).get("pico_bytes")
        ]
        mh = [(h["n"], h[alg]["mib"] * 1048576) for h in hog if h[alg].get("mib")]
        res[f"memoria_{alg}"] = {
            "solo_listas_reales": {"puntos": len(m), "exponente": round(pendiente(*zip(*m)), 2)},
            "listas_y_hogares": {"puntos": len(m + mh), "exponente": round(pendiente(*zip(*(m + mh))), 2)},
        }
    OUT.write_text(json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(res, ensure_ascii=False))


if __name__ == "__main__":
    main()
