"""
05_bench_baidu_ocr.py — Benchmark enfoque: Baidu GOT-OCR2.0 (Format-Aware Local).

Ejecuta el modelo fundacional multimodal GOT-OCR2.0 localmente con aceleración GPU (CUDA)
en modo format-aware para preservar la estructura visual y espacial de las listas.

Uso:
    python scripts/05_bench_baidu_ocr.py [--gold-standard RUTA]
"""
import argparse
import gc
import json
import os
import sys
import time
from pathlib import Path

# Ajustar paths
base_dir = Path(__file__).resolve().parent
sys.path.insert(0, str(base_dir))

import test_alternatives_app
from test_alternatives_app import run_baidu_ocr, init_baidu_model


def evaluar_baidu_ocr(gold_standard: dict, listas_dir: Path, max_docs: int = None) -> list[dict]:
    """Evalúa Baidu GOT-OCR2.0 contra el gold standard gestionando memoria VRAM."""
    import torch
    documentos = gold_standard["documentos"]
    if max_docs:
        documentos = documentos[:max_docs]

    resultados = []

    for i, doc in enumerate(documentos):
        archivo = doc["archivo"]
        colegio = doc.get("colegio", "Desconocido")
        items_gold = doc["items"]

        filepath = listas_dir / archivo
        if not filepath.exists():
            matches = list(listas_dir.rglob(archivo))
            if matches:
                filepath = matches[0]
            else:
                print(f"  ⚠ Archivo no encontrado: {archivo}")
                continue

        print(f"\n[{i+1}/{len(documentos)}] Procesando {archivo} con Baidu GOT-OCR2.0...")
        
        # Inicializar y ejecutar inferencia
        init_baidu_model()
        res = run_baidu_ocr(filepath)

        items_pred = res.get("items", [])
        latencia = res.get("latencia_s", 0)

        resultados.append({
            "archivo": archivo,
            "colegio": colegio,
            "items_gold": len(items_gold),
            "items_predichos": len(items_pred),
            "items_gold_data": items_gold,
            "items_pred_data": items_pred,
            "latencia_s": round(latencia, 4),
            "costo_usd": 0.0,
            "metodo_extraccion": "Baidu GOT-OCR2.0 (Format)",
        })
        print(f"  ✓ {len(items_pred)} ítems extraídos en {latencia:.2f}s")

        # Liberar memoria VRAM entre archivos
        test_alternatives_app.baidu_model = None
        test_alternatives_app.baidu_tokenizer = None
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

    return resultados


def main():
    parser = argparse.ArgumentParser(description="Benchmark: Baidu GOT-OCR2.0 (Format)")
    parser.add_argument("--gold-standard", type=Path, default=None)
    parser.add_argument("--max-docs", type=int, default=None)
    args = parser.parse_args()

    project_root = base_dir.parent
    gs_path = args.gold_standard or project_root / "corpus" / "gold_standard_construido.json"
    listas_dir = project_root.parent / "TesisDocumentos" / "Listas"

    if not gs_path.exists():
        print(f"ERROR: Gold standard no encontrado en {gs_path}")
        sys.exit(1)

    with open(gs_path, "r", encoding="utf-8") as f:
        gold_standard = json.load(f)

    print("=" * 60)
    print("BENCHMARK: Baidu GOT-OCR2.0 (Format-Aware Local)")
    print("=" * 60)

    resultados = evaluar_baidu_ocr(gold_standard, listas_dir, args.max_docs)

    output_dir = project_root / "resultados" / "baidu_ocr"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "resultados_baidu_ocr.json"

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(resultados, f, ensure_ascii=False, indent=2)

    print(f"\nResultados guardados en: {output_path}")
    print(f"Documentos evaluados: {len(resultados)}")
    total_gold = sum(r["items_gold"] for r in resultados)
    total_pred = sum(r["items_predichos"] for r in resultados)
    lat_avg = sum(r["latencia_s"] for r in resultados) / max(len(resultados), 1)
    print(f"Total ítems gold: {total_gold}")
    print(f"Total ítems predichos: {total_pred}")
    print(f"Latencia promedio: {lat_avg:.4f}s")


if __name__ == "__main__":
    main()
