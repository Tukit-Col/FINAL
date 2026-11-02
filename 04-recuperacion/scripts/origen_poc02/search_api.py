import time
import psycopg2
import faiss
import numpy as np
import os
import json
import torch
from sentence_transformers import SentenceTransformer

DSN = os.environ["POC02_DATABASE_URL"]  # credencial retirada al copiar; ver docker-compose de PoC-02
MODEL_NAME = "intfloat/multilingual-e5-large"
FAISS_INDEX_PATH = "results/faiss_index.bin"
MAPPING_PATH = "results/faiss_mapping.json"

class RetrievalService:
    def __init__(self):
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        print(f"Cargando modelo ({MODEL_NAME}) en {self.device}...")
        self.model = SentenceTransformer(MODEL_NAME, device=self.device)
        
        self.faiss_index = None
        self.id_to_sku = {}
        if os.path.exists(FAISS_INDEX_PATH) and os.path.exists(MAPPING_PATH):
            print("Cargando índice FAISS...")
            self.faiss_index = faiss.read_index(FAISS_INDEX_PATH)
            with open(MAPPING_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
                self.id_to_sku = {int(k): v for k, v in data.get("id_to_sku", {}).items()}
        else:
            print("No se encontró el índice FAISS. ¿El worker ya procesó los datos?")
            
    def _get_query_embedding(self, query):
        text = f"query: {query}"
        return self.model.encode([text], normalize_embeddings=True)[0]

    def search_faiss(self, query, top_k=5):
        if not self.faiss_index:
            return {"error": "Índice FAISS no cargado", "latency_s": 0}
            
        t0 = time.time()
        xq = self._get_query_embedding(query)
        xq = np.array([xq], dtype=np.float32)
        
        distances, indices = self.faiss_index.search(xq, top_k)
        
        results = []
        for dist, idx in zip(distances[0], indices[0]):
            if idx != -1 and idx in self.id_to_sku:
                sku = self.id_to_sku[idx]
                results.append({"sku": sku, "score": float(dist)})
                
        latency = time.time() - t0
        
        return {
            "backend": "faiss",
            "latency_s": latency,
            "results": results
        }

    def search_pgvector(self, query, top_k=5):
        t0 = time.time()
        xq = self._get_query_embedding(query)
        
        try:
            conn = psycopg2.connect(DSN)
            cur = conn.cursor()
            
            vec_sql = "[" + ",".join(f"{x:.6f}" for x in xq) + "]"
            
            sql = """
                SELECT sku, 1 - (embedding <=> %s::vector) AS score, nombre
                FROM productos_catalogo
                WHERE embedding IS NOT NULL
                ORDER BY embedding <=> %s::vector
                LIMIT %s
            """
            cur.execute(sql, (vec_sql, vec_sql, top_k))
            rows = cur.fetchall()
            
            results = [{"sku": r[0], "score": float(r[1]), "nombre": r[2]} for r in rows]
            
            cur.close()
            conn.close()
            
            latency = time.time() - t0
            
            return {
                "backend": "pgvector",
                "latency_s": latency,
                "results": results
            }
        except Exception as e:
            return {"error": str(e), "latency_s": 0}

if __name__ == "__main__":
    service = RetrievalService()
    q = "cuaderno cuadriculado norma"
    print(f"\nQuery: '{q}'")
    print(json.dumps(service.search_faiss(q, top_k=3), indent=2))
    print(json.dumps(service.search_pgvector(q, top_k=3), indent=2))
