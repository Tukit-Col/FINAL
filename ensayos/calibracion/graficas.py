"""Figuras (PNG) de la calibracion, a partir de los JSON de docs/informes/calibracion/.

Uso: uv run python ensayos/calibracion/graficas.py
"""

from __future__ import annotations

import json

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import nucleo as n
import numpy as np

SAL = n.SALIDA
AZUL, NARANJA, GRIS = "#1f4e79", "#c55a11", "#7f7f7f"


def leer(nombre: str):
    return json.loads((SAL / nombre).read_text(encoding="utf-8"))


def ajuste_exacto(filas):
    """Ajuste log-log t = c * S^k de la enumeracion exacta y desviacion de los residuos."""
    f = [x for x in filas if x["exacto"]]
    S = np.array([x["S"] for x in f], float)
    t = np.array([x["exacto"]["t_total"] for x in f])
    k, logc = np.polyfit(np.log(S), np.log(t), 1)
    res = np.log(t) - (k * np.log(S) + logc)
    return float(k), float(np.exp(logc)), float(res.std())


def fig_umbral():
    d = leer("umbral.json")
    filas = d["filas"]
    k, c, sd = ajuste_exacto(filas)
    fig, ax = plt.subplots(1, 2, figsize=(11, 4))
    S = np.array([x["S"] for x in filas if x["exacto"]])
    t = np.array([x["exacto"]["t_total"] for x in filas if x["exacto"]])
    ax[0].loglog(S, t, "o", color=AZUL, label="enumeración exacta (medido)")
    sn = np.array([x["S"] for x in filas for _ in x["t_nsga_s"]])
    tn = np.array([v for x in filas for v in x["t_nsga_s"]])
    ax[0].loglog(sn, tn, "s", color=NARANJA, ms=4, alpha=0.6, label="NSGA-II (medido)")
    xs = np.logspace(np.log10(S.min()), np.log10(sn.max()), 50)
    ax[0].loglog(xs, c * xs**k, "-", color=AZUL, lw=1, label=f"ajuste exacto: {c:.1e}·S^{k:.2f}")
    ax[0].loglog(xs, c * np.exp(1.645 * sd) * xs**k, "--", color=AZUL, lw=1, label="percentil 95 del ajuste")
    limite = d.get("limite_enumeracion", 4096)
    ax[0].axvline(limite, color=GRIS, ls=":")
    ax[0].text(limite * 1.1, ax[0].get_ylim()[0] * 3, str(limite), color=GRIS)
    ax[0].axhline(4.0, color="k", ls="--", lw=0.8)
    ax[0].text(S.min(), 4.4, "mitad de DP-03 (4 s)", fontsize=8)
    ax[0].set_xlabel("tamaño del espacio S")
    ax[0].set_ylabel("tiempo de pared (s)")
    ax[0].legend(fontsize=7, loc="upper left")
    ax[0].set_title("Tiempo según el tamaño del espacio")

    bits = sorted({x["bits"] for x in filas})
    med = [np.median([r for x in filas if x["bits"] == b for r in x["razon_hv"]]) for b in bits]
    mn = [np.min([r for x in filas if x["bits"] == b for r in x["razon_hv"]]) for b in bits]
    ax[1].plot(bits, med, "o-", color=AZUL, label="mediana")
    ax[1].plot(bits, mn, "s--", color=NARANJA, label="mínimo")
    ax[1].set_ylim(0.99, 1.002)
    ax[1].set_xlabel("log₂ S")
    ax[1].set_ylabel("hipervolumen NSGA-II / frente exacto")
    ax[1].legend(fontsize=8)
    ax[1].set_title("Calidad del frente NSGA-II (30 semillas)")
    fig.tight_layout()
    fig.savefig(SAL / "umbral.png", dpi=150)


