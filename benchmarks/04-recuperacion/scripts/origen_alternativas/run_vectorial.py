"""Benchmark: SOLO BASE VECTORIAL vs enfoque actual (reglas) para NL2C.

Compara, sobre el MISMO test set de `nl2c_data` (semilla 11):
  - `actual`      : parser de reglas + recuperador léxico TF-IDF n-gram
                    (producción). Referencia del reporte §5.4.
  - `reglas_e5`   : parser de reglas + recuperador embeddings e5-large.
                    Referencia del reporte §5.4 (F1 0.7260).
  - `vectorial_e5`: SOLO base vectorial (embeddings e5-large) para el mapeo
                    texto→producto, sin parser de reglas ni LLM.
  - `vectorial_minilm`: igual con MiniLM-L12 (modelo ligero).

Uso:  py -3.12 scripts/run_vectorial.py [--casos N] [--umbral 0.30]
Guarda: resultados/vectorial.json
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
from benchmarks.vectorial_only import NL2CVectorial

RAIZ = Path(__file__).resolve().parents[1]
RESULTADOS = RAIZ / "resultados"
RESULTADOS.mkdir(exist_ok=True)

MODELOS_EMBEDDING = {
    "e5": "intfloat/multilingual-e5-large",
    "minilm": "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
}


def _norm(texto: str) -> str:
    return unicodedata.normalize("NFKD", texto or "").encode("ascii", "ignore").decode().lower()


def _merge_por_id(items: list[dict]) -> list[dict]:
    por_id: dict[str, int] = {}
    for it in items:
        pid = it.get("id")
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
    ap.add_argument("--umbral", type=float, default=0.30)
    args = ap.parse_args()

    productos = generar_catalogo(semilla=7)
    casos = generar_casos(productos, semilla=11)
    if args.casos:
        casos = casos[: args.casos]

    lexico = CatalogoLexico(productos)
    e5 = CatalogoSemantico(productos, MODELOS_EMBEDDING["e5"])
    minilm = CatalogoSemantico(productos, MODELOS_EMBEDDING["minilm"])
    vec_e5 = NL2CVectorial(e5, umbral=args.umbral)
    vec_minilm = NL2CVectorial(minilm, umbral=args.umbral)

    metodos = ("actual", "reglas_e5", "reglas_minilm", "vectorial_e5", "vectorial_minilm")
    aciertos_rest: dict[str, dict[str, int]] = {m: {} for m in metodos}
    totales_rest: dict[str, dict[str, int]] = {m: {} for m in metodos}
    filas = []

    for i, caso in enumerate(casos, 1):
        fila = {"n": i, "tipo": caso["tipo"], "texto": caso["texto"]}

        items_crudos = extraer_items(caso["texto"])
        rest = extraer_restricciones(caso["texto"])

        def _medir(retrieval, vectorial: bool) -> dict:
            if vectorial:
                salida = vec_e5.resolver(caso["texto"]) if retrieval is e5 else vec_minilm.resolver(caso["texto"])
                items_map = salida["items"]
                rest_metodo = salida["restricciones"]
                latencia = salida["latencia_s"]
            else:
                items_map = retrieval.mapear_items(items_crudos)
                rest_metodo = rest
                latencia = 0.0
            pred = _merge_por_id(items_map)
            nombre_por_id = {p["id"]: p["nombre"] for p in retrieval.productos}
            detalle = [
                {"id": it.get("id"), "cantidad": it.get("cantidad", 1),
                 "descripcion": it.get("descripcion"), "score": it.get("score", 0.0),
                 "nombre": nombre_por_id.get(it["id"]) if it.get("id") else None}
                for it in items_map
            ]
            return {
                **_metricas_items(caso["items"], pred),
                "restricciones": rest_metodo,
                "items_pred": pred,
                "detalle": detalle,
                "latencia_s": latencia,
            }

        fila["actual"] = _medir(lexico, False)
        fila["reglas_e5"] = _medir(e5, False)
        fila["reglas_minilm"] = _medir(minilm, False)
        fila["vectorial_e5"] = _medir(e5, True)
        fila["vectorial_minilm"] = _medir(minilm, True)

        for metodo in metodos:
            _agregar(_metricas_restricciones(caso["restricciones"], fila[metodo]["restricciones"]),
                     aciertos_rest[metodo], totales_rest[metodo])

        filas.append(fila)
        resumen = {m: fila[m]["f1"] for m in metodos}
        print(f"[{i}/{len(casos)}] {caso['tipo']}: F1={resumen}", flush=True)

    def _prom(clave, metodo, subset=None):
        filas_subset = filas if subset is None else subset
        vals = [f[metodo].get(clave) for f in filas_subset if f[metodo].get(clave) is not None]
        return round(sum(vals) / len(vals), 4) if vals else None

    resumen = {"casos": len(casos), "umbral": args.umbral}
    for metodo in metodos:
        resumen[metodo] = {
            "f1_prom": _prom("f1", metodo),
            "precision_prom": _prom("precision", metodo),
            "recall_prom": _prom("recall", metodo),
            "cantidades_ok_prom": _prom("cantidades_ok", metodo),
            "latencia_prom_s": _prom("latencia_s", metodo),
            "restricciones_acc": {
                k: round(aciertos_rest[metodo][k] / totales_rest[metodo][k], 4)
                for k in totales_rest[metodo] if k in aciertos_rest[metodo]
            },
        }
    resumen["por_formato"] = {}
    for tipo in ("prosa", "lista"):
        f_tipo = [f for f in filas if f["tipo"] == tipo]
        if not f_tipo:
            continue
        resumen["por_formato"][tipo] = {
            m: {"f1_prom": _prom("f1", m, f_tipo), "n": len(f_tipo)} for m in metodos
        }

    umbral_etiqueta = str(args.umbral).replace(".", "_")
    salida_json = RESULTADOS / f"vectorial_umbral_{umbral_etiqueta}.json"
    with open(salida_json, "w", encoding="utf-8") as fh:
        json.dump({"resumen": resumen, "filas": filas}, fh, ensure_ascii=False, indent=2)
    print("\nRESUMEN:")
    print(json.dumps(resumen, ensure_ascii=False, indent=2))
    print("Guardado en", salida_json)


if __name__ == "__main__":
    main()
