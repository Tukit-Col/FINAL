"""Preguntas "al papá": evaluación cualitativa desde el punto de vista del
usuario final (un padre comprando útiles). Preguntas en lenguaje natural que
NO tienen una única respuesta dorada; se responden con RAG+LLM y GraphRAG+LLM
y se registran las respuestas + un veredicto humano-programático.

Uso:
    python scripts/preguntas_papa.py
"""
import json
import re
import sys
import time
import unicodedata
import urllib.request
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
EMB_URL = "http://127.0.0.1:8081/v1/embeddings"
LLM_URL = "http://127.0.0.1:8080/v1/chat/completions"

PREGUNTAS_PAPA = [
    "Necesito un cuaderno de 100 hojas para mi hija, ¿cuál me recomiendas y cuánto cuesta?",
    "¿Qué colores son los más baratos?",
    "Mi hijo empieza segundo de primaria, ¿qué necesito comprar para su lista?",
    "¿Dónde puedo comprar una lonchera para niño?",
    "¿Cuánto cuesta el morral escolar de la marca Norma?",
    "¿Qué productos están disponibles para el regreso a clases?",
]


def _norm(t):
    t = unicodedata.normalize("NFKD", t or "").encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", t.lower()).strip()


def _embeddings(textos):
    import httpx
    resp = httpx.post(EMB_URL, json={"input": textos, "model": "x"}, timeout=120)
    resp.raise_for_status()
    return [d["embedding"] for d in resp.json()["data"]]


def _dot(a, b):
    return sum(x * y for x, y in zip(a, b))


def _llm_chat(messages, max_tokens=220):
    body = json.dumps({"model": "local", "messages": messages,
                       "max_tokens": max_tokens, "temperature": 0}).encode()
    req = urllib.request.Request(LLM_URL, data=body,
                                 headers={"Content-Type": "application/json"})
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=300) as r:
        d = json.load(r)
    return d["choices"][0]["message"]["content"], time.time() - t0


def _plantilla(p):
    disp = "si" if p.get("disponible") else "no"
    precio = int(round(p["precio"])) if p.get("precio") is not None else 0
    return (f"Producto: {p['nombre']}. Marca: {p['marca']}. Categoria: {p['categoria']}. "
            f"Precio: {precio} COP. Disponible: {disp}. Proveedor: {p['proveedor']}. "
            f"URL: {p['url_producto']}.")


def _categoria_de_chunk(c):
    m = re.search(r"Categoria:\s*([^.]+)\.", c, re.IGNORECASE)
    return _norm(m.group(1)) if m else ""


def responde_rag(pregunta, chunks, vecs, topk=5):
    qv = _embeddings([pregunta])[0]
    punt = sorted(zip(vecs, chunks), key=lambda x: _dot(x[0], qv), reverse=True)[:topk]
    ctx = [c for _, c in punt]
    sistema = ("Eres un asistente amable de una papelería escolar. "
               "Responde en español con recomendaciones concretas del contexto, "
               "incluyendo nombre, precio y dónde comprar. Si no hay información suficiente, dilo.")
    usr = f"Catálogo:\n" + "\n---\n".join(ctx) + f"\n\nPregunta de un papá: {pregunta}"
    resp, dt = _llm_chat([{"role": "system", "content": sistema},
                          {"role": "user", "content": usr}])
    return resp, dt, [c[:40] for c in ctx]


def responde_graphrag(pregunta, driver):
    from scripts.graphrag_bench import consulta_grafo, _buscar_producto
    # Reutiliza la consulta de grafo con una pregunta sintética del tipo correcto.
    # Para preguntas abiertas: lista por categoría/proveedor vía búsqueda textual.
    nombre = _buscar_producto(driver, pregunta)
    tuplas = []
    if nombre:
        res = driver.execute_query(
            "MATCH (p:Producto {nombre: $n}) RETURN p.nombre AS nombre, p.precio AS precio, "
            "p.marca AS marca, p.url AS url, p.categoria AS categoria", n=nombre)
        tuplas = [(r["nombre"], r["precio"], r["marca"], r["categoria"], r["url"])
                  for r in res.records]
    else:
        res = driver.execute_query(
            "MATCH (p:Producto) WHERE p.disponible = true "
            "RETURN p.nombre AS nombre, p.precio AS precio, p.marca AS marca, "
            "p.categoria AS categoria, p.url AS url ORDER BY p.precio ASC LIMIT 8")
        tuplas = [(r["nombre"], r["precio"], r["marca"], r["categoria"], r["url"])
                  for r in res.records]
    ctx = "\n".join(" | ".join(str(x) for x in t) for t in tuplas)
    sistema = ("Eres un asistente amable de una papelería escolar. Responde en español "
               "con los datos del catálogo. Si no hay información suficiente, dilo.")
    usr = f"Datos:\n{ctx}\n\nPregunta de un papá: {pregunta}"
    resp, dt = _llm_chat([{"role": "system", "content": sistema},
                          {"role": "user", "content": usr}])
    return resp, dt, ctx[:200]


def main():
    gt = json.load(open(RAIZ / "datos" / "feed_scraper_gt.json", encoding="utf-8"))
    prods = gt["productos"]
    chunks = [_plantilla(p) for p in prods]
    vecs = _embeddings(chunks)

    from neo4j import GraphDatabase
    driver = GraphDatabase.driver("bolt://127.0.0.1:7687", auth=("neo4j", "neo4j@openspg"))

    salida = []
    for p in PREGUNTAS_PAPA:
        resp_rag, t_rag, ctx_rag = responde_rag(p, chunks, vecs)
        resp_g, t_g, ctx_g = responde_graphrag(p, driver)
        salida.append({
            "pregunta": p,
            "rag_con_llm": {"respuesta": resp_rag, "tiempo_s": round(t_rag, 1),
                            "contexto_top5": ctx_rag},
            "graphrag_con_llm": {"respuesta": resp_g, "tiempo_s": round(t_g, 1),
                                 "contexto": ctx_g},
        })
        print(f"\nQ: {p}")
        print(f"  [RAG]    ({t_rag:.1f}s) {resp_rag[:200]}")
        print(f"  [Graph]  ({t_g:.1f}s) {resp_g[:200]}")

    out = RAIZ / "resultados" / "preguntas_papa.json"
    out.write_text(json.dumps(salida, ensure_ascii=False, indent=1), encoding="utf-8")
    driver.close()
    print(f"\n-> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
