"""Evalúa el solver de KAG sobre datos/preguntas.json.

Corre desde kag/tukit (donde está kag_config.yaml):

    python solver/eval.py            # todas las preguntas
    python solver/eval.py --max-n 5  # primeras N (prueba)

Guarda resultados/kag_solver.json con respuesta, traza, hit (gold presente en
la respuesta) y tiempos por pregunta.
"""
import asyncio
import json
import re
import sys
import time
import unicodedata
from pathlib import Path

from kag.common.registry import import_modules_from_path
from kag.interface import SolverPipelineABC

from kag.common.conf import KAG_CONFIG

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

RAIZ = Path(__file__).resolve().parents[2] / ".."  # repo raíz
RAIZ = RAIZ.resolve()
RESULTADOS = RAIZ / "resultados"


def _norm(t):
    t = unicodedata.normalize("NFKD", t or "").encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", t.lower()).strip()


def _digitos(t):
    return re.sub(r"\D", "", t or "")


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


async def resolver_una(pipeline, pregunta):
    t0 = time.time()
    answer = await pipeline.ainvoke(pregunta)
    dt = time.time() - t0
    return answer, dt


async def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-n", type=int, default=0)
    args = ap.parse_args()

    preguntas = json.load(open(RAIZ / "datos" / "preguntas.json", encoding="utf-8"))["preguntas"]
    if args.max_n:
        preguntas = preguntas[: args.max_n]

    import_modules_from_path("./prompt")
    pipeline = SolverPipelineABC.from_config(
        KAG_CONFIG.all_config["kag_solver_pipeline"]
    )

    filas = []
    hits = 0
    t_total = 0.0
    for i, q in enumerate(preguntas, 1):
        print(f"[{i}/{len(preguntas)}] {q['pregunta'][:60]}")
        try:
            answer, dt = await resolver_una(pipeline, q["pregunta"])
        except Exception as exc:  # noqa: BLE001
            print(f"  ERROR: {type(exc).__name__}: {exc}")
            filas.append({"tipo": q["tipo"], "pregunta": q["pregunta"], "gold": q["gold"],
                          "error": str(exc)})
            continue
        t_total += dt
        ok, info = _puntua_respuesta(q, str(answer))
        hits += 1 if ok else 0
        filas.append({"tipo": q["tipo"], "pregunta": q["pregunta"], "gold": q["gold"],
                      "respuesta": str(answer), "hit": ok, "info": info,
                      "tiempo_s": round(dt, 1)})
        print(f"  {ok} ({dt:.1f}s) {str(answer)[:100]}")

    n = len(preguntas)
    res = {
        "pipeline": "kag_solver",
        "llm_local": "qwen2.5-1.5b-instruct",
        "preguntas": n,
        "hit": round(hits / n, 4) if n else None,
        "tiempo_total_s": round(t_total, 1),
        "tiempo_promedio_s": round(t_total / n, 1) if n else None,
        "detalles": filas,
    }
    RESULTADOS.mkdir(parents=True, exist_ok=True)
    out = RESULTADOS / "kag_solver.json"
    out.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"hit {hits}/{n}  tiempo promedio {res['tiempo_promedio_s']}s -> {out}")


if __name__ == "__main__":
    asyncio.run(main())
