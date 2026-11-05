"""
05_bench_lmm.py — Benchmark enfoque 3: LMM multimodal (GPT-4o / Claude / Gemini).

Envía cada página del documento como imagen a un LMM multimodal y le pide
extraer ítems en formato JSON. Mide P/R/F1 contra el gold standard.

Se evalúan costo por documento, latencia y privacidad.

Uso:
    python scripts/05_bench_lmm.py --provider openai [--model gpt-4o]
    python scripts/05_bench_lmm.py --provider anthropic [--model claude-sonnet-4-20250514]
    python scripts/05_bench_lmm.py --provider gemini [--model gemini-3.6-flash]
    python scripts/05_bench_lmm.py --provider local [--model qwen2.5]  # solo texto, referencia

Requisitos:
    OPENAI_API_KEY, ANTHROPIC_API_KEY o GEMINI_API_KEY en el entorno.
"""
import argparse
import base64
import json
import sys
import time
from pathlib import Path

PROMPT_SISTEMA = """Eres un asistente experto en listas de útiles escolares colombianas.
Tu tarea es extraer TODOS los ítems (artículos escolares) de la imagen proporcionada.

Emite UN SOLO objeto JSON con esta estructura exacta:
{"items": [{"descripcion": "<nombre del artículo>", "cantidad": <número entero>, "tipo": "<util|texto|uniforme|otro>"}]}

Reglas:
- Incluye TODOS los útiles, textos y materiales listados.
- La cantidad es la que pide la lista (un → 1, dos → 2). "x12" en el nombre del producto NO es la cantidad.
- "tipo" es "util" para papelería/arte, "texto" para libros, "uniforme" para ropa, "otro" para lo demás.
- Omite encabezados (nombre del colegio, grado, estudiante, fechas).
- Omite instrucciones/recomendaciones ("marcar con nombre", "comprar en...").
- NO inventes ítems que no estén en la imagen.
"""


def pdf_a_imagenes_base64(ruta: Path, max_paginas: int = 5) -> list[str]:
    """Convierte cada página de un PDF a imagen base64 (PNG)."""
    import fitz
    from PIL import Image
    import io

    imagenes = []
    with fitz.open(str(ruta)) as doc:
        for i, pagina in enumerate(doc):
            if i >= max_paginas:
                break
            # Render a 150 DPI (balance calidad/costo)
            matriz = fitz.Matrix(150 / 72, 150 / 72)
            pix = pagina.get_pixmap(matrix=matriz)
            img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)

            buffer = io.BytesIO()
            img.save(buffer, format="PNG", optimize=True)
            b64 = base64.b64encode(buffer.getvalue()).decode("utf-8")
            imagenes.append(b64)

    return imagenes


def extraer_items_openai(imagenes_b64: list[str], model: str = "gpt-4o") -> tuple[list[dict], float, float]:
    """Extrae ítems usando la API de OpenAI (multimodal)."""
    from openai import OpenAI
    from tenacity import retry, stop_after_attempt, wait_exponential

    client = OpenAI()
    items_total = []
    latencia_total = 0
    costo_total = 0

    @retry(wait=wait_exponential(multiplier=1.5, min=2, max=10), stop=stop_after_attempt(4))
    def _llamada_api(img_b64_str):
        return client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": PROMPT_SISTEMA},
                {"role": "user", "content": [
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{img_b64_str}", "detail": "high"}},
                    {"type": "text", "text": "Extrae todos los ítems de esta página de lista de útiles escolares."},
                ]},
            ],
            max_tokens=2000,
            temperature=0.0,
        )

    for img_b64 in imagenes_b64:
        inicio = time.perf_counter()
        
        try:
            response = _llamada_api(img_b64)
        except Exception as e:
            print(f"      ⚠ Error tras reintentos (OpenAI): {e}")
            continue

        latencia_total += time.perf_counter() - inicio

        # Estimar costo (precios aproximados GPT-4o)
        usage = response.usage
        if usage:
            costo_total += (usage.prompt_tokens * 0.0025 / 1000) + (usage.completion_tokens * 0.01 / 1000)

        contenido = response.choices[0].message.content or ""
        items = _parsear_json_items(contenido)
        items_total.extend(items)

    return items_total, latencia_total, costo_total


