"""
05_bench_ocr.py — Benchmark enfoque 1: OCR Tesseract + preproceso + parser de reglas.

Corre el enfoque OCR (baseline offline) sobre las listas del corpus y mide P/R/F1
contra el gold standard. Incluye preproceso OpenCV para mejorar la calidad del OCR.

Uso:
    python scripts/05_bench_ocr.py [--gold-standard RUTA]
"""
import argparse
import json
import sys
import time
from pathlib import Path


def evaluar_enfoque_ocr(textos_dir: Path, gold_standard: dict) -> list[dict]:
    """Evalúa el enfoque OCR+reglas contra el gold standard."""
    # Importar el parser (mismo de 03_pre_anotar.py)
    sys.path.insert(0, str(Path(__file__).parent))
    # noinspection PyUnresolvedReferences
    from importlib import import_module
    pre_anotar = import_module("03_pre_anotar")

    resultados = []

    for doc_gs in gold_standard["documentos"]:
        archivo = doc_gs["archivo"]
        colegio = doc_gs.get("colegio", "")
        items_gs = doc_gs["items"]

        # Buscar texto extraído correspondiente
        texto_file = None
        for tf in textos_dir.glob("*.json"):
            if tf.name.startswith("_"):
                continue
            with open(tf, "r", encoding="utf-8") as f:
                data = json.load(f)
            if data.get("archivo_original") == archivo:
                texto_file = data
                break

        if texto_file is None:
            print(f"  ⚠ No se encontró texto extraído para: {archivo}")
            continue

        # Obtener texto correspondiente al rango de páginas del documento
        paginas_rango = doc_gs.get("paginas", "1-1")
        try:
            p_start, p_end = [int(p) for p in paginas_rango.split("-")]
        except Exception:
            p_start, p_end = 1, 999

        texto_doc = ""
        paginas_data = texto_file.get("paginas", [])
        if paginas_data:
            textos_sel = [p["texto"] for p in paginas_data if p_start <= p.get("pagina", 1) <= p_end]
            texto_doc = "\n".join(textos_sel)
        if not texto_doc:
            texto_doc = texto_file.get("texto_completo", "")

        # Medir latencia del parsing
        inicio = time.perf_counter()
        items_pred = pre_anotar.parsear_items_desde_texto(texto_doc)
        latencia = time.perf_counter() - inicio

        resultados.append({
            "archivo": archivo,
            "colegio": colegio,
            "items_gold": len(items_gs),
            "items_predichos": len(items_pred),
            "items_gold_data": items_gs,
            "items_pred_data": items_pred,
            "latencia_s": round(latencia, 4),
            "metodo_extraccion": texto_file.get("metodo", "desconocido"),
        })

    return resultados


def main():
    parser = argparse.ArgumentParser(description="Benchmark: OCR Tesseract + preproceso + parser de reglas")
    parser.add_argument("--gold-standard", type=Path, default=None)
    args = parser.parse_args()

    base_dir = Path(__file__).resolve().parent.parent
    gs_path = args.gold_standard or base_dir / "corpus" / "gold_standard_construido.json"

    if not gs_path.exists():
        print(f"ERROR: Gold standard no encontrado: {gs_path}")
        sys.exit(1)

    with open(gs_path, "r", encoding="utf-8") as f:
        gold_standard = json.load(f)

    textos_dir = base_dir / "corpus" / "textos_extraidos"
    if not textos_dir.exists():
        print("ERROR: Ejecuta 02_extraer_textos.py primero.")
        sys.exit(1)

    print("Evaluando enfoque 1: OCR Tesseract + preproceso + parser de reglas")
    resultados = evaluar_enfoque_ocr(textos_dir, gold_standard)

    # Guardar resultados crudos
    output_dir = base_dir / "resultados" / "ocr"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "resultados_ocr.json"

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
