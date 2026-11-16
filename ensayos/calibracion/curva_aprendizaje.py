"""Curva de aprendizaje: ¿mejora el sistema con cada lista revisada?

Simulacion en memoria (sin tocar la base) del lazo "corregir el concepto de un renglon agrega su
texto como sinonimo del concepto correcto". Para cada orden de listas: por cada lista nueva se mide,
ANTES de aprender de ella, la fraccion de sus renglones resuelta de forma automatica (puntaje >= tau)
y correcta; despues el catalogo en memoria aprende de las correcciones de esa lista. Se promedian
20 ordenes aleatorios. Se mide tambien el mismo recorrido SIN aprender (control: separa aprendizaje
de azar de que listas tocan primero) y aprendiendo de todo renglon aprobado (cota alta).

Dos catalogos de partida (ver aprendizaje.py): "actual" (el de hoy menos 21 sinonimos aprendidos;
optimista, trae sinonimos sembrados) y "frio" (solo nombres de concepto).
Ordenes: "listas" (permutacion aleatoria de las 80 listas) y "colegios" (colegios completos en
orden aleatorio, listas al azar dentro de cada uno: como llegan en la vida real).

Uso: uv run python ensayos/calibracion/curva_aprendizaje.py
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
import aprendizaje as ap  # noqa: E402
import barrido as b  # noqa: E402
import clasificacion as k  # noqa: E402

ORDENES = 20
SEMILLA = 20261101
METRICAS = ("auto_correcta", "exactitud", "aceptada", "precision_aceptada")


def orden_de(cx: b.Contexto, tipo: str, rng: np.random.Generator) -> list[str]:
    listas = sorted(set(cx.lista))
    if tipo == "listas":
        return list(rng.permutation(listas))
    colegios = sorted(set(cx.colegio))
    salida = []
    for c in rng.permutation(colegios):
        propias = [l for l in listas if l.startswith(f"{c}|")]
        salida += list(rng.permutation(propias))
    return salida


def recorrer(sim: ap.Simulador, orden: list[str], frio: bool, modo: str) -> dict:
    cx = sim.cx
    act = k.ACTUAL
    activa = sim.inicial(frio)
    serie = {m: [] for m in METRICAS}
    nuevos = []
    for l in orden:
        filas = np.where(cx.lista == l)[0]
        p, s = sim.evaluar(activa, filas)
        m = k.metricas(p, s, cx.y[filas], act["corte"], act["tau"])
        for x in METRICAS:
            serie[x].append(m[x] if m[x] is not None else np.nan)
        if modo != "sin_aprender":
            pc = np.where(s >= act["corte"], p, -1)
            nuevos.append(sim.ensenar(activa, filas, pc, todo=(modo == "todo")))
        else:
            nuevos.append(0)
    serie["sinonimos_nuevos"] = nuevos
    return serie


def resumen(series: list[dict]) -> dict:
    out = {}
    for m in METRICAS:
        a = np.array([s[m] for s in series], dtype=float)  # (ordenes, listas)
        out[m] = {
            "media_por_posicion": np.nanmean(a, 0).tolist(),
            "p05": np.nanpercentile(a, 5, 0).tolist(),
            "p95": np.nanpercentile(a, 95, 0).tolist(),
        }
        primeras, ultimas = np.nanmean(a[:, :10], 1), np.nanmean(a[:, -10:], 1)
        t = np.arange(a.shape[1])
        pend = [np.polyfit(t, fila, 1)[0] for fila in np.where(np.isnan(a), np.nanmean(a), a)]
        out[m].update(
            {
                "media_primeras_10_listas": float(primeras.mean()),
                "media_ultimas_10_listas": float(ultimas.mean()),
                "ganancia_ultimas_menos_primeras_pp": float(100 * (ultimas - primeras).mean()),
                "ganancia_rango_entre_ordenes_pp": [float(100 * (ultimas - primeras).min()), float(100 * (ultimas - primeras).max())],
                "pendiente_pp_por_lista": float(100 * np.mean(pend)),
                "media_global": float(np.nanmean(a)),
            }
        )
    out["sinonimos_nuevos_total_media"] = float(np.mean([sum(s["sinonimos_nuevos"]) for s in series]))
    return out


def main() -> int:
    t0 = time.time()
    cx = b.Contexto()
    sim = ap.Simulador(cx)
    sal = {
        "descripcion": "Curva de aprendizaje simulada; medicion ANTES de aprender de cada lista; media de 20 ordenes.",
        "tau": k.ACTUAL["tau"],
        "ordenes": ORDENES,
        "listas": len(set(cx.lista)),
        "sinonimos_aprendidos_ya_en_el_sistema_que_se_quitan": sim.n_aprendidos,
        "escenarios": {},
    }
    for tipo in ("listas", "colegios"):
        for frio in (False, True):
            for modo in ("correcciones", "todo", "sin_aprender"):
                series = []
                for o in range(ORDENES):
                    rng = np.random.default_rng(SEMILLA + o)
                    series.append(recorrer(sim, orden_de(cx, tipo, rng), frio, modo))
                nombre = f"{tipo}|{'frio' if frio else 'actual'}|{modo}"
                sal["escenarios"][nombre] = resumen(series)
                r = sal["escenarios"][nombre]["auto_correcta"]
                print(nombre, round(100 * r["media_primeras_10_listas"], 1), round(100 * r["media_ultimas_10_listas"], 1), round(r["ganancia_ultimas_menos_primeras_pp"], 2), round(r["pendiente_pp_por_lista"], 3), flush=True)
    (k.SALIDA / "curva_aprendizaje.json").write_text(json.dumps(sal, ensure_ascii=False, indent=1, default=float), encoding="utf-8")
    figura(sal)
    print("segundos", round(time.time() - t0))
    return 0


def figura(sal: dict) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    AZUL, NARANJA, GRIS = "#1F4E86", "#A8500F", "#4D4D4D"
    plt.rcParams.update({"font.family": "serif", "font.size": 8, "axes.spines.top": False, "axes.spines.right": False})
    fig, ejes = plt.subplots(1, 2, figsize=(6.3 * 1.2, 2.8), sharey=False)
    for ax, (frio, titulo) in zip(ejes, ((False, "catalogo actual (sin 21 aprendidos)"), (True, "catalogo frio (solo nombres)")), strict=True):
        pref = f"listas|{'frio' if frio else 'actual'}|"
        for modo, color, est, et in (("correcciones", AZUL, "-", "aprende de correcciones"), ("sin_aprender", GRIS, "--", "sin aprender")):
            r = sal["escenarios"][pref + modo]["auto_correcta"]
            y = 100 * np.array(r["media_por_posicion"])
            x = np.arange(len(y))
            w = 5
            ys = np.convolve(np.pad(y, (w // 2, w // 2), mode="edge"), np.ones(w) / w, mode="valid")
            ax.plot(x, ys, color=color, ls=est, lw=1.3, label=et)
            if modo == "correcciones":
                ax.fill_between(x, 100 * np.array(r["p05"]), 100 * np.array(r["p95"]), color=color, alpha=0.12, lw=0, label="p5-p95 de las listas")
        ax.set_title(titulo, fontsize=8)
        ax.set_xlabel("listas ya vistas")
        ax.set_ylabel("resuelto automatico y correcto (%)")
        ax.legend(frameon=False, fontsize=7, loc="lower right")
    fig.tight_layout()
    fig.savefig(k.SALIDA / "curva_aprendizaje.pdf")


if __name__ == "__main__":
    raise SystemExit(main())
