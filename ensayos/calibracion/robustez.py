"""Prueba de estres: las listas de PRUEBA, perturbadas, con las constantes (nada se entrena).
Uso: uv run python ensayos/calibracion/robustez.py   (requiere haber corrido aumentacion.py)"""

from __future__ import annotations

import json
import random
import sys
import time
import unicodedata
from difflib import SequenceMatcher
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
import aumentacion as a  # noqa: E402
import barrido as b  # noqa: E402
import clasificacion as k  # noqa: E402
from particion import SEMILLA_BASE, SEMILLAS, partir  # noqa: E402

TAU = 0.75
CONFIGS_FIJAS = {"lexico": a.LEXICO, "hibrido_actual": k.ACTUAL, "hibrido_sin_rescate": a.ACTUAL_SR}
CONFIGS = [*CONFIGS_FIJAS, "calibrado_limpio", "calibrado_aumentado"]


def medir_ext(p: np.ndarray, s: np.ndarray, y: np.ndarray, corte: float, tau: float) -> dict:
    pc = np.where(s >= corte, p, -1)
    ok = pc == y
    acepta = (s >= tau) & (pc >= 0)
    n = len(y)
    err = ~ok
    return {
        "exactitud": float(ok.mean()),
        "aceptada": float(acepta.mean()),
        "precision_aceptada": float((acepta & ok).sum() / acepta.sum()) if acepta.sum() else None,
        "revision_humana": float(1 - acepta.mean()),
        "aceptada_mal": float((acepta & err).sum() / n),
        "errores": float(err.mean()),
        "errores_que_van_a_revision": float((err & ~acepta).sum() / err.sum()) if err.sum() else None,
    }


def _norm(t: str) -> list[str]:
    t = "".join(c for c in unicodedata.normalize("NFD", t.lower()) if unicodedata.category(c) != "Mn")
    return sorted("".join(ch for ch in w if ch.isalnum()) for w in t.split() if any(ch.isalnum() for ch in w))


def similitud(o: str, p: str) -> float:
    return SequenceMatcher(None, " ".join(_norm(o)), " ".join(_norm(p))).ratio()


