"""
07_run_full_benchmark.py
Script que automatiza la ejecución de los 5 enfoques de extracción sobre el 
Gold Standard y calcula P/R/F1, Latencia y Costos para generar el reporte LaTeX.
"""
import json
import time
import base64
import gc
from pathlib import Path
import os
import sys

base_dir = Path(__file__).resolve().parent
project_root = base_dir.parent

# Cargar variables de entorno desde .env si existe
env_path = project_root / ".env"
if env_path.exists():
    with open(env_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())

sys.path.insert(0, str(base_dir))

# Importar funciones
import importlib
extraer_textos = importlib.import_module("02_extraer_textos")
pre_anotar = importlib.import_module("03_pre_anotar")
bench_docling = importlib.import_module("05_bench_docling")
bench_lmm = importlib.import_module("05_bench_lmm")
import test_alternatives_app
from test_alternatives_app import run_google_vision, init_baidu_model, run_baidu_ocr

def run_benchmark():
    gs_path = base_dir.parent / "corpus" / "gold_standard_construido.json"
    listas_dir = base_dir.parent.parent / "TesisDocumentos" / "Listas"
    
    with open(gs_path, "r", encoding="utf-8") as f:
        gs = json.load(f)
        
    documentos = gs["documentos"]
    
    resultados_por_enfoque = {
        "OCR Baseline": [],
        "Google Vision": [],
        "Baidu GOT-OCR": [],
        "Docling": [],
        "Gemini (LMM)": []
    }
    
    out_path = base_dir.parent / "corpus" / "resultados_benchmark_10.json"
    archivos_procesados = set()
    if out_path.exists():
        with open(out_path, "r", encoding="utf-8") as f:
            try:
                resultados_por_enfoque = json.load(f)
                archivos_procesados = {item["archivo"] for item in resultados_por_enfoque["OCR Baseline"]}
                print(f"Resumiendo desde progreso anterior. Documentos ya procesados: {len(archivos_procesados)}")
            except json.JSONDecodeError:
                print("Error al leer archivo de resultados, empezando de cero.")
    
    for i, doc in enumerate(documentos):
        archivo = doc["archivo"]
        colegio = doc.get("colegio", "Desconocido")
        items_gold = doc["items"]
        
        filepath = listas_dir / archivo
        if archivo in archivos_procesados:
            print(f"\n[{i+1}/{len(documentos)}] Saltando {archivo} (ya procesado)...")
            continue
        # Intentar buscar el archivo mediante rglob si no está en la raíz
        if not filepath.exists():
            matches = list(listas_dir.rglob(archivo))
            if matches:
                filepath = matches[0]
            else:
                print(f"Archivo no encontrado: {archivo}")
                continue
                
        print(f"\n[{i+1}/{len(documentos)}] Procesando {archivo}...")
        
        # 1. OCR Baseline
        inicio = time.perf_counter()
        res_text = extraer_textos.extraer_texto_pdf_tipografico(filepath)
        if len(res_text.get("texto_completo", "")) < 50:
            res_text = extraer_textos.extraer_texto_pdf_ocr(filepath)
        items_ocr = pre_anotar.parsear_items_desde_texto(res_text.get("texto_completo", ""))
        lat_ocr = time.perf_counter() - inicio
        resultados_por_enfoque["OCR Baseline"].append({
            "archivo": archivo, "colegio": colegio, "items_gold_data": items_gold,
            "items_pred_data": items_ocr, "latencia_s": lat_ocr, "costo_usd": 0
        })
        print(f"  - OCR Baseline: {len(items_ocr)} items en {lat_ocr:.2f}s")
        
        # 2. Google Vision
        res_gv = run_google_vision(filepath)
        resultados_por_enfoque["Google Vision"].append({
            "archivo": archivo, "colegio": colegio, "items_gold_data": items_gold,
            "items_pred_data": res_gv.get("items", []), "latencia_s": res_gv.get("latencia_s", 0), "costo_usd": 0.0015
        })
        print(f"  - Google Vision: {len(res_gv.get('items', []))} items")
        
        # 3. Baidu GOT-OCR (OOM Safe)
        import torch
        init_baidu_model()
        res_baidu = run_baidu_ocr(filepath)
        resultados_por_enfoque["Baidu GOT-OCR"].append({
            "archivo": archivo, "colegio": colegio, "items_gold_data": items_gold,
            "items_pred_data": res_baidu.get("items", []), "latencia_s": res_baidu.get("latencia_s", 0), "costo_usd": 0
        })
        print(f"  - Baidu GOT-OCR: {len(res_baidu.get('items', []))} items")
        
        # Liberar memoria de Baidu antes de Docling
        test_alternatives_app.baidu_model = None
        test_alternatives_app.baidu_tokenizer = None
        gc.collect()
        torch.cuda.empty_cache()
        
        # 4. Docling
        items_docling, lat_docling, _ = bench_docling.extraer_items_docling(filepath)
        resultados_por_enfoque["Docling"].append({
            "archivo": archivo, "colegio": colegio, "items_gold_data": items_gold,
            "items_pred_data": items_docling, "latencia_s": lat_docling, "costo_usd": 0
        })
        print(f"  - Docling: {len(items_docling)} items en {lat_docling:.2f}s")
        
        # 5. Gemini
        inicio = time.perf_counter()
        b64_imgs = bench_lmm.pdf_a_imagenes_base64(filepath)
        items_gemini, _, cost = bench_lmm.extraer_items_gemini(b64_imgs, model='gemini-3.5-flash-lite')
        lat_gemini = time.perf_counter() - inicio
        resultados_por_enfoque["Gemini (LMM)"].append({
            "archivo": archivo, "colegio": colegio, "items_gold_data": items_gold,
            "items_pred_data": items_gemini, "latencia_s": lat_gemini, "costo_usd": cost
        })
        print(f"  - Gemini: {len(items_gemini)} items en {lat_gemini:.2f}s")
        
        # Liberar posibles cachés de docling
        gc.collect()
        torch.cuda.empty_cache()
        
        # Guardado incremental para no perder el progreso si falla
        out_path = base_dir.parent / "corpus" / "resultados_benchmark_10.json"
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(resultados_por_enfoque, f, ensure_ascii=False, indent=2)
            
    print(f"\nBenchmarking completado. Resultados guardados en {out_path.name}")

if __name__ == "__main__":
    run_benchmark()
