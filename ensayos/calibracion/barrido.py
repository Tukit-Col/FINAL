"""Barrido de las constantes de decision de la resolucion hibrida (descubrir.clasificar).
Uso: uv run python ensayos/calibracion/barrido.py"""

from __future__ import annotations

import itertools
import json
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
import clasificacion as k  # noqa: E402

OBJETIVO_PRECISION = 0.95
ACTUAL = k.ACTUAL

REJILLAS = {
    "piso": [round(x, 3) for x in np.arange(0.30, 0.9001, 0.05)],
    "w_jac": [round(x, 3) for x in np.arange(0.0, 0.8001, 0.05)],
    "w_cos": [round(x, 3) for x in np.arange(0.0, 0.5001, 0.05)],
    "res_cos": [round(x, 3) for x in np.arange(0.70, 0.9801, 0.02)] + [1.01],
    "res_piso": [round(x, 3) for x in np.arange(0.40, 0.8001, 0.05)],
    "corte": [round(x, 3) for x in np.arange(0.30, 0.8001, 0.05)],
    "tau": [round(x, 3) for x in np.arange(0.50, 1.0001, 0.025)],
}
NOMBRES = {
    "piso": "piso de la cabeza (0,6)",
    "w_jac": "peso del Jaccard (0,4)",
    "w_cos": "peso del coseno (0,15)",
    "res_cos": "coseno minimo del rescate (0,86)",
    "res_piso": "piso del rescate (0,55)",
    "corte": "corte de sin correspondencia (0,5)",
    "tau": "tau de aceptacion automatica (0,75)",
}
ESPACIO = {
    "piso": [0.5, 0.6, 0.7],
    "w_jac": [0.3, 0.4, 0.5],
    "w_cos": [0.0, 0.15, 0.3],
    "res_cos": [0.80, 0.86, 0.92],
    "res_piso": [0.5, 0.55, 0.65],
}
CORTES = [0.4, 0.45, 0.5, 0.55, 0.6]


class Contexto:

    def __init__(self, con_vectores: bool = True):
        self.d = k.cargar(con_vectores)
        self.r = k.construir_rasgos(self.d)
        self.y = k.etiquetas(self.d)
        self.u = np.array([f["u"] for f in self.d.filas])
        self.lista = np.array([f["lista"] for f in self.d.filas])
        self.colegio = np.array([f["colegio"] for f in self.d.filas])
        self._cache: dict[tuple, tuple[np.ndarray, np.ndarray]] = {}

    def puntuar(self, cfg: dict) -> tuple[np.ndarray, np.ndarray]:
        clave = tuple(round(cfg[c], 6) for c in k.CLAVES_PUNTAJE)
        if clave not in self._cache:
            idx, s = k.puntuar(self.r, cfg)
            self._cache[clave] = (idx[self.u], s[self.u])
        return self._cache[clave]

    def medir(self, cfg: dict, mask: np.ndarray | None = None) -> dict:
        p, s = self.puntuar(cfg)
        m = np.ones(len(self.y), bool) if mask is None else mask
        return k.metricas(p[m], s[m], self.y[m], cfg["corte"], cfg["tau"])


def regla_tau(s: np.ndarray, pred_c: np.ndarray, y: np.ndarray, corte: float, objetivo: float = OBJETIVO_PRECISION) -> float:
    ok = pred_c == y
    for t in np.unique(s[s >= corte]):
        ac = (s >= t) & (pred_c >= 0)
        if ac.sum() and (ac & ok).sum() / ac.sum() >= objetivo:
            return float(t)
    return 1.0


def meseta(valores: list[float], medida: list[float], tolerancia: float) -> list[float]:
    mejor = int(np.argmax(medida))
    tope = max(medida)
    a = b = mejor
    while a > 0 and medida[a - 1] >= tope - tolerancia - 1e-12:
        a -= 1
    while b < len(valores) - 1 and medida[b + 1] >= tope - tolerancia - 1e-12:
        b += 1
    return [valores[a], valores[b]]


