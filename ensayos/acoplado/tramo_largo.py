"""Tramo largo: NSGA-II (semillas 0,1,2) y PD (limite 20 s) en las 5 listas mas largas, T en {12..64}.

uv run python ensayos/acoplado/tramo_largo.py [--procesos 5] [--semillas 0 1 2]
Escribe tramo_largo.json. No modifica los scripts existentes.
"""
import argparse
import json
import statistics as st
import time
import tracemalloc
from concurrent.futures import ProcessPoolExecutor

TS = (12, 16, 24, 32, 48, 64)
LIMITE = 20.0


def _pico(fn):
    tracemalloc.start()
    try:
        fn()
    except Exception:  # noqa: BLE001
        pass
    p = tracemalloc.get_traced_memory()[1]
    tracemalloc.stop()
    return p / 2**20


def trabajo(a):
    inst, pres0, T, semillas = a
    from acoplado import F_ENVIO, Tiempo, _admisibles, costo_linea, nsga_acoplado, pd_exacta, total_de
    from comun import decidibles, optimo_ahorrador, renglones_de

    dec = decidibles(renglones_de(inst))
    n = len(dec)
    asig = optimo_ahorrador(dec)
    _, tot = total_de(dec, asig, T)
    pr = pres0 + (tot - sum(costo_linea(r, next(c for c in _admisibles(r) if c.sku == asig[str(r.orden)])) for r in dec))
    f = {"instancia": inst["id"], "lineas": n, "T": T, "presupuesto": pr}
    t = time.perf_counter()
    try:
        res, est = pd_exacta(dec, pr, T, limite_s=LIMITE)
        f.update(pd_estado="ok" if res else "infactible", pd_estados=est)
        if res:
            f["pd_fid"], f["pd_costo"] = res[0] / (2 * n), res[1]
    except Tiempo as e:
        f.update(pd_estado="tiempo", pd_estados=int(e.args[0]))
    f["pd_s"] = round(time.perf_counter() - t, 3)
    f["pd_pico_mib"] = round(_pico(lambda: pd_exacta(dec, pr, T, limite_s=LIMITE)), 1)
    ns = []
    for s in semillas:
        t = time.perf_counter()
        mejor, ev = nsga_acoplado(dec, pr, T, semilla=s)
        d = {"semilla": s, "s": round(time.perf_counter() - t, 3), "evals": ev, "factible": mejor is not None}
        if mejor:
            fid, costo, sel = mejor
            assert total_de(dec, sel, T)[1] == costo
            d["fid"], d["costo"] = fid, costo
            if f.get("pd_fid") is not None:
                d["iguala"] = bool(round(fid, 6) == round(f["pd_fid"], 6) and costo == f["pd_costo"])
                d["err_fid"] = (f["pd_fid"] - fid) / f["pd_fid"]
                d["err_costo"] = (costo - f["pd_costo"]) / f["pd_costo"]
        ns.append(d)
    f["nsga"] = ns
    f["ns_s_mediana"] = st.median(d["s"] for d in ns)
    f["ns_pico_mib"] = round(_pico(lambda: nsga_acoplado(dec, pr, T, semilla=semillas[0])), 1)
    return f


def main():
    from acoplado import AQUI, F_ENVIO
    from comun import cargar_json, decidibles, renglones_de

    ap = argparse.ArgumentParser()
    ap.add_argument("--procesos", type=int, default=5)
    ap.add_argument("--semillas", type=int, nargs="+", default=[0, 1, 2])
    ap.add_argument("--listas", type=int, default=5)
    ap.add_argument("--ts", type=int, nargs="+", default=list(TS))
    ap.add_argument("--salida", default="tramo_largo.json")
    a = ap.parse_args()
    inst = {i["id"]: i for i in cargar_json("instancias.json.gz")["instancias"]}
    pres = {e["instancia"]: e["presupuesto"] for e in cargar_json("escenarios.json")["escenarios"] if e["escenario"] == "presupuesto"}
    ids = sorted(pres, key=lambda i: -len(decidibles(renglones_de(inst[i]))))[: a.listas]
    tareas = [(inst[i], pres[i], T, a.semillas) for i in ids for T in a.ts]
    t0 = time.perf_counter()
    filas = []
    with ProcessPoolExecutor(max_workers=a.procesos) as ex:
        for f in ex.map(trabajo, tareas, chunksize=1):
            filas.append(f)
            print(f"{f['instancia']} L={f['lineas']} T={f['T']} pd={f['pd_estado']} {f['pd_s']}s ns_med={f['ns_s_mediana']}s", flush=True)
    datos = {"config": {"F_envio_cop": F_ENVIO, "ts": a.ts, "semillas": a.semillas, "limite_pd_s": LIMITE, "procesos": a.procesos,
                        "listas": ids, "tienda": "crc32(sku) % T", "segundos_totales": round(time.perf_counter() - t0, 1)},
             "filas": filas}
    (AQUI / a.salida).write_text(json.dumps(datos, indent=1, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main()
