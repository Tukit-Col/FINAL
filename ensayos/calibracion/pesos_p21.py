"""Experimento C1: pesos de los cuatro criterios a partir de la pregunta P21.
Uso: uv run python ensayos/calibracion/pesos_p21.py
Salida: ensayos/calibracion/salidas/pesos_p21.json"""

from __future__ import annotations

import csv
from pathlib import Path

import nucleo as n
import numpy as np

CRITERIOS = ("precio", "marca_exigida", "calidad", "personaje")
DATOS = Path(__file__).resolve().parent / "datos" / "p21_rankings.csv"
REMUESTREOS = 10_000


def cargar() -> np.ndarray:
    with DATOS.open(encoding="utf-8") as f:
        filas = list(csv.DictReader(f))
    puntos = np.zeros((len(filas), len(CRITERIOS)))
    for i, fila in enumerate(filas):
        for pos in range(4):
            puntos[i, CRITERIOS.index(fila[f"pos{pos + 1}"])] = 4 - pos
    return puntos


def pesos(puntos: np.ndarray) -> np.ndarray:
    return puntos.mean(axis=0) / 10.0


def main() -> int:
    puntos = cargar()
    rng = np.random.default_rng(n.SEMILLA_BASE)
    muestras = np.array(
        [pesos(puntos[rng.integers(0, len(puntos), len(puntos))]) for _ in range(REMUESTREOS)]
    )
    estimado = pesos(puntos)
    ic = np.percentile(muestras, [2.5, 97.5], axis=0)
    primero = {c: float((puntos[:, i] == 4).mean()) for i, c in enumerate(CRITERIOS)}
    salida = {
        "encuestados": len(puntos),
        "remuestreos": REMUESTREOS,
        "semilla": n.SEMILLA_BASE,
        "pesos": {c: round(float(estimado[i]), 4) for i, c in enumerate(CRITERIOS)},
        "puntos_promedio": {c: round(float(puntos[:, i].mean()), 3) for i, c in enumerate(CRITERIOS)},
        "ic95": {c: [round(float(ic[0, i]), 4), round(float(ic[1, i]), 4)] for i, c in enumerate(CRITERIOS)},
        "fraccion_en_primer_lugar": {c: round(v, 3) for c, v in primero.items()},
        "pesos_anteriores_del_codigo": {
            "precio": 0.35,
            "marca_exigida": 0.30,
            "calidad": 0.25,
            "personaje": 0.10,
        },
    }
    n.guardar("pesos_p21.json", salida)
    for c in CRITERIOS:
        print(c, salida["pesos"][c], salida["ic95"][c])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
