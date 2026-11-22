"""Robustez v2: el clasificador DE PRODUCCION (consulta.emparejar, con el limpiador de encabezados de grupo
y la ruta de libros con titulo), sobre renglones_etiquetados_v2.csv, 11 perturbaciones x leve/fuerte.
Uso: uv run python ensayos/calibracion/robustez_v2.py"""

from __future__ import annotations

import asyncio
import csv
import json
import multiprocessing as mp
import sys
import time
from collections import Counter
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
import aumentacion as a  # noqa: E402
import ruta_real as R  # noqa: E402
from particion import SEMILLA_BASE, SEMILLAS, partir  # noqa: E402
from tukit_inteligencia.dominio.pipeline import estado_desde_emparejamiento  # noqa: E402

TAU = 0.75
DATOS = Path(__file__).parent / "datos" / "renglones_etiquetados_v2.csv"
SALIDA = R.SALIDA
TIPOS = a.TIPOS
CONDS = [("limpio", "-")] + [(t, s) for t in TIPOS for s in (a.LEVE, a.FUERTE)]
MAX_LLAMADAS = 15000
G: dict = {}


def tarea(arg):
    cond, limp, canal = arg
    textos, vecs = G["textos"][cond], G["vecs"][cond]
    if canal == "lexico":
        vecs = [None] * len(textos)
    res = R.correr(textos, vecs, G["conceptos"], G["productos"], limpiador=limp, libros=True)
    out = []
    for e in res:
        out.append(
            (e.concepto_codigo, float(e.parecido), estado_desde_emparejamiento(e.a_dict(), TAU), e.estado)
        )
    return arg, out


def medir(pred, acepta, acepta_p, y, estados):
    ok = np.array([p == t for p, t in zip(pred, y, strict=True)])
    n = len(y)
    err = ~ok
    destino = Counter(estados[i] if not acepta[i] else "ACEPTADO_MAL" for i in np.flatnonzero(err))
    ne = err.sum()
    return {
        "exactitud": float(ok.mean()),
        "aceptada": float(acepta.mean()),
        "precision_aceptada": float((acepta & ok).sum() / acepta.sum()) if acepta.sum() else None,
        "revision_humana": float(1 - acepta.mean()),
        "aceptada_mal": float((acepta & err).sum() / n),
        "errores_que_van_a_revision": float((err & ~acepta).sum() / ne) if ne else None,
        "aceptada_por_puntaje": float(acepta_p.mean()),
        "precision_por_puntaje": float((acepta_p & ok).sum() / acepta_p.sum()) if acepta_p.sum() else None,
        "destino_de_errores": {k: float(v / ne) for k, v in destino.items()} if ne else {},
    }


def resumen(v):
    v = [x for x in v if x is not None]
    return {"media": float(np.mean(v)), "sd": float(np.std(v, ddof=1)), "n": len(v)} if v else None


