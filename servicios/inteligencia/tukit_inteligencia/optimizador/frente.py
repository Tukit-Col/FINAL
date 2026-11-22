"""El frente de Pareto de un kit: enumeracion exacta para espacios chicos y NSGA-II para los grandes."""

from __future__ import annotations

import math
from itertools import product
from typing import Any

# pymoo es la dependencia DURA del optimizador de la tesis. Se importa arriba,
# sin red: si falta, el servicio no arranca. Antes se importaba de forma
# defensiva y `armar_los_tres` caia a la heuristica cuando pymoo no estaba, pero
# esa degradacion silenciosa era un riesgo real —un despliegue mal configurado
# servia kits que no eran los del algoritmo sin decirlo—. Preferimos fallar
# ruidoso en el arranque a mentir en tiempo de ejecucion. La heuristica
# (`elegir_por_perfil`) sigue viva, pero SOLO para la linea de un unico
# candidato (no hay frente que optimizar) y como referencia de la prueba de
# hipervolumen; nunca como plan B de "pymoo no esta".
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

# Por encima de este tamano del espacio de busqueda (producto de candidatos por
# linea) se corre NSGA-II; por debajo se enumera el frente exacto. 4096 = 2^12
# queda entre el cruce medido de la enumeracion con el NSGA-II calibrado en la
# mediana (S ~ 4932) y en el percentil 95 del ajuste (S ~ 2380). Fuente:
# docs/informes/calibracion/umbral.json y umbral_elegida.json, seccion
# "Complejidad" de docs/informes/calibracion/optimizacion.tex.
LIMITE_ENUMERACION = 4096


# Presupuesto de busqueda del NSGA-II, escalado con el numero de lineas
# decidibles `n` y con el espacio de busqueda `espacio`, con topes para que una
# lista enorme no dispare el tiempo del pipeline. Los valores son la mitad de
# las formulas de partida (factores a = b = 0,5), elegidos por validacion
# cruzada agrupada por colegio: la configuracion mas barata cuyo hipervolumen
# medio queda a menos de 0,1 % del mejor de la rejilla. Fuente:
# docs/informes/calibracion/calibracion_nsga.json, seccion "Calibracion y
# amenazas a la validez" de docs/informes/calibracion/optimizacion.tex.
# La terminacion es por numero fijo de generaciones y no por convergencia,
# porque el frente de una semilla dada tiene que reproducirse byte a byte.
_POBLACION_POR_LINEA = 6


_POBLACION_MIN = 20


_POBLACION_MAX = 100


_GENERACIONES_POR_DECADA = 10


_GENERACIONES_MIN = 15


_GENERACIONES_MAX = 60


def _poblacion(n: int) -> int:
    """Tamano de poblacion escalado a las lineas decidibles, redondeado a par.

    Par porque el emparejamiento de padres de NSGA-II trabaja de a dos y una
    poblacion impar desperdicia un individuo por generacion.
    """
    cruda = min(_POBLACION_MAX, max(_POBLACION_MIN, _POBLACION_POR_LINEA * n))
    return cruda + (cruda & 1)


def _generaciones(espacio: int) -> int:
    """Generaciones escaladas al log10 del espacio de busqueda.

    El espacio crece multiplicativamente (producto de candidatos por linea), asi
    que el esfuerzo util crece con su logaritmo. `max(10, ...)` evita
    `log10(0)` y valores negativos en el piso.
    """
    crudas = _GENERACIONES_POR_DECADA * math.log10(max(10, espacio))
    return int(min(_GENERACIONES_MAX, max(_GENERACIONES_MIN, crudas)))


def _objetivos_de_asignacion(
    decidibles: list[Renglon],
    elegidos: list[Candidato],
    preferencias: dict[str, Any],
) -> tuple[int, float, float, float]:
    """Los cuatro ejes de una asignacion completa, sobre lo comprable.

    - `costo`: suma de subtotales con precio conocido (los sin precio no
      inflan ni abaratan el costo; su falta se refleja en `disponibilidad`).
    - `fidelidad`: nivel de marca promedio, normalizado a [0, 1]. Es lo que
      separa un kit Premium de uno Ahorrador en el frente.
    - `disponibilidad`: fraccion de lineas cuyo candidato tiene precio, o sea
      que Tukit puede efectivamente surtir hoy.
    - `personaje`: fraccion de lineas cuyo candidato trae el personaje que el
      kit Fan buscaria. Se cuenta con la MISMA regla que `elegir_por_perfil`
      Fan: si el acudiente pidio personajes para ese hijo, solo cuenta el que
      coincide; si no pidio ninguno, cuenta cualquier personaje (el Fan es "el
      kit divertido" aunque nadie lo haya pedido explicitamente). Alinear esta
      regla con la heuristica es lo que hace que el frente no pierda el punto
      intermedio que la heuristica surtia por su cuenta.
    """
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
    """`a` domina a `b`: no peor en ningun eje y mejor en al menos uno.

    Se minimiza `costo` y se maximizan `fidelidad`, `disponibilidad` y
    `personaje`, asi que la comparacion mezcla sentidos: costo `<=`, el resto
    `>=`.
    """
    no_peor = a[0] <= b[0] and a[1] >= b[1] and a[2] >= b[2] and a[3] >= b[3]
    estricto = a[0] < b[0] or a[1] > b[1] or a[2] > b[2] or a[3] > b[3]
    return no_peor and estricto


