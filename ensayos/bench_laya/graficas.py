"""Tablas (markdown) y graficas (PNG) a partir de `resultados.json.gz`.

Escribe `tablas.md`, `fig_optimo.png` y `fig_frente_<lista>.png` en
`docs/informes/benchmark-laya/`, junto al informe que las cita. El texto del
informe se escribe a mano encima de estas cifras.
"""

from __future__ import annotations

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from comun import SALIDA, cargar_json  # noqa: E402

AZUL, NARANJA, GRIS, TINTA, TINTA2 = "#2a78d6", "#eb6834", "#9a988e", "#1f1f1e", "#5f5e58"
ESCENARIOS = ("ahorrador", "premium", "fan", "presupuesto")
TITULO = {
    "ahorrador": "Ahorrador (más barato)",
    "premium": "Premium (mejor marca)",
    "fan": "Fan (personaje)",
    "presupuesto": "Presupuesto (calidad que cabe)",
}
ORDEN = [
    "optimo",
    "nsga2",
    "nsga2_frente",
    "heuristica",
    "reglas_juez_perfecto",
    "laya_A",
    "laya_B",
    "laya_C",
    "laya_D",
    "azar",
]
NOMBRE = {
    "optimo": "Óptimo exacto",
    "nsga2": "NSGA-II (producción)",
    "nsga2_frente": "NSGA-II, mejor punto del frente",
    "heuristica": "Regla simple del proyecto",
    "reglas_juez_perfecto": "Kits de reglas + juez perfecto",
    "laya_A": "Laya A: línea aislada",
    "laya_B": "Laya B: lista completa",
    "laya_C": "Laya C: secuencial",
    "laya_D": "Laya D: juez de kits",
    "azar": "Al azar",
}


def color(comp: str) -> str:
    if comp.startswith("nsga2"):
        return AZUL
    if comp.startswith("laya"):
        return NARANJA
    return GRIS


def _estilo(ax):
    for lado in ("top", "right"):
        ax.spines[lado].set_visible(False)
    for lado in ("left", "bottom"):
        ax.spines[lado].set_color("#d6d4cc")
    ax.tick_params(colors=TINTA2, labelsize=8)


def fig_optimo(resumen: dict) -> None:
    fig, ejes = plt.subplots(1, 4, figsize=(16, 4.4), sharex=True)
    for ax, esc in zip(ejes, ESCENARIOS, strict=True):
        comps = [c for c in ORDEN if f"{esc}/{c}" in resumen and c != "optimo"]
        vals = [resumen[f"{esc}/{c}"]["optimo_pct"] for c in comps]
        y = range(len(comps))[::-1]
        ax.barh(list(y), vals, color=[color(c) for c in comps], height=0.6, edgecolor="white", linewidth=2)
        for yi, v in zip(y, vals, strict=True):
            ax.text(v + 1.5, yi, f"{v:.0f}%", va="center", fontsize=8, color=TINTA)
        ax.set_yticks(list(y))
        ax.set_yticklabels(
            [NOMBRE[c] for c in comps] if ax is ejes[0] else [NOMBRE[c] for c in comps], fontsize=8
        )
        ax.set_xlim(0, 112)
        ax.set_title(TITULO[esc], fontsize=10, color=TINTA, loc="left")
        ax.xaxis.grid(True, color="#ecebe6", linewidth=0.8)
        ax.set_axisbelow(True)
        _estilo(ax)
    fig.suptitle(
        "Porcentaje de listas en que cada competidor iguala el kit óptimo",
        fontsize=12,
        color=TINTA,
        x=0.01,
        ha="left",
    )
    fig.tight_layout()
    fig.savefig(SALIDA / "fig_optimo.png", dpi=160)
    plt.close(fig)


