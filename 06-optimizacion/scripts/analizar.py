"""Agrega las corridas de `correr.py` en las tablas de RESULTADOS.md.

    python analizar.py   -> ../resultados/resumen.json y ../resultados/tablas.md

Calidad, siempre contra el frente exacto de la programacion dinamica (que se
verifica igual a la fuerza bruta en todas las instancias donde esta corre):

- `hv_ratio`   hipervolumen del frente / hipervolumen del frente exacto, en el
               espacio de 4 objetivos normalizado por instancia (ideal y nadir
               del frente exacto, punto de referencia 1,1; los ejes sin rango se
               descartan). 1 = el frente cubre todo lo que cubre el exacto.
- `cobertura`  fraccion de los puntos del frente exacto que el algoritmo encontro.
- `precision`  fraccion de los puntos del algoritmo que son Pareto-optimos.
- `exacto`     el frente es identico al exacto.
- Escenarios   el kit que se proyecta del frente iguala el optimo exacto
               de `escenarios.json` (mismas reglas que el benchmark Laya y que
               `_proyectar` / A tu Medida de produccion).
"""

from __future__ import annotations

import statistics as st
from collections import defaultdict

import numpy as np
from pymoo.indicators.hv import HV

from tukit_final import RESULTADOS, cargar_json, escenarios, guardar_json

ALGOS = ["enumeracion", "dp", "nsga2", "nsga2_sin_siembra", "voraz"]
NOMBRES = {
    "enumeracion": "Enumeración exacta",
    "dp": "Programación dinámica",
    "nsga2": "NSGA-II (producción)",
    "nsga2_sin_siembra": "NSGA-II sin siembra",
    "voraz": "Voraz (heurística + escalera)",
}
EPS = 1e-9


def _clave(v):
    return (int(v[0]), round(v[1], 6), round(v[2], 6), round(v[3], 6))


def hv_ratio(aprox: list, exacto: list) -> float:
    E = np.array([[v[0], -v[1], -v[2], -v[3]] for v in exacto], dtype=float)
    A = np.array([[v[0], -v[1], -v[2], -v[3]] for v in aprox], dtype=float) if aprox else np.empty((0, 4))
    ideal, nadir = E.min(axis=0), E.max(axis=0)
    ejes = nadir - ideal > EPS
    if not ejes.any():
        return 1.0 if any(_clave(a) == _clave(exacto[0]) for a in aprox) else 0.0
    En = (E[:, ejes] - ideal[ejes]) / (nadir - ideal)[ejes]
    An = (A[:, ejes] - ideal[ejes]) / (nadir - ideal)[ejes] if len(A) else A
    ind = HV(ref_point=np.full(int(ejes.sum()), 1.1))
    h_e = ind(En)
    return float(ind(An) / h_e) if len(An) and h_e > 0 else 0.0


def calidad(aprox: list, exacto: list) -> dict:
    ce = {_clave(v) for v in exacto}
    ca = {_clave(v) for v in aprox}
    inter = len(ce & ca)
    return {
        "hv_ratio": hv_ratio(aprox, exacto),
        "cobertura": inter / len(ce),
        "precision": inter / len(ca) if ca else 0.0,
        "exacto": float(ce == ca),
        "puntos": len(ca),
        "puntos_exacto": len(ce),
    }


# ------------------------------------------------------------ proyecciones


def _surtibles(fr):
    tope = max(v[2] for v in fr)
    return [v for v in fr if v[2] == tope]


def proyectar(fr: list, escenario: str, presupuesto: int | None = None):
    if not fr:
        return None
    s = _surtibles(fr)
    if escenario == "ahorrador":
        return min(s, key=lambda v: (v[0], -v[2], -v[1]))
    if escenario == "premium":
        return max(s, key=lambda v: (v[1], -v[0], v[2]))
    if escenario == "fan":
        return max(s, key=lambda v: (v[3], -v[0], v[1]))
    caben = [v for v in s if v[0] <= presupuesto]
    return max(caben, key=lambda v: (v[1], -v[0], v[2])) if caben else None


