"""Acuerdo entre anotadores y exactitud del sistema contra un oro independiente.

Lee `muestra_ciega/anotador_A.csv` y `anotador_B.csv` (id, concepto_codigo, comentario) y la
salida del sistema sobre esos mismos ids: la clasificacion de `clasificacion.py` con las
constantes actuales (`ACTUAL`) y tau = 0,75. Calcula:

  * kappa de Cohen entre A y B (IC 95 % por bootstrap sobre renglones) y % de acuerdo.
  * pares de desacuerdo mas frecuentes (A -> B).
  * oro = A si A == B; en los desacuerdos, la columna `adjudicado` que llena una tercera persona
    en `muestra_ciega/adjudicacion.csv` (id, texto_original, concepto_A, concepto_B, adjudicado).
    La primera corrida escribe ese archivo; se llena y se corre otra vez.
  * exactitud del sistema, precision de lo aceptado en tau y fraccion aceptada contra el oro,
    con IC 95 %, y las mismas cifras contra las etiquetas del propio sistema (circulares) sobre
    los mismos ids, con la diferencia y su IC (bootstrap pareado).

Los IC son bootstrap percentil de 2.000 remuestras por renglon. Como los renglones de una misma
lista se parecen, tambien se da el IC remuestreando por lista (colegio, grado), mas honesto y mas ancho.
El codigo `NINGUNO` (o casilla vacia en el oro) equivale a "sin concepto" y se compara con la salida
`sin correspondencia` del sistema (puntaje bajo el corte).

Uso: uv run python ensayos/calibracion/acuerdo.py [--dir muestra_ciega] [--salida acuerdo.json]
"""

from __future__ import annotations

import argparse
import collections
import csv
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
import clasificacion as k  # noqa: E402

NINGUNO = "NINGUNO"
REMUESTRAS = 2000
SEMILLA = 20261116
MUESTRA = k.SALIDA / "muestra_ciega"


def norm(c: str | None) -> str:
    c = (c or "").strip()
    return NINGUNO if c == "" or c.lower().startswith("ningun") else c.upper() if c[:1].lower() == "c" and c[1:].isdigit() else c


def leer(ruta: Path) -> dict[str, str]:
    return {x["id"].strip(): norm(x["concepto_codigo"]) for x in csv.DictReader(ruta.open(encoding="utf-8-sig"))}


def kappa(a: list[str], b: list[str]) -> float:
    n = len(a)
    po = sum(x == y for x, y in zip(a, b, strict=True)) / n
    ca, cb = collections.Counter(a), collections.Counter(b)
    pe = sum(ca[c] * cb[c] for c in ca) / n**2
    return float("nan") if pe == 1 else (po - pe) / (1 - pe)


def ic(f, n: int, rng, grupos: np.ndarray | None = None) -> list[float | None]:
    """IC 95 % percentil de f(indices). Con `grupos`, remuestrea grupos completos."""
    v = []
    if grupos is None:
        for _ in range(REMUESTRAS):
            x = f(rng.integers(0, n, n))
            if x is not None and not np.isnan(x):
                v.append(x)
    else:
        u = np.unique(grupos)
        pos = [np.flatnonzero(grupos == g) for g in u]
        for _ in range(REMUESTRAS):
            x = f(np.concatenate([pos[i] for i in rng.integers(0, len(u), len(u))]))
            if x is not None and not np.isnan(x):
                v.append(x)
    return [float(np.percentile(v, 2.5)), float(np.percentile(v, 97.5))] if v else [None, None]


def metricas_sistema(pred_ok: np.ndarray, acepta: np.ndarray, ix: np.ndarray) -> dict[str, float | None]:
    o, a = pred_ok[ix], acepta[ix]
    return {"exactitud": float(o.mean()), "aceptada": float(a.mean()), "precision_aceptada": float((o & a).sum() / a.sum()) if a.sum() else None}


def salida_sistema(filas: list[dict]) -> dict[str, dict]:
    """Por renglon de la muestra: concepto del sistema (codigo o NINGUNO), puntaje, aceptado y etiqueta circular."""
    d = k.cargar()
    r = k.construir_rasgos(d)
    idx, s = k.puntuar(r, k.ACTUAL)
    pos = {(f["colegio"], f["grado"], f["texto"]): i for i, f in reversed(list(enumerate(d.filas)))}
    out = {}
    for f in filas:
        i = pos[(f["colegio"], f["grado"], f["texto_original"])]
        u = d.filas[i]["u"]
        pred = d.codigos[idx[u]] if (idx[u] >= 0 and s[u] >= k.ACTUAL["corte"]) else NINGUNO
        out[f["id"]] = {
            "sistema": pred,
            "puntaje": float(s[u]),
            "aceptado": bool(s[u] >= k.ACTUAL["tau"] and pred != NINGUNO),
            "circular": d.filas[i]["etiqueta"] or NINGUNO,
        }
    return out