def fig_frente(lista: str, datos: dict) -> None:
    esc = next(
        e
        for e in cargar_json("escenarios.json")["escenarios"]
        if e["instancia"] == lista and e["escenario"] == "presupuesto"
    )
    nsga = next(
        f
        for f in cargar_json("nsga.json.gz")["filas"]
        if f["instancia"] == lista and f["escenario"] == "presupuesto" and f["semilla"] == 0
    )
    fig, ax = plt.subplots(figsize=(7.5, 4.8))
    fr = sorted(nsga["frente"], key=lambda p: p["costo"])
    # El frente tiene 4 objetivos; en el plano costo-fidelidad se distinguen los puntos
    # que tambien son de Pareto en 2D de los que solo lo son por otro eje (personaje).
    en_2d = [
        p
        for p in fr
        if not any(
            q["costo"] <= p["costo"]
            and q["fidelidad"] >= p["fidelidad"]
            and (q["costo"], q["fidelidad"]) != (p["costo"], p["fidelidad"])
            for q in fr
        )
    ]
    resto = [p for p in fr if p not in en_2d]
    ax.scatter(
        [p["costo"] / 1000 for p in resto],
        [p["fidelidad"] for p in resto],
        s=30,
        color="#b7d3f6",
        edgecolor="white",
        linewidth=1.5,
        label="Frente: puntos que solo ganan en personaje",
        zorder=2,
    )
    ax.scatter(
        [p["costo"] / 1000 for p in en_2d],
        [p["fidelidad"] for p in en_2d],
        s=36,
        color=AZUL,
        edgecolor="white",
        linewidth=1.5,
        label="Frente del NSGA-II (costo vs. fidelidad)",
        zorder=3,
    )
    ax.axvline(esc["presupuesto"] / 1000, color=TINTA2, linestyle="--", linewidth=1)
    ax.text(esc["presupuesto"] / 1000, ax.get_ylim()[1], "  presupuesto", color=TINTA2, fontsize=8, va="top")
    marcas = {"laya_A": "o", "laya_B": "s", "laya_C": "^", "laya_D": "D"}
    filas = [f for f in datos["filas"] if f["instancia"] == lista and f["escenario"] == "presupuesto"]
    for f in filas:
        c = f["competidor"]
        o = f["objetivos"]
        if c in marcas:
            ax.scatter(
                o["costo"] / 1000,
                o["fidelidad"],
                marker=marcas[c],
                s=70,
                color=NARANJA,
                edgecolor="white",
                linewidth=1.5,
                zorder=4,
            )
            ax.annotate(
                f"Laya {c[-1]}",
                (o["costo"] / 1000, o["fidelidad"]),
                textcoords="offset points",
                xytext=(6, -10),
                fontsize=8,
                color=TINTA,
            )
        if c in ("optimo", "nsga2"):
            ax.scatter(
                o["costo"] / 1000,
                o["fidelidad"],
                marker="*" if c == "optimo" else "P",
                s=140,
                color=TINTA if c == "optimo" else AZUL,
                edgecolor="white",
                linewidth=1.5,
                zorder=5,
            )
            ax.annotate(
                "Óptimo con presupuesto" if c == "optimo" else "Recomendado hoy",
                (o["costo"] / 1000, o["fidelidad"]),
                textcoords="offset points",
                xytext=(6, 6),
                fontsize=8,
                color=TINTA,
            )
    ax.set_xlabel("Costo del kit (miles de pesos)", fontsize=9, color=TINTA2)
    ax.set_ylabel("Fidelidad de marca (0 a 1)", fontsize=9, color=TINTA2)
    ax.set_title(
        f"Lista {lista}: frente del NSGA-II y kits de Laya con presupuesto",
        fontsize=11,
        color=TINTA,
        loc="left",
    )
    ax.grid(True, color="#ecebe6", linewidth=0.8)
    ax.set_axisbelow(True)
    ax.legend(frameon=False, fontsize=8, loc="lower right")
    _estilo(ax)
    fig.tight_layout()
    fig.savefig(SALIDA / f"fig_frente_{lista.replace('|', '_')}.png", dpi=160)
    plt.close(fig)


def _f(v, fmt="{:.1f}"):
    return "—" if v is None else fmt.format(v)


def tablas(resumen: dict) -> str:
    out = []
    cols = {
        "ahorrador": [
            ("optimo_pct", "Iguala óptimo", "{:.0f}%"),
            ("brecha_costo_pct", "Sobrecosto medio", "{:.1f}%"),
            ("dominado_por_frente", "Dominado por el frente", None),
        ],
        "premium": [
            ("optimo_pct", "Iguala óptimo", "{:.0f}%"),
            ("brecha_fidelidad", "Fidelidad perdida (0 a 1)", "{:.3f}"),
            ("costo_vs_optimo_pct", "Costo vs. óptimo", "{:+.1f}%"),
            ("dominado_por_frente", "Dominado por el frente", None),
        ],
        "fan": [
            ("optimo_pct", "Iguala óptimo", "{:.0f}%"),
            ("cobertura_personaje_vs_optimo", "Personaje logrado vs. óptimo", None),
            ("dominado_por_frente", "Dominado por el frente", None),
        ],
        "presupuesto": [
            ("cabe", "Cabe en el presupuesto", None),
            ("puntaje", "Calidad lograda vs. óptimo", None),
            ("fidelidad_si_cabe", "Fidelidad cuando cabe", "{:.3f}"),
            ("exceso_pct_mediana", "Exceso mediano", "{:.1f}%"),
            ("optimo_pct", "Iguala óptimo", "{:.0f}%"),
        ],
    }
    for esc in ESCENARIOS:
        out.append(f"### {TITULO[esc]}\n")
        cab = ["Competidor", "n"] + [c[1] for c in cols[esc]]
        out.append("| " + " | ".join(cab) + " |")
        out.append("|" + "---|" * len(cab))
        for comp in ORDEN:
            r = resumen.get(f"{esc}/{comp}")
            if not r:
                continue
            celdas = [NOMBRE[comp], str(r["n"])]
            for k, _, fmt in cols[esc]:
                v = r.get(k)
                if fmt is None:
                    celdas.append(_f(None if v is None else 100 * v, "{:.0f}%"))
                else:
                    celdas.append(_f(v, fmt))
            out.append("| " + " | ".join(celdas) + " |")
        out.append("")
    return "\n".join(out)


def main() -> int:
    datos = cargar_json("resultados.json.gz", SALIDA)
    resumen = datos["resumen"]
    fig_optimo(resumen)
    (SALIDA / "tablas.md").write_text(tablas(resumen), encoding="utf-8")
    import sys

    for lista in sys.argv[1:]:
        fig_frente(lista, datos)
    print("listo")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
