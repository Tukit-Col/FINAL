"""Figuras de la comparacion de optimizadores (PDF + PNG, 15,5 cm de ancho).

    python graficas.py   -> ../figuras/fig_opt_tiempo, fig_opt_memoria, fig_opt_calidad
"""

from __future__ import annotations

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402

from analizar import NOMBRES, hv_ratio  # noqa: E402
from tukit_final import FIGURAS, RESULTADOS, cargar_json  # noqa: E402

ANCHO = 15.5 / 2.54
plt.rcParams.update(
    {
        "font.family": "sans-serif",
        "font.sans-serif": ["Helvetica", "Arial", "DejaVu Sans"],
        "font.size": 8.5,
        "axes.titlesize": 9,
        "axes.labelsize": 8.5,
        "legend.fontsize": 7.5,
        "xtick.labelsize": 7.5,
        "ytick.labelsize": 7.5,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "pdf.fonttype": 42,
        "ps.fonttype": 42,
        "savefig.dpi": 300,
        "axes.formatter.use_locale": False,
    }
)
COLOR = {
    "enumeracion": "#7f7f7f",
    "dp": "#1b6ca8",
    "nsga2": "#d1495b",
    "nsga2_sin_siembra": "#edae49",
    "voraz": "#2e933c",
}
MARCA = {"enumeracion": "s", "dp": "o", "nsga2": "^", "nsga2_sin_siembra": "v", "voraz": "D"}
ORDEN = ["enumeracion", "dp", "nsga2", "nsga2_sin_siembra", "voraz"]
CORTO = {
    "enumeracion": "Enumeración exacta",
    "dp": "Programación dinámica",
    "nsga2": "NSGA-II (producción)",
    "nsga2_sin_siembra": "NSGA-II sin siembra",
    "voraz": "Voraz",
}


def _coma(x, _pos=None):
    return f"{x:g}".replace(".", ",")


def _guardar(fig, nombre):
    FIGURAS.mkdir(parents=True, exist_ok=True)
    for ext in ("pdf", "png"):
        fig.savefig(FIGURAS / f"{nombre}.{ext}", bbox_inches="tight")
    plt.close(fig)


def _datos():
    t = cargar_json(RESULTADOS / "corridas_tiempo.json.gz")["filas"]
    t = [f for f in t if f["prefs_tag"] == "sin_preferencias" and f["corridas"]]
    m = {}
    ruta = RESULTADOS / "corridas_memoria.json.gz"
    if ruta.exists():
        m = {
            f["instancia"]: {a: c["pico_bytes"] for a, c in f["corridas"].items()}
            for f in cargar_json(ruta)["filas"]
            if f["prefs_tag"] == "sin_preferencias"
        }
    h, hm = [], {}
    if (RESULTADOS / "hogares_tiempo.json.gz").exists():
        h = cargar_json(RESULTADOS / "hogares_tiempo.json.gz")["filas"]
    if (RESULTADOS / "hogares_memoria.json.gz").exists():
        hm = {f["instancia"]: {a: c["pico_bytes"] for a, c in f["corridas"].items()} for f in cargar_json(RESULTADOS / "hogares_memoria.json.gz")["filas"]}
    return t, m, h, hm


def _leyenda_algos(ax, algos, extra=True, loc="upper left"):
    hs = [Line2D([], [], color=COLOR[a], marker=MARCA[a], ls="", ms=4.5, label=CORTO[a]) for a in algos]
    if extra:
        hs += [
            Line2D([], [], color="0.3", marker="o", ls="", ms=4.5, label="lista real (un hijo)"),
            Line2D([], [], color="0.3", marker="o", mfc="none", ls="", ms=4.5, label="hogar sintético (2–8 hijos)"),
        ]
    ax.legend(handles=hs, loc=loc, frameon=False, handletextpad=0.3, borderaxespad=0.2)


