"""Barrido T x lista: PD exacta vs NSGA-II con costo fijo por tienda."""

from __future__ import annotations

import argparse
import json
import statistics as st
import time
import tracemalloc
from concurrent.futures import ProcessPoolExecutor

TIENDAS = (1, 2, 4, 8, 12)
LIMITE_PD_S = 20.0
SEMILLA = 0


def _medir(fn):
    t = time.perf_counter()
    r = fn()
    return r, time.perf_counter() - t


def _memoria(fn):
    tracemalloc.start()
    try:
        fn()
    except Exception:  # noqa: BLE001 (Tiempo)
        pass
    pico = tracemalloc.get_traced_memory()[1]
    tracemalloc.stop()
    return pico / 2**20


def trabajo(args):
    inst, presupuesto, T, con_memoria = args
    from acoplado import F_ENVIO, Tiempo, nsga_acoplado, pd_exacta, total_de
    from comun import decidibles, renglones_de

    dec = decidibles(renglones_de(inst))
    n = len(dec)
    from comun import optimo_ahorrador
    s0, tot0 = total_de(dec, optimo_ahorrador(dec), T)
    from acoplado import _admisibles, costo_linea
    base0 = sum(costo_linea(r, next(c for c in _admisibles(r) if c.sku == optimo_ahorrador(dec)[str(r.orden)])) for r in dec)
    presupuesto = presupuesto + (tot0 - base0)
    fila = {"instancia": inst["id"], "T": T, "lineas": n, "presupuesto": presupuesto}

    def correr_pd():
        return pd_exacta(dec, presupuesto, T, limite_s=LIMITE_PD_S)

    def correr_sin_poda():
        return pd_exacta(dec, presupuesto, T, limite_s=LIMITE_PD_S, poda=False)

    try:
        (r2, est2), seg2 = _medir(correr_sin_poda)
        fila.update(sp_estado="ok", sp_s=seg2, sp_estados=est2)
    except Tiempo as e:
        fila.update(sp_estado="tiempo", sp_s=LIMITE_PD_S, sp_estados=int(e.args[0]))

    try:
        (res, estados), seg = _medir(correr_pd)
        fila.update(pd_estado="ok" if res else "infactible", pd_s=seg, pd_estados=estados)
        pd = res
    except Tiempo as e:
        fila.update(pd_estado="tiempo", pd_s=LIMITE_PD_S, pd_estados=int(e.args[0]))
        pd = None
    if pd:
        fila["pd_fid"] = round(pd[0] / (n * 2), 6)
        fila["pd_costo"] = pd[1]

    (ns, evals), seg = _medir(lambda: nsga_acoplado(dec, presupuesto, T, semilla=SEMILLA))
    fila.update(ns_s=seg, ns_evals=evals)
    if ns:
        fila["ns_fid"], fila["ns_costo"] = ns[0], ns[1]
        s, tot = total_de(dec, ns[2], T)
        assert tot == ns[1], (tot, ns[1])
    if pd and ns:
        fila["iguala"] = bool(round(ns[0], 6) == fila["pd_fid"] and ns[1] == pd[1])
        fila["err_fid"] = (fila["pd_fid"] - ns[0]) / fila["pd_fid"] if fila["pd_fid"] else 0.0
        fila["err_costo"] = (ns[1] - pd[1]) / pd[1]
    elif pd and not ns:
        fila["iguala"] = False
        fila["ns_sin_factible"] = True
    if con_memoria:
        fila["pd_pico_mib"] = _memoria(correr_pd)
        fila["sp_pico_mib"] = _memoria(correr_sin_poda)
        fila["ns_pico_mib"] = _memoria(lambda: nsga_acoplado(dec, presupuesto, T, semilla=SEMILLA))
    return fila


