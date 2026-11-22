"""Acuerdo y exactitud contra la salida de la RUTA REAL (ruta_real_muestra.csv), oro con consejo LLM.
Uso: uv run python ensayos/calibracion/acuerdo_ruta_real.py"""

from __future__ import annotations

import collections
import csv
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
import acuerdo as ac  # noqa: E402

CAL = ac.k.SALIDA
M = ac.MUESTRA
DIVIDIDOS = {
    "M064": "dividido en el borde con NINGUNO",
    "M171": "dividido en el borde con NINGUNO",
    "M181": "dividido en el borde con NINGUNO",
    "M211": "dividido en el borde con NINGUNO",
    "M186": "dividido, confianza baja (no es estrictamente plan lector)",
    "M219": "dividido: C134 se ejemplifica solo con plan lector",
}


def bloque(ok, acepta, ix_all, listas, rng):
    m = len(ok)
    if m == 0:
        return None
    base = ac.metricas_sistema(ok, acepta, np.arange(m))
    out = {"n": m}
    for nombre in base:
        fn = lambda ix, nombre=nombre: (
            ac.metricas_sistema(ok, acepta, ix)[nombre] if acepta[ix].sum() else None
        )  # noqa: E731
        out[nombre] = {
            "valor": base[nombre],
            "ic95": ac.ic(fn, m, rng),
            "ic95_por_lista": ac.ic(fn, m, rng, listas),
        }
    return out


