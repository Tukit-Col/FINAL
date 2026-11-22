"""Experimento FRENTE: una corrida de NSGA-II (frente + 4 kits) contra la PD."""

from __future__ import annotations

import argparse
import json
import math
import statistics as st
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

AQUI = Path(__file__).resolve().parent
BENCH = AQUI.parent / "bench_laya"
if str(BENCH) not in sys.path:
    sys.path.insert(0, str(BENCH))

import numpy as np  # noqa: E402
from comun import (  # noqa: E402
    HIJO,
    costo_linea,
    decidibles,
    objetivos,
    optimo_ahorrador,
    optimo_fan,
    optimo_premium,
    optimo_presupuesto,
    personaje_de_lista,
    renglones_de,
)
from tukit_comun.texto import normalizar_personaje  # noqa: E402
from tukit_inteligencia.modelos import PerfilKit  # noqa: E402
from tukit_inteligencia.optimizador import (  # noqa: E402
    LIMITE_ENUMERACION,
    _admisibles,
    _proyectar,
    elegir_recomendado_maut,
    optimizar_frente,
)

SEMILLAS = (0, 1, 2)
BARRIDOS = (20, 50)
PESOS = {"precio": 1.0, "marca_exigida": 1.0, "calidad": 1.0, "personaje": 1.0}
EJES = ("costo", "fidelidad", "disponibilidad", "personaje")


def vec(o: dict) -> tuple:
    return (o["costo"], o["fidelidad"], o["disponibilidad"], o["personaje"])


def _domina(a: tuple, b: tuple) -> bool:
    return a[0] <= b[0] and a[1] >= b[1] and a[2] >= b[2] and a[3] >= b[3] and a != b


def no_dominados(vectores) -> list[tuple]:
    unicos = sorted(set(vectores))
    return [v for v in unicos if not any(_domina(o, v) for o in unicos)]


def hipervolumen(frente: list[tuple], ref_info: dict) -> float:
    from pymoo.indicators.hv import HV

    if not frente:
        return 0.0
    c0, c1 = ref_info["cmin"], ref_info["cmax"]
    span = max(1, c1 - c0)
    pts = np.array(
        [[(v[0] - c0) / span, 1 - v[1], 1 - v[2], 1 - v[3]] for v in frente], dtype=float
    )
    pts = np.clip(pts, 0.0, 1.0)
    return float(HV(ref_point=np.full(4, 1.1))(pts))


def pd_frente_4d(dec, prefs):
    pedidos = {r.orden: {normalizar_personaje(p) for p in prefs.get("personaje_por_hijo", {}).get(r.hijo, [])} for r in dec}
    ops = []
    for r in dec:
        fila = []
        for c in _admisibles(r):
            ped = pedidos[r.orden]
            pers = 1 if (c.personaje and (not ped or normalizar_personaje(c.personaje) in ped)) else 0
            precio = 1 if c.precio_cop is not None else 0
            fila.append((c.rango_nivel, precio, pers, costo_linea(r, c), c.sku))
        ops.append(fila)
    capas = []
    actual = {(0, 0, 0): 0}
    for fila in ops:
        nuevo: dict = {}
        for (s, d, p), cost in actual.items():
            for j, (niv, pr, pe, cl, _) in enumerate(fila):
                k = (s + niv, d + pr, p + pe)
                c2 = cost + cl
                previo = nuevo.get(k)
                if previo is None or c2 < previo[0]:
                    nuevo[k] = (c2, (s, d, p), j)
        capas.append(nuevo)
        actual = {k: v[0] for k, v in nuevo.items()}
    estados = sorted(actual.items(), key=lambda kv: (kv[1], -kv[0][0]))
    nd: list = []
    for (s, d, p), cost in estados:
        if not any(c <= cost and s2 >= s and d2 >= d and p2 >= p for (s2, d2, p2), c in nd):
            nd.append(((s, d, p), cost))
    salida = []
    for clave, _ in nd:
        elec = []
        k = clave
        for i in range(len(ops) - 1, -1, -1):
            _, padre, j = capas[i][k]
            elec.append(ops[i][j][4])
            k = padre
        elec.reverse()
        salida.append({str(r.orden): sku for r, sku in zip(dec, elec, strict=True)})
    return salida


