"""Los cuatro constructores del frente que se comparan.

Todos reciben las lineas decidibles `dec`, sus admisibles `opciones` y las
preferencias del acudiente, y devuelven una lista de `SolucionFrente` de
produccion (mismos objetivos, misma deduplicacion, mismo orden):

- `enumeracion`          el `_frente_exacto` de produccion (fuerza bruta).
- `programacion_dinamica` el frente exacto por la recurrencia del Teorema
                          "El frente exacto se calcula en tiempo polinomial"
                          (docs/algoritmos/secciones/07-optimizacion.tex).
- `nsga2_produccion`     el `_frente_nsga` de produccion (siembra heuristica +
                          escalera, N(n), G(|E|), SBX/PM con redondeo).
- `nsga2_sin_siembra`    el mismo NSGA-II con poblacion inicial al azar y sin
                          reinyectar las semillas en el filtro final.
- `voraz`                la linea base: los tres kits de `elegir_por_perfil`
                          mas los peldanos de la escalera de costo marginal.

Ademas, `dp_presupuesto` es la mochila de eleccion multiple del Teorema
"El compromiso con presupuesto es polinomial" (O(n^2 k)).
"""

from __future__ import annotations

import math
from typing import Any

import numpy as np

from tukit_final import opt

SolucionFrente = opt.SolucionFrente


# ----------------------------------------------------------------- enumeracion


def enumeracion(dec, opciones, prefs) -> list[SolucionFrente]:
    return opt._frente_exacto(dec, opciones, prefs)


# ------------------------------------------------------ programacion dinamica


def _aportes(dec, opciones, prefs) -> list[list[tuple[int, int, int, int]]]:
    """(g1, nivel, con_precio, personaje) de cada candidato, con las reglas de produccion."""
    aportes = []
    for r, ops in zip(dec, opciones, strict=True):
        pedidos = {p.lower() for p in opt._personajes_de(prefs, r.hijo)}
        fila = []
        for c in ops:
            if c.precio_cop is not None:
                g1 = c.precio_cop * opt.unidades_a_comprar(r.cantidad, c.unidades_por_empaque)
                b = 1
            else:
                g1, b = 0, 0
            p = 1 if (c.personaje and (not pedidos or c.personaje.lower() in pedidos)) else 0
            fila.append((g1, c.rango_nivel, b, p))
        aportes.append(fila)
    return aportes