def fig_rejilla():
    d = leer("calibracion_nsga.json")
    fig, ax = plt.subplots(figsize=(6, 4))
    r = d["rejilla"]
    ax.plot([x["evals_medios"] for x in r], [x["hv_medio"] for x in r], "s", color=AZUL, label="rejilla")
    e = d["elegida"]
    v = next(x for x in r if x["a"] == e["a"] and x["b"] == e["b"])
    a = next(x for x in r if x["a"] == 1.0 and x["b"] == 1.0)
    ax.plot(v["evals_medios"], v["hv_medio"], "*", ms=14, color=NARANJA, label="elegida")
    ax.plot(a["evals_medios"], a["hv_medio"], "D", ms=8, mfc="none", color="k", label="de partida")
    ax.axhline(max(x["hv_medio"] for x in r) - d["umbral_hv"], color=GRIS, ls=":", lw=1)
    ax.set_xscale("log")
    ax.set_xlabel("evaluaciones por lista (población × generaciones)")
    ax.set_ylabel("hipervolumen / frente exacto")
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(SAL / "rejilla.png", dpi=150)


def fig_pesos():
    d = leer("pesos_p21.json")
    cs = list(d["pesos"])
    fig, ax = plt.subplots(figsize=(6, 3.5))
    x = np.arange(len(cs))
    w = [d["pesos"][c] for c in cs]
    err = [[d["pesos"][c] - d["ic95"][c][0] for c in cs], [d["ic95"][c][1] - d["pesos"][c] for c in cs]]
    ax.bar(x - 0.2, w, 0.4, yerr=err, capsize=3, color=AZUL, label="encuesta P21 (IC 95 %)")
    ax.bar(
        x + 0.2,
        [d["pesos_anteriores_del_codigo"][c] for c in cs],
        0.4,
        color=GRIS,
        label="valores anteriores del código",
    )
    ax.set_xticks(x, cs)
    ax.set_ylabel("peso")
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(SAL / "pesos_p21.png", dpi=150)


def fig_sensibilidad():
    d = leer("sensibilidad.json")
    fig, ax = plt.subplots(figsize=(6, 4))
    for s, color in zip(
        sorted({c["sobreprecio"] for c in d["celdas"]}), (GRIS, AZUL, NARANJA, "#548235"), strict=False
    ):
        cs = [c for c in d["celdas"] if c["sobreprecio"] == s]
        ax.errorbar(
            [c["sd_componente_precio"] for c in cs],
            [c["estable_medio"] for c in cs],
            yerr=[
                [c["estable_medio"] - c["ic95"][0] for c in cs],
                [c["ic95"][1] - c["estable_medio"] for c in cs],
            ],
            marker="o",
            capsize=3,
            color=color,
            label=f"sobreprecio {s:.0%}",
        )
    ax.set_xlabel("desviación estándar de la perturbación del peso de precio")
    ax.set_ylabel("fracción con el mismo kit recomendado")
    ax.set_ylim(0, 1.02)
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(SAL / "sensibilidad.png", dpi=150)


def fig_tau():
    d = leer("tau.json")
    fig, ax = plt.subplots(figsize=(6, 3.5))
    c = d["curva"]
    ax.plot(
        [x["tau"] for x in c], [x["precision"] for x in c], "o-", color=AZUL, label="precisión de lo aceptado"
    )
    ax.plot(
        [x["tau"] for x in c],
        [x["fraccion_aceptada"] for x in c],
        "s-",
        color=NARANJA,
        label="fracción aceptada",
    )
    ax.axvline(0.75, color=GRIS, ls=":")
    ax.set_xlabel("τ")
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(SAL / "tau.png", dpi=150)


