"""Ejecuta el benchmark agente-vs-actual (NL2C) y guarda resultados.

Uso:
    py -3.12 scripts/run_agentes.py [--casos N] [--sin-agente]
    py -3.12 scripts/run_agentes.py --agente-local <modelo.gguf> [--casos N]
El agente OpenAI requiere OPENAI_API_KEY en el entorno; el agente local
(Qwen2.5 GGUF vía llama-cpp) no requiere red ni key.
"""
import argparse
import json
import sys
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from benchmarks.baseline_actual import extraer_items, extraer_restricciones
from benchmarks.data import generar_catalogo
from benchmarks.nl2c_data import generar_casos
from benchmarks.retrieval import CatalogoLexico, CatalogoSemantico

RAIZ = Path(__file__).resolve().parents[1]
RESULTADOS = RAIZ / "resultados"
RESULTADOS.mkdir(exist_ok=True)


def _norm(texto: str) -> str:
    """Minúsculas y sin acentos para comparar categorías de forma justa."""
    return unicodedata.normalize("NFKD", texto or "").encode("ascii", "ignore").decode().lower()


def _merge_por_id(items: list[dict]) -> list[dict]:
    """Agrupa por id de producto sumando cantidades (dedupe de duplicados)."""
    por_id: dict[str, int] = {}
    for it in items:
        pid = it.get("id") or it.get("id_producto")
        if not pid:
            continue
        por_id[pid] = por_id.get(pid, 0) + int(it.get("cantidad", 1) or 1)
    return [{"id": pid, "cantidad": c} for pid, c in por_id.items()]


def _metricas_items(gt: list[dict], pred: list[dict]) -> dict:
    gt_set = {it["id"] for it in gt}
    pred_set = {it["id"] for it in pred}
    aciertos = len(gt_set & pred_set)
    precision = aciertos / len(pred_set) if pred_set else 0.0
    recall = aciertos / len(gt_set) if gt_set else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0
    cant_ok = 0
    gt_q = {it["id"]: it["cantidad"] for it in gt}
    pred_q = {it["id"]: it["cantidad"] for it in pred}
    for pid in gt_set & pred_set:
        if gt_q[pid] == pred_q.get(pid):
            cant_ok += 1
    return {
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "cantidades_ok": round(cant_ok / len(gt_set & pred_set), 4) if gt_set & pred_set else None,
    }


def _metricas_restricciones(gt: dict, pred: dict) -> dict:
    res = {}
    for clave in ("exclusion_marcas", "precio_max", "categoria"):
        if clave in gt:
            valor_gt = gt[clave]
            valor_pred = pred.get(clave)
            if clave == "exclusion_marcas":
                ok = valor_pred is not None and set(_norm(v) for v in valor_pred) & set(_norm(v) for v in valor_gt)
            elif clave == "categoria":
                ok = valor_pred is not None and _norm(valor_pred) == _norm(valor_gt)
            else:
                ok = valor_pred == valor_gt
            res[clave] = 1 if ok else 0
    return res


