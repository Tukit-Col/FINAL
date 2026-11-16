"""fig_acoplado.pdf: tiempo y estados frente a T (PD vs NSGA-II), escala log."""
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

AQUI = Path(__file__).resolve().parent
SALIDA = AQUI.parents[1].parent / "memoria-final/dani-v2-2026-11-13/img/graficas/fig_acoplado.pdf"
d = json.loads((AQUI / "resultados.json").read_text())
Ts = [1, 2, 4, 8, 12]
R = [d["resumen"][str(t)] for t in Ts]
plt.rcParams.update({"font.family": "Helvetica", "font.size": 8, "axes.spines.top": False, "axes.spines.right": False})
fig, (a, b) = plt.subplots(1, 2, figsize=(6.2, 2.6))
a.plot(Ts, [r["pd_s_mediana"] for r in R], "o-", color="#1f3a5f", label="PD (mediana)")
a.plot(Ts, [r["pd_s_max"] for r in R], "o--", color="#1f3a5f", alpha=0.5, label="PD (máximo)")
a.plot(Ts, [r["ns_s_mediana"] for r in R], "s-", color="#b5532a", label="NSGA-II (mediana)")
a.axhline(20, color="gray", lw=0.8, ls=":")
a.text(1.1, 24, "límite 20 s (RNF03)", color="gray", fontsize=7)
a.set(yscale="log", xscale="log", xlabel="Tiendas disponibles $T$", ylabel="Tiempo de pared (s)", xticks=Ts)
a.set_xticklabels(Ts)
a.legend(frameon=False, fontsize=7, loc="center left")
b.plot(Ts, [r["pd_estados_mediana"] for r in R], "o-", color="#1f3a5f", label="PD estados (mediana)")
b.plot(Ts, [r["pd_estados_max"] for r in R], "o--", color="#1f3a5f", alpha=0.5, label="PD estados (máximo)")
b.plot(Ts, [r["ns_evals_mediana"] for r in R], "s-", color="#b5532a", label="NSGA-II evaluaciones")
b.set(yscale="log", xscale="log", xlabel="Tiendas disponibles $T$", ylabel="Estados / evaluaciones", xticks=Ts)
b.set_xticklabels(Ts)
b.legend(frameon=False, fontsize=7, loc="center left")
fig.tight_layout()
SALIDA.parent.mkdir(parents=True, exist_ok=True)
fig.savefig(SALIDA)
print(SALIDA)