def iguala(v, esc) -> bool:
    if v is None:
        return False
    o = esc["objetivos_optimo"]
    e = esc["escenario"]
    if e == "ahorrador":
        return v[0] <= o["costo"]
    if e == "premium":
        return v[1] >= o["fidelidad"] - EPS
    if e == "fan":
        return v[3] >= o["personaje"] - EPS
    return v[0] <= esc["presupuesto"] and v[1] >= o["fidelidad"] - EPS


# ------------------------------------------------------------------ resumen


def _pct(xs):
    return round(100 * st.mean(xs), 1) if xs else None


def _q(xs, q):
    return float(np.percentile(xs, q)) if xs else None


def resumir_tiempo(filas, memoria_por: dict) -> dict:
    por_algo = defaultdict(lambda: defaultdict(list))
    verif = {"instancias_comparadas": 0, "dp_igual_enumeracion": 0}
    for f in filas:
        if f["prefs_tag"] != "sin_preferencias" or "dp" not in f["corridas"]:
            continue
        exacto = f["corridas"]["dp"]["frente"]
        if "enumeracion" in f["corridas"]:
            verif["instancias_comparadas"] += 1
            en = {_clave(v) for v in f["corridas"]["enumeracion"]["frente"]}
            verif["dp_igual_enumeracion"] += int(en == {_clave(v) for v in exacto})
        mem = memoria_por.get(f["instancia"], {})
        for a, c in f["corridas"].items():
            d = por_algo[a]
            d["segundos"].append(c["segundos"])
            d["n"].append(f["n"])
            if a in mem and mem[a] is not None:
                d["pico_mib"].append(mem[a] / 2**20)
            for k, v in calidad(c["frente"], exacto).items():
                d[k].append(v)
    salida = {}
    for a in ALGOS:
        d = por_algo.get(a)
        if not d:
            continue
        salida[a] = {
            "instancias": len(d["segundos"]),
            "seg_media": st.mean(d["segundos"]),
            "seg_mediana": st.median(d["segundos"]),
            "seg_p95": _q(d["segundos"], 95),
            "seg_max": max(d["segundos"]),
            "seg_total": sum(d["segundos"]),
            "mib_mediana": st.median(d["pico_mib"]) if d["pico_mib"] else None,
            "mib_max": max(d["pico_mib"]) if d["pico_mib"] else None,
            "hv_media": st.mean(d["hv_ratio"]),
            "hv_min": min(d["hv_ratio"]),
            "cobertura_media": st.mean(d["cobertura"]),
            "precision_media": st.mean(d["precision"]),
            "frente_exacto_pct": _pct(d["exacto"]),
            "puntos_media": st.mean(d["puntos"]),
        }
    return {"por_algoritmo": salida, "verificacion_dp": verif}


def resumir_escenarios(filas) -> dict:
    frentes = {(f["instancia"], f["prefs_tag"]): f["corridas"] for f in filas}
    res = defaultdict(lambda: defaultdict(list))
    for esc in escenarios():
        tag = "fan" if esc["escenario"] == "fan" else "sin_preferencias"
        corr = frentes.get((esc["instancia"], tag), {})
        for a in ["dp", "nsga2", "nsga2_sin_siembra", "voraz"]:
            if a in corr:
                v = proyectar(corr[a]["frente"], esc["escenario"], esc.get("presupuesto"))
                res[esc["escenario"]][a].append(float(iguala(v, esc)))
                if esc["escenario"] == "presupuesto":
                    o = esc["objetivos_optimo"]["fidelidad"]
                    cal = (v[1] / o if o else 1.0) if v is not None else 0.0
                    res["presupuesto_calidad"][a].append(cal)
    return {e: {a: {"n": len(xs), "pct": _pct(xs)} for a, xs in d.items()} for e, d in res.items()}


