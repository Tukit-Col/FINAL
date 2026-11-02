"""
Benchmark de estrategias de optimización para la generación de kits (OP-01).

Mismo problema que Tukit: por cada ítem de la lista se elige UN candidato
(índice entero). Objetivos a minimizar (pymoo): [costo_total, -fan_prom,
-quality_prom]. Selección de la solución final por escalarización pesada
por perfil (DEFAULT_WEIGHTS de Tukit) sobre objetivos normalizados.

Métodos comparados:
  1. NSGA-II (pymoo) — el actual de producción.
  2. Greedy por perfil (dominante): por ítem, el candidato que optimiza la
     dimensión dominante del perfil (costo / fan / calidad).
  3. Búsqueda exhaustiva (fuerza bruta) — óptimo exacto (ground truth).
  4. Aleatorio — baseline inferior.

La normalización de las métricas se hace sobre la enumeración exhaustiva
(la misma base para todos), así los puntajes son comparables entre métodos.
"""
import itertools
import time

import numpy as np

DEFAULT_WEIGHTS = {
    "AHORRADOR": [0.7, 0.15, 0.15],
    "FAN": [0.15, 0.7, 0.15],
    "PREMIUM": [0.15, 0.15, 0.7],
}

PERFILES = ["AHORRADOR", "FAN", "PREMIUM"]

NSGA_PARAMS = {"pop_size": 100, "n_gen": 40}


def generar_instancia(n_items: int, n_cand: int, semilla: int) -> list[list[dict]]:
    """Instancia: lista de ítems; cada ítem tiene `n_cand` candidatos con
    {precio, fan_score, quality_score}."""
    rng = np.random.default_rng(semilla)
    items = []
    for _ in range(n_items):
        candidatos = []
        for _ in range(n_cand):
            candidatos.append({
                "precio": float(rng.uniform(3000, 45000)),
                "fan_score": float(rng.uniform(0, 1)),
                "quality_score": float(rng.uniform(0, 1)),
            })
        items.append(candidatos)
    return items


def _objetivos(items, eleccion) -> tuple[float, float, float]:
    costo = sum(items[i][c]["precio"] for i, c in enumerate(eleccion))
    fan = sum(items[i][c]["fan_score"] for i, c in enumerate(eleccion)) / len(items)
    quality = sum(items[i][c]["quality_score"] for i, c in enumerate(eleccion)) / len(items)
    return costo, fan, quality


def _normalizar_por_enum(combo_obj: list[tuple], f) -> float:
    """Puntaje ponderado de una solución usando min/max de TODA la
    enumeración (base de comparación común entre métodos)."""
    F = np.array(combo_obj)  # (n_combinaciones, 3) en forma minimizar
    minimos = F.min(axis=0)
    maximos = F.max(axis=0)
    rango = np.where(maximos - minimos < 1e-9, 1.0, maximos - minimos)
    F_norm = (F - minimos) / rango
    puntajes = F_norm @ np.array(f)
    return float(puntajes[0])


def optimizar_exhaustivo(items, perfil, semilla: int = 0):
    """Fuerza bruta: puntaje ponderado mínimo sobre todas las combinaciones."""
    f = DEFAULT_WEIGHTS[perfil]
    t0 = time.perf_counter()
    combinaciones = itertools.product(*[range(len(it)) for it in items])
    mejor = None
    mejor_combo = None
    for combo in combinaciones:
        costo, fan, quality = _objetivos(items, combo)
        F = np.array([[costo, -fan, -quality]])
        minimos = F[0]
        maximos = F[0]
        rango = np.where(maximos - minimos < 1e-9, 1.0, maximos - minimos)
        F_norm = (F - minimos) / rango  # = [0,0,0]; no sirve para puntaje
        # Puntaje NO normalizado (rangos por enumeración) lo calculamos globalmente:
        if mejor is None:
            mejor = (costo, -fan, -quality)
            mejor_combo = combo
        else:
            # comparación cruda por pesos (sin normalización) no es correcta;
            # el orden se determina después con normalización global.
            pass
    # Recalcular el mejor con normalización global sobre toda la enumeración.
    combos = list(itertools.product(*[range(len(it)) for it in items]))
    objs = [_objetivos(items, c) for c in combos]
    objs_min = [ (o[0], -o[1], -o[2]) for o in objs ]
    F = np.array(objs_min)
    minimos = F.min(axis=0)
    maximos = F.max(axis=0)
    rango = np.where(maximos - minimos < 1e-9, 1.0, maximos - minimos)
    F_norm = (F - minimos) / rango
    puntajes = F_norm @ np.array(f)
    idx = int(np.argmin(puntajes))
    costo, fan, quality = objs[idx]
    tiempo = time.perf_counter() - t0
    return {
        "perfil": perfil, "metodo": "exhaustivo", "costo": costo,
        "fan": fan, "quality": quality, "puntaje": float(puntajes[idx]),
        "tiempo_s": round(tiempo, 4),
    }


