import os
import argparse
import json
import sys
sys.stdout.reconfigure(encoding="utf-8")
import time
from pathlib import Path

import psycopg2
from psycopg2.extras import DictCursor
from sentence_transformers import SentenceTransformer

RAIZ = Path(__file__).resolve().parents[1]
QUERIES_FILE = RAIZ / "data" / "queries_evaluacion.json"
DSN = os.environ["POC02_DATABASE_URL"]  # credencial retirada al copiar; ver docker-compose de PoC-02
MODEL_NAME = "intfloat/multilingual-e5-large"

# --- LÓGICA DE EXPANSIÓN DE SINÓNIMOS (de la rama fix/synonym-expanded-search) ---
SINONIMOS: dict[str, frozenset[str]] = {
    "esfero": frozenset({"esfero", "esferos", "boligrafo", "bolígrafo", "boligrafos", "bolígrafos", "lapicero", "lapiceros", "birome", "biromes"}),
    "lapiz": frozenset({"lapiz", "lápiz", "lapices", "lápices", "portaminas"}),
    "lapiz de colores": frozenset({"lapiz de colores", "lápiz de colores", "colores", "lapices de colores", "lápices de colores"}),
    "marcador": frozenset({"marcador", "marcadores", "plumon", "plumón", "plumones", "rotulador", "rotuladores"}),
    "cuaderno": frozenset({"cuaderno", "cuadernos", "cuadernillo", "cuadernillos", "libreta", "libretas"}),
    "pegamento": frozenset({"pegamento", "pegamentos", "pegante", "pegantes", "silicona", "goma"}),
    "sacapuntas": frozenset({"sacapuntas", "sacapunta", "tajalapiz", "tajalápiz", "tajalapices", "tajalápices"}),
    "borrador": frozenset({"borrador", "borradores", "goma de borrar", "gomas de borrar"}),
    "cartuchera": frozenset({"cartuchera", "cartucheras", "estuche", "estuches", "bolso utiles"}),
    "mochila": frozenset({"mochila", "mochilas", "morral", "morrales", "maleta", "maletas", "maletin", "maletín"}),
}

_VARIANTE_A_CANONICO = {}
for canonico, variantes in SINONIMOS.items():
    for v in variantes:
        _VARIANTE_A_CANONICO[v] = canonico

def expandir_consulta(texto: str) -> list[str]:
    palabras = texto.lower().split()
    grupos_encontrados = set()
    no_expandibles = []
    resultado = set()
    for p in palabras:
        if p in _VARIANTE_A_CANONICO:
            canonico = _VARIANTE_A_CANONICO[p]
            if canonico not in grupos_encontrados:
                grupos_encontrados.add(canonico)
                resultado.update(SINONIMOS[canonico])
        else:
            no_expandibles.append(p)
    resultado.update(no_expandibles)
    return sorted(list(resultado))

def expandir_para_pg_trgm(texto: str) -> str:
    return " ".join(expandir_consulta(texto))

# --- ESTRATEGIAS DE BÚSQUEDA ---

def buscar_lexica_pura(cur, query: str, limit: int = 20):
    sql = """
    SELECT id, nombre, proveedor, marca, precio,
           word_similarity(%s, nombre) AS score
    FROM productos_catalogo
    WHERE %s <%% nombre
    ORDER BY score DESC
    LIMIT %s;
    """
    t0 = time.time()
    cur.execute(sql, (query, query, limit))
    resultados = cur.fetchall()
    lat = (time.time() - t0) * 1000
    return resultados, lat

def buscar_lexica_expandida(cur, query: str, limit: int = 20):
    query_exp = expandir_para_pg_trgm(query)
    sql = """
    SELECT id, nombre, proveedor, marca, precio,
           word_similarity(%s, nombre) AS score
    FROM productos_catalogo
    WHERE %s <%% nombre
    ORDER BY score DESC
    LIMIT %s;
    """
    t0 = time.time()
    cur.execute(sql, (query_exp, query_exp, limit))
    resultados = cur.fetchall()
    lat = (time.time() - t0) * 1000
    return resultados, lat

def buscar_vectorial(cur, query_vec: list[float], limit: int = 20):
    vec_str = "[" + ",".join(f"{x:.6f}" for x in query_vec) + "]"
    sql = """
    SELECT id, nombre, proveedor, marca, precio,
           1 - (embedding <=> %s::vector) AS score
    FROM productos_catalogo
    ORDER BY embedding <=> %s::vector
    LIMIT %s;
    """
    t0 = time.time()
    cur.execute(sql, (vec_str, vec_str, limit))
    resultados = cur.fetchall()
    lat = (time.time() - t0) * 1000
    return resultados, lat

