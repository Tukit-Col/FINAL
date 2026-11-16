"""Sensibilidad de la matriz ATAM (tab:atam, Capitulo V de la memoria v3).

Lee pesos y calificaciones directamente del .tex y prueba si la eleccion de
grano grueso resiste cambios en pesos y calificaciones.
Salidas: docs/informes/calibracion/sensibilidad_atam.{json,pdf} y
tabla_sensibilidad_atam.tex.  Uso: uv run python ensayos/calibracion/sensibilidad_atam.py
"""
import json, re
from pathlib import Path
import numpy as np

RAIZ = Path(__file__).resolve().parents[2]
TEX = RAIZ.parent / "memoria-final/v3-2026-11-14/Memoria_Tukit_v3.tex"
SAL = RAIZ / "docs/informes/calibracion"
ALTS = ["Monolito", "Grano fino", "Grano grueso"]
ELEGIDA = 2
N_PERFILES, SEMILLA = 10_000, 20261115
CONCENTRACIONES = [20, 50, 200]   # alfa = c * w; c=50 es la principal (sd de un peso de 15 % ~ 5 pp)
CONC_PRINCIPAL = 50


def leer_matriz():
    t = TEX.read_text(encoding="utf-8")
    i = t.index(r"\label{tab:atam}")
    bloque = t[i:t.index(r"\end{tabularx}", i)]
    crit, w, R = [], [], []
    for lin in bloque.splitlines():
        m = re.match(r"(.+?)\s*&\s*(\d+)\\,\\%\s*&\s*(\d)\s*&\s*(\d)\s*&\s*(\d)\s*\\\\", lin.strip())
        if m:
            crit.append(re.sub(r"\s*\(RNF[^)]*\)", "", m.group(1)).strip())
            w.append(int(m.group(2)) / 100)
            R.append([int(m.group(k)) for k in (3, 4, 5)])
    w, R = np.array(w), np.array(R, float)
    assert len(crit) == 10 and abs(w.sum() - 1) < 1e-9
    return crit, w, R


def puntaje(w, R):
    return w @ R


def ganadores(P):  # P: (n, 3) -> indice ganador (empates a favor de menor indice no ocurren en continuo)
    return P.argmax(axis=1)


