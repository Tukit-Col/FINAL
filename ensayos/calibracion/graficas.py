"""Figuras (PNG y PDF vectorial) de la calibracion, a partir de los JSON de docs/informes/calibracion/.

Uso: uv run python ensayos/calibracion/graficas.py
"""

from __future__ import annotations

import json

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager as _fm

for _f in ("lmroman10-regular.otf", "lmroman10-bold.otf"):
    _r = __import__("subprocess").run(["kpsewhich", _f], capture_output=True, text=True).stdout.strip()
    if _r:
        _fm.fontManager.addfont(_r)
import nucleo as n
import numpy as np

SAL = n.SALIDA
# Paleta de la vista de contenedores (C4) de la memoria.
AZUL, NARANJA, VERDE, VIOLETA, GRIS = "#1F4E86", "#A8500F", "#2E6B2B", "#5B2E99", "#4D4D4D"
ANCHO = 6.3  # pulgadas: \\linewidth de una pagina A4 de la memoria

plt.rcParams.update(
    {
        "font.family": "serif",
        "font.serif": ["Latin Modern Roman", "CMU Serif", "Computer Modern Roman", "DejaVu Serif"],
        "mathtext.fontset": "cm",
        "axes.unicode_minus": False,
        "font.size": 9,
        "axes.titlesize": 9.5,
        "axes.labelsize": 9,
        "legend.fontsize": 7.5,
        "legend.frameon": True,
        "legend.edgecolor": "#BBBBBB",
        "axes.edgecolor": GRIS,
        "axes.labelcolor": "black",
        "axes.grid": True,
        "grid.color": "#E3E3E3",
        "grid.linewidth": 0.6,
        "axes.axisbelow": True,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "pdf.fonttype": 42,
        "axes.formatter.use_locale": False,
    }
)
from matplotlib.ticker import FuncFormatter  # noqa: E402

COMA = FuncFormatter(lambda v, _: f"{v:g}".replace(".", ","))


def guardar(fig, nombre: str) -> None:
    """Guarda PNG (150 ppp) y PDF vectorial con el mismo nombre."""
    fig.savefig(SAL / f"{nombre}.png", dpi=200)
    fig.savefig(SAL / f"{nombre}.pdf")
    plt.close(fig)


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
    fig, ax = plt.subplots(1, 2, figsize=(ANCHO, 2.9))
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
    ax[0].legend(fontsize=6.5, loc="lower right")
    ax[0].set_title("Tiempo según el tamaño S")

    bits = sorted({x["bits"] for x in filas})
    med = [np.median([r for x in filas if x["bits"] == b for r in x["razon_hv"]]) for b in bits]
    mn = [np.min([r for x in filas if x["bits"] == b for r in x["razon_hv"]]) for b in bits]
    ax[1].plot(bits, med, "o-", color=AZUL, label="mediana")
    ax[1].plot(bits, mn, "s--", color=NARANJA, label="mínimo")
    ax[1].set_ylim(0.99, 1.002)
    ax[1].set_xlabel("log$_2$ S")
    ax[1].set_ylabel("HV NSGA-II / frente exacto")
    ax[1].legend(fontsize=8)
    ax[1].set_title("Calidad del frente NSGA-II")
    fig.tight_layout()
    guardar(fig, "umbral")


def fig_rejilla():
    d = leer("calibracion_nsga.json")
    fig, ax = plt.subplots(figsize=(ANCHO * 0.7, 3.0))
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
    guardar(fig, "rejilla")


def fig_pesos():
    d = leer("pesos_p21.json")
    cs = list(d["pesos"])
    fig, ax = plt.subplots(figsize=(ANCHO * 0.7, 2.8))
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
    guardar(fig, "pesos_p21")


