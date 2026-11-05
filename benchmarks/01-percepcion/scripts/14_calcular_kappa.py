"""
14_calcular_kappa.py — Fase 4 F3-5.1: acuerdo (Cohen kappa) CLF vs LLM (2.º anotador).

Compara `corpus/anotable_2026.json` (categoría de 09) contra
`corpus/predicciones_llm_2026.json` (baseline LLM) por ítem `id`: kappa global,
por categoría y por documento, en una tabla markdown impresa en stdout.

Uso:
    python scripts/14_calcular_kappa.py [--anotable ...] [--predicciones ...] [--min-por-cat 5]
"""
import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
DEFAULT_ANOTABLE = REPO / "poc_01_percepcion" / "corpus" / "anotable_2026.json"
DEFAULT_PRED = REPO / "poc_01_percepcion" / "corpus" / "predicciones_llm_2026.json"


def kappa(a, b):
    from sklearn.metrics import cohen_kappa_score
    return cohen_kappa_score(a, b)


def main():
    ap = argparse.ArgumentParser(description="Kappa CLF vs LLM sobre corpus 2026")
    ap.add_argument("--anotable", type=str, default=str(DEFAULT_ANOTABLE))
    ap.add_argument("--predicciones", type=str, default=str(DEFAULT_PRED))
    ap.add_argument("--min-por-cat", type=int, default=5)
    args = ap.parse_args()

    anotable = json.load(open(args.anotable))
    preds_file = json.load(open(args.predicciones))
    preds = {p["id"]: p for p in preds_file["documentos_anotados"]}

    pares = []
    for d in anotable["documentos"]:
        for it in d["items"]:
            if it["id"] in preds:
                pares.append((d["id"], it["id"], it["categoria"], preds[it["id"]].get("categoria")))

    if not pares:
        sys.exit("No hay ids coincidentes entre anotable y predicciones (¿corrió 13_anotar_llm?).")
    a, b = [p[2] for p in pares], [p[3] for p in pares]
    k = kappa(a, b)
    print(f"COINCIDENTES={len(pares)}  KAPPA GLOBAL={k:.4f}\n")

    print("| Categoría | n | acuerdo | kappa |")
    print("|---|---|---|---|")
    por_cat = {}
    for _, _, x, y in pares:
        por_cat.setdefault(x, []).append(y == x)
    for cat in sorted(por_cat, key=lambda c: -len(por_cat[c])):
        vals = por_cat[cat]
        n = len(vals)
        if n < args.min_por_cat:
            continue
        bin_a = [1 if (x == cat) else 0 for x, _, _, _ in [p for p in pares]]
        bin_b = [1 if (y == cat) else 0 for _, _, _, y in pares]
        kc = kappa(bin_a, bin_b) if len(set(bin_a) | set(bin_b)) > 1 else float("nan")
        print(f"| {cat} | {n} | {sum(vals)/n:.2f} | {kc:.4f}" if len(set(bin_a) | set(bin_b)) > 1 else f"| {cat} | {n} | {sum(vals)/n:.2f} | -")

    print("\n| Documento | n | kappa |")
    print("|---|---|---|")
    por_doc = {}
    for doc, _, x, y in pares:
        por_doc.setdefault(doc, []).append((x, y))
    for doc in sorted(por_doc, key=lambda d2: -len(por_doc[d2])):
        a2 = [x for x, _ in por_doc[doc]]
        b2 = [y for _, y in por_doc[doc]]
        print(f"| {doc} | {len(a2)} | {kappa(a2, b2):.4f} |")


if __name__ == "__main__":
    main()