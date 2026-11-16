"""Seleccion de constantes sobre un subconjunto de renglones (entrenamiento) y medida en otro.

Espacio de busqueda: 3^5 = 243 combinaciones de las 5 constantes de puntaje x 5 cortes = 1.215
(ver barrido.ESPACIO / CORTES). Criterio: exactitud del concepto en el subconjunto de
entrenamiento; en empate se prefiere la combinacion con menos constantes distintas del valor
actual (un desempate conservador, declarado). tau se fija despues con la regla "menor tau cuya
precision de lo aceptado llegue al objetivo" sobre el mismo subconjunto.
"""

from __future__ import annotations

import itertools

import numpy as np

import barrido as b
import clasificacion as k

OBJETIVOS_TAU = (0.95, 0.98)


class Espacio:
    def __init__(self, cx: b.Contexto):
        self.cx = cx
        claves = k.CLAVES_PUNTAJE
        self.cfgs = [
            {**k.ACTUAL, **dict(zip(claves, v, strict=True))}
            for v in itertools.product(*(b.ESPACIO[c] for c in claves))
        ]
        res = [cx.puntuar(c) for c in self.cfgs]
        self.P = np.array([p for p, _ in res])
        self.S = np.array([s for _, s in res])
        self.cortes = b.CORTES
        self.dist = np.array(
            [[sum(abs(c[x] - k.ACTUAL[x]) > 1e-9 for x in claves) + (abs(j - k.ACTUAL["corte"]) > 1e-9) for j in self.cortes] for c in self.cfgs]
        )
        self.i_actual = next(i for i, c in enumerate(self.cfgs) if all(abs(c[x] - k.ACTUAL[x]) < 1e-9 for x in claves))
        self.j_actual = self.cortes.index(k.ACTUAL["corte"])
        self.n_combinaciones = len(self.cfgs) * len(self.cortes)

    def exactitud(self, mask: np.ndarray) -> np.ndarray:
        y = self.cx.y[mask]
        out = np.zeros((len(self.cfgs), len(self.cortes)))
        for j, corte in enumerate(self.cortes):
            pc = np.where(self.S[:, mask] >= corte, self.P[:, mask], -1)
            out[:, j] = (pc == y).mean(1)
        return out

    def elegir(self, train: np.ndarray, val: np.ndarray | None = None, topk: int = 5) -> dict:
        acc = self.exactitud(train)
        orden = sorted(((i, j) for i in range(len(self.cfgs)) for j in range(len(self.cortes))), key=lambda t: (-round(acc[t], 12), self.dist[t]))
        cand = orden[:topk]
        if val is not None:
            av = self.exactitud(val)
            cand = sorted(cand, key=lambda t: (-round(av[t], 12), cand.index(t)))
        i, j = cand[0]
        cfg = {**self.cfgs[i], "corte": self.cortes[j]}
        pc = np.where(self.S[i, train] >= cfg["corte"], self.P[i, train], -1)
        taus = {str(o): b.regla_tau(self.S[i, train], pc, self.cx.y[train], cfg["corte"], o) for o in OBJETIVOS_TAU}
        return {
            "cfg": cfg,
            "taus": taus,
            "exactitud_train": float(acc[i, j]),
            "es_el_actual": bool(i == self.i_actual and j == self.j_actual),
            "empates_en_train": int(sum(1 for t in orden if abs(acc[t] - acc[i, j]) < 1e-12)),
        }

    def medir(self, cfg: dict, mask: np.ndarray, tau: float) -> dict:
        return self.cx.medir({**cfg, "tau": tau}, mask)


def resumen(valores: list[float]) -> dict:
    v = [x for x in valores if x is not None]
    return {"media": float(np.mean(v)), "min": float(np.min(v)), "max": float(np.max(v)), "sd": float(np.std(v))} if v else {}
