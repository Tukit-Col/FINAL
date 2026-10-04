"""Mide a todos los competidores con la misma vara y escribe `resultados.json`.

Competidores:
- `optimo`        el optimo exacto de cada escenario (techo).
- `nsga2`         produccion, semilla 0 (las semillas 1-4 miden variabilidad).
- `nsga2_frente`  solo presupuesto: el mejor punto del frente que cabe (lo que el
                  frente ya tiene y hoy `recomendar` no entrega).
- `heuristica`    `elegir_por_perfil` (piso del proyecto). En presupuesto: el kit
                  recomendado entre los tres heuristicos.
- `azar`          un candidato al azar por linea (semilla fija), para leer a Laya.
- `laya_A..D`     las cuatro modalidades de Laya.
"""

from __future__ import annotations

import random
import statistics as st
from collections import defaultdict

from comun import (
    CARPETA,
    cargar_json,
    decidibles,
    domina,
    guardar_json,
    objetivos,
    renglones_de,
)
from tukit_inteligencia.modelos import PerfilKit
from tukit_inteligencia.optimizador import _admisibles, armar_kit, elegir_por_perfil, recomendar

from correr_laya import decidibles as decidibles_dict  # noqa: E402  (no importa laya al cargar)
from correr_laya import kits_por_reglas  # noqa: E402

PERFIL = {"ahorrador": "Ahorrador", "premium": "Premium", "fan": "Fan"}


def _orden_juez(esc: dict, o: dict) -> tuple:
    """Lo que un juez perfecto maximizaria en cada escenario (mismos desempates que `_proyectar`)."""
    e = esc["escenario"]
    if e == "ahorrador":
        return (-o["costo"], o["fidelidad"])
    if e == "premium":
        return (o["fidelidad"], -o["costo"])
    if e == "fan":
        return (o["personaje"], -o["costo"], o["fidelidad"])
    cabe = o["costo"] <= esc["presupuesto"]
    return (cabe, o["fidelidad"] if cabe else -o["costo"], -o["costo"])


def _heuristica(renglones, dec, esc) -> dict[str, str]:
    prefs = esc["preferencias"]
    personajes = tuple((prefs.get("personaje_por_hijo") or {}).get("hijo-1") or ())
    if esc["escenario"] in PERFIL:
        return {
            str(r.orden): elegir_por_perfil(r.candidatos, PERFIL[esc["escenario"]], personajes=personajes).sku
            for r in dec
        }
    kits = recomendar([armar_kit(renglones, p.value, prefs) for p in PerfilKit], prefs)
    kit = next(k for k in kits if k.recomendado)
    claves = {str(r.orden) for r in dec}
    return {str(l.orden): l.elegido.sku for l in kit.lineas if l.elegido and str(l.orden) in claves}


def _azar(dec, clave: str) -> dict[str, str]:
    rng = random.Random(clave)
    return {str(r.orden): rng.choice(_admisibles(r)).sku for r in dec}


def _puntaje(esc: dict, obj: dict, opt: dict) -> dict[str, float]:
    """Metricas del escenario. `optimo_ok` es 1 si iguala al optimo en su eje."""
    e = esc["escenario"]
    if e == "ahorrador":
        brecha = (obj["costo"] - opt["costo"]) / opt["costo"] if opt["costo"] else 0.0
        return {"brecha_costo_pct": 100 * brecha, "optimo_ok": float(obj["costo"] <= opt["costo"])}
    if e == "premium":
        extra = (obj["costo"] - opt["costo"]) / opt["costo"] if opt["costo"] else 0.0
        return {
            "brecha_fidelidad": opt["fidelidad"] - obj["fidelidad"],
            "costo_vs_optimo_pct": 100 * extra,
            "optimo_ok": float(obj["fidelidad"] >= opt["fidelidad"] - 1e-9),
        }
    if e == "fan":
        cob = obj["personaje"] / opt["personaje"] if opt["personaje"] else 1.0
        return {
            "cobertura_personaje_vs_optimo": cob,
            "optimo_ok": float(obj["personaje"] >= opt["personaje"] - 1e-9),
        }
    cabe = obj["costo"] <= esc["presupuesto"]
    logro = obj["fidelidad"] / opt["fidelidad"] if opt["fidelidad"] else 1.0
    return {
        "cabe": float(cabe),
        "fidelidad_si_cabe": obj["fidelidad"] if cabe else None,
        "puntaje": logro if cabe else 0.0,
        "optimo_ok": float(cabe and obj["fidelidad"] >= opt["fidelidad"] - 1e-9),
        "exceso_pct": 100 * max(0.0, obj["costo"] - esc["presupuesto"]) / esc["presupuesto"],
    }


