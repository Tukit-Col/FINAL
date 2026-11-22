"""Comparar constantes al MISMO punto de operacion (curva riesgo-cobertura).
Uso: uv run python ensayos/calibracion/punto_operacion.py"""

from __future__ import annotations

import itertools
import json
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
import barrido as b  # noqa: E402
import clasificacion as k  # noqa: E402
import particion as pa  # noqa: E402

REMUESTREOS = 2000
SEMILLA_BOOT = 20261101
NIVELES = {"actual": None, "75": 0.75, "80": 0.80, "88": 0.88}
TOPE_AURC = 0.88
ESPACIO = {
    "piso": [0.5, 0.55, 0.6, 0.65, 0.7],
    "w_jac": [0.3, 0.35, 0.4, 0.45, 0.5],
    "w_cos": [0.0, 0.05, 0.1, 0.15, 0.2, 0.3],
    "corte": [0.4, 0.45, 0.5, 0.55, 0.6],
}
CLAVES = ("piso", "w_jac", "w_cos", "corte")


class Grupos:
    def __init__(self, p: np.ndarray, s: np.ndarray, y: np.ndarray, corte: float):
        pc = np.where(s >= corte, p, -1)
        self.elegible = pc >= 0
        self.ok = (pc == y)[self.elegible]
        sv = np.round(s[self.elegible], 9)
        self.valores, inv = np.unique(-sv, return_inverse=True)
        self.valores = -self.valores
        self.g = inv
        self.G = len(self.valores)

    def sumas(self, w: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        we = w[self.elegible]
        return np.bincount(self.g, we, self.G), np.bincount(self.g, we * self.ok, self.G)


def _acum(wg: np.ndarray, cg: np.ndarray):
    return np.concatenate([[0.0], np.cumsum(wg)]), np.concatenate([[0.0], np.cumsum(cg)])


def precision_en(wg, cg, wtot: float, cobertura: np.ndarray) -> np.ndarray:
    W, C = _acum(wg, cg)
    x = np.asarray(cobertura) * wtot
    j = np.clip(np.searchsorted(W, x, side="left") - 1, 0, len(wg) - 1)
    r = np.divide(cg, wg, out=np.zeros_like(cg), where=wg > 0)
    c = C[j] + (x - W[j]) * r[j]
    out = c / x
    return np.where(x <= W[-1] + 1e-9, out, np.nan)


def _integral_riesgo(W, C, r, x: float) -> float:
    tot = 0.0
    for j in range(len(r)):
        a, bb = W[j], min(W[j + 1], x)
        if a >= x:
            break
        if bb <= a:
            continue
        A = C[j] - r[j] * W[j]
        tot += (1 - r[j]) * (bb - a) - (A * np.log(bb / a) if a > 0 else 0.0)
    return tot


def aurc(wg, cg, wtot: float, lo: float, hi: float) -> float:
    W, C = _acum(wg, cg)
    if hi * wtot > W[-1] + 1e-9:
        return float("nan")
    r = np.divide(cg, wg, out=np.zeros_like(cg), where=wg > 0)
    return (_integral_riesgo(W, C, r, hi * wtot) - _integral_riesgo(W, C, r, lo * wtot)) / ((hi - lo) * wtot)


def tau_para(grp: Grupos, wg, wtot: float, cobertura: float) -> tuple[float, float]:
    cum = np.cumsum(wg) / wtot
    j = int(np.searchsorted(cum, cobertura - 1e-12))
    j = min(j, len(cum) - 1)
    return float(grp.valores[j]), float(cum[j])


def resumen_config(grp: Grupos, w: np.ndarray, niveles: dict[str, float]) -> dict:
    wg, cg = grp.sumas(w)
    wt = float(w.sum())
    pre = {n: float(precision_en(wg, cg, wt, np.array([c]))[0]) for n, c in niveles.items()}
    return {
        "precision": pre,
        "aurc_0_88": float(aurc(wg, cg, wt, 0.0, TOPE_AURC)),
        "aurc_50_88": float(aurc(wg, cg, wt, 0.5, TOPE_AURC)),
        "cobertura_maxima": float(wg.sum() / wt),
    }


def vector_metricas(grp: Grupos, w: np.ndarray, niveles: np.ndarray) -> np.ndarray:
    wg, cg = grp.sumas(w)
    wt = float(w.sum())
    return np.concatenate(
        [
            precision_en(wg, cg, wt, niveles),
            [aurc(wg, cg, wt, 0.0, TOPE_AURC), aurc(wg, cg, wt, 0.5, TOPE_AURC)],
        ]
    )


def cfgs_nombradas() -> dict[str, dict]:
    a = dict(k.ACTUAL)
    return {
        "actual": a,
        "piso 0,5": {**a, "piso": 0.5},
        "piso 0,55": {**a, "piso": 0.55},
        "peso Jaccard 0,35": {**a, "w_jac": 0.35},
        "peso coseno 0,05": {**a, "w_cos": 0.05},
        "corte 0,55": {**a, "corte": 0.55},
    }


def todas_las_combinaciones() -> list[dict]:
    return [
        {**k.ACTUAL, **dict(zip(CLAVES, v, strict=True))}
        for v in itertools.product(*(ESPACIO[c] for c in CLAVES))
    ]


def aurc_cfg(cx: b.Contexto, cfg: dict, mask: np.ndarray | None = None) -> float:
    p, s = cx.puntuar(cfg)
    m = np.ones(len(cx.y), bool) if mask is None else mask
    grp = Grupos(p[m], s[m], cx.y[m], cfg["corte"])
    wg, cg = grp.sumas(np.ones(int(m.sum())))
    return aurc(wg, cg, float(m.sum()), 0.0, TOPE_AURC)


def exactitud_cfg(cx: b.Contexto, cfg: dict, mask: np.ndarray | None = None) -> float:
    p, s = cx.puntuar(cfg)
    m = np.ones(len(cx.y), bool) if mask is None else mask
    return float((np.where(s[m] >= cfg["corte"], p[m], -1) == cx.y[m]).mean())


def parte1(cx: b.Contexto, combos: list[dict]) -> tuple[dict, dict]:
    n = len(cx.y)
    p0, s0 = cx.puntuar(k.ACTUAL)
    pc0 = np.where(s0 >= k.ACTUAL["corte"], p0, -1)
    ac0 = (s0 >= k.ACTUAL["tau"]) & (pc0 >= 0)
    cob_act = float(ac0.sum() / n)
    niveles = {"actual": cob_act, "75": 0.75, "80": 0.80, "88": 0.88}

    t0 = time.time()
    ex, au, pre = [], [], []
    for c in combos:
        p, s = cx.puntuar(c)
        grp = Grupos(p, s, cx.y, c["corte"])
        wg, cg = grp.sumas(np.ones(n))
        ex.append(exactitud_cfg(cx, c))
        au.append(aurc(wg, cg, float(n), 0.0, TOPE_AURC))
        pre.append(float(precision_en(wg, cg, float(n), np.array([cob_act]))[0]))
    ex, au, pre = (
        np.array(ex),
        np.nan_to_num(np.array(au), nan=np.inf),
        np.nan_to_num(np.array(pre), nan=-np.inf),
    )
    i_act = next(i for i, c in enumerate(combos) if all(abs(c[x] - k.ACTUAL[x]) < 1e-9 for x in CLAVES))
    dist = np.array([sum(abs(c[x] - k.ACTUAL[x]) > 1e-9 for x in CLAVES) for c in combos])

    def mejor(v, mayor):
        o = sorted(
            range(len(combos)), key=lambda i: (-round(v[i], 12) if mayor else round(v[i], 12), dist[i])
        )
        return o[0]

    i_ex, i_au, i_pr = mejor(ex, True), mejor(au, False), mejor(pre, True)
    conj = {
        "mejor conjunta por exactitud": combos[i_ex],
        "mejor conjunta por AURC (en muestra)": combos[i_au],
        "mejor conjunta por precision a 85,6 % (en muestra)": combos[i_pr],
    }
    barrido_completo = {
        "combinaciones": len(combos),
        "espacio": ESPACIO,
        "segundos": round(time.time() - t0, 1),
        "puesto_del_actual": {
            "exactitud": int((ex > ex[i_act] + 1e-12).sum() + 1),
            "aurc_0_88": int((au < au[i_act] - 1e-12).sum() + 1),
            "precision_a_85_6": int((pre > pre[i_act] + 1e-12).sum() + 1),
        },
        "mejor_exactitud_pp_sobre_actual": float(100 * (ex[i_ex] - ex[i_act])),
        "mejor_aurc_pp_sobre_actual": float(100 * (au[i_act] - au[i_au])),
        "combinaciones_que_no_llegan_a_88": int(np.isinf(au).sum()),
        "mejor_precision_85_6_pp_sobre_actual": float(100 * (pre[i_pr] - pre[i_act])),
        "combinaciones_con_precision_85_6_mayor_que_el_actual": int((pre > pre[i_act] + 1e-12).sum()),
        "combinaciones_con_aurc_menor_que_el_actual": int((au < au[i_act] - 1e-12).sum()),
    }

    cands = {**cfgs_nombradas(), **conj}
    vistos: dict[tuple, str] = {}
    alias: dict[str, str] = {}
    unicas: dict[str, dict] = {}
    for nom, c in cands.items():
        clave = tuple(round(c[x], 6) for x in CLAVES)
        if clave in vistos:
            alias[nom] = vistos[clave]
            continue
        vistos[clave] = nom
        unicas[nom] = c
    grp = {}
    for nom, c in unicas.items():
        p, s = cx.puntuar(c)
        grp[nom] = Grupos(p, s, cx.y, c["corte"])

    w1 = np.ones(n)
    punt = {}
    for nom, c in unicas.items():
        wg, cg = grp[nom].sumas(w1)
        r = resumen_config(grp[nom], w1, niveles)
        m75 = k.metricas(*cx.puntuar(c), cx.y, c["corte"], 0.75)
        tau85, cob85 = tau_para(grp[nom], wg, float(n), cob_act)
        punt[nom] = {
            "constantes": {x: c[x] for x in CLAVES},
            "exactitud": exactitud_cfg(cx, c),
            "en_tau_0_75": {"aceptada": m75["aceptada"], "precision_aceptada": m75["precision_aceptada"]},
            "tau_que_da_la_cobertura_actual": tau85,
            "cobertura_con_ese_tau": cob85,
            **r,
        }

    listas = np.unique(cx.lista)
    idx_l = {l: np.where(cx.lista == l)[0] for l in listas}
    por_l = np.array([[len(idx_l[l])] for l in listas]).ravel()
    pos_l = {l: i for i, l in enumerate(listas)}
    fila_l = np.array([pos_l[l] for l in cx.lista])
    rng = np.random.default_rng(SEMILLA_BOOT)
    niv = np.array(list(niveles.values()))
    malla = np.round(np.arange(0.50, 0.9001, 0.01), 2)
    nm = len(niv)
    nombres = list(unicas)
    boot = {nom: np.zeros((REMUESTREOS, nm + 2)) for nom in nombres}
    bootm = {nom: np.zeros((REMUESTREOS, len(malla))) for nom in nombres}
    t0 = time.time()
    for r in range(REMUESTREOS):
        veces = np.bincount(rng.integers(0, len(listas), len(listas)), minlength=len(listas)).astype(float)
        w = veces[fila_l]
        for nom in nombres:
            boot[nom][r] = vector_metricas(grp[nom], w, niv)
            wg, cg = grp[nom].sumas(w)
            bootm[nom][r] = precision_en(wg, cg, float(w.sum()), malla)
    etiquetas = list(niveles) + ["aurc_0_88", "aurc_50_88"]

    def ic(v: np.ndarray) -> list[float]:
        v = v[~np.isnan(v)]
        return [float(np.percentile(v, 2.5)), float(np.percentile(v, 97.5))]

    comparacion = {}
    for nom in nombres:
        if nom == "actual":
            continue
        fila = {}
        for j, et in enumerate(etiquetas):
            sgn = -1.0 if et.startswith("aurc") else 1.0
            d = sgn * (boot[nom][:, j] - boot["actual"][:, j]) * 100
            pt = (
                sgn * (punt[nom]["precision"][et] - punt["actual"]["precision"][et]) * 100
                if not et.startswith("aurc")
                else sgn * (punt[nom][et] - punt["actual"][et]) * 100
            )
            lo, hi = ic(d)
            fila[et] = {
                "diferencia_pp": float(pt),
                "ic95_pp": [lo, hi],
                "excluye_cero": bool(lo > 0 or hi < 0),
                "mejor_que_actual_con_ic": bool(lo > 0),
            }
        comparacion[nom] = fila
    malla_out = {
        "cobertura": malla.tolist(),
        "precision_actual": [
            float(precision_en(*grp["actual"].sumas(w1), float(n), np.array([m]))[0]) for m in malla
        ],
        "diferencia_pp": {},
        "ic95_pp": {},
    }
    for nom in nombres:
        if nom == "actual":
            continue
        wg, cg = grp[nom].sumas(w1)
        pn = precision_en(wg, cg, float(n), malla)
        pa_ = np.array(malla_out["precision_actual"])
        malla_out["diferencia_pp"][nom] = (100 * (pn - pa_)).tolist()
        d = 100 * (bootm[nom] - bootm["actual"])
        malla_out["ic95_pp"][nom] = [
            np.nanpercentile(d, 2.5, axis=0).tolist(),
            np.nanpercentile(d, 97.5, axis=0).tolist(),
        ]
    boot_s = round(time.time() - t0, 1)
    sal = {
        "cobertura_actual": cob_act,
        "aceptados_actual": int(ac0.sum()),
        "correctos_entre_aceptados_actual": int((ac0 & (pc0 == cx.y)).sum()),
        "renglones": n,
        "listas": int(len(listas)),
        "niveles_de_cobertura": niveles,
        "barrido_completo": barrido_completo,
        "alias": alias,
        "puntual": punt,
        "comparacion_con_actual_bootstrap_por_listas": {
            "remuestreos": REMUESTREOS,
            "segundos": boot_s,
            "positivo_es_mejor_que_el_actual": True,
            "candidatos": comparacion,
        },
        "malla_precision": malla_out,
    }
    return sal, {"unicas": unicas, "alias": alias}


def parte2(cx: b.Contexto, combos: list[dict]) -> dict:
    n = len(cx.y)
    p0, s0 = cx.puntuar(k.ACTUAL)
    pc0 = np.where(s0 >= k.ACTUAL["corte"], p0, -1)
    cob_act = float(((s0 >= k.ACTUAL["tau"]) & (pc0 >= 0)).sum() / n)
    niveles = {"actual": cob_act, "75": 0.75, "80": 0.80, "88": 0.88}
    niv = np.array(list(niveles.values()))
    PS = [cx.puntuar(c) for c in combos]
    i_act = next(i for i, c in enumerate(combos) if all(abs(c[x] - k.ACTUAL[x]) < 1e-9 for x in CLAVES))
    dist = np.array([sum(abs(c[x] - k.ACTUAL[x]) > 1e-9 for x in CLAVES) for c in combos])
    listas = sorted(set(cx.lista))

    def exact(mask):
        return np.array(
            [
                (np.where(s[mask] >= c["corte"], p[mask], -1) == cx.y[mask]).mean()
                for c, (p, s) in zip(combos, PS, strict=True)
            ]
        )

    def aurcs(mask):
        out = []
        for c, (p, s) in zip(combos, PS, strict=True):
            g = Grupos(p[mask], s[mask], cx.y[mask], c["corte"])
            wg, cg = g.sumas(np.ones(int(mask.sum())))
            out.append(aurc(wg, cg, float(mask.sum()), 0.0, TOPE_AURC))
        return np.nan_to_num(np.array(out), nan=np.inf)

    def elegir(tr, va, crit):
        v_tr = exact(tr) if crit == "exactitud" else -aurcs(tr)
        o = sorted(range(len(combos)), key=lambda i: (-round(v_tr[i], 12), dist[i]))[:5]
        v_va = exact(va) if crit == "exactitud" else -aurcs(va)
        o = sorted(o, key=lambda i: (-round(v_va[i], 12), o.index(i)))
        return o[0]

    def medir(i, mask):
        c = combos[i]
        p, s = PS[i]
        g = Grupos(p[mask], s[mask], cx.y[mask], c["corte"])
        return resumen_config(g, np.ones(int(mask.sum())), niveles)

    et = list(niveles) + ["aurc_0_88", "aurc_50_88"]
    filas = []
    t0 = time.time()
    for i in range(pa.SEMILLAS):
        sem = pa.SEMILLA_BASE + i
        parte = pa.partir(listas, sem)
        m = {q: np.isin(cx.lista, ls) for q, ls in parte.items()}
        fila = {
            "semilla": sem,
            "renglones_prueba": int(m["prueba"].sum()),
            "listas_prueba": len(parte["prueba"]),
        }
        pr = m["prueba"]
        base = medir(i_act, pr)
        fila["actual"] = base
        fila["cobertura_actual_en_prueba_tau_0_75"] = float(((s0 >= 0.75) & (pc0 >= 0))[pr].mean())
        for crit in ("exactitud", "aurc"):
            j = elegir(m["entrenamiento"], m["validacion"], crit)
            r = medir(j, pr)
            fila[f"elegido_por_{crit}"] = {
                "constantes": {x: combos[j][x] for x in CLAVES},
                "es_el_actual": bool(j == i_act),
                "precision": r["precision"],
                "aurc_0_88": r["aurc_0_88"],
                "aurc_50_88": r["aurc_50_88"],
                "diferencia_pp": {
                    e: float(
                        100
                        * (
                            (r["precision"][e] - base["precision"][e])
                            if not e.startswith("aurc")
                            else -(r[e] - base[e])
                        )
                    )
                    for e in et
                },
            }
        filas.append(fila)
    sal = {"semillas": pa.SEMILLAS, "segundos": round(time.time() - t0, 1), "por_semilla": filas}
    for crit in ("exactitud", "aurc"):
        res = {}
        for e in et:
            d = np.array([f[f"elegido_por_{crit}"]["diferencia_pp"][e] for f in filas])
            ok = ~np.isnan(d)
            d = d[ok]
            res[e] = {
                "media_pp": float(d.mean()),
                "sd_pp": float(d.std()),
                "min_pp": float(d.min()),
                "max_pp": float(d.max()),
                "semillas_validas": int(len(d)),
                "gana": int((d > 1e-9).sum()),
                "empata": int((np.abs(d) <= 1e-9).sum()),
                "pierde": int((d < -1e-9).sum()),
                "ic95_media_entre_semillas_pp": [
                    float(d.mean() - 1.96 * d.std(ddof=1) / np.sqrt(len(d))),
                    float(d.mean() + 1.96 * d.std(ddof=1) / np.sqrt(len(d))),
                ],
            }
        res["semillas_en_que_lo_elegido_es_el_actual"] = int(
            sum(f[f"elegido_por_{crit}"]["es_el_actual"] for f in filas)
        )
        freq: dict[str, int] = {}
        for f in filas:
            kk = json.dumps(f[f"elegido_por_{crit}"]["constantes"])
            freq[kk] = freq.get(kk, 0) + 1
        res["combinaciones_elegidas"] = [
            {"constantes": json.loads(a), "veces": v} for a, v in sorted(freq.items(), key=lambda t: -t[1])
        ]
        sal[f"elegido_por_{crit}_menos_actual"] = res
    sal["nota"] = (
        "El IC entre semillas es solo orientativo: las 20 particiones comparten listas, no son independientes. El juicio principal es el bootstrap por listas de la parte 1."
    )
    return sal


def conclusion(p1: dict, p2: dict) -> dict:
    comp = p1["comparacion_con_actual_bootstrap_por_listas"]["candidatos"]
    mejores, peores = [], []
    for nom, f in comp.items():
        for e in ("actual", "75", "80", "88", "aurc_0_88", "aurc_50_88"):
            if f[e]["mejor_que_actual_con_ic"]:
                mejores.append({"candidato": nom, "punto": e, **f[e]})
            if f[e]["ic95_pp"][1] < 0:
                peores.append({"candidato": nom, "punto": e, **f[e]})
    return {
        "candidatos_mejores_que_el_actual_con_ic_que_excluye_cero": mejores,
        "candidatos_peores_que_el_actual_con_ic_que_excluye_cero": peores,
    }


def dibujar(sal: dict) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib import font_manager as fm

    for f in ("lmroman10-regular.otf", "lmroman10-bold.otf"):
        r = __import__("subprocess").run(["kpsewhich", f], capture_output=True, text=True).stdout.strip()
        if r:
            fm.fontManager.addfont(r)
    plt.rcParams.update(
        {
            "font.family": "serif",
            "font.serif": ["Latin Modern Roman", "DejaVu Serif"],
            "font.size": 9,
            "axes.grid": True,
            "grid.color": "#E3E3E3",
            "axes.spines.top": False,
            "axes.spines.right": False,
            "pdf.fonttype": 42,
            "axes.formatter.use_locale": False,
            "axes.unicode_minus": False,
        }
    )
    p1 = sal["parte1_todos_los_datos"]
    mp = p1["malla_precision"]
    cob = np.array(mp["cobertura"]) * 100
    color = {
        "actual": "#000000",
        "piso 0,5": "#1F4E86",
        "piso 0,55": "#5B8DC9",
        "peso Jaccard 0,35": "#2E6B2B",
        "peso coseno 0,05": "#A8500F",
        "corte 0,55": "#5B2E99",
    }
    otros = ["#B22222", "#888800", "#008888"]
    nombres = list(mp["diferencia_pp"])
    col = {}
    for nm in nombres:
        col[nm] = color.get(nm) or otros[len(col) % 3] if nm not in color else color[nm]
    co = p1["cobertura_actual"] * 100
    fig, ax = plt.subplots(1, 3, figsize=(12.6, 3.9))
    a = ax[0]
    a.plot(cob, 100 * np.array(mp["precision_actual"]), color="black", lw=2, label="actual")
    for nm in nombres:
        pa_ = np.array(mp["precision_actual"]) * 100 + np.array(mp["diferencia_pp"][nm])
        a.plot(cob, pa_, color=col[nm], lw=1.1, label=nm)
    a.axvline(co, color="#888", ls=":", lw=1)
    a.set_xlabel("fraccion aceptada (%)")
    a.set_ylabel("precision de lo aceptado (%)")
    a.set_title("Curvas riesgo-cobertura")
    a.legend(fontsize=6.5, loc="lower left")
    b_ = ax[1]
    for nm in nombres:
        if nm.startswith("mejor"):
            continue
        d = np.array(mp["diferencia_pp"][nm])
        b_.plot(cob, d, color=col[nm], lw=1.2, label=nm)
        lo, hi = mp["ic95_pp"][nm]
        b_.fill_between(cob, lo, hi, color=col[nm], alpha=0.07)
    b_.axhline(0, color="black", lw=0.8)
    b_.axvline(co, color="#888", ls=":", lw=1)
    b_.set_xlabel("fraccion aceptada (%)")
    b_.set_ylabel("candidato menos actual (puntos)")
    b_.set_title("Diferencia con el actual, IC 95 % por listas")
    b_.legend(fontsize=6.5)
    c = ax[2]
    p2 = sal["parte2_particion_por_lista_20_semillas"]
    for pos, crit, et in ((0, "exactitud", "actual"), (1, "aurc", "actual")):
        d = [f[f"elegido_por_{crit}"]["diferencia_pp"][et] for f in p2["por_semilla"]]
        x = pos + (np.random.default_rng(1).random(len(d)) - 0.5) * 0.3
        c.scatter(x, d, s=14, color="#1F4E86" if pos == 0 else "#A8500F", alpha=0.8)
        c.hlines(np.nanmean(d), pos - 0.25, pos + 0.25, color="black", lw=2)
    c.axhline(0, color="black", lw=0.8)
    c.set_xticks([0, 1], ["elegido por\nexactitud", "elegido por\nAURC"])
    c.set_ylabel("precision en prueba, elegido menos actual (puntos)")
    c.set_title("Particion por lista: 20 semillas, a %.1f %% aceptado" % co)
    fig.tight_layout()
    fig.savefig(k.SALIDA / "punto_operacion.pdf")
    plt.close(fig)


def main() -> int:
    cx = b.Contexto()
    combos = todas_las_combinaciones()
    print(len(combos), "combinaciones")
    p1, _ = parte1(cx, combos)
    print("parte 1 lista", p1["barrido_completo"])
    p2 = parte2(cx, combos)
    sal = {
        "descripcion": "Comparacion al mismo punto de operacion (curva riesgo-cobertura). Ver docstring de punto_operacion.py.",
        "etiquetas": "El concepto que dejo la persona al revisar la salida del propio sistema (circularidad posible).",
        "parte1_todos_los_datos": p1,
        "parte2_particion_por_lista_20_semillas": p2,
        "conclusion_cuantitativa": conclusion(p1, p2),
    }
    ruta = k.SALIDA / "punto_operacion.json"
    ruta.write_text(json.dumps(sal, ensure_ascii=False, indent=1, default=float), encoding="utf-8")
    dibujar(sal)
    print("escrito", ruta)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