def _leyenda_figura(fig, algos):
    hs = [Line2D([], [], color=COLOR[a], marker=MARCA[a], ls="", ms=4.5, label=CORTO[a]) for a in algos]
    hs += [
        Line2D([], [], color="0.3", marker="o", ls="", ms=4.5, label="lista real (un hijo)"),
        Line2D([], [], color="0.3", marker="o", mfc="none", ls="", ms=4.5, label="hogar sintético (2–8 hijos)"),
    ]
    fig.legend(handles=hs, loc="outside lower center", ncol=4, frameon=False, handletextpad=0.3, columnspacing=1.0)


def fig_tiempo(t, h):
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(ANCHO, 3.35), layout="constrained")
    for a in ORDEN:
        xs = [f["n"] for f in t if a in f["corridas"]]
        ys = [f["corridas"][a]["segundos"] for f in t if a in f["corridas"]]
        a1.scatter(xs, ys, s=9, color=COLOR[a], marker=MARCA[a], alpha=0.75, lw=0)
        hx = [f["n"] for f in h if a in f["corridas"]]
        hy = [f["corridas"][a]["segundos"] for f in h if a in f["corridas"]]
        a1.scatter(hx, hy, s=14, facecolors="none", edgecolors=COLOR[a], marker=MARCA[a], lw=0.8)
    a1.set_yscale("log")
    a1.set_xscale("log")
    a1.set_xlabel("Líneas decidibles $n$")
    a1.set_ylabel("Tiempo de pared (s)")
    a1.set_title("(a) Tiempo frente a $n$", loc="left")
    a1.xaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(_coma))
    for a in ORDEN:
        xs = [10 ** f["log10_espacio"] for f in t if a in f["corridas"]]
        ys = [f["corridas"][a]["segundos"] for f in t if a in f["corridas"]]
        a2.scatter(xs, ys, s=9, color=COLOR[a], marker=MARCA[a], alpha=0.75, lw=0)
        hx = [10 ** f["log10_espacio"] for f in h if a in f["corridas"]]
        hy = [f["corridas"][a]["segundos"] for f in h if a in f["corridas"]]
        a2.scatter(hx, hy, s=14, facecolors="none", edgecolors=COLOR[a], marker=MARCA[a], lw=0.8)
    a2.axvline(4096, color="0.4", lw=0.8, ls="--")
    a2.annotate("límite de enumeración\nen producción (4.096)", xy=(4096, 3e-4), xytext=(1e25, 1.2e-4),
                fontsize=7, color="0.3", arrowprops={"arrowstyle": "-", "color": "0.5", "lw": 0.6})
    a2.set_xscale("log")
    a2.set_yscale("log")
    a2.set_xticks([1, 1e20, 1e40, 1e60, 1e80, 1e100])
    a2.set_xlabel("Tamaño del espacio $|E|$")
    a2.set_title("(b) Tiempo frente a $|E|$", loc="left")
    _leyenda_figura(fig, ORDEN)
    _guardar(fig, "fig_opt_tiempo")


def fig_memoria(t, m, h, hm):
    fig, ax = plt.subplots(figsize=(ANCHO, 3.0), layout="constrained")
    for a in ORDEN:
        xs = [f["n"] for f in t if m.get(f["instancia"], {}).get(a) is not None]
        ys = [m[f["instancia"]][a] / 2**20 for f in t if m.get(f["instancia"], {}).get(a) is not None]
        ax.scatter(xs, ys, s=9, color=COLOR[a], marker=MARCA[a], alpha=0.75, lw=0)
        hx = [f["n"] for f in h if hm.get(f["instancia"], {}).get(a) is not None]
        hy = [hm[f["instancia"]][a] / 2**20 for f in h if hm.get(f["instancia"], {}).get(a) is not None]
        ax.scatter(hx, hy, s=14, facecolors="none", edgecolors=COLOR[a], marker=MARCA[a], lw=0.8)
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlabel("Líneas decidibles $n$")
    ax.set_ylabel("Pico de memoria (MiB, tracemalloc)")
    ax.xaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(_coma))
    ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(_coma))
    hs = [Line2D([], [], color=COLOR[a], marker=MARCA[a], ls="", ms=4.5, label=CORTO[a]) for a in ORDEN]
    hs += [
        Line2D([], [], color="0.3", marker="o", ls="", ms=4.5, label="lista real (un hijo)"),
        Line2D([], [], color="0.3", marker="o", mfc="none", ls="", ms=4.5, label="hogar sintético\n(2–8 hijos)"),
    ]
    fig.legend(handles=hs, loc="outside right center", frameon=False, handletextpad=0.3)
    _guardar(fig, "fig_opt_memoria")


