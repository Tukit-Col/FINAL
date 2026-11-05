"""Embeddings sobre datos reales: reordenar el pool anotado del gold de calibracion.

El arnes original (`benchmarks/embeddings.py` de Isis2610-G19-Tukit-Alternativas)
usa un catalogo sintetico de 29 productos y 87 parafrasis, y satura: la linea
base lexica empata con e5-large en MRR 0,9943. Aqui se repite la comparacion
sobre el gold real de `tukit-mvp-pipeline` (542 renglones de listas reales,
5 candidatos cada uno, 1.273 pares correctos anotados a mano):

- para cada renglon con al menos un candidato correcto (392), se ordenan sus 5
  candidatos por coseno(renglon, nombre del producto) y se mide P@1 y MRR;
- sobre los 2.710 pares se mide el ROC-AUC del coseno como senal de acierto.

Ademas se recalcula el arnes sintetico con MRR@10 truncado en 10 y se prueba
e5-large con los prefijos "query: " / "passage: " que su ficha exige.

    FASTEMBED_CACHE_PATH=... python evaluar_embeddings_gold.py
        -> ../resultados/embeddings_gold.json
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics import roc_auc_score

AQUI = Path(__file__).resolve().parent
GOLD = AQUI.parents[1] / "05-umbral" / "datos" / "gold_standard_final.csv"
SALIDA = AQUI.parent / "resultados" / "embeddings_gold.json"

MODELOS = [
    ("multilingual-e5-large", "intfloat/multilingual-e5-large", None),
    ("multilingual-e5-large (prefijos query/passage)", "intfloat/multilingual-e5-large", ("query: ", "passage: ")),
    ("jina-embeddings-v2-base-es", "jinaai/jina-embeddings-v2-base-es", None),
    ("paraphrase-multilingual-mpnet-base-v2", "sentence-transformers/paraphrase-multilingual-mpnet-base-v2", None),
    ("paraphrase-multilingual-MiniLM-L12-v2", "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2", None),
    ("all-MiniLM-L6-v2", "sentence-transformers/all-MiniLM-L6-v2", None),
]


def _unit(x):
    x = np.asarray(x, dtype=np.float32)
    return x / (np.linalg.norm(x, axis=1, keepdims=True) + 1e-12)


def metricas_pool(df: pd.DataFrame, sim: np.ndarray) -> dict:
    df = df.assign(sim=sim)
    y = df["es_correcto"].to_numpy()
    con = df.groupby("item_id")["es_correcto"].transform("max") == 1
    p1, rr = [], []
    for _, g in df[con].groupby("item_id"):
        g = g.sort_values(["sim", "rank_rerank"], ascending=[False, True])
        etiquetas = g["es_correcto"].to_numpy()
        p1.append(float(etiquetas[0]))
        rr.append(1.0 / (int(np.argmax(etiquetas)) + 1))
    return {
        "items": len(p1),
        "p_at_1": round(float(np.mean(p1)), 4),
        "mrr": round(float(np.mean(rr)), 4),
        "roc_auc_pares": round(float(roc_auc_score(y, sim)), 4),
    }


def sinteticas(modelo, prefijos) -> dict:
    """Arnes sintetico original con MRR@10 truncado."""
    raiz = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    if raiz is None:
        return {}
    sys.path.insert(0, str(raiz))
    from benchmarks.data import generar_catalogo, generar_consultas

    productos = generar_catalogo(semilla=7)
    consultas = generar_consultas(productos, semilla=7)
    nombres = [p["nombre"] for p in productos]
    ids = [p["id"] for p in productos]
    textos = [c["consulta"] for c in consultas]
    rel = [c["id_producto"] for c in consultas]
    q_pref, d_pref = prefijos or ("", "")
    if modelo is None:
        vec = TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), strip_accents="unicode", lowercase=True)
        D = vec.fit_transform(nombres)
        sims = (vec.transform(textos) @ D.T).toarray()
    else:
        P = _unit(list(modelo.embed([d_pref + n for n in nombres])))
        Q = _unit(list(modelo.embed([q_pref + t for t in textos])))
        sims = Q @ P.T
    idx = {pid: i for i, pid in enumerate(ids)}
    ranks = np.argsort(-sims, axis=1)
    pos = np.array([int(np.where(ranks[i] == idx[r])[0][0]) + 1 for i, r in enumerate(rel)])
    return {
        "mrr_sin_truncar": round(float(np.mean(1 / pos)), 4),
        "mrr_at_10": round(float(np.mean(np.where(pos <= 10, 1 / pos, 0.0))), 4),
        "recall_at_5": round(float(np.mean(pos <= 5)), 4),
        "recall_at_10": round(float(np.mean(pos <= 10)), 4),
    }


def main() -> int:
    from fastembed import TextEmbedding

    df = pd.read_csv(GOLD)
    consultas = sorted(df["descripcion"].unique())
    productos = sorted(df["nombre_producto"].unique())
    qi = {t: i for i, t in enumerate(consultas)}
    pi = {t: i for i, t in enumerate(productos)}
    salida = {"datos": {"pares": len(df), "renglones": df["item_id"].nunique(), "textos_consulta": len(consultas), "productos": len(productos)}}

    # Linea base lexica: TF-IDF de n-gramas de caracteres 3-5 (aprox. pg_trgm).
    vec = TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), strip_accents="unicode", lowercase=True)
    vec.fit(consultas + productos)
    Q, P = vec.transform(consultas), vec.transform(productos)
    sim = np.asarray([(Q[qi[a]] @ P[pi[b]].T).toarray()[0, 0] for a, b in zip(df["descripcion"], df["nombre_producto"])])
    salida["ngram-3-5 (lexico, aprox. pg_trgm)"] = {**metricas_pool(df, sim), "sintetico": sinteticas(None, None)}
    for etiqueta in ("vec_score", "lex_score", "rerank_score"):
        salida[f"senal guardada: {etiqueta}"] = metricas_pool(df, df[etiqueta].to_numpy(dtype=float))

    for nombre, ident, prefijos in MODELOS:
        modelo = TextEmbedding(model_name=ident)
        q_pref, d_pref = prefijos or ("", "")
        t0 = time.perf_counter()
        EQ = _unit(list(modelo.embed([q_pref + t for t in consultas])))
        EP = _unit(list(modelo.embed([d_pref + t for t in productos])))
        seg = time.perf_counter() - t0
        sim = np.array([float(EQ[qi[a]] @ EP[pi[b]]) for a, b in zip(df["descripcion"], df["nombre_producto"])])
        salida[nombre] = {
            **metricas_pool(df, sim),
            "dim": int(EQ.shape[1]),
            "ms_por_texto": round(1000 * seg / (len(consultas) + len(productos)), 2),
            "sintetico": sinteticas(modelo, prefijos),
        }
        print(nombre, salida[nombre], flush=True)
    SALIDA.parent.mkdir(parents=True, exist_ok=True)
    SALIDA.write_text(json.dumps(salida, ensure_ascii=False, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