def por_tramos(filas, memoria_por, tramos) -> list[dict]:
    salida = []
    for lo, hi in tramos:
        fila = {"tramo": f"{lo}-{hi}"}
        sel = [f for f in filas if f["prefs_tag"] == "sin_preferencias" and lo <= f["n"] <= hi and f["corridas"]]
        fila["instancias"] = len(sel)
        if not sel:
            continue
        fila["log10_espacio_mediana"] = st.median(f["log10_espacio"] for f in sel)
        for a in ALGOS:
            xs = [f["corridas"][a]["segundos"] for f in sel if a in f["corridas"]]
            ms = [memoria_por.get(f["instancia"], {}).get(a) for f in sel]
            ms = [m / 2**20 for m in ms if m is not None]
            fila[a] = {
                "n": len(xs),
                "seg_mediana": st.median(xs) if xs else None,
                "mib_mediana": st.median(ms) if ms else None,
            }
        ternas = [f["corridas"]["dp"].get("ternas_max_etapa") for f in sel if "dp" in f["corridas"]]
        fila["dp_ternas_max_mediana"] = st.median(ternas) if ternas else None
        salida.append(fila)
    return salida


def semillas(filas_tiempo) -> dict:
    ruta = RESULTADOS / "corridas_semillas.json.gz"
    if not ruta.exists():
        return {}
    exactos = {
        f["instancia"]: f["corridas"]["dp"]["frente"]
        for f in filas_tiempo
        if f["prefs_tag"] == "sin_preferencias" and "dp" in f["corridas"]
    }
    por = defaultdict(lambda: defaultdict(list))
    for f in filas_tiempo:
        if f["prefs_tag"] == "sin_preferencias" and f["instancia"] in exactos:
            for a in ["nsga2", "nsga2_sin_siembra"]:
                if a in f["corridas"]:
                    por[a][f["instancia"]].append(calidad(f["corridas"][a]["frente"], exactos[f["instancia"]]))
    for f in cargar_json(ruta)["filas"]:
        if f["instancia"] not in exactos:
            continue
        for a, c in f["corridas"].items():
            por[a][f["instancia"]].append(calidad(c["frente"], exactos[f["instancia"]]))
    salida = {}
    for a, d in por.items():
        hv = [q["hv_ratio"] for qs in d.values() for q in qs]
        ex = [q["exacto"] for qs in d.values() for q in qs]
        sd = [st.pstdev([q["hv_ratio"] for q in qs]) for qs in d.values() if len(qs) > 1]
        salida[a] = {
            "corridas": len(hv),
            "hv_media": st.mean(hv),
            "hv_min": min(hv),
            "frente_exacto_pct": _pct(ex),
            "hv_desv_entre_semillas_media": st.mean(sd) if sd else None,
            "listas_con_frente_exacto_en_las_5": _pct([float(all(q["exacto"] for q in qs)) for qs in d.values()]),
        }
    return salida


