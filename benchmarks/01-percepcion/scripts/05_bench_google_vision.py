"""
05_bench_google_vision.py — Benchmark enfoque: Google Cloud Vision API.

Extrae texto de PDFs e imágenes usando Google Cloud Vision API (Document Text Detection)
y parsea los ítems con el parser de reglas. Mide P/R/F1, latencia y costos.

Uso:
    python scripts/05_bench_google_vision.py [--gold-standard RUTA]
"""
import argparse
import json
import os
import sys
import time
from pathlib import Path

# Ajustar paths
base_dir = Path(__file__).resolve().parent
sys.path.insert(0, str(base_dir))

# Configurar credenciales de Google
creds_path = base_dir.parent / "google-credentials.json"
if not creds_path.exists():
    creds_path = Path("c:/Users/gabri/Documents/Tesis/POC-Tesis/google-credentials.json")
if creds_path.exists():
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = str(creds_path)

import importlib
pre_anotar = importlib.import_module("03_pre_anotar")
from test_alternatives_app import run_google_vision


def evaluar_google_vision(gold_standard: dict, listas_dir: Path, max_docs: int = None) -> list[dict]:
    """Evalúa Google Cloud Vision API contra el gold standard."""
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

        print(f"[{i+1}/{len(documentos)}] Procesando {archivo} con Google Vision...")
        res = run_google_vision(filepath)

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
            "costo_usd": 0.0015,  # Costo estimado por llamada API
            "metodo_extraccion": "Google Cloud Vision API",
        })
        print(f"  ✓ {len(items_pred)} ítems extraídos en {latencia:.2f}s")

    return resultados


def main():
    parser = argparse.ArgumentParser(description="Benchmark: Google Cloud Vision API")
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
    print("BENCHMARK: Google Cloud Vision API")
    print("=" * 60)

    resultados = evaluar_google_vision(gold_standard, listas_dir, args.max_docs)

    output_dir = project_root / "resultados" / "google_vision"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "resultados_google_vision.json"

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
