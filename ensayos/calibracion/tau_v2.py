"""Calibracion de tau con el conjunto grande (renglones_etiquetados_v2.csv), por la RUTA REAL."""

from __future__ import annotations

import asyncio
import csv
import json
from collections import Counter

import numpy as np
import ruta_real as RR

RAIZ, SALIDA = RR.RAIZ, RR.SALIDA
ETIQ = RR.CL.DATOS / "renglones_etiquetados_v2.csv"
ORO = RR.MUESTRA_CIEGA / "adjudicacion_llm.csv"
SEMILLA = 20261101
REP = 2000
OBJ = 0.95
GRID = np.round(np.arange(0.5, 1.0001, 0.025), 3)
PUNTOS = (0.5, 0.6, 0.7, 0.75, 0.8, 0.85, 0.9)


def emparejar_todo(textos):
    conceptos, productos = asyncio.run(RR.cargar_indice())
    unicos = sorted(set(textos))
    vecs, _ = RR.vectores(unicos)
    em = RR.correr(unicos, vecs, conceptos, productos)
    d = {}
    for t, e in zip(unicos, em, strict=True):
        ok = e.estado == "reconocido" and bool(e.opciones)
        d[t] = (ok, float(e.parecido or 0.0), e.concepto_codigo or "")
    return d


class Datos:
    def __init__(self, textos, etiquetas, listas, colegios, em, extra=None):
        self.ok = np.array([em[t][0] for t in textos])
        self.p = np.array([em[t][1] for t in textos])
        self.acierto = np.array([em[t][2] == (e or "") for t, e in zip(textos, etiquetas, strict=True)])
        self.listas = np.array(listas)
        self.colegios = np.array(colegios)
        self.extra = extra
        self.n = len(textos)

    def sub(self, m):
        o = object.__new__(Datos)
        o.ok, o.p, o.acierto, o.listas, o.colegios = (
            a[m] for a in (self.ok, self.p, self.acierto, self.listas, self.colegios)
        )
        o.extra, o.n = None, int(m.sum())
        return o


def acepta(d, tau):
    return d.ok & (d.p >= tau - 1e-12)


def cifras(d, tau):
    a = acepta(d, tau)
    na = int(a.sum())
    ac = int((a & d.acierto).sum())
    return {
        "tau": float(tau),
        "n": d.n,
        "aceptados": na,
        "fraccion_aceptada": na / d.n if d.n else None,
        "precision": ac / na if na else None,
        "a_revision": d.n - na,
        "errores_aceptados": na - ac,
        "errores_por_100_renglones": 100 * (na - ac) / d.n if d.n else None,
    }


def bootstrap(d, clave, taus, rng):
    cl = d.listas if clave == "lista" else d.colegios
    ids = sorted(set(cl))
    na = np.array([[int((acepta(d, t) & (cl == c)).sum()) for t in taus] for c in ids], float)
    ac = np.array([[int((acepta(d, t) & d.acierto & (cl == c)).sum()) for t in taus] for c in ids], float)
    nn = np.array([int((cl == c).sum()) for c in ids], float)
    fr, pr = [], []
    for _ in range(REP):
        i = rng.integers(0, len(ids), len(ids))
        a, k, n = na[i].sum(0), ac[i].sum(0), nn[i].sum()
        fr.append(a / n)
        pr.append(np.where(a > 0, k / np.maximum(a, 1), np.nan))
    fr, pr = np.array(fr), np.array(pr)
    out = []
    for j in range(len(taus)):
        f = np.percentile(fr[:, j], [2.5, 97.5])
        pj = pr[:, j][~np.isnan(pr[:, j])]
        out.append(
            {
                "fraccion_ic95": [float(f[0]), float(f[1])],
                "precision_ic95": [float(np.percentile(pj, 2.5)), float(np.percentile(pj, 97.5))]
                if len(pj)
                else None,
            }
        )
    return out


def curva(d, rng, con_ic=True):
    taus = [float(t) for t in GRID]
    base = [cifras(d, t) for t in taus]
    if con_ic:
        bl, bc = bootstrap(d, "lista", taus, rng), bootstrap(d, "colegio", taus, rng)
        for b, x, y in zip(base, bl, bc, strict=True):
            b["ic95_por_lista"], b["ic95_por_colegio"] = x, y
    return base


def elegir(d, objetivo=OBJ):
    for t in sorted(set(d.p[d.ok])):
        c = cifras(d, float(t))
        if c["precision"] is not None and c["precision"] >= objetivo:
            return float(t)
    return 1.01


def resumen_cv(filas, clave="precision"):
    v = [f[clave] for f in filas if f[clave] is not None]
    return {
        "media": float(np.mean(v)),
        "sd": float(np.std(v, ddof=1)) if len(v) > 1 else None,
        "min": float(np.min(v)),
        "max": float(np.max(v)),
    }


def loso(d, objetivo=OBJ):
    filas = []
    for c in sorted(set(d.colegios)):
        te = d.colegios == c
        t = elegir(d.sub(~te), objetivo)
        filas.append(
            {
                "colegio_retenido": c,
                "tau_elegido": t,
                **cifras(d.sub(te), t),
                "en_075": cifras(d.sub(te), 0.75),
            }
        )
    return filas