def fig_sensibilidad():
    d = leer("sensibilidad.json")
    fig, ax = plt.subplots(figsize=(ANCHO * 0.7, 3.0))
    for s, color in zip(
        sorted({c["sobreprecio"] for c in d["celdas"]}), (GRIS, AZUL, NARANJA, VERDE), strict=False
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
    guardar(fig, "sensibilidad")


def fig_tau():
    d = leer("tau.json")
    fig, ax = plt.subplots(figsize=(ANCHO * 0.7, 2.8))
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
    ax.set_xlabel(r"$\tau$")
    ax.legend(fontsize=8)
    fig.tight_layout()
    guardar(fig, "tau")


def fig_tau_clasificacion():
    """Matriz de confusion en tau = 0,75, precision frente a cobertura y ROC del parecido."""
    d = leer("tau.json")
    m = d["matriz_tau_actual"]
    fig, (a1, a2, a3) = plt.subplots(1, 3, figsize=(ANCHO, 2.4))
    mat = np.array([[m["tp"], m["fn"]], [m["fp"], m["tn"]]])
    a1.imshow(mat, cmap="Blues")
    for (i, j), v in np.ndenumerate(mat):
        a1.text(j, i, str(v), ha="center", va="center", color="white" if v > 150 else "black", fontsize=12)
    a1.set_xticks([0, 1], ["acepta", "revisión"])
    a1.set_yticks([0, 1], ["correcto", "incorrecto"])
    a1.set_xlabel(r"decisión con $\tau$ = 0,75")
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
    guardar(fig, "tau_clasificacion")


def fig_hipervolumen():
    d = leer("hipervolumen_prueba.json")
    perfiles = d["hv_relativo_por_perfil"]
    nombres = list(perfiles)
    fig, ax = plt.subplots(figsize=(ANCHO * 0.7, 2.8))
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
    guardar(fig, "hipervolumen_prueba")


# F1 de la percepcion en CGS-10 (diez documentos, 1.293 items). Fuente: Tabla tab:percepcion de la
# memoria, medida en los prototipos de tesis; no hay JSON de esa corrida en el repo.
PERCEPCION = [
    ("OCR con reglas", 0.298, 0.419),
    ("Docling", 0.364, 0.424),
    ("GOT-OCR2.0", 0.597, 0.569),
    ("Google Vision", 0.673, 0.672),
    ("Gemini (multimodal)", 0.948, 0.944),
]


def fig_percepcion():
    fig, ax = plt.subplots(figsize=(ANCHO * 0.78, 2.3))
    y = np.arange(len(PERCEPCION))
    mic = [m for _, m, _ in PERCEPCION]
    mac = [m for _, _, m in PERCEPCION]
    ax.barh(y + 0.19, mic, 0.36, color=AZUL, label="F1 micro")
    ax.barh(y - 0.19, mac, 0.36, color=NARANJA, label="F1 macro")
    for yi, v in zip(y, mic):
        ax.text(v + 0.012, yi + 0.19, f"{v:.3f}".replace(".", ","), va="center", fontsize=7)
    ax.set_yticks(y, [n for n, _, _ in PERCEPCION])
    ax.set_xlim(0, 1.08)
    ax.set_xlabel("F1 sobre CGS-10")
    ax.xaxis.set_major_formatter(COMA)
    ax.grid(axis="y", visible=False)
    ax.legend(loc="lower right")
    fig.tight_layout()
    guardar(fig, "percepcion_f1")


def fig_optimizador():
    """(a) Listas en que cada metodo iguala el optimo exacto; (b) latencia de ESC-D4 frente a DP-03."""
    raiz = SAL.parent / "benchmark-laya"
    r = json.loads((raiz / "resumen.json").read_text(encoding="utf-8"))
    e = leer("esc_d4.json")
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(ANCHO, 2.6), gridspec_kw={"width_ratios": [1.25, 1]})
    perfiles = [("ahorrador", "Ahorrador"), ("premium", "Premium"), ("fan", "Fan")]
    metodos = [("nsga2", "NSGA-II", AZUL), ("heuristica", "regla simple", VERDE), ("azar", "al azar", GRIS)]
    x = np.arange(len(perfiles))
    for k, (m, nom, col) in enumerate(metodos):
        vals = [r[f"{p}/{m}"]["optimo_pct"] for p, _ in perfiles]
        a1.bar(x + (k - 1) * 0.26, vals, 0.24, color=col, label=nom)
        for xi, v in zip(x + (k - 1) * 0.26, vals):
            a1.text(xi, v + 2, f"{v:.0f}", ha="center", fontsize=6.5)
    a1.set_xticks(x, [n for _, n in perfiles])
    a1.set_ylim(0, 115)
    a1.set_ylabel("% de listas con el kit exacto")
    a1.set_title(f"(a) Frente a la programación dinámica (n = {r['ahorrador/nsga2']['n']})", fontsize=9)
    a1.legend(loc="upper center", ncol=3, bbox_to_anchor=(0.5, -0.13), fontsize=7)
    a1.grid(axis="x", visible=False)
    cuant = [("mediana_s", "p50"), ("p95_s", "p95"), ("p99_s", "p99"), ("max_s", "máx.")]
    xx = np.arange(len(cuant))
    for k, (clave, nom, col) in enumerate([("sin_preferencias", "sin preferencias", AZUL), ("personaje_y_punto_medio", "con personaje", NARANJA)]):
        vals = [e[clave][c] for c, _ in cuant]
        a2.bar(xx + (k - 0.5) * 0.36, vals, 0.34, color=col, label=nom)
    a2.axhline(e["limite_s"], color=VIOLETA, ls="--", lw=1)
    a2.text(len(cuant) - 0.5, e["limite_s"] * 0.8, f"DP-03: {e['limite_s']:g} s", ha="right", va="top", fontsize=7, color=VIOLETA)
    a2.set_yscale("log")
    a2.set_ylim(0.05, 15)
    a2.set_xticks(xx, [n for _, n in cuant])
    a2.set_ylabel("segundos (escala log)")
    a2.set_title(f"(b) ESC-D4, {e['sin_preferencias']['ejecuciones'] * 2:,} ejecuciones".replace(",", "."), fontsize=9)
    a2.yaxis.set_major_formatter(COMA)
    a2.legend(loc="center left", fontsize=7)
    a2.grid(axis="x", visible=False)
    fig.tight_layout()
    guardar(fig, "optimizador_benchmarks")


if __name__ == "__main__":
    for f in (fig_umbral, fig_rejilla, fig_pesos, fig_sensibilidad, fig_tau, fig_tau_clasificacion, fig_hipervolumen, fig_percepcion, fig_optimizador):
        try:
            f()
            print("ok", f.__name__)
        except FileNotFoundError as e:
            print("falta", e.filename)
