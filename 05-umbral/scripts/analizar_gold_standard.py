"""Análisis ROC/PR sobre el gold-standard etiquetado (542 ítems) para
recalibrar τ/δ del motor de resolución (Stage 3).

Lee los items+candidatos y las anotaciones ya descargadas del artifact
(guardadas como JSON individuales por doc_id) y construye un dataset
candidato-nivel: para cada (item, candidato) del top-5, label=1 si el sku
fue marcado correcto por el humano, label=0 en caso contrario (incluyendo
los ítems marcados "ninguno de estos" como negativos fuertes).

Uso:
    python calibration/analizar_gold_standard.py
"""

import json
import sys
from pathlib import Path

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import numpy as np
from sklearn.metrics import roc_auc_score, roc_curve, precision_recall_curve, average_precision_score

SCRATCH = Path(r"C:\Users\gabri\AppData\Local\Temp\claude\C--Users-gabri-Documents-Tesis\3a46be7d-95f2-47cd-84c1-ff3db15e9237\scratchpad")
ITEMS_DIR = SCRATCH / "items_final" / "items"
ANOT_DIR = SCRATCH / "anotaciones_final" / "anotaciones"


def cargar_dataset():
    filas = []
    items_meta = []  # nivel-ítem: para análisis de δ (gap top1-top2)
    for f in ITEMS_DIR.glob("*.json"):
        doc_id = f.stem
        item = json.loads(f.read_text(encoding="utf-8"))
        anot_path = ANOT_DIR / f"{doc_id}.json"
        if not anot_path.exists():
            continue
        anot = json.loads(anot_path.read_text(encoding="utf-8"))
        skus_correctos = set(anot.get("skus_correctos", []))
        sin_match = anot.get("sin_match_en_catalogo", False)

        candidatos = item.get("candidatos", [])
        confianzas_item = []
        for rank, c in enumerate(candidatos, start=1):
            label = 1 if (not sin_match and c["sku"] in skus_correctos) else 0
            rerank = c.get("rerank_score")
            fila = {
                "item_id": doc_id,
                "descripcion": item.get("descripcion", ""),
                "rank": rank,
                "sku": c["sku"],
                "label": label,
                "rrf_score": c.get("rrf_score", 0.0),
                "lex_score": c.get("lex_score", 0.0),
                "vec_score": c.get("vec_score", 0.0),
                "rerank_score": rerank if rerank is not None else np.nan,
                "max_vec_lex": max(c.get("vec_score", 0.0), c.get("lex_score", 0.0)),
            }
            filas.append(fila)
            confianzas_item.append(fila)

        if confianzas_item:
            items_meta.append({
                "item_id": doc_id,
                "sin_match": sin_match,
                "candidatos": confianzas_item,
            })

    return filas, items_meta


def evaluar_score(nombre, filas):
    y = np.array([f["label"] for f in filas])
    x = np.array([f[nombre] for f in filas], dtype=float)
    mask = ~np.isnan(x)
    y, x = y[mask], x[mask]
    if y.sum() == 0 or y.sum() == len(y):
        print(f"  {nombre}: sin variación en labels, se salta")
        return None

    auc_roc = roc_auc_score(y, x)
    auc_pr = average_precision_score(y, x)

    # mejor umbral por F1
    prec, rec, thr = precision_recall_curve(y, x)
    f1 = np.where((prec + rec) > 0, 2 * prec * rec / (prec + rec + 1e-12), 0)
    # precision_recall_curve devuelve thr de longitud len(prec)-1
    idx_f1 = np.argmax(f1[:-1]) if len(f1) > 1 else 0
    mejor_thr_f1 = thr[idx_f1] if len(thr) > 0 else float("nan")
    mejor_f1 = f1[idx_f1]

    # mejor umbral por Youden's J (ROC)
    fpr, tpr, thr_roc = roc_curve(y, x)
    j = tpr - fpr
    idx_j = np.argmax(j)
    mejor_thr_j = thr_roc[idx_j]

    print(f"  {nombre:14s} ROC-AUC={auc_roc:.3f}  PR-AUC={auc_pr:.3f}  "
          f"mejor_thr(F1)={mejor_thr_f1:.3f} (F1={mejor_f1:.3f})  "
          f"mejor_thr(Youden)={mejor_thr_j:.3f}")
    return {"roc_auc": auc_roc, "pr_auc": auc_pr, "thr_f1": mejor_thr_f1, "f1": mejor_f1, "thr_youden": mejor_thr_j}


def analizar_delta(items_meta, campo="rerank_score"):
    """¿El gap entre el candidato #1 y #2 (por `campo`) predice si el #1 es correcto?"""
    gaps_correctos = []
    gaps_incorrectos = []
    for it in items_meta:
        cands = sorted(it["candidatos"], key=lambda c: c["rank"])
        if len(cands) < 2:
            continue
        v1 = cands[0][campo]
        v2 = cands[1][campo]
        if np.isnan(v1) or np.isnan(v2):
            continue
        gap = v1 - v2
        if cands[0]["label"] == 1:
            gaps_correctos.append(gap)
        else:
            gaps_incorrectos.append(gap)
    if gaps_correctos and gaps_incorrectos:
        print(f"\n  δ sobre {campo} (gap top1-top2):")
        print(f"    top1 CORRECTO   -> gap promedio={np.mean(gaps_correctos):.4f}  mediana={np.median(gaps_correctos):.4f}  n={len(gaps_correctos)}")
        print(f"    top1 INCORRECTO -> gap promedio={np.mean(gaps_incorrectos):.4f}  mediana={np.median(gaps_incorrectos):.4f}  n={len(gaps_incorrectos)}")


def main():
    filas, items_meta = cargar_dataset()
    y = np.array([f["label"] for f in filas])
    print(f"Dataset: {len(filas)} pares (item, candidato) de {len(items_meta)} ítems")
    print(f"Positivos: {y.sum()} ({100*y.mean():.1f}%)  Negativos: {len(y)-y.sum()}")

    print("\n=== Poder discriminativo de cada señal (candidato-nivel) ===")
    resultados = {}
    for campo in ["rrf_score", "lex_score", "vec_score", "rerank_score", "max_vec_lex"]:
        r = evaluar_score(campo, filas)
        if r:
            resultados[campo] = r

    print("\n=== Análisis de δ (margen de ambigüedad top1 vs top2) ===")
    analizar_delta(items_meta, "rerank_score")
    analizar_delta(items_meta, "max_vec_lex")
    analizar_delta(items_meta, "rrf_score")

    # ¿Cuántos items tienen top1 correcto vs no, usando cada señal para elegir el top1?
    print("\n=== Precision@1 (elegir el candidato con mayor score de cada señal) ===")
    for campo in ["rrf_score", "rerank_score", "max_vec_lex"]:
        aciertos = 0
        total = 0
        for it in items_meta:
            if it["sin_match"]:
                continue  # no hay top1 correcto posible
            cands = [c for c in it["candidatos"] if not np.isnan(c[campo])]
            if not cands:
                continue
            mejor = max(cands, key=lambda c: c[campo])
            total += 1
            if mejor["label"] == 1:
                aciertos += 1
        print(f"  {campo:14s} Precision@1 = {aciertos}/{total} = {100*aciertos/total:.1f}%")

    out = Path(__file__).resolve().parent / "resultado_calibracion.json"
    out.write_text(json.dumps({
        "n_pares": len(filas), "n_items": len(items_meta),
        "positivos": int(y.sum()), "resultados_por_senal": resultados,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nResumen guardado en {out}")


if __name__ == "__main__":
    main()
