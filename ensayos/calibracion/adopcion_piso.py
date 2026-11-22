"""Adopcion del piso 0,5 (hoy 0,6): que cifras cambian en la memoria.
Uso: uv run python ensayos/calibracion/adopcion_piso.py"""

from __future__ import annotations

import collections
import csv
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
import clasificacion as k  # noqa: E402
import nucleo as n  # noqa: E402
import tau as T  # noqa: E402
from tukit_catalogo.transcripcion import corregir, lexico_de  # noqa: E402

OBJ = 0.97
REGLA = (
    "tau nuevo = el menor tau de la rejilla fina (paso 0,005) con precision de lo aceptado >= 0,97 "
    "sobre los 405 pares con piso 0,5"
)
REJILLA = [round(i * 0.005, 3) for i in range(0, 201)]


def pares_con_renglon():
    revisadas = list(csv.DictReader(T.CURADURIA.open(encoding="utf-8")))
    items = list(csv.DictReader(T.ITEMS.open(encoding="utf-8")))
    cdt = collections.defaultdict(set)
    for x in items:
        cdt[x["texto_original"].strip().lower()].add(x["colegio_codigo"])
    votos = collections.defaultdict(collections.Counter)
    for x in revisadas:
        for c in cdt.get(x["texto_original"].strip().lower(), ()):
            votos[x["colegio_id"]][c] += 1
    cod = {u: v.most_common(1)[0][0] for u, v in votos.items()}
    idxr = {}
    for inst in n.instancias():
        for r in inst["renglones"]:
            idxr[(inst["colegio"], inst["grado"], r["texto"].strip().lower())] = r
    out = []
    for x in revisadas:
        col = cod.get(x["colegio_id"])
        r = idxr.get((col, x["grado"], x["texto_original"].strip().lower()))
        if r is not None:
            out.append((col, x["grado"], x["concepto"], r))
    return out


def resolver_bench(pisos: list[float]):
    d = k.cargar(con_vectores=False)
    textos = sorted({r["texto"] for i in n.instancias() for r in i["renglones"]})
    d.textos = textos
    d.corr = [corregir(t, lexico_de(d.conceptos)) for t in textos]
    d.vectores = None
    rs = k.construir_rasgos(d)
    ind = {t: i for i, t in enumerate(textos)}
    res = {}
    for p in pisos:
        idx, s = k.puntuar(rs, {**k.ACTUAL, "piso": p})
        res[p] = (idx, s)
    return d, ind, res


def conjunto_de_pares(base, d, ind, res, piso: float, tratamiento: str):
    idx6, s6 = res[0.6]
    idx, s = res[piso]
    pares, estado = [], collections.Counter()
    for col, grado, concepto, r in base:
        u = ind[r["texto"]]
        c6 = d.codigos[int(idx6[u])] if idx6[u] >= 0 and s6[u] >= 0.5 else None
        reproduce = c6 == r["concepto_codigo"] and abs(s6[u] - r["parecido"]) < 1e-9
        no_buscado = r["concepto_codigo"] is None and r["parecido"] == 0.0
        if tratamiento == "A":
            usar = reproduce and not no_buscado
        else:
            usar = not no_buscado
        estado["recalculado" if usar else ("no_buscado_fijo" if no_buscado else "deriva_catalogo_fijo")] += 1
        if usar:
            cod = d.codigos[int(idx[u])] if idx[u] >= 0 and s[u] >= 0.5 else None
            par = float(s[u])
        else:
            cod, par = r["concepto_codigo"], float(r["parecido"])
        pares.append(
            {
                "lista": f"{col}|{grado}",
                "colegio": col,
                "parecido": par,
                "concepto_resolver": cod,
                "concepto_revisor": concepto,
                "acierto": bool(cod) and cod == concepto,
            }
        )
    return pares, dict(estado)


def regla_tau(p, y, objetivo=OBJ):
    for t in REJILLA:
        m = T.metricas(p, y, t)
        if m["precision"] is not None and m["precision"] >= objetivo:
            return t
    return None


def tau_misma_fraccion(p, y, aceptados_ref):
    c = [t for t in REJILLA if int((p >= t).sum()) >= aceptados_ref]
    return max(c) if c else None