def fig_tau_clasificacion():
    """Matriz de confusion en tau = 0,75, precision frente a cobertura y ROC del parecido."""
    d = leer("tau.json")
    m = d["matriz_tau_actual"]
    fig, (a1, a2, a3) = plt.subplots(1, 3, figsize=(10, 3.2))
    mat = np.array([[m["tp"], m["fn"]], [m["fp"], m["tn"]]])
    a1.imshow(mat, cmap="Blues")
    for (i, j), v in np.ndenumerate(mat):
        a1.text(j, i, str(v), ha="center", va="center", color="white" if v > 150 else "black", fontsize=12)
    a1.set_xticks([0, 1], ["acepta", "revisión"])
    a1.set_yticks([0, 1], ["correcto", "incorrecto"])
    a1.set_xlabel("decisión con τ = 0,75")
    a1.set_ylabel("según el revisor")
    a1.set_title("(a) Matriz de confusión", fontsize=9)
    pares = len(d["roc"]) and d["pares"]
    pos = d["aciertos"]
    cob, pre = [], []
    for pt in d["roc"][1:]:
        acept_pos = pt["tpr"] * pos
        acept_neg = pt["fpr"] * (pares - pos)
        cob.append((acept_pos + acept_neg) / pares)
        pre.append(acept_pos / (acept_pos + acept_neg))
    a2.plot(cob, pre, "o-", color=AZUL, ms=3, lw=1)
    a2.plot([d["en_tau_actual"]["fraccion_aceptada"]], [d["en_tau_actual"]["precision"]], "o", color=NARANJA, ms=7)
    a2.axhline(pos / pares, color=GRIS, ls=":")
    a2.set_xlabel("fracción aceptada sin revisión")
    a2.set_ylabel("precisión de lo aceptado")
    a2.set_title("(b) Precisión frente a cobertura", fontsize=9)
    fpr = [x["fpr"] for x in d["roc"]]
    tpr = [x["tpr"] for x in d["roc"]]
    a3.plot(fpr, tpr, "o-", color=AZUL, ms=3, lw=1)  # empates: segmento recto entre puntos de operación
    i = next(k for k, x in enumerate(d["roc"]) if x["umbral"] is not None and x["umbral"] < 0.75) - 1
    a3.plot([fpr[i]], [tpr[i]], "o", color=NARANJA, ms=7)
    a3.plot([0, 1], [0, 1], color=GRIS, ls=":")
    a3.set_xlabel("tasa de falsos positivos")
    a3.set_ylabel("tasa de verdaderos positivos")
    a3.set_title(f"(c) ROC, AUC = {d['auc_parecido']:.3f}".replace(".", ","), fontsize=9)
    fig.tight_layout()
    fig.savefig(SAL / "tau_clasificacion.pdf")
    fig.savefig(SAL / "tau_clasificacion.png", dpi=150)


def fig_hipervolumen():
    d = leer("hipervolumen_prueba.json")
    perfiles = d["hv_relativo_por_perfil"]
    nombres = list(perfiles)
    fig, ax = plt.subplots(figsize=(6, 3.5))
    x = np.arange(len(nombres) + 1)
    medias = [d["razon_hv_frente_media"]] + [perfiles[p]["media"] for p in nombres]
    ics = [d["razon_hv_frente_ic95"]] + [perfiles[p]["ic95"] for p in nombres]
    err = [
        [m - i[0] for m, i in zip(medias, ics, strict=True)],
        [i[1] - m for m, i in zip(medias, ics, strict=True)],
    ]
    ax.bar(x, medias, 0.6, yerr=err, capsize=3, color=[AZUL] + [NARANJA] * len(nombres))
    ax.set_xticks(x, ["frente"] + nombres)
    ax.set_ylabel("hipervolumen / frente exacto")
    fig.tight_layout()
    fig.savefig(SAL / "hipervolumen_prueba.png", dpi=150)


if __name__ == "__main__":
    for f in (fig_umbral, fig_rejilla, fig_pesos, fig_sensibilidad, fig_tau, fig_tau_clasificacion, fig_hipervolumen):
        try:
            f()
            print("ok", f.__name__)
        except FileNotFoundError as e:
            print("falta", e.filename)