def main() -> int:
    t0 = time.time()
    filas = list(csv.DictReader(DATOS.open(encoding="utf-8")))
    tx = sorted({f["texto_original"] for f in filas})
    ind = {t: i for i, t in enumerate(tx)}
    u = np.array([ind[f["texto_original"]] for f in filas])
    y = [f["concepto_codigo"] or None for f in filas]
    lista = np.array([f"{f['colegio']}|{f['grado']}" for f in filas])
    origen = np.array([f["origen_revision"] for f in filas])
    corr = np.array([f["concepto_corregido_por_persona"] == "1" for f in filas])
    print("renglones", len(filas), "textos", len(tx), "listas", len(set(lista)), flush=True)

    base_v = np.load(R.CL.DATOS / "vectores_renglones.npz", allow_pickle=False)
    vb = dict(zip(base_v["textos"].tolist(), base_v["vectores"].astype(np.float64), strict=True))
    textos = {c: tx if c[0] == "limpio" else [a.perturbar(t, c[0], c[1]) for t in tx] for c in CONDS}
    nuevos = {t for c in CONDS for t in textos[c]} - set(vb)
    cache = a._cargar_cache()
    faltan = sorted(t for t in nuevos if t not in cache)
    print("textos perturbados distintos", len(nuevos), "sin vector en cache", len(faltan), flush=True)
    if len(faltan) > MAX_LLAMADAS:
        raise SystemExit(f"{len(faltan)} > {MAX_LLAMADAS}: hay que reducir con muestra estratificada")
    if faltan:
        cache = a.vectorizar_nuevos(set(faltan))
    vecs = {c: [(vb[t] if t in vb else a._unit(cache[t])).tolist() for t in textos[c]] for c in CONDS}
    conceptos, productos = asyncio.run(R.cargar_indice())
    G.update(textos=textos, vecs=vecs, conceptos=conceptos, productos=productos)

    tareas = [(c, limp, canal) for c in CONDS for limp in (True, False) for canal in ("hibrido", "lexico")]
    with mp.get_context("fork").Pool(min(8, mp.cpu_count())) as pool:
        raw = {}
        for arg, out in pool.imap_unordered(tarea, tareas):
            raw[arg] = out
            print(len(raw), "/", len(tareas), f"{time.time() - t0:.0f}s", flush=True)

    listas = sorted(set(lista))
    masc = [np.isin(lista, p["prueba"]) for p in (partir(listas, SEMILLA_BASE + i) for i in range(SEMILLAS))]
    yy = np.array(y, dtype=object)

    def por_part(clave, mask_extra=None):
        out = raw[clave]
        pred = np.array([out[i][0] for i in u], dtype=object)
        est = np.array([out[i][2] for i in u])
        acep = est == "RESUELTO_AUTO"
        acep_p = np.array([(out[i][3] != "sin_match") and out[i][1] >= TAU for i in u])
        return [medir(pred[m], acep[m], acep_p[m], yy[m], est[m]) for m in masc], (pred, acep, est)

    mets = (
        "exactitud",
        "aceptada",
        "precision_aceptada",
        "revision_humana",
        "aceptada_mal",
        "errores_que_van_a_revision",
        "aceptada_por_puntaje",
        "precision_por_puntaje",
    )
    tabla, filas_sem, cruda = {}, {}, {}
    for c in CONDS:
        for limp in (True, False):
            for canal in ("hibrido", "lexico"):
                f, cr = por_part((c, limp, canal))
                k = f"{c[0]}|{c[1]}"
                lab = f"{canal}|{'limpiador' if limp else 'sin_limpiador'}"
                filas_sem[(k, lab)] = f
                cruda[(k, lab)] = cr
                tabla.setdefault(k, {})[lab] = {m: resumen([x[m] for x in f]) for m in mets} | {
                    "destino_de_errores": {
                        d: float(
                            np.mean(
                                [x["destino_de_errores"].get(d, 0.0) for x in f if x["destino_de_errores"]]
                            )
                        )
                        for d in ("sin_match", "HUECO_CATALOGO", "AMBIGUO", "ACEPTADO_MAL", "RESUELTO_AUTO")
                    }
                }

    def par(k, l1, l2, m):
        d = np.array(
            [
                100 * (x1[m] - x2[m])
                for x1, x2 in zip(filas_sem[(k, l1)], filas_sem[(k, l2)], strict=True)
                if x1[m] is not None and x2[m] is not None
            ]
        )
        return {"media_pp": float(d.mean()), "error_estandar": float(d.std(ddof=1) / np.sqrt(len(d)))}

    efecto = {}
    for c in CONDS:
        k = f"{c[0]}|{c[1]}"
        efecto[k] = {
            "limpiador_menos_sin_limpiador_hibrido": {
                m: par(k, "hibrido|limpiador", "hibrido|sin_limpiador", m)
                for m in ("exactitud", "aceptada", "precision_aceptada", "errores_que_van_a_revision")
            },
            "limpiador_menos_sin_limpiador_lexico": {
                m: par(k, "lexico|limpiador", "lexico|sin_limpiador", m)
                for m in ("exactitud", "aceptada", "precision_aceptada", "errores_que_van_a_revision")
            },
            "hibrido_menos_lexico_con_limpiador": {
                m: par(k, "hibrido|limpiador", "lexico|limpiador", m)
                for m in ("exactitud", "aceptada", "precision_aceptada", "errores_que_van_a_revision")
            },
        }
    deg = {}
    for c in CONDS[1:]:
        k = f"{c[0]}|{c[1]}"
        deg[k] = {}
        for lab in ("hibrido|limpiador", "hibrido|sin_limpiador", "lexico|limpiador", "lexico|sin_limpiador"):
            deg[k][lab] = {}
            for m in ("exactitud", "aceptada", "precision_aceptada"):
                d = np.array(
                    [
                        100 * (p[m] - q[m])
                        for p, q in zip(filas_sem[(k, lab)], filas_sem[("limpio|-", lab)], strict=True)
                        if p[m] is not None and q[m] is not None
                    ]
                )
                deg[k][lab][m] = {"media_pp": float(d.mean()), "sd_pp": float(d.std(ddof=1))}

    glob = {}
    for sev in (a.LEVE, a.FUERTE, "todas"):
        ks = [f"{t}|{s}" for t in TIPOS for s in ((a.LEVE, a.FUERTE) if sev == "todas" else (sev,))]
        glob[sev] = {
            lab: {
                m: float(np.mean([tabla[k][lab][m]["media"] for k in ks if tabla[k][lab][m]])) for m in mets
            }
            for lab in (
                "hibrido|limpiador",
                "hibrido|sin_limpiador",
                "lexico|limpiador",
                "lexico|sin_limpiador",
            )
        }

    pred, acep, est = cruda[("limpio|-", "hibrido|limpiador")]
    ok = np.array([p == t for p, t in zip(pred, yy, strict=True)])
    estratos = {}
    for o in sorted(set(origen)):
        m = origen == o
        estratos[o] = {
            "renglones": int(m.sum()),
            "exactitud": float(ok[m].mean()),
            "aceptada": float(acep[m].mean()),
        }
    estratos["corregido_por_persona"] = {
        "renglones": int(corr.sum()),
        "exactitud": float(ok[corr].mean()),
        "aceptada": float(acep[corr].mean()),
    }
    sin_c = np.array([t is None for t in y])
    estratos["sin_concepto"] = {
        "renglones": int(sin_c.sum()),
        "exactitud": float(ok[sin_c].mean()),
        "aceptada": float(acep[sin_c].mean()),
    }

    ej = []
    for sv in (a.LEVE, a.FUERTE):
        k = f"prefijo|{sv}"
        pa, _, _ = cruda[(k, "hibrido|limpiador")]
        pb, _, _ = cruda[(k, "hibrido|sin_limpiador")]
        idx = [i for i in range(len(filas)) if pa[i] != pb[i]][:300:25]
        for i in idx:
            ej.append(
                {
                    "severidad": sv,
                    "texto": textos[("prefijo", sv)][u[i]],
                    "etiqueta": y[i],
                    "con_limpiador": pa[i],
                    "sin_limpiador": pb[i],
                }
            )

    sal = {
        "descripcion": "Robustez del clasificador de produccion (consulta.emparejar) sobre renglones_etiquetados_v2.csv; 11 perturbaciones x leve/fuerte; 20 particiones por lista (solo prueba); sin calibrar nada.",
        "tau": TAU,
        "tipos": TIPOS,
        "renglones": len(filas),
        "listas": len(listas),
        "textos_unicos": len(tx),
        "definiciones": {
            "aceptada": "estado RESUELTO_AUTO (concepto reconocido, con opciones en catalogo, parecido >= tau)",
            "aceptada_por_puntaje": "concepto reconocido y parecido >= tau (sin exigir producto; comparable con robustez.json)",
            "revision_humana": "1 - aceptada",
            "errores_que_van_a_revision": "fraccion de los errores de concepto que NO se aceptan solos",
            "destino_de_errores": "por estado final, fraccion de los errores",
        },
        "limpio": tabla["limpio|-"],
        "estres": {k: v for k, v in tabla.items() if k != "limpio|-"},
        "efecto_limpiador_y_canal_pp": efecto,
        "degradacion_vs_limpio": deg,
        "resumen_global": glob,
        "limpio_por_origen_de_etiqueta": estratos,
        "ejemplos_prefijo_donde_el_limpiador_cambia": ej,
        "llamadas": {
            "textos_perturbados_distintos": len(nuevos),
            "sin_vector_en_cache_(llamadas_a_Gemini)": len(faltan),
            "solicitudes": a.LLAMADAS["solicitudes"],
            "emparejar_calls": len(tareas) * len(tx),
        },
        "segundos": time.time() - t0,
    }
    (SALIDA / "robustez_v2.json").write_text(
        json.dumps(sal, ensure_ascii=False, indent=1, default=float), encoding="utf-8"
    )
    figura(sal)
    print(json.dumps(glob["todas"], indent=0)[:2500])
    return 0


