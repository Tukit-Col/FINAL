"""
Benchmark de motores de búsqueda vectorial (top-k por similitud de coseno).

Tukit migró de FAISS (aproximado) a pgvector (exacto, integrado con
Postgres). Este benchmark compara, sobre vectores sintéticos de la misma
dimensión de producción (1024):
  1. numpy — búsqueda exacta por fuerza bruta (equivalente conceptual a
     pgvector `ORDER BY embedding <=> q`, el estado actual).
  2. FAISS IndexFlatIP — exacta, pero con kernels BLAS optimizados.
  3. FAISS IndexIVFFlat — aproximada (nlist/probes), mide recall vs exacta.

Métricas: tiempo de indexación, latencia por consulta, recall@10 de la
aproximada contra la exacta, y memoria aproximada del índice.
"""
import time

import numpy as np


def _gen_vectores(n: int, d: int, seed: int = 1) -> np.ndarray:
    rng = np.random.default_rng(seed)
    v = rng.normal(size=(n, d)).astype(np.float32)
    return v / (np.linalg.norm(v, axis=1, keepdims=True) + 1e-9)


def exacto_numpy(vectores: np.ndarray, queries: np.ndarray, k: int = 10) -> np.ndarray:
    t0 = time.perf_counter()
    idx = np.argsort(-(queries @ vectores.T), axis=1)[:, :k]
    return idx, time.perf_counter() - t0


def faiss_flat(vectores: np.ndarray, queries: np.ndarray, k: int = 10):
    import faiss
    t0 = time.perf_counter()
    index = faiss.IndexFlatIP(vectores.shape[1])
    index.add(vectores)
    build_s = time.perf_counter() - t0
    t0 = time.perf_counter()
    scores, idx = index.search(queries, k)
    return idx, build_s, time.perf_counter() - t0


def faiss_ivf(vectores: np.ndarray, queries: np.ndarray, k: int = 10,
              nlist: int = 64, nprobe: int = 8):
    import faiss
    t0 = time.perf_counter()
    quantizer = faiss.IndexFlatIP(vectores.shape[1])
    index = faiss.IndexIVFFlat(quantizer, vectores.shape[1], nlist, faiss.METRIC_INNER_PRODUCT)
    index.train(vectores)
    index.add(vectores)
    index.nprobe = nprobe
    build_s = time.perf_counter() - t0
    t0 = time.perf_counter()
    _, idx = index.search(queries, k)
    return idx, build_s, time.perf_counter() - t0


def recall_at_k(approx: np.ndarray, exact: np.ndarray, k: int = 10) -> float:
    total = 0
    for a, e in zip(approx, exact):
        total += len(set(a.tolist()) & set(e.tolist()))
    return round(total / (len(exact) * k), 4)


def ejecutar(n: int = 10_000, d: int = 1024, n_queries: int = 100, k: int = 10,
             nlist: int = 64, nprobe: int = 8) -> dict:
    vectores = _gen_vectores(n, d)
    queries = _gen_vectores(n_queries, d, seed=2)

    idx_np, t_np = exacto_numpy(vectores, queries, k)
    idx_flat, t_flat_build, t_flat_q = faiss_flat(vectores, queries, k)
    idx_ivf, t_ivf_build, t_ivf_q = faiss_ivf(vectores, queries, k, nlist, nprobe)

    return {
        "n": n, "d": d, "n_queries": n_queries, "k": k,
        "numpy": {
            "index_s": 0.0, "query_ms": round(t_np / n_queries * 1000, 3),
            "recall@10": 1.0,
        },
        "faiss_flat": {
            "index_s": round(t_flat_build, 3),
            "query_ms": round(t_flat_q / n_queries * 1000, 3),
            "recall@10": recall_at_k(idx_flat, idx_np, k),
        },
        "faiss_ivf": {
            "index_s": round(t_ivf_build, 3),
            "query_ms": round(t_ivf_q / n_queries * 1000, 3),
            "recall@10": recall_at_k(idx_ivf, idx_np, k),
            "nlist": nlist, "nprobe": nprobe,
        },
    }