def barrido_unico(cx: Contexto) -> dict:
    salida: dict = {}
    for clave, valores in REJILLAS.items():
        filas = []
        for v in valores:
            cfg = {**ACTUAL, clave: v}
            m = cx.medir(cfg)
            filas.append({"valor": v, **m})
        ex = [f["exactitud"] for f in filas]
        i_act = int(np.argmin([abs(v - ACTUAL[clave]) for v in valores]))
        rango = int(sum(1 for e in ex if e > ex[i_act] + 1e-12)) + 1
        info = {
            "nombre": NOMBRES[clave],
            "valor_actual": ACTUAL[clave],
            "combinaciones_probadas": len(valores),
            "valores": filas,
        }
        if clave == "tau":
            p, s = cx.puntuar(ACTUAL)
            pc = np.where(s >= ACTUAL["corte"], p, -1)
            t_regla = regla_tau(s, pc, cx.y, ACTUAL["corte"])
            m_regla = k.metricas(p, s, cx.y, ACTUAL["corte"], t_regla)
            m_act = cx.medir(ACTUAL)
            info.update(
                {
                    "objetivo": f"menor tau con precision_aceptada >= {OBJETIVO_PRECISION}",
                    "tau_regla": t_regla,
                    "tau_minimo_por_precision_objetivo": {
                        str(o): regla_tau(s, pc, cx.y, ACTUAL["corte"], o) for o in (0.95, 0.96, 0.97, 0.98, 0.99)
                    },
                    "metricas_en_tau_regla": m_regla,
                    "metricas_en_tau_actual": m_act,
                    "tau_actual_cumple_objetivo": bool(
                        m_act["precision_aceptada"] is not None and m_act["precision_aceptada"] >= OBJETIVO_PRECISION
                    ),
                    "diferencia_aceptada_pp": 100 * (m_regla["aceptada"] - m_act["aceptada"]),
                    "diferencia_precision_pp": 100 * (m_regla["precision_aceptada"] - m_act["precision_aceptada"]),
                    "meseta_aceptada_a_precision_ge_0.95": [
                        f["valor"] for f in filas if f["precision_aceptada"] is not None and f["precision_aceptada"] >= OBJETIVO_PRECISION
                    ][:1]
                    + [filas[-1]["valor"]],
                }
            )
        else:
            mejor = int(np.argmax(ex))
            info.update(
                {
                    "objetivo": "exactitud del concepto",
                    "valor_optimo": valores[mejor],
                    "exactitud_optima": ex[mejor],
                    "exactitud_actual": ex[i_act],
                    "diferencia_optimo_menos_actual_pp": 100 * (ex[mejor] - ex[i_act]),
                    "puesto_del_actual": rango,
                    "actual_es_el_mejor": bool(ex[i_act] >= ex[mejor] - 1e-12),
                    "valores_empatados_con_el_mejor": [v for v, e in zip(valores, ex, strict=True) if e >= ex[mejor] - 1e-12],
                    "meseta_dentro_de_0.1pp": meseta(valores, ex, 0.001),
                    "meseta_dentro_de_0.5pp": meseta(valores, ex, 0.005),
                    "actual_dentro_de_meseta_0.5pp": bool(
                        meseta(valores, ex, 0.005)[0] <= ACTUAL[clave] <= meseta(valores, ex, 0.005)[1]
                    ),
                }
            )
        salida[clave] = info
    return salida


def ic_diferencia_por_lista(cx: Contexto, cfg_a: dict, cfg_b: dict, repeticiones: int = 1000) -> dict:
    pa, sa = cx.puntuar(cfg_a)
    pb, sb = cx.puntuar(cfg_b)
    oka = np.where(sa >= cfg_a["corte"], pa, -1) == cx.y
    okb = np.where(sb >= cfg_b["corte"], pb, -1) == cx.y
    listas = np.unique(cx.lista)
    por = {l: np.where(cx.lista == l)[0] for l in listas}
    rng = np.random.default_rng(20261101)
    difs = []
    for _ in range(repeticiones):
        sel = rng.choice(listas, len(listas))
        ii = np.concatenate([por[l] for l in sel])
        difs.append(100 * (oka[ii].mean() - okb[ii].mean()))
    return {"media_pp": float(np.mean(difs)), "ic95_pp": [float(np.percentile(difs, 2.5)), float(np.percentile(difs, 97.5))]}