def cv_agrupada(pares, p, y, objetivo):
    listas = sorted({q["lista"] for q in pares})
    rng = np.random.default_rng(n.SEMILLA_BASE)
    orden = np.array(listas)
    rng.shuffle(orden)
    pl = {lista: i % T.PLIEGUES for i, lista in enumerate(orden)}
    fold = np.array([pl[q["lista"]] for q in pares])
    filas = []
    old = T.OBJETIVO_PRECISION
    T.OBJETIVO_PRECISION = objetivo
    try:
        for kk in range(T.PLIEGUES):
            ent, pru = fold != kk, fold == kk
            tau = T.elegir_tau(p[ent], y[ent])
            filas.append(
                {"pliegue": kk, "n_prueba": int(pru.sum()), "tau": tau, **T.metricas(p[pru], y[pru], tau)}
            )
    finally:
        T.OBJETIVO_PRECISION = old
    agr = {"aceptados": sum(f["aceptados"] for f in filas)}
    tp = sum(round(f["precision"] * f["aceptados"]) for f in filas if f["precision"] is not None)
    agr["precision_agregada"] = tp / agr["aceptados"] if agr["aceptados"] else None
    agr["fraccion_aceptada_agregada"] = agr["aceptados"] / len(pares)
    return {"objetivo": objetivo, "pliegues": filas, **agr}


def cifras(pares, tau):
    p = np.array([q["parecido"] for q in pares])
    y = np.array([q["acierto"] for q in pares])
    return {
        "pares": len(pares),
        "aciertos": int(y.sum()),
        "incorrectos": int((~y).sum()),
        "precision_aceptar_todo": float(y.mean()),
        "parecido_valores_distintos": int(len(np.unique(p))),
        "auc": T.auc(p, y),
        "tau": tau,
        "en_tau": T.metricas(p, y, tau),
        "matriz": T.matriz_confusion(p, y, tau),
        "ic95_bootstrap": T.ic_bootstrap(p, y, tau),
        "curva_memoria": [T.metricas(p, y, t) for t in (0.5, 0.75, 0.85, 0.95)],
        "validacion_cruzada_agrupada_regla_actual_0_95": cv_agrupada(pares, p, y, 0.95),
        "validacion_cruzada_agrupada_regla_0_97": cv_agrupada(pares, p, y, 0.97),
    }


def recorrido(d, rs, y, piso, tau):
    idx, s = k.puntuar(rs, {**k.ACTUAL, "piso": piso})
    u = np.array([f["u"] for f in d.filas])
    m = k.metricas(idx[u], s[u], y, k.ACTUAL["corte"], tau)
    acepta = (s[u] >= tau) & (np.where(s[u] >= k.ACTUAL["corte"], idx[u], -1) >= 0)
    m["aceptados"] = int(acepta.sum())
    m["a_revision"] = int(len(y) - acepta.sum())
    m["correctos_entre_aceptados"] = int((acepta & (np.where(s[u] >= 0.5, idx[u], -1)[:] == y)).sum())
    m["piso"], m["tau"] = piso, tau
    return m


