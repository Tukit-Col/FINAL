"""Almacen vectorial: busqueda exacta frente a indices aproximados, con vectores reales.

El benchmark original (`benchmarks/vectorstore.py` de Isis2610-G19-Tukit-Alternativas)
usa 10.000 vectores gaussianos isotropos de 1.024 dimensiones. Es el peor caso
posible para un indice aproximado: no hay estructura de vecindad y el top-10
exacto es casi arbitrario. Aqui se repite con dos conjuntos:

- `sintetico`: el mismo del original (10.000 x 1.024, semillas 1 y 2), para
  reproducir sus cifras y agregar HNSW;
- `catalogo`: los 6.122 productos del catalogo limpio de PoC-02
  (`feed_scraper_gt.json`) embebidos con multilingual-e5-large (1.024 d, el
  modelo de produccion), con los 381 textos de renglones reales del gold de
  calibracion como consultas.

Indices: numpy exacto (equivalente a `ORDER BY embedding <=> q` sin indice),
FAISS IndexFlatIP (exacto), IndexIVFFlat (nlist = 64, nprobe = 8, como el
original, y nprobe = 16) e IndexHNSWFlat con los parametros por omision de
pgvector (m = 16, ef_construction = 64, ef_search = 40) y ef_search = 100.
Latencia: una consulta a la vez, un hilo.

    FASTEMBED_CACHE_PATH=... python comparar_indices.py <ruta feed_scraper_gt.json>
        -> ../resultados/indices_vectoriales.json
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import faiss
import numpy as np

AQUI = Path(__file__).resolve().parent
SALIDA = AQUI.parent / "resultados" / "indices_vectoriales.json"
CACHE = Path("/tmp/tukit_vectores_catalogo.npz")
GOLD = AQUI.parents[1] / "05-umbral" / "datos" / "gold_standard_final.csv"
K = 10

faiss.omp_set_num_threads(1)


def _unit(x):
    x = np.asarray(x, dtype=np.float32)
    return x / (np.linalg.norm(x, axis=1, keepdims=True) + 1e-12)


def _gauss(n, d, seed):
    return _unit(np.random.default_rng(seed).normal(size=(n, d)))


def _vectores_catalogo(ruta_feed: Path):
    if CACHE.exists():
        z = np.load(CACHE)
        return z["docs"], z["consultas"]
    import pandas as pd
    from fastembed import TextEmbedding

    feed = json.loads(ruta_feed.read_text(encoding="utf-8"))["productos"]
    nombres = [f"{p['nombre']} {p.get('marca') or ''} {p.get('categoria') or ''}".strip() for p in feed]
    consultas = sorted(pd.read_csv(GOLD)["descripcion"].unique())
    m = TextEmbedding(model_name="intfloat/multilingual-e5-large")
    docs = _unit(list(m.embed(nombres)))
    qs = _unit(list(m.embed(consultas)))
    np.savez_compressed(CACHE, docs=docs, consultas=qs)
    return docs, qs


def _recall(aprox, exacto):
    return float(np.mean([len(set(a) & set(e)) / K for a, e in zip(aprox, exacto)]))


def _uno_a_uno(index, Q):
    t0 = time.perf_counter()
    filas = [index.search(Q[i : i + 1], K)[1][0] for i in range(len(Q))]
    return np.array(filas), (time.perf_counter() - t0) / len(Q) * 1000


def evaluar(X, Q, nombre):
    d = X.shape[1]
    res = {"vectores": int(X.shape[0]), "dim": int(d), "consultas": int(Q.shape[0])}
    t0 = time.perf_counter()
    exacto = []
    for i in range(len(Q)):
        s = X @ Q[i]
        exacto.append(np.argpartition(-s, K)[:K][np.argsort(-s[np.argpartition(-s, K)[:K]])])
    exacto = np.array(exacto)
    res["numpy_exacto"] = {"construccion_s": 0.0, "ms_por_consulta": round((time.perf_counter() - t0) / len(Q) * 1000, 3), "recall@10": 1.0}

    def medir(etiqueta, index, entrenar=False, **params):
        t0 = time.perf_counter()
        if entrenar:
            index.train(X)
        index.add(X)
        construccion = time.perf_counter() - t0
        for k, v in params.items():
            if k == "nprobe":
                index.nprobe = v
            elif k == "efSearch":
                index.hnsw.efSearch = v
        idx, ms = _uno_a_uno(index, Q)
        res[etiqueta] = {
            "construccion_s": round(construccion, 3),
            "ms_por_consulta": round(ms, 3),
            "recall@10": round(_recall(idx, exacto), 4),
            "memoria_mib": round(faiss.serialize_index(index).nbytes / 2**20, 2),
            **params,
        }
        return index

    medir("faiss_flat_ip", faiss.IndexFlatIP(d))
    for nprobe in (8, 16):
        q = faiss.IndexFlatIP(d)
        medir(f"faiss_ivf_flat_nprobe{nprobe}", faiss.IndexIVFFlat(q, d, 64, faiss.METRIC_INNER_PRODUCT), entrenar=True, nprobe=nprobe)
    for ef in (40, 100):
        h = faiss.IndexHNSWFlat(d, 16, faiss.METRIC_INNER_PRODUCT)
        h.hnsw.efConstruction = 64
        medir(f"faiss_hnsw_m16_ef{ef}", h, efSearch=ef)
    print(nombre, json.dumps(res, indent=1), flush=True)
    return res


def main() -> int:
    salida = {"sintetico": evaluar(_gauss(10_000, 1024, 1), _gauss(100, 1024, 2), "sintetico")}
    if len(sys.argv) > 1:
        docs, qs = _vectores_catalogo(Path(sys.argv[1]))
        salida["catalogo"] = evaluar(docs, qs, "catalogo")
    SALIDA.parent.mkdir(parents=True, exist_ok=True)
    SALIDA.write_text(json.dumps(salida, ensure_ascii=False, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
