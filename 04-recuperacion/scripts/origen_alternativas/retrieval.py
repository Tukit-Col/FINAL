"""
Recuperadores intercambiables para el benchmark NL2C: mismo contrato
(.buscar(descripcion, k), .mapear_items(items, umbral), .productos).

- CatalogoLexico:      TF-IDF de n-gramas de caracteres (approx. pg_trgm),
                       el matching de producción del enfoque actual.
- CatalogoSemantico:   embeddings multilingües fastembed
                       (paraphrase-multilingual-MiniLM-L12-v2) + coseno.
                       Captura sinonimia que el léxico no ve ("maleta con
                       carrito para libros" ↔ "cartuchera con ruedas").
"""
import numpy as np


class CatalogoLexico:
    def __init__(self, productos: list[dict]) -> None:
        import unicodedata
        from sklearn.feature_extraction.text import TfidfVectorizer

        self.productos = productos
        self._normalizar = lambda t: unicodedata.normalize(
            "NFKD", t).encode("ascii", "ignore").decode().lower()
        nombres = [self._normalizar(p["nombre"]) for p in productos]
        self._vec = TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5),
                                    strip_accents="unicode", lowercase=True)
        self._X = self._vec.fit_transform(nombres)

    def buscar(self, descripcion: str, k: int = 3) -> list[dict]:
        from sklearn.metrics.pairwise import cosine_similarity
        q = self._vec.transform([self._normalizar(descripcion)])
        sims = cosine_similarity(q, self._X)[0]
        top = sims.argsort()[::-1][:k]
        return [
            {**self.productos[i], "score": round(float(sims[i]), 4)}
            for i in top if sims[i] > 0
        ]

    def mapear_items(self, items: list[dict], umbral: float = 0.30) -> list[dict]:
        return _mapear(self, items, umbral)


class CatalogoSemantico:
    """Embeddings multilingües + coseno. Carga el modelo la primera vez."""

    def __init__(self, productos: list[dict],
                 modelo_id: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2") -> None:
        from fastembed import TextEmbedding

        self.productos = productos
        self._modelo = TextEmbedding(model_name=modelo_id)
        nombres = [p["nombre"] for p in productos]
        emb = np.array(list(self._modelo.embed(nombres)))
        self._E = emb / (np.linalg.norm(emb, axis=1, keepdims=True) + 1e-12)

    def _sims(self, descripcion: str) -> np.ndarray:
        q = np.array(list(self._modelo.embed([descripcion])))[0]
        q = q / (np.linalg.norm(q) + 1e-12)
        return self._E @ q

    def buscar(self, descripcion: str, k: int = 3) -> list[dict]:
        sims = self._sims(descripcion)
        top = sims.argsort()[::-1][:k]
        return [
            {**self.productos[i], "score": round(float(sims[i]), 4)}
            for i in top if sims[i] > 0
        ]

    def mapear_items(self, items: list[dict], umbral: float = 0.30) -> list[dict]:
        return _mapear(self, items, umbral)


def _mapear(retrieval, items: list[dict], umbral: float) -> list[dict]:
    resultado = []
    for it in items:
        mejores = retrieval.buscar(it["descripcion"], k=1)
        if mejores and mejores[0]["score"] >= umbral:
            resultado.append({
                "id": mejores[0]["id"], "cantidad": it["cantidad"],
                "descripcion": it["descripcion"], "score": mejores[0]["score"],
            })
        else:
            resultado.append({
                "id": None, "cantidad": it["cantidad"],
                "descripcion": it["descripcion"], "score": 0.0,
            })
    return resultado
