"""Experimento E: umbral tau del emparejamiento (TUKIT_TAU, 0,75 por omision).

Pregunta: dado el `parecido` que el resolver asigna a un renglon, a partir de que
valor conviene aceptar el emparejamiento sin revision humana.

Fuente de las decisiones humanas. La tabla `transicion_resolucion` de la base
`tukit_inteligencia` solo guarda transiciones automaticas (ver `contar_tabla`),
asi que no sirve de etiqueta. La unica decision humana disponible es el concepto
de `datos/curaduria/listas_revisadas.csv` (4 anotadores con una pauta común; acuerdo entre ellos no calculado), que se une con los
renglones del benchmark (`bench_laya/instancias.json.gz`, emparejamiento solo
lexico) por colegio, grado y texto del renglon. Un renglon cuenta como acierto
cuando el concepto del resolver es el que dejo el revisor.

Validacion cruzada AGRUPADA por lista (colegio, grado): 5 pliegues; en cada uno
se elige tau con los otros 4 como el menor valor cuya precision de aceptacion sea
al menos OBJETIVO_PRECISION, y se mide en el pliegue retenido. Se reporta tambien
el AUC de `parecido` como puntaje de acierto y la precision y el cobertura en
tau = 0,75.

Uso: uv run python ensayos/calibracion/tau.py
Salida: docs/informes/calibracion/tau.json
"""

from __future__ import annotations

import collections
import csv
import os

import nucleo as n
import numpy as np
from scipy import stats

OBJETIVO_PRECISION = 0.95
PLIEGUES = 5
TAU_ACTUAL = 0.75
CURADURIA = n.RAIZ / "datos" / "curaduria" / "listas_revisadas.csv"
ITEMS = n.RAIZ / "datos" / "listas" / "items_lista.csv"


def contar_tabla() -> dict:
    """Cuenta las decisiones de la tabla de transiciones con `psql`, si la base esta arriba."""
    import subprocess

    entorno = {**os.environ, "PGGSSENCMODE": "disable", "PGPASSWORD": "tukit"}
    base = ["psql", "-h", "127.0.0.1", "-U", "tukit", "-d", "tukit_inteligencia", "-At", "-F", "|", "-c"]

    def consulta(sql: str) -> list[list[str]]:
        r = subprocess.run([*base, sql], capture_output=True, text=True, env=entorno, timeout=30, check=True)
        return [linea.split("|") for linea in r.stdout.strip().splitlines()]

    try:
        return {
            "disponible": True,
            "transiciones(estado_anterior, estado_nuevo, decidida_por_humano, filas)": consulta(
                "select coalesce(estado_anterior,'(ninguno)'), estado_nuevo, decidida_por is not null, count(*) "
                "from transicion_resolucion group by 1,2,3"
            ),
            "resolucion_item(estado, min_parecido, max_parecido, filas)": consulta(
                "select estado, min(parecido), max(parecido), count(*) from resolucion_item group by 1"
            ),
        }
    except Exception as e:  # noqa: BLE001
        return {"disponible": False, "motivo": str(e)[:200]}


def pares_etiquetados() -> list[dict]:
    revisadas = list(csv.DictReader(CURADURIA.open(encoding="utf-8")))
    items = list(csv.DictReader(ITEMS.open(encoding="utf-8")))
    colegios_de_texto: dict[str, set[str]] = collections.defaultdict(set)
    for x in items:
        colegios_de_texto[x["texto_original"].strip().lower()].add(x["colegio_codigo"])
    votos: dict[str, collections.Counter] = collections.defaultdict(collections.Counter)
    for x in revisadas:
        for c in colegios_de_texto.get(x["texto_original"].strip().lower(), ()):
            votos[x["colegio_id"]][c] += 1
    codigo_de = {uuid: v.most_common(1)[0][0] for uuid, v in votos.items()}

    indice = {}
    for inst in n.instancias():
        for r in inst["renglones"]:
            indice[(inst["colegio"], inst["grado"], r["texto"].strip().lower())] = r
    pares = []
    for x in revisadas:
        col = codigo_de.get(x["colegio_id"])
        clave = (col, x["grado"], x["texto_original"].strip().lower())
        r = indice.get(clave)
        if r is None:
            continue
        pares.append(
            {
                "lista": f"{col}|{x['grado']}",
                "colegio": col,
                "parecido": float(r["parecido"]),
                "concepto_resolver": r["concepto_codigo"],
                "concepto_revisor": x["concepto"],
                "acierto": bool(r["concepto_codigo"]) and r["concepto_codigo"] == x["concepto"],
            }
        )
    return pares


def auc(puntaje: np.ndarray, y: np.ndarray) -> float | None:
    pos, neg = puntaje[y], puntaje[~y]
    if len(pos) == 0 or len(neg) == 0:
        return None
    u = stats.mannwhitneyu(pos, neg, alternative="two-sided").statistic
    return float(u / (len(pos) * len(neg)))


