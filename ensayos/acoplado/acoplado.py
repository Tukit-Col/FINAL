"""Presupuesto con COSTO FIJO POR TIENDA: PD exacta extendida y NSGA-II del sistema."""

from __future__ import annotations

import itertools
import math
import sys
import time
import zlib
from pathlib import Path

AQUI = Path(__file__).resolve().parent
BENCH = AQUI.parent / "bench_laya"
if str(BENCH) not in sys.path:
    sys.path.insert(0, str(BENCH))

import numpy as _np  # noqa: E402
from comun import TOPE_NIVEL, costo_linea  # noqa: E402
from pymoo.algorithms.moo.nsga2 import NSGA2  # noqa: E402
from pymoo.core.problem import Problem  # noqa: E402
from pymoo.operators.crossover.sbx import SBX  # noqa: E402
from pymoo.operators.mutation.pm import PM  # noqa: E402
from pymoo.operators.repair.rounding import RoundingRepair  # noqa: E402
from pymoo.optimize import minimize as _minimizar  # noqa: E402
from tukit_inteligencia.modelos import PerfilKit  # noqa: E402
from tukit_inteligencia.optimizador import (  # noqa: E402
    _admisibles,
    _escalera_costo_marginal,
    _generaciones,
    _objetivos_de_asignacion,
    _poblacion,
    _poblacion_inicial,
    elegir_por_perfil,
)

F_ENVIO = 10_000


def tienda_de(sku: str, T: int) -> int:
    return zlib.crc32(sku.encode()) % T


class Tiempo(Exception):
    pass


def opciones_de(dec, T):
    salida = []
    for r in dec:
        fila = []
        for c in _admisibles(r):
            bit = (1 << tienda_de(c.sku, T)) if c.precio_cop is not None else 0
            fila.append((min(c.rango_nivel, TOPE_NIVEL), costo_linea(r, c), bit, c.sku))
        salida.append(fila)
    return salida


def pd_exacta(dec, presupuesto, T, F=F_ENVIO, limite_s=None, poda=True):
    t0 = time.perf_counter()
    ops = opciones_de(dec, T)
    capas = []
    actual = {(0, 0): (0, None, -1)}
    estados = 1
    cuenta = 0
    for fila in ops:
        nuevo: dict = {}
        for (s, m), (cost, _, _) in actual.items():
            for j, (niv, cl, bit, _) in enumerate(fila):
                cuenta += 1
                if limite_s is not None and cuenta & 8191 == 0 and time.perf_counter() - t0 > limite_s:
                    raise Tiempo(estados)
                m2 = m | bit
                c2 = cost + cl
                if poda and c2 + F * m2.bit_count() > presupuesto:
                    continue
                k = (s + niv, m2)
                previo = nuevo.get(k)
                if previo is None or c2 < previo[0]:
                    nuevo[k] = (c2, (s, m), j)
        capas.append(nuevo)
        estados += len(nuevo)
        actual = nuevo
        if not actual:
            return None, estados
    factibles = [kv for kv in actual.items() if kv[1][0] + F * kv[0][1].bit_count() <= presupuesto]
    if not factibles:
        return None, estados
    mejor = max(factibles, key=lambda kv: (kv[0][0], -(kv[1][0] + F * kv[0][1].bit_count())))
    (s, m), (cost, _, _) = mejor
    elec = []
    clave = (s, m)
    for i in range(len(ops) - 1, -1, -1):
        c, padre, j = capas[i][clave]
        elec.append(ops[i][j][3])
        clave = padre
    elec.reverse()
    total = cost + F * m.bit_count()
    return (s, total, {str(r.orden): sku for r, sku in zip(dec, elec, strict=True)}), estados


def enumeracion(dec, presupuesto, T, F=F_ENVIO):
    ops = opciones_de(dec, T)
    mejor = None
    for combo in itertools.product(*[range(len(f)) for f in ops]):
        s = costo = mask = 0
        for fila, j in zip(ops, combo, strict=True):
            niv, cl, bit, _ = fila[j]
            s += niv
            costo += cl
            mask |= bit
        total = costo + F * mask.bit_count()
        if total > presupuesto:
            continue
        if mejor is None or (s, -total) > (mejor[0], -mejor[1]):
            mejor = (s, total)
    return mejor


def total_de(dec, asignacion, T, F=F_ENVIO):
    costo = mask = s = 0
    for r in dec:
        sku = asignacion[str(r.orden)]
        c = next(c for c in _admisibles(r) if c.sku == sku)
        costo += costo_linea(r, c)
        s += min(c.rango_nivel, TOPE_NIVEL)
        if c.precio_cop is not None:
            mask |= 1 << tienda_de(c.sku, T)
    return s, costo + F * mask.bit_count()


def nsga_acoplado(dec, presupuesto, T, F=F_ENVIO, semilla=0):
    opciones = [_admisibles(r) for r in dec]
    n = len(dec)
    tamanos = [len(o) for o in opciones]
    prefs: dict = {}

    sembradas = []
    for perfil in PerfilKit:
        fila = []
        for i, r in enumerate(dec):
            el = elegir_por_perfil(tuple(opciones[i]), perfil.value, personajes=(), cantidad=r.cantidad)
            fila.append(next((j for j, c in enumerate(opciones[i]) if c is el), 0))
        sembradas.append(fila)
    sembradas.extend(_escalera_costo_marginal(dec, opciones))

    def indices(x):
        return [min(tamanos[i] - 1, max(0, int(round(float(x[i]))))) for i in range(n)]

    def evaluar(idx):
        elegidos = [opciones[i][j] for i, j in enumerate(idx)]
        costo, fid, disp, pers = _objetivos_de_asignacion(dec, elegidos, prefs)
        mask = 0
        for c in elegidos:
            if c.precio_cop is not None:
                mask |= 1 << tienda_de(c.sku, T)
        return costo + F * mask.bit_count(), fid, disp, pers

    n_eval = 0

    class _P(Problem):
        def __init__(self):
            super().__init__(
                n_var=n,
                n_obj=4,
                n_constr=0,
                xl=_np.zeros(n, dtype=int),
                xu=_np.array([t - 1 for t in tamanos], dtype=int),
                vtype=int,
            )

        def _evaluate(self, X, out, *a, **k):
            nonlocal n_eval
            filas = []
            for fila in X:
                n_eval += 1
                c, f, d, p = evaluar(indices(fila))
                filas.append([c, -f, -d, -p])
            out["F"] = _np.array(filas, dtype=float)

    pop = _poblacion(n)
    alg = NSGA2(
        pop_size=pop,
        sampling=_poblacion_inicial(sembradas, tamanos, pop, semilla),
        crossover=SBX(prob=0.9, eta=15, repair=RoundingRepair()),
        mutation=PM(prob=1.0, eta=20, repair=RoundingRepair()),
        eliminate_duplicates=True,
    )
    res = _minimizar(_P(), alg, ("n_gen", _generaciones(math.prod(tamanos))), seed=semilla, verbose=False)
    cand = [indices(f) for f in (_np.atleast_2d(res.X) if res.X is not None else [])] + sembradas
    mejor = None
    for idx in cand:
        c, f, _, _ = evaluar(idx)
        if c <= presupuesto and (mejor is None or (f, -c) > (mejor[0], -mejor[1])):
            mejor = (
                f,
                c,
                {str(r.orden): opciones[i][j].sku for i, (r, j) in enumerate(zip(dec, idx, strict=True))},
            )
    return mejor, n_eval