def main() -> int:
    instancias = {i["id"]: i for i in cargar_json("instancias.json")["instancias"]}
    escenarios = cargar_json("escenarios.json")["escenarios"]
    nsga = cargar_json("nsga.json")["filas"]
    nsga_por = defaultdict(dict)
    for f in nsga:
        nsga_por[(f["instancia"], f["escenario"])][f["semilla"]] = f

    laya = {}
    for m in "ABCD":
        ruta = CARPETA / f"laya_{m}.json"
        if ruta.exists():
            laya[m] = {(f["instancia"], f["escenario"]): f for f in cargar_json(ruta.name)["filas"]}

    filas = []
    frente_dominado: list[dict] = []
    semillas: list[dict] = []
    for esc in escenarios:
        clave = (esc["instancia"], esc["escenario"])
        renglones = renglones_de(instancias[esc["instancia"]])
        dec = decidibles(renglones)
        prefs = esc["preferencias"]
        opt = esc["objetivos_optimo"]
        n0 = nsga_por[clave].get(0)
        frente = n0["frente"] if n0 else []

        competidores = {"optimo": esc["optimo"], "heuristica": _heuristica(renglones, dec, esc), "azar": _azar(dec, "|".join(clave))}
        if n0:
            competidores["nsga2"] = n0["asignacion"]
            if esc["escenario"] == "presupuesto" and n0.get("asignacion_frente"):
                competidores["nsga2_frente"] = n0["asignacion_frente"]
        for m, filas_m in laya.items():
            f = filas_m.get(clave)
            if f and not f["error"]:
                competidores[f"laya_{m}"] = f["asignacion"]

        # Los 5 kits de reglas que ve Laya D, y el que elegiria un juez perfecto.
        kits_reglas = [
            {o: c["sku"] for o, c in k["elec"].items()}
            for k in kits_por_reglas(decidibles_dict(instancias[esc["instancia"]]), esc.get("personaje"))
        ]
        if kits_reglas and dec:
            competidores["reglas_juez_perfecto"] = max(
                kits_reglas, key=lambda a: _orden_juez(esc, objetivos(dec, a, prefs))
            )
            if frente:
                objs_reglas = [objetivos(dec, a, prefs) for a in kits_reglas]
                frente_dominado.append(
                    {
                        "instancia": esc["instancia"],
                        "escenario": esc["escenario"],
                        "puntos_frente": len(frente),
                        "puntos_dominados": sum(1 for p in frente if any(domina(o, p) for o in objs_reglas)),
                    }
                )

        for s in range(1, 5):
            fs = nsga_por[clave].get(s)
            if fs:
                o = objetivos(dec, fs["asignacion"], prefs)
                semillas.append({"escenario": esc["escenario"], "semilla": s, **_puntaje(esc, o, opt)})
        if n0:
            semillas.append({"escenario": esc["escenario"], "semilla": 0, **_puntaje(esc, objetivos(dec, n0["asignacion"], prefs), opt)})

        for nombre, asign in competidores.items():
            obj = objetivos(dec, asign, prefs)
            fila = {
                "instancia": esc["instancia"],
                "escenario": esc["escenario"],
                "competidor": nombre,
                "lineas": len(dec),
                "objetivos": obj,
                **_puntaje(esc, obj, opt),
            }
            if esc["escenario"] != "presupuesto" and frente:
                fila["dominado_por_frente"] = float(any(domina(p, obj) for p in frente))
                fila["domina_al_frente"] = float(any(domina(obj, p) for p in frente))
            if nombre.startswith("laya_"):
                f = laya[nombre[-1]][clave]
                fila["segundos"] = f["segundos"]
                fila["confianza_media"] = f["confianza_media"]
            if nombre == "nsga2":
                fila["segundos"] = n0["segundos"]
                fila["metodo"] = n0["metodo"]
            filas.append(fila)

    # variabilidad del NSGA-II entre semillas
    variab = []
    for clave, por_semilla in nsga_por.items():
        vectores = {tuple(sorted(f["objetivos"].items())) for f in por_semilla.values()}
        variab.append({"instancia": clave[0], "escenario": clave[1], "distintos": len(vectores), "metodo": por_semilla[0]["metodo"]})

    resumen = resumir(filas, variab)
    por_esc = defaultdict(list)
    for s in semillas:
        por_esc[s["escenario"]].append(s["optimo_ok"])
    resumen["nsga2_optimo_pct_todas_las_semillas"] = {e: round(100 * st.mean(v), 1) for e, v in por_esc.items()}
    con_dom = [d for d in frente_dominado if d["puntos_dominados"] > 0]
    resumen["frente_con_puntos_dominados_por_reglas"] = {
        "listas_escenario": len(frente_dominado),
        "con_algun_punto_dominado_pct": round(100 * len(con_dom) / max(1, len(frente_dominado)), 1),
        "fraccion_media_de_puntos_dominados": round(
            st.mean(d["puntos_dominados"] / d["puntos_frente"] for d in frente_dominado), 4
        )
        if frente_dominado
        else None,
    }
    guardar_json(
        "resultados.json",
        {"resumen": resumen, "variabilidad_nsga": variab, "frente_dominado": frente_dominado, "filas": filas},
    )
    imprimir(resumen)
    return 0


