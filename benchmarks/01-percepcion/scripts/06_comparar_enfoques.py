"""
06_comparar_enfoques.py — Genera tabla comparativa P/R/F1 entre los 3 enfoques.

Lee los resultados de cada benchmark (05_bench_*.py) y calcula Precision,
Recall y F1 contra el gold standard. Genera la tabla comparativa del Anexo Q.

Usa fuzzy matching (difflib.SequenceMatcher, ratio > 0.85) para absorber
variaciones menores de OCR/tipeo en las descripciones.

Uso:
    python scripts/06_comparar_enfoques.py [--gold-standard RUTA]
"""
import argparse
import json
import sys
from difflib import SequenceMatcher
from pathlib import Path

import pandas as pd
from tabulate import tabulate


UMBRAL_FUZZY = 0.75  # ratio mínimo para considerar un match


def normalizar(texto: str) -> str:
    """Normalización básica para comparación."""
    import re
    texto = texto.lower().strip()
    texto = re.sub(r"[^\w\sáéíóúñü]", "", texto)
    texto = re.sub(r"\s+", " ", texto)
    return texto


def match_fuzzy(desc_pred: str, desc_gold: str) -> float:
    """Calcula similitud entre dos descripciones de ítems."""
    a = normalizar(desc_pred)
    b = normalizar(desc_gold)
    return SequenceMatcher(None, a, b).ratio()


def calcular_prf1(items_pred: list[dict], items_gold: list[dict]) -> dict:
    """Calcula Precision, Recall, F1 con indexación rápida y fuzzy matching."""
    if not items_gold:
        return {"precision": 0, "recall": 0, "f1": 0, "tp": 0, "fp": len(items_pred), "fn": 0, "matches": []}

    usados_gold = set()
    tp = 0
    matches = []

    # Pre-indexar descripciones normalizadas de gold
    gold_norm = [normalizar(g.get("descripcion", "")) for g in items_gold]
    gold_map = {}
    for j, g_text in enumerate(gold_norm):
        if g_text not in gold_map:
            gold_map[g_text] = []
        gold_map[g_text].append(j)

    # 1. Pasada rápida: Exact Normalized Match
    items_pendientes = []
    for pred in items_pred:
        desc_pred = pred.get("descripcion", "")
        norm_p = normalizar(desc_pred)

        match_encontrado = False
        if norm_p in gold_map:
            for idx in gold_map[norm_p]:
                if idx not in usados_gold:
                    tp += 1
                    usados_gold.add(idx)
                    matches.append({
                        "pred": desc_pred,
                        "gold": items_gold[idx].get("descripcion", ""),
                        "score": 1.0,
                    })
                    match_encontrado = True
                    break
        if not match_encontrado:
            items_pendientes.append((pred, norm_p))

    # 2. Pasada fallback: Fuzzy Matching sobre items restantes con pre-filtro
    for pred, norm_p in items_pendientes:
        desc_pred = pred.get("descripcion", "")
        mejor_score = 0
        mejor_idx = -1
        set_p = set(norm_p.split())
        chars_p = set(norm_p)

        for j, g_text in enumerate(gold_norm):
            if j in usados_gold:
                continue
            # Pre-filtro 1: Longitud
            len_p = len(norm_p)
            len_g = len(g_text)
            if abs(len_p - len_g) > max(len_p, len_g) * 0.35:
                continue

            # Pre-filtro 2: Caracteres compartidos
            chars_g = set(g_text)
            if len(chars_p & chars_g) / max(len(chars_p | chars_g), 1) < 0.55:
                continue

            # Pre-filtro 3: Si comparten al menos una palabra de 4+ caracteres
            set_g = set(g_text.split())
            if not (set_p & set_g) and len(norm_p) > 10:
                # Comprobar si al menos las primeras 4 letras coinciden
                if norm_p[:4] != g_text[:4]:
                    continue

            score = SequenceMatcher(None, norm_p, g_text).ratio()
            if score > mejor_score:
                mejor_score = score
                mejor_idx = j

        if mejor_score >= UMBRAL_FUZZY and mejor_idx >= 0:
            tp += 1
            usados_gold.add(mejor_idx)
            matches.append({
                "pred": desc_pred,
                "gold": items_gold[mejor_idx].get("descripcion", ""),
                "score": round(mejor_score, 3),
            })

    fp = len(items_pred) - tp
    fn = len(items_gold) - tp

    precision = tp / max(tp + fp, 1)
    recall = tp / max(tp + fn, 1)
    f1 = 2 * precision * recall / max(precision + recall, 1e-10)

    return {
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "total_pred": len(items_pred),
        "total_gold": len(items_gold),
        "matches": matches,
    }


