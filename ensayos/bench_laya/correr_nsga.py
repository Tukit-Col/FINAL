"""El competidor de produccion: NSGA-II (o enumeracion exacta si el espacio es chico).
Salida: `nsga.json` con, por (instancia, escenario, semilla):"""

from __future__ import annotations

import argparse
import time
from concurrent.futures import ProcessPoolExecutor, as_completed

SEMILLAS = (0, 1, 2, 3, 4)


def _trabajo(instancia: dict, escenarios: list[dict], semilla: int) -> list[dict]:
    from comun import decidibles, objetivos, renglones_de
    from tukit_inteligencia.modelos import PerfilKit
    from tukit_inteligencia.optimizador import _proyectar, armar_kit, optimizar_frente, recomendar

    renglones = renglones_de(instancia)
    dec = decidibles(renglones)
    claves_dec = {str(r.orden) for r in dec}
    por_linea = {(r.hijo, r.orden): {c.sku: c for c in r.candidatos} for r in renglones if not r.informativa}

    def asignacion_de(kit) -> dict[str, str]:
        return {
            str(linea.orden): linea.elegido.sku
            for linea in kit.lineas
            if not linea.informativa and linea.elegido is not None and str(linea.orden) in claves_dec
        }

    def armar(prefs: dict):
        t0 = time.perf_counter()
        frente = optimizar_frente(renglones, prefs, semilla=semilla)
        kits = []
        for perfil in PerfilKit:
            punto = _proyectar(frente, perfil.value) if frente else None
            elecciones = None
            if punto is not None:
                elecciones = {
                    k: por_linea[k][sku]
                    for k, sku in punto.asignacion.items()
                    if k in por_linea and sku in por_linea[k]
                }
            kits.append(armar_kit(renglones, perfil.value, prefs, elecciones=elecciones))
        kits = recomendar(kits, prefs)
        return frente, kits, time.perf_counter() - t0

    import json

    salida = []
    corridas: dict[str, tuple] = {}
    for esc in escenarios:
        prefs = esc["preferencias"]
        clave = json.dumps(prefs, sort_keys=True)
        if clave not in corridas:
            corridas[clave] = armar(prefs)
        frente, kits, seg = corridas[clave]
        por_perfil = {k.perfil: k for k in kits}
        fila = {
            "instancia": instancia["id"],
            "escenario": esc["escenario"],
            "semilla": semilla,
            "segundos": round(seg, 4),
            "metodo": "nsga2" if _uso_nsga(dec) else "exacto",
            "frente": [
                {
                    "costo": s.costo,
                    "fidelidad": s.fidelidad,
                    "disponibilidad": s.disponibilidad,
                    "personaje": s.personaje,
                }
                for s in frente
            ],
        }
        if esc["escenario"] in ("ahorrador", "premium", "fan"):
            nombre = {"ahorrador": "Ahorrador", "premium": "Premium", "fan": "Fan"}[esc["escenario"]]
            kit = por_perfil[nombre]
            fila["asignacion"] = asignacion_de(kit)
        else:
            recomendado = next(k for k in kits if k.recomendado)
            fila["asignacion"] = asignacion_de(recomendado)
            fila["perfil_recomendado"] = recomendado.perfil
            tope = esc["presupuesto"]
            caben = [s for s in frente if s.costo <= tope]
            if caben:
                mejor = max(caben, key=lambda s: (s.fidelidad, -s.costo))
                fila["asignacion_frente"] = {str(o): sku for (_h, o), sku in mejor.asignacion.items()}
            else:
                fila["asignacion_frente"] = None
        fila["objetivos"] = objetivos(dec, fila["asignacion"], prefs)
        salida.append(fila)
    return salida


def _uso_nsga(dec) -> bool:
    import math

    from tukit_inteligencia.optimizador import LIMITE_ENUMERACION, _admisibles

    return math.prod(len(_admisibles(r)) for r in dec) > LIMITE_ENUMERACION


def main() -> int:
    from comun import cargar_json, guardar_json

    ap = argparse.ArgumentParser()
    ap.add_argument("--procesos", type=int, default=6)
    ap.add_argument("--limite", type=int, default=0, help="solo las primeras N instancias (prueba)")
    ap.add_argument("--salida", default="nsga.json.gz")
    args = ap.parse_args()

    instancias = {i["id"]: i for i in cargar_json("instancias.json.gz")["instancias"]}
    escenarios = cargar_json("escenarios.json")["escenarios"]
    por_inst: dict[str, list[dict]] = {}
    for e in escenarios:
        por_inst.setdefault(e["instancia"], []).append(e)
    ids = sorted(por_inst)
    if args.limite:
        ids = ids[: args.limite]

    filas: list[dict] = []
    t0 = time.perf_counter()
    with ProcessPoolExecutor(max_workers=args.procesos) as ex:
        futuros = [ex.submit(_trabajo, instancias[i], por_inst[i], s) for i in ids for s in SEMILLAS]
        for n, f in enumerate(as_completed(futuros), 1):
            filas.extend(f.result())
            if n % 50 == 0:
                print(f"  {n}/{len(futuros)} en {time.perf_counter() - t0:.0f}s", flush=True)
    filas.sort(key=lambda f: (f["instancia"], f["escenario"], f["semilla"]))
    guardar_json(args.salida, {"semillas": list(SEMILLAS), "filas": filas})
    print(f"{len(filas)} filas en {time.perf_counter() - t0:.0f}s -> {args.salida}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
