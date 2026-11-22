"""Experimento C2: estabilidad del kit recomendado ante cambios en los pesos.
Uso: uv run python ensayos/calibracion/sensibilidad.py
Salida: ensayos/calibracion/salidas/sensibilidad.json"""

from __future__ import annotations

import json

import nucleo as n
import numpy as np
from tukit_inteligencia.modelos import PESOS_POR_OMISION
from tukit_inteligencia.optimizador import elegir_recomendado_maut, optimizar_frente

CRITERIOS = ("precio", "marca_exigida", "calidad", "personaje")
KAPPAS = (20, 50, 100, 200)
SOBREPRECIOS = (0.0, 0.05, 0.10, 0.20)
PERTURBACIONES = 1000
SEMILLA_FRENTE = 0


def listas_de_prueba() -> list[dict]:
    datos = json.loads((n.SALIDA / "calibracion_nsga.json").read_text())
    colegios = set(datos["particion"]["colegios_prueba"])
    return [i for i in n.instancias() if i["colegio"] in colegios]


def clave(s) -> tuple:
    return (s.costo, s.fidelidad, s.disponibilidad, s.personaje)


def mismo_punto(frente, w, s, base) -> bool:
    return clave(
        elegir_recomendado_maut(frente, dict(zip(CRITERIOS, w, strict=True)), sobreprecio=s)
    ) == clave(base)


def main() -> int:
    rng = np.random.default_rng(n.SEMILLA_BASE)
    w0 = np.array([PESOS_POR_OMISION[c] for c in CRITERIOS])
    ic = json.loads((n.SALIDA / "pesos_p21.json").read_text())["ic95"]
    bajos = np.array([ic[c][0] for c in CRITERIOS])
    altos = np.array([ic[c][1] for c in CRITERIOS])
    por_celda: dict[tuple[int, float], list[float]] = {(k, s): [] for k in KAPPAS for s in SOBREPRECIOS}
    en_ic: dict[float, list[float]] = {s: [] for s in SOBREPRECIOS}
    tamanos = []
    for inst in listas_de_prueba():
        renglones = n.renglones_de(inst)
        frente = optimizar_frente(renglones, {}, semilla=SEMILLA_FRENTE)
        if len(frente) < 2:
            continue
        tamanos.append(len(frente))
        for s in SOBREPRECIOS:
            base = elegir_recomendado_maut(frente, dict(zip(CRITERIOS, w0, strict=True)), sobreprecio=s)
            for k in KAPPAS:
                ws = rng.dirichlet(k * w0, size=PERTURBACIONES)
                iguales = sum(mismo_punto(frente, w, s, base) for w in ws)
                por_celda[(k, s)].append(iguales / PERTURBACIONES)
            ws = rng.uniform(bajos, altos, size=(PERTURBACIONES, len(CRITERIOS)))
            ws = ws / ws.sum(axis=1, keepdims=True)
            iguales = sum(mismo_punto(frente, w, s, base) for w in ws)
            en_ic[s].append(iguales / PERTURBACIONES)

    celdas = []
    for (k, s), xs in por_celda.items():
        x = np.array(xs)
        medias = [x[rng.integers(0, len(x), len(x))].mean() for _ in range(5000)]
        celdas.append(
            {
                "kappa": k,
                "sobreprecio": s,
                "listas": len(x),
                "sd_componente_precio": float(np.sqrt(w0[0] * (1 - w0[0]) / (k + 1))),
                "estable_medio": float(x.mean()),
                "ic95": [float(v) for v in np.percentile(medias, [2.5, 97.5])],
                "estable_minimo_lista": float(x.min()),
            }
        )
    dentro_ic = []
    for s, xs in en_ic.items():
        x = np.array(xs)
        medias = [x[rng.integers(0, len(x), len(x))].mean() for _ in range(5000)]
        dentro_ic.append(
            {
                "sobreprecio": s,
                "listas": len(x),
                "estable_medio": float(x.mean()),
                "ic95": [float(v) for v in np.percentile(medias, [2.5, 97.5])],
                "estable_minimo_lista": float(x.min()),
                "listas_estables_100": int((x == 1.0).sum()),
            }
        )
    n.guardar(
        "sensibilidad.json",
        {
            "pesos": dict(zip(CRITERIOS, map(float, w0), strict=True)),
            "perturbaciones": PERTURBACIONES,
            "listas": len(tamanos),
            "puntos_del_frente_mediana": float(np.median(tamanos)),
            "celdas": celdas,
            "dentro_ic95_p21": dentro_ic,
        },
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