def extraer_items_anthropic(imagenes_b64: list[str], model: str = "claude-sonnet-4-20250514") -> tuple[list[dict], float, float]:
    """Extrae ítems usando la API de Anthropic (multimodal)."""
    import anthropic
    from tenacity import retry, stop_after_attempt, wait_exponential

    client = anthropic.Anthropic()
    items_total = []
    latencia_total = 0
    costo_total = 0

    @retry(wait=wait_exponential(multiplier=1.5, min=2, max=10), stop=stop_after_attempt(4))
    def _llamada_api(img_b64_str):
        return client.messages.create(
            model=model,
            max_tokens=2000,
            system=PROMPT_SISTEMA,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": img_b64_str}},
                    {"type": "text", "text": "Extrae todos los ítems de esta página de lista de útiles escolares."},
                ],
            }],
        )

    for img_b64 in imagenes_b64:
        inicio = time.perf_counter()
        
        try:
            response = _llamada_api(img_b64)
        except Exception as e:
            print(f"      ⚠ Error tras reintentos (Anthropic): {e}")
            continue

        latencia_total += time.perf_counter() - inicio

        # Estimar costo (precios aproximados Claude Sonnet)
        usage = response.usage
        if usage:
            costo_total += (usage.input_tokens * 0.003 / 1000) + (usage.output_tokens * 0.015 / 1000)

        contenido = response.content[0].text if response.content else ""
        items = _parsear_json_items(contenido)
        items_total.extend(items)

    return items_total, latencia_total, costo_total


def extraer_items_gemini(imagenes_b64: list[str], model: str = "gemini-3.5-flash-lite") -> tuple[list[dict], float, float]:
    """Extrae ítems usando la API de Google GenAI (multimodal)."""
    from google import genai
    from google.genai import types
    from google.genai.errors import APIError
    import os

    client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))
    items_total = []
    latencia_total = 0
    costo_total = 0

    for i, img_b64 in enumerate(imagenes_b64):
        inicio = time.perf_counter()
        
        image_part = types.Part.from_bytes(
            data=base64.b64decode(img_b64),
            mime_type='image/png',
        )

        max_reintentos = 15
        response = None
        for intento in range(max_reintentos):
            try:
                print(f"      - Página {i+1}/{len(imagenes_b64)} (Intento {intento+1})...", end="", flush=True)
                response = client.models.generate_content(
                    model=model,
                    contents=[
                        image_part,
                        "Extrae todos los ítems de esta página de lista de útiles escolares."
                    ],
                    config=types.GenerateContentConfig(
                        system_instruction=PROMPT_SISTEMA,
                        temperature=0.0,
                        max_output_tokens=2000,
                    )
                )
                print(" OK", flush=True)
                break
            except APIError as e:
                code = getattr(e, 'code', 0)
                if code == 429 or getattr(e, 'status', '') == 'RESOURCE_EXHAUSTED' or code == 503:
                    print(f" ⚠ Cuota excedida/503. Esperando 120s antes del próximo intento...", flush=True)
                    time.sleep(120)
                else:
                    print(f" ⚠ Error de API ({code}): {e}", flush=True)
                    time.sleep(30)
            except Exception as e:
                print(f" ⚠ Error general: {e}", flush=True)
                time.sleep(5)
        
        if not response:
            print(f"      ⚠ Falló la página {i+1} tras {max_reintentos} reintentos. Saltando.", flush=True)
            continue

        latencia_total += time.perf_counter() - inicio

        # Estimar costo (precios aproximados Gemini 3.6 Flash: $0.075 / 1M tokens input, $0.3 / 1M output)
        usage = response.usage_metadata
        if usage:
            costo_total += (usage.prompt_token_count * 0.075 / 1000000) + (usage.candidates_token_count * 0.3 / 1000000)

        contenido = response.text or ""
        items = _parsear_json_items(contenido)
        items_total.extend(items)
        
        # Dormir 6 segundos para no exceder límite gratuito (10 RPM)
        if i < len(imagenes_b64) - 1:
            time.sleep(6)

    return items_total, latencia_total, costo_total


def _parsear_json_items(contenido: str) -> list[dict]:
    """Parsea ítems desde la respuesta del LMM (busca JSON en el texto)."""
    import re

    # Buscar bloque JSON
    match = re.search(r'\{[\s\S]*"items"[\s\S]*\}', contenido)
    if match:
        try:
            data = json.loads(match.group())
            if isinstance(data.get("items"), list):
                return [
                    {
                        "descripcion": item.get("descripcion", ""),
                        "cantidad": int(item.get("cantidad", 1)),
                        "tipo": item.get("tipo", "util"),
                    }
                    for item in data["items"]
                    if item.get("descripcion")
                ]
        except (json.JSONDecodeError, ValueError):
            pass
    return []