def main():
    crit, w, R = leer_matriz()
    base = puntaje(w, R)
    assert np.allclose(np.round(base, 2), [2.82, 3.44, 3.91]), base
    rivales = [0, 1]
    out = {"criterios": crit, "pesos": w.tolist(), "calificaciones": R.tolist(),
           "alternativas": ALTS, "puntaje_base": base.tolist(),
           "margen_base_sobre_segunda": float(base[ELEGIDA] - base[1])}

    # (a) un peso a la vez
    a = []
    for k, c in enumerate(crit):
        fila = {"criterio": c}
        for f in (-0.5, -0.25, 0.25, 0.5):
            w2 = w.copy(); w2[k] *= 1 + f; w2 /= w2.sum()
            p = puntaje(w2, R)
            fila[f"{int(f*100):+d}%"] = {"peso_nuevo": float(w2[k]), "puntajes": p.tolist(),
                                        "ganador": ALTS[int(p.argmax())],
                                        "margen_vs_segunda": float(p[ELEGIDA] - np.delete(p, ELEGIDA).max())}
        a.append(fila)
    out["a_un_peso"] = a
    out["a_gana_grueso"] = f"{sum(f[k]['ganador']=='Grano grueso' for f in a for k in f if k!='criterio')} de {len(a)*4}"

    # (b) Dirichlet
    rng = np.random.default_rng(SEMILLA)
    b = {}
    for c in CONCENTRACIONES:
        W = rng.dirichlet(c * w, N_PERFILES)
        g = ganadores(W @ R)
        b[str(c)] = {"fraccion": {ALTS[i]: float((g == i).mean()) for i in range(3)},
                     "sd_peso_15pct": float(np.sqrt(.15 * .85 / (c + 1)))}
    # concentracion muy baja como estres: pesos casi arbitrarios
    W = rng.dirichlet(np.ones(10), N_PERFILES)
    g = ganadores(W @ R)
    b["uniforme_sin_informacion"] = {"fraccion": {ALTS[i]: float((g == i).mean()) for i in range(3)}}
    out["b_dirichlet"] = {"n_perfiles": N_PERFILES, "semilla": SEMILLA, "principal": CONC_PRINCIPAL, "resultados": b}

    # (c) calificaciones
    c1 = []
    for k in range(10):
        for j in range(3):
            for d in (-1, 1):
                R2 = R.copy(); R2[k, j] = np.clip(R2[k, j] + d, 1, 5)
                if R2[k, j] == R[k, j]:
                    continue
                p = puntaje(w, R2)
                c1.append({"criterio": crit[k], "alternativa": ALTS[j], "delta": d,
                           "ganador": ALTS[int(p.argmax())],
                           "margen": float(p[ELEGIDA] - np.delete(p, ELEGIDA).max())})
    out["c_una_a_la_vez"] = {"casos": len(c1), "gana_grueso": sum(x["ganador"] == "Grano grueso" for x in c1),
                             "cambian_ganador": [x for x in c1 if x["ganador"] != "Grano grueso"],
                             "peor_margen": min(c1, key=lambda x: x["margen"])}
    R2 = R.copy(); R2[:, ELEGIDA] = np.clip(R2[:, ELEGIDA] - 1, 1, 5)
    for j in rivales: R2[:, j] = np.clip(R2[:, j] + 1, 1, 5)
    p = puntaje(w, R2)
    R3 = R.copy(); R3[:, ELEGIDA] = np.clip(R3[:, ELEGIDA] - 1, 1, 5)
    p3 = puntaje(w, R3)
    # numero minimo de celdas (+-1 adversarias) para que cambie el ganador: voraz sobre ganancia ponderada
    def minimo_celdas(rival):
        gan = []
        for k in range(10):
            gan.append((w[k] * (1 if R[k, ELEGIDA] > 1 else 0) + w[k] * (1 if R[k, rival] < 5 else 0), k))
        # cada celda ajustable por 1 punto: bajar la elegida o subir el rival
        pasos = []
        for k in range(10):
            if R[k, ELEGIDA] > 1: pasos.append(w[k])
            if R[k, rival] < 5: pasos.append(w[k])
        pasos.sort(reverse=True)
        d = base[ELEGIDA] - base[rival]; n = 0
        for s in pasos:
            if d < 0: break
            d -= s; n += 1
        return n, len(pasos)
    out["c_peor_caso"] = {
        "todas_a_la_vez_elegida_menos1_rivales_mas1": {"puntajes": p.tolist(), "ganador": ALTS[int(p.argmax())]},
        "solo_elegida_menos1": {"puntajes": p3.tolist(), "ganador": ALTS[int(p3.argmax())]},
        "min_celdas_para_que_gane_grano_fino": minimo_celdas(1),
        "min_celdas_para_que_gane_monolito": minimo_celdas(0)}
    # ruido aleatorio en calificaciones
    rr = rng.integers(-1, 2, size=(N_PERFILES, 10, 3))
    Rn = np.clip(R[None] + rr, 1, 5)
    g = (np.einsum("k,nkj->nj", w, Rn)).argmax(axis=1)
    out["c_ruido_aleatorio"] = {"descripcion": "cada celda +-1 o 0 con prob 1/3, recortado a 1..5",
                                "fraccion": {ALTS[i]: float((g == i).mean()) for i in range(3)}}
    # ambos a la vez: pesos Dirichlet y ruido
    W = rng.dirichlet(CONC_PRINCIPAL * w, N_PERFILES)
    g = np.einsum("nk,nkj->nj", W, Rn).argmax(axis=1)
    out["c_pesos_y_ruido"] = {"fraccion": {ALTS[i]: float((g == i).mean()) for i in range(3)}}

    # (d) punto de cruce: w_k' con el resto reescalado proporcionalmente
    d = []
    for k, c in enumerate(crit):
        fila = {"criterio": c, "peso": float(w[k])}
        for r in rivales:
            # f(x)=score_elegida-score_r con peso x en k; lineal en x
            def f(x):
                resto = (1 - x) / (1 - w[k])
                pe = x * R[k, ELEGIDA] + resto * (base[ELEGIDA] - w[k] * R[k, ELEGIDA])
                pr = x * R[k, r] + resto * (base[r] - w[k] * R[k, r])
                return pe - pr
            f0, f1 = f(0.0), f(1.0)
            if f0 * f1 < 0:
                x = f0 / (f0 - f1)
                fila[ALTS[r]] = {"cruce": float(x), "cambio_pp": float((x - w[k]) * 100),
                                 "cambio_relativo": float(x / w[k] - 1)}
            else:
                fila[ALTS[r]] = None  # no existe cruce con peso en [0,1]
        cruces = [(abs(v["cambio_relativo"]), n, v) for n, v in fila.items() if isinstance(v, dict)]
        fila["mas_cercano"] = min(cruces, key=lambda t: t[0])[1:] and {"rival": min(cruces, key=lambda t: t[0])[1], **min(cruces, key=lambda t: t[0])[2]} if cruces else None
        d.append(fila)
    out["d_cruce"] = d
    ordenados = sorted([x for x in d if x["mas_cercano"]], key=lambda x: abs(x["mas_cercano"]["cambio_relativo"]))
    out["d_mas_sensibles"] = [x["criterio"] for x in ordenados[:3]]

    SAL.mkdir(parents=True, exist_ok=True)
    (SAL / "sensibilidad_atam.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    tabla_tex(out, crit, w, d)
    grafica(out, crit, w, d)
    resumen(out)


def pc(x, dec=1):
    return f"{x*100:.{dec}f}".replace(".", ",")


def tabla_tex(out, crit, w, d):
    L = [r"\begin{tabular}{@{}lrlrr@{}}", r"\toprule",
         r"\textbf{Criterio} & \textbf{Peso} & \textbf{Rival que alcanza} & \textbf{Peso de cruce} & \textbf{Cambio} \\",
         r"\midrule"]
    for x in sorted(d, key=lambda x: abs(x["mas_cercano"]["cambio_relativo"]) if x["mas_cercano"] else 9):
        m = x["mas_cercano"]
        nom = x["criterio"].replace("%", r"\%")
        if m:
            L.append(f"{nom} & {pc(x['peso'],0)}\\,\\% & {m['rival']} & {pc(m['cruce'],0)}\\,\\% & "
                     f"{'+' if m['cambio_pp']>=0 else '$-$'}{pc(abs(m['cambio_pp'])/100,0)}\\,pp \\\\")
        else:
            L.append(f"{nom} & {pc(x['peso'],0)}\\,\\% & ninguno & --- & --- \\\\")
    L += [r"\bottomrule", r"\end{tabular}"]
    (SAL / "tabla_sensibilidad_atam.tex").write_text("\n".join(L) + "\n", encoding="utf-8")


def grafica(out, crit, w, d):
    import matplotlib; matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(1, 2, figsize=(11, 4.6))
    xs = np.linspace(0, 1, 2)
    ordenados = sorted(range(10), key=lambda k: abs(d[k]["mas_cercano"]["cambio_pp"]) if d[k]["mas_cercano"] else 99)
    y = np.arange(10)
    ax[0].barh(y, [abs(d[k]["mas_cercano"]["cambio_pp"]) if d[k]["mas_cercano"] else 0 for k in ordenados], color="#1B5E8C")
    ax[0].set_yticks(y); ax[0].set_yticklabels([crit[k][:38] for k in ordenados], fontsize=7)
    ax[0].invert_yaxis(); ax[0].set_xlabel("Cambio de peso (pp) para que otra alternativa empate")
    ax[0].set_title("Margen: punto de cruce por criterio", fontsize=9)
    b = out["b_dirichlet"]["resultados"]
    claves = [str(c) for c in CONCENTRACIONES] + ["uniforme_sin_informacion"]
    etq = [f"c={c}" for c in CONCENTRACIONES] + ["Dirichlet(1)"]
    bot = np.zeros(len(claves)); cols = ["#9aa5b1", "#c9a227", "#1B5E8C"]
    for i, n in enumerate(ALTS):
        v = np.array([b[c]["fraccion"][n] for c in claves]) * 100
        ax[1].bar(etq, v, bottom=bot, label=n, color=cols[i]); bot += v
    ax[1].set_ylabel("% de 10.000 perfiles de pesos"); ax[1].legend(fontsize=7)
    ax[1].set_title("Quién gana con pesos aleatorios", fontsize=9)
    fig.tight_layout(); fig.savefig(SAL / "sensibilidad_atam.pdf"); plt.close(fig)


def resumen(o):
    print("base", np.round(o["puntaje_base"], 2), "margen", round(o["margen_base_sobre_segunda"], 2))
    print("a:", o["a_gana_grueso"])
    for c, v in o["b_dirichlet"]["resultados"].items(): print("b", c, {k: round(x, 4) for k, x in v["fraccion"].items()})
    print("c una a una:", o["c_una_a_la_vez"]["gana_grueso"], "de", o["c_una_a_la_vez"]["casos"],
          "| cambian:", [(x["criterio"][:30], x["alternativa"], x["delta"], x["ganador"]) for x in o["c_una_a_la_vez"]["cambian_ganador"]])
    print("c peor caso:", o["c_peor_caso"])
    print("c ruido:", o["c_ruido_aleatorio"]["fraccion"], "pesos+ruido:", o["c_pesos_y_ruido"]["fraccion"])
    for x in o["d_cruce"]:
        m = x["mas_cercano"]; print("d", x["criterio"][:45], x["peso"], m and (m["rival"], round(m["cruce"], 3), round(m["cambio_pp"], 1)))


if __name__ == "__main__":
    main()