def barrido_conjunto(cx: Contexto) -> dict:
    t0 = time.time()
    lex = list(
        itertools.product([0.5, 0.55, 0.6, 0.65, 0.7], [0.2, 0.3, 0.4, 0.5, 0.6], [0.4, 0.45, 0.5, 0.55, 0.6], [0.6, 0.65, 0.7, 0.75, 0.8, 0.85, 0.9])
    )
    filas = []
    for piso, wj, corte, tau in lex:
        cfg = {**ACTUAL, "piso": piso, "w_jac": wj, "corte": corte, "tau": tau}
        filas.append({"piso": piso, "w_jac": wj, "corte": corte, "tau": tau, **cx.medir(cfg)})
    hib = list(itertools.product([0.0, 0.1, 0.15, 0.2, 0.3], [0.80, 0.84, 0.86, 0.90, 0.94], [0.5, 0.55, 0.6, 0.7]))
    filas_h = []
    for wc, rc, rp in hib:
        cfg = {**ACTUAL, "w_cos": wc, "res_cos": rc, "res_piso": rp}
        filas_h.append({"w_cos": wc, "res_cos": rc, "res_piso": rp, **cx.medir(cfg)})

    def resumen(filas_, claves):
        act = next(f for f in filas_ if all(abs(f[c] - ACTUAL[c]) < 1e-9 for c in claves))
        mejor = max(f["exactitud"] for f in filas_)
        mejores = [f for f in filas_ if f["exactitud"] >= mejor - 1e-12]
        sup = sum(1 for f in filas_ if f["exactitud"] > act["exactitud"] + 1e-12)
        return {
            "combinaciones": len(filas_),
            "exactitud_actual": act["exactitud"],
            "exactitud_maxima": mejor,
            "diferencia_pp": 100 * (mejor - act["exactitud"]),
            "combinaciones_mejores_que_el_actual": sup,
            "combinaciones_empatadas_con_el_maximo": len(mejores),
            "puesto_del_actual": sup + 1,
            "ejemplos_del_maximo": mejores[:5],
        }

    ok = [f for f in filas if f["precision_aceptada"] is not None and f["precision_aceptada"] >= OBJETIVO_PRECISION]
    mej = max(ok, key=lambda f: f["auto_correcta"]) if ok else None
    act = next(f for f in filas if all(abs(f[c] - ACTUAL[c]) < 1e-9 for c in ("piso", "w_jac", "corte", "tau")))
    return {
        "lexica": {"constantes": ["piso", "w_jac", "corte", "tau"], **resumen(filas, ("piso", "w_jac", "corte", "tau")), "filas": filas},
        "hibrida": {"constantes": ["w_cos", "res_cos", "res_piso"], **resumen(filas_h, ("w_cos", "res_cos", "res_piso")), "filas": filas_h},
        "lexica_mejor_auto_correcta_con_precision_ge_0.95": mej,
        "lexica_actual": act,
        "segundos": time.time() - t0,
    }


def solo_lexico(cx: Contexto) -> dict:
    cfg = {**ACTUAL, "w_cos": 0.0, "res_cos": 1.01}
    return {"lexico_puro": cx.medir(cfg), "hibrido_actual": cx.medir(ACTUAL)}


def diagnostico_rescate(cx: Contexto) -> dict:
    p0, s0 = cx.puntuar({**ACTUAL, "res_cos": 1.01})
    out: dict = {}
    for res in (0.70, 0.76, 0.80, 0.86):
        p, s = cx.puntuar({**ACTUAL, "res_cos": res})
        cam = p != p0
        out[str(res)] = {
            "renglones_que_cambian_de_concepto": int(cam.sum()),
            "de_esos_correctos_con_rescate": int(((p == cx.y) & cam).sum()),
            "de_esos_correctos_sin_rescate": int(((p0 == cx.y) & cam).sum()),
        }
    sin = (np.where(s0 >= ACTUAL["corte"], p0, -1) < 0) & (cx.y >= 0)
    out["renglones_con_concepto_aprobado_y_sin_correspondencia_del_sistema"] = int(sin.sum())
    cc = cx.r.cos
    mejor_concepto = np.full(len(cx.d.textos), -1)
    mejor_cos = np.zeros(len(cx.d.textos))
    for i in range(len(cx.d.conceptos)):
        cols = np.where(cx.r.col_concepto == i)[0]
        c = cc[:, cols[0]]
        m = c > mejor_cos
        mejor_cos[m], mejor_concepto[m] = c[m], i
    out["de_esos_cuyo_concepto_mas_cercano_por_coseno_es_el_aprobado"] = int((mejor_concepto[cx.u][sin] == cx.y[sin]).sum())
    return out


