"""El frente de Pareto de un kit: enumeracion exacta para espacios chicos y NSGA-II para los grandes.

Decisiones:
- `LIMITE_ENUMERACION = 4096` (2^12) es el espacio de busqueda (producto de candidatos por linea)
  por encima del cual se corre NSGA-II; queda entre el cruce medido con el NSGA-II calibrado en la
  mediana (S ~ 4932) y en el percentil 95 del ajuste (S ~ 2380).
- El presupuesto de busqueda escala con el numero de lineas decidibles y con el espacio, con topes
  para que una lista enorme no dispare el tiempo. Son la mitad de las formulas de partida,
  elegidos por validacion cruzada agrupada por colegio: la configuracion mas barata cuyo
  hipervolumen medio queda a menos de 0,1 % del mejor de la rejilla.
- La terminacion es por numero fijo de generaciones y no por convergencia, porque el frente de una
  semilla dada tiene que reproducirse byte a byte.
"""

from __future__ import annotations

import math
from itertools import product
from typing import Any

import numpy as _np
from pymoo.algorithms.moo.nsga2 import NSGA2
from pymoo.core.problem import Problem
from pymoo.operators.crossover.sbx import SBX
from pymoo.operators.mutation.pm import PM
from pymoo.operators.repair.rounding import RoundingRepair
from pymoo.optimize import minimize as _minimizar
from tukit_comun.texto import normalizar_personaje

from ..modelos import PerfilKit
from .candidatos import elegir_por_perfil
from .preferencias import _personajes_de
from .tipos import (
    ORDEN_NIVEL,
    Candidato,
    Renglon,
    SolucionFrente,
    _admisibles,
    _costo_para_ordenar,
    unidades_a_comprar,
)

LIMITE_ENUMERACION = 4096


_POBLACION_POR_LINEA = 6


_POBLACION_MIN = 20


_POBLACION_MAX = 100


_GENERACIONES_POR_DECADA = 10


_GENERACIONES_MIN = 15


_GENERACIONES_MAX = 60


def _poblacion(n: int) -> int:
    cruda = min(_POBLACION_MAX, max(_POBLACION_MIN, _POBLACION_POR_LINEA * n))
    return cruda + (cruda & 1)


def _generaciones(espacio: int) -> int:
    crudas = _GENERACIONES_POR_DECADA * math.log10(max(10, espacio))
    return int(min(_GENERACIONES_MAX, max(_GENERACIONES_MIN, crudas)))


def _objetivos_de_asignacion(
    decidibles: list[Renglon],
    elegidos: list[Candidato],
    preferencias: dict[str, Any],
) -> tuple[int, float, float, float]:
    if not decidibles:
        return (0, 0.0, 0.0, 0.0)

    costo = 0
    suma_fidelidad = 0.0
    con_precio = 0
    con_personaje = 0
    tope_nivel = max(1, len(ORDEN_NIVEL) - 1)
    for renglon, elegido in zip(decidibles, elegidos, strict=True):
        unidades = unidades_a_comprar(renglon.cantidad, elegido.unidades_por_empaque)
        if elegido.precio_cop is not None:
            costo += elegido.precio_cop * unidades
            con_precio += 1
        suma_fidelidad += elegido.rango_nivel / tope_nivel
        pedidos = {normalizar_personaje(p) for p in _personajes_de(preferencias, renglon.hijo)}
        if elegido.personaje and (not pedidos or normalizar_personaje(elegido.personaje) in pedidos):
            con_personaje += 1

    n = len(decidibles)
    return (
        costo,
        round(suma_fidelidad / n, 6),
        round(con_precio / n, 6),
        round(con_personaje / n, 6),
    )


def _domina(a: tuple[int, float, float, float], b: tuple[int, float, float, float]) -> bool:
    no_peor = a[0] <= b[0] and a[1] >= b[1] and a[2] >= b[2] and a[3] >= b[3]
    estricto = a[0] < b[0] or a[1] > b[1] or a[2] > b[2] or a[3] > b[3]
    return no_peor and estricto