def particion(d, objetivo=OBJ, semillas=20):
    ls = sorted(set(d.listas))
    filas = []
    for s in range(semillas):
        r = np.random.default_rng(SEMILLA + s)
        o = list(ls)
        r.shuffle(o)
        k1, k2 = round(0.70 * len(o)), round(0.85 * len(o))
        g = {l: (0 if i < k1 else 1 if i < k2 else 2) for i, l in enumerate(o)}
        gi = np.array([g[l] for l in d.listas])
        t = elegir(d.sub(gi == 0), objetivo)
        fila = {"semilla": SEMILLA + s, "tau_elegido": t}
        for nom, k in (("val", 1), ("prueba", 2)):
            fila[nom] = cifras(d.sub(gi == k), t)
            fila[nom + "_en_075"] = cifras(d.sub(gi == k), 0.75)
        filas.append(fila)
    res = {"filas": filas, "tau_elegido": resumen_cv([{"x": f["tau_elegido"]} for f in filas], "x")}
    for nom in ("val", "prueba", "val_en_075", "prueba_en_075"):
        res[nom] = {
            "precision": resumen_cv([f[nom] for f in filas]),
            "fraccion_aceptada": resumen_cv([f[nom] for f in filas], "fraccion_aceptada"),
        }
    return res


def main():
    rng = np.random.default_rng(SEMILLA)
    et = list(csv.DictReader(ETIQ.open(encoding="utf-8")))
    M_ = RR.MUESTRA_CIEGA
    rd = lambda n: {r["id"]: r["concepto_codigo"] for r in csv.DictReader((M_ / n).open(encoding="utf-8"))}  # noqa: E731
    A, B = rd("anotador_A_llm.csv"), rd("anotador_B_llm.csv")
    adj = {r["id"]: r["adjudicado"] for r in csv.DictReader(ORO.open(encoding="utf-8"))}
    oro = {i: (A[i] if A[i] == B[i] else adj[i]) for i in A}
    ou = [{"id": i, "adjudicado": oro[i]} for i in sorted(oro)]
    mu = {r["id"]: r for r in csv.DictReader((RR.MUESTRA_CIEGA / "muestra.csv").open(encoding="utf-8"))}
    em = emparejar_todo([r["texto_original"] for r in et] + [r["texto_original"] for r in mu.values()])
    D = Datos(
        [r["texto_original"] for r in et],
        [r["concepto_codigo"] for r in et],
        [r["colegio"] + "|" + r["grado"] for r in et],
        [r["colegio"] for r in et],
        em,
    )
    out = {
        "aviso": "Etiquetas = salida del sistema aceptada o corregida por una revision (parcialmente circular); el catalogo vivo puede haber aprendido de esas mismas correcciones. Sin cambios adoptados.",
        "conjunto": {
            "renglones": D.n,
            "listas": len(set(D.listas)),
            "colegios": len(set(D.colegios)),
            "sin_concepto": int(sum(r["concepto_codigo"] == "" for r in et)),
            "origen": dict(Counter(r["origen_revision"] for r in et)),
            "elegibles_a_aceptar(reconocido_con_opciones)": int(D.ok.sum()),
            "precision_global_si_se_acepta_todo_elegible": cifras(D, 0.0)["precision"],
        },
    }
    out["curva_sistema"] = curva(D, rng)
    out["puntos_clave_sistema"] = [c for c in out["curva_sistema"] if round(c["tau"], 3) in PUNTOS]
    out["loso_por_colegio"] = loso(D)
    out["loso_resumen"] = {
        "precision": resumen_cv(out["loso_por_colegio"]),
        "precision_en_075": resumen_cv([f["en_075"] for f in out["loso_por_colegio"]]),
        "tau_elegidos": [f["tau_elegido"] for f in out["loso_por_colegio"]],
    }
    out["loso_objetivo_098"] = loso(D, 0.98)
    out["particion_70_15_15"] = particion(D)
    out["particion_70_15_15_objetivo_098"] = {k: v for k, v in particion(D, 0.98).items() if k != "filas"}
    corr = np.array([r["concepto_corregido_por_persona"] == "1" for r in et])
    sin_c = np.array([r["concepto_codigo"] != "" for r in et])
    out["sensibilidad"] = {}
    for nom, m in (
        ("sin_28_corregidos", ~corr),
        ("solo_con_concepto", sin_c),
        ("solo_Agustiniano_excluido", D.colegios != "COLEGIO AGUSTINIANO CIUDAD SALITRE"),
    ):
        s = D.sub(m)
        out["sensibilidad"][nom] = [cifras(s, t) for t in PUNTOS]
    out["por_colegio_en_075"] = {c: cifras(D.sub(D.colegios == c), 0.75) for c in sorted(set(D.colegios))}
    ids = [r["id"] for r in ou]
    M = Datos(
        [mu[i]["texto_original"] for i in ids],
        [r["adjudicado"].replace("NINGUNO", "") for r in ou],
        [mu[i]["colegio"] + "|" + mu[i]["grado"] for i in ids],
        [mu[i]["colegio"] for i in ids],
        em,
    )
    rm = {r["id"]: r for r in csv.DictReader((SALIDA / "ruta_real_muestra.csv").open(encoding="utf-8"))}
    dif = sum((acepta(M, 0.75)[k]) != (rm[i]["aceptado"] == "si") for k, i in enumerate(ids))
    out["muestra_ciega_oro_llm"] = {
        "n": M.n,
        "listas": len(set(M.listas)),
        "colegios": len(set(M.colegios)),
        "textos_de_la_muestra_presentes_en_v2": int(
            sum(mu[i]["texto_original"] in {r["texto_original"] for r in et} for i in ids)
        ),
        "discrepancias_aceptado_vs_ruta_real_muestra.csv_en_075": int(dif),
        "curva": curva(M, rng),
    }
    out["muestra_ciega_oro_llm"]["puntos_clave"] = [
        c for c in out["muestra_ciega_oro_llm"]["curva"] if round(c["tau"], 3) in PUNTOS
    ]
    ts = {mu[i]["texto_original"] for i in ids}
    mm = np.array([r["texto_original"] in ts for r in et])
    out["etiquetas_sistema_en_textos_de_la_muestra"] = [cifras(D.sub(mm), t) for t in PUNTOS]
    a = [c["precision"] for c in out["curva_sistema"]]
    b = [c["precision"] for c in out["muestra_ciega_oro_llm"]["curva"]]
    out["comparacion_curvas"] = {
        "diferencia_precision_media_abs": float(
            np.nanmean([abs(x - y) for x, y in zip(a, b, strict=True) if x is not None and y is not None])
        ),
        "diferencia_fraccion_media_abs": float(
            np.mean(
                [
                    abs(x["fraccion_aceptada"] - y["fraccion_aceptada"])
                    for x, y in zip(out["curva_sistema"], out["muestra_ciega_oro_llm"]["curva"], strict=True)
                ]
            )
        ),
        "precision_sistema_menos_oro_por_tau": {
            f"{c['tau']:.3f}": (
                None if c["precision"] is None or y["precision"] is None else c["precision"] - y["precision"]
            )
            for c, y in zip(out["curva_sistema"], out["muestra_ciega_oro_llm"]["curva"], strict=True)
        },
    }
    v = json.load((SALIDA / "tau.json").open())
    out["calibracion_vieja_405"] = {
        "pares": v["pares"],
        "listas": v["listas"],
        "colegios": 3,
        "aciertos": v["aciertos"],
        "auc": v["auc_parecido"],
        "puntos": [c for c in v["curva"] if c["tau"] in (0.5, 0.6, 0.7, 0.75, 0.8, 0.85, 0.9)],
        "ic95_precision_075": v["ic95_bootstrap_tau_actual"]["precision"],
        "cv_taus": [f["tau"] for f in v["validacion_cruzada_agrupada"]],
    }
    (SALIDA / "tau_v2.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=1, default=str), encoding="utf-8"
    )
    tex(out)
    print(json.dumps({k: out[k] for k in ("conjunto", "puntos_clave_sistema")}, ensure_ascii=False)[:100])