def evaluar_enfoque(resultados: list[dict]) -> dict:
    """Evalúa un enfoque completo (múltiples documentos)."""
    metricas_por_doc = []
    tp_total, fp_total, fn_total = 0, 0, 0
    latencias = []
    costos = []

    for r in resultados:
        items_pred = r.get("items_pred_data", [])
        items_gold = r.get("items_gold_data", [])

        prf1 = calcular_prf1(items_pred, items_gold)
        tp_total += prf1["tp"]
        fp_total += prf1["fp"]
        fn_total += prf1["fn"]
        latencias.append(r.get("latencia_s", 0))
        costos.append(r.get("costo_usd", 0))

        metricas_por_doc.append({
            "archivo": r.get("archivo", ""),
            "colegio": r.get("colegio", ""),
            **prf1,
            "latencia_s": r.get("latencia_s", 0),
            "costo_usd": r.get("costo_usd", 0),
        })

    # Micro-averaged P/R/F1
    precision_micro = tp_total / max(tp_total + fp_total, 1)
    recall_micro = tp_total / max(tp_total + fn_total, 1)
    f1_micro = 2 * precision_micro * recall_micro / max(precision_micro + recall_micro, 1e-10)

    # Macro-averaged P/R/F1
    if metricas_por_doc:
        precision_macro = sum(m["precision"] for m in metricas_por_doc) / len(metricas_por_doc)
        recall_macro = sum(m["recall"] for m in metricas_por_doc) / len(metricas_por_doc)
        f1_macro = sum(m["f1"] for m in metricas_por_doc) / len(metricas_por_doc)
    else:
        precision_macro = recall_macro = f1_macro = 0

    # Latencia percentiles
    latencias_sorted = sorted(latencias) if latencias else [0]
    p50_idx = len(latencias_sorted) // 2
    p95_idx = min(int(len(latencias_sorted) * 0.95), len(latencias_sorted) - 1)

    return {
        "documentos": len(resultados),
        "micro": {
            "precision": round(precision_micro, 4),
            "recall": round(recall_micro, 4),
            "f1": round(f1_micro, 4),
        },
        "macro": {
            "precision": round(precision_macro, 4),
            "recall": round(recall_macro, 4),
            "f1": round(f1_macro, 4),
        },
        "tp_total": tp_total,
        "fp_total": fp_total,
        "fn_total": fn_total,
        "latencia": {
            "promedio_s": round(sum(latencias) / max(len(latencias), 1), 4),
            "p50_s": round(latencias_sorted[p50_idx], 4),
            "p95_s": round(latencias_sorted[p95_idx], 4),
        },
        "costo": {
            "total_usd": round(sum(costos), 4),
            "promedio_usd": round(sum(costos) / max(len(costos), 1), 6),
        },
        "privacidad": "offline",  # se sobreescribe para LMM
        "por_documento": metricas_por_doc,
    }


