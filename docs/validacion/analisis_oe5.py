"""Analisis de la validacion con acudientes (OE5), fijado antes de la primera sesion.

Lee un CSV con una fila por participante (ver `COLUMNAS`) y calcula lo que el
plan de analisis (`plan_analisis_oe5.md`) declara como confirmatorio y
secundario. No decide nada que el plan no diga: si una prueba cambia, se
anota como desviacion en el plan, no aqui en silencio.

    python docs/validacion/analisis_oe5.py datos.csv
    python docs/validacion/analisis_oe5.py --sintetico   # se prueba a si mismo

Columnas por participante (ACU-xx):
- sus1..sus10: SUS de 1 a 5, en el orden del cuestionario (impares positivos).
- nps: 0 a 10.
- tlx_trad_1..6 y tlx_tukit_1..6: NASA-TLX raw (RTLX), 0 a 100 por escala.
- t1..t7: S (sin ayuda), A (asistida), F (fallida), N (no aplica / fallo del sistema).
- int_t1..int_t7: interacciones discretas contadas en la grabacion.
- seg_t1..seg_t7: segundos por tarea (la espera del sistema en T3 no cuenta).
"""

from __future__ import annotations

import csv
import math
import random
import sys
from dataclasses import dataclass

import numpy as np
from scipy import stats

TAREAS = [f"t{i}" for i in range(1, 8)]
CRITICAS = ("t1", "t4", "t6")
UMBRAL_SUS = 68.0
UMBRAL_EXITO = 0.80
COLUMNAS = (
    ["codigo"]
    + [f"sus{i}" for i in range(1, 11)]
    + ["nps"]
    + [f"tlx_trad_{i}" for i in range(1, 7)]
    + [f"tlx_tukit_{i}" for i in range(1, 7)]
    + TAREAS
    + [f"int_{t}" for t in TAREAS]
    + [f"seg_{t}" for t in TAREAS]
)


def puntaje_sus(respuestas: list[int]) -> float:
    """Brooke (1996): impares aportan r-1, pares 5-r; la suma por 2,5."""
    if len(respuestas) != 10 or any(r < 1 or r > 5 for r in respuestas):
        raise ValueError("el SUS son 10 respuestas de 1 a 5")
    suma = sum((r - 1) if i % 2 == 0 else (5 - r) for i, r in enumerate(respuestas))
    return suma * 2.5


def nps(valores: list[int]) -> float:
    """% promotores (9-10) menos % detractores (0-6)."""
    n = len(valores)
    return 100.0 * (sum(v >= 9 for v in valores) - sum(v <= 6 for v in valores)) / n


def wilson(exitos: int, n: int, z: float = 1.959964) -> tuple[float, float]:
    if n == 0:
        return (math.nan, math.nan)
    p = exitos / n
    centro = (p + z * z / (2 * n)) / (1 + z * z / n)
    margen = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return (centro - margen, centro + margen)


def ic_bootstrap_nps(
    valores: list[int], repeticiones: int = 10_000, semilla: int = 2610
) -> tuple[float, float]:
    azar = np.random.default_rng(semilla)
    datos = np.asarray(valores)
    muestras = [nps(list(azar.choice(datos, size=len(datos), replace=True))) for _ in range(repeticiones)]
    return (float(np.percentile(muestras, 2.5)), float(np.percentile(muestras, 97.5)))


@dataclass
class Prueba:
    nombre: str
    prueba: str
    estadistico: float
    p: float
    efecto: float
    ic: tuple[float, float]


def contra_umbral(sus: list[float]) -> Prueba:
    """C1: SUS > 68. t de una muestra si Shapiro-Wilk no rechaza; si no, Wilcoxon."""
    datos = np.asarray(sus)
    media = float(datos.mean())
    ic = stats.t.interval(0.95, len(datos) - 1, loc=media, scale=stats.sem(datos))
    if len(datos) >= 3 and stats.shapiro(datos).pvalue > 0.05:
        r = stats.ttest_1samp(datos, UMBRAL_SUS, alternative="greater")
        return Prueba("C1 SUS > 68", "t de una muestra", float(r.statistic), float(r.pvalue), media, ic)
    r = stats.wilcoxon(datos - UMBRAL_SUS, alternative="greater")
    return Prueba("C1 SUS > 68", "Wilcoxon de una muestra", float(r.statistic), float(r.pvalue), media, ic)


def pareada(tradicional: list[float], tukit: list[float]) -> Prueba:
    """C2: carga con Tukit < tradicional. Diferencia = tradicional - Tukit (> 0 es mejora)."""
    dif = np.asarray(tradicional) - np.asarray(tukit)
    media = float(dif.mean())
    ic = stats.t.interval(0.95, len(dif) - 1, loc=media, scale=stats.sem(dif))
    dz = media / float(dif.std(ddof=1)) if dif.std(ddof=1) > 0 else math.nan
    if len(dif) >= 3 and stats.shapiro(dif).pvalue > 0.05:
        r = stats.ttest_1samp(dif, 0.0, alternative="greater")
        return Prueba("C2 RTLX Tukit < tradicional", "t pareada", float(r.statistic), float(r.pvalue), dz, ic)
    r = stats.wilcoxon(dif, alternative="greater")
    return Prueba(
        "C2 RTLX Tukit < tradicional", "Wilcoxon pareada", float(r.statistic), float(r.pvalue), dz, ic
    )