def _agregar(claves, aciertos, totales):
    for k, v in claves.items():
        totales[k] = totales.get(k, 0) + 1
        aciertos[k] = aciertos.get(k, 0) + v


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--casos", type=int, default=None)
    ap.add_argument("--sin-agente", action="store_true")
    ap.add_argument("--agente-local", metavar="MODELO_GGUF", default=None,
                    help="usa el agente local (llama-cpp) en vez del agente OpenAI")
    ap.add_argument("--recuperador", choices=("lexico", "e5", "minilm"), default="lexico",
                    help="recuperador del catálogo: TF-IDF n-gram (lexico, producción), "
                         "embeddings e5-large (producción) o MiniLM-L12 (ligero)")
    args = ap.parse_args()

    productos = generar_catalogo(semilla=7)
    casos = generar_casos(productos, semilla=11)
    if args.casos:
        casos = casos[: args.casos]

    MODELOS_EMBEDDING = {
        "e5": "intfloat/multilingual-e5-large",
        "minilm": "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
    }
    if args.recuperador in MODELOS_EMBEDDING:
        catalogo = CatalogoSemantico(productos, MODELOS_EMBEDDING[args.recuperador])
    else:
        catalogo = CatalogoLexico(productos)
    print(f"recuperador: {args.recuperador}", flush=True)

    agente = None
    if not args.sin_agente:
        if args.agente_local:
            from benchmarks.agente_local import AgenteLocalNL2C
            agente = AgenteLocalNL2C(catalogo, args.agente_local)
        else:
            from benchmarks.agente_nl2c import AgenteNL2C
            agente = AgenteNL2C(catalogo)

    filas = []
    aciertos_rest: dict[str, dict[str, int]] = {"actual": {}, "agente": {}}
    totales_rest: dict[str, dict[str, int]] = {"actual": {}, "agente": {}}
    for i, caso in enumerate(casos, 1):
        fila = {"n": i, "tipo": caso["tipo"], "texto": caso["texto"]}

        # ── Enfoque actual (reglas) ────────────────────────────────
        rest = extraer_restricciones(caso["texto"])
        items_crudos = extraer_items(caso["texto"])
        items_map = catalogo.mapear_items(items_crudos)
        pred_actual = _merge_por_id(items_map)
        fila["actual"] = {
            **_metricas_items(caso["items"], pred_actual),
            "restricciones": rest,
            "items_pred": pred_actual,
            "latencia_s": None, "costo_usd": 0.0,
        }
        _agregar(_metricas_restricciones(caso["restricciones"], rest),
                 aciertos_rest["actual"], totales_rest["actual"])

        # ── Agente (LLM) ──────────────────────────────────────────
        if agente is not None:
            salida = agente.resolver(caso["texto"])
            resultado = salida["resultado"]
            if isinstance(resultado, dict):
                items_agente = resultado.get("items", [])
                rest_agente = {
                    k: v for k, v in resultado.items()
                    if k in ("exclusion_marcas", "precio_max", "precio_min", "categoria")
                    and v not in (None, [], "")
                }
            else:
                items_agente, rest_agente = [], {}
            pred_agente = _merge_por_id(items_agente)
            fila["agente"] = {
                **_metricas_items(caso["items"], pred_agente),
                "restricciones": rest_agente,
                "items_pred": pred_agente,
                "llamadas_tool": salida["llamadas_tool"],
                "latencia_s": salida["latencia_s"],
                "tokens": salida["tokens"]["total"],
                "costo_usd": salida["costo_usd"],
            }
            _agregar(_metricas_restricciones(caso["restricciones"], rest_agente),
                     aciertos_rest["agente"], totales_rest["agente"])

        filas.append(fila)
        resumen = {
            "actual": {k: v for k, v in fila["actual"].items() if k in ("f1", "precision", "recall")},
            "agente": {k: v for k, v in fila.get("agente", {}).items() if k in ("f1", "precision", "recall")} if agente is not None else None,
        }
        print(f"[{i}/{len(casos)}] {caso['tipo']}: actual={resumen['actual']} agente={resumen['agente']}")

    # Resumen agregado
    def _prom(filas, clave, metodo):
        vals = [f[metodo].get(clave) for f in filas if metodo in f and f[metodo].get(clave) is not None]
        return round(sum(vals) / len(vals), 4) if vals else None

    resumen = {"casos": len(casos)}
    for metodo in ("actual", "agente"):
        if any(metodo in f for f in filas):
            resumen[metodo] = {
                "f1_prom": _prom(filas, "f1", metodo),
                "precision_prom": _prom(filas, "precision", metodo),
                "recall_prom": _prom(filas, "recall", metodo),
                "cantidades_ok_prom": _prom(filas, "cantidades_ok", metodo),
                "latencia_prom_s": _prom(filas, "latencia_s", metodo),
                "costo_total_usd": round(sum(f[metodo].get("costo_usd", 0.0) for f in filas if metodo in f), 5),
                "llamadas_tool_prom": _prom(filas, "llamadas_tool", metodo),
                "tokens_prom": _prom(filas, "tokens", metodo),
            }
            # restricciones
            resumen[metodo]["restricciones_acc"] = {
                k: round(aciertos_rest[metodo][k] / totales_rest[metodo][k], 4)
                for k in totales_rest[metodo] if k in aciertos_rest[metodo]
            }

    resumen["por_formato"] = {}
    for tipo in ("prosa", "lista"):
        f_tipo = [f for f in filas if f["tipo"] == tipo]
        if not f_tipo:
            continue
        resumen["por_formato"][tipo] = {}
        for metodo in ("actual", "agente"):
            if any(metodo in f for f in f_tipo):
                resumen["por_formato"][tipo][metodo] = {
                    "f1_prom": _prom(f_tipo, "f1", metodo),
                    "n": len(f_tipo),
                }

    salida_json = RESULTADOS / f"agentes_{args.recuperador}.json"
    with open(salida_json, "w", encoding="utf-8") as fh:
        json.dump({"recuperador": args.recuperador, "resumen": resumen, "filas": filas},
                  fh, ensure_ascii=False, indent=2)
    print("\nRESUMEN:")
    print(json.dumps(resumen, ensure_ascii=False, indent=2))
    print("Guardado en", salida_json)


if __name__ == "__main__":
    main()
