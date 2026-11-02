"""Benchmark del pipeline RAG base sobre el catálogo escolar limpio.

Dos modos:
  1) RAG sin LLM (solo recuperación): embebe la pregunta, recupera top-k chunks
     por similitud coseno y mide si el hecho dorado aparece en los chunks
     recuperados (hit@k). Métricas de precisión de recuperación + latencia.
  2) RAG con LLM local: recupera top-k, genera la respuesta con el LLM local
     (qwen2.5-1.5b vía OpenAI-compatible en 127.0.0.1:8080) y evalúa si la
     respuesta contiene el hecho dorado.

Chunks = un producto por chunk (misma plantilla que el build de KAG) para
comparar de forma justa con KAG.

Uso:
    python scripts/rag_bench.py [--topk 5] [--llm] [--salida resultados/rag_*.json]
"""
import argparse
import json
import re
import sys
import time
import unicodedata
import urllib.request
from pathlib import Path

import httpx

RAIZ = Path(__file__).resolve().parents[1]
EMB_URL = "http://127.0.0.1:8081/v1/embeddings"
LLM_URL = "http://127.0.0.1:8080/v1/chat/completions"


def _norm(t):
    t = unicodedata.normalize("NFKD", t or "").encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", t.lower()).strip()


def _digitos(t):
    return re.sub(r"\D", "", t or "")


def _embeddings(textos):
    resp = httpx.post(EMB_URL, json={"input": textos, "model": "x"}, timeout=120)
    resp.raise_for_status()
    return [d["embedding"] for d in resp.json()["data"]]


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


def _puntua(q, answer):
    tipo = q["tipo"]
    gold = q["gold"]
    ans = _norm(answer)
    if tipo in ("precio_producto", "min_precio"):
        gd = _digitos(gold)
        return (gd and gd in _digitos(answer)), gd
    gn = _norm(gold)
    return (gn and gn in ans), gn


def _categoria_de_chunk(c):
    m = re.search(r"Categoria:\s*([^.]+)\.", c, re.IGNORECASE)
    return _norm(m.group(1)) if m else ""


def _eval_recuperacion(q, ctx):
    """Evalúa la recuperación: para preguntas de categoría usa precisión de
    categoría del top-k (>=3 chunks de la categoría pedida); para el resto,
    el hecho dorado debe aparecer en el contexto recuperado."""
    if q["tipo"] == "categoria":
        m = re.search(r"categoría\s+([\w\s]+?)\s+que\s+", q["pregunta"], re.IGNORECASE)
        objetivo = _norm(m.group(1)) if m else ""
        aciertos = sum(1 for c in ctx if objetivo and _categoria_de_chunk(c) == objetivo)
        return aciertos >= min(3, aciertos if aciertos else 3), aciertos
    return _puntua(q, " ".join(ctx))


def _puntua_respuesta(q, answer):
    """Evalúa la respuesta generada: recall de ítems dorados (categoría) o
    presencia del hecho dorado."""
    if q["tipo"] == "categoria":
        items = [_norm(i) for i in q["gold"].split(";") if i.strip()]
        encontrados = sum(1 for i in items if i in _norm(answer))
        return encontrados >= 2, encontrados
    return _puntua(q, answer)


def _plantilla(p):
    disp = "si" if p.get("disponible") else "no"
    precio = int(round(p["precio"])) if p.get("precio") is not None else 0
    return (f"Producto: {p['nombre']}. Marca: {p['marca']}. Categoria: {p['categoria']}. "
            f"Precio: {precio} COP. Disponible: {disp}. Proveedor: {p['proveedor']}. "
            f"URL: {p['url_producto']}.")