def resumir_hogares() -> dict:
    ruta_t = RESULTADOS / "hogares_tiempo.json.gz"
    if not ruta_t.exists():
        return {}
    filas = cargar_json(ruta_t)["filas"]
    ruta_m = RESULTADOS / "hogares_memoria.json.gz"
    mem = {}
    if ruta_m.exists():
        mem = {f["instancia"]: {a: c["pico_bytes"] for a, c in f["corridas"].items()} for f in cargar_json(ruta_m)["filas"]}
    salida = []
    for f in sorted(filas, key=lambda f: f["n"]):
        exacto = f["corridas"]["dp"]["frente"]
        fila = {
            "instancia": f["instancia"],
            "hijos": f["hijos"],
            "n": f["n"],
            "log10_espacio": f["log10_espacio"],
            "dp_ternas_max": f["corridas"]["dp"].get("ternas_max_etapa"),
        }
        for a, c in f["corridas"].items():
            pico = mem.get(f["instancia"], {}).get(a)
            fila[a] = {
                "segundos": c["segundos"],
                "mib": pico / 2**20 if pico is not None else None,
                "hv_ratio": hv_ratio(c["frente"], exacto),
                "exacto": calidad(c["frente"], exacto)["exacto"],
                "puntos": len(c["frente"]),
            }
        salida.append(fila)
    # Escenarios en hogares: no hay optimo en escenarios.json, asi que el techo es
    # la proyeccion del frente exacto; el tope es la mitad entre Ahorrador y Premium.
    esc = {}
    for a in ["nsga2", "nsga2_sin_siembra", "voraz"]:
        ah, pr, ok, cal = [], [], [], []
        for f in filas:
            E, A = f["corridas"]["dp"]["frente"], f["corridas"][a]["frente"]
            eah, epr = proyectar(E, "ahorrador"), proyectar(E, "premium")
            tope = int(eah[0] + 0.5 * (epr[0] - eah[0]))
            e, x = proyectar(E, "presupuesto", tope), proyectar(A, "presupuesto", tope)
            ah.append(float(proyectar(A, "ahorrador")[0] <= eah[0]))
            pr.append(float(proyectar(A, "premium")[1] >= epr[1] - EPS))
            ok.append(float(x is not None and x[1] >= e[1] - EPS))
            cal.append(x[1] / e[1] if x else 0.0)
        esc[a] = {
            "hogares": len(filas),
            "ahorrador_pct": _pct(ah),
            "premium_pct": _pct(pr),
            "presupuesto_iguala_pct": _pct(ok),
            "presupuesto_calidad_media_pct": round(100 * st.mean(cal), 2),
            "presupuesto_calidad_min_pct": round(100 * min(cal), 2),
        }
    return {"filas": salida, "escenarios_tope_medio": esc}


def ajustes_potencia(filas_tiempo, memoria_por) -> dict:
    """Exponente b de t = a * n^b (minimos cuadrados en log-log) con listas de n >= 15 y hogares."""
    puntos = defaultdict(lambda: {"t": [], "m": []})
    for f in filas_tiempo:
        if f["prefs_tag"] != "sin_preferencias" or f["n"] < 15:
            continue
        for a, c in f["corridas"].items():
            puntos[a]["t"].append((f["n"], c["segundos"]))
            m = memoria_por.get(f["instancia"], {}).get(a)
            if m:
                puntos[a]["m"].append((f["n"], m))
    ruta_t = RESULTADOS / "hogares_tiempo.json.gz"
    ruta_m = RESULTADOS / "hogares_memoria.json.gz"
    if ruta_t.exists():
        for f in cargar_json(ruta_t)["filas"]:
            for a, c in f["corridas"].items():
                puntos[a]["t"].append((f["n"], c["segundos"]))
    if ruta_m.exists():
        for f in cargar_json(ruta_m)["filas"]:
            for a, c in f["corridas"].items():
                if c["pico_bytes"]:
                    puntos[a]["m"].append((f["n"], c["pico_bytes"]))
    salida = {}
    for a, d in puntos.items():
        r = {}
        for k in ("t", "m"):
            if len(d[k]) >= 5:
                x = np.log([p[0] for p in d[k]])
                y = np.log([max(p[1], 1e-9) for p in d[k]])
                b, _ = np.polyfit(x, y, 1)
                r["exponente_tiempo" if k == "t" else "exponente_memoria"] = round(float(b), 2)
                r["puntos_" + k] = len(d[k])
        salida[a] = r
    return salida