def main():
    parser = argparse.ArgumentParser(description="Comparar enfoques de percepción: P/R/F1")
    args = parser.parse_args()

    base_dir = Path(__file__).resolve().parent.parent
    resultados_dir = base_dir / "resultados"

    enfoques = {}

    # Cargar resultados de cada enfoque
    ocr_path = resultados_dir / "ocr" / "resultados_ocr.json"
    if ocr_path.exists():
        with open(ocr_path, "r", encoding="utf-8") as f:
            ocr_data = json.load(f)
        metricas = evaluar_enfoque(ocr_data)
        metricas["privacidad"] = "offline (sin datos en la nube)"
        enfoques["OCR Tesseract + Reglas"] = metricas
        print(f"✓ OCR Tesseract: {len(ocr_data)} docs, F1 micro={metricas['micro']['f1']}")

    docling_path = resultados_dir / "docling" / "resultados_docling.json"
    if docling_path.exists():
        with open(docling_path, "r", encoding="utf-8") as f:
            docling_data = json.load(f)
        metricas = evaluar_enfoque(docling_data)
        metricas["privacidad"] = "offline (sin datos en la nube)"
        enfoques["Docling Layout (IBM)"] = metricas
        print(f"✓ Docling: {len(docling_data)} docs, F1 micro={metricas['micro']['f1']}")

    gv_path = resultados_dir / "google_vision" / "resultados_google_vision.json"
    if gv_path.exists():
        with open(gv_path, "r", encoding="utf-8") as f:
            gv_data = json.load(f)
        metricas = evaluar_enfoque(gv_data)
        metricas["privacidad"] = "⚠ cloud (Google Vision API)"
        enfoques["Google Cloud Vision"] = metricas
        print(f"✓ Google Vision: {len(gv_data)} docs, F1 micro={metricas['micro']['f1']}")

    baidu_path = resultados_dir / "baidu_ocr" / "resultados_baidu_ocr.json"
    if baidu_path.exists():
        with open(baidu_path, "r", encoding="utf-8") as f:
            baidu_data = json.load(f)
        metricas = evaluar_enfoque(baidu_data)
        metricas["privacidad"] = "offline (GPU CUDA local)"
        enfoques["Baidu GOT-OCR2.0"] = metricas
        print(f"✓ Baidu GOT-OCR2.0: {len(baidu_data)} docs, F1 micro={metricas['micro']['f1']}")

    # LMM (puede haber múltiples providers)
    lmm_dir = resultados_dir / "lmm"
    if lmm_dir.exists():
        for lmm_file in lmm_dir.glob("resultados_lmm_*.json"):
            provider = lmm_file.stem.replace("resultados_lmm_", "")
            with open(lmm_file, "r", encoding="utf-8") as f:
                lmm_data = json.load(f)
            if lmm_data:
                model = lmm_data[0].get("model", provider)
                metricas = evaluar_enfoque(lmm_data)
                metricas["privacidad"] = "⚠ cloud (datos enviados a API externa)"
                metricas["costo"]["nota"] = "Costo real por llamada API"
                enfoques[f"LMM {provider} ({model})"] = metricas
                print(f"✓ LMM {provider}: {len(lmm_data)} docs, F1 micro={metricas['micro']['f1']}")

    if not enfoques:
        print("\nERROR: No se encontraron resultados de ningún enfoque.")
        print("Ejecuta los scripts 05_bench_*.py primero.")
        sys.exit(1)

    # Tabla comparativa
    print("\n" + "=" * 100)
    print("TABLA COMPARATIVA — PERCEPCIÓN DOCUMENTAL (F3-6.1)")
    print("=" * 100)

    tabla = []
    for nombre, m in enfoques.items():
        tabla.append({
            "Enfoque": nombre,
            "P (micro)": m["micro"]["precision"],
            "R (micro)": m["micro"]["recall"],
            "F1 (micro)": m["micro"]["f1"],
            "P (macro)": m["macro"]["precision"],
            "R (macro)": m["macro"]["recall"],
            "F1 (macro)": m["macro"]["f1"],
            "Lat. p50 (s)": m["latencia"]["p50_s"],
            "Lat. p95 (s)": m["latencia"]["p95_s"],
            "Costo (USD)": m["costo"]["total_usd"],
            "Privacidad": m["privacidad"][:20],
            "Docs": m["documentos"],
        })

    df = pd.DataFrame(tabla)
    print(tabulate(df, headers="keys", tablefmt="github", showindex=False))

    # Guardar tabla y metricas completas
    output_dir = resultados_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    comparativa_path = output_dir / "comparativa_enfoques.json"
    with open(comparativa_path, "w", encoding="utf-8") as f:
        json.dump(enfoques, f, ensure_ascii=False, indent=2)

    tabla_md_path = output_dir / "tabla_comparativa.md"
    with open(tabla_md_path, "w", encoding="utf-8") as f:
        f.write("# Tabla Comparativa — Percepción Documental (F3-6.1)\n\n")
        f.write(tabulate(df, headers="keys", tablefmt="github", showindex=False))
        f.write("\n\n## Notas\n\n")
        f.write(f"- Umbral de fuzzy matching: {UMBRAL_FUZZY}\n")
        f.write(f"- Métricas micro: ponderadas por ítem (favorece documentos con más ítems)\n")
        f.write(f"- Métricas macro: promedio por documento (todos los documentos pesan igual)\n")

    print(f"\nResultados completos guardados en: {comparativa_path}")
    print(f"Tabla markdown guardada en: {tabla_md_path}")


if __name__ == "__main__":
    main()