def correr(dir_muestra: Path, salida: Path, adjudicacion: Path | None = None) -> dict:
    filas = list(csv.DictReader((dir_muestra / "muestra.csv").open(encoding="utf-8-sig")))
    ids = [f["id"] for f in filas]
    A, B = leer(dir_muestra / "anotador_A.csv"), leer(dir_muestra / "anotador_B.csv")
    faltan = [i for i in ids if i not in A or i not in B]
    if faltan:
        raise SystemExit(f"Faltan {len(faltan)} ids en las hojas de A o B (ej. {faltan[:3]}).")
    a, b = [A[i] for i in ids], [B[i] for i in ids]
    rng = np.random.default_rng(SEMILLA)
    n = len(ids)
    acu = np.array([x == y for x, y in zip(a, b, strict=True)])
    res: dict = {
        "n": n,
        "acuerdo_A_B": {
            "porcentaje": float(acu.mean()),
            "ic95": ic(lambda ix: acu[ix].mean(), n, rng),
            "kappa_cohen": kappa(a, b),
            "kappa_ic95": ic(lambda ix: kappa([a[i] for i in ix], [b[i] for i in ix]), n, rng),
            "desacuerdos": int((~acu).sum()),
            "desacuerdos_mas_frecuentes": [
                {"A": x, "B": y, "n": c} for (x, y), c in collections.Counter((x, y) for x, y in zip(a, b, strict=True) if x != y).most_common(10)
            ],
        },
    }
    sis = salida_sistema(filas)
    # adjudicacion
    ruta_adj = adjudicacion or dir_muestra / "adjudicacion.csv"
    adj = {}
    if ruta_adj.exists():
        adj = {x["id"].strip(): norm(x["adjudicado"]) for x in csv.DictReader(ruta_adj.open(encoding="utf-8-sig")) if (x.get("adjudicado") or "").strip()}
    else:
        with ruta_adj.open("w", encoding="utf-8", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(["id", "texto_original", "concepto_A", "concepto_B", "adjudicado"])
            for f, x, y in zip(filas, a, b, strict=True):
                if x != y:
                    w.writerow([f["id"], f["texto_original"], x, y, ""])
        res["adjudicacion"] = f"escrita en {ruta_adj}: la tercera persona llena `adjudicado` y se vuelve a correr"
    oro, sin_oro = {}, []
    for i, x, y in zip(ids, a, b, strict=True):
        if x == y:
            oro[i] = x
        elif i in adj:
            oro[i] = adj[i]
        else:
            sin_oro.append(i)
    res["oro"] = {"con_oro": len(oro), "por_acuerdo": int(acu.sum()), "por_adjudicacion": len(oro) - int(acu.sum()), "sin_oro_pendientes": len(sin_oro)}
    if sin_oro:
        res["oro"]["aviso"] = "faltan adjudicaciones; las cifras se calculan solo sobre renglones con oro (sesgo: los desacuerdos son los dificiles)"
    ok_ids = [i for i in ids if i in oro]
    if not ok_ids:
        res["sistema"] = None
        salida.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
        return res
    ofl = {f["id"]: f for f in filas}
    pred_oro = np.array([sis[i]["sistema"] == oro[i] for i in ok_ids])
    pred_circ = np.array([sis[i]["sistema"] == sis[i]["circular"] for i in ok_ids])
    acepta = np.array([sis[i]["aceptado"] for i in ok_ids])
    listas = np.array([f'{ofl[i]["colegio"]}|{ofl[i]["grado"]}' for i in ok_ids])
    m = len(ok_ids)
    rng = np.random.default_rng(SEMILLA)

    def bloque(ok: np.ndarray) -> dict:
        base = metricas_sistema(ok, acepta, np.arange(m))
        out = {}
        for nombre in base:
            fn = lambda ix, nombre=nombre: metricas_sistema(ok, acepta, ix)[nombre] if acepta[ix].sum() else None  # noqa: E731
            out[nombre] = {"valor": base[nombre], "ic95": ic(fn, m, rng), "ic95_por_lista": ic(fn, m, rng, listas)}
        return out

    res["sistema"] = {
        "tau": k.ACTUAL["tau"],
        "n": m,
        "contra_oro_independiente": bloque(pred_oro),
        "contra_etiquetas_del_sistema_circulares": bloque(pred_circ),
    }
    dif = {}
    for nombre in ("exactitud", "precision_aceptada"):
        def fd(ix, nombre=nombre):
            if not acepta[ix].sum():
                return None
            return metricas_sistema(pred_circ, acepta, ix)[nombre] - metricas_sistema(pred_oro, acepta, ix)[nombre]
        v = metricas_sistema(pred_circ, acepta, np.arange(m))[nombre] - metricas_sistema(pred_oro, acepta, np.arange(m))[nombre]
        dif[nombre] = {"circular_menos_oro": v, "ic95": ic(fd, m, rng), "ic95_por_lista": ic(fd, m, rng, listas)}
    res["sistema"]["inflacion_por_circularidad"] = dif
    circ = [sis[i]["circular"] for i in ok_ids]
    res["etiqueta_circular_vs_oro"] = {
        "acuerdo": float(np.mean([c == oro[i] for c, i in zip(circ, ok_ids, strict=True)])),
        "kappa": kappa(circ, [oro[i] for i in ok_ids]),
        "A_vs_circular": float(np.mean([A[i] == sis[i]["circular"] for i in ids])),
        "B_vs_circular": float(np.mean([B[i] == sis[i]["circular"] for i in ids])),
        "lectura": "si las personas coinciden mas con la etiqueta circular que entre si, hay sesgo de confirmacion en la etiqueta vieja",
    }
    salida.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    return res


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", type=Path, default=MUESTRA)
    ap.add_argument("--salida", type=Path, default=k.SALIDA / "acuerdo.json")
    ap.add_argument("--adjudicacion", type=Path, default=None)
    g = ap.parse_args()
    r = correr(g.dir, g.salida, g.adjudicacion)
    print(json.dumps({"acuerdo": r["acuerdo_A_B"]["porcentaje"], "kappa": r["acuerdo_A_B"]["kappa_cohen"], "oro": r["oro"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