def leer(ruta: str) -> list[dict[str, str]]:
    with open(ruta, newline="", encoding="utf-8") as archivo:
        filas = list(csv.DictReader(archivo))
    faltan = [c for c in COLUMNAS if filas and c not in filas[0]]
    if faltan:
        raise SystemExit(f"faltan columnas: {', '.join(faltan)}")
    return filas


def analizar(filas: list[dict[str, str]]) -> str:
    sus = [puntaje_sus([int(f[f"sus{i}"]) for i in range(1, 11)]) for f in filas]
    nps_v = [int(f["nps"]) for f in filas]
    tlx_trad = [np.mean([float(f[f"tlx_trad_{i}"]) for i in range(1, 7)]) for f in filas]
    tlx_tukit = [np.mean([float(f[f"tlx_tukit_{i}"]) for i in range(1, 7)]) for f in filas]
    salida = [f"n = {len(filas)} participantes"]

    c1 = contra_umbral(sus)
    cumple_c1 = c1.efecto >= UMBRAL_SUS and c1.ic[0] > UMBRAL_SUS
    salida.append(
        f"{c1.nombre}: media {c1.efecto:.1f}, IC95 [{c1.ic[0]:.1f}, {c1.ic[1]:.1f}], "
        f"{c1.prueba} p = {c1.p:.4f} -> {'cumple' if cumple_c1 else 'NO cumple'} (regla estricta)"
    )
    c2 = pareada(tlx_trad, tlx_tukit)
    cumple_c2 = c2.ic[0] > 0 and c2.efecto >= 0.5
    salida.append(
        f"{c2.nombre}: diferencia media {np.mean(np.subtract(tlx_trad, tlx_tukit)):.1f}, "
        f"IC95 [{c2.ic[0]:.1f}, {c2.ic[1]:.1f}], dz = {c2.efecto:.2f}, {c2.prueba} p = {c2.p:.4f} "
        f"-> {'cumple' if cumple_c2 else 'NO cumple'}"
    )
    for tarea in TAREAS:
        validas = [f[tarea] for f in filas if f[tarea] in ("S", "A", "F")]
        exitos = sum(v == "S" for v in validas)
        bajo, alto = wilson(exitos, len(validas))
        marca = ""
        if tarea in CRITICAS:
            marca = (
                " (critica: "
                + ("cumple" if validas and exitos / len(validas) >= UMBRAL_EXITO else "NO cumple")
                + ")"
            )
        tasa = exitos / len(validas) if validas else math.nan
        interacciones = [float(f[f"int_{tarea}"]) for f in filas if f[f"int_{tarea}"]]
        segundos = [float(f[f"seg_{tarea}"]) for f in filas if f[f"seg_{tarea}"]]
        salida.append(
            f"{tarea.upper()}: exito sin ayuda {exitos}/{len(validas)} = {tasa:.0%} "
            f"IC95 [{bajo:.0%}, {alto:.0%}]{marca}; "
            f"interacciones mediana {np.median(interacciones) if interacciones else math.nan:.0f}; "
            f"segundos mediana {np.median(segundos) if segundos else math.nan:.0f}"
        )
    bajo, alto = ic_bootstrap_nps(nps_v)
    salida.append(f"S1 NPS = {nps(nps_v):.0f}, IC95 bootstrap [{bajo:.0f}, {alto:.0f}]")
    return "\n".join(salida)


def sintetico(n: int = 10, semilla: int = 2610) -> list[dict[str, str]]:
    azar = random.Random(semilla)
    filas = []
    for i in range(n):
        fila: dict[str, str] = {"codigo": f"ACU-{i + 1:02d}"}
        for k in range(1, 11):
            fila[f"sus{k}"] = str(azar.choice([4, 5]) if k % 2 else azar.choice([1, 2]))
        fila["nps"] = str(azar.choice([6, 8, 9, 10]))
        for k in range(1, 7):
            fila[f"tlx_trad_{k}"] = str(azar.randint(50, 85))
            fila[f"tlx_tukit_{k}"] = str(azar.randint(15, 45))
        for t in TAREAS:
            fila[t] = azar.choice(["S", "S", "S", "A"])
            fila[f"int_{t}"] = str(azar.randint(3, 15))
            fila[f"seg_{t}"] = str(azar.randint(30, 200))
        filas.append(fila)
    return filas


def _autoprueba() -> None:
    # Valores conocidos del SUS: todo neutro da 50; el mejor patron, 100; el peor, 0.
    assert puntaje_sus([3] * 10) == 50.0
    assert puntaje_sus([5, 1] * 5) == 100.0
    assert puntaje_sus([1, 5] * 5) == 0.0
    assert nps([10, 9, 8, 7, 6]) == 20.0 and nps([10, 9, 6, 5, 8]) == 0.0
    bajo, alto = wilson(8, 10)
    assert round(bajo, 2) == 0.49 and round(alto, 2) == 0.94


if __name__ == "__main__":
    _autoprueba()
    if len(sys.argv) > 1 and sys.argv[1] == "--sintetico":
        print("(datos sinteticos: solo prueban el cuaderno, no son resultados)")
        print(analizar(sintetico()))
    elif len(sys.argv) > 1:
        print(analizar(leer(sys.argv[1])))
    else:
        raise SystemExit(__doc__)