def f(x, d=1, pct=True):
    if x is None:
        return "--"
    return (f"{100 * x:.{d}f}" if pct else f"{x:.{d}f}").replace(".", ",")


def tex(o):
    L = [
        r"% Generado por ensayos/calibracion/tau_v2.py. Precision y fraccion en \%.",
        r"\begin{tabular}{@{}rrrrrrr@{}}",
        r"\toprule",
        r"& \multicolumn{3}{c}{3.037 renglones, 80 listas, 7 colegios} & \multicolumn{2}{c}{Oro LLM, 240 renglones} & Vieja (405) \\",
        r"\cmidrule(lr){2-4}\cmidrule(lr){5-6}\cmidrule(lr){7-7}",
        r"$\tau$ & Aceptado & Precisi\'on & IC 95\,\% (listas) & Aceptado & Precisi\'on & Precisi\'on \\",
        r"\midrule",
    ]
    vie = {c["tau"]: c for c in o["calibracion_vieja_405"]["puntos"]}
    mu = {round(c["tau"], 3): c for c in o["muestra_ciega_oro_llm"]["puntos_clave"]}
    for c in o["puntos_clave_sistema"]:
        t = round(c["tau"], 3)
        ic = c["ic95_por_lista"]["precision_ic95"]
        L.append(
            f"{f(t, 2, False)} & {f(c['fraccion_aceptada'])} & {f(c['precision'])} & [{f(ic[0])}; {f(ic[1])}] & "
            f"{f(mu[t]['fraccion_aceptada'])} & {f(mu[t]['precision'])} & {f(vie[t]['precision'] if t in vie else None)} \\\\"
        )
    L += [r"\bottomrule", r"\end{tabular}"]
    (SALIDA / "tabla_tau_v2.tex").write_text("\n".join(L) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