def programacion_dinamica(dec, opciones, prefs, *, info: dict | None = None) -> list[SolucionFrente]:
    """Frente de Pareto exacto de los cuatro objetivos por programacion dinamica.

    Estado tras procesar i lineas: la terna (a, b, p) = (suma de niveles, lineas
    con precio, lineas con el personaje). C_i(a, b, p) es el minimo costo de una
    asignacion parcial con esa terna:

        C_0(0,0,0) = 0
        C_i(t)     = min_{c in A_i} C_{i-1}(t - (nivel(c), precio(c)!=None, phi_i(c))) + g_{1,i}(c)

    Solo se guardan las ternas alcanzables (diccionario disperso). El frente es
    el conjunto de vectores no dominados de {(C_n(t), a/(2n), b/n, p/n)}; el
    filtro final usa el minimo acumulado sobre el ortante t' >= t (O(#ternas)).
    La asignacion se recupera con la eleccion guardada por etapa.

    Peor caso: (2i+1)(i+1)^2 ternas tras i lineas -> O(n^4 k) tiempo y memoria
    para las elecciones. `info` recibe el numero de ternas por etapa.
    """
    n = len(dec)
    if n == 0:
        return []
    aportes = _aportes(dec, opciones, prefs)
    base = n + 1
    # La terna se codifica como un entero: clave = (a*base + b)*base + p. La
    # codificacion es lineal, asi que sumar un aporte es sumar su clave.
    delta = [[(g1, (a * base + b) * base + p) for (g1, a, b, p) in fila] for fila in aportes]

    actual: dict[int, int] = {0: 0}
    elecciones: list[dict[int, int]] = []
    ternas_por_etapa = []
    for fila in delta:
        nuevo: dict[int, int] = {}
        eleccion: dict[int, int] = {}
        for clave, costo in actual.items():
            for j, (g1, dk) in enumerate(fila):
                k2 = clave + dk
                c2 = costo + g1
                previo = nuevo.get(k2)
                if previo is None or c2 < previo:
                    nuevo[k2] = c2
                    eleccion[k2] = j
        elecciones.append(eleccion)
        actual = nuevo
        ternas_por_etapa.append(len(actual))

    claves = np.fromiter(actual.keys(), dtype=np.int64, count=len(actual))
    costos = np.fromiter(actual.values(), dtype=np.float64, count=len(actual))
    p = claves % base
    b = (claves // base) % base
    a = claves // (base * base)
    no_dominadas = _filtro_ortante(a, b, p, costos)

    frente = []
    for clave in claves[no_dominadas].tolist():
        js = [0] * n
        k = clave
        for i in range(n - 1, -1, -1):
            j = elecciones[i][k]
            js[i] = j
            k -= delta[i][j][1]
        elegidos = [opciones[i][j] for i, j in enumerate(js)]
        frente.append(opt._solucion(dec, elegidos, prefs))
    frente.sort(key=lambda s: (s.costo, -s.fidelidad, -s.disponibilidad, -s.personaje))
    if info is not None:
        info["ternas_finales"] = int(len(actual))
        info["ternas_max_etapa"] = int(max(ternas_por_etapa))
        info["ternas_total"] = int(sum(ternas_por_etapa))
    return frente


def _filtro_ortante(a, b, p, costos) -> np.ndarray:
    """Mascara de ternas no dominadas: t lo esta si existe t' >= t, t' != t, con C(t') <= C(t)."""
    a0, b0, p0 = a.min(), b.min(), p.min()
    forma = (int(a.max() - a0) + 2, int(b.max() - b0) + 2, int(p.max() - p0) + 2)
    rejilla = np.full(forma, np.inf)
    ia, ib, ip = a - a0, b - b0, p - p0
    rejilla[ia, ib, ip] = costos
    # Suf(t) = min_{t' >= t} C(t'): minimo acumulado de atras hacia adelante en cada eje.
    suf = rejilla
    for eje in range(3):
        suf = np.flip(np.minimum.accumulate(np.flip(suf, axis=eje), axis=eje), axis=eje)
    # Minimo sobre t' >= t con t' != t: el de los tres vecinos t + e_j.
    vecinos = np.minimum(np.minimum(suf[ia + 1, ib, ip], suf[ia, ib + 1, ip]), suf[ia, ib, ip + 1])
    return ~(vecinos <= costos)


def dp_presupuesto(dec, opciones, presupuesto: int) -> list[int] | None:
    """Maxima fidelidad con costo <= presupuesto (MCKP), O(n^2 k).

    M_i(s) = minimo costo de las primeras i lineas con suma de niveles s. Se
    devuelven los indices elegidos o None si nada cabe. A igual fidelidad gana
    el menor costo.
    """
    aportes = _aportes(dec, opciones, {})
    mejor: dict[int, tuple[int, list[int]]] = {0: (0, [])}
    for fila in aportes:
        nuevo: dict[int, tuple[int, list[int]]] = {}
        for s, (costo, elec) in mejor.items():
            for j, (g1, nivel, _b, _p) in enumerate(fila):
                s2 = s + nivel
                c2 = costo + g1
                if s2 not in nuevo or c2 < nuevo[s2][0]:
                    nuevo[s2] = (c2, elec + [j])
        mejor = nuevo
    factibles = [(s, c, e) for s, (c, e) in mejor.items() if c <= presupuesto]
    if not factibles:
        return None
    return max(factibles, key=lambda t: (t[0], -t[1]))[2]


# ---------------------------------------------------------------------- NSGA-II


def nsga2_produccion(dec, opciones, prefs, *, semilla: int = 0) -> list[SolucionFrente]:
    return opt._frente_nsga(dec, opciones, prefs, semilla=semilla)


def nsga2_sin_siembra(dec, opciones, prefs, *, semilla: int = 0) -> list[SolucionFrente]:
    """El NSGA-II de produccion sin siembra: mismos N, G, operadores y semilla.

    Es la copia de `_frente_nsga` con la poblacion inicial 100 % al azar (el
    mismo generador con la misma semilla) y sin reinyectar las semillas en el
    filtro final. Mide cuanto del resultado de produccion se debe al algoritmo
    evolutivo y cuanto a la siembra voraz.
    """
    from pymoo.algorithms.moo.nsga2 import NSGA2
    from pymoo.core.problem import Problem
    from pymoo.operators.crossover.sbx import SBX
    from pymoo.operators.mutation.pm import PM
    from pymoo.operators.repair.rounding import RoundingRepair
    from pymoo.optimize import minimize

    n = len(dec)
    tamanos = [len(o) for o in opciones]

    def indices(x) -> list[int]:
        return [min(tamanos[i] - 1, max(0, int(round(float(x[i]))))) for i in range(n)]

    class _Problema(Problem):
        def __init__(self) -> None:
            super().__init__(
                n_var=n,
                n_obj=4,
                n_constr=0,
                xl=np.zeros(n, dtype=int),
                xu=np.array([t - 1 for t in tamanos], dtype=int),
                vtype=int,
            )

        def _evaluate(self, X, out, *args, **kwargs):  # noqa: N802
            filas = []
            for fila in X:
                elegidos = [opciones[i][idx] for i, idx in enumerate(indices(fila))]
                c, f, d, p = opt._objetivos_de_asignacion(dec, elegidos, prefs)
                filas.append([c, -f, -d, -p])
            out["F"] = np.array(filas, dtype=float)

    espacio = math.prod(tamanos)
    tamano = opt._poblacion(n)
    algoritmo = NSGA2(
        pop_size=tamano,
        sampling=opt._poblacion_inicial([], tamanos, tamano, semilla),
        crossover=SBX(prob=0.9, eta=15, repair=RoundingRepair()),
        mutation=PM(prob=1.0, eta=20, repair=RoundingRepair()),
        eliminate_duplicates=True,
    )
    res = minimize(_Problema(), algoritmo, ("n_gen", opt._generaciones(espacio)), seed=semilla, verbose=False)
    matriz = np.atleast_2d(res.X) if res.X is not None else np.empty((0, n))
    soluciones = [
        opt._solucion(dec, [opciones[i][idx] for i, idx in enumerate(indices(fila))], prefs) for fila in matriz
    ]
    return opt._no_dominadas(soluciones)


# ------------------------------------------------------------------------ voraz


def semillas_voraces(dec, opciones, prefs) -> list[list[int]]:
    """Los tres kits de `elegir_por_perfil` y los peldanos de la escalera (indices)."""
    filas = []
    for perfil in opt.PerfilKit:
        fila = []
        for i, r in enumerate(dec):
            elegido = opt.elegir_por_perfil(
                tuple(opciones[i]),
                perfil.value,
                personajes=opt._personajes_de(prefs, r.hijo),
                cantidad=r.cantidad,
            )
            fila.append(next((j for j, c in enumerate(opciones[i]) if c is elegido), 0))
        filas.append(fila)
    filas.extend(opt._escalera_costo_marginal(dec, opciones))
    return filas


def voraz(dec, opciones, prefs) -> list[SolucionFrente]:
    sols = [
        opt._solucion(dec, [opciones[i][j] for i, j in enumerate(fila)], prefs)
        for fila in semillas_voraces(dec, opciones, prefs)
    ]
    return opt._no_dominadas(sols)


ALGORITMOS: dict[str, Any] = {
    "enumeracion": enumeracion,
    "dp": programacion_dinamica,
    "nsga2": nsga2_produccion,
    "nsga2_sin_siembra": nsga2_sin_siembra,
    "voraz": voraz,
}
