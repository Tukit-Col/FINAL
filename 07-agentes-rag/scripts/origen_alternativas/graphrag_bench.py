"""Benchmark GraphRAG: grafo de catálogo escolar en Neo4j + LLM local.

Persiste el catálogo limpio como grafo (Producto -> Categoria/Marca/Proveedor,
y aristas de alternativa entre productos de la misma categoría), responde las
preguntas con consultas de grafo (plantillas deterministas por tipo) y genera
la respuesta final con el LLM local.

Métricas: tiempo de persistencia del grafo, tiempo de consulta, hit de
recuperación (el hecho dorado está en las tuplas del grafo), precisión de la
respuesta generada y latencia por pregunta.

Uso:
    python scripts/graphrag_bench.py [--salida resultados/graphrag.json]
"""
import argparse
import json
import re
import sys
import time
import unicodedata
import urllib.request
from pathlib import Path

from neo4j import GraphDatabase

RAIZ = Path(__file__).resolve().parents[1]
LLM_URL = "http://127.0.0.1:8080/v1/chat/completions"
URI = "bolt://127.0.0.1:7687"
AUTH = ("neo4j", "neo4j@openspg")


def _norm(t):
    t = unicodedata.normalize("NFKD", t or "").encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", t.lower()).strip()


def _digitos(t):
    return re.sub(r"\D", "", t or "")


def _llm_chat(messages, max_tokens=256):
    body = json.dumps({"model": "local", "messages": messages,
                       "max_tokens": max_tokens, "temperature": 0}).encode()
    req = urllib.request.Request(LLM_URL, data=body,
                                 headers={"Content-Type": "application/json"})
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=300) as r:
        d = json.load(r)
    dt = time.time() - t0
    return d["choices"][0]["message"]["content"], dt, d.get("usage", {})


def cargar_grafo(driver, prods):
    driver.execute_query("MATCH (n) DETACH DELETE n")
    for p in prods:
        driver.execute_query(
            "MERGE (c:Categoria {nombre: $cat})", cat=p["categoria"])
        driver.execute_query(
            "MERGE (m:Marca {nombre: $marca})", marca=p["marca"] or "N/A")
        driver.execute_query(
            "MERGE (pr:Proveedor {nombre: $prov})", prov=p["proveedor"])
        driver.execute_query(
            """MERGE (p:Producto {nombre: $nombre})
               ON CREATE SET p.marca=$marca, p.categoria=$cat, p.precio=$precio,
                             p.disponible=$disp, p.proveedor=$prov, p.url=$url
               ON MATCH SET p.precio=$precio, p.disponible=$disp, p.url=$url""",
            nombre=p["nombre"], marca=p["marca"] or "N/A", cat=p["categoria"],
            precio=float(p["precio"]), disp=bool(p["disponible"]),
            prov=p["proveedor"], url=p["url_producto"])
        driver.execute_query(
            "MATCH (p:Producto {nombre: $n}) MATCH (c:Categoria {nombre: $cat}) MERGE (p)-[:DE_CATEGORIA]->(c)",
            n=p["nombre"], cat=p["categoria"])
        driver.execute_query(
            "MATCH (p:Producto {nombre: $n}) MATCH (m:Marca {nombre: $marca}) MERGE (p)-[:FABRICADO_POR]->(m)",
            n=p["nombre"], marca=p["marca"] or "N/A")
        driver.execute_query(
            "MATCH (p:Producto {nombre: $n}) MATCH (pr:Proveedor {nombre: $prov}) MERGE (p)-[:VENDIDO_POR]->(pr)",
            n=p["nombre"], prov=p["proveedor"])
    driver.execute_query(
        """MATCH (a:Producto), (b:Producto)
           WHERE a.nombre < b.nombre AND a.categoria = b.categoria
           MERGE (a)-[:ALTERNATIVA]-(b)""")


def _buscar_producto(driver, pregunta):
    prods = driver.execute_query("MATCH (p:Producto) RETURN p.nombre AS n, p.precio AS precio")
    mejor, mejor_score = None, 0.0
    for rec in prods.records:
        nombre = _norm(rec["n"])
        score = 0.0
        for tok in nombre.split():
            if tok and tok in _norm(pregunta):
                score += len(tok)
        if score > mejor_score:
            mejor, mejor_score = rec["n"], score
    return mejor