def main() -> int:
    filas = list(csv.DictReader((M / "muestra.csv").open(encoding="utf-8-sig")))
    ids = [f["id"] for f in filas]
    fm = {f["id"]: f for f in filas}
    A, B = ac.leer(M / "anotador_A_llm.csv"), ac.leer(M / "anotador_B_llm.csv")
    adj = {
        x["id"]: ac.norm(x["adjudicado"])
        for x in csv.DictReader((M / "adjudicacion_llm.csv").open(encoding="utf-8-sig"))
    }
    R = {x["id"]: x for x in csv.DictReader((CAL / "ruta_real_muestra.csv").open(encoding="utf-8-sig"))}
    TAXONOMIA = {
        x["codigo"].strip() for x in csv.DictReader((M / "conceptos.csv").open(encoding="utf-8-sig"))
    }
    a, b = [A[i] for i in ids], [B[i] for i in ids]
    oro = {i: (A[i] if A[i] == B[i] else adj[i]) for i in ids}
    og = [oro[i] for i in ids]
    sis = {i: ac.norm(R[i]["concepto"]) for i in ids}
    n = len(ids)
    rng = np.random.default_rng(ac.SEMILLA)
    listas = np.array([f"{fm[i]['colegio']}|{fm[i]['grado']}" for i in ids])
    kap = lambda x, y: lambda ix: ac.kappa([x[i] for i in ix], [y[i] for i in ix])  # noqa: E731
    acu = np.array([x == y for x, y in zip(a, b, strict=True)])
    res = {
        "aviso_honestidad": "Los tres jueces son LLM (dos anotadores Haiku ciegos A y B y un consejo LLM como tercer juez en los 11 desacuerdos); el oro NO es humano. Las cifras miden concordancia con ese oro, no con criterio humano.",
        "n": n,
        "fuente_sistema": "ruta_real_muestra.csv (consulta.emparejar + estado_desde_emparejamiento, tau=0.75, catalogo vivo)",
        "acuerdo_A_B": {
            "porcentaje": float(acu.mean()),
            "desacuerdos": int((~acu).sum()),
            "kappa_cohen": ac.kappa(a, b),
            "kappa_ic95": ac.ic(kap(a, b), n, rng),
            "kappa_ic95_por_lista": ac.ic(kap(a, b), n, rng, listas),
        },
        "kappa_vs_oro": {
            "A": {
                "kappa": ac.kappa(a, og),
                "ic95": ac.ic(kap(a, og), n, rng),
                "acuerdo": float(np.mean([x == y for x, y in zip(a, og, strict=True)])),
            },
            "B": {
                "kappa": ac.kappa(b, og),
                "ic95": ac.ic(kap(b, og), n, rng),
                "acuerdo": float(np.mean([x == y for x, y in zip(b, og, strict=True)])),
            },
            "nota": "el oro hereda el acuerdo A=B en 229 renglones, asi que estos kappa estan inflados por construccion",
        },
        "oro": {
            "por_acuerdo": int(acu.sum()),
            "por_consejo": int((~acu).sum()),
            "consejo_dividido_o_baja_confianza": DIVIDIDOS,
        },
    }
    ok = np.array([sis[i] == oro[i] for i in ids])
    acepta = np.array([R[i]["aceptado"].strip().lower() == "si" for i in ids])
    res["sistema_ruta_real"] = {"tau": 0.75, "global": bloque(ok, acepta, None, listas, rng)}
    solo = np.flatnonzero(acu)
    res["sistema_ruta_real"]["solo_renglones_con_acuerdo_A_B"] = bloque(
        ok[solo], acepta[solo], None, listas[solo], rng
    )

    libro = np.array([oro[i] == "C134" for i in ids])
    res["por_tipo"] = {
        "libros_con_titulo_oro_C134": bloque(ok[libro], acepta[libro], None, listas[libro], rng),
        "resto": bloque(ok[~libro], acepta[~libro], None, listas[~libro], rng),
    }
    col = np.array([fm[i]["colegio"] for i in ids])
    res["por_colegio"] = {
        c: bloque(ok[col == c], acepta[col == c], None, listas[col == c], rng) for c in sorted(set(col))
    }

    err = collections.defaultdict(list)
    for i in ids:
        if sis[i] != oro[i]:
            err[(oro[i], sis[i])].append(i)
    tipos = []
    for (o, s), l in sorted(err.items(), key=lambda kv: -len(kv[1])):
        tipos.append(
            {
                "oro": o,
                "sistema": s,
                "n": len(l),
                "aceptados": sum(acepta[ids.index(i)] for i in l),
                "ejemplos": [
                    {"id": i, "texto": fm[i]["texto_original"], "estado": R[i]["estado"]} for i in l[:3]
                ]
                if len(l) >= 3
                else [{"id": i, "texto": fm[i]["texto_original"], "estado": R[i]["estado"]} for i in l],
            }
        )
    res["errores_por_tipo"] = tipos
    res["errores_total"] = int((~ok).sum())
    acep_mal = []
    for i, e in zip(ids, acepta, strict=True):
        if e and sis[i] != oro[i]:
            razones = []
            if i in DIVIDIDOS:
                razones.append("oro del consejo: " + DIVIDIDOS[i])
            elif A[i] != B[i]:
                razones.append("oro por consejo (A y B discrepaban)")
            if not (oro[i] == "NINGUNO" or oro[i] in TAXONOMIA):
                razones.append(
                    "el oro usa una etiqueta fuera de la taxonomia (" + oro[i] + "); no hay codigo comparable"
                )
            if A[i] != B[i] and sis[i] in (A[i], B[i]):
                razones.append("el sistema coincide con uno de los dos anotadores")
            acep_mal.append(
                {
                    "id": i,
                    "texto": fm[i]["texto_original"],
                    "oro": oro[i],
                    "sistema": sis[i],
                    "A": A[i],
                    "B": B[i],
                    "dudoso_del_oro": bool(razones),
                    "razon": "; ".join(razones),
                }
            )
    res["aceptados_erroneos"] = {
        "n": len(acep_mal),
        "dudosos_del_oro": sum(x["dudoso_del_oro"] for x in acep_mal),
        "error_del_sistema_probable": sum(not x["dudoso_del_oro"] for x in acep_mal),
        "detalle": acep_mal,
        "nota": "dudoso = el oro vino del consejo en un caso dividido o A y B discrepaban; el resto se cuenta como error del sistema salvo revision humana.",
    }
    res["comparacion_previa"] = {
        "reimplementacion_clasificacion_py": {"n": 229, "exactitud": 0.838, "precision_aceptada": 0.943},
        "etiquetas_circulares": {"exactitud": 0.948, "precision_aceptada": 0.964},
        "ruta_real_actual": {
            "n": n,
            "exactitud": res["sistema_ruta_real"]["global"]["exactitud"]["valor"],
            "precision_aceptada": res["sistema_ruta_real"]["global"]["precision_aceptada"]["valor"],
            "aceptada": res["sistema_ruta_real"]["global"]["aceptada"]["valor"],
        },
        "nota": "no comparables 1 a 1: distinto n (240 vs 229, oro completo vs parcial) y oro LLM vs el oro de entonces",
    }
    (CAL / "acuerdo_ruta_real.json").write_text(
        json.dumps(res, ensure_ascii=False, indent=1, default=lambda o: o.item()), encoding="utf-8"
    )
    g = res["sistema_ruta_real"]["global"]
    print(
        json.dumps(
            {
                "kappa_AB": res["acuerdo_A_B"]["kappa_cohen"],
                "kA": res["kappa_vs_oro"]["A"]["kappa"],
                "kB": res["kappa_vs_oro"]["B"]["kappa"],
                **{k: g[k] for k in ("exactitud", "precision_aceptada", "aceptada")},
                "errores": res["errores_total"],
                "aceptados_err": {k: v for k, v in res["aceptados_erroneos"].items() if k != "detalle"},
                "libros": res["por_tipo"]["libros_con_titulo_oro_C134"],
                "resto": res["por_tipo"]["resto"],
            },
            ensure_ascii=False,
            indent=1,
        )[:5000]
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
