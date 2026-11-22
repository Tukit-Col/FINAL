"""Experimento D: hipervolumen del frente y de los kits por perfil, en las listas de PRUEBA.

Espacio de los 4 objetivos normalizado a [0, 1] con 0 como lo mejor (ver
`nucleo.hipervolumen`) y punto de referencia (1,1; 1,1; 1,1; 1,1). Por lista:

- HV del frente de produccion (30 semillas cuando corre NSGA-II) dividido entre el
  HV del frente exacto (poda por linea);
- HV de cada perfil: el volumen que domina el punto de ese kit hasta la
  referencia, dividido entre el HV del frente exacto (Ahorrador, Premium y el
  punto MAUT con los pesos P21);
- cobertura de los kits: HV del conjunto {Ahorrador, Premium} dividido entre el HV
  del frente exacto, o sea que parte del volumen del frente dominan los dos kits
  que siempre se muestran.

Uso: uv run python ensayos/calibracion/hipervolumen_prueba.py
Salida: ensayos/calibracion/salidas/hipervolumen_prueba.json
"""

from __future__ import annotations

import math

import nucleo as n
import numpy as np
from sensibilidad import listas_de_prueba
from tukit_inteligencia.modelos import PESOS_POR_OMISION
from tukit_inteligencia.optimizador import (
    LIMITE_ENUMERACION,
    _proyectar,
    elegir_recomendado_maut,
    optimizar_frente,
)

SEMILLAS = tuple(range(30))
PERFILES = ("Ahorrador", "Premium")


def main() -> int:
    filas = []
    for inst in listas_de_prueba():
        renglones = n.renglones_de(inst)
        dec = n.decidibles(renglones)
        ops = n.opciones_de(dec)
        if not dec or n.espacio_de(ops) <= 1:
            continue
        lo, hi = n.limites_costo(dec, ops)
        exacto = n.frente_exacto_por_podas(dec, ops, {})
        hv_exacto = n.hipervolumen(exacto, lo, hi)
        usa_nsga = n.espacio_de(ops) > LIMITE_ENUMERACION
        semillas = SEMILLAS if usa_nsga else (0,)
        razones = []
        for s in semillas:
            frente = optimizar_frente(renglones, {}, semilla=s)
            razones.append(n.hipervolumen(frente, lo, hi) / hv_exacto)
        frente0 = optimizar_frente(renglones, {}, semilla=0)
        puntos = {p: _proyectar(frente0, p) for p in PERFILES}
        puntos["MAUT_P21"] = elegir_recomendado_maut(frente0, PESOS_POR_OMISION)
        por_perfil = {p: n.hipervolumen([pt], lo, hi) / hv_exacto for p, pt in puntos.items()}
        filas.append(
            {
                "lista": inst["id"],
                "colegio": inst["colegio"],
                "log2_espacio": math.log2(n.espacio_de(ops)),
                "metodo": "nsga2" if usa_nsga else "exacto",
                "puntos_frente": len(frente0),
                "hv_frente_exacto": hv_exacto,
                "razon_hv_frente": [float(r) for r in razones],
                "hv_por_perfil": por_perfil,
                "cobertura_dos_kits": n.hipervolumen([puntos[p] for p in PERFILES], lo, hi) / hv_exacto,
            }
        )
    razon = np.array([np.mean(f["razon_hv_frente"]) for f in filas])
    cob = np.array([f["cobertura_dos_kits"] for f in filas])
    rng = np.random.default_rng(n.SEMILLA_BASE)

    def ic(x):
        medias = [x[rng.integers(0, len(x), len(x))].mean() for _ in range(5000)]
        return [float(v) for v in np.percentile(medias, [2.5, 97.5])]

    perfiles = {
        p: {
            "media": float(np.mean([f["hv_por_perfil"][p] for f in filas])),
            "ic95": ic(np.array([f["hv_por_perfil"][p] for f in filas])),
        }
        for p in (*PERFILES, "MAUT_P21")
    }
    n.guardar(
        "hipervolumen_prueba.json",
        {
            "referencia": n.REFERENCIA,
            "listas": len(filas),
            "listas_nsga2": sum(f["metodo"] == "nsga2" for f in filas),
            "razon_hv_frente_media": float(razon.mean()),
            "razon_hv_frente_ic95": ic(razon),
            "razon_hv_frente_minima": float(razon.min()),
            "cobertura_dos_kits_media": float(cob.mean()),
            "cobertura_dos_kits_ic95": ic(cob),
            "hv_relativo_por_perfil": perfiles,
            "semillas": len(SEMILLAS),
            "filas": filas,
        },
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
