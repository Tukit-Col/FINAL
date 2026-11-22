"""Un colegio nuevo: dejar un colegio fuera (leave-one-school-out) entre los 7.
Uso: uv run python ensayos/calibracion/generalizacion.py"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
import aprendizaje as ap  # noqa: E402
import barrido as b  # noqa: E402
import clasificacion as k  # noqa: E402
import seleccion as sel  # noqa: E402

MIN_RENGLONES = 150
ORDENES = 5


def ic_listas(
    cx: b.Contexto, mask: np.ndarray, p: np.ndarray, s: np.ndarray, corte: float, rep: int = 1000
) -> list[float] | None:
    ok = np.where(s >= corte, p, -1) == cx.y
    listas = np.unique(cx.lista[mask])
    if len(listas) < 3:
        return None
    por = {l: np.where(mask & (cx.lista == l))[0] for l in listas}
    rng = np.random.default_rng(20261101)
    v = [
        100 * ok[np.concatenate([por[l] for l in rng.choice(listas, len(listas))])].mean() for _ in range(rep)
    ]
    return [float(np.percentile(v, 2.5)), float(np.percentile(v, 97.5))]


def main() -> int:
    cx = b.Contexto()
    esp = sel.Espacio(cx)
    sim = ap.Simulador(cx)
    colegios = sorted(set(cx.colegio), key=lambda c: -int((cx.colegio == c).sum()))
    filas_sal = []
    act = k.ACTUAL
    for col in colegios:
        pr = cx.colegio == col
        tr = ~pr
        eleg = esp.elegir(tr)
        cfg = eleg["cfg"]
        p_a, s_a = cx.puntuar(act)
        fila = {
            "colegio": col,
            "renglones": int(pr.sum()),
            "listas": int(len(set(cx.lista[pr]))),
            "poco_confiable": bool(pr.sum() < MIN_RENGLONES or len(set(cx.lista[pr])) < 5),
            "etiquetas_sin_concepto": int((cx.y[pr] < 0).sum()),
            "constantes_elegidas_con_los_otros_6": cfg,
            "taus_con_los_otros_6": eleg["taus"],
            "elegido_es_el_actual": eleg["es_el_actual"],
            "actual_tau_0.75": esp.medir(act, pr, act["tau"]),
            "elegido_tau_0.75": esp.medir(cfg, pr, act["tau"]),
            "elegido_tau_regla_0.98": esp.medir(cfg, pr, eleg["taus"]["0.98"]),
            "actual_tau_regla_0.98": esp.medir(act, pr, eleg["taus"]["0.98"]),
            "ic95_exactitud_actual_por_listas": ic_listas(cx, pr, p_a, s_a, act["corte"]),
        }
        listas_tr = sorted(set(cx.lista[tr]))
        res = []
        sin_aprender = None
        for o in range(ORDENES):
            rng = np.random.default_rng(20261101 + o)
            activa = sim.inicial(frio=True)
            for l in rng.permutation(listas_tr):
                filas = np.where(cx.lista == l)[0]
                p, s = sim.evaluar(activa, filas)
                pc = np.where(s >= act["corte"], p, -1)
                sim.ensenar(activa, filas, pc)
            filas_pr = np.where(pr)[0]
            p, s = sim.evaluar(activa, filas_pr)
            res.append(k.metricas(p, s, cx.y[filas_pr], act["corte"], act["tau"]))
        p0, s0 = sim.evaluar(sim.inicial(frio=True), np.where(pr)[0])
        sin_aprender = k.metricas(p0, s0, cx.y[pr], act["corte"], act["tau"])
        fila["frio_sin_aprender"] = sin_aprender
        fila["frio_aprendiendo_de_los_otros_6"] = {
            m: float(np.mean([r[m] for r in res])) for m in res[0] if m != "n"
        } | {"rango_exactitud": [min(r["exactitud"] for r in res), max(r["exactitud"] for r in res)]}
        filas_sal.append(fila)
        print(
            col[:28],
            fila["renglones"],
            round(100 * fila["actual_tau_0.75"]["exactitud"], 1),
            round(100 * fila["elegido_tau_0.75"]["exactitud"], 1),
            round(100 * fila["frio_sin_aprender"]["exactitud"], 1),
            round(100 * fila["frio_aprendiendo_de_los_otros_6"]["exactitud"], 1),
        )

    def micro(clave, m):
        return float(np.mean([f[clave][m] for f in filas_sal]))

    sal = {
        "descripcion": "Leave-one-school-out entre los 7 colegios. Ver docstring de generalizacion.py.",
        "min_renglones_para_confiar": MIN_RENGLONES,
        "colegios": filas_sal,
        "media_simple_7_colegios": {
            v: {m: micro(v, m) for m in ("exactitud", "aceptada", "precision_aceptada", "revision_humana")}
            for v in ("actual_tau_0.75", "elegido_tau_0.75", "elegido_tau_regla_0.98", "frio_sin_aprender")
        }
        | {
            "frio_aprendiendo_de_los_otros_6": {
                m: micro("frio_aprendiendo_de_los_otros_6", m)
                for m in ("exactitud", "aceptada", "precision_aceptada", "revision_humana")
            }
        },
        "elegido_menos_actual_exactitud_pp": [
            100 * (f["elegido_tau_0.75"]["exactitud"] - f["actual_tau_0.75"]["exactitud"]) for f in filas_sal
        ],
    }
    (k.SALIDA / "generalizacion.json").write_text(
        json.dumps(sal, ensure_ascii=False, indent=1, default=float), encoding="utf-8"
    )
    print(sal["media_simple_7_colegios"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