def main():
    parser = argparse.ArgumentParser(description="Benchmark: LMM multimodal")
    parser.add_argument("--provider", required=True, choices=["openai", "anthropic", "local", "gemini"])
    parser.add_argument("--model", type=str, default=None)
    parser.add_argument("--gold-standard", type=Path, default=None)
    parser.add_argument("--max-docs", type=int, default=5,
                        help="Límite de documentos a procesar (controlar costos)")
    args = parser.parse_args()

    base_dir = Path(__file__).resolve().parent.parent

    # Cargar variables de entorno desde .env si existe
    env_path = base_dir / ".env"
    if env_path.exists():
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    os.environ.setdefault(k.strip(), v.strip())

    gs_path = args.gold_standard or base_dir / "corpus" / "gold_standard_construido.json"
    listas_dir = base_dir.parent / "TesisDocumentos" / "Listas"

    if not gs_path.exists():
        print(f"ERROR: Gold standard no encontrado: {gs_path}")
        sys.exit(1)

    with open(gs_path, "r", encoding="utf-8") as f:
        gold_standard = json.load(f)

    if args.model is None:
        args.model = {
            "openai": "gpt-4o",
            "anthropic": "claude-sonnet-4-20250514",
            "local": "qwen2.5-1.5b",
            "gemini": "gemini-3.5-flash-lite",
        }[args.provider]

    print(f"Evaluando enfoque 3: LMM multimodal ({args.provider} / {args.model})", flush=True)
    print(f"Límite de documentos: {args.max_docs}", flush=True)

    resultados = []
    costo_acumulado = 0

    for i, doc_gs in enumerate(gold_standard["documentos"]):
        if i >= args.max_docs:
            print(f"\n  ⚠ Límite de {args.max_docs} documentos alcanzado. Usa --max-docs para cambiar.")
            break

        archivo = doc_gs["archivo"]
        colegio = doc_gs.get("colegio", "")
        items_gs = doc_gs["items"]

        ruta_archivo = listas_dir / archivo
        if not ruta_archivo.exists():
            print(f"  ⚠ Archivo no encontrado: {ruta_archivo}")
            continue

        ext = ruta_archivo.suffix.lower()
        if ext != ".pdf":
            print(f"  ⚠ Solo PDFs soportados para LMM multimodal, saltando: {ext}")
            continue

        print(f"  [{i+1}/{min(len(gold_standard['documentos']), args.max_docs)}] {colegio}", flush=True)

        # Convertir PDF a imágenes
        imagenes_b64 = pdf_a_imagenes_base64(ruta_archivo)
        print(f"    → {len(imagenes_b64)} páginas", flush=True)

        # Extraer ítems según provider
        try:
            if args.provider == "openai":
                items_pred, latencia, costo = extraer_items_openai(imagenes_b64, args.model)
            elif args.provider == "anthropic":
                items_pred, latencia, costo = extraer_items_anthropic(imagenes_b64, args.model)
            elif args.provider == "gemini":
                items_pred, latencia, costo = extraer_items_gemini(imagenes_b64, args.model)
            else:
                print(f"    → Provider 'local' no soporta multimodal. Usa openai, anthropic o gemini.")
                items_pred, latencia, costo = [], 0, 0
        except Exception as e:
            print(f"    → Error general en provider: {e}", flush=True)
            items_pred, latencia, costo = [], 0, 0

        costo_acumulado += costo

        resultados.append({
            "archivo": archivo,
            "colegio": colegio,
            "provider": args.provider,
            "model": args.model,
            "items_gold": len(items_gs),
            "items_predichos": len(items_pred),
            "items_gold_data": items_gs,
            "items_pred_data": items_pred,
            "latencia_s": round(latencia, 4),
            "costo_usd": round(costo, 6),
            "paginas_procesadas": len(imagenes_b64),
        })

        print(f"    → {len(items_pred)} ítems, {latencia:.2f}s, ${costo:.4f}", flush=True)
        
        # Pausa extra entre documentos
        time.sleep(2)

    # Guardar resultados
    output_dir = base_dir / "resultados" / "lmm"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"resultados_lmm_{args.provider}.json"

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(resultados, f, ensure_ascii=False, indent=2)

    print(f"\n=== RESUMEN ===")
    print(f"Provider: {args.provider} / {args.model}")
    print(f"Documentos evaluados: {len(resultados)}")
    print(f"Costo total: ${costo_acumulado:.4f}")

    total_gold = sum(r["items_gold"] for r in resultados)
    total_pred = sum(r["items_predichos"] for r in resultados)
    lat_avg = sum(r["latencia_s"] for r in resultados) / max(len(resultados), 1)
    print(f"Total ítems gold: {total_gold}")
    print(f"Total ítems predichos: {total_pred}")
    print(f"Latencia promedio: {lat_avg:.4f}s")
    print(f"\nResultados guardados en: {output_path}")


if __name__ == "__main__":
    main()