def main() -> int:
    base = pares_con_renglon()
    d, ind, res = resolver_bench([0.6, 0.5])
    sal: dict = {
        "regla_tau": REGLA,
        "objetivo_precision": OBJ,
        "rejilla": "0,000 a 1,000 paso 0,005",
        "nota_regla_hoy": "tau.py usa objetivo 0,95 (no 0,97) y el 0,75 de hoy es una eleccion conservadora, no el minimo de ninguna regla: ver reglas_aplicadas_a_piso_0_6.",
    }
    for trat in ("A", "B"):
        c6, est6 = conjunto_de_pares(base, d, ind, res, 0.6, trat)
        c5, est5 = conjunto_de_pares(base, d, ind, res, 0.5, trat)
        p6 = np.array([q["parecido"] for q in c6])
        y6 = np.array([q["acierto"] for q in c6])
        p5 = np.array([q["parecido"] for q in c5])
        y5 = np.array([q["acierto"] for q in c5])
        t_nuevo = regla_tau(p5, y5)
        ref = int((p6 >= 0.75).sum())
        t_mf = tau_misma_fraccion(p5, y5, ref)
        bloque = {
            "estado_de_los_pares": {"piso_0_6": est6, "piso_0_5": est5},
            "reglas_aplicadas_a_piso_0_6": {
                "tau_menor_con_precision_0_97": regla_tau(p6, y6, 0.97),
                "tau_menor_con_precision_0_95": regla_tau(p6, y6, 0.95),
            },
            "tau_nuevo_regla_0_97": t_nuevo,
            "alternativa_misma_fraccion_aceptada_que_hoy": {
                "aceptados_hoy": ref,
                "tau": t_mf,
                "metricas": T.metricas(p5, y5, t_mf) if t_mf is not None else None,
                "criterio": "mayor tau de la rejilla con aceptados >= 340",
            },
            "control_piso_0_6_tau_0_75": cifras(c6, 0.75),
            "nuevo_piso_0_5_tau_nuevo": cifras(c5, t_nuevo),
            "piso_0_5_tau_0_75": cifras(c5, 0.75),
            "piso_0_6_con_tau_nuevo": cifras(c6, t_nuevo),
            "intervalo_tau_equivalente_al_nuevo": (lambda e: [e[0], e[-1]])(
                [t for t in REJILLA if int((p5 >= t).sum()) == int((p5 >= t_nuevo).sum())]
            ),
            "barrido_fino_piso_0_5": [T.metricas(p5, y5, t) for t in REJILLA],
            "barrido_fino_piso_0_6": [T.metricas(p6, y6, t) for t in REJILLA],
        }
        if t_mf is not None:
            bloque["piso_0_5_tau_misma_fraccion"] = cifras(c5, t_mf)
        sal[f"tratamiento_{trat}"] = bloque

    dd = k.cargar(con_vectores=True)
    rs = k.construir_rasgos(dd)
    y = k.etiquetas(dd)
    t_nuevo = sal["tratamiento_A"]["tau_nuevo_regla_0_97"]
    sal["recorrido_3037"] = {
        "renglones": len(dd.filas),
        "listas": len({f["lista"] for f in dd.filas}),
        "con_vectores_de_cache": dd.vectores is not None,
        "control_piso_0_6_tau_0_75": recorrido(dd, rs, y, 0.6, 0.75),
        "piso_0_5_tau_0_75": recorrido(dd, rs, y, 0.5, 0.75),
        "nuevo_piso_0_5_tau_nuevo": recorrido(dd, rs, y, 0.5, t_nuevo),
        "piso_0_5_tau_misma_fraccion_405": (
            recorrido(
                dd, rs, y, 0.5, sal["tratamiento_A"]["alternativa_misma_fraccion_aceptada_que_hoy"]["tau"]
            )
            if sal["tratamiento_A"]["alternativa_misma_fraccion_aceptada_que_hoy"]["tau"] is not None
            else None
        ),
    }
    t_nuevo = sal["tratamiento_A"]["tau_nuevo_regla_0_97"]
    tx = sorted({r["texto"] for i in n.instancias() for r in i["renglones"]})
    ind_bench = {}
    for piso, tau in ((0.6, 0.75), (0.5, 0.75), (0.5, t_nuevo)):
        idx, s_ = res[piso]
        u = np.array([ind[t] for t in tx])
        con = (idx[u] >= 0) & (s_[u] >= 0.5)
        ind_bench[f"piso_{piso}_tau_{tau}"] = {
            "textos": len(tx),
            "auto_por_puntaje": float((con & (s_[u] >= tau)).mean()),
            "ambiguo_entre_0_5_y_tau": float((con & (s_[u] < tau)).mean()),
            "sin_correspondencia": float((~con).mean()),
        }
    sal["indicativo_textos_unicos_bench"] = {
        "aviso": "Aproximacion: solo puntaje, sin estado hueco/abstencion ni los 60 sublistas de la corrida de la memoria (35,3/36,5/28,1), que no se pudo reproducir.",
        **ind_bench,
    }
    ruta = n.guardar("adopcion_piso.json", sal)
    print(ruta)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