def buscar_hibrida(cur, query: str, query_vec: list[float], limit: int = 20, rrf_k: int = 60):
    query_exp = expandir_para_pg_trgm(query)
    vec_str = "[" + ",".join(f"{x:.6f}" for x in query_vec) + "]"
    
    # Reciprocal Rank Fusion
    sql = f"""
    WITH lex AS (
        SELECT id, nombre, proveedor, marca, precio,
               word_similarity(%s, nombre) AS lex_score,
               ROW_NUMBER() OVER (ORDER BY word_similarity(%s, nombre) DESC) AS lex_rank
        FROM productos_catalogo
        WHERE %s <%% nombre
        ORDER BY lex_score DESC
        LIMIT 50
    ),
    vec AS (
        SELECT id, 1 - (embedding <=> %s::vector) AS vec_score,
               ROW_NUMBER() OVER (ORDER BY embedding <=> %s::vector) AS vec_rank
        FROM productos_catalogo
        ORDER BY embedding <=> %s::vector
        LIMIT 50
    ),
    fusion AS (
        SELECT COALESCE(lex.id, vec.id) as id,
               COALESCE(1.0 / ({rrf_k} + lex.lex_rank), 0.0) +
               COALESCE(1.0 / ({rrf_k} + vec.vec_rank), 0.0) AS score
        FROM lex
        FULL OUTER JOIN vec ON lex.id = vec.id
    )
    SELECT p.id, p.nombre, p.proveedor, p.marca, p.precio, f.score
    FROM fusion f
    JOIN productos_catalogo p ON p.id = f.id
    ORDER BY f.score DESC
    LIMIT %s;
    """
    t0 = time.time()
    cur.execute(sql, (query_exp, query_exp, query_exp, vec_str, vec_str, vec_str, limit))
    resultados = cur.fetchall()
    lat = (time.time() - t0) * 1000
    return resultados, lat


def main():
    if not QUERIES_FILE.exists():
        print(f"Archivo de queries no encontrado en {QUERIES_FILE}")
        return 1

    with open(QUERIES_FILE, "r", encoding="utf-8") as fh:
        consultas = json.load(fh)["consultas"]

    print("Conectando a PostgreSQL...")
    conn = psycopg2.connect(DSN)
    cur = conn.cursor(cursor_factory=DictCursor)
    
    print(f"Cargando modelo {MODEL_NAME}...")
    model = SentenceTransformer(MODEL_NAME)
    
    resultados_totales = {
        "A_lexica_pura": {"latencias": [], "n_resultados": []},
        "B_lexica_expandida": {"latencias": [], "n_resultados": []},
        "C_vectorial": {"latencias_db": [], "latencias_emb": [], "latencias_total": [], "n_resultados": []},
        "D_hibrida": {"latencias": [], "n_resultados": []}
    }

    print(f"Ejecutando Benchmark con {len(consultas)} consultas...\n")
    for q in consultas:
        print(f"Consulta: '{q}'")
        
        # A. Léxica Pura
        res_A, lat_A = buscar_lexica_pura(cur, q)
        resultados_totales["A_lexica_pura"]["latencias"].append(lat_A)
        resultados_totales["A_lexica_pura"]["n_resultados"].append(len(res_A))
        
        # B. Léxica Expandida
        res_B, lat_B = buscar_lexica_expandida(cur, q)
        resultados_totales["B_lexica_expandida"]["latencias"].append(lat_B)
        resultados_totales["B_lexica_expandida"]["n_resultados"].append(len(res_B))
        
        # Generar embedding (común para C y D)
        t_emb_0 = time.time()
        q_vec = model.encode(f"query: {q}", normalize_embeddings=True).tolist()
        lat_emb = (time.time() - t_emb_0) * 1000
        
        # C. Vectorial Pura
        res_C, lat_C = buscar_vectorial(cur, q_vec)
        resultados_totales["C_vectorial"]["latencias_emb"].append(lat_emb)
        resultados_totales["C_vectorial"]["latencias_db"].append(lat_C)
        resultados_totales["C_vectorial"]["latencias_total"].append(lat_emb + lat_C)
        resultados_totales["C_vectorial"]["n_resultados"].append(len(res_C))
        
        # D. Híbrida
        res_D, lat_D = buscar_hibrida(cur, q, q_vec)
        resultados_totales["D_hibrida"]["latencias"].append(lat_emb + lat_D)
        resultados_totales["D_hibrida"]["n_resultados"].append(len(res_D))
        
        # Imprimir top 1 de cada estrategia
        print(f"  [A] Lex: {res_A[0]['nombre'] if res_A else '∅'} ({lat_A:.1f}ms)")
        print(f"  [B] LexExp: {res_B[0]['nombre'] if res_B else '∅'} ({lat_B:.1f}ms)")
        print(f"  [C] Vec: {res_C[0]['nombre'] if res_C else '∅'} ({(lat_C+lat_emb):.1f}ms)")
        print(f"  [D] Híb: {res_D[0]['nombre'] if res_D else '∅'} ({(lat_D+lat_emb):.1f}ms)\n")

    # Guardar resultados brutos
    import statistics
    res_summary = {}
    for k, v in resultados_totales.items():
        lats = v.get("latencias", v.get("latencias_total"))
        if not lats: continue
        res_summary[k] = {
            "p50_ms": round(statistics.median(lats), 2),
            "avg_ms": round(statistics.mean(lats), 2),
            "max_ms": round(max(lats), 2),
            "avg_resultados": round(statistics.mean(v["n_resultados"]), 1)
        }
        
    out_dir = RAIZ / "results"
    out_dir.mkdir(parents=True, exist_ok=True)
    with open(out_dir / "benchmark_retrieval.json", "w", encoding="utf-8") as fh:
        json.dump(res_summary, fh, indent=2)
        
    print(f"Benchmark completado. Resumen guardado en {out_dir / 'benchmark_retrieval.json'}")
    return 0

if __name__ == "__main__":
    sys.exit(main())