def _no_dominadas(soluciones: list[SolucionFrente]) -> list[SolucionFrente]:
    """Filtra el frente de Pareto de un conjunto de soluciones.

    Se deduplica primero por vector de objetivos para no dejar copias, y se
    ordena el resultado por costo para que el frente salga estable y leible
    (dos corridas del NSGA-II con la misma semilla dan el mismo frente).
    """
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
    """Frente OPTIMO por enumeracion. Exacto e instantaneo para kits chicos."""
    soluciones = [_solucion(decidibles, list(combo), preferencias) for combo in product(*opciones)]
    return _no_dominadas(soluciones)


def _escalera_costo_marginal(decidibles: list[Renglon], opciones: list[list[Candidato]]) -> list[list[int]]:
    """Kits del mas barato al de mejor marca, subiendo de nivel donde cuesta menos.

    Arranca en el kit Ahorrador (el candidato de menor costo de linea en cada
    renglon) y en cada peldano sube UNA linea a un candidato de mejor nivel: la
    que tenga menor costo extra por nivel ganado. Termina cuando ninguna linea
    puede subir. Cada peldano es una asignacion (indice del candidato por linea).

    Es la regla que en el benchmark Laya vs NSGA-II dominaba algun punto del
    frente en el 68 % de las listas: con objetivos que se suman por linea, subir
    donde la marca sale mas barata recorre bien el compromiso costo-fidelidad,
    que es justo lo que SBX/PM (operadores ordinales sobre un indice nominal)
    no siempre encuentran. Por eso siembra la poblacion del NSGA-II y entra al
    filtro final del frente. Los candidatos sin precio no son peldano: su costo
    no se conoce.
    """

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
    """Las asignaciones sembradas primero y el resto al azar, con la semilla fija.

    Si hay mas sembradas que cupos, se toman espaciadas a lo largo de la lista
    (la escalera va de barato a caro, y asi se conserva todo el recorrido). El
    azar sale de un generador con la misma semilla del NSGA-II, de modo que la
    poblacion —y con ella el frente— sigue reproduciendose byte a byte.
    """
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
    """Frente de Pareto por NSGA-II sobre pymoo. El optimizador de la tesis.

    Las variables de decision son ENTERAS en [0, n_i - 1]: la variable de la
    linea i es directamente el indice del candidato elegido. Antes eran reales
    en [0, n_i) con floor, la relajacion continua estandar, pero ahi SBX trataba
    el indice como una magnitud —interpolaba el indice 3 "entre" el 2 y el 4—
    cuando el indice es una ETIQUETA nominal, no un numero en una recta. Con
    una poblacion inicial entera + `RoundingRepair` en cruce y mutacion, la
    descendencia cae siempre en indices legales sin el epsilon de `n_i - 1e-6` y
    sin dejar de ser determinista bajo una semilla fija.

    Caveat honesto: SBX/PM con redondeo siguen siendo operadores ORDINALES sobre
    un eje nominal —asumen que indices vecinos son soluciones vecinas, que aqui
    no es cierto—. El benchmark Laya vs NSGA-II midio ese sesgo: una regla de
    subida por costo marginal dominaba algun punto del frente en el 68 % de las
    listas. Se corrige sembrando esa regla (abajo) en vez de cambiar el
    operador: la siembra entra al filtro final y garantiza que el frente no
    quede por debajo de ella, sin tocar el cruce ni la reproducibilidad.

    La poblacion inicial se siembra con las tres soluciones heuristicas
    (Ahorrador/Premium/Fan), que garantizan los extremos, y con los peldanos de
    la escalera de costo marginal (`_escalera_costo_marginal`), que recorren el
    compromiso costo-fidelidad entre ellos; el resto de la poblacion es azar con
    la misma semilla. El resultado se vuelve a filtrar por no-dominancia junto
    con todas esas semillas, asi que ningun kit sembrado puede dominar un punto
    del frente. `pop`/`gen` se escalan con el tamano del problema
    (`_poblacion`/`_generaciones`).
    """
    n = len(decidibles)
    tamanos = [len(o) for o in opciones]

    # Siembra: las tres heuristicas cubren min-costo, max-nivel y personaje,
    # que son justo los puntos que los perfiles van a proyectar; la escalera
    # cubre lo que hay entre el Ahorrador y el Premium, que es de donde sale el
    # kit recomendado con presupuesto.
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
        # Guarda de legalidad: RoundingRepair ya entrega enteros en rango, pero
        # se recorta igual para no depender de esa invariante externa.
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
            # ponytail: bucle por fila, no vectorizado. A escala tesis (pop<=200,
            # gen<=120, n de unas decenas) es sub-segundo. Una copia numpy de la
            # logica de objetivos correria el riesgo de divergir de
            # `_objetivos_de_asignacion` —justo la clase de bug que B4 arregla—,
            # asi que se reusa esa unica definicion. Vectorizar solo si el
            # perfilado lo pide.
            filas = []
            for fila in X:
                elegidos = [opciones[i][idx] for i, idx in enumerate(indices(fila))]
                costo, fidelidad, disp, pers = _objetivos_de_asignacion(
                    decidibles, elegidos, preferencias_local
                )
                # pymoo minimiza; los tres ejes "mas es mejor" se niegan.
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

    # Las sembradas entran tambien al filtro final: el NSGA-II puede perderlas
    # en el camino, y el frente no debe quedar por debajo de su propia semilla.
    for fila in sembradas:
        elegidos = [opciones[i][j] for i, j in enumerate(fila)]
        soluciones.append(_solucion(decidibles, elegidos, preferencias_local))

    return _no_dominadas(soluciones)


