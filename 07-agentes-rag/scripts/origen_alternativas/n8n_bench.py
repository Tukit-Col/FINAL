"""Benchmark n8n: workflow no-code que responde las consultas estructuradas.

El workflow `n8n/workflow/tukit_pregunta.json` expone el webhook
POST /webhook/tukit/pregunta: un nodo Code clasifica el intento (misma
semantica que `graphrag/service.py` del repo principal), el nodo Postgres
consulta `productos_catalogo` y otro nodo Code formatea la respuesta.
Este script envia las 16 preguntas de `datos/preguntas.json`, mide la
latencia end-to-end y puntua el `resumen` contra el gold con el MISMO scorer
de `graphrag_bench.py` (normalizacion de digitos/monedas y de texto).

Uso:
    python scripts/n8n_bench.py [--url http://localhost:5678/webhook/tukit/pregunta]
"""
import argparse
import json
import re
import sys
import time
import unicodedata
import urllib.request
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
WEBHOOK = "http://localhost:5678/webhook/tukit/pregunta"


def _norm(t):
    t = unicodedata.normalize("NFKD", t or "").encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", t.lower()).strip()


def _digitos(t):
    return re.sub(r"\D", "", t or "")


def _puntua_respuesta(q, answer):
    """Mismo scorer que graphrag_bench.py (consulta estructurada)."""
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
    ap.add_argument("--url", default=WEBHOOK)
    ap.add_argument("--salida", default=None)
    args = ap.parse_args()

    preg = json.load(open(RAIZ / "datos" / "preguntas.json", encoding="utf-8"))["preguntas"]
    n = len(preg)

    filas = []
    hits = 0
    t_total = 0.0
    for q in preg:
        body = json.dumps({"pregunta": q["pregunta"]}, ensure_ascii=False).encode()
        req = urllib.request.Request(args.url, data=body,
                                     headers={"Content-Type": "application/json"})
        t0 = time.time()
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                d = json.load(r)
        except Exception as exc:  # noqa: BLE001
            filas.append({
                "tipo": q["tipo"], "pregunta": q["pregunta"], "gold": q["gold"],
                "resumen": "", "hit": False, "latencia_s": round(time.time() - t0, 3),
                "error": str(exc),
            })
            continue
        dt = time.time() - t0
        t_total += dt
        resumen = d.get("resumen") or ""
        hit, extra = _puntua_respuesta(q, resumen)
        if hit:
            hits += 1
        filas.append({
            "tipo": q["tipo"], "pregunta": q["pregunta"], "gold": q["gold"],
            "resumen": resumen, "hit": hit,
            "tipo_clasificado": d.get("tipo"),
            "latencia_s": round(dt, 3),
        })

    res = {
        "pipeline": "n8n",
        "motor": "workflow no-code (nodos Code + Postgres)",
        "webhook": args.url,
        "hit_respuesta": round(hits / n, 4),
        "tiempo_pregunta_promedio_s": round(t_total / n, 3),
        "detalles": filas,
    }
    salida = Path(args.salida or RAIZ / "resultados" / "n8n.json")
    salida.parent.mkdir(parents=True, exist_ok=True)
    salida.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"n8n (workflow no-code)  webhook={args.url}")
    print(f"  hit respuesta: {hits}/{n} = {res['hit_respuesta']}")
    print(f"  tiempo pregunta promedio: {res['tiempo_pregunta_promedio_s']}s")
    print(f"  -> {salida}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
