"""Escenario ESC-D4 del ATAM: tiempo de la etapa de optimizacion contra DP-03 (8 s).

Mide el tiempo de pared de `armar_los_tres` (frente de Pareto + proyeccion de
perfiles + armado de los kits) por lista, en las 174 listas reales del banco,
con 30 ejecuciones por lista (semillas 0..29), sin preferencias y con el perfil
de la sesion de OE5 (personaje y punto medio, que anade Fan y A tu Medida).
Reporta media, mediana, p95, p99 y maximo sobre todas las ejecuciones, y el p95
por lista (la peor lista manda).

No incluye la percepcion ni la recuperacion de candidatos: las listas del banco
ya traen los candidatos resueltos. Es el tiempo de la etapa que ESC-D4 acota.

Uso: uv run python ensayos/calibracion/esc_d4.py
Salida: docs/informes/calibracion/esc_d4.json
"""

from __future__ import annotations

import time

import nucleo as n
import numpy as np
from tukit_inteligencia.optimizador import armar_los_tres

EJECUCIONES = 30
LIMITE_S = 8.0
PERFILES = {
    "sin_preferencias": {},
    "personaje_y_punto_medio": {"personaje_por_hijo": {"hijo-1": ["spiderman"]}, "prioridad": "equilibrio"},
}


def main() -> int:
    instancias = n.instancias()
    salida: dict = {"hardware": n.hardware(), "ejecuciones_por_lista": EJECUCIONES, "limite_s": LIMITE_S}
    for nombre, prefs in PERFILES.items():
        todos, p95_lista = [], []
        for inst in instancias:
            renglones = n.renglones_de(inst)
            tiempos = []
            for s in range(EJECUCIONES):
                t0 = time.perf_counter()
                armar_los_tres(renglones, prefs, semilla=s)
                tiempos.append(time.perf_counter() - t0)
            todos.extend(tiempos)
            p95_lista.append(float(np.percentile(tiempos, 95)))
        t = np.array(todos)
        salida[nombre] = {
            "listas": len(instancias),
            "ejecuciones": int(t.size),
            "media_s": float(t.mean()),
            "mediana_s": float(np.median(t)),
            "p95_s": float(np.percentile(t, 95)),
            "p99_s": float(np.percentile(t, 99)),
            "max_s": float(t.max()),
            "peor_p95_por_lista_s": float(max(p95_lista)),
            "ejecuciones_sobre_limite": int((t > LIMITE_S).sum()),
        }
        print(nombre, {k: round(v, 3) if isinstance(v, float) else v for k, v in salida[nombre].items()}, flush=True)
    print(n.guardar("esc_d4.json", salida))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