def _no_dominadas(soluciones: list[SolucionFrente]) -> list[SolucionFrente]:
    unicas: dict[tuple[int, float, float, float], SolucionFrente] = {}
    for s in soluciones:
        clave = (s.costo, s.fidelidad, s.disponibilidad, s.personaje)
        unicas.setdefault(clave, s)

    puntos = list(unicas.values())
    frente = [
        s
        for s in puntos
        if not any(
            _domina(
                (o.costo, o.fidelidad, o.disponibilidad, o.personaje),
                (s.costo, s.fidelidad, s.disponibilidad, s.personaje),
            )
            for o in puntos
            if o is not s
        )
    ]
    frente.sort(key=lambda s: (s.costo, -s.fidelidad, -s.disponibilidad, -s.personaje))
    return frente


def _solucion(
    decidibles: list[Renglon], elegidos: list[Candidato], preferencias: dict[str, Any]
) -> SolucionFrente:
    costo, fidelidad, disponibilidad, personaje = _objetivos_de_asignacion(decidibles, elegidos, preferencias)
    asignacion = {(r.hijo, r.orden): c.sku for r, c in zip(decidibles, elegidos, strict=True)}
    return SolucionFrente(asignacion, costo, fidelidad, disponibilidad, personaje)


def _frente_exacto(
    decidibles: list[Renglon],
    opciones: list[list[Candidato]],
    preferencias: dict[str, Any],
) -> list[SolucionFrente]:
    soluciones = [_solucion(decidibles, list(combo), preferencias) for combo in product(*opciones)]
    return _no_dominadas(soluciones)


def _escalera_costo_marginal(decidibles: list[Renglon], opciones: list[list[Candidato]]) -> list[list[int]]:

    def costo(i: int, j: int) -> int | None:
        c = opciones[i][j]
        if c.precio_cop is None:
            return None
        return c.precio_cop * unidades_a_comprar(decidibles[i].cantidad, c.unidades_por_empaque)

    actual = [
        min(
            range(len(o)),
            key=lambda j, i=i, o=o: (
                _costo_para_ordenar(o[j], decidibles[i].cantidad),
                -o[j].rango_nivel,
                o[j].sku,
            ),
        )
        for i, o in enumerate(opciones)
    ]
    peldanos = [list(actual)]
    while True:
        mejor: tuple[float, int, int, int] | None = None
        for i, o in enumerate(opciones):
            costo_actual = costo(i, actual[i]) or 0
            nivel_actual = o[actual[i]].rango_nivel
            for j, candidato in enumerate(o):
                costo_j = costo(i, j)
                if costo_j is None or candidato.rango_nivel <= nivel_actual:
                    continue
                extra = costo_j - costo_actual
                clave = (extra / (candidato.rango_nivel - nivel_actual), extra, i, j)
                if mejor is None or clave < mejor:
                    mejor = clave
        if mejor is None:
            return peldanos
        _, _, i, j = mejor
        actual[i] = j
        peldanos.append(list(actual))


def _poblacion_inicial(
    semillas: list[list[int]], tamanos: list[int], tamano_poblacion: int, semilla: int
) -> _np.ndarray:
    unicas = list(dict.fromkeys(tuple(s) for s in semillas))
    if len(unicas) > tamano_poblacion:
        pasos = _np.linspace(0, len(unicas) - 1, tamano_poblacion).round().astype(int)
        unicas = [unicas[k] for k in dict.fromkeys(pasos.tolist())]
    generador = _np.random.default_rng(semilla)
    faltan = tamano_poblacion - len(unicas)
    azar = (
        generador.integers(0, _np.array(tamanos), size=(faltan, len(tamanos)))
        if faltan > 0
        else _np.empty((0, len(tamanos)), dtype=int)
    )
    sembradas = _np.array(unicas, dtype=int).reshape(-1, len(tamanos))
    return _np.vstack([sembradas, azar]).astype(int)