def figura(sal: dict) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    plt.rcParams.update(
        {"font.family": "serif", "font.size": 7.5, "axes.spines.top": False, "axes.spines.right": False}
    )
    tipos = sal["tipos"]
    C = {
        "hibrido|limpiador": ("#1F4E86", "hibrido, con limpiador"),
        "hibrido|sin_limpiador": ("#A8500F", "hibrido, sin limpiador"),
        "lexico|limpiador": ("#4D4D4D", "lexico puro, con limpiador"),
    }
    fig, ejes = plt.subplots(3, 1, figsize=(7.2, 7.6), sharex=True)
    for ax, m, tit in zip(
        ejes,
        ("exactitud", "errores_que_van_a_revision", "aceptada_mal"),
        ("exactitud", "errores que el guardrail manda a revision", "aceptada mal (fraccion de renglones)"),
        strict=True,
    ):
        for j, (lab, (col, nom)) in enumerate(C.items()):
            off = (j - 1) * 0.22
            ax.axhline(100 * sal["limpio"][lab][m]["media"], color=col, lw=0.5, ls=":")
            for sv, fc in (("leve", "white"), ("fuerte", col)):
                ys = [
                    100
                    * (
                        sal["estres"][f"{t}|{sv}"][lab][m]["media"]
                        if sal["estres"][f"{t}|{sv}"][lab][m]
                        else np.nan
                    )
                    for t in tipos
                ]
                ax.plot(
                    np.arange(len(tipos)) + off,
                    ys,
                    "o",
                    mfc=fc,
                    mec=col,
                    ms=3.5,
                    ls="none",
                    label=f"{nom}, {sv}" if m == "exactitud" else None,
                )
        ax.set_ylabel(tit + " (%)", fontsize=7)
    ejes[0].legend(frameon=False, fontsize=5.5, ncol=3, loc="lower left")
    ejes[-1].set_xticks(np.arange(len(tipos)))
    ejes[-1].set_xticklabels(tipos, rotation=35, ha="right")
    fig.suptitle(
        "Robustez v2, clasificador de produccion (media de 20 particiones; hueco = leve, lleno = fuerte; punteada = limpio)",
        fontsize=7,
    )
    fig.tight_layout()
    fig.savefig(SALIDA / "robustez_v2.pdf")


if __name__ == "__main__":
    raise SystemExit(main())