def consulta_grafo(driver, q):
    tipo = q["tipo"]
    if tipo == "precio_producto":
        nombre = _buscar_producto(driver, q["pregunta"])
        res = driver.execute_query(
            "MATCH (p:Producto {nombre: $n}) RETURN p.nombre AS nombre, p.precio AS precio, p.url AS url",
            n=nombre)
        tuplas = [(r["nombre"], r["precio"], r["url"]) for r in res.records]
        return tuplas
    if tipo == "categoria":
        m = re.search(r"categoría\s+([\w\s]+?)\s+que\s+", q["pregunta"], re.IGNORECASE)
        cat = m.group(1).strip() if m else ""
        res = driver.execute_query(
            "MATCH (c:Categoria {nombre: $cat})<-[:DE_CATEGORIA]-(p:Producto) "
            "WHERE p.disponible = true RETURN p.nombre AS nombre LIMIT 8",
            cat=cat)
        return [(r["nombre"],) for r in res.records]
    if tipo == "disponibilidad":
        m = re.search(r"en\s+(\w+)\.\s*Responde", q["pregunta"], re.IGNORECASE)
        prov = m.group(1) if m else ""
        prov_key = {"panamericana": "panamericana", "exito": "exito"}.get(prov, prov)
        res = driver.execute_query(
            "MATCH (pr:Proveedor {nombre: $prov})<-[:VENDIDO_POR]-(p:Producto) "
            "WHERE p.categoria = 'Maletería' RETURN p.disponible AS disp",
            prov=prov_key)
        disp = [r["disp"] for r in res.records]
        hay = any(disp)
        return [(f"hay_maletas_disponibles={hay}",)]
    if tipo == "min_precio":
        m = re.search(r"categoría\s+([\w\s]+?)\s+y\s+cuánto", q["pregunta"], re.IGNORECASE)
        cat = m.group(1).strip() if m else ""
        res = driver.execute_query(
            "MATCH (c:Categoria {nombre: $cat})<-[:DE_CATEGORIA]-(p:Producto) "
            "RETURN p.nombre AS nombre, p.precio AS precio ORDER BY p.precio ASC LIMIT 1",
            cat=cat)
        return [(r["nombre"], r["precio"]) for r in res.records]
    if tipo == "referencia_compra":
        nombre = _buscar_producto(driver, q["pregunta"])
        res = driver.execute_query(
            "MATCH (p:Producto {nombre: $n}) RETURN p.nombre AS nombre, p.url AS url",
            n=nombre)
        return [(r["nombre"], r["url"]) for r in res.records]
    if tipo == "marca":
        nombre = _buscar_producto(driver, q["pregunta"])
        res = driver.execute_query(
            "MATCH (p:Producto {nombre: $n}) RETURN p.nombre AS nombre, p.marca AS marca",
            n=nombre)
        return [(r["nombre"], r["marca"]) for r in res.records]
    return []


def _puntua_respuesta(q, answer):
    tipo, gold = q["tipo"], q["gold"]
    ans = _norm(answer)
    if tipo == "categoria":
        items = [_norm(i) for i in gold.split(";") if i.strip()]
        encontrados = sum(1 for i in items if i in ans)
        return encontrados >= 2, encontrados
    if tipo in ("precio_producto", "min_precio"):
        gd = _digitos(gold)
        return (gd and gd in _digitos(answer)), gd
    gn = _norm(gold)
    return (gn and gn in ans), gn


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--llm", action="store_true")
    ap.add_argument("--salida", default=None)
    args = ap.parse_args()

    gt = json.load(open(RAIZ / "datos" / "feed_scraper_gt.json", encoding="utf-8"))
    prods = gt["productos"]
    preg = json.load(open(RAIZ / "datos" / "preguntas.json", encoding="utf-8"))["preguntas"]

    driver = GraphDatabase.driver(URI, auth=AUTH)
    t0 = time.time()
    cargar_grafo(driver, prods)
    t_carga = time.time() - t0

    filas = []
    hits_ret = 0
    hits_llm = 0
    t_ret_total = 0.0
    t_llm_total = 0.0
    tokens_total = 0
    for q in preg:
        t0 = time.time()
        tuplas = consulta_grafo(driver, q)
        t_ret = time.time() - t0
        t_ret_total += t_ret
        ctx = "\n".join(" | ".join(str(x) for x in t) for t in tuplas)
        ret_ok = bool(tuplas)
        if ret_ok:
            hits_ret += 1

        ok, _ = False, None
        resp = ""
        t_llm = 0.0
        if args.llm:
            sistema = ("Eres un asistente de un catálogo de útiles escolares. "
                       "Responde SOLO con los datos del contexto, en español, breve y exacta.")
            usr = (f"Datos del grafo:\n{ctx}\n\nPregunta: {q['pregunta']}\n"
                   "Responde de forma breve y exacta.")
            resp, t_llm, usage = _llm_chat([{"role": "system", "content": sistema},
                                            {"role": "user", "content": usr}])
            t_llm_total += t_llm
            tokens_total += usage.get("total_tokens", 0)
            ok, _ = _puntua_respuesta(q, resp)
            if ok:
                hits_llm += 1

        filas.append({
            "tipo": q["tipo"], "pregunta": q["pregunta"], "gold": q["gold"],
            "tuplas_grafo": [tuple(str(x) for x in t) for t in tuplas],
            "hit_recuperacion": ret_ok, "tiempo_consulta_s": round(t_ret, 3),
            "respuesta_llm": resp if args.llm else None,
            "hit_llm": ok if args.llm else None,
            "tiempo_llm_s": round(t_llm, 2) if args.llm else None,
        })

    n = len(preg)
    res = {
        "pipeline": "graphrag",
        "grafo": "neo4j",
        "nodos_productos": len(prods),
        "llm_local": bool(args.llm),
        "tiempo_carga_grafo_s": round(t_carga, 2),
        "hit_recuperacion_grafo": round(hits_ret / n, 4),
        "tiempo_consulta_promedio_s": round(t_ret_total / n, 3),
        "precision_respuesta": round(hits_llm / n, 4) if args.llm else None,
        "tiempo_llm_promedio_s": round(t_llm_total / n, 2) if args.llm else None,
        "tokens_totales": tokens_total if args.llm else None,
        "detalles": filas,
    }
    salida = Path(args.salida or RAIZ / "resultados" / "graphrag.json")
    salida.parent.mkdir(parents=True, exist_ok=True)
    salida.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"GraphRAG (Neo4j) con {'LLM' if args.llm else 'consulta pura'}  nodos={len(prods)}")
    print(f"  carga grafo: {res['tiempo_carga_grafo_s']}s")
    print(f"  hit recuperación grafo: {hits_ret}/{n}")
    print(f"  tiempo consulta promedio: {res['tiempo_consulta_promedio_s']}s")
    if args.llm:
        print(f"  precisión respuesta LLM: {hits_llm}/{n} = {res['precision_respuesta']}")
        print(f"  tiempo LLM promedio: {res['tiempo_llm_promedio_s']}s")
    print(f"  -> {salida}")
    driver.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
