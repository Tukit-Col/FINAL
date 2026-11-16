"""Hogar con CONSOLIDACION entre hermanos dentro del objetivo: PD exacta y NSGA-II.

Regla del sistema (`optimizador.consolidar`, solo lectura): las lineas de un hogar
que eligen el MISMO sku (y no son `no_consolidable`) se compran juntas si piden
ese sku al menos DOS hijos distintos: unidades = ceil(suma de cantidades / empaque).
Si todas las lineas del sku son del mismo hijo no se junta nada (suma de ceil por
linea). El costo de un producto compartido depende de la demanda acumulada.

PD exacta: estado = (suma de niveles, demanda de cada sku compartido "vivo"),
con el costo minimo por estado. Por sku compartido se guarda (D, h, S):
D = demanda acumulada, h = unico hijo que lo pidio (o -1 si ya son varios),
S = unidades sueltas acumuladas (solo si h != -1). Un sku se "cierra" (sale del
estado) cuando ya no queda ninguna linea que pueda elegirlo: asi los estados se
funden. Poda: cota inferior = suma de p*ceil(D/E) (monotona) > presupuesto.

Diferencias con el sistema (documentadas, medidas en `validacion`):
 * `juntar_herramientas` (mismo hijo, mismo sku, `uno_por_estudiante`, compra el
   maximo y no la suma) NO esta modelada; el sistema la aplica antes de consolidar.
 * Se descartan candidatos sin precio cuando la linea tiene alguno con precio (en
   los tres metodos, incluida la linea base), para que "disponibilidad" sea constante.
 * Las lineas informativas no entran (igual que `decidibles`).

Solo archivos nuevos: importa el optimizador, el bench y `acoplado` sin tocarlos.
"""

from __future__ import annotations

import bisect
import itertools
import math
import time
from dataclasses import replace

from acoplado import (  # noqa: F401  (importa tambien la ruta al bench)
    NSGA2,
    SBX,
    PM,
    PerfilKit,
    Problem,
    RoundingRepair,
    Tiempo,
    _admisibles,
    _escalera_costo_marginal,
    _generaciones,
    _minimizar,
    _np,
    _poblacion,
    _poblacion_inicial,
    elegir_por_perfil,
)
from comun import TOPE_NIVEL, decidibles, renglones_de
from tukit_inteligencia.optimizador import _frente_nsga, _surtibles, armar_kit

MASK_D = 20
SHIFT_K = 48