def _media(xs):
    xs = [x for x in xs if x is not None]
    return round(st.mean(xs), 4) if xs else None


def _mediana(xs):
    xs = [x for x in xs if x is not None]
    return round(st.median(xs), 4) if xs else None


def resumir(filas, variab):
    grupos = defaultdict(list)
    for f in filas:
        grupos[(f["escenario"], f["competidor"])].append(f)
    resumen = {}
    for (esc, comp), fs in sorted(grupos.items()):
        r = {"n": len(fs), "optimo_pct": round(100 * _media([f["optimo_ok"] for f in fs]), 1)}
        for k in ("brecha_costo_pct", "brecha_fidelidad", "costo_vs_optimo_pct", "cobertura_personaje_vs_optimo", "cabe", "fidelidad_si_cabe", "puntaje", "exceso_pct", "dominado_por_frente", "domina_al_frente", "segundos", "confianza_media"):
            if any(k in f for f in fs):
                r[k] = _media([f.get(k) for f in fs])
                if k in ("brecha_costo_pct", "segundos", "exceso_pct"):
                    r[k + "_mediana"] = _mediana([f.get(k) for f in fs])
        resumen[f"{esc}/{comp}"] = r
    por_metodo = defaultdict(list)
    for v in variab:
        por_metodo[v["metodo"]].append(v["distintos"] == 1)
    resumen["nsga2_reproducible_entre_semillas_pct"] = {
        m: round(100 * sum(xs) / len(xs), 1) for m, xs in por_metodo.items()
    }
    return resumen


def imprimir(resumen):
    for k, v in resumen.items():
        print(k, v)


if __name__ == "__main__":
    raise SystemExit(main())