def optimizar_frente(
    renglones: list[Renglon], preferencias: dict[str, Any] | None = None, *, semilla: int = 0
) -> list[SolucionFrente]:
    """El frente de Pareto de un kit. Enumera si es chico, NSGA-II si no.

    Devuelve `[]` cuando no hay un compromiso real que optimizar (ninguna linea
    decidible, o todas con un solo candidato): en ese caso `armar_los_tres` cae
    a la heuristica, que da exactamente el mismo kit sin gastar el algoritmo.
    """
    preferencias = preferencias or {}
    decidibles = [r for r in renglones if not r.informativa and _admisibles(r)]
    if not decidibles:
        return []

    opciones = [_admisibles(r) for r in decidibles]
    espacio = math.prod(len(o) for o in opciones)
    if espacio <= 1:
        return []

    if espacio <= LIMITE_ENUMERACION:
        # Enumeracion exacta para kits chicos: mismo frente que NSGA-II pero
        # exacto e instantaneo. Es una optimizacion por tamano, NO un plan B por
        # falta de pymoo (pymoo es dependencia dura).
        return _frente_exacto(decidibles, opciones, preferencias)
    return _frente_nsga(decidibles, opciones, preferencias, semilla=semilla)


def _surtibles(frente: list[SolucionFrente]) -> list[SolucionFrente]:
    """Los puntos del frente con la mayor disponibilidad que el frente alcanza.

    El costo no suma lo que no tiene precio (su falta la mide `disponibilidad`),
    asi que cambiar un candidato con precio por uno sin precio BAJA el costo y
    los dos puntos quedan en el frente sin dominarse. Proyectar sobre todo el
    frente hacia que el Ahorrador eligiera lo que no tiene precio, con un total
    que no incluia esa linea, y que el Premium y A tu Medida lo tomaran como una
    marca gratis. Es la misma regla de la heuristica (`_costo_para_ordenar`): lo
    que Tukit no puede surtir no gana una comparacion de precio, pero si una
    linea SOLO tiene candidatos sin precio, todos los puntos los llevan y la
    linea sigue saliendo.
    """
    tope = max(s.disponibilidad for s in frente)
    return [s for s in frente if s.disponibilidad == tope]


def _proyectar(frente: list[SolucionFrente], perfil: str) -> SolucionFrente | None:
    """Elige el punto del frente que corresponde a un perfil.

    Los tres perfiles son arquetipos, no los pesos del acudiente (esos solo
    deciden CUAL de los tres se recomienda, en `recomendar`). Por eso cada uno
    proyecta el frente sobre un eje distinto, entre los puntos de maxima
    disponibilidad (`_surtibles`):

    - `Ahorrador`: minimo costo.
    - `Premium`: maxima fidelidad de marca (desempata por menor costo).
    - `Fan`: maximo `personaje`; si el frente no ofrece personaje (nadie lo
      pidio), se comporta como `Ahorrador`, igual que la heuristica.
    """
    if not frente:
        return None
    frente = _surtibles(frente)
    if perfil == PerfilKit.PREMIUM.value:
        return max(frente, key=lambda s: (s.fidelidad, -s.costo, s.disponibilidad))
    if perfil == PerfilKit.FAN.value:
        mejor = max(frente, key=lambda s: (s.personaje, -s.costo, s.fidelidad))
        if mejor.personaje > 0:
            return mejor
        # Sin personaje pedido, Fan es Ahorrador: no inventa un personaje.
    return min(frente, key=lambda s: (s.costo, -s.disponibilidad, -s.fidelidad))
