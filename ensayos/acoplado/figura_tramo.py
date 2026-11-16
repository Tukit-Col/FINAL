"""fig_acoplado.pdf con el tramo largo: izquierda barrido original, derecha las 5 listas mas largas (T hasta 64)."""
import json
import statistics as st
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

AQUI = Path(__file__).resolve().parent
SALIDA = AQUI.parents[1].parent / "memoria-final/dani-v2-2026-11-13/img/graficas/fig_acoplado.pdf"
d = json.loads((AQUI / "resultados.json").read_text())
t = json.loads((AQUI / "tramo_largo.json").read_text())
Ts = [1, 2, 4, 8, 12]
R = [d["resumen"][str(x)] for x in Ts]
AZ, NA = "#1f3a5f", "#b5532a"
plt.rcParams.update({"font.family": "Helvetica", "font.size": 8, "axes.spines.top": False, "axes.spines.right": False})
fig, (a, b) = plt.subplots(1, 2, figsize=(6.6, 2.7))
a.plot(Ts, [r["pd_s_mediana"] for r in R], "o-", color=AZ, label="PD (mediana)")
a.plot(Ts, [r["pd_s_max"] for r in R], "o--", color=AZ, alpha=0.5, label="PD (máximo)")
a.plot(Ts, [r["ns_s_mediana"] for r in R], "s-", color=NA, label="NSGA-II (mediana)")
a.axhline(20, color="gray", lw=0.8, ls=":")
a.text(1.1, 24, "límite 20 s (RNF03)", color="gray", fontsize=7)
a.set(yscale="log", xscale="log", xlabel="Tiendas disponibles $T$ (todas las listas)", ylabel="Tiempo de pared (s)", xticks=Ts)
a.set_xticklabels(Ts)
a.minorticks_off()
a.legend(frameon=False, fontsize=7, loc="center left")

TT = t["config"]["ts"]
F = t["filas"]
def por_t(clave, T):
    return [f[clave] for f in F if f["T"] == T]
pd_med = [st.median(min(x, 20.0) if False else x for x in por_t("pd_s", T)) for T in TT]
for T in TT:
    for f in F:
        if f["T"] == T and f["pd_estado"] == "tiempo":
            b.plot(T, 20, marker="^", color=AZ, ms=3.5, alpha=0.5, ls="none")
b.plot(TT, [max(por_t("pd_s", T)) for T in TT], "o--", color=AZ, alpha=0.5, label="PD (máximo)")
b.plot(TT, [st.median(por_t("pd_s", T)) for T in TT], "o-", color=AZ, label="PD (mediana, triángulos: cortada a 20 s)")
b.plot(TT, [st.median(por_t("ns_s_mediana", T)) for T in TT], "s-", color=NA, label="NSGA-II (mediana de 3 semillas)")
b.axhline(20, color="gray", lw=0.8, ls=":")
b.text(12.5, 28, "límite 20 s (RNF03)", color="gray", fontsize=7)
b.set(yscale="log", xscale="log", xlabel="Tiendas disponibles $T$ (5 listas de 38 a 64 líneas)", xticks=TT, ylim=(0.02, 120))
b.set_xticklabels(TT)
b.minorticks_off()
b.legend(frameon=False, fontsize=6.5, loc="lower right")
fig.tight_layout()
SALIDA.parent.mkdir(parents=True, exist_ok=True)
fig.savefig(SALIDA)
print(SALIDA)
