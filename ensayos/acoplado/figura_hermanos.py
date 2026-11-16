"""fig_hermanos.pdf: tiempo y estados frente al numero de hijos (PD vs NSGA-II), escala log."""
import json
import statistics as st
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

AQUI = Path(__file__).resolve().parent
SALIDA = AQUI.parents[1].parent / "memoria-final/dani-v2-2026-11-13/img/graficas/fig_hermanos.pdf"
d = json.loads((AQUI / "hermanos.json").read_text())
Ks = sorted({f["hijos"] for f in d["filas"]})
por = {k: [f for f in d["filas"] if f["hijos"] == k] for k in Ks}
pd_s = [st.median(f["pd_pres"]["s"] for f in por[k]) for k in Ks]
pd_smax = [max(f["pd_pres"]["s"] for f in por[k]) for k in Ks]
ns_s = [st.median(x["s"] for f in por[k] for x in f["ns"]) for k in Ks]
pd_e = [st.median(f["pd_pres"]["estados"] for f in por[k]) for k in Ks]
pd_emax = [max(f["pd_pres"]["estados"] for f in por[k]) for k in Ks]
ns_e = [st.median(x["evals"] for f in por[k] for x in f["ns"]) for k in Ks]
fallo = [sum(f["pd_pres"]["estado"] not in ("ok", "infactible") for f in por[k]) for k in Ks]
plt.rcParams.update({"font.family": "Helvetica", "font.size": 8, "axes.spines.top": False, "axes.spines.right": False})
fig, (a, b) = plt.subplots(1, 2, figsize=(6.4, 2.7))
a.plot(Ks, pd_s, "o-", color="#1f3a5f", label="PD (mediana)")
a.plot(Ks, pd_smax, "o--", color="#1f3a5f", alpha=0.5, label="PD (máximo)")
a.plot(Ks, ns_s, "s-", color="#b5532a", label="NSGA-II (mediana)")
a.axhline(20, color="gray", lw=0.8, ls=":")
a.text(2.05, 26, "límite 20 s (RNF03)", color="gray", fontsize=7)
a.set(yscale="log", xlabel="Hijos en el hogar", ylabel="Tiempo de pared (s)", xticks=Ks, ylim=(0.01, 80))
a.legend(frameon=False, fontsize=7, loc="lower right")
b.plot(Ks, pd_e, "o-", color="#1f3a5f", label="PD estados (mediana)")
b.plot(Ks, pd_emax, "o--", color="#1f3a5f", alpha=0.5, label="PD estados (máximo)")
b.plot(Ks, ns_e, "s-", color="#b5532a", label="NSGA-II evaluaciones")
for k, e, n in zip(Ks, pd_emax, fallo):
    if n:
        b.annotate(f"{n}/{len(por[k])}", (k, e), textcoords="offset points", xytext=(0, 5), ha="center", fontsize=6.5, color="#1f3a5f")
b.set(yscale="log", xlabel="Hijos en el hogar", ylabel="Estados / evaluaciones", xticks=Ks, ylim=(1e3, 5e7))
b.legend(frameon=False, fontsize=7, loc="center right", bbox_to_anchor=(1.0, 0.45))
fig.tight_layout()
SALIDA.parent.mkdir(parents=True, exist_ok=True)
fig.savefig(SALIDA)
print(SALIDA)
