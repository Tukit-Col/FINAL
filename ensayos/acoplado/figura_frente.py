"""fig_frente.pdf desde frente.json."""
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter

AQUI = Path(__file__).resolve().parent
SALIDA = AQUI.parents[2] / "memoria-final/dani-v2-2026-11-13/img/graficas/fig_frente.pdf"
d = json.loads((AQUI / "frente.json").read_text())
f = d["filas"]
coma = FuncFormatter(lambda v, _: f"{v:g}".replace(".", ","))
plt.rcParams.update({"font.size": 8, "axes.spines.top": False, "axes.spines.right": False})
fig, ax = plt.subplots(1, 3, figsize=(11, 3.3))

# (a) lista representativa: NSGA-II, mediana de lineas entre las que usan NSGA-II
cand = sorted((r for r in f if r["metodo"] == "nsga2"), key=lambda r: r["lineas"])
r = cand[len(cand) // 2]
ex = r["frente_exacto"]
a = ax[0]
a.scatter([v[0] / 1000 for v in ex], [v[1] for v in ex], s=40, c=["#e8a33d" if v[3] > 0 else "#bbbbbb" for v in ex], label=f"Exacto ({len(ex)}); naranja: con personaje")
ns = r["frente_nsga_s0"]
a.scatter([v[0] / 1000 for v in ns], [v[1] for v in ns], s=14, facecolors="none", edgecolors="#1b6ca8", label=f"NSGA-II ({len(ns)})")
b = r["frente_b20"]
a.scatter([v[0] / 1000 for v in b], [v[1] for v in b], s=22, marker="x", c="#d1495b", label="PD, barrido de 20 presupuestos")
a.set_xlabel("Costo (miles de COP)"); a.set_ylabel("Fidelidad")
a.xaxis.set_major_formatter(coma); a.yaxis.set_major_formatter(coma)
a.set_title(f"(a) Lista {r['instancia'].replace('|', ' ')}, {r['lineas']} líneas\n(proyección costo-fidelidad de 4 ejes)")
a.legend(frameon=False, fontsize=6.5, loc="lower right")

# (b) tiempo total por lista
a = ax[1]
x = [q["lineas"] for q in f]
a.scatter(x, [q["nsga_s_medio"] for q in f], s=9, c="#1b6ca8", label="NSGA-II: frente + 4 kits")
a.scatter(x, [q["pd_b50"]["s"] for q in f], s=9, c="#d1495b", marker="x", label="PD: barrido de 50 presupuestos")
a.scatter(x, [q["pd4_s"] for q in f], s=9, c="#e0a100", marker="s", label="PD: 4 kits (4 corridas)")
a.scatter(x, [q["pd4d_s"] for q in f], s=9, c="#2a9d5c", marker="^", label="PD 4-D exacta (frente completo)")
a.set_yscale("log"); a.set_xlabel("Líneas decidibles"); a.set_ylabel("Segundos por lista")
a.set_title("(b) Tiempo por lista (174 listas)")
a.set_ylim(1e-5, 1e3); a.legend(frameon=False, fontsize=6.5, loc="upper left")

# (c) hipervolumen relativo
a = ax[2]
def hv(k):
    return [q[k]["hv_rel"] if isinstance(q[k], dict) else q[k] for q in f]
datos = [
    [sum(x["hv_rel"] for x in q["nsga"]) / 3 for q in f],
    [q["pd_b50"]["con_extremos"]["hv_rel"] for q in f],
    [q["pd_b50"]["hv_rel"] for q in f],
    [q["pd4_kits"]["hv_rel"] for q in f],
]
bp = a.boxplot(datos, tick_labels=["NSGA-II", "PD 50 +\nextremos", "PD 50", "PD 4 kits"], patch_artist=True, widths=0.5, flierprops={"markersize": 2})
for p, c in zip(bp["boxes"], ["#1b6ca8", "#e0a100", "#d1495b", "#bbbbbb"]):
    p.set_facecolor(c); p.set_alpha(0.8)
a.yaxis.set_major_formatter(coma); a.set_ylabel("Hipervolumen / exacto (4 ejes)")
a.set_title("(c) Calidad del frente")
fig.tight_layout()
SALIDA.parent.mkdir(parents=True, exist_ok=True)
fig.savefig(SALIDA)
print(SALIDA)
