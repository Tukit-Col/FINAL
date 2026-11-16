"""Metrica principal: el mejor punto del frente que cabe (asignacion_frente), que es el kit
proyectado de la memoria. El kit que hoy entrega `recomendar` (uno de los tres heuristicos) se
reporta aparte como `kit_recomendado`.

Audita las listas de presupuesto donde NSGA-II (con siembra) no iguala el optimo exacto.

Reutiliza `_trabajo` de bench_laya/correr_nsga.py (misma funcion de produccion) sobre
las listas reales, solo el escenario de presupuesto, semillas 0, 1 y 2. Tambien lee las
corridas guardadas en nsga.json.gz para ver si coinciden con la re-corrida actual.
Igualar = el kit entregado cabe en el presupuesto y su fidelidad >= la del optimo exacto
(mismo criterio que `optimo_ok` de evaluar.py). Se reporta ademas si la asignacion es
identica sku a sku y el costo adicional.

Uso: uv run python ensayos/calibracion/auditar_presupuesto.py [--procesos 6]
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

BANCO = Path(__file__).resolve().parents[1] / "bench_laya"
SALIDA = Path(__file__).resolve().parents[2] / "docs" / "informes" / "calibracion" / "auditar_presupuesto.json"
SEMILLAS = (0, 1, 2)
sys.path.insert(0, str(BANCO))


def _job(args):
    from correr_nsga import _trabajo

    inst, escs, s = args
    return _trabajo(inst, escs, s)


def main() -> int:
    from comun import cargar_json, decidibles, objetivos, renglones_de
    from tukit_inteligencia.optimizador import LIMITE_ENUMERACION, _admisibles

    ap = argparse.ArgumentParser()
    ap.add_argument("--procesos", type=int, default=6)
    a = ap.parse_args()

    insts = {i["id"]: i for i in cargar_json("instancias.json.gz")["instancias"]}
    escs = {e["instancia"]: e for e in cargar_json("escenarios.json")["escenarios"] if e["escenario"] == "presupuesto"}
    guardado = {
        (f["instancia"], f["semilla"]): f
        for f in cargar_json("nsga.json.gz")["filas"]
        if f["escenario"] == "presupuesto"
    }
    trabajos = [(insts[i], [escs[i]], s) for i in sorted(escs) for s in SEMILLAS]
    with ProcessPoolExecutor(max_workers=a.procesos) as ex:
        filas = [f for fs in ex.map(_job, trabajos, chunksize=2) for f in fs]
    nuevo = {(f["instancia"], f["semilla"]): f for f in filas}

    detalle = []
    for i in sorted(escs):
        e = escs[i]
        dec = decidibles(renglones_de(insts[i]))
        espacio = math.prod(len(_admisibles(r)) for r in dec)
        opt = e["objetivos_optimo"]
        reg = {
            "instancia": i, "colegio": insts[i]["colegio"], "grado": insts[i]["grado"],
            "lineas_decidibles": len(dec), "log10_espacio": round(math.log10(espacio), 2) if espacio else 0,
            "espacio_enumerable": espacio <= LIMITE_ENUMERACION, "presupuesto": e["presupuesto"],
            "optimo": {"costo": opt["costo"], "fidelidad": opt["fidelidad"]}, "semillas": {},
        }
        for s in SEMILLAS:
            f = nuevo[(i, s)]
            asig = f.get("asignacion_frente") or {}
            o = objetivos(dec, asig, e["preferencias"]) if asig else {"costo": 10**12, "fidelidad": 0.0}
            orec = objetivos(dec, f["asignacion"], e["preferencias"])
            cabe = o["costo"] <= e["presupuesto"]
            igual = cabe and o["fidelidad"] >= opt["fidelidad"] - 1e-9
            dif = sum(1 for k, v in e["optimo"].items() if asig.get(k) != v)
            g = guardado.get((i, s))
            reg["semillas"][str(s)] = {
                "iguala": bool(igual), "cabe": bool(cabe), "costo": o["costo"], "fidelidad": o["fidelidad"],
                "fidelidad_perdida": round(opt["fidelidad"] - o["fidelidad"], 6),
                "costo_adicional": o["costo"] - opt["costo"],
                "costo_adicional_pct": round(100 * (o["costo"] - opt["costo"]) / opt["costo"], 3),
                "lineas_distintas_al_optimo": dif,
                "perfil_recomendado": f.get("perfil_recomendado"),
                "kit_recomendado": {"costo": orec["costo"], "fidelidad": orec["fidelidad"],
                                    "cabe": orec["costo"] <= e["presupuesto"],
                                    "iguala": orec["costo"] <= e["presupuesto"] and orec["fidelidad"] >= opt["fidelidad"] - 1e-9},
                "puntos_frente": len(f["frente"]),
                "coincide_con_guardado": None if g is None else g.get("asignacion_frente") == f.get("asignacion_frente"),
            }
        detalle.append(reg)

    resumen = {"listas": len(detalle)}
    for s in SEMILLAS:
        mal = [d["instancia"] for d in detalle if not d["semillas"][str(s)]["iguala"]]
        resumen[f"semilla_{s}"] = {"igualan": len(detalle) - len(mal), "no_igualan": mal,
                                  "pct": round(100 * (len(detalle) - len(mal)) / len(detalle), 2)}
    todas = set().union(*(set(resumen[f"semilla_{s}"]["no_igualan"]) for s in SEMILLAS))
    siempre = set.intersection(*(set(resumen[f"semilla_{s}"]["no_igualan"]) for s in SEMILLAS))
    resumen["union_no_igualan"] = sorted(todas)
    resumen["siempre_no_igualan"] = sorted(siempre)
    resumen["kit_recomendado_igualan_por_semilla"] = {
        str(s): sum(d["semillas"][str(s)]["kit_recomendado"]["iguala"] for d in detalle) for s in SEMILLAS}
    resumen["coincide_con_nsga_json_gz"] = all(
        d["semillas"][str(s)]["coincide_con_guardado"] in (True, None) for d in detalle for s in SEMILLAS
    )
    resumen["no_coinciden_con_guardado"] = sorted(
        {d["instancia"] + f"/s{s}" for d in detalle for s in SEMILLAS if d["semillas"][str(s)]["coincide_con_guardado"] is False}
    )
    # perfil de las que fallan vs las demas
    fallan = [d for d in detalle if d["instancia"] in todas]
    resto = [d for d in detalle if d["instancia"] not in todas]
    med = lambda xs: sorted(xs)[len(xs) // 2] if xs else None
    resumen["lineas_mediana_fallan"] = med([d["lineas_decidibles"] for d in fallan])
    resumen["lineas_mediana_resto"] = med([d["lineas_decidibles"] for d in resto])
    resumen["enumerables_entre_fallan"] = sum(d["espacio_enumerable"] for d in fallan)
    SALIDA.parent.mkdir(parents=True, exist_ok=True)
    SALIDA.write_text(json.dumps({"resumen": resumen, "fallan": fallan, "detalle": detalle}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(resumen, ensure_ascii=False, indent=1))
    for d in fallan:
        print(d["instancia"], d["lineas_decidibles"], "lineas log10esp", d["log10_espacio"], d["espacio_enumerable"],
              {s: (v["iguala"], v["fidelidad_perdida"], v["costo_adicional"], v["lineas_distintas_al_optimo"], v["cabe"]) for s, v in d["semillas"].items()})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