def fig_calidad(resumen, t, h):
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(ANCHO, 3.2), layout="constrained", gridspec_kw={"width_ratios": [1, 1.3]})
    algos = ["nsga2", "nsga2_sin_siembra", "voraz"]
    pos = np.arange(len(algos))
    minimo = 1.0
    for desplaz, conjunto, rayado in ((-0.19, t, None), (0.19, h, "////")):
        datos = [
            [hv_ratio(f["corridas"][a]["frente"], f["corridas"]["dp"]["frente"]) for f in conjunto if a in f["corridas"]]
            for a in algos
        ]
        minimo = min(minimo, min(min(d) for d in datos))
        bp = a1.boxplot(datos, positions=pos + desplaz, widths=0.32, patch_artist=True, showfliers=True,
                        flierprops={"marker": ".", "ms": 2.5, "alpha": 0.6}, medianprops={"color": "black", "lw": 1})
        for patch, a in zip(bp["boxes"], algos):
            patch.set_facecolor(COLOR[a])
            patch.set_alpha(0.6)
            if rayado:
                patch.set_hatch(rayado)
                patch.set_edgecolor("0.25")
    a1.axhline(1.0, color=COLOR["dp"], lw=0.9, ls="--")
    a1.text(-0.45, 1.004, "frente exacto (DP) = 1", color=COLOR["dp"], fontsize=6.8, ha="left", va="bottom")
    a1.set_xticks(pos, ["NSGA-II\n(producción)", "NSGA-II\nsin siembra", "Voraz"])
    a1.set_ylabel("Hipervolumen / hipervolumen exacto")
    a1.set_ylim(minimo - 0.03, 1.035)
    a1.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(_coma))
    a1.set_title("(a) Calidad del frente (4 objetivos)", loc="left")
    from matplotlib.patches import Patch

    a1.legend(
        handles=[Patch(facecolor="0.75", edgecolor="0.25", label="174 listas reales"),
                 Patch(facecolor="0.75", edgecolor="0.25", hatch="////", label="24 hogares sintéticos")],
        loc="lower left", frameon=True, framealpha=0.9, edgecolor="none",
    )

    esc = resumen["escenarios"]
    claves = [("ahorrador", "Ahorrador"), ("premium", "Premium"), ("fan", "Fan"), ("presupuesto", "Presupuesto")]
    algos2 = ["dp", "nsga2", "nsga2_sin_siembra", "voraz"]
    ancho = 0.2
    for i, a in enumerate(algos2):
        vals = [esc.get(k, {}).get(a, {}).get("pct") or 0 for k, _ in claves]
        xs = np.arange(len(claves)) + (i - 1.5) * ancho
        a2.bar(xs, vals, width=ancho, color=COLOR[a], label=CORTO[a])
        for x, v in zip(xs, vals):
            if v < 99.95:
                a2.text(x, v + 1, f"{v:.0f}", ha="center", va="bottom", fontsize=6.3)
    a2.set_xticks(np.arange(len(claves)), [c for _, c in claves])
    a2.set_ylabel("Listas en que iguala el óptimo (%)")
    a2.set_ylim(0, 108)
    a2.set_yticks([0, 25, 50, 75, 100])
    a2.legend(loc="upper center", bbox_to_anchor=(0.5, -0.11), frameon=False, ncol=2, columnspacing=0.8, handlelength=1.2)
    a2.set_title("(b) Kit proyectado frente al óptimo", loc="left")
    _guardar(fig, "fig_opt_calidad")


def main() -> int:
    resumen = cargar_json(RESULTADOS / "resumen.json")
    t, m, h, hm = _datos()
    fig_tiempo(t, h)
    fig_memoria(t, m, h, hm)
    fig_calidad(resumen, t, h)
    print("figuras en", FIGURAS)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
