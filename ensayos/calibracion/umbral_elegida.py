"""Experimento A2: tiempo del NSGA-II con la configuracion elegida en `calibrar_nsga.py`.

`umbral.py` midio el NSGA-II con la configuracion de partida (a = b = 1). El
umbral de enumeracion depende del tiempo del NSGA-II, asi que aqui se vuelve a
medir, en serie y sobre los MISMOS subproblemas de `umbral.json`, con los
factores (a, b) elegidos. La enumeracion exacta no se repite: su tiempo no
depende de (a, b).

Uso: uv run python ensayos/calibracion/umbral_elegida.py
Salida: ensayos/calibracion/salidas/umbral_elegida.json
"""

from __future__ import annotations

import json
import math
import time

import nucleo as n
import numpy as np
from calibrar_nsga import generaciones_con, poblacion_con
from tukit_inteligencia import optimizador as opt
from umbral import SEMILLAS_TIEMPO, reconstruir


def main() -> int:
    u = json.loads((n.SALIDA / "umbral.json").read_text(encoding="utf-8"))
    c = json.loads((n.SALIDA / "calibracion_nsga.json").read_text(encoding="utf-8"))
    a, b = c["elegida"]["a"], c["elegida"]["b"]
    opt._poblacion = poblacion_con(a)
    opt._generaciones = generaciones_con(b)

    d0, o0 = reconstruir(u["filas"][0])
    opt._frente_nsga(d0, o0, {}, semilla=0)

    filas = []
    for f in u["filas"]:
        dec, ops = reconstruir(f)
        lo, hi = n.limites_costo(dec, ops)
        tiempos, razones = [], []
        for s in SEMILLAS_TIEMPO:
            t0 = time.perf_counter()
            frente = opt._frente_nsga(dec, ops, {}, semilla=s)
            tiempos.append(time.perf_counter() - t0)
            razones.append(n.hipervolumen(frente, lo, hi) / f["hv_exacto"] if f["hv_exacto"] > 0 else 1.0)
        filas.append(
            {
                "bits": f["bits"],
                "S": f["S"],
                "t_exacto": f["exacto"]["t_total"] if f["exacto"] else None,
                "t_nsga_s": tiempos,
                "razon_hv": razones,
            }
        )

    con = [f for f in filas if f["t_exacto"]]
    S = np.array([f["S"] for f in con], float)
    t = np.array([f["t_exacto"] for f in con])
    k, logc = np.polyfit(np.log(S), np.log(t), 1)
    sd = float((np.log(t) - (k * np.log(S) + logc)).std())
    t_med = float(np.median([np.mean(f["t_nsga_s"]) for f in filas]))
    n.guardar(
        "umbral_elegida.json",
        {
            "hardware": n.hardware(),
            "elegida": {"a": a, "b": b},
            "ajuste_exacto": {
                "exponente": float(k),
                "constante": float(math.exp(logc)),
                "sd_log_residuo": sd,
            },
            "t_nsga_mediana_s": t_med,
            "cruce_mediana": float(math.exp((math.log(t_med) - logc) / k)),
            "cruce_percentil95": float(math.exp((math.log(t_med) - logc - 1.645 * sd) / k)),
            "filas": filas,
        },
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