def resumen(filas):
    out = {}
    for T in TIENDAS:
        fs = [f for f in filas if f["T"] == T]
        ok = [f for f in fs if f["pd_estado"] == "ok"]
        comp = [f for f in ok if "iguala" in f]
        med = [f for f in fs if "pd_pico_mib" in f]
        out[str(T)] = {
            "listas": len(fs),
            "pd_ok": len(ok),
            "pd_infactible": sum(f["pd_estado"] == "infactible" for f in fs),
            "pd_supera_20s": sum(f["pd_estado"] == "tiempo" for f in fs),
            "pd_s_mediana": st.median(f["pd_s"] for f in fs),
            "pd_s_media": st.mean(f["pd_s"] for f in fs),
            "pd_s_max": max(f["pd_s"] for f in fs),
            "pd_estados_mediana": st.median(f["pd_estados"] for f in fs),
            "pd_estados_max": max(f["pd_estados"] for f in fs),
            "sp_supera_20s": sum(f["sp_estado"] == "tiempo" for f in fs),
            "sp_s_mediana": st.median(f["sp_s"] for f in fs),
            "sp_estados_mediana": st.median(f["sp_estados"] for f in fs),
            "sp_estados_max": max(f["sp_estados"] for f in fs),
            "sp_pico_mib_mediana": st.median(f["sp_pico_mib"] for f in med) if med else None,
            "sp_pico_mib_max": max(f["sp_pico_mib"] for f in med) if med else None,
            "ns_s_mediana": st.median(f["ns_s"] for f in fs),
            "ns_s_max": max(f["ns_s"] for f in fs),
            "ns_evals_mediana": st.median(f["ns_evals"] for f in fs),
            "pd_pico_mib_mediana": st.median(f["pd_pico_mib"] for f in med) if med else None,
            "pd_pico_mib_max": max(f["pd_pico_mib"] for f in med) if med else None,
            "ns_pico_mib_mediana": st.median(f["ns_pico_mib"] for f in med) if med else None,
            "n_memoria": len(med),
            "comparables": len(comp),
            "ns_iguala": sum(f["iguala"] for f in comp),
            "ns_iguala_frac": (sum(f["iguala"] for f in comp) / len(comp)) if comp else None,
            "ns_err_fid_media": st.mean(f["err_fid"] for f in comp) if comp else None,
            "ns_err_fid_max": max(f["err_fid"] for f in comp) if comp else None,
            "ns_err_costo_media": st.mean(f["err_costo"] for f in comp) if comp else None,
            "ns_err_costo_max": max(f["err_costo"] for f in comp) if comp else None,
            "ns_sin_factible": sum(bool(f.get("ns_sin_factible")) for f in fs),
        }
    return out


def main():
    from acoplado import AQUI, F_ENVIO
    from comun import cargar_json

    ap = argparse.ArgumentParser()
    ap.add_argument("--procesos", type=int, default=6)
    ap.add_argument("--limite", type=int, default=0)
    ap.add_argument("--memoria-cada", type=int, default=5)
    args = ap.parse_args()

    inst = {i["id"]: i for i in cargar_json("instancias.json.gz")["instancias"]}
    pres = {e["instancia"]: e["presupuesto"] for e in cargar_json("escenarios.json")["escenarios"] if e["escenario"] == "presupuesto"}
    ids = sorted(pres)
    if args.limite:
        ids = ids[:: max(1, len(ids) // args.limite)][: args.limite]
    tareas = [
        (inst[i], pres[i], T, k % args.memoria_cada == 0)
        for k, i in enumerate(ids)
        for T in TIENDAS
    ]
    t0 = time.perf_counter()
    with ProcessPoolExecutor(max_workers=args.procesos) as ex:
        filas = []
        for n, f in enumerate(ex.map(trabajo, tareas, chunksize=1), 1):
            filas.append(f)
            if n % 50 == 0:
                print(f"{n}/{len(tareas)} {time.perf_counter() - t0:.0f}s", flush=True)
    datos = {
        "config": {"F_envio_cop": F_ENVIO, "tiendas": list(TIENDAS), "limite_pd_s": LIMITE_PD_S,
                   "semilla_nsga": SEMILLA, "listas": len(ids), "procesos": args.procesos,
                   "presupuesto": "presupuesto del escenario del bench + envio del kit ahorrador (siempre factible)",
                   "tienda": "crc32(sku) % T", "memoria_cada": args.memoria_cada,
                   "segundos_totales": round(time.perf_counter() - t0, 1)},
        "resumen": resumen(filas),
        "filas": filas,
    }
    (AQUI / "resultados.json").write_text(json.dumps(datos, indent=1, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(datos["resumen"], indent=1)[:3000])


if __name__ == "__main__":
    main()