def trabajo(args):
    inst, escenarios_inst = args
    renglones = renglones_de(inst)
    dec = decidibles(renglones)
    esc_pres = next(e for e in escenarios_inst if e["escenario"] == "presupuesto")
    tope = esc_pres["presupuesto"]
    pers = personaje_de_lista(dec)
    prefs = {"personaje_por_hijo": {HIJO: [pers]}} if pers else {}
    pedidos = {pers} if pers else set()
    espacio = math.prod(len(_admisibles(r)) for r in dec)
    fila = {
        "instancia": inst["id"], "lineas": len(dec), "espacio": espacio,
        "metodo": "enumeracion" if espacio <= LIMITE_ENUMERACION else "nsga2",
        "personaje_pedido": pers, "tope": tope,
    }

    ns = []
    for semilla in SEMILLAS:
        t = time.perf_counter()
        frente = optimizar_frente(renglones, prefs, semilla=semilla)
        kits = {p.value: _proyectar(frente, p.value) for p in PerfilKit}
        kits["A tu Medida"] = elegir_recomendado_maut(frente, PESOS, tope=tope)
        seg = time.perf_counter() - t
        ns.append({
            "semilla": semilla, "s": seg, "n_frente": len(frente),
            "vectores": [(s.costo, s.fidelidad, s.disponibilidad, s.personaje) for s in frente],
            "kits": {k: (None if v is None else (v.costo, v.fidelidad, v.disponibilidad, v.personaje)) for k, v in kits.items()},
        })

    t = time.perf_counter()
    asig = {
        "Ahorrador": optimo_ahorrador(dec),
        "Premium": optimo_premium(dec),
        "Fan": optimo_fan(dec, pedidos),
        "A tu Medida": optimo_presupuesto(dec, tope),
    }
    fila["pd4_s"] = time.perf_counter() - t
    objs = {k: (vec(objetivos(dec, a, prefs)) if a else None) for k, a in asig.items()}
    extremos = [v for k, v in objs.items() if k != "A tu Medida" and v]

    c_lo = objs["Ahorrador"][0]
    c_hi = max(objs["Premium"][0], objs["Fan"][0] if objs["Fan"] else 0, c_lo + 1)
    barridos = {}
    ks = {f"b{k}": k for k in BARRIDOS}
    ks["bK"] = max(2, len(ns[0]["vectores"]))
    ks["bK"] = min(ks["bK"], 400)
    for nombre, k in ks.items():
        t = time.perf_counter()
        pts = []
        for b in np.linspace(c_lo, c_hi, k):
            a = optimo_presupuesto(dec, int(round(b)))
            if a:
                pts.append(vec(objetivos(dec, a, prefs)))
        seg_total = time.perf_counter() - t
        barridos[nombre] = {"k": k, "s_total": seg_total, "vectores": pts}
    for nombre, k in ks.items():
        t = time.perf_counter()
        for b in np.linspace(c_lo, c_hi, k):
            optimo_presupuesto(dec, int(round(b)))
        barridos[nombre]["s"] = time.perf_counter() - t

    t = time.perf_counter()
    asigs4 = pd_frente_4d(dec, prefs)
    fila["pd4d_s"] = time.perf_counter() - t
    exacto = no_dominados([vec(objetivos(dec, a, prefs)) for a in asigs4])
    fila["n_exacto"] = len(exacto)
    ref = {"cmin": min(v[0] for v in exacto), "cmax": max(v[0] for v in exacto)}
    hv_ex = hipervolumen(exacto, ref)
    set_exacto = set(exacto)

    def metricas(vectores):
        nd = no_dominados(vectores)
        return {
            "n_nd": len(nd),
            "hv_rel": hipervolumen(nd, ref) / hv_ex if hv_ex else 1.0,
            "recall": len(set(nd) & set_exacto) / len(set_exacto),
            "niv_pers": len({v[3] for v in nd}),
            "niv_disp": len({v[2] for v in nd}),
            "niv_fid": len({v[1] for v in nd}),
        }

    fila["exacto"] = metricas(exacto)
    fila["nsga_s_medio"] = st.mean(r["s"] for r in ns)
    fila["nsga"] = [{"semilla": r["semilla"], "s": r["s"], **metricas(r["vectores"])} for r in ns]
    fila["pd4_kits"] = metricas([v for v in objs.values() if v])
    for nombre, b in barridos.items():
        fila[f"pd_{nombre}"] = {"k": b["k"], "s": b["s"], **metricas(b["vectores"]),
                                **{"con_extremos": metricas(b["vectores"] + extremos)}}
    fila["kits_nsga_s0"] = ns[0]["kits"]
    fila["kits_pd"] = objs
    fila["frente_nsga_s0"] = ns[0]["vectores"]
    fila["frente_exacto"] = exacto
    fila["frente_b20"] = barridos["b20"]["vectores"]
    return fila