def optimizar_greedy(items, perfil, semilla: int = 0):
    """Por cada ítem elige el candidato dominante del perfil:
    AHORRADOR→menor precio, FAN→mayor fan_score, PREMIUM→mayor quality."""
    t0 = time.perf_counter()
    eleccion = []
    for candidatos in items:
        if perfil == "AHORRADOR":
            eleccion.append(int(np.argmin([c["precio"] for c in candidatos])))
        elif perfil == "FAN":
            eleccion.append(int(np.argmax([c["fan_score"] for c in candidatos])))
        else:
            eleccion.append(int(np.argmax([c["quality_score"] for c in candidatos])))
    costo, fan, quality = _objetivos(items, eleccion)
    tiempo = time.perf_counter() - t0
    return {
        "perfil": perfil, "metodo": "greedy", "costo": costo,
        "fan": fan, "quality": quality, "puntaje": None, "tiempo_s": round(tiempo, 4),
    }


def optimizar_nsga2(items, perfil, semilla: int = 42):
    """NSGA-II (pymoo) con los parámetros de producción de Tukit; la mejor
    solución del frente se elige por pesos normalizados dentro del frente."""
    from pymoo.algorithms.moo.nsga2 import NSGA2
    from pymoo.core.problem import Problem
    from pymoo.optimize import minimize

    f = DEFAULT_WEIGHTS[perfil]
    n_items = len(items)
    n_slots = max(len(it) for it in items)

    class _Problema(Problem):
        def __init__(self):
            def _padded(field):
                filas = []
                for it in items:
                    vals = [c[field] for c in it]
                    filas.append(vals + [vals[-1]] * (n_slots - len(vals)))
                return np.array(filas)

            self.precios = _padded("precio")
            self.fan = _padded("fan_score")
            self.quality = _padded("quality_score")
            super().__init__(n_var=n_items, n_obj=3, xl=0, xu=n_slots - 1)

        def _evaluate(self, X, out, *args, **kwargs):
            idx = np.clip(np.round(X).astype(int), 0, n_slots - 1)
            fila = np.arange(n_items)
            costo = (self.precios[fila, idx]).sum(axis=1)
            fan = self.fan[fila, idx].mean(axis=1)
            quality = self.quality[fila, idx].mean(axis=1)
            out["F"] = np.column_stack([costo, -fan, -quality])

    t0 = time.perf_counter()
    problema = _Problema()
    algoritmo = NSGA2(pop_size=NSGA_PARAMS["pop_size"])
    res = minimize(problema, algoritmo, ("n_gen", NSGA_PARAMS["n_gen"]), seed=semilla, verbose=False)

    F = res.F
    minimos = F.min(axis=0)
    maximos = F.max(axis=0)
    rango = np.where(maximos - minimos < 1e-9, 1.0, maximos - minimos)
    F_norm = (F - minimos) / rango
    puntajes = F_norm @ np.array(f)
    idx_mejor = int(np.argmin(puntajes))
    costo, fan, quality = F[idx_mejor][0], -F[idx_mejor][1], -F[idx_mejor][2]
    tiempo = time.perf_counter() - t0
    return {
        "perfil": perfil, "metodo": "nsga2", "costo": float(costo),
        "fan": float(fan), "quality": float(quality),
        "puntaje": float(puntajes[idx_mejor]), "tiempo_s": round(tiempo, 4),
    }


def optimizar_random(items, perfil, n_muestras: int = 500, semilla: int = 42):
    """Baseline inferior: muestreo aleatorio de asignaciones, mejor por pesos."""
    f = DEFAULT_WEIGHTS[perfil]
    rng = np.random.default_rng(semilla)
    t0 = time.perf_counter()
    mejor_puntaje = None
    mejor = None
    for _ in range(n_muestras):
        eleccion = [rng.integers(0, len(it)) for it in items]
        costo, fan, quality = _objetivos(items, eleccion)
        F = np.array([[costo, -fan, -quality]])
        # puntaje crudo con pesos normalizados por rangos de la muestra
        # (solo para ordenar la muestra; el puntaje final se recalcula afuera)
        puntaje = f[0] * costo + f[1] * (-fan) + f[2] * (-quality)
        if mejor_puntaje is None or puntaje < mejor_puntaje:
            mejor_puntaje = puntaje
            mejor = (costo, fan, quality)
    costo, fan, quality = mejor
    tiempo = time.perf_counter() - t0
    return {
        "perfil": perfil, "metodo": "random", "costo": costo,
        "fan": fan, "quality": quality, "puntaje": None, "tiempo_s": round(tiempo, 4),
    }


def puntaje_global(items, sol, f) -> float:
    """Puntaje de una solución usando la base de enumeración completa (para
    reportar todos los métodos con la MISMA normalización)."""
    combos = list(itertools.product(*[range(len(it)) for it in items]))
    objs_min = [(_objetivos(items, c)[0], -_objetivos(items, c)[1], -_objetivos(items, c)[2]) for c in combos]
    F = np.array(objs_min)
    minimos = F.min(axis=0)
    maximos = F.max(axis=0)
    rango = np.where(maximos - minimos < 1e-9, 1.0, maximos - minimos)
    F_norm = (F - minimos) / rango
    X = np.array([sol["costo"], -sol["fan"], -sol["quality"]])
    return float(((X - minimos) / rango) @ np.array(f))