def main() -> int:
    t = cargar_json(RESULTADOS / "corridas_tiempo.json.gz")
    ruta_m = RESULTADOS / "corridas_memoria.json.gz"
    memoria_por = {}
    if ruta_m.exists():
        for f in cargar_json(ruta_m)["filas"]:
            if f["prefs_tag"] == "sin_preferencias":
                memoria_por[f["instancia"]] = {a: c["pico_bytes"] for a, c in f["corridas"].items()}
    filas = t["filas"]
    resumen = {
        "entorno": t["entorno"],
        "tope_enumeracion": t["tope_enumeracion"],
        **resumir_tiempo(filas, memoria_por),
        "escenarios": resumir_escenarios(filas),
        "tramos": por_tramos(filas, memoria_por, [(1, 10), (11, 15), (16, 20), (21, 30), (31, 64)]),
        "semillas": semillas(filas),
        "hogares": resumir_hogares(),
        "ajustes_potencia_n": ajustes_potencia(filas, memoria_por),
        "enumeracion_hasta_4096_max_s": max(
            (f["corridas"]["enumeracion"]["segundos"] for f in filas
             if f["prefs_tag"] == "sin_preferencias" and "enumeracion" in f["corridas"] and (f["espacio"] or 0) <= 4096),
            default=None,
        ),
        "instancias": {
            "listas": len({f["instancia"] for f in filas}),
            "con_frente": sum(1 for f in filas if f["prefs_tag"] == "sin_preferencias" and f["corridas"]),
            "nsga_en_produccion": sum(
                1 for f in filas if f["prefs_tag"] == "sin_preferencias" and f["metodo_produccion"] == "nsga2"
            ),
            "n_media": st.mean(f["n"] for f in filas if f["prefs_tag"] == "sin_preferencias"),
            "n_max": max(f["n"] for f in filas),
        },
    }
    guardar_json(RESULTADOS / "resumen.json", resumen)
    print(tablas_md(resumen))
    (RESULTADOS / "tablas.md").write_text(tablas_md(resumen), encoding="utf-8")
    return 0


def _f(x, fmt="{:.3f}"):
    return "—" if x is None else fmt.format(x)


def _seg(x):
    if x is None:
        return "—"
    if x < 1e-3:
        return f"{x * 1e6:.0f} µs"
    if x < 1:
        return f"{x * 1e3:.1f} ms"
    return f"{x:.2f} s"