def _techo(a: int, e: int) -> int:
    return -(-a // e)


# ---------------------------------------------------------------- hogares


def solo_con_precio(renglon):
    """Descarta candidatos sin precio si la linea tiene alguno con precio."""
    con = tuple(c for c in renglon.candidatos if c.precio_cop is not None)
    return replace(renglon, candidatos=con) if con and len(con) < len(renglon.candidatos) else renglon


def armar_hogar(instancias):
    """Lista de listas (instancias del bench) -> renglones del hogar (un hijo por lista)."""
    renglones = []
    for k, inst in enumerate(instancias, start=1):
        for r in renglones_de(inst):
            r = replace(r, hijo=f"hijo-{k}")
            renglones.append(solo_con_precio(r))
    return renglones


class Hogar:
    """Precalcula por linea los candidatos admisibles y los skus compartidos."""

    def __init__(self, renglones):
        self.renglones = renglones
        self.dec = decidibles(renglones)
        self.n = len(self.dec)
        self.opc = [_admisibles(r) for r in self.dec]
        self.hijos = sorted({r.hijo for r in self.dec}, key=lambda h: int(h.split("-")[1]))
        self.hi = [self.hijos.index(r.hijo) for r in self.dec]
        # hijos distintos que pueden pedir cada sku (solo lineas consolidables, con precio)
        pedidores: dict[str, set] = {}
        for i, (r, o) in enumerate(zip(self.dec, self.opc, strict=True)):
            if r.no_consolidable:
                continue
            for c in o:
                if c.precio_cop is not None:
                    pedidores.setdefault(c.sku, set()).add(self.hi[i])
        self.compartidos = sorted(s for s, h in pedidores.items() if len(h) >= 2)
        kidx = {s: k for k, s in enumerate(self.compartidos)}
        self.K = len(self.compartidos)
        self.skuinfo = [None] * self.K  # (precio, empaque)
        # por linea y candidato: (nivel, precio, empaque, unidades_linea, k o -1, sku, costo_linea)
        self.cand = []
        ultimo = [-1] * self.K
        for i, (r, o) in enumerate(zip(self.dec, self.opc, strict=True)):
            fila = []
            for c in o:
                p = c.precio_cop or 0
                e = max(1, c.unidades_por_empaque)
                u = _techo(r.cantidad, e) if r.cantidad > 0 else 0
                k = -1
                if not r.no_consolidable and c.precio_cop is not None and c.sku in kidx:
                    k = kidx[c.sku]
                    self.skuinfo[k] = (p, e)
                    ultimo[k] = i
                fila.append((min(c.rango_nivel, TOPE_NIVEL), p, e, u, k, c.sku, p * u))
            self.cand.append(fila)
        self.cierra = [[] for _ in range(self.n)]
        for k, i in enumerate(ultimo):
            if i >= 0:
                self.cierra[i].append(k)
        self.q = [r.cantidad for r in self.dec]

    # -- costo de una asignacion (indices) con la regla del sistema
    def costo(self, idx):
        total = 0
        grupos: dict[int, list] = {}
        for i, j in enumerate(idx):
            niv, p, e, u, k, _, cl = self.cand[i][j]
            if k < 0:
                total += cl
            else:
                g = grupos.get(k)
                if g is None:
                    grupos[k] = [self.q[i], {self.hi[i]}, u]
                else:
                    g[0] += self.q[i]
                    g[1].add(self.hi[i])
                    g[2] += u
        for k, (d, hs, s) in grupos.items():
            p, e = self.skuinfo[k]
            total += p * (_techo(d, e) if len(hs) >= 2 else s)
        return total

    def nivel(self, idx):
        return sum(self.cand[i][j][0] for i, j in enumerate(idx))

    def fid(self, idx):
        return self.nivel(idx) / (self.n * TOPE_NIVEL)

    def idx_de(self, asignacion):
        """{(hijo, orden): sku} -> lista de indices."""
        salida = []
        for r, o in zip(self.dec, self.opc, strict=True):
            sku = asignacion[(r.hijo, r.orden)]
            salida.append(next(j for j, c in enumerate(o) if c.sku == sku))
        return salida

    def costo_sin_consolidar(self, idx):
        return sum(self.cand[i][j][6] for i, j in enumerate(idx))

    def heuristica(self, perfil):
        idx = []
        perfil = PerfilKit[perfil.upper()].value if isinstance(perfil, str) and perfil.upper() in PerfilKit.__members__ else perfil
        for r, o in zip(self.dec, self.opc, strict=True):
            el = elegir_por_perfil(tuple(o), perfil, personajes=(), cantidad=r.cantidad)
            idx.append(next(j for j, c in enumerate(o) if c is el))
        return idx

    def cota_inferior_ahorrador(self):
        """Cota valida del minimo con consolidacion: sum_lineas min p*q/E (sin techo)."""
        return sum(min(c[1] * self.q[i] / c[2] for c in self.cand[i]) for i in range(self.n))

    def total_armar_kit(self, idx):
        """Total del sistema (`armar_kit`, con juntar_herramientas y consolidar)."""
        el = {(r.hijo, r.orden): o[j] for r, o, j in zip(self.dec, self.opc, idx, strict=True)}
        return armar_kit(self.renglones, "ahorrador", {}, elecciones=el).total_cop


# ---------------------------------------------------------------- PD exacta


def _opciones_pd(h: Hogar, i: int):
    """Candidatos de la linea i: los no compartidos se reducen a su frente (nivel, costo)."""
    ns: dict[int, tuple] = {}
    sh = []
    for j, (niv, p, e, u, k, sku, cl) in enumerate(h.cand[i]):
        if k >= 0:
            sh.append((niv, p, e, u, k, j))
        elif niv not in ns or cl < ns[niv][0]:
            ns[niv] = (cl, j)
    # Pareto: nivel mayor y costo menor
    base = []
    mejor = None
    for niv in sorted(ns, reverse=True):
        cl, j = ns[niv]
        if mejor is None or cl < mejor:
            base.append((niv, cl, j))
            mejor = cl
    return base, sh


def pd_hogar(h: Hogar, modo: str, tope: int, limite_s: float | None = None, tope_capa: int = 600_000, reconstruir=False):
    """PD exacta con consolidacion.

    modo 'presupuesto': maximiza la suma de niveles con costo <= tope (desempata menor costo).
    modo 'costo': minimiza el costo total (tope = cota superior para podar; el estado no lleva s).
    Devuelve ((suma_niveles, costo, asignacion|None) | None, estados). Lanza Tiempo(estados, motivo).
    """
    t0 = time.perf_counter()
    con_s = modo == "presupuesto"
    capas = []
    # estado: (s, tupla_ordenada_de_entradas) -> (c, lb, padre, j)
    actual = {(0, ()): (0, 0, None, -1)}
    estados = 1
    cuenta = 0
    for i in range(h.n):
        base, sh = _opciones_pd(h, i)
        q, hi = h.q[i], h.hi[i]
        cierra = h.cierra[i]
        nuevo: dict = {}
        for (s, tup), (c, lb, _, _) in actual.items():
            pos = {e >> SHIFT_K: m for m, e in enumerate(tup)} if sh else None
            for niv, cl, j in base:
                cuenta += 1
                if limite_s is not None and cuenta & 4095 == 0 and time.perf_counter() - t0 > limite_s:
                    raise Tiempo(estados, "tiempo")
                c2, lb2 = c + cl, lb + cl
                if lb2 > tope:
                    continue
                t2, lb3, c3 = tup, lb2, c2
                if cierra:
                    t2, lb3 = _cerrar(h, t2, cierra, lb3)
                k2 = (s + niv if con_s else 0, t2)
                prev = nuevo.get(k2)
                if prev is None or c3 < prev[0]:
                    nuevo[k2] = (c3, lb3, (s, tup), j)
            for niv, p, e, u, k, j in sh:
                cuenta += 1
                if limite_s is not None and cuenta & 4095 == 0 and time.perf_counter() - t0 > limite_s:
                    raise Tiempo(estados, "tiempo")
                m = pos.get(k)
                if m is None:
                    dc = dlb = p * u
                    entrada = (k << SHIFT_K) | (q << MASK_D) | ((hi + 1) << 12) | u
                    lista = list(tup)
                    bisect.insort(lista, entrada)
                else:
                    ent = tup[m]
                    cod = ent & ((1 << SHIFT_K) - 1)
                    d = cod >> MASK_D
                    hh = ((cod >> 12) & 0xFF) - 1
                    ss = cod & 0xFFF
                    d2 = d + q
                    dlb = p * (_techo(d2, e) - _techo(d, e))
                    if hh == -1:
                        dc, nc = dlb, (d2 << MASK_D) | 0
                    elif hh == hi:
                        dc, nc = p * u, (d2 << MASK_D) | ((hi + 1) << 12) | (ss + u)
                    else:
                        dc, nc = p * (_techo(d2, e) - ss), (d2 << MASK_D)
                        # h = -1 se codifica con (h+1) = 0
                    nc2 = nc
                    lista = list(tup)
                    lista[m] = (k << SHIFT_K) | nc2
                c2, lb2 = c + dc, lb + dlb
                if lb2 > tope:
                    continue
                t2 = tuple(lista)
                lb3 = lb2
                if cierra:
                    t2, lb3 = _cerrar(h, t2, cierra, lb3)
                k2 = (s + niv if con_s else 0, t2)
                prev = nuevo.get(k2)
                if prev is None or c2 < prev[0]:
                    nuevo[k2] = (c2, lb3, (s, tup), j)
            if len(nuevo) > tope_capa:
                raise Tiempo(estados + len(nuevo), "memoria")
        estados += len(nuevo)
        if reconstruir:
            capas.append(nuevo)
        actual = nuevo
        if not actual:
            return None, estados
    # capa final: todas las entradas estan cerradas -> clave (s, ())
    mejor = None
    for (s, tup), (c, _, _, _) in actual.items():
        if modo == "presupuesto":
            if c > tope:
                continue
            clave = (s, -c)
        else:
            clave = (-c,)
        if mejor is None or clave > mejor[0]:
            mejor = (clave, (s, tup), c, s)
    if mejor is None:
        return None, estados
    _, kf, c, s = mejor
    asignacion = None
    if reconstruir:
        asignacion = []
        clave = kf
        base_cache = {}
        for i in range(h.n - 1, -1, -1):
            _, _, padre, j = capas[i][clave]
            asignacion.append(j)
            clave = padre
        asignacion.reverse()
    return (s, c, asignacion), estados


def _cerrar(h, tup, cierra, lb):
    """Saca de la tupla los skus que ya no pueden elegirse; ajusta la cota a su costo exacto."""
    ks = set(cierra)
    salida = []
    for e in tup:
        k = e >> SHIFT_K
        if k in ks:
            cod = e & ((1 << SHIFT_K) - 1)
            if ((cod >> 12) & 0xFF) != 0:  # hijo unico: costo exacto p*S > p*ceil(D/E)
                d, ss = cod >> MASK_D, cod & 0xFFF
                p, ee = h.skuinfo[k]
                lb += p * (ss - _techo(d, ee))
        else:
            salida.append(e)
    return tuple(salida), lb


def enumeracion_hogar(h: Hogar, modo: str, tope: int):
    """Fuerza bruta con el mismo costo consolidado (oraculo de la PD en hogares chicos)."""
    mejor = None
    for combo in itertools.product(*[range(len(f)) for f in h.cand]):
        c = h.costo(combo)
        s = h.nivel(combo)
        if modo == "presupuesto":
            if c > tope:
                continue
            clave = (s, -c)
        else:
            clave = (-c, 0)
        if mejor is None or clave > mejor[0]:
            mejor = (clave, s, c)
    return None if mejor is None else (mejor[1], mejor[2])


# ---------------------------------------------------------------- NSGA-II


def nsga_hogar(h: Hogar, presupuesto: int, semilla: int = 0):
    """Copia de `_frente_nsga` con el costo CONSOLIDADO en la evaluacion.

    Mismos operadores, poblacion, generaciones, siembra y semilla. Devuelve
    (ahorrador, presupuesto_kit, evaluaciones): cada kit = (fid, costo, idx) o None.
    """
    n = h.n
    tam = [len(o) for o in h.opc]
    sembradas = []
    for perfil in PerfilKit:
        sembradas.append(h.heuristica(perfil.value))
    sembradas.extend(_escalera_costo_marginal(h.dec, h.opc))
    n_eval = 0

    def indices(x):
        return [min(tam[i] - 1, max(0, int(round(float(x[i]))))) for i in range(n)]

    class _P(Problem):
        def __init__(self):
            super().__init__(n_var=n, n_obj=4, n_constr=0, xl=_np.zeros(n, dtype=int),
                            xu=_np.array([t - 1 for t in tam], dtype=int), vtype=int)

        def _evaluate(self, X, out, *a, **k):
            nonlocal n_eval
            filas = []
            for fila in X:
                n_eval += 1
                idx = indices(fila)
                filas.append([h.costo(idx), -h.fid(idx), -1.0, 0.0])
            out["F"] = _np.array(filas, dtype=float)

    pop = _poblacion(n)
    alg = NSGA2(pop_size=pop, sampling=_poblacion_inicial(sembradas, tam, pop, semilla),
                crossover=SBX(prob=0.9, eta=15, repair=RoundingRepair()),
                mutation=PM(prob=1.0, eta=20, repair=RoundingRepair()), eliminate_duplicates=True)
    res = _minimizar(_P(), alg, ("n_gen", _generaciones(math.prod(tam))), seed=semilla, verbose=False)
    cand = [indices(f) for f in (_np.atleast_2d(res.X) if res.X is not None else [])] + sembradas
    ahorr = presu = None
    for idx in cand:
        c, f = h.costo(idx), h.fid(idx)
        if ahorr is None or (c, -f) < (ahorr[1], -ahorr[0]):
            ahorr = (f, c, idx)
        if c <= presupuesto and (presu is None or (f, -c) > (presu[0], -presu[1])):
            presu = (f, c, idx)
    return ahorr, presu, n_eval


def base_hogar(h: Hogar, presupuesto: int, semilla: int = 0):
    """Linea base = produccion: `_frente_nsga` SIN consolidar en la evaluacion; luego se
    proyecta (Ahorrador = menor costo; presupuesto = mayor fidelidad con costo sin
    consolidar <= tope, como `_armar_a_tu_medida`) y SE CONSOLIDA DESPUES (costo real)."""
    frente = _frente_nsga(h.dec, h.opc, {}, semilla=semilla)
    sur = _surtibles(frente)
    a = min(sur, key=lambda s: (s.costo, -s.disponibilidad, -s.fidelidad))
    caben = [s for s in sur if s.costo <= presupuesto]
    b = max(caben, key=lambda s: (s.fidelidad, -s.costo, s.disponibilidad)) if caben else None
    out = []
    for s in (a, b):
        if s is None:
            out.append(None)
            continue
        idx = h.idx_de(s.asignacion)
        out.append((h.fid(idx), h.costo(idx), idx))
    return out[0], out[1]
