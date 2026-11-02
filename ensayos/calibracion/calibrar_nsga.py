"""Experimento B: poblacion y generaciones del NSGA-II, con particion por colegio.

Las listas con espacio mayor que LIMITE_ENUMERACION (las que corren NSGA-II en
produccion) se reparten por COLEGIO en entrenamiento (~60 % de las listas),
validacion (~20 %) y prueba (~20 %): todas las listas de un colegio caen del mismo
lado, porque dos grados del mismo colegio comparten productos y marcas.

La rejilla multiplica las formulas actuales por factores:
    poblacion = clamp(a * 12n, a * 40, a * 200)   (par)
    generaciones = clamp(b * 20 log10 S, b * 30, b * 120)
con a, b en {0,25; 0,5; 1; 2}. El par (1, 1) es la configuracion actual.

1. ENTRENAMIENTO: se corre toda la rejilla (3 semillas por lista).
2. VALIDACION: se corre toda la rejilla (5 semillas por lista). De aqui se elige
   la configuracion MAS BARATA (evaluaciones = poblacion x generaciones) cuyo
   hipervolumen medio no baja mas de 0,1 % del mejor de la rejilla.
3. PRUEBA: una sola vez, configuracion actual contra la elegida, 30 semillas por
   lista, tiempos en serie.

El hipervolumen se mide contra el frente exacto (poda por linea), en el espacio
normalizado de `nucleo.hipervolumen`.

Uso: uv run python ensayos/calibracion/calibrar_nsga.py [--rapido]
Salida: docs/informes/calibracion/calibracion_nsga.json
"""

from __future__ import annotations

import argparse
import math
import random
import time
from concurrent.futures import ProcessPoolExecutor
from itertools import product

import nucleo as n
import numpy as np
from scipy import stats
from tukit_inteligencia import optimizador as opt

FACTORES = (0.25, 0.5, 1.0, 2.0)
UMBRAL_HV = 0.001
SEMILLAS_ENTRENAMIENTO = (0, 1, 2)
SEMILLAS_VALIDACION = (0, 1, 2, 3, 4)
SEMILLAS_PRUEBA = tuple(range(30))


def poblacion_con(a: float):
    def f(nlineas: int) -> int:
        cruda = min(a * 200, max(a * 40, a * 12 * nlineas))
        cruda = max(4, int(round(cruda)))
        return cruda + (cruda & 1)

    return f


def generaciones_con(b: float):
    def f(espacio: int) -> int:
        return max(2, int(min(b * 120, max(b * 30, b * 20 * math.log10(max(10, espacio))))))

    return f


def particion(insts: list[dict]) -> dict[str, list[str]]:
    """Reparte los colegios (no las listas) 60/20/20 con semilla fija."""
    por_colegio: dict[str, list[str]] = {}
    for i in insts:
        por_colegio.setdefault(i["colegio"], []).append(i["id"])
    colegios = sorted(por_colegio)
    random.Random(n.SEMILLA_BASE).shuffle(colegios)
    total = sum(len(v) for v in por_colegio.values())
    lados: dict[str, list[str]] = {"entrenamiento": [], "validacion": [], "prueba": []}
    colegios_de: dict[str, list[str]] = {k: [] for k in lados}
    for c in colegios:
        if len(lados["entrenamiento"]) < 0.6 * total:
            lado = "entrenamiento"
        elif len(lados["validacion"]) < 0.2 * total:
            lado = "validacion"
        else:
            lado = "prueba"
        lados[lado].extend(por_colegio[c])
        colegios_de[lado].append(c)
    return {**lados, "colegios": colegios_de}  # type: ignore[dict-item]


def cargar(id_lista: str):
    inst = next(i for i in n.instancias() if i["id"] == id_lista)
    dec = n.decidibles(n.renglones_de(inst))
    return dec, n.opciones_de(dec)


def _referencia(id_lista: str):
    dec, ops = cargar(id_lista)
    lo, hi = n.limites_costo(dec, ops)
    return dec, ops, lo, hi, n.hipervolumen(n.frente_exacto_por_podas(dec, ops, {}), lo, hi)


def _trabajo(args):
    id_lista, a, b, semillas = args
    opt._poblacion = poblacion_con(a)
    opt._generaciones = generaciones_con(b)
    dec, ops, lo, hi, hv_ref = _referencia(id_lista)
    razones, tiempos = [], []
    for s in semillas:
        t0 = time.perf_counter()
        f = opt._frente_nsga(dec, ops, {}, semilla=s)
        tiempos.append(time.perf_counter() - t0)
        razones.append(n.hipervolumen(f, lo, hi) / hv_ref if hv_ref > 0 else 1.0)
    evals = opt._poblacion(len(dec)) * opt._generaciones(n.espacio_de(ops))
    return {"lista": id_lista, "a": a, "b": b, "razon": razones, "t": tiempos, "evals": evals}


def correr_rejilla(ids: list[str], semillas, procesos: int) -> list[dict]:
    trabajos = [(i, a, b, semillas) for i in ids for a, b in product(FACTORES, FACTORES)]
    with ProcessPoolExecutor(max_workers=procesos) as ex:
        return list(ex.map(_trabajo, trabajos, chunksize=8))