def ejemplos(cx: b.Contexto, estres: dict, n: int = 30) -> dict:
    r = random.Random(11)
    con_conc = [i for i, f in enumerate(cx.d.filas) if f["etiqueta"]]
    u_conc = sorted({cx.d.filas[i]["u"] for i in con_conc})
    nombre_de_u: dict[int, str] = {}
    for i in con_conc:
        nombre_de_u.setdefault(cx.d.filas[i]["u"], cx.d.conceptos[cx.y[i]]["nombre"])
    out = {}
    for tp in a.TIPOS_TODOS:
        lista = []
        for sv in (a.LEVE, a.FUERTE):
            cam = [u for u in u_conc if estres[(tp, sv)][u] != cx.d.textos[u]]
            for u in r.sample(cam, min(n // 2, len(cam))):
                lista.append({"severidad": sv, "original": cx.d.textos[u], "perturbado": estres[(tp, sv)][u], "concepto_aprobado": nombre_de_u[u], "similitud": round(similitud(cx.d.textos[u], estres[(tp, sv)][u]), 3)})
        auto = {}
        for sv in (a.LEVE, a.FUERTE):
            lst = estres[(tp, sv)]
            sim = np.array([similitud(cx.d.textos[u], lst[u]) for u in range(len(lst))])
            camb = np.array([lst[u] != cx.d.textos[u] for u in range(len(lst))])
            vacio = int(sum(1 for t in lst if not t.strip()))
            auto[sv] = {"cambia_el_texto": float(camb.mean()), "similitud_media_de_los_que_cambian": float(sim[camb].mean()) if camb.any() else None,
                        "similitud_minima": float(sim.min()), "vacios": vacio, "bajo_0.6": int((sim < 0.6).sum())}
        out[tp] = {"verificacion_automatica_todos_los_textos": auto, "ejemplos": lista}
    return out


def main() -> int:
    t0 = time.time()
    cx = b.Contexto()
    estres = a.conjuntos_de_estres(cx.d.textos)
    cache = a.vectorizar_nuevos({t for lst in estres.values() for t in lst} - set(cx.d.textos))
    print("llamadas a Gemini en esta corrida:", a.LLAMADAS, flush=True)
    cal = json.load((k.SALIDA / "calibracion_aumentada.json").open(encoding="utf-8"))["por_semilla"]
    conjuntos = {("limpio", "-"): cx} | {key: a.contexto_con_textos(cx, lst, cache) for key, lst in estres.items()}
    listas = sorted(set(cx.lista))
    partes = [partir(listas, SEMILLA_BASE + i) for i in range(SEMILLAS)]
    masc = [np.isin(cx.lista, p["prueba"]) for p in partes]
    cfg_sem = []
    for f in cal:
        cfg_sem.append({}) 
        for nom, ll in (("calibrado_limpio", "elegido_limpio"), ("calibrado_aumentado", "elegido_aumentado")):
            v = {**f[ll], "tau": f[ll]["taus"]["0.95"]}
            v.pop("taus")
            cfg_sem[-1][nom] = v
    res: dict = {}
    for key, c in conjuntos.items():
        nombre = "|".join(key)
        por_cfg: dict = {}
        for nom in CONFIGS:
            filas = []
            for si in range(SEMILLAS):
                cfg = {**CONFIGS_FIJAS[nom], "tau": TAU} if nom in CONFIGS_FIJAS else cfg_sem[si][nom]
                p, s = c.puntuar(cfg)
                m = masc[si]
                filas.append(medir_ext(p[m], s[m], cx.y[m], cfg["corte"], cfg["tau"]))
            por_cfg[nom] = filas
        res[nombre] = por_cfg
        print(nombre, f"{time.time() - t0:.0f}s", flush=True)

    mets = ("exactitud", "aceptada", "precision_aceptada", "revision_humana", "aceptada_mal", "errores_que_van_a_revision")
    tabla: dict = {}
    for nombre, por_cfg in res.items():
        tabla[nombre] = {nom: {m: a.resumen([f[m] for f in filas]) for m in mets} for nom, filas in por_cfg.items()}
    limpio = res["limpio|-"]
    deg: dict = {}
    for nombre, por_cfg in res.items():
        if nombre == "limpio|-":
            continue
        d = {}
        for nom in CONFIGS:
            d[nom] = {}
            for m in ("exactitud", "aceptada", "precision_aceptada", "aceptada_mal"):
                v = np.array([(100 * (por_cfg[nom][i][m] - limpio[nom][i][m])) if por_cfg[nom][i][m] is not None and limpio[nom][i][m] is not None else np.nan for i in range(SEMILLAS)])
                d[nom][m] = {"media_pp": float(np.nanmean(v)), "sd_pp": float(np.nanstd(v, ddof=1))}
        for par, (x, y2) in {"hibrido_actual_menos_lexico": ("hibrido_actual", "lexico"), "hibrido_sin_rescate_menos_lexico": ("hibrido_sin_rescate", "lexico")}.items():
            dif = np.array([100 * ((por_cfg[x][i]["exactitud"] - limpio[x][i]["exactitud"]) - (por_cfg[y2][i]["exactitud"] - limpio[y2][i]["exactitud"])) for i in range(SEMILLAS)])
            d[par + "_degradacion_exactitud_pp"] = {"media": float(dif.mean()), "error_estandar": float(dif.std(ddof=1) / np.sqrt(SEMILLAS)), "semillas_hibrido_se_degrada_menos": int((dif > 1e-9).sum()), "semillas_igual": int((abs(dif) <= 1e-9).sum()), "semillas_hibrido_se_degrada_mas": int((dif < -1e-9).sum())}
            nivel = np.array([100 * (por_cfg[x][i]["exactitud"] - por_cfg[y2][i]["exactitud"]) for i in range(SEMILLAS)])
            d[par + "_exactitud_nivel_pp"] = {"media": float(nivel.mean()), "error_estandar": float(nivel.std(ddof=1) / np.sqrt(SEMILLAS))}
        deg[nombre] = d
    def prom(clave_fn, filtro):
        vs = [clave_fn(d) for n, d in deg.items() if filtro(n)]
        return float(np.mean(vs))

    glob = {}
    for sev in ("leve", "fuerte", None):
        filtro = (lambda n, s=sev: n.endswith("|" + s)) if sev else (lambda n: True)
        glob[sev or "todas"] = {
            **{f"degradacion_exactitud_pp_{nom}": prom(lambda d, nom=nom: d[nom]["exactitud"]["media_pp"], filtro) for nom in CONFIGS},
            **{f"degradacion_aceptada_pp_{nom}": prom(lambda d, nom=nom: d[nom]["aceptada"]["media_pp"], filtro) for nom in CONFIGS},
            **{f"precision_aceptada_media_{nom}": float(np.mean([tabla[n][nom]["precision_aceptada"]["media"] for n in tabla if n != "limpio|-" and filtro(n)])) for nom in CONFIGS},
            **{f"aceptada_mal_media_{nom}": float(np.mean([tabla[n][nom]["aceptada_mal"]["media"] for n in tabla if n != "limpio|-" and filtro(n)])) for nom in CONFIGS},
            "hibrido_sin_rescate_menos_lexico_degradacion_exactitud_pp": prom(lambda d: d["hibrido_sin_rescate_menos_lexico_degradacion_exactitud_pp"]["media"], filtro),
            "hibrido_actual_menos_lexico_degradacion_exactitud_pp": prom(lambda d: d["hibrido_actual_menos_lexico_degradacion_exactitud_pp"]["media"], filtro),
            "perturbaciones_en_que_el_hibrido_sin_rescate_se_degrada_menos_que_el_lexico": int(sum(1 for n, d in deg.items() if filtro(n) and d["hibrido_sin_rescate_menos_lexico_degradacion_exactitud_pp"]["media"] > 0)),
            "perturbaciones_totales": int(sum(1 for n in deg if filtro(n))),
        }
    sal = {
        "descripcion": "Prueba de estres: listas de PRUEBA reales perturbadas (cada tipo y severidad por separado), 20 particiones por lista. Nada se entrena; las constantes son las de cada configuracion.",
        "tau": TAU,
        "tipos": a.TIPOS_TODOS,
        "configuraciones": {"lexico": "w_cos 0, rescate apagado", "hibrido_actual": "constantes actuales", "hibrido_sin_rescate": "constantes actuales, rescate apagado",
                            "calibrado_limpio": "constantes elegidas en entrenamiento limpio (rescate apagado, corte propio y su tau por la regla 0,95)", "calibrado_aumentado": "idem con entrenamiento aumentado"},
        "limpio": tabla["limpio|-"],
        "estres": {n: tabla[n] for n in tabla if n != "limpio|-"},
        "degradacion_respecto_al_limpio": deg,
        "resumen_global": glob,
        "vectores": {"llamadas_a_gemini_en_esta_corrida": a.LLAMADAS, "textos_distintos_en_cache": len(cache), "nota": "las llamadas de las perturbaciones de estres y de la aumentacion las hace aumentacion.py (primera corrida); aqui se lee el cache"},
        "ejemplos_por_tipo": ejemplos(cx, estres),
        "segundos": time.time() - t0,
    }
    (k.SALIDA / "robustez.json").write_text(json.dumps(sal, ensure_ascii=False, indent=1, default=float), encoding="utf-8")
    figura(sal)
    print(json.dumps(glob["todas"], indent=0)[:1500])
    return 0


def figura(sal: dict) -> Path:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    COL = {"lexico": "#4D4D4D", "hibrido_actual": "#1F4E86", "hibrido_sin_rescate": "#A8500F"}
    plt.rcParams.update({"font.family": "serif", "font.size": 7.5, "axes.spines.top": False, "axes.spines.right": False})
    tipos = sal["tipos"]
    fig, ejes = plt.subplots(3, 1, figsize=(7.2, 7.4), sharex=True)
    for ax, m, tit in zip(ejes, ("exactitud", "aceptada", "precision_aceptada"), ("exactitud contra el concepto aprobado", "fraccion aceptada sin revision (tau 0,75)", "precision de lo aceptado"), strict=True):
        for j, (nom, col) in enumerate(COL.items()):
            off = (j - 1) * 0.2
            base = sal["limpio"][nom][m]["media"]
            ax.axhline(100 * base, color=col, lw=0.5, ls=":")
            for sv, mk, fc in (("leve", "o", "white"), ("fuerte", "o", col)):
                ys = [100 * sal["estres"][f"{t}|{sv}"][nom][m]["media"] for t in tipos]
                ax.plot(np.arange(len(tipos)) + off, ys, mk, mfc=fc, mec=col, ms=3.5, ls="none", label=f"{nom} {sv}" if m == "exactitud" else None)
        ax.set_ylabel(tit + " (%)", fontsize=7)
    ejes[0].legend(frameon=False, fontsize=6, ncol=3, loc="lower left")
    ejes[-1].set_xticks(np.arange(len(tipos)))
    ejes[-1].set_xticklabels(tipos, rotation=35, ha="right")
    fig.suptitle("Degradacion por perturbacion (media de 20 particiones; hueco = leve, lleno = fuerte; punteada = limpio)", fontsize=7.5)
    fig.tight_layout()
    ruta = k.SALIDA / "robustez.pdf"
    fig.savefig(ruta)
    return ruta


if __name__ == "__main__":
    raise SystemExit(main())
