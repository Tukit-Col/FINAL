"""
05_bench_docling.py — Benchmark enfoque 2: Docling layout analysis (IBM / LF AI).

Usa Docling para convertir PDFs/DOCXs en markdown con análisis de layout,
luego extrae ítems del markdown y mide P/R/F1 contra el gold standard.

Docling es layout-aware: entiende tablas, columnas y estructura visual del
documento, lo que puede ser superior al OCR crudo + parser de reglas para
listas que usan formatos complejos (tablas, columnas dobles, etc.).

Uso:
    python scripts/05_bench_docling.py [--gold-standard RUTA]

Requisitos:
    pip install docling
"""
import argparse
import json
import sys
import time
from pathlib import Path


def extraer_items_docling(ruta_archivo: Path) -> tuple[list[dict], float, str]:
    """Extrae ítems de un archivo usando Docling + parser de reglas post-conversión."""
    try:
        from docling.document_converter import DocumentConverter
    except ImportError:
        return [], 0, "ERROR: docling no instalado (pip install docling)"

    sys.path.insert(0, str(Path(__file__).parent))
    from importlib import import_module
    pre_anotar = import_module("03_pre_anotar")

    inicio = time.perf_counter()

    try:
        converter = DocumentConverter()
        resultado = converter.convert(str(ruta_archivo))
        markdown = resultado.document.export_to_markdown()
    except Exception as e:
        return [], time.perf_counter() - inicio, f"ERROR: {e}"

    # Parsear ítems del markdown con el parser de reglas
    items = pre_anotar.parsear_items_desde_texto(markdown)
    latencia = time.perf_counter() - inicio

    return items, latencia, markdown


def main():
    parser = argparse.ArgumentParser(description="Benchmark: Docling layout analysis")
    parser.add_argument("--gold-standard", type=Path, default=None)
    parser.add_argument("--max-docs", type=int, default=None, help="Límite opcional de documentos")
    args = parser.parse_args()

    base_dir = Path(__file__).resolve().parent.parent
    gs_path = args.gold_standard or base_dir / "corpus" / "gold_standard_construido.json"
    listas_dir = base_dir.parent / "TesisDocumentos" / "Listas"

    if not gs_path.exists():
        print(f"ERROR: Gold standard no encontrado: {gs_path}")
        sys.exit(1)

    with open(gs_path, "r", encoding="utf-8") as f:
        gold_standard = json.load(f)

    print("Evaluando enfoque 2: Docling layout analysis (IBM / LF AI)")
    resultados = []
    
    docs_a_procesar = gold_standard["documentos"]
    if args.max_docs:
        docs_a_procesar = docs_a_procesar[:args.max_docs]

    # Directorio de caché
    cache_dir = base_dir / "corpus" / "textos_extraidos_docling"
    cache_dir.mkdir(parents=True, exist_ok=True)

    # Instanciar converter una sola vez
    from docling.document_converter import DocumentConverter
    converter = DocumentConverter()

    sys.path.insert(0, str(Path(__file__).parent))
    from importlib import import_module
    pre_anotar = import_module("03_pre_anotar")

    for doc_gs in docs_a_procesar:
        archivo = doc_gs["archivo"]
        colegio = doc_gs.get("colegio", "")
        items_gs = doc_gs["items"]
        
        paginas_rango = doc_gs.get("paginas", "1-1")
        try:
            p_start, p_end = [int(p) for p in paginas_rango.split("-")]
        except Exception:
            p_start, p_end = 1, 999

        ruta_archivo = listas_dir / archivo
        if not ruta_archivo.exists():
            print(f"  ⚠ Archivo no encontrado: {ruta_archivo}")
            continue

        print(f"  Procesando: {doc_gs.get('id', archivo)} - {colegio} ({doc_gs.get('grado', '')})")
        
        safe_name = archivo.replace("/", "_").replace("\\", "_").replace(".pdf", "")
        cache_file = cache_dir / f"{safe_name}_{p_start}_{p_end}.md"

        # Verificar si ya convertimos este archivo y páginas
        if cache_file.exists():
            with open(cache_file, "r", encoding="utf-8") as f:
                markdown = f.read()
            latencia = 0.0
        else:
            inicio = time.perf_counter()
            try:
                # Intentar convertir solo las páginas solicitadas
                resultado = converter.convert(str(ruta_archivo), page_range=(p_start, p_end))
                markdown = resultado.document.export_to_markdown()
                with open(cache_file, "w", encoding="utf-8") as f:
                    f.write(markdown)
            except Exception as e:
                # Si falla (ej. documento con menos páginas de las pedidas), intentar completo
                print(f"    ⚠ Fallo con page_range ({p_start}-{p_end}), intentando documento completo: {e}")
                try:
                    resultado = converter.convert(str(ruta_archivo))
                    markdown = resultado.document.export_to_markdown()
                    with open(cache_file, "w", encoding="utf-8") as f:
                        f.write(markdown)
                except Exception as e2:
                    markdown = f"ERROR: {e2}"
            latencia = time.perf_counter() - inicio

        # Parsear ítems de la sección/markdown
        items_pred = pre_anotar.parsear_items_desde_markdown(markdown)

        resultados.append({
            "archivo": archivo,
            "colegio": colegio,
            "items_gold": len(items_gs),
            "items_predichos": len(items_pred),
            "items_gold_data": items_gs,
            "items_pred_data": items_pred,
            "latencia_s": round(latencia, 4),
            "markdown_preview": markdown[:500] if isinstance(markdown, str) else "",
        })

        print(f"    -> {len(items_pred)} ítems extraídos ({latencia:.2f}s)")

    # Guardar resultados
    output_dir = base_dir / "resultados" / "docling"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "resultados_docling.json"

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