def _dot(a, b):
    return sum(x * y for x, y in zip(a, b))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--topk", type=int, default=5)
    ap.add_argument("--llm", action="store_true")
    ap.add_argument("--salida", default=None)
    args = ap.parse_args()

    gt = json.load(open(RAIZ / "datos" / "feed_scraper_gt.json", encoding="utf-8"))
    prods = gt["productos"]
    preg = json.load(open(RAIZ / "datos" / "preguntas.json", encoding="utf-8"))["preguntas"]

    chunks = [_plantilla(p) for p in prods]
    t0 = time.time()
    vecs = _embeddings(chunks)
    t_vec = time.time() - t0
    dims = len(vecs[0])

    # Normaliza y guarda para el evaluador de recuperación.
    idx = {_norm(c): v for c, v in zip(chunks, vecs)}

    filas = []
    hits_ret = 0
    t_ret_total = 0.0
    hits_llm = 0
    t_llm_total = 0.0
    tokens_total = 0
    for q in preg:
        t0 = time.time()
        qv = _embeddings([q["pregunta"]])[0]
        # Similitud coseno contra todos los chunks.
        punt = sorted(((idx[c], c) for c in idx), key=lambda x: _dot(x[0], qv), reverse=True)[:args.topk]
        t_ret = time.time() - t0
        t_ret_total += t_ret
        ctx = [c for _, c in punt]
        ret_ok, _ = _eval_recuperacion(q, ctx)
        if ret_ok:
            hits_ret += 1

        resp = ""
        t_llm = 0.0
        if args.llm:
            sistema = ("Eres un asistente de un catálogo de útiles escolares. "
                       "Responde SOLO con la información del contexto, en español, breve y exacta.")
            usr = ("Contexto:\n" + "\n---\n".join(ctx) +
                   f"\n\nPregunta: {q['pregunta']}\nResponde de forma breve y exacta.")
            resp, t_llm, usage = _llm_chat([{"role": "system", "content": sistema},
                                            {"role": "user", "content": usr}])
            t_llm_total += t_llm
            tokens_total += usage.get("total_tokens", 0)
            ok, _ = _puntua_respuesta(q, resp)
            if ok:
                hits_llm += 1

        filas.append({
            "tipo": q["tipo"], "pregunta": q["pregunta"], "gold": q["gold"],
            "hit_recuperacion": ret_ok, "topk": args.topk,
            "tiempo_recuperacion_s": round(t_ret, 3),
            "contexto": ctx if not args.llm else None,
            "respuesta_llm": resp if args.llm else None,
            "hit_llm": ok if args.llm else None,
            "tiempo_llm_s": round(t_llm, 2) if args.llm else None,
        })

    n = len(preg)
    res = {
        "pipeline": "rag_con_llm" if args.llm else "rag_sin_llm",
        "llm_local": bool(args.llm),
        "chunks": len(chunks),
        "topk": args.topk,
        "precision_recuperacion": round(hits_ret / n, 4),
        "tiempo_recuperacion_total_s": round(t_ret_total, 2),
        "tiempo_recuperacion_promedio_s": round(t_ret_total / n, 3),
        "tiempo_vectorizado_chunks_s": round(t_vec, 2),
        "precision_respuesta": round(hits_llm / n, 4) if args.llm else None,
        "tiempo_llm_total_s": round(t_llm_total, 2) if args.llm else None,
        "tiempo_llm_promedio_s": round(t_llm_total / n, 2) if args.llm else None,
        "tokens_totales": tokens_total if args.llm else None,
        "detalles": filas,
    }
    salida = args.salida or (RAIZ / "resultados" / ("rag_con_llm.json" if args.llm else "rag_sin_llm.json"))
    salida = Path(salida)
    salida.parent.mkdir(parents=True, exist_ok=True)
    salida.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"RAG {'con' if args.llm else 'sin'} LLM  topk={args.topk}")
    print(f"  chunks: {len(chunks)} (embeddings {dims}d en {t_vec:.1f}s)")
    print(f"  precisión recuperación: {hits_ret}/{n} = {res['precision_recuperacion']}")
    print(f"  tiempo recuperación promedio: {res['tiempo_recuperacion_promedio_s']}s")
    if args.llm:
        print(f"  precisión respuesta LLM: {hits_llm}/{n} = {res['precision_respuesta']}")
        print(f"  tiempo LLM promedio: {res['tiempo_llm_promedio_s']}s")
        print(f"  tokens totales: {tokens_total}")
    print(f"  -> {salida}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
