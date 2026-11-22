"""Particion 70/15/15 por LISTA (colegio, grado), sin fuga, repetida con 20 semillas.
Uso: uv run python ensayos/calibracion/particion.py"""

from __future__ import annotations

import collections
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
import barrido as b  # noqa: E402
import clasificacion as k  # noqa: E402
import seleccion as sel  # noqa: E402

SEMILLA_BASE = 20261101
SEMILLAS = 20


def partir(listas: list[str], semilla: int) -> dict[str, list[str]]:
    rng = np.random.default_rng(semilla)
    orden = list(rng.permutation(listas))
    n = len(orden)
    n_val, n_pru = round(0.15 * n), round(0.15 * n)
    return {"entrenamiento": orden[: n - n_val - n_pru], "validacion": orden[n - n_val - n_pru : n - n_pru], "prueba": orden[n - n_pru :]}


def main() -> int:
    cx = b.Contexto()
    esp = sel.Espacio(cx)
    listas = sorted(set(cx.lista))
    colegios = sorted(set(cx.colegio))
    por_semilla = []
    cuentas_colegio = {p: {c: [] for c in colegios} for p in ("entrenamiento", "validacion", "prueba")}
    for i in range(SEMILLAS):
        sem = SEMILLA_BASE + i
        parte = partir(listas, sem)
        mask = {p: np.isin(cx.lista, ls) for p, ls in parte.items()}
        eleg = esp.elegir(mask["entrenamiento"], mask["validacion"])
        cfg = eleg["cfg"]
        fila = {
            "semilla": sem,
            "listas": {p: len(v) for p, v in parte.items()},
            "renglones": {p: int(mask[p].sum()) for p in parte},
            "elegido": cfg,
            "taus": eleg["taus"],
            "elegido_es_el_actual": eleg["es_el_actual"],
            "empates_en_entrenamiento": eleg["empates_en_train"],
        }
        for p in parte:
            for c in colegios:
                cuentas_colegio[p][c].append(int((mask[p] & (cx.colegio == c)).sum()))
        act = k.ACTUAL
        pr = mask["prueba"]
        fila["prueba"] = {
            "actual_tau_0.75": esp.medir(act, pr, act["tau"]),
            "elegido_tau_0.75": esp.medir(cfg, pr, act["tau"]),
            "elegido_tau_regla_0.95": esp.medir(cfg, pr, eleg["taus"]["0.95"]),
            "elegido_tau_regla_0.98": esp.medir(cfg, pr, eleg["taus"]["0.98"]),
            "actual_tau_regla_0.98": esp.medir(act, pr, eleg["taus"]["0.98"]),
        }
        fila["entrenamiento"] = {"actual_tau_0.75": esp.medir(act, mask["entrenamiento"], act["tau"]), "elegido_tau_0.75": esp.medir(cfg, mask["entrenamiento"], act["tau"])}
        fila["validacion"] = {"actual_tau_0.75": esp.medir(act, mask["validacion"], act["tau"]), "elegido_tau_0.75": esp.medir(cfg, mask["validacion"], act["tau"])}
        por_semilla.append(fila)

    agg: dict = {}
    for variante in por_semilla[0]["prueba"]:
        agg[variante] = {m: sel.resumen([f["prueba"][variante][m] for f in por_semilla]) for m in ("exactitud", "aceptada", "precision_aceptada", "auto_correcta", "revision_humana")}
    dif = [100 * (f["prueba"]["elegido_tau_0.75"]["exactitud"] - f["prueba"]["actual_tau_0.75"]["exactitud"]) for f in por_semilla]
    gap_train = [100 * (f["entrenamiento"]["elegido_tau_0.75"]["exactitud"] - f["entrenamiento"]["actual_tau_0.75"]["exactitud"]) for f in por_semilla]
    freq = collections.Counter(json.dumps({x: f["elegido"][x] for x in (*k.CLAVES_PUNTAJE, "corte")}) for f in por_semilla)
    sal = {
        "descripcion": "Particion por lista (colegio, grado) 70/15/15, 20 semillas. Seleccion en entrenamiento+validacion, medida una vez en prueba.",
        "espacio_de_busqueda": {"puntaje": b.ESPACIO, "cortes": b.CORTES, "combinaciones": esp.n_combinaciones, "tau": "regla del menor tau con precision >= 0.95 y >= 0.98 sobre entrenamiento"},
        "listas_totales": len(listas),
        "renglones_totales": int(len(cx.y)),
        "conteo_por_particion_semilla_1": {p: {"listas": por_semilla[0]["listas"][p], "renglones": por_semilla[0]["renglones"][p]} for p in por_semilla[0]["listas"]},
        "listas_por_particion": {"valores": sorted({tuple(f["listas"].values()) for f in por_semilla})},
        "renglones_por_particion_media_y_rango": {p: sel.resumen([f["renglones"][p] for f in por_semilla]) for p in ("entrenamiento", "validacion", "prueba")},
        "renglones_por_colegio_y_particion_media_y_rango": {p: {c: sel.resumen(v) for c, v in d.items()} for p, d in cuentas_colegio.items()},
        "prueba_media_y_rango_20_semillas": agg,
        "prueba_elegido_menos_actual_exactitud_pp": {**sel.resumen(dif), "semillas_en_que_gana": int(sum(1 for x in dif if x > 1e-9)), "empata": int(sum(1 for x in dif if abs(x) <= 1e-9)), "pierde": int(sum(1 for x in dif if x < -1e-9))},
        "entrenamiento_elegido_menos_actual_exactitud_pp": sel.resumen(gap_train),
        "semillas_en_que_lo_elegido_es_el_actual": int(sum(f["elegido_es_el_actual"] for f in por_semilla)),
        "combinaciones_elegidas": [{"combinacion": json.loads(c), "veces": n} for c, n in freq.most_common()],
        "por_semilla": por_semilla,
    }
    ruta = k.SALIDA / "particion.json"
    ruta.write_text(json.dumps(sal, ensure_ascii=False, indent=1, default=float), encoding="utf-8")
    print(sal["conteo_por_particion_semilla_1"], sal["renglones_por_particion_media_y_rango"])
    print({v: (round(100 * a["exactitud"]["media"], 2), round(100 * a["exactitud"]["min"], 2), round(100 * a["exactitud"]["max"], 2), round(100 * a["aceptada"]["media"], 1), round(100 * a["precision_aceptada"]["media"], 2)) for v, a in agg.items()})
    print(sal["prueba_elegido_menos_actual_exactitud_pp"], sal["semillas_en_que_lo_elegido_es_el_actual"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