def _frente_nsga(
    decidibles: list[Renglon],
    opciones: list[list[Candidato]],
    preferencias: dict[str, Any],
    *,
    semilla: int,
) -> list[SolucionFrente]:
    n = len(decidibles)
    tamanos = [len(o) for o in opciones]

    sembradas: list[list[int]] = []
    for perfil in PerfilKit:
        fila = []
        for i, r in enumerate(decidibles):
            elegido = elegir_por_perfil(
                tuple(opciones[i]),
                perfil.value,
                personajes=_personajes_de(preferencias, r.hijo),
                cantidad=r.cantidad,
            )
            fila.append(next((j for j, c in enumerate(opciones[i]) if c is elegido), 0))
        sembradas.append(fila)
    sembradas.extend(_escalera_costo_marginal(decidibles, opciones))

    def indices(x: _np.ndarray) -> list[int]:
        return [min(tamanos[i] - 1, max(0, int(round(float(x[i]))))) for i in range(n)]

    preferencias_local = preferencias

    class _ProblemaKit(Problem):
        def __init__(self) -> None:
            super().__init__(
                n_var=n,
                n_obj=4,
                n_constr=0,
                xl=_np.zeros(n, dtype=int),
                xu=_np.array([t - 1 for t in tamanos], dtype=int),
                vtype=int,
            )

        def _evaluate(self, X, out, *args, **kwargs):  # noqa: N802 (pymoo API)
            filas = []
            for fila in X:
                elegidos = [opciones[i][idx] for i, idx in enumerate(indices(fila))]
                costo, fidelidad, disp, pers = _objetivos_de_asignacion(
                    decidibles, elegidos, preferencias_local
                )
                filas.append([costo, -fidelidad, -disp, -pers])
            out["F"] = _np.array(filas, dtype=float)

    espacio = math.prod(tamanos)
    tamano_poblacion = _poblacion(n)
    algoritmo = NSGA2(
        pop_size=tamano_poblacion,
        sampling=_poblacion_inicial(sembradas, tamanos, tamano_poblacion, semilla),
        crossover=SBX(prob=0.9, eta=15, repair=RoundingRepair()),
        mutation=PM(prob=1.0, eta=20, repair=RoundingRepair()),
        eliminate_duplicates=True,
    )
    resultado = _minimizar(
        _ProblemaKit(),
        algoritmo,
        ("n_gen", _generaciones(espacio)),
        seed=semilla,
        verbose=False,
    )

    soluciones: list[SolucionFrente] = []
    matriz = _np.atleast_2d(resultado.X) if resultado.X is not None else _np.empty((0, n))
    for fila in matriz:
        elegidos = [opciones[i][idx] for i, idx in enumerate(indices(fila))]
        soluciones.append(_solucion(decidibles, elegidos, preferencias_local))

    for fila in sembradas:
        elegidos = [opciones[i][j] for i, j in enumerate(fila)]
        soluciones.append(_solucion(decidibles, elegidos, preferencias_local))

    return _no_dominadas(soluciones)


def optimizar_frente(
    renglones: list[Renglon], preferencias: dict[str, Any] | None = None, *, semilla: int = 0
) -> list[SolucionFrente]:
    preferencias = preferencias or {}
    decidibles = [r for r in renglones if not r.informativa and _admisibles(r)]
    if not decidibles:
        return []

    opciones = [_admisibles(r) for r in decidibles]
    espacio = math.prod(len(o) for o in opciones)
    if espacio <= 1:
        return []

    if espacio <= LIMITE_ENUMERACION:
        return _frente_exacto(decidibles, opciones, preferencias)
    return _frente_nsga(decidibles, opciones, preferencias, semilla=semilla)


def _surtibles(frente: list[SolucionFrente]) -> list[SolucionFrente]:
    tope = max(s.disponibilidad for s in frente)
    return [s for s in frente if s.disponibilidad == tope]


def _proyectar(frente: list[SolucionFrente], perfil: str) -> SolucionFrente | None:
    if not frente:
        return None
    frente = _surtibles(frente)
    if perfil == PerfilKit.PREMIUM.value:
        return max(frente, key=lambda s: (s.fidelidad, -s.costo, s.disponibilidad))
    if perfil == PerfilKit.FAN.value:
        mejor = max(frente, key=lambda s: (s.personaje, -s.costo, s.fidelidad))
        if mejor.personaje > 0:
            return mejor
    return min(frente, key=lambda s: (s.costo, -s.disponibilidad, -s.fidelidad))