def metricas(parecido: np.ndarray, y: np.ndarray, tau: float) -> dict:
    acepta = parecido >= tau
    tp = int((acepta & y).sum())
    return {
        "tau": tau,
        "aceptados": int(acepta.sum()),
        "precision": tp / acepta.sum() if acepta.sum() else None,
        "cobertura_de_aciertos": tp / y.sum() if y.sum() else None,
        "fraccion_aceptada": float(acepta.mean()),
    }


def matriz_confusion(parecido: np.ndarray, y: np.ndarray, tau: float) -> dict:
    """Aceptar sin revision (parecido >= tau) frente a acierto del resolver segun el revisor."""
    acepta = parecido >= tau
    tp, fp = int((acepta & y).sum()), int((acepta & ~y).sum())
    fn, tn = int((~acepta & y).sum()), int((~acepta & ~y).sum())
    p = tp / (tp + fp) if tp + fp else None
    r = tp / (tp + fn) if tp + fn else None
    f1 = 2 * p * r / (p + r) if p and r else None
    return {"tau": tau, "tp": tp, "fp": fp, "fn": fn, "tn": tn, "precision": p, "recall": r, "f1": f1}


def curva_roc(parecido: np.ndarray, y: np.ndarray) -> list[dict]:
    """Un punto por cada valor distinto de parecido (umbral), de mayor a menor, mas los extremos."""
    pos, neg = int(y.sum()), int((~y).sum())
    puntos = [{"umbral": None, "fpr": 0.0, "tpr": 0.0}]
    for t in sorted(np.unique(parecido), reverse=True):
        acepta = parecido >= t
        puntos.append({"umbral": float(t), "fpr": float((acepta & ~y).sum() / neg), "tpr": float((acepta & y).sum() / pos)})
    return puntos


def ic_bootstrap(parecido: np.ndarray, y: np.ndarray, tau: float, repeticiones: int = 2000) -> dict:
    """IC 95 % por percentiles, remuestreando renglones; el AUC con el mismo remuestreo."""
    rng = np.random.default_rng(n.SEMILLA_BASE)
    acum: dict[str, list[float]] = {"precision": [], "recall": [], "f1": [], "auc": []}
    for _ in range(repeticiones):
        i = rng.integers(0, len(y), len(y))
        m = matriz_confusion(parecido[i], y[i], tau)
        for k in ("precision", "recall", "f1"):
            if m[k] is not None:
                acum[k].append(m[k])
        a = auc(parecido[i], y[i])
        if a is not None:
            acum["auc"].append(a)
    return {k: [float(np.percentile(v, 2.5)), float(np.percentile(v, 97.5))] for k, v in acum.items()}


def elegir_tau(parecido: np.ndarray, y: np.ndarray) -> float:
    for tau in np.unique(parecido):
        m = metricas(parecido, y, float(tau))
        if m["precision"] is not None and m["precision"] >= OBJETIVO_PRECISION:
            return float(tau)
    return 1.0


def main() -> int:
    pares = pares_etiquetados()
    parecido = np.array([p["parecido"] for p in pares])
    y = np.array([p["acierto"] for p in pares])
    listas = sorted({p["lista"] for p in pares})
    salida: dict = {
        "tabla_transicion_resolucion": contar_tabla(),
        "pares": len(pares),
        "listas": len(listas),
        "colegios": dict(collections.Counter(p["colegio"] for p in pares)),
        "aciertos": int(y.sum()),
        "parecido_valores_distintos": int(len(np.unique(parecido))),
        "parecido_min_mediana_max": [float(parecido.min()), float(np.median(parecido)), float(parecido.max())],
        "auc_parecido": auc(parecido, y),
        "en_tau_actual": metricas(parecido, y, TAU_ACTUAL),
        "matriz_tau_actual": matriz_confusion(parecido, y, TAU_ACTUAL),
        "ic95_bootstrap_tau_actual": ic_bootstrap(parecido, y, TAU_ACTUAL),
        "roc": curva_roc(parecido, y),
        "curva": [metricas(parecido, y, t) for t in (0.0, 0.5, 0.6, 0.7, 0.75, 0.8, 0.85, 0.9, 0.95, 1.0)],
    }
    rng = np.random.default_rng(n.SEMILLA_BASE)
    orden = np.array(listas)
    rng.shuffle(orden)
    pliegue_de = {lista: i % PLIEGUES for i, lista in enumerate(orden)}
    fold = np.array([pliegue_de[p["lista"]] for p in pares])
    filas = []
    for k in range(PLIEGUES):
        ent, pru = fold != k, fold == k
        if pru.sum() == 0 or ent.sum() == 0:
            continue
        tau = elegir_tau(parecido[ent], y[ent])
        filas.append({"pliegue": k, "n_prueba": int(pru.sum()), "tau": tau, **metricas(parecido[pru], y[pru], tau)})
    salida["validacion_cruzada_agrupada"] = filas
    n.guardar("tau.json", salida)
    print(salida["pares"], salida["listas"], salida["aciertos"], salida["parecido_valores_distintos"], salida["auc_parecido"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
