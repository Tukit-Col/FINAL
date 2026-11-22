"""Simulacion en memoria del lazo "corregir ensena" (commits 8b26c12 y 43d1da8), sin tocar la base."""

from __future__ import annotations

import barrido as b
import clasificacion as k
import numpy as np


class Simulador:
    def __init__(self, cx: b.Contexto):
        self.cx = cx
        d = cx.d
        ind = {c: i for i, c in enumerate(d.codigos)}
        self.syn: list[str | None] = [k.sinonimo_de_renglon(f["texto"]) for f in d.filas]
        pool = sorted({(int(cx.y[i]), s) for i, s in enumerate(self.syn) if s and cx.y[i] >= 0})
        self.r = k.construir_rasgos(d, pool)
        self.col_de: dict[tuple[int, str], int] = {}
        for c in range(len(self.r.col_texto)):
            self.col_de.setdefault((int(self.r.col_concepto[c]), self.r.col_texto[c]), c)
        import json

        aprend = json.load((k.DATOS / "catalogo_conceptos.json").open(encoding="utf-8"))[
            "sinonimos_aprendidos"
        ]
        self.aprendidos_actuales = {
            self.col_de[(ind[a["concepto"]], a["sinonimo"])]
            for a in aprend
            if (ind.get(a["concepto"]), a["sinonimo"]) in self.col_de
        }
        self.n_aprendidos = len(aprend)
        tipo = np.array(self.r.col_tipo)
        self.base_actual = tipo != "pool"
        for c in self.aprendidos_actuales:
            self.base_actual[c] = False
        self.base_frio = tipo == "nombre"

    def inicial(self, frio: bool) -> np.ndarray:
        return (self.base_frio if frio else self.base_actual).copy()

    def evaluar(self, activa: np.ndarray, filas: np.ndarray, cfg: dict | None = None):
        cfg = cfg or k.ACTUAL
        cols = np.where(activa)[0]
        us = self.cx.u[filas]
        uniq, inv = np.unique(us, return_inverse=True)
        p, s = k.puntuar(self.r, cfg, activas=cols, filas=uniq)
        return p[inv], s[inv]

    def ensenar(self, activa: np.ndarray, filas: np.ndarray, pred_c: np.ndarray, todo: bool = False) -> int:
        nuevos = 0
        for f, pc in zip(filas, pred_c, strict=True):
            y = int(self.cx.y[f])
            s = self.syn[f]
            if y < 0 or not s or (not todo and pc == y):
                continue
            c = self.col_de.get((y, s))
            if c is not None and not activa[c]:
                activa[c] = True
                nuevos += 1
            if pc >= 0 and pc != y:
                c2 = self.col_de.get((int(pc), s))
                if c2 is not None:
                    activa[c2] = False
        return nuevos
