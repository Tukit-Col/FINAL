"""
Benchmark de modelos de embeddings para retrieval semántico en español.

Compara:
  - all-MiniLM-L6-v2            (baseline monolingüe EN)
  - intfloat/multilingual-e5-small
  - intfloat/multilingual-e5-base
  - intfloat/multilingual-e5-large   (modelo actual de producción en Tukit)
  - baseline léxica de n-gramas (approx. de pg_trgm)

Métricas por modelo: MRR@10, Recall@5, Recall@10, latencia media por
documento y tamaño del modelo (parámetros).
"""
import time

import numpy as np

MODELOS = [
    {"nombre": "paraphrase-multilingual-MiniLM-L12-v2", "id": "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2", "tipo": "multilingüe ligero"},
    {"nombre": "paraphrase-multilingual-mpnet-base-v2", "id": "sentence-transformers/paraphrase-multilingual-mpnet-base-v2", "tipo": "multilingüe"},
    {"nombre": "jina-embeddings-v2-base-es", "id": "jinaai/jina-embeddings-v2-base-es", "tipo": "español dedicado"},
    {"nombre": "multilingual-e5-large", "id": "intfloat/multilingual-e5-large", "tipo": "multilingüe (producción)"},
    {"nombre": "all-MiniLM-L6-v2", "id": "sentence-transformers/all-MiniLM-L6-v2", "tipo": "monolingüe EN"},
]


def _normalizar(texto: str) -> str:
    import unicodedata
    return unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode().lower()


def metricas_retrieval(emb_productos: np.ndarray, emb_consultas: np.ndarray,
                       ids_productos: list[str], ids_relevantes: list[str]) -> dict:
    """Cosine sim vía producto punto sobre vectores normalizados."""
    P = emb_productos / (np.linalg.norm(emb_productos, axis=1, keepdims=True) + 1e-12)
    Q = emb_consultas / (np.linalg.norm(emb_consultas, axis=1, keepdims=True) + 1e-12)
    sims = Q @ P.T  # (n_consultas, n_productos)

    idx = {pid: i for i, pid in enumerate(ids_productos)}
    ranks = np.argsort(-sims, axis=1)
    mrr = 0.0
    r5 = 0.0
    r10 = 0.0
    for i, rel in enumerate(ids_relevantes):
        pos = np.where(ranks[i] == idx[rel])[0][0] + 1
        mrr += 1.0 / pos
        r5 += 1 if pos <= 5 else 0
        r10 += 1 if pos <= 10 else 0
    n = len(ids_relevantes)
    return {"MRR@10": round(mrr / n, 4), "Recall@5": round(r5 / n, 4), "Recall@10": round(r10 / n, 4)}


def evaluar_modelo_fastembed(modelo_id: str, nombres_productos: list[str],
                             consultas: list[str], ids_productos: list[str],
                             ids_relevantes: list[str]) -> dict:
    from fastembed import TextEmbedding

    t0 = time.perf_counter()
    model = TextEmbedding(model_name=modelo_id)
    carga_s = time.perf_counter() - t0

    t0 = time.perf_counter()
    emb_productos = np.array(list(model.embed(nombres_productos)))
    t_embed_docs = time.perf_counter() - t0

    t0 = time.perf_counter()
    emb_consultas = np.array(list(model.embed(consultas)))
    t_embed_q = time.perf_counter() - t0

    res = metricas_retrieval(emb_productos, emb_consultas, ids_productos, ids_relevantes)
    res.update({
        "carga_modelo_s": round(carga_s, 2),
        "latencia_ms_por_doc": round(t_embed_docs / len(nombres_productos) * 1000, 2),
        "latencia_ms_por_query": round(t_embed_q / len(consultas) * 1000, 2),
        "dim": int(emb_productos.shape[1]),
    })
    return res


def evaluar_baseline_ngram(nombres_productos: list[str], consultas: list[str],
                           ids_productos: list[str], ids_relevantes: list[str]) -> dict:
    """Baseline léxica: TF-IDF de n-gramas de caracteres (3-5), emulando el
    matching trigrama de pg_trgm. Sin modelo neuronal."""
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity

    t0 = time.perf_counter()
    vec = TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5),
                          strip_accents="unicode", lowercase=True)
    X_docs = vec.fit_transform(nombres_productos)
    X_q = vec.transform(consultas)
    t_fit = time.perf_counter() - t0

    sims = cosine_similarity(X_q, X_docs)
    idx = {pid: i for i, pid in enumerate(ids_productos)}
    ranks = np.argsort(-sims, axis=1)
    mrr = 0.0
    r5 = 0.0
    r10 = 0.0
    for i, rel in enumerate(ids_relevantes):
        pos = np.where(ranks[i] == idx[rel])[0][0] + 1
        mrr += 1.0 / pos
        r5 += 1 if pos <= 5 else 0
        r10 += 1 if pos <= 10 else 0
    n = len(ids_relevantes)
    return {
        "MRR@10": round(mrr / n, 4),
        "Recall@5": round(r5 / n, 4),
        "Recall@10": round(r10 / n, 4),
        "carga_modelo_s": round(t_fit, 2),
        "latencia_ms_por_doc": 0.0,
        "latencia_ms_por_query": 0.0,
        "dim": int(X_docs.shape[1]),
    }