def mediana(xs):
    xs = list(xs)
    return st.median(xs) if xs else None


def resumen(filas):
    out = {}
    for nombre, sel in (("todas", filas), ("nsga2", [f for f in filas if f["metodo"] == "nsga2"]),
                        ("enumeracion", [f for f in filas if f["metodo"] == "enumeracion"])):
        if not sel:
            continue
        r = {"listas": len(sel)}
        r["nsga_s_mediana"] = mediana(f["nsga_s_medio"] for f in sel)
        r["nsga_s_max"] = max(f["nsga_s_medio"] for f in sel)
        r["pd4_s_mediana"] = mediana(f["pd4_s"] for f in sel)
        r["pd4d_s_mediana"] = mediana(f["pd4d_s"] for f in sel)
        r["pd4d_s_max"] = max(f["pd4d_s"] for f in sel)
        for b in ("b20", "b50", "bK"):
            r[f"pd_{b}_s_mediana"] = mediana(f[f"pd_{b}"]["s"] for f in sel)
        r["n_exacto_mediana"] = mediana(f["n_exacto"] for f in sel)
        r["n_nsga_mediana"] = mediana(st.mean(x["n_nd"] for x in f["nsga"]) for f in sel)
        r["hv_nsga_media"] = st.mean(st.mean(x["hv_rel"] for x in f["nsga"]) for f in sel)
        r["recall_nsga_media"] = st.mean(st.mean(x["recall"] for x in f["nsga"]) for f in sel)
        r["niv_pers_nsga"] = mediana(st.mean(x["niv_pers"] for x in f["nsga"]) for f in sel)
        r["niv_pers_exacto"] = mediana(f["exacto"]["niv_pers"] for f in sel)
        r["pd4_n_nd_mediana"] = mediana(f["pd4_kits"]["n_nd"] for f in sel)
        r["pd4_hv_media"] = st.mean(f["pd4_kits"]["hv_rel"] for f in sel)
        for b in ("b20", "b50", "bK"):
            r[f"{b}_n_nd_mediana"] = mediana(f[f"pd_{b}"]["n_nd"] for f in sel)
            r[f"{b}_hv_media"] = st.mean(f[f"pd_{b}"]["hv_rel"] for f in sel)
            r[f"{b}_recall_media"] = st.mean(f[f"pd_{b}"]["recall"] for f in sel)
            r[f"{b}_niv_pers"] = mediana(f[f"pd_{b}"]["niv_pers"] for f in sel)
            r[f"{b}_ext_hv_media"] = st.mean(f[f"pd_{b}"]["con_extremos"]["hv_rel"] for f in sel)
            r[f"{b}_ext_n_nd_mediana"] = mediana(f[f"pd_{b}"]["con_extremos"]["n_nd"] for f in sel)
        out[nombre] = r
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--procesos", type=int, default=4)
    ap.add_argument("--limite", type=int, default=0)
    args = ap.parse_args()
    from comun import cargar_json

    inst = {i["id"]: i for i in cargar_json("instancias.json.gz")["instancias"]}
    esc: dict = {}
    for e in cargar_json("escenarios.json")["escenarios"]:
        esc.setdefault(e["instancia"], []).append(e)
    ids = sorted(i for i in esc if any(e["escenario"] == "presupuesto" for e in esc[i]))
    if args.limite:
        ids = ids[:: max(1, len(ids) // args.limite)][: args.limite]
    tareas = [(inst[i], esc[i]) for i in ids]
    t0 = time.perf_counter()
    with ProcessPoolExecutor(max_workers=args.procesos) as ex:
        filas = []
        for n, f in enumerate(ex.map(trabajo, tareas, chunksize=1), 1):
            filas.append(f)
            if n % 20 == 0:
                print(f"{n}/{len(tareas)} {time.perf_counter() - t0:.0f}s", flush=True)
    datos = {
        "config": {"semillas": list(SEMILLAS), "barridos": list(BARRIDOS), "procesos": args.procesos,
                   "listas": len(ids), "segundos_totales": round(time.perf_counter() - t0, 1),
                   "nota": "bK = tantos presupuestos como puntos del frente de NSGA-II (semilla 0, tope 400)"},
        "resumen": resumen(filas),
        "filas": filas,
    }
    (AQUI / "frente.json").write_text(json.dumps(datos, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(datos["resumen"], indent=1, ensure_ascii=False)[:4000])


if __name__ == "__main__":
    main()