def figura(sal: dict) -> Path:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    AZUL, NARANJA, GRIS = "#1F4E86", "#A8500F", "#4D4D4D"
    plt.rcParams.update({"font.family": "serif", "font.size": 8, "axes.spines.top": False, "axes.spines.right": False})
    fig, ejes = plt.subplots(2, 4, figsize=(6.3 * 1.25, 3.9))
    for ax, clave in zip(ejes.flat, REJILLAS, strict=False):
        inf = sal["unico"][clave]
        v = [f["valor"] for f in inf["valores"]]
        if clave == "tau":
            ax.plot(v, [100 * f["precision_aceptada"] if f["precision_aceptada"] is not None else np.nan for f in inf["valores"]], color=AZUL, label="precision")
            ax.plot(v, [100 * f["aceptada"] for f in inf["valores"]], color=NARANJA, label="aceptada")
            ax.axhline(95, color=GRIS, lw=0.6, ls=":")
            ax.legend(frameon=False, fontsize=6.5)
        else:
            vv = [x if x <= 1.0 else 1.0 for x in v]
            ax.plot(vv, [100 * f["exactitud"] for f in inf["valores"]], color=AZUL, marker="o", ms=2.5, lw=1)
        ax.axvline(ACTUAL[clave], color=NARANJA, lw=0.8, ls="--")
        ax.set_title(inf["nombre"], fontsize=7)
        ax.set_xlabel("valor")
        ax.set_ylabel("%")
    ejes.flat[-1].axis("off")
    ejes.flat[-1].text(0, 0.6, "linea punteada: valor actual\nexactitud del concepto\n(3.037 renglones)", fontsize=7, va="top")
    fig.tight_layout()
    ruta = k.SALIDA / "barrido.pdf"
    fig.savefig(ruta)
    return ruta


def main() -> int:
    k.SALIDA.mkdir(parents=True, exist_ok=True)
    cx = Contexto()
    val = k.validar(cx.d, cx.r)
    colegios = {c: int((cx.colegio == c).sum()) for c in sorted(set(cx.colegio))}
    sal = {
        "descripcion": "Barrido de constantes de descubrir.clasificar sobre renglones etiquetados (concepto aprobado). Etiquetas = salida del propio sistema revisada por una persona: sesgo de confirmacion posible.",
        "datos": {
            "renglones": len(cx.y),
            "textos_unicos": len(cx.d.textos),
            "listas": len(set(cx.lista)),
            "colegios": colegios,
            "renglones_sin_concepto": int((cx.y < 0).sum()),
            "conceptos_en_catalogo": len(cx.d.conceptos),
            "conceptos_con_centroide": int(cx.d.tiene_cent.sum()),
            "vectores": "Gemini gemini-embedding-001 (1024), el embeder del sistema; centroides de producto_canonico.embedding",
        },
        "validacion_contra_el_sistema": val,
        "actual": {**ACTUAL, **cx.medir(ACTUAL)},
        "lexico_vs_hibrido": solo_lexico(cx),
        "unico": barrido_unico(cx),
        "rescate_diagnostico": diagnostico_rescate(cx),
        "conjunto": barrido_conjunto(cx),
    }
    for clave in ("piso", "w_jac", "w_cos", "res_cos", "res_piso", "corte"):
        inf = sal["unico"][clave]
        cfg = {**ACTUAL, clave: inf["valor_optimo"]}
        inf["ic95_bootstrap_listas_optimo_menos_actual"] = ic_diferencia_por_lista(cx, cfg, ACTUAL)
    sal["combinaciones_totales"] = (
        sum(v["combinaciones_probadas"] for v in sal["unico"].values())
        + sal["conjunto"]["lexica"]["combinaciones"]
        + sal["conjunto"]["hibrida"]["combinaciones"]
    )
    ruta = k.SALIDA / "barrido.json"
    ruta.write_text(json.dumps(sal, ensure_ascii=False, indent=1, default=float), encoding="utf-8")
    figura(sal)
    print("combinaciones", sal["combinaciones_totales"], "->", ruta)
    for c, inf in sal["unico"].items():
        if c == "tau":
            print(c, inf["tau_regla"], inf["metricas_en_tau_actual"]["precision_aceptada"], inf["diferencia_aceptada_pp"])
        else:
            print(c, inf["valor_optimo"], round(inf["diferencia_optimo_menos_actual_pp"], 3), inf["puesto_del_actual"], inf["meseta_dentro_de_0.5pp"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