def resumen_por_config(filas: list[dict]) -> list[dict]:
    out = []
    for a, b in product(FACTORES, FACTORES):
        fs = [f for f in filas if f["a"] == a and f["b"] == b]
        por_lista = [float(np.mean(f["razon"])) for f in fs]
        out.append(
            {
                "a": a,
                "b": b,
                "listas": len(fs),
                "hv_medio": float(np.mean(por_lista)),
                "hv_min_lista": float(np.min(por_lista)),
                "t_medio_s": float(np.mean([np.mean(f["t"]) for f in fs])),
                "evals_medios": float(np.mean([f["evals"] for f in fs])),
            }
        )
    return out


def elegir(res_val: list[dict]) -> dict:
    mejor = max(r["hv_medio"] for r in res_val)
    admisibles = [r for r in res_val if r["hv_medio"] >= mejor - UMBRAL_HV]
    return min(admisibles, key=lambda r: (r["evals_medios"], -r["hv_medio"]))


def ic_bootstrap(x: np.ndarray, rng: np.random.Generator, k: int = 10_000) -> list[float]:
    medias = [x[rng.integers(0, len(x), len(x))].mean() for _ in range(k)]
    return [float(v) for v in np.percentile(medias, [2.5, 97.5])]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rapido", action="store_true")
    ap.add_argument("--procesos", type=int, default=8)
    args = ap.parse_args()

    grandes = []
    for i in n.instancias():
        dec = n.decidibles(n.renglones_de(i))
        if dec and n.espacio_de(n.opciones_de(dec)) > opt.LIMITE_ENUMERACION:
            grandes.append(i)
    lados = particion(grandes)
    if args.rapido:
        for k in ("entrenamiento", "validacion", "prueba"):
            lados[k] = lados[k][:3]
    sem_ent = SEMILLAS_ENTRENAMIENTO[:1] if args.rapido else SEMILLAS_ENTRENAMIENTO
    sem_val = SEMILLAS_VALIDACION[:2] if args.rapido else SEMILLAS_VALIDACION
    sem_pru = SEMILLAS_PRUEBA[:3] if args.rapido else SEMILLAS_PRUEBA

    salida: dict = {
        "hardware": n.hardware(),
        "listas_grandes": len(grandes),
        "particion": {k: len(lados[k]) for k in ("entrenamiento", "validacion", "prueba")},
        "colegios": lados["colegios"],
        "factores": list(FACTORES),
        "umbral_hv": UMBRAL_HV,
        "referencia_hv": n.REFERENCIA,
    }

    ent = correr_rejilla(lados["entrenamiento"], sem_ent, args.procesos)
    val = correr_rejilla(lados["validacion"], sem_val, args.procesos)
    salida["entrenamiento"] = resumen_por_config(ent)
    salida["validacion"] = resumen_por_config(val)
    elegida = elegir(salida["validacion"])
    salida["elegida"] = {"a": elegida["a"], "b": elegida["b"]}
    print("elegida", salida["elegida"], flush=True)

    # Prueba: una sola vez, en serie para medir tiempo con la maquina libre.
    por_config: dict[str, list[dict]] = {}
    for nombre, (a, b) in (("actual", (1.0, 1.0)), ("elegida", (elegida["a"], elegida["b"]))):
        por_config[nombre] = [_trabajo((i, a, b, sem_pru)) for i in lados["prueba"]]
    hv_a = np.array([np.mean(f["razon"]) for f in por_config["actual"]])
    hv_e = np.array([np.mean(f["razon"]) for f in por_config["elegida"]])
    t_a = np.array([np.mean(f["t"]) for f in por_config["actual"]])
    t_e = np.array([np.mean(f["t"]) for f in por_config["elegida"]])
    rng = np.random.default_rng(n.SEMILLA_BASE)
    dif = hv_e - hv_a
    try:
        p_hv = float(stats.wilcoxon(hv_e, hv_a).pvalue) if np.any(dif != 0) else 1.0
    except ValueError:
        p_hv = 1.0
    p_t = float(stats.wilcoxon(t_e, t_a).pvalue)
    salida["prueba"] = {
        "listas": len(lados["prueba"]),
        "semillas": len(sem_pru),
        "actual": {"hv_medio": float(hv_a.mean()), "hv_min": float(hv_a.min()), "t_medio_s": float(t_a.mean()), "t_max_s": float(t_a.max())},
        "elegida": {"hv_medio": float(hv_e.mean()), "hv_min": float(hv_e.min()), "t_medio_s": float(t_e.mean()), "t_max_s": float(t_e.max())},
        "dif_hv_elegida_menos_actual": {"media": float(dif.mean()), "ic95": ic_bootstrap(dif, rng), "wilcoxon_p": p_hv},
        "dif_t_s_elegida_menos_actual": {"media": float((t_e - t_a).mean()), "ic95": ic_bootstrap(t_e - t_a, rng), "wilcoxon_p": p_t},
        "razon_por_semilla_actual": [r for f in por_config["actual"] for r in f["razon"]],
        "razon_por_semilla_elegida": [r for f in por_config["elegida"] for r in f["razon"]],
    }
    n.guardar("calibracion_nsga.json" if not args.rapido else "calibracion_nsga_rapido.json", salida)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