def tablas_md(r: dict) -> str:
    lin = ["### Resumen por algoritmo (listas reales, sin preferencias)", ""]
    lin.append(
        "| Algoritmo | Instancias | Tiempo mediano | Tiempo p95 | Tiempo máx. | Memoria pico mediana | "
        "HV / HV exacto (media) | HV mín. | Frente exacto | Cobertura del frente exacto |"
    )
    lin.append("|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
    for a in ALGOS:
        s = r["por_algoritmo"].get(a)
        if not s:
            continue
        lin.append(
            f"| {NOMBRES[a]} | {s['instancias']} | {_seg(s['seg_mediana'])} | {_seg(s['seg_p95'])} | "
            f"{_seg(s['seg_max'])} | {_f(s['mib_mediana'], '{:.2f} MiB')} | {_f(s['hv_media'], '{:.4f}')} | "
            f"{_f(s['hv_min'], '{:.4f}')} | {_f(s['frente_exacto_pct'], '{:.1f} %')} | "
            f"{_f(100 * s['cobertura_media'], '{:.1f} %')} |"
        )
    v = r["verificacion_dp"]
    lin += ["", f"DP = enumeración en {v['dp_igual_enumeracion']} de {v['instancias_comparadas']} listas.", ""]
    lin += ["### Iguala el óptimo por escenario (kit proyectado del frente)", ""]
    lin.append("| Algoritmo | Ahorrador | Premium | Fan | Presupuesto | Calidad con presupuesto |")
    lin.append("|---|---:|---:|---:|---:|---:|")
    e = r["escenarios"]
    for a in ["dp", "nsga2", "nsga2_sin_siembra", "voraz"]:
        celdas = [_f(e.get(k, {}).get(a, {}).get("pct"), "{:.1f} %") for k in ("ahorrador", "premium", "fan", "presupuesto")]
        cal = e.get("presupuesto_calidad", {}).get(a, {}).get("pct")
        lin.append(f"| {NOMBRES[a]} | " + " | ".join(celdas) + f" | {_f(cal, '{:.1f} %')} |")
    ns = {k: e.get(k, {}).get("dp", {}).get("n") for k in ("ahorrador", "premium", "fan", "presupuesto")}
    lin += ["", f"n por escenario: {ns}.", ""]
    lin += ["### Tiempo y memoria por tamaño (n = líneas decidibles)", ""]
    lin.append("| n | Listas | log10 \\|E\\| mediano | Enumeración | DP | NSGA-II | NSGA-II sin siembra | Voraz | Ternas DP (máx./etapa) |")
    lin.append("|---|---:|---:|---:|---:|---:|---:|---:|---:|")
    for t in r["tramos"]:
        cel = []
        for a in ALGOS:
            d = t.get(a, {})
            if not d or not d.get("n"):
                cel.append("—")
            else:
                cel.append(f"{_seg(d['seg_mediana'])} / {_f(d['mib_mediana'], '{:.2f} MiB')}" + (f" ({d['n']})" if a == "enumeracion" else ""))
        lin.append(
            f"| {t['tramo']} | {t['instancias']} | {t['log10_espacio_mediana']:.1f} | " + " | ".join(cel) + f" | {_f(t['dp_ternas_max_mediana'], '{:.0f}')} |"
        )
    if r.get("semillas"):
        lin += ["", "### Variabilidad del NSGA-II con 5 semillas (0-4)", ""]
        lin.append("| Variante | Corridas | HV medio | HV mín. | Frente exacto | Listas con frente exacto en las 5 semillas |")
        lin.append("|---|---:|---:|---:|---:|---:|")
        for a, s in r["semillas"].items():
            lin.append(
                f"| {NOMBRES[a]} | {s['corridas']} | {s['hv_media']:.4f} | {s['hv_min']:.4f} | "
                f"{s['frente_exacto_pct']:.1f} % | {s['listas_con_frente_exacto_en_las_5']:.1f} % |"
            )
    h = r.get("hogares", {}).get("filas")
    if h:
        lin += ["", "### Hogares sintéticos (varios hijos)", ""]
        lin.append("| Hogar | Hijos | n | log10 \\|E\\| | Ternas DP | DP | NSGA-II | NSGA-II sin siembra | Voraz | HV NSGA-II | HV sin siembra | HV voraz |")
        lin.append("|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
        for f in h:
            def tm(a):
                c = f.get(a)
                if not c:
                    return "—"
                return f"{_seg(c['segundos'])} / {_f(c['mib'], '{:.1f} MiB')}"

            lin.append(
                f"| {f['instancia']} | {f['hijos']} | {f['n']} | {f['log10_espacio']:.1f} | {f['dp_ternas_max']} | "
                f"{tm('dp')} | {tm('nsga2')} | {tm('nsga2_sin_siembra')} | {tm('voraz')} | "
                f"{f['nsga2']['hv_ratio']:.4f} | {f['nsga2_sin_siembra']['hv_ratio']:.4f} | {f['voraz']['hv_ratio']:.4f} |"
            )
    aj = r.get("ajustes_potencia_n")
    if aj:
        lin += ["", "### Exponente empírico b (t ∝ n^b, listas con n ≥ 15 y hogares)", ""]
        lin.append("| Algoritmo | b (tiempo) | b (memoria) |")
        lin.append("|---|---:|---:|")
        for a in ALGOS:
            if a in aj:
                lin.append(f"| {NOMBRES[a]} | {_f(aj[a].get('exponente_tiempo'), '{:.2f}')} | {_f(aj[a].get('exponente_memoria'), '{:.2f}')} |")
    if r.get("enumeracion_hasta_4096_max_s") is not None:
        lin += ["", f"Enumeración con |E| ≤ 4.096 (lo que produccion enumera): máximo {_seg(r['enumeracion_hasta_4096_max_s'])}."]
    return "\n".join(lin) + "\n"


if __name__ == "__main__":
    raise SystemExit(main())
